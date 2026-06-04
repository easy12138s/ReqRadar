"""WebSocket 连接管理 — Session 事件实时推送。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    """WebSocket 连接。"""
    connection_id: str
    session_id: str
    connected: bool = True
    send_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class ConnectionManager:
    """WebSocket 连接管理器。"""
    
    def __init__(self) -> None:
        """初始化连接管理器。"""
        self._connections: dict[str, list[WSConnection]] = {}  # session_id -> connections
    
    def connect(self, connection_id: str, session_id: str) -> WSConnection:
        """注册新连接。
        
        Args:
            connection_id: 连接 ID
            session_id: Session ID
            
        Returns:
            连接对象
        """
        conn = WSConnection(connection_id=connection_id, session_id=session_id)
        
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(conn)
        
        logger.info(f"WS 连接建立: {connection_id} -> session={session_id}")
        return conn
    
    def disconnect(self, connection_id: str, session_id: str) -> None:
        """断开连接。
        
        Args:
            connection_id: 连接 ID
            session_id: Session ID
        """
        conns = self._connections.get(session_id, [])
        self._connections[session_id] = [c for c in conns if c.connection_id != connection_id]
        
        if not self._connections[session_id]:
            del self._connections[session_id]
        
        logger.info(f"WS 连接断开: {connection_id}")
    
    async def broadcast(self, session_id: str, event_data: dict) -> int:
        """向指定 Session 的所有连接广播事件。
        
        Args:
            session_id: Session ID
            event_data: 事件数据
            
        Returns:
            成功推送的连接数
        """
        conns = self._connections.get(session_id, [])
        sent = 0
        
        for conn in conns:
            if conn.connected:
                try:
                    await conn.send_queue.put(json.dumps(event_data, ensure_ascii=False))
                    sent += 1
                except Exception as e:
                    logger.warning(f"WS 推送失败: {e}")
                    conn.connected = False
        
        return sent
    
    def get_connection_count(self, session_id: str | None = None) -> int:
        """获取连接数。"""
        if session_id:
            return len(self._connections.get(session_id, []))
        return sum(len(conns) for conns in self._connections.values())
    
    def get_session_ids(self) -> list[str]:
        """获取所有有连接的 Session ID。"""
        return list(self._connections.keys())
