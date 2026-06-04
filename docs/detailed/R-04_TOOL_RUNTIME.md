# R-04 ToolRuntime 详细设计

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ToolRuntime（工具运行时）详细设计规格 |
| 前置文档 | 01_RESTRUCTURE_OVERVIEW.md（6.3 ToolRuntime）、02_SYSTEM_ARCHITECTURE.md（4.4 ToolRuntime）、04_IMPLEMENTATION_ROADMAP.md（P4 ToolRuntime） |
| 核心目标 | 定义工具执行的管控中间层，在工具注册表之上增加超时控制、重试策略、权限校验、Checkpoint 记录、事件记录、结果缓存六项管控能力 |
| 文档职责 | What & How — ToolRuntime 的数据模型、接口定义、执行流程、管控策略、迁移方案的完整规格 |

---

## 2. 概述

### 2.1 ToolRuntime 在 V2 中的定位

ToolRuntime 是 Cognition Layer 的核心组件之一，位于工具注册表（ToolRegistry）之上，为工具调用增加统一的管控中间层。

```
ReAct Agent
    │
    ▼
ToolRuntime（管控中间层）
    │  超时控制 / 重试策略 / 权限校验 / Checkpoint / 事件记录 / 结果缓存
    ▼
ToolRegistry（工具注册表）
    │
    ▼
BaseTool 实现类（search_code / read_file / get_dependencies / ...）
```

V1 中工具调用路径为：Agent → ToolRegistry → BaseTool.execute()。V2 在 Agent 和 ToolRegistry 之间插入 ToolRuntime，所有工具调用必须经过 ToolRuntime.execute()，由 ToolRuntime 统一执行管控逻辑。

### 2.2 设计原则

| 原则 | 说明 |
|------|------|
| 不改变工具实现 | BaseTool 子类的 execute() 方法保持不变，ToolRuntime 只在外层增加管控 |
| 声明式能力描述 | 每个工具通过 ToolCapability 声明自身元数据，ToolRuntime 据此执行管控 |
| 调用级可覆盖 | 工具级默认配置可被单次调用参数覆盖（如超时时间） |
| 事件自动记录 | 工具调用的 TOOL_INVOKED / TOOL_RETURNED 事件由 ToolRuntime 自动发布，工具实现无需关心 |
| 失败安全 | 管控逻辑本身异常不应导致工具调用失败，应降级为直接执行 |

---

## 3. 核心概念

### 3.1 ToolRuntime 的本质

ToolRuntime 不改变工具的实现方式，只增加管控能力。它是一个横切关注点的统一处理层：

- **Before 执行**：权限校验、缓存检查、Checkpoint 前置记录
- **During 执行**：超时控制
- **After 执行**：重试判断、事件记录、缓存写入、Checkpoint 后置记录

工具开发者只需实现 `BaseTool.execute()` 并声明 `ToolCapability`，无需关心超时、重试、权限等横切逻辑。

### 3.2 能力声明（Capability Declaration）

每个工具在注册时必须附带一份 ToolCapability 声明，描述该工具的元数据和管控需求。ToolRuntime 读取这些声明来决定管控策略。

能力声明与工具实现分离的好处：
- 同一工具在不同场景下可使用不同的能力声明
- 能力声明可动态更新（如调整超时时间），无需修改工具代码
- 能力声明是权限审计和治理的基础数据

### 3.3 执行管控

ToolRuntime 的六项管控能力按执行阶段组织：

| 阶段 | 管控能力 | 说明 |
|------|---------|------|
| 执行前 | 权限校验 | 基于 Scope x Domain 矩阵检查调用者是否有权使用该工具 |
| 执行前 | 缓存检查 | 相同参数的短期结果可直接返回，避免重复执行 |
| 执行前 | Checkpoint 前置 | requires_checkpoint=True 的工具执行前自动创建快照 |
| 执行中 | 超时控制 | asyncio.wait_for 强制超时中断 |
| 执行后 | 重试策略 | 可重试错误自动按指数退避重试 |
| 执行后 | 事件记录 | 自动发布 TOOL_INVOKED / TOOL_RETURNED 事件 |
| 执行后 | 缓存写入 | 成功结果按参数哈希写入短期缓存 |
| 执行后 | Checkpoint 后置 | requires_checkpoint=True 的工具执行后自动创建快照 |

---

## 4. ToolCapability 声明 Schema

### 4.1 Pydantic 模型定义

```python
from enum import Enum
from pydantic import BaseModel, Field


class ToolCategory(str, Enum):
    """工具分类"""
    READ_ONLY = "read_only"
    WRITE = "write"
    STATEFUL = "stateful"
    EXTERNAL = "external"


class RetryPolicy(BaseModel):
    """重试策略配置"""
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    initial_backoff: float = Field(default=1.0, ge=0.1, le=60.0, description="初始退避间隔（秒）")
    max_backoff: float = Field(default=30.0, ge=1.0, le=300.0, description="最大退避间隔（秒）")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0, description="退避倍数")
    jitter: bool = Field(default=True, description="是否添加随机抖动")


class RateLimitConfig(BaseModel):
    """速率限制配置"""
    max_calls: int = Field(default=60, ge=1, description="时间窗口内最大调用次数")
    window_seconds: int = Field(default=60, ge=1, description="时间窗口（秒）")


**速率限制实现方案**：

Phase 1（P4）采用基于进程内滑动窗口的实现：

```python
class SlidingWindowRateLimiter:
    """基于滑动窗口的速率限制器（进程内实现）"""

    def __init__(self, max_requests: int, window_seconds: int):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    async def acquire(self, tool_id: str) -> bool:
        """尝试获取执行许可，返回 True 表示允许执行"""
        now = time.monotonic()
        cutoff = now - self._window_seconds
        # 清理过期时间戳
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max_requests:
            return False
        self._timestamps.append(now)
        return True
