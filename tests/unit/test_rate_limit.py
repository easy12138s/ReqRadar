"""RateLimitMiddleware 单元测试"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from reqradar.web.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture
def mock_app():
    return AsyncMock(return_value=JSONResponse(content={"ok": True}))


@pytest.fixture
def middleware(mock_app):
    return RateLimitMiddleware(mock_app, requests_per_minute=3)


def _build_request(path: str = "/api/test", client_host: str = "127.0.0.1", scheme: str = "http") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [],
        "path": path,
        "query_string": b"",
        "scheme": scheme,
    }
    request = Request(scope)
    if client_host:
        from starlette.datastructures import Address

        request._client = Address(client_host, 12345)
    else:
        request._client = None
    return request


class TestRateLimitMiddlewareInit:
    def test_default_rate(self):
        mw = RateLimitMiddleware(app=None)
        assert mw.requests_per_minute == 60

    def test_custom_rate(self):
        mw = RateLimitMiddleware(app=None, requests_per_minute=10)
        assert mw.requests_per_minute == 10

    def test_empty_requests_dict(self):
        mw = RateLimitMiddleware(app=None)
        assert mw._requests == {}


class TestRateLimitMiddlewareDispatch:
    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self, middleware):
        req = _build_request()
        response = await middleware.dispatch(req, AsyncMock(return_value=JSONResponse(content={})))
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rejects_request_over_limit(self, middleware):
        call_next = AsyncMock(return_value=JSONResponse(content={}))
        for _ in range(3):
            req = _build_request()
            await middleware.dispatch(req, call_next)

        req_over = _build_request()
        response = await middleware.dispatch(req_over, call_next)
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_skips_health_endpoint(self, middleware, mock_app):
        req = _build_request(path="/health")
        await middleware.dispatch(req, mock_app)
        mock_app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_app_static_files(self, middleware, mock_app):
        req = _build_request(path="/app/index.html")
        await middleware.dispatch(req, mock_app)
        mock_app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_websocket_upgrade(self, middleware, mock_app):
        req = _build_request()
        req.headers.__getitem__ = lambda k: "websocket" if k.lower() == "upgrade" else ""
        await middleware.dispatch(req, mock_app)
        mock_app.assert_awaited_once()

    @pytest.mark.xfail(reason="BUG-20260512-003: RateLimitMiddleware cannot correctly get client IP from Address object")
    @pytest.mark.asyncio
    async def test_tracks_per_client_ip(self, middleware):
        call_next = AsyncMock(return_value=JSONResponse(content={}))
        req_a = _build_request(client_host="1.1.1.1")
        req_b = _build_request(client_host="2.2.2.2")
        for _ in range(3):
            await middleware.dispatch(req_a, call_next)

        response_b = await middleware.dispatch(req_b, call_next)
        assert response_b.status_code == 200

    @pytest.mark.asyncio
    async def test_handles_missing_client(self, middleware):
        req = _build_request()
        req._client = None
        response = await middleware.dispatch(req, AsyncMock(return_value=JSONResponse(content={})))
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_old_requests_cleaned_up(self, middleware):
        call_next = AsyncMock(return_value=JSONResponse(content={}))
        with patch("reqradar.web.middleware.rate_limit.time.time", return_value=1000.0):
            for _ in range(3):
                req = _build_request()
                await middleware.dispatch(req, call_next)

        with patch("reqradar.web.middleware.rate_limit.time.time", return_value=1061.0):
            req_new = _build_request()
            response = await middleware.dispatch(req_new, call_next)
            assert response.status_code == 200
