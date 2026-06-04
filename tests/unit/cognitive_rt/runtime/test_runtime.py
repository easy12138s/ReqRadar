"""P3 Runtime Core 全面单元测试。

覆盖 Session 状态机、EventPublisher、InMemoryEventBus、
CheckpointManager、CheckpointStorage、CheckpointRecovery 以及端到端流程。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from reqradar.cognitive_rt.runtime.checkpoint import (
    CheckpointManager,
    CheckpointRecord,
    StateSummary,
)
from reqradar.cognitive_rt.runtime.checkpoint_recovery import (
    CheckpointRecovery,
)
from reqradar.cognitive_rt.runtime.checkpoint_storage import (
    CheckpointStorage,
    ColdStateStorage,
    HotStateStorage,
)
from reqradar.cognitive_rt.runtime.event_bus import InMemoryEventBus
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

# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

SESSION_ID = "test-session-001"
PROJECT_ID = "test-project-001"
USER_ID = "test-user-001"


@pytest.fixture
def state_machine() -> SessionStateMachine:
    """创建一个新的 CREATED 状态机实例。"""
    return create_session(SESSION_ID, PROJECT_ID, USER_ID)


@pytest.fixture
def event_publisher() -> EventPublisher:
    """创建一个新的事件发布器实例。"""
    return EventPublisher()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    """创建一个新的内存事件总线实例。"""
    return InMemoryEventBus()


@pytest.fixture
def checkpoint_manager() -> CheckpointManager:
    """创建一个新的 Checkpoint 管理器实例。"""
    return CheckpointManager()


@pytest.fixture
def state_summary() -> StateSummary:
    """创建一个测试用状态摘要。"""
    return StateSummary(
        current_step=1,
        total_steps=10,
        evidence_count=3,
        dimension_status={"performance": "in_progress", "security": "not_started"},
        context_usage=500,
        context_budget=4000,
    )


@pytest.fixture
def hot_storage() -> HotStateStorage:
    """创建一个新的热状态存储实例。"""
    return HotStateStorage(max_hot=3)


@pytest.fixture
def cold_storage() -> ColdStateStorage:
    """创建一个新的冷状态存储实例。"""
    return ColdStateStorage()


@pytest.fixture
def checkpoint_storage(
    hot_storage: HotStateStorage,
    cold_storage: ColdStateStorage,
) -> CheckpointStorage:
    """创建一个新的 Checkpoint 存储管理器实例。"""
    return CheckpointStorage(hot_storage=hot_storage, cold_storage=cold_storage)


# ===========================================================================
# TestSessionStateMachine — Session 状态机测试
# ===========================================================================


class TestSessionStateMachine:
    """Session 状态机的单元测试。"""

    def test_initial_state_is_created(self, state_machine: SessionStateMachine) -> None:
        """新建 Session 应处于 CREATED 状态。"""
        assert state_machine.status == SessionStatus.CREATED

    def test_created_to_ready_transition(self, state_machine: SessionStateMachine) -> None:
        """CREATED -> READY 转换应成功。"""
        state_machine.transition(SessionStatus.READY)
        assert state_machine.status == SessionStatus.READY

    def test_ready_to_running_transition(self, state_machine: SessionStateMachine) -> None:
        """READY -> RUNNING 转换应成功，且 started_at 被设置。"""
        state_machine.transition(SessionStatus.READY)
        assert state_machine.state.started_at is None

        state_machine.transition(SessionStatus.RUNNING)
        assert state_machine.status == SessionStatus.RUNNING
        assert state_machine.state.started_at is not None

    def test_running_to_completed_transition(self, state_machine: SessionStateMachine) -> None:
        """RUNNING -> COMPLETED 转换应成功，且 finished_at 被设置。"""
        state_machine.transition(SessionStatus.READY)
        state_machine.transition(SessionStatus.RUNNING)
        state_machine.transition(SessionStatus.COMPLETED)

        assert state_machine.status == SessionStatus.COMPLETED
        assert state_machine.state.finished_at is not None

    def test_invalid_transition_raises_error(self, state_machine: SessionStateMachine) -> None:
        """CREATED -> COMPLETED 是非法转换，应抛出 IllegalTransitionError。"""
        with pytest.raises(IllegalTransitionError) as exc_info:
            state_machine.transition(SessionStatus.COMPLETED)

        assert exc_info.value.current == SessionStatus.CREATED
        assert exc_info.value.target == SessionStatus.COMPLETED

    def test_idempotent_transition(self, state_machine: SessionStateMachine) -> None:
        """RUNNING -> RUNNING 的幂等转换应不报错。"""
        state_machine.transition(SessionStatus.READY)
        state_machine.transition(SessionStatus.RUNNING)

        result = state_machine.transition(SessionStatus.RUNNING)
        assert state_machine.status == SessionStatus.RUNNING
        assert result.status == SessionStatus.RUNNING

    def test_terminal_state_no_transition(self, state_machine: SessionStateMachine) -> None:
        """COMPLETED 是终态，不应再转换到其他状态。"""
        state_machine.transition(SessionStatus.READY)
        state_machine.transition(SessionStatus.RUNNING)
        state_machine.transition(SessionStatus.COMPLETED)

        with pytest.raises(IllegalTransitionError):
            state_machine.transition(SessionStatus.RUNNING)

    def test_status_history_recorded(self, state_machine: SessionStateMachine) -> None:
        """两次转换后，status_history 应有 2 条记录。"""
        state_machine.transition(SessionStatus.READY)
        state_machine.transition(SessionStatus.RUNNING)

        history = state_machine.state.status_history
        assert len(history) == 2

        assert history[0]["from"] == SessionStatus.CREATED.value
        assert history[0]["to"] == SessionStatus.READY.value

        assert history[1]["from"] == SessionStatus.READY.value
        assert history[1]["to"] == SessionStatus.RUNNING.value

    def test_cancel_sets_flag(self, state_machine: SessionStateMachine) -> None:
        """转换到 CANCELLING 应设置 cancel_requested 为 True。"""
        state_machine.transition(SessionStatus.READY)
        state_machine.transition(SessionStatus.RUNNING)
        state_machine.transition(SessionStatus.CANCELLING)

        assert state_machine.state.cancel_requested is True

    def test_error_message_recorded(self, state_machine: SessionStateMachine) -> None:
        """FAILED 转换应记录 error_message 和 error_type。"""
        state_machine.transition(SessionStatus.READY)
        state_machine.transition(SessionStatus.RUNNING)
        state_machine.transition(
            SessionStatus.FAILED,
            error_message="LLM 超时",
            error_type="LLMException",
        )

        assert state_machine.state.error_message == "LLM 超时"
        assert state_machine.state.error_type == "LLMException"

    def test_create_session_factory(self) -> None:
        """create_session() 工厂函数应返回 CREATED 状态的 SessionStateMachine。"""
        session = create_session("s1", "p1", "u1", config={"max_steps": 50})

        assert isinstance(session, SessionStateMachine)
        assert session.status == SessionStatus.CREATED
        assert session.state.session_id == "s1"
        assert session.state.project_id == "p1"
        assert session.state.user_id == "u1"
        assert session.state.config == {"max_steps": 50}


# ===========================================================================
# TestEventPublisher — 事件发布器测试
# ===========================================================================


class TestEventPublisher:
    """事件发布器的单元测试。"""

    def test_publish_creates_event(self, event_publisher: EventPublisher) -> None:
        """publish() 应返回包含正确字段的 EventRecord。"""
        record = event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test-producer",
            payload={"key": "value"},
        )

        assert record.session_id == SESSION_ID
        assert record.event_type == EventType.SESSION_CREATED
        assert record.event_level == EventLevel.SESSION
        assert record.producer == "test-producer"
        assert record.payload == {"key": "value"}
        assert record.event_id
        assert record.sequence == 1

    def test_sequence_auto_increment(self, event_publisher: EventPublisher) -> None:
        """第二个事件的 sequence 应为 2。"""
        event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test",
        )
        second = event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_STARTED,
            event_level=EventLevel.SESSION,
            producer="test",
        )

        assert second.sequence == 2

    def test_get_events_by_session(self, event_publisher: EventPublisher) -> None:
        """get_events() 应返回指定 Session 的所有事件。"""
        event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test",
        )
        event_publisher.publish(
            session_id="other-session",
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test",
        )

        events = event_publisher.get_events(SESSION_ID)
        assert len(events) == 1
        assert events[0].session_id == SESSION_ID

    def test_get_events_by_type(self, event_publisher: EventPublisher) -> None:
        """get_events_by_type() 应按事件类型正确过滤。"""
        event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test",
        )
        event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.STEP_STARTED,
            event_level=EventLevel.REASONING,
            producer="test",
        )
        event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.STEP_COMPLETED,
            event_level=EventLevel.REASONING,
            producer="test",
        )

        step_events = event_publisher.get_events_by_type(SESSION_ID, EventType.STEP_STARTED)
        assert len(step_events) == 1
        assert step_events[0].event_type == EventType.STEP_STARTED

    def test_clear_session(self, event_publisher: EventPublisher) -> None:
        """clear(session_id) 应仅清除指定 Session 的事件。"""
        event_publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test",
        )
        event_publisher.publish(
            session_id="other-session",
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test",
        )

        event_publisher.clear(SESSION_ID)

        assert event_publisher.get_event_count(SESSION_ID) == 0
        assert event_publisher.get_event_count("other-session") == 1

    def test_publish_to_bus(self) -> None:
        """当提供 bus 时，publish() 应调用 bus.publish()。"""
        mock_bus = MagicMock()
        publisher = EventPublisher(bus=mock_bus)

        record = publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="test",
        )

        mock_bus.publish.assert_called_once_with(record)


# ===========================================================================
# TestInMemoryEventBus — 内存事件总线测试
# ===========================================================================


class TestInMemoryEventBus:
    """内存事件总线的单元测试。"""

    def test_publish_creates_message(self, event_bus: InMemoryEventBus) -> None:
        """publish() 应返回 message_id。"""
        mock_event = MagicMock()
        mock_event.session_id = SESSION_ID
        mock_event.event_id = "evt-001"
        mock_event.event_type = EventType.SESSION_CREATED
        mock_event.sequence = 1
        mock_event.timestamp = "2026-01-01T00:00:00Z"
        mock_event.payload = {}

        msg_id = event_bus.publish(mock_event)
        assert msg_id
        assert isinstance(msg_id, str)

    def test_get_messages(self, event_bus: InMemoryEventBus) -> None:
        """get_messages() 应返回已发布的消息。"""
        mock_event = MagicMock()
        mock_event.session_id = SESSION_ID
        mock_event.event_id = "evt-001"
        mock_event.event_type = EventType.SESSION_CREATED
        mock_event.sequence = 1
        mock_event.timestamp = "2026-01-01T00:00:00Z"
        mock_event.payload = {}

        event_bus.publish(mock_event)
        channel = f"events:{SESSION_ID}"
        messages = event_bus.get_messages(channel)

        assert len(messages) == 1
        assert messages[0].channel == channel
        assert messages[0].data["event_id"] == "evt-001"

    def test_max_len_truncation(self) -> None:
        """消息数超过 max_len 时应被截断。"""
        bus = InMemoryEventBus(max_len=3)
        channel = f"events:{SESSION_ID}"

        for i in range(5):
            mock_event = MagicMock()
            mock_event.session_id = SESSION_ID
            mock_event.event_id = f"evt-{i:03d}"
            mock_event.event_type = EventType.STEP_STARTED
            mock_event.sequence = i + 1
            mock_event.timestamp = "2026-01-01T00:00:00Z"
            mock_event.payload = {}
            bus.publish(mock_event)

        messages = bus.get_messages(channel)
        assert len(messages) == 3
        assert messages[0].data["event_id"] == "evt-002"

    def test_subscribe_and_notify(self, event_bus: InMemoryEventBus) -> None:
        """订阅者应收到消息通知。"""
        subscriber = MagicMock()
        channel = f"events:{SESSION_ID}"
        event_bus.subscribe(channel, subscriber)

        mock_event = MagicMock()
        mock_event.session_id = SESSION_ID
        mock_event.event_id = "evt-001"
        mock_event.event_type = EventType.SESSION_CREATED
        mock_event.sequence = 1
        mock_event.timestamp = "2026-01-01T00:00:00Z"
        mock_event.payload = {}

        event_bus.publish(mock_event)

        subscriber.on_message.assert_called_once()
        received_msg = subscriber.on_message.call_args[0][0]
        assert received_msg.channel == channel


# ===========================================================================
# TestCheckpointManager — Checkpoint 管理器测试
# ===========================================================================


class TestCheckpointManager:
    """Checkpoint 管理器的单元测试。"""

    def test_create_checkpoint(
        self, checkpoint_manager: CheckpointManager, state_summary: StateSummary
    ) -> None:
        """创建的 Checkpoint 应有正确的版本号。"""
        cp = checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )

        assert cp.version == 1
        assert cp.session_id == SESSION_ID
        assert cp.type == CheckpointType.STEP_COMPLETE

    def test_version_auto_increment(
        self, checkpoint_manager: CheckpointManager, state_summary: StateSummary
    ) -> None:
        """第二个 Checkpoint 的 version 应为 2。"""
        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )
        cp2 = checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.PERIODIC,
            state_summary=state_summary,
        )

        assert cp2.version == 2

    def test_previous_version_chain(
        self, checkpoint_manager: CheckpointManager, state_summary: StateSummary
    ) -> None:
        """第二个 Checkpoint 的 previous_version 应为 1。"""
        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )
        cp2 = checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.PERIODIC,
            state_summary=state_summary,
        )

        assert cp2.previous_version == 1

    def test_get_latest(
        self, checkpoint_manager: CheckpointManager, state_summary: StateSummary
    ) -> None:
        """get_latest() 应返回最高版本的 Checkpoint。"""
        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )
        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.PERIODIC,
            state_summary=state_summary,
        )

        latest = checkpoint_manager.get_latest(SESSION_ID)
        assert latest is not None
        assert latest.version == 2

    def test_get_version(
        self, checkpoint_manager: CheckpointManager, state_summary: StateSummary
    ) -> None:
        """get_version() 应返回指定版本的 Checkpoint。"""
        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )
        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.PERIODIC,
            state_summary=state_summary,
        )

        cp1 = checkpoint_manager.get_version(SESSION_ID, 1)
        assert cp1 is not None
        assert cp1.version == 1

        cp2 = checkpoint_manager.get_version(SESSION_ID, 2)
        assert cp2 is not None
        assert cp2.version == 2

        assert checkpoint_manager.get_version(SESSION_ID, 99) is None

    def test_diff_computation(self, checkpoint_manager: CheckpointManager) -> None:
        """两个 Checkpoint 之间的 diff 应正确追踪维度变化。"""
        summary1 = StateSummary(
            current_step=1,
            total_steps=10,
            dimension_status={"performance": "in_progress", "security": "not_started"},
        )
        summary2 = StateSummary(
            current_step=2,
            total_steps=10,
            dimension_status={
                "performance": "completed",
                "security": "in_progress",
                "usability": "not_started",
            },
        )

        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=summary1,
        )
        cp2 = checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.PERIODIC,
            state_summary=summary2,
        )

        assert "usability" in cp2.diff["added"]
        assert "performance" in cp2.diff["modified"]
        assert "security" in cp2.diff["modified"]
        assert len(cp2.diff["removed"]) == 0


# ===========================================================================
# TestCheckpointStorage — Checkpoint 存储测试
# ===========================================================================


class TestCheckpointStorage:
    """Checkpoint 存储（热/冷/协调）的单元测试。"""

    def test_hot_storage_save_load(
        self, hot_storage: HotStateStorage, state_summary: StateSummary
    ) -> None:
        """HotStateStorage 的 save/load 应正确工作。"""
        record = CheckpointRecord(
            checkpoint_id="cp-001",
            session_id=SESSION_ID,
            version=1,
            previous_version=None,
            created_at=datetime.now(UTC),
            created_by="test",
            type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )
        hot_storage.save(record)

        loaded = hot_storage.load(SESSION_ID)
        assert loaded is not None
        assert loaded["version"] == 1
        assert loaded["checkpoint_id"] == "cp-001"

    def test_hot_storage_max_limit(self) -> None:
        """热状态存储应只保留最近 N 个状态。"""
        storage = HotStateStorage(max_hot=2)

        for i in range(4):
            record = MagicMock()
            record.session_id = SESSION_ID
            record.checkpoint_id = f"cp-{i:03d}"
            record.version = i + 1
            record.state_summary = StateSummary()
            record.hot_state = {}
            record.created_at = "2026-01-01T00:00:00Z"
            storage.save(record)

        states = storage.get_all(SESSION_ID)
        assert len(states) == 2
        assert states[0]["version"] == 3
        assert states[1]["version"] == 4

    def test_cold_storage_memory_uri(
        self, cold_storage: ColdStateStorage, state_summary: StateSummary
    ) -> None:
        """无 base_path 的 ColdStateStorage 应使用 memory:// URI。"""
        record = CheckpointRecord(
            checkpoint_id="cp-001",
            session_id=SESSION_ID,
            version=1,
            previous_version=None,
            created_at=datetime.now(UTC),
            created_by="test",
            type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )

        uri = cold_storage.save(record)
        assert uri is not None
        assert uri.startswith("memory://")

        loaded = cold_storage.load(uri)
        assert loaded is not None
        assert loaded["checkpoint_id"] == "cp-001"

    def test_cold_storage_file(self, tmp_path) -> None:
        """有 base_path 的 ColdStateStorage 应写入 JSON 文件。"""
        from types import SimpleNamespace

        storage = ColdStateStorage(base_path=tmp_path)

        record = SimpleNamespace(
            checkpoint_id="cp-001",
            session_id=SESSION_ID,
            version=1,
            created_at="2026-01-01T00:00:00Z",
            state_summary={"step": 1},
            hot_state={},
        )

        uri = storage.save(record)
        assert uri is not None

        loaded = storage.load(uri)
        assert loaded is not None
        assert loaded["checkpoint_id"] == "cp-001"

        with open(uri, encoding="utf-8") as f:
            data = json.load(f)
        assert data["session_id"] == SESSION_ID

    def test_checkpoint_storage_coordinates(
        self,
        checkpoint_storage: CheckpointStorage,
        state_summary: StateSummary,
    ) -> None:
        """CheckpointStorage 应同时保存到热区和冷区。"""
        record = CheckpointRecord(
            checkpoint_id="cp-001",
            session_id=SESSION_ID,
            version=1,
            previous_version=None,
            created_at=datetime.now(UTC),
            created_by="test",
            type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )

        checkpoint_storage.save(record)

        hot_loaded = checkpoint_storage.load_latest(SESSION_ID)
        assert hot_loaded is not None
        assert hot_loaded["version"] == 1


