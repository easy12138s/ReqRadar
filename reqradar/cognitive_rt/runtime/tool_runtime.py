"""ToolRuntime — 工具管控中间层，为所有工具调用提供统一的超时、重试、权限、
Checkpoint、事件和缓存六项管控能力。

设计参考：docs/detailed/R-04_TOOL_RUNTIME.md、docs/adr/014-tool-runtime.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from reqradar.cognitive_rt.cognition.tools.security import ToolPermissionChecker
from reqradar.cognitive_rt.runtime.checkpoint import StateSummary
from reqradar.kernel.enums import CheckpointType, EventLevel, EventType
from reqradar.kernel.exceptions import ReqRadarException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 枚举与数据模型
# ---------------------------------------------------------------------------


class ToolCategory(str, Enum):
    """工具分类 — 决定默认管控策略。"""

    READ_ONLY = "read_only"
    WRITE = "write"
    STATEFUL = "stateful"
    EXTERNAL = "external"


class RetryPolicy(BaseModel):
    """重试策略配置。"""

    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    initial_backoff: float = Field(default=1.0, ge=0.1, le=60.0, description="初始退避间隔（秒）")
    max_backoff: float = Field(default=30.0, ge=1.0, le=300.0, description="最大退避间隔（秒）")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0, description="退避倍数")
    jitter: bool = Field(default=True, description="是否添加随机抖动")


class RateLimitConfig(BaseModel):
    """速率限制配置。"""

    max_calls: int = Field(default=60, ge=1, description="时间窗口内最大调用次数")
    window_seconds: int = Field(default=60, ge=1, description="时间窗口（秒）")


class ToolCapability(BaseModel):
    """工具能力声明 — 描述工具的元数据和管控需求。"""

    tool_id: str = Field(description="工具唯一标识，与 BaseTool.name 一致")
    name: str = Field(description="工具显示名称")
    description: str = Field(description="工具功能描述")
    category: ToolCategory = Field(description="工具分类")
    timeout: float = Field(default=30.0, ge=1.0, le=600.0, description="默认超时时间（秒）")
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy, description="重试策略")
    required_scopes: list[str] = Field(
        default_factory=list, description="所需权限范围列表（格式 scope:domain）"
    )
    requires_checkpoint: bool = Field(default=False, description="是否需要执行前后自动 Checkpoint")
    cache_ttl: int = Field(default=0, ge=0, description="结果缓存 TTL（秒），0 不缓存")
    rate_limit: RateLimitConfig | None = Field(default=None, description="速率限制，None 不限速")
    idempotent: bool = Field(default=False, description="是否幂等（幂等工具可安全重试）")


# ---------------------------------------------------------------------------
# 增强的 ToolResult
# ---------------------------------------------------------------------------


@dataclass
class ManagedToolResult:
    """V2 管控工具结果 — 在 V1 ToolResult 基础上增加管控元数据。"""

    success: bool
    data: str
    error: str = ""
    truncated: bool = False
    tool_id: str = ""
    execution_id: str = ""
    duration_ms: float = 0.0
    retry_count: int = 0
    from_cache: bool = False
    checkpoint_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# 异常层次
# ---------------------------------------------------------------------------


class ToolRuntimeError(ReqRadarException):
    """ToolRuntime 基础异常。"""

    def __init__(
        self,
        message: str,
        tool_id: str = "",
        execution_id: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.tool_id = tool_id
        self.execution_id = execution_id


class ToolNotFoundError(ToolRuntimeError):
    """工具未注册。"""


class ToolPermissionDeniedError(ToolRuntimeError):
    """权限不足。"""


class ToolTimeoutError(ToolRuntimeError):
    """执行超时。"""

    def __init__(
        self,
        message: str,
        tool_id: str = "",
        execution_id: str = "",
        timeout: float = 0.0,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, tool_id, execution_id, cause)
        self.timeout = timeout


class ToolRetryExhaustedError(ToolRuntimeError):
    """重试次数耗尽。"""

    def __init__(
        self,
        message: str,
        tool_id: str = "",
        execution_id: str = "",
        retry_count: int = 0,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, tool_id, execution_id, cause)
        self.retry_count = retry_count


class ToolRateLimitError(ToolRuntimeError):
    """速率限制。"""


# ---------------------------------------------------------------------------
# 限流器
# ---------------------------------------------------------------------------


class SlidingWindowRateLimiter:
    """基于滑动窗口的速率限制器（进程内实现）。"""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def acquire(self) -> bool:
        """尝试获取执行许可。返回 True 表示允许执行。"""
        now = time.monotonic()
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max_requests:
            return False
        self._timestamps.append(now)
        return True


# ---------------------------------------------------------------------------
# 结果缓存
# ---------------------------------------------------------------------------


class ToolResultCache:
    """LRU 结果缓存。"""

    def __init__(self, max_size: int = 256) -> None:
        from collections import OrderedDict

        self._max_size = max_size
        self._cache: OrderedDict[str, tuple[ManagedToolResult, float]] = OrderedDict()

    def get(self, key: str, ttl: int) -> ManagedToolResult | None:
        """获取缓存结果。"""
        if key not in self._cache:
            return None
        result, ts = self._cache[key]
        if time.monotonic() - ts > ttl:
            del self._cache[key]
            return None
        # LRU: 移动到末尾
        self._cache.move_to_end(key)
        result.from_cache = True
        return result

    def put(self, key: str, result: ManagedToolResult) -> None:
        """写入缓存。"""
        if key in self._cache:
            # 已存在，更新并移动到末尾
            self._cache.move_to_end(key)
        elif len(self._cache) >= self._max_size:
            # 缓存满，淘汰最久未使用的（第一个）
            self._cache.popitem(last=False)
        self._cache[key] = (result, time.monotonic())

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()


# ---------------------------------------------------------------------------
# ToolRuntime 核心
# ---------------------------------------------------------------------------


class ToolRuntime:
    """工具管控中间层 — 所有工具调用的统一入口。

    实现五阶段执行流程：
    Phase 1 - 权限校验
    Phase 2 - 限流检查
    Phase 3 - Checkpoint 前置
    Phase 4 - 执行工具（含超时 + 重试）
    Phase 5 - Checkpoint 后置 + 事件记录
    """

    def __init__(
        self,
        registry: object,
        event_publisher: object | None = None,
        checkpoint_mgr: object | None = None,
        permission_checker: ToolPermissionChecker | None = None,
        capabilities: dict[str, ToolCapability] | None = None,
    ) -> None:
        """初始化 ToolRuntime。

        Args:
            registry: 工具注册表（需有 get/list_names 方法）
            event_publisher: 事件发布器（可选，需有 publish 方法）
            checkpoint_mgr: Checkpoint 管理器（可选，需有 create_checkpoint 方法）
            permission_checker: 权限检查器
            capabilities: 工具能力声明映射 {tool_id: ToolCapability}
        """
        self._registry = registry
        self._publisher = event_publisher
        self._checkpoint_mgr = checkpoint_mgr
        self._permission_checker = permission_checker or ToolPermissionChecker()
        self._capabilities = capabilities or {}
        self._rate_limiters: dict[str, SlidingWindowRateLimiter] = {}
        self._cache = ToolResultCache()

    async def execute(
        self,
        tool_id: str,
        params: dict | None = None,
        session_id: str = "",
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        skip_cache: bool = False,
        skip_checkpoint: bool = False,
    ) -> ManagedToolResult:
        """执行工具调用，经过完整的管控流程。

        Args:
            tool_id: 工具标识
            params: 工具执行参数
            session_id: 当前 Session ID
            timeout: 调用级超时覆盖
            max_retries: 调用级重试次数覆盖
            skip_cache: 是否跳过缓存
            skip_checkpoint: 是否跳过 Checkpoint

        Returns:
            ManagedToolResult 管控结果
        """
        params = params or {}
        execution_id = str(uuid4())
        start_time = time.monotonic()

        # Phase 0: 查找工具和能力声明
        tool = self._registry.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(
                message=f"工具未注册: {tool_id}",
                tool_id=tool_id,
                execution_id=execution_id,
            )

        capability = self._capabilities.get(tool_id)
        if capability is None:
            # 使用默认能力声明
            capability = ToolCapability(
                tool_id=tool_id,
                name=tool_id,
                description=getattr(tool, "description", ""),
                category=ToolCategory.READ_ONLY,
            )

        effective_timeout = timeout or capability.timeout
        effective_max_retries = (
            max_retries if max_retries is not None else capability.retry_policy.max_retries
        )

        # Phase 1: 权限校验
        try:
            if capability.required_scopes:
                allowed, missing = self._permission_checker.check_tool(capability.required_scopes)
                if not allowed:
                    self._publish_event(
                        session_id,
                        EventType.TOOL_PERMISSION_DENIED,
                        {"tool_id": tool_id, "missing": missing},
                    )
                    return ManagedToolResult(
                        success=False,
                        data="",
                        error=f"权限不足: 缺少 {missing}",
                        tool_id=tool_id,
                        execution_id=execution_id,
                        duration_ms=(time.monotonic() - start_time) * 1000,
                    )
        except Exception as e:
            logger.warning("权限校验异常，降级继续: %s", e)

        # Phase 2: 限流检查
        try:
            if capability.rate_limit is not None:
                limiter = self._get_rate_limiter(tool_id, capability.rate_limit)
                if not limiter.acquire():
                    self._publish_event(
                        session_id,
                        EventType.TOOL_PERMISSION_DENIED,
                        {"tool_id": tool_id, "reason": "rate_limit"},
                    )
                    return ManagedToolResult(
                        success=False,
                        data="",
                        error=f"速率限制: {tool_id} 超过 {capability.rate_limit.max_calls}/{capability.rate_limit.window_seconds}s",
                        tool_id=tool_id,
                        execution_id=execution_id,
                        duration_ms=(time.monotonic() - start_time) * 1000,
                    )
        except Exception as e:
            logger.warning("限流检查异常，降级继续: %s", e)

        # 缓存检查
        cache_key = ""
        if not skip_cache and capability.cache_ttl > 0:
            # 使用 json.dumps 处理嵌套 dict，生成稳定的缓存 key
            params_str = json.dumps(params, sort_keys=True, default=str)
            cache_key = f"{tool_id}:{params_str}"
            cached = self._cache.get(cache_key, capability.cache_ttl)
            if cached is not None:
                cached.execution_id = execution_id
                return cached

        # Phase 3: Checkpoint 前置
        pre_checkpoint_id = None
        if (
            not skip_checkpoint
            and capability.requires_checkpoint
            and self._checkpoint_mgr is not None
        ):
            try:
                cp = self._checkpoint_mgr.create_checkpoint(
                    session_id=session_id,
                    checkpoint_type=CheckpointType.TOOL_PRE,
                    state_summary=StateSummary(
                        dimension_status={"tool_id": tool_id, "params_keys": list(params.keys())},
                    ),
                )
                pre_checkpoint_id = cp.checkpoint_id if hasattr(cp, "checkpoint_id") else str(cp)
            except Exception as e:
                logger.warning("前置 Checkpoint 创建失败，降级继续: %s", e)
                self._publish_event(
                    session_id,
                    EventType.TOOL_CHECKPOINT_FAILED,
                    {"tool_id": tool_id, "error": str(e)},
                )

        # Phase 4: 发布 TOOL_INVOKED 事件
        self._publish_event(
            session_id,
            EventType.TOOL_INVOKED,
            {"tool_id": tool_id, "execution_id": execution_id, "params_keys": list(params.keys())},
        )

        # Phase 4: 执行循环（超时 + 重试）
        last_error: Exception | None = None
        retry_count = 0
        result_data = ""
        result_success = False
        result_error = ""

        for attempt in range(effective_max_retries + 1):
            try:
                raw_result = await asyncio.wait_for(
                    tool.execute(**params),
                    timeout=effective_timeout,
                )
                result_data = raw_result.data if hasattr(raw_result, "data") else str(raw_result)
                result_success = raw_result.success if hasattr(raw_result, "success") else True
                result_error = raw_result.error if hasattr(raw_result, "error") else ""
                last_error = None
                break

            except asyncio.TimeoutError as e:
                last_error = e
                retry_count = attempt
                if attempt < effective_max_retries:
                    backoff = self._compute_backoff(attempt, capability.retry_policy)
                    self._publish_event(
                        session_id,
                        EventType.TOOL_RETRY,
                        {
                            "tool_id": tool_id,
                            "attempt": attempt + 1,
                            "error": "timeout",
                            "backoff": backoff,
                        },
                    )
                    await asyncio.sleep(backoff)
                else:
                    self._publish_event(
                        session_id,
                        EventType.TOOL_TIMEOUT,
                        {"tool_id": tool_id, "timeout": effective_timeout},
                    )

            except Exception as e:
                last_error = e
                retry_count = attempt
                if attempt < effective_max_retries:
                    backoff = self._compute_backoff(attempt, capability.retry_policy)
                    self._publish_event(
                        session_id,
                        EventType.TOOL_RETRY,
                        {
                            "tool_id": tool_id,
                            "attempt": attempt + 1,
                            "error": str(e)[:200],
                            "backoff": backoff,
                        },
                    )
                    await asyncio.sleep(backoff)
                else:
                    result_error = f"重试耗尽 ({attempt + 1} 次): {e}"

        duration_ms = (time.monotonic() - start_time) * 1000

        # 构造结果
        if last_error is not None:
            result_success = False
            if not result_error:
                result_error = str(last_error)

        managed_result = ManagedToolResult(
            success=result_success,
            data=result_data,
            error=result_error,
            tool_id=tool_id,
            execution_id=execution_id,
            duration_ms=duration_ms,
            retry_count=retry_count,
            checkpoint_id=pre_checkpoint_id,
        )

        # 缓存写入
        if not skip_cache and capability.cache_ttl > 0 and result_success and cache_key:
            self._cache.put(cache_key, managed_result)

        # Phase 5: Checkpoint 后置
        if (
            not skip_checkpoint
            and capability.requires_checkpoint
            and self._checkpoint_mgr is not None
        ):
            try:
                self._checkpoint_mgr.create_checkpoint(
                    session_id=session_id,
                    checkpoint_type=CheckpointType.TOOL_POST,
                    state_summary=StateSummary(
                        dimension_status={
                            "tool_id": tool_id,
                            "success": result_success,
                            "duration_ms": duration_ms,
                        },
                    ),
                )
            except Exception as e:
                logger.warning("后置 Checkpoint 创建失败，降级继续: %s", e)

        # Phase 5: 发布 TOOL_RETURNED 事件
        self._publish_event(
            session_id,
            EventType.TOOL_RETURNED,
            {
                "tool_id": tool_id,
                "execution_id": execution_id,
                "success": result_success,
                "duration_ms": round(duration_ms, 2),
                "retry_count": retry_count,
            },
        )

        return managed_result

    def register_capability(self, capability: ToolCapability) -> None:
        """注册工具能力声明。"""
        self._capabilities[capability.tool_id] = capability

    def get_capability(self, tool_id: str) -> ToolCapability | None:
        """获取工具能力声明。"""
        return self._capabilities.get(tool_id)

    def _get_rate_limiter(self, tool_id: str, config: RateLimitConfig) -> SlidingWindowRateLimiter:
        """获取或创建限流器。"""
        if tool_id not in self._rate_limiters:
            self._rate_limiters[tool_id] = SlidingWindowRateLimiter(
                max_requests=config.max_calls,
                window_seconds=config.window_seconds,
            )
        return self._rate_limiters[tool_id]

    @staticmethod
    def _compute_backoff(attempt: int, policy: RetryPolicy) -> float:
        """计算指数退避时间。"""
        backoff = min(
            policy.initial_backoff * (policy.backoff_multiplier**attempt),
            policy.max_backoff,
        )
        if policy.jitter:
            backoff = backoff * (0.5 + random.random() * 0.5)
        return backoff

    def _publish_event(self, session_id: str, event_type: str, payload: dict) -> None:
        """发布事件（降级安全）。"""
        if self._publisher is None or not session_id:
            return
        try:
            self._publisher.publish(
                session_id=session_id,
                event_type=event_type,
                event_level=EventLevel.COGNITIVE,
                producer="tool_runtime",
                payload=payload,
            )
        except Exception as e:
            logger.warning("事件发布失败，降级继续: %s", e)
