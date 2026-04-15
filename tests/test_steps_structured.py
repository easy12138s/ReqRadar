"""测试 _call_llm_structured 降级逻辑"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from reqradar.agent.steps import EXTRACT_SCHEMA, _call_llm_structured, _parse_json_response


class TestCallLlmStructured:
    @pytest.mark.asyncio
    async def test_function_calling_succeeds(self):
        llm = AsyncMock()
        llm.complete_structured = AsyncMock(
            return_value={"summary": "test", "keywords": ["a", "b"]}
        )

        result = await _call_llm_structured(
            llm,
            messages=[{"role": "user", "content": "test"}],
            schema=EXTRACT_SCHEMA,
        )

        assert result["summary"] == "test"
        assert result["keywords"] == ["a", "b"]
        llm.complete_structured.assert_called_once()
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_text_parsing(self):
        llm = AsyncMock()
        llm.complete_structured = AsyncMock(return_value=None)
        llm.complete = AsyncMock(return_value='{"summary": "fallback", "keywords": ["x"]}')

        result = await _call_llm_structured(
            llm,
            messages=[{"role": "user", "content": "test"}],
            schema=EXTRACT_SCHEMA,
        )

        assert result["summary"] == "fallback"
        llm.complete_structured.assert_called_once()
        llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_with_markdown_code_block(self):
        llm = AsyncMock()
        llm.complete_structured = AsyncMock(return_value=None)
        llm.complete = AsyncMock(
            return_value='```json\n{"summary": "in block", "keywords": []}\n```'
        )

        result = await _call_llm_structured(
            llm,
            messages=[{"role": "user", "content": "test"}],
            schema=EXTRACT_SCHEMA,
        )

        assert result["summary"] == "in block"


class TestParseJsonResponse:
    def test_plain_json_object(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        result = _parse_json_response('Here is the result: {"key": "value"} End.')
        assert result == {"key": "value"}

    def test_json_array_of_strings(self):
        result = _parse_json_response('["alpha", "beta", "gamma"]')
        assert len(result) == 3
        assert result[0] == "alpha"

    def test_json_object_in_surrounding_text(self):
        result = _parse_json_response('Results:\n[{"id": "1"}]\nDone.')
        assert result == {"id": "1"}

    def test_markdown_code_block(self):
        result = _parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_markdown_code_block_array(self):
        result = _parse_json_response('```\n[{"id": "1"}]\n```')
        assert len(result) == 1

    def test_plain_string_array(self):
        data = '["alpha", "beta", "gamma"]'
        result = _parse_json_response(data)
        assert isinstance(result, list)
        assert len(result) == 3
