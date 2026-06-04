"""CognitiveSession 状态机 — 管理 Session 生命周期。

包含 11 状态、20 条合法转换的状态机实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from reqradar.kernel.enums import SessionStatus
from reqradar.kernel.exceptions import SessionException


class IllegalTransitionError(SessionException):
    """非法状态转换错误。"""

    def __init__(
        self,
        current: SessionStatus,
        target: SessionStatus,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"非法状态转换: {current.value} -> {target.value}",
            cause=cause,
        )
        self.current = current
        self.target = target


_TRANSITIONS: dict[tuple[SessionStatus, SessionStatus], str] = {
    (SessionStatus.CREATED, SessionStatus.READY): "配置校验通过",
    (SessionStatus.CREATED, SessionStatus.FAILED): "配置校验失败",
    (SessionStatus.READY, SessionStatus.RUNNING): "用户启动",
    (SessionStatus.READY, SessionStatus.CANCELLED): "用户取消",
    (SessionStatus.RUNNING, SessionStatus.CHECKPOINTING): "周期/手动触发",
    (SessionStatus.RUNNING, SessionStatus.WAITING_INPUT): "Agent 请求用户输入",
    (SessionStatus.RUNNING, SessionStatus.CANCELLING): "用户取消",
    (SessionStatus.RUNNING, SessionStatus.COMPLETED): "推理正常结束",
    (SessionStatus.RUNNING, SessionStatus.FAILED): "可恢复错误",
    (SessionStatus.RUNNING, SessionStatus.TIMEOUT): "超过最大执行时间",
    (SessionStatus.RUNNING, SessionStatus.ABORTED): "不可恢复错误",
    (SessionStatus.CHECKPOINTING, SessionStatus.RUNNING): "Checkpoint 写入成功",
    (SessionStatus.CHECKPOINTING, SessionStatus.CANCELLING): "用户取消",
    (SessionStatus.CHECKPOINTING, SessionStatus.FAILED): "Checkpoint 写入失败",
    (SessionStatus.CHECKPOINTING, SessionStatus.ABORTED): "存储服务不可用",
    (SessionStatus.WAITING_INPUT, SessionStatus.RUNNING): "用户提供输入",
    (SessionStatus.WAITING_INPUT, SessionStatus.CANCELLING): "用户取消",
    (SessionStatus.CANCELLING, SessionStatus.CANCELLED): "清理完成",
    (SessionStatus.CANCELLING, SessionStatus.TIMEOUT): "取消过程中超时",
    (SessionStatus.CANCELLING, SessionStatus.ABORTED): "取消过程中不可恢复错误",
}

_TERMINAL_STATES: frozenset[SessionStatus] = frozenset(
    {
        SessionStatus.COMPLETED,
        SessionStatus.FAILED,
        SessionStatus.CANCELLED,
        SessionStatus.TIMEOUT,
        SessionStatus.ABORTED,
    }
)

_RUNNING_STATES: frozenset[SessionStatus] = frozenset(
    {
        SessionStatus.RUNNING,
        SessionStatus.CHECKPOINTING,
    }
)


@dataclass
class RuntimeState:
    """Session 运行时状态。"""

    session_id: str
    project_id: str
    user_id: str
    status: SessionStatus = SessionStatus.CREATED
    config: dict = field(default_factory=dict)
    state: dict = field(default_factory=dict)
    error_message: str | None = None
    error_type: str | None = None
    last_checkpoint_version: int = 0
    total_reasoning_steps: int = 0
    total_tool_calls: int = 0
    status_history: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancel_requested: bool = False


class SessionStateMachine:
    """CognitiveSession 状态机 — 管理 Session 生命周期。"""

    def __init__(self, state: RuntimeState) -> None:
        self._state = state

    @property
    def state(self) -> RuntimeState:
        """获取当前运行时状态快照。"""
        return self._state

    @property
    def status(self) -> SessionStatus:
        """获取当前会话状态。"""
        return self._state.status

    def can_transition(self, target: SessionStatus) -> bool:
        """检查是否可以转换到目标状态。"""
        if self._state.status == target:
            return True
        return (self._state.status, target) in _TRANSITIONS

    def transition(
        self,
        target: SessionStatus,
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> RuntimeState:
        """执行状态转换，返回更新后的状态。

        Raises:
            IllegalTransitionError: 非法转换
        """
        current = self._state.status

        if current == target:
            return self._state

        if not self.can_transition(target):
            raise IllegalTransitionError(current, target)

        now = datetime.now(UTC)

        self._state.status_history.append(
            {
                "from": current.value,
                "to": target.value,
                "timestamp": now.isoformat(),
                "reason": _TRANSITIONS.get((current, target), ""),
            }
        )

        self._state.status = target
        self._state.updated_at = now

        if target == SessionStatus.RUNNING and self._state.started_at is None:
            self._state.started_at = now

        if target in _TERMINAL_STATES:
            self._state.finished_at = now

        if error_message:
            self._state.error_message = error_message
        if error_type:
            self._state.error_type = error_type

        if target == SessionStatus.CANCELLING:
            self._state.cancel_requested = True

        return self._state

    def is_terminal(self) -> bool:
        """检查是否处于终态。"""
        return self._state.status in _TERMINAL_STATES

    def is_running(self) -> bool:
        """检查是否正在运行。"""
        return self._state.status in _RUNNING_STATES


def create_session(
    session_id: str,
    project_id: str,
    user_id: str,
    config: dict | None = None,
) -> SessionStateMachine:
    """创建新的 Session 状态机。"""
    state = RuntimeState(
        session_id=session_id,
        project_id=project_id,
        user_id=user_id,
        config=config or {},
    )
    return SessionStateMachine(state)
