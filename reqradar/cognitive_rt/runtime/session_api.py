"""Session 生命周期服务 — 创建、启动、取消、查询 Session。"""

from __future__ import annotations

import asyncio
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
        self._background_tasks: set[asyncio.Task] = set()

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

    async def start(
        self,
        session_id: str,
        agent: object | None = None,
        llm_client: object | None = None,
        tool_registry: object | None = None,
        config: object = None,
        section_descriptions: object = None,
        project_memory: object = None,
        requirement_text: str | None = None,
        resume_from: int | None = None,
    ) -> SessionInfo:
        """启动 Session。

        Args:
            session_id: Session ID
            agent: Runner Agent 实例
            llm_client: LLM 客户端
            tool_registry: 工具注册表
            config: 运行配置
            section_descriptions: 章节描述
            project_memory: 项目记忆
            requirement_text: 需求文本
            resume_from: 从指定步骤恢复

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

        # 如果提供了 Runner 参数，异步启动分析
        if agent is not None and llm_client is not None and tool_registry is not None:
            task = asyncio.create_task(
                self._run_analysis(
                    session_id=session_id,
                    agent=agent,
                    llm_client=llm_client,
                    tool_registry=tool_registry,
                    config=config,
                    section_descriptions=section_descriptions,
                    project_memory=project_memory,
                    requirement_text=requirement_text,
                    resume_from=resume_from,
                )
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

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

    def wait_for_input(self, session_id: str) -> SessionInfo:
        """将 Session 转换为等待用户输入状态。

        Args:
            session_id: Session ID

        Returns:
            Session 信息

        Raises:
            KeyError: Session 不存在
            IllegalTransitionError: 非法转换（当前状态非 RUNNING）
        """
        sm = self._get(session_id)
        sm.transition(SessionStatus.WAITING_INPUT)

        self._publisher.publish(
            session_id=session_id,
            event_type=EventType.SESSION_WAITING_INPUT,
            event_level=EventLevel.SESSION,
            producer="session_service",
        )

        logger.info("Session 等待用户输入: %s", session_id)
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

    def get_evidence(
        self,
        session_id: str,
        evidence_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """获取 Session 的证据列表。

        从 EventPublisher 的事件历史中提取 EVIDENCE_ADDED 事件。
        """
        self._get(session_id)
        events = self._publisher.get_events(session_id)
        evidence = []
        for evt in events:
            if evt.get("event_type") == "EVIDENCE_ADDED":
                payload = evt.get("payload", {})
                if evidence_type and payload.get("evidence_type") != evidence_type:
                    continue
                evidence.append(payload)
        return evidence[-limit:]

    def get_dimensions(self, session_id: str) -> dict:
        """获取 Session 的维度状态。

        从最新的 CHECKPOINTED 事件中提取维度状态。
        """
        sm = self._get(session_id)
        events = self._publisher.get_events(session_id)
        for evt in reversed(events):
            payload = evt.get("payload", {})
            if "dimension_status" in payload:
                return payload["dimension_status"]
        if sm._state.last_checkpoint_version > 0:
            return {"status": "available", "version": sm._state.last_checkpoint_version}
        return {"status": "no_data"}

    async def _run_analysis(
        self,
        session_id: str,
        agent,
        llm_client,
        tool_registry,
        config=None,
        section_descriptions=None,
        project_memory=None,
        requirement_text: str | None = None,
        resume_from: int | None = None,
    ) -> None:
        """异步执行分析，完成后驱动状态转换。"""
        from reqradar.cognitive_rt.cognition.runner import run_react_analysis

        try:
            await run_react_analysis(
                agent=agent,
                llm_client=llm_client,
                tool_registry=tool_registry,
                config=config,
                section_descriptions=section_descriptions,
                project_memory=project_memory,
                requirement_text=requirement_text,
                session_id=session_id,
                event_publisher=self._publisher,
                checkpoint_mgr=self._checkpoint_mgr,
                checkpoint_storage=self._checkpoint_storage,
                on_complete=self._on_analysis_complete,
                on_fail=self._on_analysis_fail,
                on_checkpoint=self._on_analysis_checkpoint,
            )
        except Exception as e:
            logger.error("Runner 执行异常: %s", e)
            try:
                self.fail(session_id, str(e))
            except Exception:
                logger.error("Session fail 转换也失败: session=%s", session_id)

    async def _on_analysis_complete(self, session_id: str) -> None:
        """Runner 完成回调。"""
        try:
            self.complete(session_id)
        except Exception as e:
            logger.error("Session complete 转换失败: session=%s, error=%s", session_id, e)

    async def _on_analysis_fail(self, session_id: str, error_message: str) -> None:
        """Runner 失败回调。"""
        try:
            self.fail(session_id, error_message)
        except Exception as e:
            logger.error("Session fail 转换失败: session=%s, error=%s", session_id, e)

    async def _on_analysis_checkpoint(
        self,
        session_id: str,
        checkpoint_type,
        version: int,
    ) -> None:
        """Runner Checkpoint 回调 — 驱动 RUNNING → CHECKPOINTING → RUNNING 转换。"""
        try:
            sm = self._get(session_id)
            if sm.status == SessionStatus.RUNNING:
                sm.transition(SessionStatus.CHECKPOINTING)
                sm._state.last_checkpoint_version = version
                sm.transition(SessionStatus.RUNNING)
            self._publisher.publish(
                session_id=session_id,
                event_type=EventType.SESSION_CHECKPOINTED,
                event_level=EventLevel.SESSION,
                producer="session_service",
                payload={
                    "version": version,
                    "checkpoint_type": checkpoint_type.value
                    if hasattr(checkpoint_type, "value")
                    else str(checkpoint_type),
                },
            )
        except Exception as e:
            logger.error("Checkpoint 回调状态转换失败: session=%s, error=%s", session_id, e)

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
