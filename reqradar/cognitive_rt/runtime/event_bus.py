"""Event Bus 内存模拟 — P3 阶段的事件总线实现。"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BusMessage:
    """总线消息。"""

    channel: str
    data: dict
    message_id: str = ""


class InMemoryEventBus:
    """内存事件总线 — P3 阶段模拟 Redis Streams/Pub-Sub。"""

    def __init__(self, max_len: int = 10000) -> None:
        """初始化内存事件总线。

        Args:
            max_len: 每个 channel 的最大消息数
        """
        self._max_len = max_len
        self._channels: dict[str, list[BusMessage]] = defaultdict(list)
        self._subscribers: dict[str, list[object]] = defaultdict(list)

    def publish(self, event_record: object) -> str:
        """发布事件到总线。

        Args:
            event_record: 事件记录对象（需有 session_id 和 event_type 属性）

        Returns:
            消息 ID
        """
        session_id = getattr(event_record, "session_id", "unknown")
        channel = f"events:{session_id}"

        msg = BusMessage(
            channel=channel,
            data={
                "event_id": getattr(event_record, "event_id", ""),
                "event_type": str(getattr(event_record, "event_type", "")),
                "sequence": getattr(event_record, "sequence", 0),
                "timestamp": str(getattr(event_record, "timestamp", "")),
                "payload": getattr(event_record, "payload", {}),
            },
            message_id=f"msg-{len(self._channels[channel])}",
        )

        self._channels[channel].append(msg)

        # 限制消息数量
        if len(self._channels[channel]) > self._max_len:
            self._channels[channel] = self._channels[channel][-self._max_len :]

        # 通知订阅者
        for subscriber in self._subscribers.get(channel, []):
            try:
                subscriber.on_message(msg)
            except Exception as e:
                logger.warning(f"订阅者处理消息失败: {e}")

        return msg.message_id

    def subscribe(self, channel: str, subscriber: object) -> None:
        """订阅频道。"""
        self._subscribers[channel].append(subscriber)

    def unsubscribe(self, channel: str, subscriber: object) -> None:
        """取消订阅。"""
        if subscriber in self._subscribers.get(channel, []):
            self._subscribers[channel].remove(subscriber)

    def get_messages(self, channel: str) -> list[BusMessage]:
        """获取频道的所有消息。"""
        return list(self._channels.get(channel, []))

    def get_message_count(self, channel: str) -> int:
        """获取频道的消息数量。"""
        return len(self._channels.get(channel, []))

    def clear(self) -> None:
        """清除所有消息和订阅。"""
        self._channels.clear()
        self._subscribers.clear()
