"""LLM 客户端 - OpenAI / Ollama，支持 function calling 结构化输出"""

import asyncio
import base64
import json
import logging
import re
from abc import ABC, abstractmethod

import httpx

from reqradar.agent.llm_utils import _parse_json_response
from reqradar.core.exceptions import LLMException

logger = logging.getLogger("reqradar.llm")


def _strip_thinking_tags(text: str) -> str:
    """Remove MiniMax-style ◀thinking▶ and ◀reasoning_content▶ tags from text."""
    text = re.sub(r'◀thinking▶.*?◀/thinking▶', '', text, flags=re.DOTALL)
    text = re.sub(r'◀reasoning_content▶.*?◀/reasoning_content▶', '', text, flags=re.DOTALL)
    return text.strip()


def _log_llm_call(
    caller: str,
    model: str,
    method: str,
    prompt_chars: int,
    completion_chars: int,
    duration_ms: int,
    success: bool,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    tool_calls_count: int = 0,
    tool_names: str = "",
    error_message: str | None = None,
    task_id: int | None = None,
):
    """Log an LLM call to the database (fire-and-forget)."""
    try:
        import asyncio
        from reqradar.web.models import LLMCallLog

        async def _write():
            import reqradar.web.dependencies as dep_module
            if dep_module.async_session_factory is None:
                return
            async with dep_module.async_session_factory() as session:
                log = LLMCallLog(
                    task_id=task_id,
                    caller=caller,
                    model=model,
                    method=method,
                    prompt_chars=prompt_chars,
                    completion_chars=completion_chars,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    duration_ms=duration_ms,
                    success=success,
                    tool_calls_count=tool_calls_count,
                    tool_names=tool_names,
                    error_message=error_message[:2000] if error_message else None,
                )
                session.add(log)
                await session.commit()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_write())
        except RuntimeError:
            pass
    except Exception:
        pass


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
        """检测当前模型是否支持 tool calling（function calling）"""
        if self._tool_calling_supported is not None:
            return self._tool_calling_supported

        model = getattr(self, "model", "unknown").lower()

        # Known models that support function calling
        KNOWN_TOOL_MODELS = (
            "minimax", "gpt-4", "gpt-3.5", "claude", "qwen", "deepseek",
            "gemini", "llama-3", "mixtral",
        )
        if any(m in model for m in KNOWN_TOOL_MODELS):
            self._tool_calling_supported = True
            return True

        # Fallback: probe once, don't cache failure
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
            if result is not None:
                self._tool_calling_supported = True
                return True
        except Exception:
            pass

        logger.warning(
            "Tool calling not detected for %s (model=%s). "
            "Falling back to structured text output.",
            self.__class__.__name__, model,
        )
        return False

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
        self._current_task_id: int | None = None

    def _build_headers(self) -> dict[str, str]:
        if not self.api_key or not str(self.api_key).strip():
            raise LLMException("OpenAI API key is missing or empty")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """发送 OpenAI API 请求"""
        import time
        headers = self._build_headers()
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        model_name = kwargs.get("model", self.model)
        t0 = time.monotonic()

        payload = {
            "model": model_name,
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
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    _log_llm_call(
                        caller="complete", model=model_name, method="complete",
                        prompt_chars=prompt_chars, completion_chars=len(content),
                        duration_ms=duration_ms, success=True,
                        prompt_tokens=usage.get("prompt_tokens"),
                        completion_tokens=usage.get("completion_tokens"),
                        total_tokens=usage.get("total_tokens"),
                        task_id=self._current_task_id,
                    )
                    return content
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
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        # Only force tool_choice when explicitly requested (some providers e.g. MiniMax
        # may return 400 if tool_choice is set but the model decides not to call it)
        # For complete_structured, we always want forced tool_choice since the caller
        # expects structured JSON output from a specific function.
        if "tool_choice" not in kwargs:
            payload["tool_choice"] = {"type": "function", "function": {"name": function_name}}

        import time
        prompt_chars = sum(len(m.get("content", "") or "") for m in messages)
        model_name = kwargs.get("model", self.model)
        t0 = time.monotonic()

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
                        content = _strip_thinking_tags(content)
                        try:
                            result_data = _parse_json_response(content)
                            usage = result.get("usage", {})
                            duration_ms = int((time.monotonic() - t0) * 1000)
                            _log_llm_call(
                                caller="complete_structured", model=model_name, method="complete_structured",
                                prompt_chars=prompt_chars, completion_chars=len(content),
                                duration_ms=duration_ms, success=True,
                                prompt_tokens=usage.get("prompt_tokens"),
                                completion_tokens=usage.get("completion_tokens"),
                                total_tokens=usage.get("total_tokens"),
                                task_id=self._current_task_id,
                            )
                            return result_data
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(
                                "No tool_calls and failed to parse content as JSON: %s", e
                            )
                    logger.debug("No tool_calls in function calling response, returning None")
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    _log_llm_call(
                        caller="complete_structured", model=model_name, method="complete_structured",
                        prompt_chars=prompt_chars, completion_chars=0,
                        duration_ms=duration_ms, success=False,
                        error_message="no_tool_calls_no_content",
                        task_id=self._current_task_id,
                    )
                    return None

                tool_call = tool_calls[0]
                arguments_str = tool_call["function"]["arguments"]

                try:
                    parsed = _parse_json_response(arguments_str)
                    usage = result.get("usage", {})
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    _log_llm_call(
                        caller="complete_structured", model=model_name, method="complete_structured",
                        prompt_chars=prompt_chars, completion_chars=len(arguments_str),
                        duration_ms=duration_ms, success=True,
                        prompt_tokens=usage.get("prompt_tokens"),
                        completion_tokens=usage.get("completion_tokens"),
                        total_tokens=usage.get("total_tokens"),
                        tool_calls_count=len(tool_calls),
                        task_id=self._current_task_id,
                    )
                    return parsed
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse function calling arguments: %s", e)
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    _log_llm_call(
                        caller="complete_structured", model=model_name, method="complete_structured",
                        prompt_chars=prompt_chars, completion_chars=len(arguments_str),
                        duration_ms=duration_ms, success=False,
                        error_message=f"json_parse_error: {e}",
                        tool_calls_count=len(tool_calls),
                        task_id=self._current_task_id,
                    )
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

        # MiniMax M2 recommends reasoning_split=True for cleaner output
        model_lower = payload["model"].lower()
        if "minimax" in model_lower or "mini-max" in model_lower:
            payload["reasoning_split"] = True

        if "tool_choice" in kwargs:
            payload["tool_choice"] = kwargs["tool_choice"]

        import time as _time
        _prompt_chars = sum(len(m.get("content", "") or "") for m in messages)
        _model_name = kwargs.get("model", self.model)
        _t0 = _time.monotonic()

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
                    reasoning_details = message.get("reasoning_details", [])

                    if tool_calls:
                        parsed_calls = []
                        tool_name_list = []
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            parsed_calls.append(
                                {
                                    "id": tc.get("id", ""),
                                    "name": fn.get("name", ""),
                                    "arguments": fn.get("arguments", "{}"),
                                }
                            )
                            tool_name_list.append(fn.get("name", ""))
                        usage = result.get("usage", {})
                        duration_ms = int((_time.monotonic() - _t0) * 1000)
                        logger.info(
                            "LLM complete_with_tools: model=%s tools=%s tool_calls=%d duration=%dms tokens=%s",
                            _model_name, tool_name_list, len(tool_calls), duration_ms,
                            usage.get("total_tokens", "?"),
                        )
                        _log_llm_call(
                            caller="complete_with_tools", model=_model_name, method="complete_with_tools",
                            prompt_chars=_prompt_chars, completion_chars=len(str(message)),
                            duration_ms=duration_ms, success=True,
                            prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"),
                            total_tokens=usage.get("total_tokens"),
                            tool_calls_count=len(tool_calls),
                            tool_names=",".join(tool_name_list),
                            task_id=self._current_task_id,
                        )
                        # Preserve full assistant message for MiniMax Interleaved Thinking
                        # reasoning_details must be retained across rounds for reasoning continuity.
                        return {"tool_calls": parsed_calls, "assistant_message": message}
                    elif content:
                        # Strip MiniMax thinking tags from content-only responses
                        cleaned = _strip_thinking_tags(content)
                        if cleaned.strip():
                            usage = result.get("usage", {})
                            duration_ms = int((_time.monotonic() - _t0) * 1000)
                            _log_llm_call(
                                caller="complete_with_tools", model=_model_name, method="complete_with_tools",
                                prompt_chars=_prompt_chars, completion_chars=len(cleaned),
                                duration_ms=duration_ms, success=True,
                                prompt_tokens=usage.get("prompt_tokens"),
                                completion_tokens=usage.get("completion_tokens"),
                                total_tokens=usage.get("total_tokens"),
                                task_id=self._current_task_id,
                            )
                            return {"content": cleaned}
                        return None
                    elif reasoning_details and not content.strip():
                        # Model only produced reasoning, no content
                        logger.debug("Model returned only reasoning, no content")
                        return None
                    else:
                        duration_ms = int((_time.monotonic() - _t0) * 1000)
                        _log_llm_call(
                            caller="complete_with_tools", model=_model_name, method="complete_with_tools",
                            prompt_chars=_prompt_chars, completion_chars=0,
                            duration_ms=duration_ms, success=False,
                            error_message="empty_response",
                            task_id=self._current_task_id,
                        )
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
                    # Don't retry 400s — the request format is wrong
                    return None
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
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
