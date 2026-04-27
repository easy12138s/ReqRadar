import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("reqradar.middleware.rate_limit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = {}

    def _cleanup(self, client_ip: str, now: float) -> None:
        if client_ip in self._requests:
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if now - t < 60
            ]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/health") or path.startswith("/app"):
            return await call_next(request)

        if request.url.scheme == "ws" or request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        self._cleanup(client_ip, now)
        requests = self._requests.setdefault(client_ip, [])
        if len(requests) >= self.requests_per_minute:
            logger.warning(
                "Rate limit exceeded for %s: %d requests/min",
                client_ip,
                len(requests),
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
        requests.append(now)
        return await call_next(request)
