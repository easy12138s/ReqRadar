"""Session 生命周期服务 — 创建、启动、取消、查询 Session。"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from reqradar.cognitive_rt.runtime.checkpoint import CheckpointManager, StateSummary
from reqradar.cognitive_rt.runtime.checkpoint_storage import CheckpointStorage
from reqradar.cognitive_rt.runtime.events import EventPublisher
from reqradar.cognitive_rt.runtime.session import (
    IllegalTransitionError,
    SessionStateMachine,
    create_session,
)
from reqradar.kernel.enums import (
    CheckpointType,
    EventLevel,
    EventType,
    SessionStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Session 信息摘要。"""

    session_id: str
    project_id: str
    user_id: str
    status: SessionStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_reasoning_steps: int = 0
    last_checkpoint_version: int = 0


class SessionService:
    """Session 生命周期服务。"""

    def __init__(
        self,
        event_publisher: EventPublisher | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        checkpoint_storage: CheckpointStorage | None = None,
    ) -> None:
        """初始化服务。

        Args:
            event_publisher: 事件发布器
            checkpoint_manager: Checkpoint 管理器
            checkpoint_storage: Checkpoint 存储
        """
        self._publisher = event_publisher or EventPublisher()
        self._checkpoint_mgr = checkpoint_manager or CheckpointManager()
        self._checkpoint_storage = checkpoint_storage or CheckpointStorage()
        self._sessions: dict[str, SessionStateMachine] = {}

    def create(
        self,
        project_id: str,
        user_id: str,
        config: dict | None = None,
    ) -> SessionInfo:
        """创建新 Session。

        Args:
            project_id: 项目 ID
            user_id: 用户 ID
            config: 会话配置

        Returns:
            Session 信息
        """
        session_id = str(uuid4())
        sm = create_session(session_id, project_id, user_id, config)

        # 自动转换到 READY
        with contextlib.suppress(IllegalTransitionError):
            sm.transition(SessionStatus.READY)

        self._sessions[session_id] = sm

        # 发布事件
        self._publisher.publish(
            session_id=session_id,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="session_service",
            payload={"project_id": project_id, "user_id": user_id},
        )

        logger.info("Session 创建: %s", session_id)
        return self._to_info(sm)

    def start(self, session_id: str) -> SessionInfo:
        """启动 Session。

        Args:
            session_id: Session ID

        Returns:
            Session 信息

        Raises:
            KeyError: Session 不存在
            IllegalTransitionError: 非法转换
        """
        sm = self._get(session_id)
        sm.transition(SessionStatus.RUNNING)

        self._publisher.publish(
            session_id=session_id,
            event_type=EventType.SESSION_STARTED,
            event_level=EventLevel.SESSION,
            producer="session_service",
        )

        logger.info("Session 启动: %s", session_id)
        return self._to_info(sm)

    def cancel(self, session_id: str) -> SessionInfo:
        """取消 Session。

        Args:
            session_id: Session ID

        Returns:
            Session 信息
        """
        sm = self._get(session_id)
        current = sm.status

        if current == SessionStatus.RUNNING:
            sm.transition(SessionStatus.CANCELLING)
            sm.transition(SessionStatus.CANCELLED)
        elif current == SessionStatus.READY:
            sm.transition(SessionStatus.CANCELLED)
        elif current == SessionStatus.WAITING_INPUT:
            sm.transition(SessionStatus.CANCELLING)
            sm.transition(SessionStatus.CANCELLED)
        else:
            raise IllegalTransitionError(current, SessionStatus.CANCELLED)

        self._publisher.publish(
            session_id=session_id,
            event_type=EventType.SESSION_CANCELLED,
            event_level=EventLevel.SESSION,
            producer="session_service",
        )

        logger.info("Session 取消: %s", session_id)
        return self._to_info(sm)

    def complete(self, session_id: str) -> SessionInfo:
        """完成 Session。

        Args:
            session_id: Session ID

        Returns:
            Session 信息
        """
        sm = self._get(session_id)
        sm.transition(SessionStatus.COMPLETED)

        self._publisher.publish(
            session_id=session_id,
            event_type=EventType.SESSION_COMPLETED,
            event_level=EventLevel.SESSION,
            producer="session_service",
        )

        logger.info("Session 完成: %s", session_id)
        return self._to_info(sm)

    def fail(self, session_id: str, error_message: str, error_type: str = "unknown") -> SessionInfo:
        """标记 Session 失败。

        Args:
            session_id: Session ID
            error_message: 错误信息
            error_type: 错误类型

        Returns:
            Session 信息
        """
        sm = self._get(session_id)
        sm.transition(SessionStatus.FAILED, error_message=error_message, error_type=error_type)

        self._publisher.publish(
            session_id=session_id,
            event_type=EventType.SESSION_FAILED,
            event_level=EventLevel.SESSION,
            producer="session_service",
            payload={"error_message": error_message, "error_type": error_type},
        )

        logger.info("Session 失败: %s, error=%s", session_id, error_message)
        return self._to_info(sm)

    def checkpoint(
        self,
        session_id: str,
        checkpoint_type: CheckpointType = CheckpointType.STEP_COMPLETE,
        current_step: int = 0,
        evidence_count: int = 0,
        dimension_status: dict | None = None,
    ) -> str:
        """创建 Checkpoint。

        Args:
            session_id: Session ID
            checkpoint_type: Checkpoint 类型
            current_step: 当前步骤
            evidence_count: 证据数
            dimension_status: 维度状态

        Returns:
            Checkpoint ID
        """
        sm = self._get(session_id)

        # 转换到 CHECKPOINTING
        if sm.status == SessionStatus.RUNNING:
            sm.transition(SessionStatus.CHECKPOINTING)

        summary = StateSummary(
            current_step=current_step,
            evidence_count=evidence_count,
            dimension_status=dimension_status or {},
        )

        record = self._checkpoint_mgr.create_checkpoint(
            session_id=session_id,
            checkpoint_type=checkpoint_type,
            state_summary=summary,
        )

        self._checkpoint_storage.save(record)

        # 更新 session 的 checkpoint version
        sm._state.last_checkpoint_version = record.version

        # 转换回 RUNNING
        if sm.status == SessionStatus.CHECKPOINTING:
            sm.transition(SessionStatus.RUNNING)

        self._publisher.publish(
            session_id=session_id,
            event_type=EventType.SESSION_CHECKPOINTED,
            event_level=EventLevel.SESSION,
            producer="session_service",
            payload={"version": record.version, "checkpoint_id": record.checkpoint_id},
        )

        return record.checkpoint_id

    def get(self, session_id: str) -> SessionInfo:
        """获取 Session 信息。"""
        return self._to_info(self._get(session_id))

    def list_sessions(self, status: SessionStatus | None = None) -> list[SessionInfo]:
        """列出所有 Session。"""
        result = []
        for sm in self._sessions.values():
            if status is None or sm.status == status:
                result.append(self._to_info(sm))
        return result

    def get_events(self, session_id: str) -> list:
        """获取 Session 的事件列表。"""
        return self._publisher.get_events(session_id)

    def _get(self, session_id: str) -> SessionStateMachine:
        """获取 Session 状态机。"""
        if session_id not in self._sessions:
            raise KeyError(f"Session 不存在: {session_id}")
        return self._sessions[session_id]

    def _to_info(self, sm: SessionStateMachine) -> SessionInfo:
        """转换为 SessionInfo。"""
        return SessionInfo(
            session_id=sm.state.session_id,
            project_id=sm.state.project_id,
            user_id=sm.state.user_id,
            status=sm.status,
            created_at=sm.state.created_at,
            started_at=sm.state.started_at,
            finished_at=sm.state.finished_at,
            total_reasoning_steps=sm.state.total_reasoning_steps,
            last_checkpoint_version=sm.state.last_checkpoint_version,
        )
