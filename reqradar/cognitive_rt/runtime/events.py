"""Event Stream 发布器 — 结构化推理链事件管理。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from reqradar.kernel.enums import EventLevel, EventType

logger = logging.getLogger(__name__)


@dataclass
class EventRecord:
    """事件记录。"""

    event_id: str
    session_id: str
    sequence: int
    event_type: EventType
    event_level: EventLevel
    timestamp: datetime
    producer: str
    payload: dict = field(default_factory=dict)


class EventPublisher:
    """事件发布器 — 发布事件到内存存储和可选的外部总线。"""

    def __init__(self, bus: object | None = None) -> None:
        """初始化事件发布器。

        Args:
            bus: 可选的事件总线（实现 publish 方法）
        """
        self._bus = bus
        self._events: dict[str, list[EventRecord]] = {}  # session_id -> events
        self._sequences: dict[str, int] = {}  # session_id -> next sequence

    def publish(
        self,
        session_id: str,
        event_type: EventType,
        event_level: EventLevel,
        producer: str,
        payload: dict | None = None,
    ) -> EventRecord:
        """发布一个事件。

        Args:
            session_id: Session ID
            event_type: 事件类型
            event_level: 事件层级
            producer: 事件生产者
            payload: 事件负载

        Returns:
            创建的事件记录
        """
        seq = self._sequences.get(session_id, 0) + 1
        self._sequences[session_id] = seq

        record = EventRecord(
            event_id=str(uuid4()),
            session_id=session_id,
            sequence=seq,
            event_type=event_type,
            event_level=event_level,
            timestamp=datetime.now(UTC),
            producer=producer,
            payload=payload or {},
        )

        if session_id not in self._events:
            self._events[session_id] = []
        self._events[session_id].append(record)

        # 推送到外部总线
        if self._bus is not None:
            try:
                self._bus.publish(record)
            except Exception as e:
                logger.warning("事件总线推送失败: %s", e)

        logger.debug(
            "事件发布: session=%s, type=%s, level=%s, seq=%s",
            session_id,
            event_type.value,
            event_level.value,
            seq,
        )
        return record

    def get_events(self, session_id: str) -> list[EventRecord]:
        """获取指定 Session 的所有事件。"""
        return list(self._events.get(session_id, []))

    def get_events_by_type(self, session_id: str, event_type: EventType) -> list[EventRecord]:
        """按事件类型过滤。"""
        return [e for e in self.get_events(session_id) if e.event_type == event_type]

    def get_event_count(self, session_id: str) -> int:
        """获取指定 Session 的事件数量。"""
        return len(self._events.get(session_id, []))

    def clear(self, session_id: str | None = None) -> None:
        """清除事件记录。"""
        if session_id:
            self._events.pop(session_id, None)
            self._sequences.pop(session_id, None)
        else:
            self._events.clear()
            self._sequences.clear()