```

| 参数 | 说明 |
|------|------|
| 实现方式 | 进程内滑动窗口（`collections.deque`） |
| 存储 | 进程内存，不持久化 |
| 多 Worker | P4 阶段单 Worker 部署，无需跨进程同步 |
| P5 升级 | 迁移到 Redis Sorted Set 实现分布式滑动窗口 |

**限流行为**：

| 场景 | 行为 |
|------|------|
| 请求在窗口内未超限 | 正常执行 |
| 请求在窗口内超限 | 返回 `ToolRateLimitError`，不重试 |
| 限流器配置为 None | 不限流 |


class ToolCapability(BaseModel):
    """工具能力声明"""
    tool_id: str = Field(description="工具唯一标识，与 BaseTool.name 一致")
    name: str = Field(description="工具显示名称")
    description: str = Field(description="工具功能描述")
    category: ToolCategory = Field(description="工具分类")
    timeout: float = Field(default=30.0, ge=1.0, le=600.0, description="默认超时时间（秒）")
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy, description="重试策略")
    required_scopes: list[str] = Field(default_factory=list, description="所需权限范围列表")
    requires_checkpoint: bool = Field(default=False, description="是否需要执行前后自动 Checkpoint")
    cache_ttl: int = Field(default=0, ge=0, description="结果缓存 TTL（秒），0 表示不缓存")
    rate_limit: RateLimitConfig | None = Field(default=None, description="速率限制，None 表示不限速")
    idempotent: bool = Field(default=False, description="是否幂等（幂等工具可安全重试）")
    deprecated: bool = Field(default=False, description="是否已废弃")
    replacement: str | None = Field(default=None, description="废弃时的替代工具 ID")
```

### 4.2 工具分类语义

| 分类 | 含义 | 典型工具 | 管控差异 |
|------|------|---------|---------|
| `READ_ONLY` | 只读操作，不修改任何状态 | search_code, read_file, list_modules | 无需 Checkpoint，可缓存，可安全重试 |
| `WRITE` | 写入操作，修改系统状态 | 暂无（预留） | 需要 Checkpoint，不可缓存，需审慎重试 |
| `STATEFUL` | 有状态操作，依赖或修改运行时状态 | get_dependencies（依赖内存数据） | 需要 Checkpoint，缓存 TTL 较短 |
| `EXTERNAL` | 调用外部服务 | search_git_history（依赖向量存储） | 超时较长，重试策略更激进，缓存视场景而定 |

### 4.3 字段语义与约束

| 字段 | 语义 | 约束 | 默认值 |
|------|------|------|--------|
| `tool_id` | 工具唯一标识，必须与 BaseTool.name 精确匹配 | 非空，全局唯一，注册时校验 | 无（必填） |
| `name` | 人类可读的显示名称 | 非空 | 无（必填） |
| `description` | 功能描述，用于审计和文档 | 非空 | 无（必填） |
| `category` | 工具分类，决定默认管控策略 | 枚举值 | 无（必填） |
| `timeout` | 工具执行的最大等待时间 | 1.0 ~ 600.0 秒 | 30.0 |
| `retry_policy` | 重试策略，控制失败后的重试行为 | 见 RetryPolicy 字段 | max_retries=3, initial_backoff=1.0 |
| `required_scopes` | 调用此工具所需的权限范围 | 格式为 `scope:domain`，如 `read:code` | 空列表（无权限要求） |
| `requires_checkpoint` | 是否在执行前后自动创建 Checkpoint | 仅 STATEFUL/WRITE 类工具建议设为 True | False |
| `cache_ttl` | 结果缓存的存活时间 | 0 = 不缓存；READ_ONLY 工具建议 > 0 | 0 |
| `rate_limit` | 速率限制配置 | None = 不限速 | None |
| `idempotent` | 幂等性标记 | 幂等工具可安全重试，非幂等工具重试需谨慎 | False |
| `deprecated` | 废弃标记 | 废弃工具调用时记录警告事件 | False |
| `replacement` | 废弃时的替代工具 ID | 仅 deprecated=True 时有效 | None |

---

## 5. ToolRuntime 接口详细设计

### 5.1 ToolRuntime.execute() 完整接口签名

```python
class ToolRuntime:
    async def execute(
        self,
        tool_id: str,
        params: dict,
        session: CognitiveSession,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        skip_cache: bool = False,
        skip_checkpoint: bool = False,
    ) -> ToolResult:
        """
        执行工具调用，经过完整的管控流程。

        参数:
            tool_id: 工具标识，对应 ToolCapability.tool_id
            params: 工具执行参数，传递给 BaseTool.execute()
            session: 当前认知会话，用于权限校验和事件发布
            timeout: 调用级超时覆盖（秒），None 使用工具默认值
            max_retries: 调用级重试次数覆盖，None 使用工具默认值
            skip_cache: 是否跳过缓存读写
            skip_checkpoint: 是否跳过 Checkpoint 记录

        返回:
            ToolResult: 工具执行结果

        异常:
            ToolNotFoundError: 工具未注册
            ToolPermissionDeniedError: 权限不足
            ToolTimeoutError: 执行超时
            ToolRetryExhaustedError: 重试次数耗尽
            ToolExecutionError: 工具内部错误
        """
        ...
```

### 5.2 ToolResult 数据模型

V2 的 ToolResult 在 V1 基础上增加管控元数据：

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: str
    error: str = ""
    truncated: bool = False

    # V2 新增管控元数据
    tool_id: str = ""
    execution_id: str = ""
    duration_ms: float = 0.0
    retry_count: int = 0
    from_cache: bool = False
    checkpoint_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

| 字段 | 语义 |
|------|------|
| `success` | 工具是否执行成功 |
| `data` | 工具返回的数据（文本形式） |
| `error` | 错误信息，成功时为空 |
| `truncated` | 返回数据是否被截断 |
| `tool_id` | 执行的工具 ID |
| `execution_id` | 本次执行的唯一标识（UUID），用于事件关联 |
| `duration_ms` | 实际执行耗时（毫秒），不含重试等待 |
| `retry_count` | 本次调用实际重试次数 |
| `from_cache` | 结果是否来自缓存 |
| `checkpoint_id` | 执行前创建的 Checkpoint ID（仅 requires_checkpoint=True 时有值） |
| `timestamp` | 执行完成时间戳 |

### 5.3 ToolExecutionError 异常层次

```python
class ToolExecutionError(ReqRadarException):
    """工具执行错误基类"""
    def __init__(
        self,
        message: str,
        tool_id: str = "",
        execution_id: str = "",
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.tool_id = tool_id
        self.execution_id = execution_id


class ToolNotFoundError(ToolExecutionError):
    """工具未注册"""


class ToolPermissionDeniedError(ToolExecutionError):
    """权限不足，缺少 required_scopes 中的权限"""


class ToolTimeoutError(ToolExecutionError):
    """执行超时"""
    def __init__(
        self,
        message: str,
        tool_id: str = "",
        execution_id: str = "",
        timeout: float = 0.0,
        cause: Exception | None = None,
    ):
        super().__init__(message, tool_id, execution_id, cause)
        self.timeout = timeout


class ToolRetryExhaustedError(ToolExecutionError):
    """重试次数耗尽"""
    def __init__(
        self,
        message: str,
        tool_id: str = "",
        execution_id: str = "",
        retry_count: int = 0,
        last_error: Exception | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, tool_id, execution_id, cause)
        self.retry_count = retry_count
        self.last_error = last_error


class ToolCheckpointError(ToolExecutionError):
    """Checkpoint 创建失败（降级为无 Checkpoint 继续执行）"""
```

