"""LLM 客户端 - OpenAI / Ollama，支持 function calling 结构化输出"""

import asyncio
import base64
import json
import logging
from abc import ABC, abstractmethod

import httpx

from reqradar.agent.llm_utils import _parse_json_response
from reqradar.core.exceptions import LLMException

logger = logging.getLogger("reqradar.llm")


class LLMClient(ABC):
    """LLM 客户端基类"""

    def __init__(self):
        self._tool_calling_supported: bool | None = None

    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """发送对话请求"""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """获取文本嵌入"""
        pass

    async def complete_vision(self, image_data: bytes, prompt: str, **kwargs) -> str:
        """发送视觉请求（图片+文本）- 默认抛出 NotImplementedError"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support vision")

    async def supports_tool_calling(self) -> bool:
        """检测当前模型是否支持 tool calling（function calling）

        通过发送一个简单的 probe 请求来检测，结果会被缓存。
        """
        if self._tool_calling_supported is not None:
            return self._tool_calling_supported

        try:
            probe_schema = {
                "name": "probe_test",
                "description": "Probe test for tool calling support",
                "parameters": {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                },
            }
            result = await self.complete_structured(
                [{"role": "user", "content": "Reply with result 'ok'."}],
                probe_schema,
                max_tokens=50,
            )
            self._tool_calling_supported = result is not None
        except Exception:
            self._tool_calling_supported = False

        if not self._tool_calling_supported:
            logger.warning(
                "Tool calling not supported by %s (model=%s). "
                "Falling back to structured text output.",
                self.__class__.__name__,
                getattr(self, "model", "unknown"),
            )

        return self._tool_calling_supported

    async def complete_structured(
        self, messages: list[dict,], schema: dict, **kwargs
    ) -> dict | list | None:
        """使用 function calling 获取结构化 JSON 响应

        Args:
            messages: 对话消息列表
            schema: JSON Schema 格式的输出定义，会转换为 function/tool 定义
            **kwargs: 传递给 complete 的额外参数

        Returns:
            解析后的 dict 或 list，失败返回 None（调用方应降级到 complete + 文本解析）
        """
        return None

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """使用 tool_use 协议发送请求，支持多轮工具调用

        Args:
            messages: 对话消息列表（可包含tool角色的消息）
            tools: 工具定义列表（OpenAI tool format）
            **kwargs: 传递给API的额外参数

        Returns:
            dict with keys:
              - "tool_calls": list of {id, name, arguments} if LLM wants to call tools
              - "content": str if LLM responded with text only
              - "structured_output": dict if LLM called the output function
            None if request fails
        """
        return None


class OpenAIClient(LLMClient):
    """OpenAI API 客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 60,
        max_retries: int = 2,
        embedding_model: str = "text-embedding-3-small",
        embedding_dim: int = 1024,
    ):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim

    def _build_headers(self) -> dict[str, str]:
        if not self.api_key or not str(self.api_key).strip():
            raise LLMException("OpenAI API key is missing or empty")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """发送 OpenAI API 请求"""
        headers = self._build_headers()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = 2**attempt
                    logger.warning(
                        "OpenAI API timeout, retrying in %ds (attempt %d/%d)",
                        wait,
                        attempt + 1,
                        self.max_retries + 1,
                    )
                    await asyncio.sleep(wait)
                continue
            except httpx.HTTPStatusError as e:
                raise LLMException(f"OpenAI API error: {e.response.status_code}", cause=e)
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
                raise LLMException(f"OpenAI API request failed: {e}", cause=e)

        raise LLMException(
            f"OpenAI API timeout after {self.max_retries + 1} attempts", cause=last_error
        )

    async def complete_structured(
        self, messages: list[dict], schema: dict, **kwargs
    ) -> dict | list | None:
        """使用 function calling 获取结构化 JSON 响应"""
        headers = self._build_headers()

        function_name = schema.get("name", "structured_output")
        function_desc = schema.get("description", "Extract structured information")

        parameters = schema.get("parameters", schema)
        if "name" in parameters and "parameters" in parameters:
            parameters = parameters["parameters"]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": function_name,
                    "description": function_desc,
                    "parameters": parameters,
                },
            }
        ]

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "tools": tools,
            "tool_choice": {"type": "function", "function": {"name": function_name}},
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                message = result["choices"][0]["message"]
                tool_calls = message.get("tool_calls", [])
                content = message.get("content", "")

                if not tool_calls:
                    if content:
                        try:
                            return _parse_json_response(content)
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(
                                "No tool_calls and failed to parse content as JSON: %s", e
                            )
                    logger.warning("No tool_calls in function calling response, returning None")
                    return None

                tool_call = tool_calls[0]
                arguments_str = tool_call["function"]["arguments"]

                try:
                    parsed = _parse_json_response(arguments_str)
                    return parsed
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse function calling arguments: %s", e)
                    return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    error_body = ""
                    try:
                        error_body = e.response.text[:1000]
                    except Exception:
                        pass
                    tool_names = [t.get("function", {}).get("name", "?") for t in tools]
                    logger.warning(
                        "complete_structured 400 error for model=%s function=%s tool_choice=%s\nPayload keys: %s\nError body: %s",
                        payload.get("model"), function_name,
                        payload.get("tool_choice"), list(payload.keys()),
                        error_body,
                    )
                    return None
                raise LLMException(f"OpenAI API error: {e.response.status_code}", cause=e)
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                return None
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
                logger.warning("Function calling failed: %s", e)
            return None

        return None

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """使用 OpenAI tool_use 协议发送请求"""
        headers = self._build_headers()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "tools": tools,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        if "tool_choice" in kwargs:
            payload["tool_choice"] = kwargs["tool_choice"]

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    message = result["choices"][0]["message"]
                    tool_calls = message.get("tool_calls", [])
                    content = message.get("content", "")

                    if tool_calls:
                        parsed_calls = []
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            parsed_calls.append(
                                {
                                    "id": tc.get("id", ""),
                                    "name": fn.get("name", ""),
                                    "arguments": fn.get("arguments", "{}"),
                                }
                            )
                        return {"tool_calls": parsed_calls, "assistant_message": message}
                    elif content:
                        return {"content": content}
                    else:
                        return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    error_body = ""
                    try:
                        error_body = e.response.text[:1000]
                    except Exception:
                        pass
                    tool_names = [t.get("function", {}).get("name", "?") for t in tools]
                    logger.warning(
                        "complete_with_tools 400 error for model=%s tools=%s tool_choice=%s\nPayload keys: %s\nError body: %s",
                        payload.get("model"), tool_names,
                        payload.get("tool_choice"), list(payload.keys()),
                        error_body,
                    )
                    return None
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
                logger.warning("complete_with_tools failed: %s", e)
                return None

        return None

    async def complete_vision(self, image_data: bytes, prompt: str, **kwargs) -> str:
        """发送 OpenAI Vision API 请求"""
        headers = self._build_headers()

        b64_image = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:image/png;base64,{b64_image}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = 2**attempt
                    logger.warning(
                        "OpenAI Vision API timeout, retrying in %ds (attempt %d/%d)",
                        wait,
                        attempt + 1,
                        self.max_retries + 1,
                    )
                    await asyncio.sleep(wait)
                continue
            except httpx.HTTPStatusError as e:
                raise LLMException(f"OpenAI Vision API error: {e.response.status_code}", cause=e)
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
                raise LLMException(f"OpenAI Vision API request failed: {e}", cause=e)

        raise LLMException(
            f"OpenAI Vision API timeout after {self.max_retries + 1} attempts", cause=last_error
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """获取 OpenAI embeddings"""
        headers = self._build_headers()

        payload = {
            "model": self.embedding_model,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return [item["embedding"] for item in result["data"]]


class OllamaClient(LLMClient):
    """Ollama 本地模型客户端"""

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        host: str = "http://localhost:11434",
        timeout: int = 120,
        embedding_dim: int = 1024,
    ):
        super().__init__()
        self._tool_calling_supported = False
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.embedding_dim = embedding_dim

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """发送 Ollama 请求"""
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.host}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return result["message"]["content"]
            except httpx.TimeoutException as e:
                raise LLMException(f"Ollama request timed out after {self.timeout}s", cause=e)
            except httpx.HTTPStatusError as e:
                raise LLMException(f"Ollama API error: {e.response.status_code}", cause=e)
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
                raise LLMException(f"Ollama request failed: {e}", cause=e)

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """Ollama暂不支持tool_use协议，返回None触发降级"""
        return None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """获取 Ollama embeddings"""
        embeddings = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for text in texts:
                payload = {
                    "model": self.model,
                    "prompt": text,
                }
                try:
                    response = await client.post(
                        f"{self.host}/api/embeddings",
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    embeddings.append(result["embedding"])
                except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
                    logger.warning("Ollama embedding failed for text, using zero vector: %s", e)
                    embeddings.append([0.0] * self.embedding_dim)

        return embeddings


def create_llm_client(provider: str, **kwargs) -> LLMClient:
    """工厂函数：创建 LLM 客户端"""
    if provider == "openai":
        return OpenAIClient(**kwargs)
    elif provider == "ollama":
        return OllamaClient(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
