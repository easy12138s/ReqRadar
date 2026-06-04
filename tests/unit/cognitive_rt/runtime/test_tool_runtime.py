"""ToolRuntime 单元测试。

覆盖执行流程、超时控制、重试策略、权限校验、事件发布、Checkpoint 和降级逻辑。
"""

from __future__ import annotations

import asyncio

import pytest

from reqradar.cognitive_rt.cognition.tools.base import BaseTool, ToolResult
from reqradar.cognitive_rt.cognition.tools.security import ToolPermissionChecker
from reqradar.cognitive_rt.runtime.tool_runtime import (
    ManagedToolResult,
    RetryPolicy,
    ToolCapability,
    ToolCategory,
    ToolNotFoundError,
    ToolRuntime,
)

# ---------------------------------------------------------------------------
# Mock 工具
# ---------------------------------------------------------------------------


class MockTool(BaseTool):
    name = "mock_tool"
    description = "Mock tool for testing"

    def __init__(
        self,
        result: ToolResult | None = None,
        delay: float = 0,
        error: Exception | None = None,
    ):
        self._result = result or ToolResult(success=True, data="mock result")
        self._delay = delay
        self._error = error

    async def execute(self, **kwargs) -> ToolResult:
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return self._result


class MockParamCaptureTool(BaseTool):
    name = "param_capture"
    description = "Captures params for assertion"

    def __init__(self) -> None:
        self.captured_params: dict = {}

    async def execute(self, **kwargs) -> ToolResult:
        self.captured_params = dict(kwargs)
        return ToolResult(success=True, data="captured")


class MockFailThenSucceedTool(BaseTool):
    name = "fail_then_succeed"
    description = "Fails first N calls then succeeds"

    def __init__(self, fail_count: int, result: ToolResult | None = None):
        self._fail_count = fail_count
        self._call_count = 0
        self._result = result or ToolResult(success=True, data="success after retries")

    async def execute(self, **kwargs) -> ToolResult:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise RuntimeError(f"simulated failure #{self._call_count}")
        return self._result


class MockSlowThenFastTool(BaseTool):
    name = "slow_then_fast"
    description = "Slow on first call, fast on subsequent calls"

    def __init__(self, slow_duration: float = 5.0):
        self._call_count = 0
        self._slow_duration = slow_duration

    async def execute(self, **kwargs) -> ToolResult:
        self._call_count += 1
        if self._call_count == 1:
            await asyncio.sleep(self._slow_duration)
        return ToolResult(success=True, data="fast result")


class MockAlwaysFailTool(BaseTool):
    name = "always_fail"
    description = "Always raises an exception"

    async def execute(self, **kwargs) -> ToolResult:
        raise RuntimeError("permanent failure")


# ---------------------------------------------------------------------------
# Mock 协作对象
# ---------------------------------------------------------------------------


class MockRegistry:
    def __init__(self, tools: dict[str, BaseTool] | None = None):
        self._tools = tools or {}

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())


class MockEventPublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(
        self,
        session_id: str,
        event_type: str,
        event_level: str,
        producer: str,
        payload: dict | None = None,
    ) -> None:
        self.events.append(
            {
                "session_id": session_id,
                "event_type": event_type,
                "event_level": event_level,
                "producer": producer,
                "payload": payload or {},
            }
        )


class MockCheckpointMgr:
    def __init__(self, fail: bool = False):
        self.checkpoints: list = []
        self._fail = fail

    def create_checkpoint(
        self,
        session_id: str,
        checkpoint_type: str,
        state_summary: dict,
        **kwargs,
    ):
        if self._fail:
            raise RuntimeError("checkpoint failed")
        cp = type("CP", (), {"checkpoint_id": f"cp-{len(self.checkpoints)}"})()
        self.checkpoints.append(cp)
        return cp


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

SESSION_ID = "test-session-001"


def _fast_retry_policy(max_retries: int = 3) -> RetryPolicy:
    """最短合法退避策略，加速重试测试。"""
    return RetryPolicy(
        max_retries=max_retries,
        initial_backoff=0.1,
        max_backoff=1.0,
        backoff_multiplier=1.0,
        jitter=False,
    )