### 5.4 execute() 完整执行流程

```
ToolRuntime.execute(tool_id, params, session, ...)
│
├── 1. 查找工具
│   ├── 从 ToolRegistry 获取 BaseTool 实例
│   ├── 从 CapabilityRegistry 获取 ToolCapability 声明
│   └── 工具不存在 → 抛出 ToolNotFoundError
│
├── 2. 权限校验
│   ├── 读取 session 的权限上下文
│   ├── 检查 session.scopes 是否包含 capability.required_scopes
│   └── 权限不足 → 抛出 ToolPermissionDeniedError
│
├── 3. 缓存检查（skip_cache=False 且 cache_ttl > 0）
│   ├── 计算参数哈希 cache_key = hash(tool_id + sorted(params))
│   ├── 命中缓存且未过期 → 返回 ToolResult(from_cache=True)
│   └── 未命中 → 继续
│
├── 4. Checkpoint 前置（requires_checkpoint=True 且 skip_checkpoint=False）
│   ├── 创建 pre-execution Checkpoint
│   ├── Checkpoint 创建失败 → 记录 ToolCheckpointError 事件，降级继续
│   └── 记录 checkpoint_id
│
├── 5. 发布 TOOL_INVOKED 事件
│
├── 6. 执行循环（含超时和重试）
│   ├── 6a. 计算有效超时 = timeout_override ?? capability.timeout
│   ├── 6b. asyncio.wait_for(tool.execute(**params), timeout=effective_timeout)
│   ├── 6c. 执行成功 → 跳出循环
│   ├── 6d. 超时 → asyncio.TimeoutError
│   │   ├── 可重试且未达上限 → 等待退避时间后重试
│   │   └── 不可重试或已达上限 → 抛出 ToolTimeoutError
│   ├── 6e. 工具内部错误
│   │   ├── 可重试且未达上限 → 等待退避时间后重试
│   │   └── 不可重试或已达上限 → 抛出 ToolRetryExhaustedError
│   └── 6f. 每次重试前发布 TOOL_RETRY 事件
│
├── 7. 构造 ToolResult（填充管控元数据）
│
├── 8. 缓存写入（skip_cache=False 且 cache_ttl > 0 且 success=True）
│
├── 9. Checkpoint 后置（requires_checkpoint=True 且 skip_checkpoint=False）
│   ├── 创建 post-execution Checkpoint
│   └── Checkpoint 创建失败 → 记录事件，不影响结果返回
│
├── 10. 发布 TOOL_RETURNED 事件
│
└── 11. 返回 ToolResult
```

---

## 6. 超时控制

### 6.1 实现方案

使用 `asyncio.wait_for()` 实现超时控制：

```python
import asyncio


async def _execute_with_timeout(
    tool: BaseTool,
    params: dict,
    timeout: float,
) -> ToolResult:
    try:
        return await asyncio.wait_for(
            tool.execute(**params),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise ToolTimeoutError(
            message=f"工具 '{tool.name}' 执行超时（{timeout}s）",
            tool_id=tool.name,
            timeout=timeout,
        )
```

### 6.2 超时后的清理逻辑

`asyncio.wait_for()` 超时后会自动取消底层 Task。但某些工具可能持有外部资源（如文件句柄、网络连接），需要额外清理：

```python
class ToolRuntime:
    async def _execute_with_cleanup(
        self,
        tool: BaseTool,
        params: dict,
        timeout: float,
    ) -> ToolResult:
        task = asyncio.create_task(tool.execute(**params))
        try:
            return await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # 调用工具的清理方法（如果实现）
            if hasattr(tool, "cleanup"):
                try:
                    await tool.cleanup()
                except Exception:
                    pass

            raise ToolTimeoutError(
                message=f"工具 '{tool.name}' 执行超时（{timeout}s），已取消并清理",
                tool_id=tool.name,
                timeout=timeout,
            )
```

BaseTool 可选实现 `async def cleanup()` 方法，用于超时后的资源释放。未实现则跳过。

### 6.3 超时时间配置

超时时间的优先级：

```
调用级 timeout 参数 > ToolCapability.timeout > 全局默认值（30s）
```

| 配置层级 | 来源 | 优先级 | 说明 |
|---------|------|--------|------|
| 调用级 | `execute(timeout=60.0)` | 最高 | 单次调用临时覆盖 |
| 工具级 | `ToolCapability.timeout` | 中 | 工具声明的默认超时 |
| 全局级 | `ToolRuntimeConfig.default_timeout` | 最低 | 全局兜底默认值 |

各工具分类的推荐默认超时：

| 分类 | 推荐超时 | 理由 |
|------|---------|------|
| READ_ONLY | 15s | 只读操作通常较快 |
| WRITE | 30s | 写入操作可能涉及持久化 |
| STATEFUL | 30s | 有状态操作可能涉及内存计算 |
| EXTERNAL | 60s | 外部服务调用延迟不可控 |

---

## 7. 重试策略

### 7.1 指数退避算法

```python
import random


def calculate_backoff(
    attempt: int,
    policy: RetryPolicy,
) -> float:
    """
    计算第 N 次重试的等待时间。

    算法: backoff = min(initial_backoff * multiplier^attempt, max_backoff)
    如果 jitter=True，在计算结果上添加 [0, 0.5 * backoff] 的随机抖动。
    """
    backoff = min(
        policy.initial_backoff * (policy.backoff_multiplier ** attempt),
        policy.max_backoff,
    )
    if policy.jitter:
        backoff = backoff + random.uniform(0, backoff * 0.5)
    return backoff
```

退避时间示例（initial_backoff=1.0, multiplier=2.0, max_backoff=30.0, jitter=False）：

| 重试次数 | 退避时间 | 累计等待 |
|---------|---------|---------|
| 1 | 1.0s | 1.0s |
| 2 | 2.0s | 3.0s |
| 3 | 4.0s | 7.0s |
| 4 | 8.0s | 15.0s |
| 5 | 16.0s | 31.0s |
| 6 | 30.0s（封顶） | 61.0s |

### 7.2 可重试条件判断

并非所有错误都应该重试。重试判断逻辑：