# ===========================================================================
# TestCheckpointRecovery — Checkpoint 恢复测试
# ===========================================================================


class TestCheckpointRecovery:
    """Checkpoint 恢复器的单元测试。"""

    def test_recover_latest(
        self, checkpoint_manager: CheckpointManager, state_summary: StateSummary
    ) -> None:
        """应能从最新 Checkpoint 恢复。"""
        checkpoint_manager.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=state_summary,
        )

        mock_storage = MagicMock()
        mock_storage.load_latest.return_value = {
            "checkpoint_id": "cp-001",
            "session_id": SESSION_ID,
            "version": 1,
        }

        recovery = CheckpointRecovery(storage=mock_storage)
        result = recovery.recover(SESSION_ID)

        assert result.success is True
        assert result.version == 1
        assert result.restored_state["checkpoint_id"] == "cp-001"

    def test_recover_specific_version(
        self, checkpoint_manager: CheckpointManager, state_summary: StateSummary
    ) -> None:
        """应能从指定版本的 Checkpoint 恢复。"""
        mock_storage = MagicMock()
        mock_storage.load_version.return_value = {
            "checkpoint_id": "cp-002",
            "session_id": SESSION_ID,
            "version": 2,
        }

        recovery = CheckpointRecovery(storage=mock_storage)
        result = recovery.recover(SESSION_ID, version=2)

        assert result.success is True
        assert result.version == 2
        mock_storage.load_version.assert_called_once_with(SESSION_ID, 2)

    def test_recover_no_checkpoint_fails(self) -> None:
        """无 Checkpoint 时恢复应失败。"""
        mock_storage = MagicMock()
        mock_storage.load_latest.return_value = None

        recovery = CheckpointRecovery(storage=mock_storage)
        result = recovery.recover(SESSION_ID)

        assert result.success is False
        assert "未找到 Checkpoint" in result.error_message

    def test_recover_with_evidence_validation(self) -> None:
        """Evidence 链有效时恢复应成功。"""
        mock_storage = MagicMock()
        mock_storage.load_latest.return_value = {
            "checkpoint_id": "cp-001",
            "session_id": SESSION_ID,
            "version": 1,
        }

        mock_event_store = MagicMock()
        event1 = MagicMock()
        event1.sequence = 1
        event2 = MagicMock()
        event2.sequence = 2
        event3 = MagicMock()
        event3.sequence = 3
        mock_event_store.get_events.return_value = [event1, event2, event3]

        recovery = CheckpointRecovery(storage=mock_storage, event_store=mock_event_store)
        result = recovery.recover(SESSION_ID)

        assert result.success is True
        assert result.evidence_chain_valid is True