def _build_capability(
    tool_id: str = "mock_tool",
    *,
    timeout: float = 30.0,
    retry_policy: RetryPolicy | None = None,
    required_scopes: list[str] | None = None,
    requires_checkpoint: bool = False,
    category: ToolCategory = ToolCategory.READ_ONLY,
) -> ToolCapability:
    return ToolCapability(
        tool_id=tool_id,
        name=tool_id,
        description="test capability",
        category=category,
        timeout=timeout,
        retry_policy=retry_policy or RetryPolicy(max_retries=0),
        required_scopes=required_scopes or [],
        requires_checkpoint=requires_checkpoint,
    )


def _build_runtime(
    tools: dict[str, BaseTool] | None = None,
    capabilities: dict[str, ToolCapability] | None = None,
    event_publisher: MockEventPublisher | None = None,
    checkpoint_mgr: MockCheckpointMgr | None = None,
    permission_checker: ToolPermissionChecker | None = None,
) -> ToolRuntime:
    return ToolRuntime(
        registry=MockRegistry(tools or {}),
        event_publisher=event_publisher,
        checkpoint_mgr=checkpoint_mgr,
        permission_checker=permission_checker,
        capabilities=capabilities or {},
    )


# ===========================================================================
# TestToolRuntimeExecute — 基本执行流程
# ===========================================================================


class TestToolRuntimeExecute:
    """测试 ToolRuntime.execute 的基本执行逻辑。"""

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """工具返回成功 → ManagedToolResult.success=True。"""
        tool = MockTool(result=ToolResult(success=True, data="ok"))
        runtime = _build_runtime(tools={"mock_tool": tool})

        result = await runtime.execute("mock_tool")

        assert result.success is True
        assert result.data == "ok"
        assert result.tool_id == "mock_tool"
        assert isinstance(result, ManagedToolResult)

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self) -> None:
        """未注册的工具 → 抛出 ToolNotFoundError。"""
        runtime = _build_runtime(tools={})

        with pytest.raises(ToolNotFoundError) as exc_info:
            await runtime.execute("nonexistent_tool")

        assert exc_info.value.tool_id == "nonexistent_tool"
        assert "nonexistent_tool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_params(self) -> None:
        """params 透传到工具的 execute 方法。"""
        tool = MockParamCaptureTool()
        runtime = _build_runtime(tools={"param_capture": tool})

        params = {"query": "test", "limit": 10}
        result = await runtime.execute("param_capture", params=params)

        assert result.success is True
        assert tool.captured_params == params

    @pytest.mark.asyncio
    async def test_execute_timeout_configurable(self) -> None:
        """ToolCapability.timeout 被正确使用。"""
        tool = MockTool(delay=3.0)
        cap = _build_capability(timeout=1.0)
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
        )

        result = await runtime.execute("mock_tool")

        assert result.success is False
        assert result.data == ""

    @pytest.mark.asyncio
    async def test_execute_custom_timeout_override(self) -> None:
        """execute(timeout=X) 覆盖 capability.timeout。"""
        tool = MockTool(delay=3.0)
        cap = _build_capability(timeout=60.0)
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
        )

        result = await runtime.execute("mock_tool", timeout=1.0)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_duration_ms(self) -> None:
        """结果包含非零的 duration_ms。"""
        tool = MockTool(delay=0.05, result=ToolResult(success=True, data="ok"))
        runtime = _build_runtime(tools={"mock_tool": tool})

        result = await runtime.execute("mock_tool")

        assert result.duration_ms > 0


# ===========================================================================
# TestTimeoutControl — 超时控制
# ===========================================================================


class TestTimeoutControl:
    """测试工具执行的超时控制。"""

    @pytest.mark.asyncio
    async def test_timeout_triggers_error(self) -> None:
        """工具执行 5s，超时 1s → 结果为失败。"""
        tool = MockTool(delay=5.0)
        cap = _build_capability(timeout=1.0)
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
        )

        result = await runtime.execute("mock_tool")

        assert result.success is False
        assert result.data == ""

    @pytest.mark.asyncio
    async def test_timeout_before_completion(self) -> None:
        """快速工具在充裕超时内完成 → 成功。"""
        tool = MockTool(delay=0.01)
        cap = _build_capability(timeout=5.0)
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
        )

        result = await runtime.execute("mock_tool")

        assert result.success is True
        assert result.data == "mock result"

    @pytest.mark.asyncio
    async def test_timeout_with_retry(self) -> None:
        """首次超时，重试后成功。"""
        tool = MockSlowThenFastTool(slow_duration=5.0)
        cap = _build_capability(
            timeout=1.0,
            retry_policy=RetryPolicy(
                max_retries=1,
                initial_backoff=0.1,
                max_backoff=1.0,
                backoff_multiplier=1.0,
                jitter=False,
            ),
        )
        publisher = MockEventPublisher()
        runtime = _build_runtime(
            tools={"slow_then_fast": tool},
            capabilities={"slow_then_fast": cap},
            event_publisher=publisher,
        )

        result = await runtime.execute("slow_then_fast", session_id=SESSION_ID)

        assert result.success is True
        assert result.data == "fast result"
        retry_events = [e for e in publisher.events if e["event_type"] == "TOOL_RETRY"]
        assert len(retry_events) >= 1