```python
def is_retryable(error: Exception, capability: ToolCapability) -> bool:
    """判断错误是否可重试"""
    # 非幂等工具不重试（除非是超时类错误）
    if not capability.idempotent and not isinstance(error, asyncio.TimeoutError):
        return False

    # 以下错误类型不可重试
    NON_RETRYABLE_ERRORS = (
        ToolPermissionDeniedError,
        ToolNotFoundError,
        ValueError,
        TypeError,
    )
    if isinstance(error, NON_RETRYABLE_ERRORS):
        return False

    # 以下错误类型可重试
    RETRYABLE_ERRORS = (
        asyncio.TimeoutError,
        ConnectionError,
        OSError,
        LLMException,
        VectorStoreException,
    )
    if isinstance(error, RETRYABLE_ERRORS):
        return True

    # 未知错误：仅对幂等工具重试
    return capability.idempotent
```

| 错误类型 | 可重试 | 理由 |
|---------|--------|------|
| asyncio.TimeoutError | 是 | 外部延迟导致，重试可能成功 |
| ConnectionError | 是 | 网络瞬断，重试可能恢复 |
| OSError | 是 | 文件系统临时不可用 |
| LLMException | 是 | LLM 服务临时不可用 |
| VectorStoreException | 是 | 向量存储临时不可用 |
| ToolPermissionDeniedError | 否 | 权限问题不会因重试改变 |
| ToolNotFoundError | 否 | 工具不存在是配置错误 |
| ValueError / TypeError | 否 | 参数错误，重试无意义 |

> **外部服务错误的包装规则**：当外部服务返回异常数据导致解析失败（如 JSON 解析 ValueError）时，应在工具调用层将此类错误包装为 `ExternalServiceError`（可重试），而非让 ValueError 直接传播到 ToolRuntime。`is_retryable()` 中 ValueError 默认不可重试的语义是"调用方传了错误参数"，这是正确的行为。

| 未知错误 | 仅幂等工具 | 保守策略，避免副作用 |

### 7.3 最大重试次数配置

重试次数的优先级：

```
调用级 max_retries 参数 > ToolCapability.retry_policy.max_retries > 全局默认值（3）
```

### 7.4 重试事件记录

每次重试自动发布事件，包含退避等待时间：

```python
{
    "event_type": "TOOL_RETRY",
    "tool_id": "search_code",
    "execution_id": "uuid",
    "attempt": 2,
    "max_retries": 3,
    "backoff_ms": 2000,
    "error": "ConnectionError: vector store unreachable",
    "timestamp": "2026-06-01T10:00:02Z",
}
```

---

## 8. 权限校验

### 8.1 基于 Scope x Domain 矩阵的权限检查

V2 采用 Scope x Domain 矩阵替代 V1 的简单字符串权限列表。权限标识格式为 `{scope}:{domain}`。

| | code | git | memory | history | index | runtime |
|--|------|-----|--------|---------|-------|---------|
| **read** | read:code | read:git | read:memory | read:history | read:index | read:runtime |
| **write** | write:code | write:git | write:memory | - | write:index | write:runtime |
| **admin** | admin:code | admin:git | admin:memory | - | admin:index | admin:runtime |

### 8.2 工具级权限声明

ToolCapability.required_scopes 声明工具所需的权限列表。调用者必须拥有全部声明的权限才能执行：

```python
# V1 工具权限映射到 V2 Scope:Domain
CAPABILITY_MIGRATIONS = {
    "search_code": ["read:code"],
    "read_file": ["read:code"],
    "read_module_summary": ["read:memory"],
    "list_modules": ["read:memory"],
    "get_dependencies": ["read:code", "read:memory"],
    "get_contributors": ["read:git"],
    "search_git_history": ["read:git"],
    "search_requirements": ["read:history"],
    "get_terminology": ["read:memory"],
    "get_project_profile": ["read:memory"],
}
```

### 8.3 Scope 继承关系

Scope 之间存在隐含的继承关系，高权限 Scope 自动包含低权限 Scope 的能力：

```
admin ⊃ write ⊃ read
```

| 父 Scope | 子 Scope | 说明 |
|---------|---------|------|
| `admin` | `write`, `read` | admin 隐含 write + read 权限 |
| `write` | `read` | write 隐含 read 权限 |
| `read` | 无 | 最小权限集 |

权限校验时，若工具声明 `required_scopes = ["write:code"]`，则用户持有 `admin:code` 或 `write:code` 均可通过，持有 `read:code` 则拒绝。

### 8.4 Session 级权限上下文

CognitiveSession 携带权限上下文，由 Session 创建时从配置矩阵解析：

```python
@dataclass
class SessionPermissionContext:
    """Session 级权限上下文"""
    scopes: set[str]
    project_id: int | None = None
    user_id: int | None = None

    def has_scope(self, required: str) -> bool:
        """检查是否拥有指定权限"""
        return required in self.scopes

    def check_scopes(self, required_scopes: list[str]) -> tuple[bool, list[str]]:
        """检查是否拥有全部所需权限，返回 (是否通过, 缺失权限列表)"""
        missing = [s for s in required_scopes if s not in self.scopes]
        return len(missing) == 0, missing
```

权限解析优先级（与配置矩阵一致）：

```
SESSION > USER > PROJECT > SYSTEM
```

### 8.5 权限拒绝处理

权限不足时的处理流程：

1. 抛出 `ToolPermissionDeniedError`，包含缺失的权限列表
2. 发布 `TOOL_PERMISSION_DENIED` 事件
3. 事件 Payload 包含 tool_id、required_scopes、missing_scopes、session_id
4. 前端可据此提示用户申请权限或切换项目

```python
{
    "event_type": "TOOL_PERMISSION_DENIED",
    "tool_id": "search_git_history",
    "execution_id": "uuid",
    "session_id": "uuid",
    "required_scopes": ["read:git"],
    "missing_scopes": ["read:git"],
    "timestamp": "2026-06-01T10:00:00Z",
}
```

---

## 9. Checkpoint 集成

### 9.1 工具执行前后的自动 Checkpoint

对于 `requires_checkpoint=True` 的工具，ToolRuntime 在执行前后自动创建 Checkpoint：

```python
class ToolRuntime:
    async def _checkpoint_before(
        self,
        tool_id: str,
        params: dict,
        session: CognitiveSession,
    ) -> str | None:
        """执行前创建 Checkpoint，返回 checkpoint_id"""
        try:
            checkpoint_id = await self.checkpoint_manager.create(
                session_id=session.session_id,
                trigger=f"tool_pre:{tool_id}",
                metadata={"tool_id": tool_id, "params": params},
            )
            return checkpoint_id
        except Exception as e:
            # Checkpoint 创建失败不应阻塞工具执行
            logger.warning("Checkpoint pre-execution 创建失败: %s", e)
            await self.event_bus.publish({
                "event_type": "TOOL_CHECKPOINT_FAILED",
                "tool_id": tool_id,
                "session_id": session.session_id,
                "phase": "pre",
                "error": str(e),
            })
            return None

    async def _checkpoint_after(
        self,
        tool_id: str,
        result: ToolResult,
        session: CognitiveSession,
    ) -> None:
        """执行后创建 Checkpoint"""
        try:
            await self.checkpoint_manager.create(
                session_id=session.session_id,
                trigger=f"tool_post:{tool_id}",
                metadata={
                    "tool_id": tool_id,
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                },
            )
        except Exception as e:
            logger.warning("Checkpoint post-execution 创建失败: %s", e)
```

