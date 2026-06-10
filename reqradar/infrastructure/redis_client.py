"""Redis 客户端封装 — 连接管理与内存降级。

当 Redis 不可用时自动降级为内存模式，保证开发环境和单元测试可独立运行。
支持基础 get/set/delete 操作和 Redis Streams 的 xadd/xread。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 客户端，支持连接失败时自动降级为内存模式。"""

    def __init__(self, url: str = "redis://localhost:6379") -> None:
        self._url = url
        self._redis: Any = None
        self.is_connected: bool = False
        self._memory_store: dict[str, tuple[Any, float | None]] = {}  # (value, expire_at)
        self._memory_streams: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    async def connect(self) -> None:
        """尝试连接 Redis，失败时降级为内存模式。"""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._url, decode_responses=True)
            await self._redis.ping()
            self.is_connected = True
            logger.info("Redis 连接成功: %s", self._url)
        except Exception as exc:
            self._redis = None
            self.is_connected = False
            logger.warning("Redis 连接失败，降级为内存模式: %s", exc)

    def _require_memory(self) -> None:
        if self.is_connected:
            raise RuntimeError("此方法仅在内存模式下调用")

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        """设置键值对。"""
        if self.is_connected and self._redis is not None:
            await self._redis.set(key, value, ex=ex)
        else:
            # 内存模式：记录过期时间
            expire_at = time.monotonic() + ex if ex is not None else None
            self._memory_store[key] = (value, expire_at)

    async def get(self, key: str) -> Any:
        """获取键对应的值，不存在返回 None。"""
        if self.is_connected and self._redis is not None:
            return await self._redis.get(key)
        # 内存模式：检查是否过期
        if key not in self._memory_store:
            return None
        value, expire_at = self._memory_store[key]
        if expire_at is not None and time.monotonic() > expire_at:
            del self._memory_store[key]
            return None
        return value

    async def delete(self, key: str) -> int:
        """删除键，返回删除数量。"""
        if self.is_connected and self._redis is not None:
            return await self._redis.delete(key)  # type: ignore[no-any-return]
        if key in self._memory_store:
            del self._memory_store[key]
            return 1
        return 0

    async def xadd(self, stream: str, data: dict[str, Any]) -> str:
        """向 Stream 追加消息，返回消息 ID。"""
        if self.is_connected and self._redis is not None:
            return await self._redis.xadd(stream, data)  # type: ignore[no-any-return]
        self._require_memory()
        if stream not in self._memory_streams:
            self._memory_streams[stream] = []
        message_id = f"{int(time.time() * 1000)}-{len(self._memory_streams[stream])}"
        self._memory_streams[stream].append((message_id, dict(data)))
        return message_id

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[tuple[str, list[tuple[str, dict[str, Any]]]]]:
        """从多个 Stream 读取消息。

        Args:
            streams: {stream_name: last_id} 映射，last_id="0" 表示从头读取。
            count: 每个 Stream 最多读取的消息数。
            block: 阻塞等待毫秒数（内存模式下为 no-op）。

        Returns:
            [(stream_name, [(message_id, data), ...]), ...]
        """
        if self.is_connected and self._redis is not None:
            return await self._redis.xread(streams, count=count, block=block)  # type: ignore[no-any-return]

        if block:
            await asyncio.sleep(block / 1000)

        result: list[tuple[str, list[tuple[str, dict[str, Any]]]]] = []
        for stream_name, last_id in streams.items():
            messages = self._memory_streams.get(stream_name, [])
            filtered = [
                (msg_id, data) for msg_id, data in messages if msg_id > last_id or last_id == "0"
            ]
            if count is not None:
                filtered = filtered[:count]
            if filtered:
                result.append((stream_name, filtered))
        return result