# ===========================================================================
# TestRetryStrategy — 重试策略
# ===========================================================================


class TestRetryStrategy:
    """测试重试策略的行为。"""

    @pytest.mark.asyncio
    async def test_retry_on_error(self) -> None:
        """工具失败 3 次后成功 → retry_count=2, success=True。"""
        tool = MockFailThenSucceedTool(fail_count=3)
        cap = _build_capability(
            retry_policy=RetryPolicy(
                max_retries=3,
                initial_backoff=0.1,
                max_backoff=1.0,
                backoff_multiplier=1.0,
                jitter=False,
            ),
        )
        runtime = _build_runtime(
            tools={"fail_then_succeed": tool},
            capabilities={"fail_then_succeed": cap},
            event_publisher=MockEventPublisher(),
        )

        result = await runtime.execute("fail_then_succeed", session_id=SESSION_ID)

        assert result.success is True
        assert result.data == "success after retries"
        assert result.retry_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self) -> None:
        """工具始终失败 → retry_count=max_retries, success=False。"""
        tool = MockAlwaysFailTool()
        max_retries = 3
        cap = _build_capability(
            retry_policy=RetryPolicy(
                max_retries=max_retries,
                initial_backoff=0.1,
                max_backoff=1.0,
                backoff_multiplier=1.0,
                jitter=False,
            ),
        )
        runtime = _build_runtime(
            tools={"always_fail": tool},
            capabilities={"always_fail": cap},
        )

        result = await runtime.execute("always_fail")

        assert result.success is False
        assert result.retry_count == max_retries
        assert "重试耗尽" in result.error

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self) -> None:
        """工具首次即成功 → retry_count=0。"""
        tool = MockTool(result=ToolResult(success=True, data="first try"))
        cap = _build_capability(retry_policy=RetryPolicy(max_retries=3))
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
        )

        result = await runtime.execute("mock_tool")

        assert result.success is True
        assert result.retry_count == 0


# ===========================================================================
# TestPermissionCheck — 权限校验
# ===========================================================================


class TestPermissionCheck:
    """测试权限校验逻辑。"""

    @pytest.mark.asyncio
    async def test_permission_granted(self) -> None:
        """工具所需权限与用户权限匹配 → 执行成功。"""
        tool = MockTool(result=ToolResult(success=True, data="granted"))
        checker = ToolPermissionChecker(user_permissions={"read:files", "write:files"})
        cap = _build_capability(required_scopes=["read:files"])
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
            permission_checker=checker,
        )

        result = await runtime.execute("mock_tool")

        assert result.success is True
        assert result.data == "granted"

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        """缺少权限 → 返回失败结果。"""
        tool = MockTool()
        checker = ToolPermissionChecker(user_permissions=set())
        cap = _build_capability(required_scopes=["admin:all"])
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
            permission_checker=checker,
        )

        result = await runtime.execute("mock_tool", session_id=SESSION_ID)

        assert result.success is False
        assert "权限不足" in result.error

    @pytest.mark.asyncio
    async def test_no_permission_required(self) -> None:
        """工具无需权限 → 始终通过。"""
        tool = MockTool(result=ToolResult(success=True, data="no scope"))
        checker = ToolPermissionChecker(user_permissions=set())
        cap = _build_capability(required_scopes=[])
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
            permission_checker=checker,
        )

        result = await runtime.execute("mock_tool")

        assert result.success is True
        assert result.data == "no scope"


# ===========================================================================
# TestEventPublishing — 事件发布
# ===========================================================================


