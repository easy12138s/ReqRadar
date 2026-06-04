"""内部 API Key 认证中间件。

基于 S-01 第 5.1 节 Internal-API-Key 方案：
- 所有 /internal/ 路径必须携带 X-Internal-API-Key Header
- 缺失或错误的 Key 返回 403
- 非 /internal/ 路径不做校验
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class InternalAPIKeyMiddleware(BaseHTTPMiddleware):
    """内部 API Key 校验中间件。

    Args:
        app: ASGI 应用。
        api_key: 期望的内部 API Key。
    """

    def __init__(self, app: object, api_key: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith("/internal/"):
            return await call_next(request)

        provided_key = request.headers.get("X-Internal-API-Key", "")
        if provided_key != self._api_key:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: invalid or missing internal API key"},
            )

        return await call_next(request)