### 9.2 requires_checkpoint 标记的工具

| 工具 | requires_checkpoint | 理由 |
|------|-------------------|------|
| search_code | False | 只读，无状态变更 |
| read_file | False | 只读，无状态变更 |
| read_module_summary | False | 只读，无状态变更 |
| list_modules | False | 只读，无状态变更 |
| get_dependencies | False | 只读，虽依赖内存数据但不修改 |
| get_contributors | False | 只读，无状态变更 |
| search_git_history | False | 只读，无状态变更 |
| search_requirements | False | 只读，无状态变更 |
| get_terminology | False | 只读，无状态变更 |
| get_project_profile | False | 只读，无状态变更 |
| （未来 WRITE 类工具） | True | 写入操作需要可回滚 |

当前 V1 全部工具均为只读，requires_checkpoint 均为 False。此能力为未来 WRITE/STATEFUL 工具预留。

### 9.3 Checkpoint 与工具执行的事务性

ToolRuntime 对 Checkpoint 采用"尽力而为"策略，不保证强事务性：

| 场景 | 行为 |
|------|------|
| Pre-checkpoint 成功，工具执行成功 | 正常流程，Post-checkpoint 创建 |
| Pre-checkpoint 成功，工具执行失败 | Post-checkpoint 不创建，Pre-checkpoint 保留作为回滚点 |
| Pre-checkpoint 失败 | 记录事件，降级为无 Checkpoint 继续执行 |
| Post-checkpoint 失败 | 记录事件，不影响工具结果返回 |

**设计决策**：Checkpoint 是辅助能力，其失败不应阻塞核心的工具执行流程。这与 P3 的"可降级"原则一致——Checkpoint 写入失败时，自动切换为"无 Checkpoint 模式"继续执行。

---

## 10. 事件记录

### 10.1 事件的自动发布

ToolRuntime 在工具执行的关键节点自动发布事件，工具实现无需关心事件发布逻辑。

| 事件类型 | 发布时机 | 说明 |
|---------|---------|------|
| TOOL_INVOKED | 工具开始执行前 | 记录调用意图和参数 |
| TOOL_RETURNED | 工具执行完成后 | 记录执行结果和耗时 |
| TOOL_RETRY | 重试前 | 记录重试原因和退避时间 |
| TOOL_TIMEOUT | 执行超时 | 记录超时时间和已执行时长 |
| TOOL_PERMISSION_DENIED | 权限校验失败 | 记录缺失权限 |
| TOOL_CHECKPOINT_FAILED | Checkpoint 创建失败 | 记录失败阶段和原因 |

### 10.2 事件 Payload 结构

**TOOL_INVOKED**：

```python
{
    "event_type": "TOOL_INVOKED",
    "session_id": "uuid",
    "execution_id": "uuid",
    "tool_id": "search_code",
    "params": {"keyword": "auth", "symbol_type": "class"},
    "timeout": 15.0,
    "attempt": 1,
    "timestamp": "2026-06-01T10:00:00Z",
}
```

**TOOL_RETURNED**：

```python
{
    "event_type": "TOOL_RETURNED",
    "session_id": "uuid",
    "execution_id": "uuid",
    "tool_id": "search_code",
    "success": True,
    "duration_ms": 234.5,
    "retry_count": 0,
    "from_cache": False,
    "result_length": 1024,
    "timestamp": "2026-06-01T10:00:00Z",
}
```

**TOOL_TIMEOUT**：

```python
{
    "event_type": "TOOL_TIMEOUT",
    "session_id": "uuid",
    "execution_id": "uuid",
    "tool_id": "search_git_history",
    "timeout": 60.0,
    "attempt": 2,
    "max_retries": 3,
    "timestamp": "2026-06-01T10:01:00Z",
}
```

所有事件通过 Event Bus（R-03）发布，由 api-service 通过 Redis Pub/Sub 转发给前端 WebSocket 客户端。

---

## 11. 结果缓存

### 11.1 基于参数哈希的短期缓存

缓存 Key 的计算方式：

```python
import hashlib
import json


def compute_cache_key(tool_id: str, params: dict) -> str:
    """计算缓存 Key：tool_id + 参数排序后的 JSON 哈希"""
    canonical = json.dumps(
        {"tool_id": tool_id, "params": params},
        sort_keys=True,
        ensure_ascii=False,
    )
    return f"{tool_id}:{hashlib.sha256(canonical.encode()).hexdigest()}"
```

### 11.2 缓存存储

P4 阶段使用进程内字典 + TTL 管理，不引入外部缓存依赖：

```python
import time


class ToolCache:
    """工具结果缓存（进程内）"""

    def __init__(self):
        self._store: dict[str, tuple[str, float, float]] = {}  # key -> (data, ttl_expires, created_at)

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        data, expires_at, _ = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return data

    def set(self, key: str, data: str, ttl: int) -> None:
        expires_at = time.monotonic() + ttl
        self._store[key] = (data, expires_at, time.monotonic())

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def invalidate_tool(self, tool_id: str) -> int:
        """使某工具的所有缓存失效（通过前缀扫描），返回失效条目数"""
        prefix = f"{tool_id}:"
        keys_to_remove = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._store[k]
        return len(keys_to_remove)

    def cleanup_expired(self) -> int:
        """清理过期缓存条目，返回清理数量"""
        now = time.monotonic()
        expired = [k for k, (_, exp, _) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
        return len(expired)
```

> **演进方向**：P5 完成后，ToolCache 可迁移到 Redis，支持跨实例共享和更精细的 TTL 管理。当前进程内方案满足 P4 需求。

### 11.3 缓存 TTL 配置

| 工具分类 | 推荐 cache_ttl | 理由 |
|---------|---------------|------|
| READ_ONLY | 300（5 分钟） | 只读结果短期内不会变化 |
| WRITE | 0 | 写入操作结果不应缓存 |
| STATEFUL | 60（1 分钟） | 有状态数据可能变化，TTL 较短 |
| EXTERNAL | 120（2 分钟） | 外部数据可能更新，中等 TTL |

### 11.4 缓存失效策略

