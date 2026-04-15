"""测试 LLM 结构化输出（function calling）"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reqradar.modules.llm_client import OpenAIClient, OllamaClient


class TestOpenAIClientCompleteStructured:
    def _make_tool_response(self, arguments_dict):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "structured_output",
                                    "arguments": json.dumps(arguments_dict, ensure_ascii=False),
                                },
                                "id": "call_123",
                                "type": "function",
                            }
                        ]
                    }
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_complete_structured_success(self):
        client = OpenAIClient(api_key="test-key", model="test-model")

        schema = {
            "name": "extract_info",
            "description": "Extract information",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary"],
            },
        }

        mock_response = self._make_tool_response(
            {
                "summary": "测试摘要",
                "keywords": ["关键词1", "关键词2"],
            }
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_post = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.raise_for_status = MagicMock()
            mock_response_obj.json = MagicMock(return_value=mock_response)
            mock_post.return_value = mock_response_obj
            mock_client.post = mock_post

            result = await client.complete_structured(
                messages=[{"role": "user", "content": "test"}],
                schema=schema,
            )

        assert result is not None
        assert result["summary"] == "测试摘要"
        assert result["keywords"] == ["关键词1", "关键词2"]

    @pytest.mark.asyncio
    async def test_complete_structured_no_tool_calls(self):
        client = OpenAIClient(api_key="test-key", model="test-model")

        schema = {
            "name": "test",
            "description": "test",
            "parameters": {"type": "object", "properties": {}},
        }

        mock_response_data = {
            "choices": [{"message": {"content": "text response", "tool_calls": []}}]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_post = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.raise_for_status = MagicMock()
            mock_response_obj.json = MagicMock(return_value=mock_response_data)
            mock_post.return_value = mock_response_obj
            mock_client.post = mock_post

            result = await client.complete_structured(
                messages=[{"role": "user", "content": "test"}],
                schema=schema,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_complete_structured_400_returns_none(self):
        client = OpenAIClient(api_key="test-key", model="test-model")

        schema = {
            "name": "test",
            "description": "test",
            "parameters": {"type": "object", "properties": {}},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_post = AsyncMock()
            import httpx

            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 400
            mock_response_obj.text = "Bad Request"
            mock_post.side_effect = httpx.HTTPStatusError(
                "400 Bad Request", request=MagicMock(), response=mock_response_obj
            )
            mock_client.post = mock_post

            result = await client.complete_structured(
                messages=[{"role": "user", "content": "test"}],
                schema=schema,
            )

        assert result is None


class TestOllamaClientCompleteStructured:
    @pytest.mark.asyncio
    async def test_ollama_returns_none(self):
        client = OllamaClient(model="test-model", host="http://localhost:11434")
        result = await client.complete_structured(
            messages=[{"role": "user", "content": "test"}],
            schema={"name": "test"},
        )
        assert result is None
