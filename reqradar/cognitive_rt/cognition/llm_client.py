"""LLM 客户端 — 封装 MiniMax API（OpenAI 兼容格式）。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import httpx

from reqradar.cognitive_rt.cognition.llm_utils import _parse_json_response

logger = logging.getLogger("reqradar.cognitive_rt.cognition.llm_client")


class LLMError(Exception):
    """LLM 调用异常。"""


class LiteLLMClient:
    """轻量 LLM 客户端，封装 OpenAI 兼容的 chat/completions 接口。"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self._model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self._base_url = (
            base_url or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._supports_tools: bool | None = None

        if not self._api_key:
            logger.warning("LLM_API_KEY 未配置，LLM 调用将失败")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Authorization": "Bearer %s" % self._api_key,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _call_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        """调用 chat/completions 接口，带重试。"""
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            start = time.monotonic()
            try:
                resp = await client.post("/chat/completions", json=payload)
                duration_ms = int((time.monotonic() - start) * 1000)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    logger.warning(
                        "LLM 速率限制，等待 %ds 后重试 (attempt %d/%d)",
                        retry_after,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code >= 400:
                    raise LLMError(
                        "LLM API 错误: status=%d, body=%s"
                        % (resp.status_code, resp.text[:500])
                    )

                data = resp.json()
                usage = data.get("usage", {})
                logger.info(
                    "LLM 调用完成: model=%s, prompt_tokens=%d, completion_tokens=%d, duration_ms=%d",
                    self._model,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    duration_ms,
                )
                return data

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "LLM 超时 (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries,
                    e,
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)
            except LLMError:
                raise
            except Exception as e:
                raise LLMError("LLM 调用异常: %s" % e) from e

        raise LLMError(
            "LLM 调用失败，已重试 %d 次: %s" % (self._max_retries, last_error)
        ) from last_error

    async def complete(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> str | None:
        """纯文本补全。"""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        data = await self._call_api(payload)
        choices = data.get("choices", [])
        if not choices:
            return None
        return choices[0].get("message", {}).get("content")

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        **kwargs: Any,
    ) -> dict | None:
        """结构化 JSON 输出 — 在 system prompt 中注入 JSON schema 约束。"""
        schema_instruction = (
            "你必须以严格的 JSON 格式响应，符合以下 schema:\n%s\n"
            "不要包含任何其他文本，只输出 JSON。"
            % json.dumps(schema, ensure_ascii=False)
        )
        enhanced_messages = list(messages)
        if enhanced_messages and enhanced_messages[0].get("role") == "system":
            enhanced_messages[0] = {
                "role": "system",
                "content": enhanced_messages[0]["content"] + "\n\n" + schema_instruction,
            }
        else:
            enhanced_messages.insert(
                0, {"role": "system", "content": schema_instruction}
            )

        response_text = await self.complete(enhanced_messages, **kwargs)
        if response_text is None:
            return None

        return _parse_json_response(response_text)

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Function calling — 传入 tools 参数到 API。"""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "tools": tools,
            "tool_choice": kwargs.get("tool_choice", "auto"),
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        data = await self._call_api(payload)
        return data

    async def supports_tool_calling(self) -> bool:
        """检测模型是否支持 tool calling。"""
        if self._supports_tools is not None:
            return self._supports_tools

        try:
            payload: dict[str, Any] = {
                "model": self._model,
                "messages": [{"role": "user", "content": "test"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "test_fn",
                            "description": "test",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
                "max_tokens": 10,
            }
            await self._call_api(payload)
            self._supports_tools = True
        except LLMError:
            self._supports_tools = False
            logger.info("模型 %s 不支持 tool calling", self._model)

        return self._supports_tools

    def estimate_tokens(
        self, messages: list[dict[str, str]] | list[dict[str, Any]]
    ) -> int:
        """估算 token 数（同步方法）。"""
        text = str(messages)
        return len(text) // 4