| 策略 | 触发条件 | 说明 |
|------|---------|------|
| TTL 过期 | 缓存条目超过 cache_ttl | 自动失效，下次调用重新执行 |
| 手动失效 | 调用 `skip_cache=True` | 单次调用跳过缓存 |
| 工具级失效 | 工具注册更新时 | 清除该工具所有缓存 |
| Session 结束 | Session 完成或失败 | 清除该 Session 关联的所有缓存 |

---

## 12. 现有工具迁移方案

### 12.1 V1 工具列表

| 工具 | V1 权限 | V2 Scope | 分类 | 默认超时 | cache_ttl |
|------|---------|----------|------|---------|-----------|
| search_code | read:code | read:code | READ_ONLY | 15s | 300s |
| read_file | read:code | read:code | READ_ONLY | 15s | 300s |
| read_module_summary | read:memory | read:memory | READ_ONLY | 10s | 300s |
| list_modules | read:memory | read:memory | READ_ONLY | 10s | 300s |
| get_dependencies | read:code | read:code, read:memory | STATEFUL | 30s | 60s |
| get_contributors | read:git | read:git | READ_ONLY | 15s | 300s |
| search_git_history | read:git | read:git | EXTERNAL | 60s | 120s |
| search_requirements | read:history | read:history | EXTERNAL | 30s | 120s |
| get_terminology | read:memory | read:memory | READ_ONLY | 10s | 300s |
| get_project_profile | read:memory | read:memory | READ_ONLY | 10s | 300s |

### 12.2 迁移步骤

**步骤 1：为每个工具编写 ToolCapability 声明**

```python
# cognitive_rt/runtime/tool_capabilities.py

TOOL_CAPABILITIES: dict[str, ToolCapability] = {
    "search_code": ToolCapability(
        tool_id="search_code",
        name="代码搜索",
        description="在项目代码中搜索包含指定关键词的类、函数或变量",
        category=ToolCategory.READ_ONLY,
        timeout=15.0,
        retry_policy=RetryPolicy(max_retries=2, initial_backoff=1.0),
        required_scopes=["read:code"],
        cache_ttl=300,
        idempotent=True,
    ),
    "read_file": ToolCapability(
        tool_id="read_file",
        name="文件读取",
        description="读取项目中指定文件的源代码内容",
        category=ToolCategory.READ_ONLY,
        timeout=15.0,
        retry_policy=RetryPolicy(max_retries=2, initial_backoff=1.0),
        required_scopes=["read:code"],
        cache_ttl=300,
        idempotent=True,
    ),
    # ... 其余工具类似
}
```

**步骤 2：适配 ToolRuntime.execute() 接口**

V1 调用方式：

```python
# V1: 直接通过 ToolRegistry 调用
registry = ToolRegistry(user_permissions=user_perms)
result = await registry.execute_with_permissions("search_code", keyword="auth")
```

V2 调用方式：

```python
# V2: 通过 ToolRuntime 调用
tool_runtime = ToolRuntime(
    registry=registry,
    capability_registry=capability_registry,
    event_bus=event_bus,
    checkpoint_manager=checkpoint_manager,
    cache=tool_cache,
)
result = await tool_runtime.execute(
    tool_id="search_code",
    params={"keyword": "auth"},
    session=cognitive_session,
)
```

**步骤 3：修改 Agent 推理循环**

将 `runner.py` 中的工具调用入口从 `ToolRegistry.execute_with_permissions()` 切换为 `ToolRuntime.execute()`。这是唯一需要修改的调用点。

### 12.3 迁移后的调用方式变化

| 维度 | V1 | V2 |
|------|----|----|
| 调用入口 | `ToolRegistry.execute_with_permissions()` | `ToolRuntime.execute()` |
| 超时控制 | 无 | 自动（asyncio.wait_for） |
| 重试策略 | 无 | 自动（指数退避） |
| 权限校验 | 字符串集合匹配 | Scope x Domain 矩阵 |
| 事件记录 | 无 | 自动（TOOL_INVOKED / TOOL_RETURNED） |
| 结果缓存 | 无 | 自动（参数哈希 + TTL） |
| Checkpoint | 无 | 自动（requires_checkpoint 工具） |
| 错误类型 | ToolResult(success=False) | ToolExecutionError 异常层次 |

---

## 13. 接口定义

### 13.1 ToolRuntime 完整接口

```python
class ToolRuntime:
    """工具运行时管控中间层"""

    def __init__(
        self,
        registry: ToolRegistry,
        capability_registry: CapabilityRegistry,
        event_bus: EventBus,
        checkpoint_manager: CheckpointManager | None = None,
        cache: ToolCache | None = None,
        config: ToolRuntimeConfig | None = None,
    ): ...

    async def execute(
        self,
        tool_id: str,
        params: dict,
        session: CognitiveSession,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        skip_cache: bool = False,
        skip_checkpoint: bool = False,
    ) -> ToolResult: ...

    async def execute_batch(
        self,
        calls: list[ToolCall],
        session: CognitiveSession,
    ) -> list[ToolResult]:
        """批量执行工具调用（并行，各自独立管控）"""
        ...

    def get_capability(self, tool_id: str) -> ToolCapability | None:
        """获取工具能力声明"""
        ...

    def list_capabilities(self) -> list[ToolCapability]:
        """列出所有已注册工具的能力声明"""
        ...

    def invalidate_cache(self, tool_id: str | None = None) -> int:
        """使缓存失效，返回失效条目数"""
        ...


@dataclass
class ToolCall:
    """批量调用单元"""
    tool_id: str
    params: dict
    timeout: float | None = None
    max_retries: int | None = None
    skip_cache: bool = False
```

### 13.2 ToolRegistry 接口（工具注册表）

V2 的 ToolRegistry 在 V1 基础上增加能力声明注册：

```python
class ToolRegistry:
    """工具注册表"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具实例"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """获取工具实例"""
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """列出所有已注册工具名称"""
        return list(self._tools.keys())

    def get_schemas(self, names: list[str] | None = None) -> list[dict]:
        """获取工具的 OpenAI function calling schema"""
        if names is None:
            return [t.openai_schema() for t in self._tools.values()]
        return [self._tools[n].openai_schema() for n in names if n in self._tools]
```

### 13.3 CapabilityRegistry 接口

```python
class CapabilityRegistry:
    """工具能力声明注册表"""

    def __init__(self) -> None:
        self._capabilities: dict[str, ToolCapability] = {}

    def register(self, capability: ToolCapability) -> None:
        """注册工具能力声明"""
        self._capabilities[capability.tool_id] = capability

    def get(self, tool_id: str) -> ToolCapability | None:
        """获取工具能力声明"""
        return self._capabilities.get(tool_id)

    def list_all(self) -> list[ToolCapability]:
        """列出所有能力声明"""
        return list(self._capabilities.values())

    def update(self, tool_id: str, **overrides) -> ToolCapability:
        """动态更新能力声明（如调整超时时间）"""
        cap = self._capabilities.get(tool_id)
        if cap is None:
            raise ToolNotFoundError(f"工具能力声明未找到: {tool_id}")
        updated = cap.model_copy(update=overrides)
        self._capabilities[tool_id] = updated
        return updated
```

