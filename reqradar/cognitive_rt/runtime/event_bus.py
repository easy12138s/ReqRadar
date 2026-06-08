"""Event Bus — 支持内存模式与 Redis Stream 模式。"""

from __future__ import annotations

import json
import logging
import os
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
    """事件总线 — 内存模式 + Redis Stream 双模式。"""

    def __init__(self, max_len: int = 10000, redis_url: str = "") -> None:
        """初始化事件总线。

        Args:
            max_len: 每个 channel 的最大消息数
            redis_url: Redis 连接地址，为空时使用内存模式
        """
        self._max_len = max_len
        self._redis_url = redis_url or os.environ.get("REDIS_URL", "")
        self._redis = None
        self._channels: dict[str, list[BusMessage]] = defaultdict(list)
        self._subscribers: dict[str, list[object]] = defaultdict(list)
        self._connected = False

    async def connect(self) -> None:
        """连接 Redis，失败时降级为内存模式。"""
        if not self._redis_url:
            logger.warning("Redis URL 未配置，使用内存模式")
            return
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
            self._connected = True
            logger.info("EventBus Redis 连接成功: %s", self._redis_url)
        except Exception as e:
            logger.warning("EventBus Redis 连接失败，降级为内存模式: %s", e)
            self._redis = None
            self._connected = False

    async def publish(
        self,
        channel: str = "",
        message: BusMessage | None = None,
        event_record: object | None = None,
    ) -> str:
        """发布事件到总线。

        支持两种调用方式：
          1. publish(channel="...", message=BusMessage(...)) — 新接口
          2. publish(event_record=obj) — 兼容旧接口（从 event_record 提取 channel）

        Returns:
            消息 ID
        """
        if message is None and event_record is not None:
            session_id = getattr(event_record, "session_id", "unknown")
            channel = f"events:{session_id}"
            message = BusMessage(
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
        elif message is None:
            logger.warning("publish 调用缺少 message 或 event_record")
            return ""

        msg = message
        if not msg.message_id:
            msg.message_id = f"msg-{len(self._channels[channel])}"

        self._channels[channel].append(msg)

        if len(self._channels[channel]) > self._max_len:
            self._channels[channel] = self._channels[channel][-self._max_len :]

        for subscriber in self._subscribers.get(channel, []):
            if hasattr(subscriber, "on_message"):
                try:
                    await subscriber.on_message(msg)
                except Exception as e:
                    logger.warning("订阅者处理消息失败: %s", e)

        if self._connected and self._redis:
            try:
                await self._redis.xadd(
                    "reqradar:events:%s" % channel,
                    {"data": json.dumps(msg.data, default=str)},
                )
            except Exception as e:
                logger.warning("Redis xadd 失败: %s", e)

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

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._redis:
            await self._redis.close()