# ===========================================================================
# TestEndToEndRuntimeFlow — 端到端运行时流程测试
# ===========================================================================


class TestEndToEndRuntimeFlow:
    """端到端运行时流程的集成测试。"""

    def test_full_lifecycle(self) -> None:
        """完整生命周期：CREATE -> READY -> RUNNING -> checkpoint -> COMPLETED。"""
        session = create_session(SESSION_ID, PROJECT_ID, USER_ID)
        publisher = EventPublisher()
        checkpoint_mgr = CheckpointManager()

        assert session.status == SessionStatus.CREATED
        publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CREATED,
            event_level=EventLevel.SESSION,
            producer="runtime",
        )

        session.transition(SessionStatus.READY)
        session.transition(SessionStatus.RUNNING)
        publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_STARTED,
            event_level=EventLevel.SESSION,
            producer="runtime",
        )

        summary = StateSummary(
            current_step=5,
            total_steps=10,
            dimension_status={"performance": "completed"},
        )
        cp = checkpoint_mgr.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=summary,
        )
        assert cp.version == 1

        session.transition(SessionStatus.COMPLETED)
        publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_COMPLETED,
            event_level=EventLevel.SESSION,
            producer="runtime",
        )

        assert session.status == SessionStatus.COMPLETED
        assert session.is_terminal()
        assert session.state.finished_at is not None
        assert publisher.get_event_count(SESSION_ID) == 3

    def test_cancel_flow(self) -> None:
        """取消流程：RUNNING -> CANCELLING -> CANCELLED。"""
        session = create_session(SESSION_ID, PROJECT_ID, USER_ID)
        publisher = EventPublisher()

        session.transition(SessionStatus.READY)
        session.transition(SessionStatus.RUNNING)

        session.transition(SessionStatus.CANCELLING)
        assert session.state.cancel_requested is True
        publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CANCELLING,
            event_level=EventLevel.SESSION,
            producer="runtime",
        )

        session.transition(SessionStatus.CANCELLED)
        publisher.publish(
            session_id=SESSION_ID,
            event_type=EventType.SESSION_CANCELLED,
            event_level=EventLevel.SESSION,
            producer="runtime",
        )

        assert session.status == SessionStatus.CANCELLED
        assert session.is_terminal()
        assert publisher.get_event_count(SESSION_ID) == 2

    def test_checkpoint_recovery_flow(self) -> None:
        """Checkpoint 恢复流程：RUNNING -> checkpoint -> 恢复 -> 验证状态。"""
        session = create_session(SESSION_ID, PROJECT_ID, USER_ID)
        checkpoint_mgr = CheckpointManager()

        session.transition(SessionStatus.READY)
        session.transition(SessionStatus.RUNNING)

        summary = StateSummary(
            current_step=3,
            total_steps=10,
            evidence_count=5,
            dimension_status={"performance": "in_progress", "security": "completed"},
        )
        checkpoint_mgr.create_checkpoint(
            session_id=SESSION_ID,
            checkpoint_type=CheckpointType.STEP_COMPLETE,
            state_summary=summary,
            hot_state={"step": 3, "context": "partial"},
        )

        latest = checkpoint_mgr.get_latest(SESSION_ID)
        assert latest is not None
        assert latest.version == 1
        assert latest.state_summary.current_step == 3
        assert latest.state_summary.evidence_count == 5

        mock_storage = MagicMock()
        mock_storage.load_latest.return_value = {
            "checkpoint_id": latest.checkpoint_id,
            "session_id": SESSION_ID,
            "version": 1,
        }

        recovery = CheckpointRecovery(storage=mock_storage)
        result = recovery.recover(SESSION_ID)

        assert result.success is True
        assert result.version == 1
        assert result.restored_state["session_id"] == SESSION_ID
