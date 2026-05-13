"""Web 异常处理器单元测试"""

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from reqradar.core.exceptions import (
    ConfigException,
    FatalError,
    GitException,
    IndexException,
    LLMException,
    LoaderException,
    ParseException,
    ReportException,
    ReqRadarException,
    VectorStoreException,
    VisionNotConfiguredError,
)
from reqradar.web.exceptions import EXCEPTION_STATUS_MAP, reqradar_exception_handler


@pytest.fixture
def fake_request():
    from unittest.mock import MagicMock

    return MagicMock(spec=Request)


class TestExceptionStatusMap:
    def test_fatal_error_500(self):
        assert EXCEPTION_STATUS_MAP[FatalError] == 500

    def test_config_exception_500(self):
        assert EXCEPTION_STATUS_MAP[ConfigException] == 500

    def test_parse_exception_400(self):
        assert EXCEPTION_STATUS_MAP[ParseException] == 400

    def test_llm_exception_502(self):
        assert EXCEPTION_STATUS_MAP[LLMException] == 502

    def test_loader_exception_400(self):
        assert EXCEPTION_STATUS_MAP[LoaderException] == 400

    def test_vision_not_configured_501(self):
        assert EXCEPTION_STATUS_MAP[VisionNotConfiguredError] == 501


class TestReqRadarExceptionHandler:
    @pytest.mark.asyncio
    async def test_handles_base_exception(self, fake_request):
        exc = ReqRadarException("base error")
        response = await reqradar_exception_handler(fake_request, exc)
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_handles_fatal_error(self, fake_request):
        exc = FatalError("fatal")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_handles_parse_error_returns_400(self, fake_request):
        exc = ParseException("bad format")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_handles_llm_error_returns_502(self, fake_request):
        exc = LLMException("model down")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_handles_loader_error_returns_400(self, fake_request):
        exc = LoaderException("file not found")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_handles_vision_error_returns_501(self, fake_request):
        exc = VisionNotConfiguredError("no vision model")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 501

    @pytest.mark.asyncio
    async def test_response_contains_detail(self, fake_request):
        exc = ConfigException("missing key")
        response = await reqradar_exception_handler(fake_request, exc)
        body = json_loads_if_possible(response)
        assert body is not None
        assert body["detail"] == "missing key"

    @pytest.mark.asyncio
    async def test_subclass_matches_parent_status(self, fake_request):
        """子类异常应匹配父类的状态码"""
        exc = GitException("git failed")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_index_exception_status(self, fake_request):
        exc = IndexException("index corrupted")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_report_exception_status(self, fake_request):
        exc = ReportException("render failed")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_vector_store_exception_status(self, fake_request):
        exc = VectorStoreException("db error")
        response = await reqradar_exception_handler(fake_request, exc)
        assert response.status_code == 500


def json_loads_if_possible(response: JSONResponse):
    try:
        import json

        body_bytes = response.body
        if hasattr(body_bytes, "decode"):
            return json.loads(body_bytes.decode())
        if isinstance(response.body, dict):
            return response.body
    except Exception:
        return None
    return None