### 13.4 工具管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/tools` | GET | 列出所有已注册工具及其能力声明 |
| `/api/v2/tools/{tool_id}` | GET | 获取指定工具的能力声明 |
| `/api/v2/tools/{tool_id}/capability` | PUT | 动态更新工具能力声明（超时、重试等） |
| `/api/v2/tools/cache` | DELETE | 清除所有工具缓存 |
| `/api/v2/tools/cache/{tool_id}` | DELETE | 清除指定工具缓存 |

---

## 14. 错误处理

### 14.1 错误分类与处理策略

| 错误类型 | 异常类 | HTTP 映射 | 处理策略 |
|---------|--------|----------|---------|
| 工具未注册 | ToolNotFoundError | 404 | 不重试，记录事件 |
| 权限不足 | ToolPermissionDeniedError | 403 | 不重试，记录事件，提示用户 |
| 执行超时 | ToolTimeoutError | 504 | 按重试策略处理 |
| 重试耗尽 | ToolRetryExhaustedError | 502 | 记录最后一次错误，返回失败结果 |
| 工具内部错误 | ToolExecutionError | 500 | 按重试策略处理 |
| Checkpoint 失败 | ToolCheckpointError | - | 降级继续，记录事件 |

### 14.2 错误传播

```
BaseTool.execute() 抛出异常
    │
    ▼
ToolRuntime 捕获
    │
    ├── 可重试错误 → 进入重试循环
    │       │
    │       ├── 重试成功 → 返回 ToolResult(success=True)
    │       └── 重试耗尽 → 抛出 ToolRetryExhaustedError
    │
    ├── 不可重试错误 → 直接抛出 ToolExecutionError
    │
    └── 超时 → 抛出 ToolTimeoutError
```

### 14.3 错误与 ToolResult 的关系

V1 中工具错误通过 `ToolResult(success=False, error=...)` 返回。V2 保持兼容：

- **可恢复错误**（工具内部 catch 后返回 ToolResult(success=False)）：ToolRuntime 视为执行成功，不触发重试
- **不可恢复错误**（工具 execute() 抛出异常）：ToolRuntime 捕获后按重试策略处理

工具开发者应遵循以下约定：
- 参数校验失败、数据不存在等预期错误 → 返回 `ToolResult(success=False)`
- 网络中断、服务不可用等非预期错误 → 抛出异常，由 ToolRuntime 决定是否重试

---

## 15. 配置参数

### 15.1 ToolRuntimeConfig

```python
class ToolRuntimeConfig(BaseModel):
    """ToolRuntime 全局配置"""
    default_timeout: float = Field(default=30.0, description="全局默认超时（秒）")
    default_max_retries: int = Field(default=3, description="全局默认最大重试次数")
    default_cache_ttl: int = Field(default=300, description="全局默认缓存 TTL（秒）")
    cache_enabled: bool = Field(default=True, description="是否启用结果缓存")
    cache_max_size: int = Field(default=1000, description="缓存最大条目数")
    cache_cleanup_interval: int = Field(default=300, description="缓存清理间隔（秒）")
    checkpoint_enabled: bool = Field(default=True, description="是否启用 Checkpoint 集成")
    event_publishing_enabled: bool = Field(default=True, description="是否启用事件发布")
    rate_limit_enabled: bool = Field(default=True, description="是否启用速率限制")
```

### 15.2 配置矩阵位置

ToolRuntime 配置位于 Scope x Domain 矩阵的 TOOL 列：

| Scope | TOOL 列配置 |
|-------|-----------|
| SYSTEM | 全局工具开关、默认超时、默认重试策略 |
| PROJECT | 项目级工具集、项目级超时覆盖 |
| USER | 用户工具权限（对应 required_scopes） |
| SESSION | 会话级工具调用状态、会话级超时覆盖 |

---

## 16. 与其他模块的关系

### 16.1 依赖关系

```
ToolRuntime
    │
    ├── R-01 CognitiveSession ─── 提供 session 权限上下文、session_id
    │
    ├── R-03 Event Stream ─── TOOL_INVOKED / TOOL_RETURNED 等事件的发布通道
    │
    ├── R-05 Checkpoint ─── 工具执行前后的自动 Checkpoint 创建
    │
    └── M-01 Evidence ─── 工具返回结果中的 Evidence 提取（ToolRuntime 不直接操作 Evidence，
                          但 TOOL_RETURNED 事件可触发 Evidence 聚合）
```

### 16.2 被依赖关系

| 模块 | 依赖方式 | 说明 |
|------|---------|------|
| Cognition Layer (ReAct Agent) | 调用 ToolRuntime.execute() | Agent 的工具调用统一经过 ToolRuntime |
| api-service | 读取 TOOL_* 事件 | WebSocket 推送给前端 |
| output-service | 间接依赖 | 报告中的工具调用记录来自事件流 |

### 16.3 接口契约

| 接口 | 提供方 | 消费方 | 说明 |
|------|--------|--------|------|
| `ToolRuntime.execute()` | ToolRuntime | ReAct Agent | 工具执行入口 |
| `EventBus.publish()` | R-03 Event Stream | ToolRuntime | 事件发布 |
| `CheckpointManager.create()` | R-05 Checkpoint | ToolRuntime | Checkpoint 创建 |
| `SessionPermissionContext` | R-01 Session | ToolRuntime | 权限上下文 |
| `ToolCapability` | ToolRuntime | api-service | 工具能力查询 |

---

## 17. 测试策略

### 17.1 单元测试

| 测试类别 | 测试内容 | 覆盖要求 |
|---------|---------|---------|
| ToolCapability 校验 | Schema 验证、字段约束、默认值 | 所有字段边界值 |
| 超时控制 | 正常超时、超时取消、清理回调 | 超时精度 + 2s 内 |
| 重试策略 | 指数退避计算、可重试判断、最大次数 | 全部错误类型 |
| 权限校验 | 有权限、无权限、部分权限、空权限 | 全部 Scope 组合 |
| 缓存 | 命中、未命中、TTL 过期、手动失效 | 缓存一致性 |
| Checkpoint | 前置成功、后置成功、创建失败降级 | 失败降级路径 |
| 事件记录 | TOOL_INVOKED、TOOL_RETURNED、TOOL_RETRY | 事件完整性 |

