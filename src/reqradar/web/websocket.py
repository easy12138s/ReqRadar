import logging
from fastapi import WebSocket

logger = logging.getLogger("reqradar.web.websocket")


class ConnectionManager:
    def __init__(self):
        self._connections: dict[int, set[WebSocket]] = {}

    def subscribe(self, task_id: int, ws: WebSocket):
        if task_id not in self._connections:
            self._connections[task_id] = set()
        self._connections[task_id].add(ws)
        logger.info("WebSocket subscribed to task %d (total: %d)", task_id, len(self._connections[task_id]))

    def unsubscribe(self, task_id: int, ws: WebSocket):
        if task_id in self._connections:
            self._connections[task_id].discard(ws)
            if not self._connections[task_id]:
                del self._connections[task_id]
            logger.info("WebSocket unsubscribed from task %d", task_id)

    async def broadcast(self, task_id: int, event: dict):
        if task_id not in self._connections:
            return
        dead: list[WebSocket] = []
        for ws in self._connections[task_id]:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unsubscribe(task_id, ws)


manager = ConnectionManager()