class TestEventPublishing:
    """测试事件发布行为。"""

    @pytest.mark.asyncio
    async def test_publish_tool_invoked(self) -> None:
        """执行工具时发布 TOOL_INVOKED 事件。"""
        tool = MockTool()
        publisher = MockEventPublisher()
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            event_publisher=publisher,
        )

        await runtime.execute("mock_tool", session_id=SESSION_ID)

        invoked = [e for e in publisher.events if e["event_type"] == "TOOL_INVOKED"]
        assert len(invoked) == 1
        assert invoked[0]["session_id"] == SESSION_ID
        assert invoked[0]["payload"]["tool_id"] == "mock_tool"

    @pytest.mark.asyncio
    async def test_publish_tool_returned(self) -> None:
        """工具执行完毕后发布 TOOL_RETURNED 事件，包含 success 和 duration。"""
        tool = MockTool(delay=0.05)
        publisher = MockEventPublisher()
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            event_publisher=publisher,
        )

        await runtime.execute("mock_tool", session_id=SESSION_ID)

        returned = [e for e in publisher.events if e["event_type"] == "TOOL_RETURNED"]
        assert len(returned) == 1
        assert returned[0]["payload"]["success"] is True
        assert returned[0]["payload"]["duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_publish_tool_retry(self) -> None:
        """重试时发布 TOOL_RETRY 事件。"""
        tool = MockFailThenSucceedTool(fail_count=1)
        cap = _build_capability(
            retry_policy=RetryPolicy(
                max_retries=2,
                initial_backoff=0.1,
                max_backoff=1.0,
                backoff_multiplier=1.0,
                jitter=False,
            ),
        )
        publisher = MockEventPublisher()
        runtime = _build_runtime(
            tools={"fail_then_succeed": tool},
            capabilities={"fail_then_succeed": cap},
            event_publisher=publisher,
        )

        await runtime.execute("fail_then_succeed", session_id=SESSION_ID)

        retry_events = [e for e in publisher.events if e["event_type"] == "TOOL_RETRY"]
        assert len(retry_events) >= 1
        assert retry_events[0]["payload"]["tool_id"] == "fail_then_succeed"


# ===========================================================================
# TestCheckpoint — Checkpoint 管理
# ===========================================================================


class TestCheckpoint:
    """测试 Checkpoint 创建行为。"""

    @pytest.mark.asyncio
    async def test_checkpoint_created_when_required(self) -> None:
        """requires_checkpoint=True → checkpoint_mgr 被调用。"""
        tool = MockTool()
        cp_mgr = MockCheckpointMgr()
        cap = _build_capability(requires_checkpoint=True)
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
            checkpoint_mgr=cp_mgr,
        )

        result = await runtime.execute("mock_tool", session_id=SESSION_ID)

        assert result.success is True
        assert len(cp_mgr.checkpoints) >= 1
        assert result.checkpoint_id is not None

    @pytest.mark.asyncio
    async def test_no_checkpoint_when_not_required(self) -> None:
        """requires_checkpoint=False → checkpoint_mgr 不被调用。"""
        tool = MockTool()
        cp_mgr = MockCheckpointMgr()
        cap = _build_capability(requires_checkpoint=False)
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
            checkpoint_mgr=cp_mgr,
        )

        result = await runtime.execute("mock_tool", session_id=SESSION_ID)

        assert result.success is True
        assert len(cp_mgr.checkpoints) == 0
        assert result.checkpoint_id is None


# ===========================================================================
# TestDegradation — 降级逻辑
# ===========================================================================


class TestDegradation:
    """测试降级处理。"""

    @pytest.mark.asyncio
    async def test_checkpoint_failure_degrades(self) -> None:
        """checkpoint_mgr 抛异常 → 工具仍正常执行并返回成功。"""
        tool = MockTool(result=ToolResult(success=True, data="degraded ok"))
        cp_mgr = MockCheckpointMgr(fail=True)
        cap = _build_capability(requires_checkpoint=True)
        publisher = MockEventPublisher()
        runtime = _build_runtime(
            tools={"mock_tool": tool},
            capabilities={"mock_tool": cap},
            checkpoint_mgr=cp_mgr,
            event_publisher=publisher,
        )

        result = await runtime.execute("mock_tool", session_id=SESSION_ID)

        assert result.success is True
        assert result.data == "degraded ok"

        checkpoint_failed = [
            e for e in publisher.events if e["event_type"] == "TOOL_CHECKPOINT_FAILED"
        ]
        assert len(checkpoint_failed) >= 1