### 17.2 集成测试

| 场景 | 验证内容 |
|------|---------|
| 工具超时自动中断 | 超时后任务取消，发布 TOOL_TIMEOUT 事件 |
| 重试后成功 | 第一次失败、第二次成功，retry_count=1 |
| 重试耗尽 | 连续失败 N 次后抛出 ToolRetryExhaustedError |
| 权限拒绝 | 缺少权限时抛出 ToolPermissionDeniedError |
| 缓存命中 | 相同参数第二次调用 from_cache=True |
| Checkpoint 创建失败降级 | Checkpoint 服务不可用时工具仍正常执行 |
| 完整事件链 | TOOL_INVOKED → TOOL_RETURNED 事件配对 |

### 17.3 E2E 测试

| 场景 | 验证内容 |
|------|---------|
| 前端实时看到工具调用事件 | TOOL_INVOKED → 超时 → 重试 → TOOL_RETURNED |
| 分析中断恢复后工具调用继续 | Checkpoint 恢复后工具调用链完整 |
| 多工具并行执行 | execute_batch 各工具独立管控互不干扰 |

### 17.4 Mock 策略

| 外部依赖 | Mock 方式 |
|---------|----------|
| BaseTool | Mock 返回 ToolResult 或抛出指定异常 |
| EventBus | Mock 记录发布的事件列表 |
| CheckpointManager | Mock 返回 checkpoint_id 或抛出异常 |
| CognitiveSession | Mock 包含指定权限上下文 |
| ToolCache | 使用真实实例（进程内，无外部依赖） |

---

## 18. 明确不做的事

| 方向 | 结论 | 理由 |
|------|------|------|
| 工具编排 / DAG 调度 | 不做 | 工具编排由 ReAct Agent 的推理循环负责，ToolRuntime 只管控单次调用 |
| 工具间数据传递 | 不做 | 工具间数据传递通过 Agent 的上下文管理，不经过 ToolRuntime |
| 分布式缓存 | 不做（P4 阶段） | 进程内缓存满足当前需求，P5 后可迁移到 Redis |
| 工具版本管理 | 不做 | 工具版本由代码版本控制管理，ToolRuntime 不维护版本链 |
| 工具热加载 | 不做 | 工具注册在 Session 创建时完成，运行期间不动态增删 |
| 工具沙箱隔离 | 不做 | 当前所有工具在相同进程空间执行，不引入进程级隔离 |
| 工具调用审计日志（持久化） | 不做 | 审计数据通过 Event Stream 由 index-service 持久化，ToolRuntime 不直接写审计表 |
| 自定义重试策略插件 | 不做 | P4 仅支持内置指数退避，自定义策略作为未来扩展点 |
| 工具熔断器 | 不做 | 熔断模式需要更复杂的状态管理，P4 不引入 |
| 工具调用链追踪（分布式 Tracing） | 不做 | 当前为单服务调用，无需分布式追踪 |

---

## 附录 A：ToolRuntime 类图

```
┌─────────────────────────────────────────────────────┐
│                     ToolRuntime                      │
│                                                      │
│  - registry: ToolRegistry                            │
│  - capability_registry: CapabilityRegistry           │
│  - event_bus: EventBus                               │
│  - checkpoint_manager: CheckpointManager | None      │
│  - cache: ToolCache | None                           │
│  - config: ToolRuntimeConfig                         │
│                                                      │
│  + execute(tool_id, params, session, ...) → ToolResult│
│  + execute_batch(calls, session) → list[ToolResult]  │
│  + get_capability(tool_id) → ToolCapability | None   │
│  + list_capabilities() → list[ToolCapability]        │
│  + invalidate_cache(tool_id) → int                   │
└──────────────────────┬──────────────────────────────┘
                       │ 使用
          ┌────────────┼────────────┬──────────────┐
          ▼            ▼            ▼              ▼
   ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ToolRegistry│ │Capability│ │ EventBus │ │Checkpoint│
   │            │ │Registry  │ │          │ │Manager   │
   │+register() │ │+register │ │+publish()│ │+create() │
   │+get()      │ │+get()    │ │          │ │          │
   │+list_names │ │+list_all │ │          │ │          │
   └─────┬──────┘ └──────────┘ └──────────┘ └──────────┘
         │
         ▼
   ┌──────────┐
   │ BaseTool │
   │(abstract)│
   │+execute()│
   └──────────┘
```

## 附录 B：execute() 时序图

```
Agent                ToolRuntime           Cache      Registry     EventBus    Checkpoint
  │                      │                   │           │            │            │
  │  execute(tool_id,    │                   │           │            │            │
  │   params, session)   │                   │           │            │            │
  │─────────────────────>│                   │           │            │            │
  │                      │                   │           │            │            │
  │                      │  get(tool_id)     │           │            │            │
  │                      │──────────────────────────────>│            │            │
  │                      │  BaseTool         │           │            │            │
  │                      │<──────────────────────────────│            │            │
  │                      │                   │           │            │            │
  │                      │ [权限校验]         │           │            │            │
  │                      │                   │           │            │            │
  │                      │  get(cache_key)   │           │            │            │
  │                      │──────────────────>│           │            │            │
  │                      │  cache_miss       │           │            │            │
  │                      │<──────────────────│           │            │            │
  │                      │                   │           │            │            │
  │                      │ [Checkpoint pre]  │           │            │            │
  │                      │───────────────────────────────────────────────────────>│
  │                      │  checkpoint_id    │           │            │            │
  │                      │<───────────────────────────────────────────────────────│
  │                      │                   │           │            │            │
  │                      │  publish(TOOL_INVOKED)        │            │            │
  │                      │──────────────────────────────────────────>│            │
  │                      │                   │           │            │            │
  │                      │  wait_for(        │           │            │            │
  │                      │   tool.execute()) │           │            │            │
  │                      │──────────────────────────────>│            │            │
  │                      │  ToolResult       │           │            │            │
  │                      │<──────────────────────────────│            │            │
  │                      │                   │           │            │            │
  │                      │  set(cache_key,   │           │            │            │
  │                      │   result, ttl)    │           │            │            │
  │                      │──────────────────>│           │            │            │
  │                      │                   │           │            │            │
  │                      │ [Checkpoint post] │           │            │            │
  │                      │───────────────────────────────────────────────────────>│
  │                      │                   │           │            │            │
  │                      │  publish(TOOL_RETURNED)       │            │            │
  │                      │──────────────────────────────────────────>│            │
  │                      │                   │           │            │            │
  │  ToolResult          │                   │           │            │            │
  │<─────────────────────│                   │           │            │            │
```
