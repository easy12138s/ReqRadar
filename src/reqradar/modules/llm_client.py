"""LLM 客户端 - 基于 LiteLLM 统一接入 100+ 语言模型厂商"""

import asyncio
import base64
import json
import logging
import time
from abc import ABC, abstractmethod

import litellm

from reqradar.agent.llm_utils import _parse_json_response, _strip_thinking_tags
from reqradar.core.exceptions import LLMException

logger = logging.getLogger("reqradar.llm")

# 禁用 LiteLLM 冗余日志（调试时改为 "INFO"）
litellm.set_verbose = False
litellm.suppress_debug_info = True


def _detect_mime_type(image_data: bytes) -> str:
    """根据魔术字节检测图片 MIME 类型"""
    header = image_data[:12]
    if header.startswith(b"\x89PNG"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"GIF8"):
        return "image/gif"
    if header.startswith(b"RIFF") and b"WEBP" in header:
        return "image/webp"
    if header.startswith(b"BM"):
        return "image/bmp"
    return "image/png"


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

    async def stream_complete(self, messages: list[dict], **kwargs):
        """流式调用，默认回退到 complete 方法"""
        result = await self.complete(messages, **kwargs)
        if result:
            yield result

    async def complete_vision(self, image_data: bytes, prompt: str, **kwargs) -> str:
        """发送视觉请求"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support vision")

    async def supports_tool_calling(self) -> bool:
        """检测当前模型是否支持 tool calling"""
        if self._tool_calling_supported is not None:
            return self._tool_calling_supported
        self._tool_calling_supported = True
        return True

    async def complete_structured(
        self, messages: list[dict], schema: dict, **kwargs
    ) -> dict | list | None:
        """使用 function calling 获取结构化 JSON 响应"""
        return None

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """使用 tool_use 协议发送请求"""
        return None


class LiteLLMClient(LLMClient):
    """基于 LiteLLM 的统一客户端，支持 100+ LLM 厂商。

    用法:
        # OpenAI
        client = LiteLLMClient(model="gpt-4o-mini", api_key="sk-xxx")

        # Anthropic
        client = LiteLLMClient(model="anthropic/claude-sonnet-4-20250514", api_key="sk-ant-xxx")

        # DeepSeek (via OpenAI-compatible endpoint)
        client = LiteLLMClient(model="deepseek/deepseek-chat", api_key="sk-xxx")

        # Ollama (via OpenAI-compatible endpoint, Ollama v0.5+)
        client = LiteLLMClient(model="ollama/qwen2.5:14b", api_base="http://localhost:11434/v1")

        # Custom OpenAI-compatible
        client = LiteLLMClient(model="gpt-4o-mini", api_key="sk-xxx", api_base="https://your.proxy.com/v1")
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str = "",
        base_url: str | None = None,
        api_base: str | None = None,
        host: str | None = None,
        timeout: int = 60,
        max_retries: int = 2,
    ):
        super().__init__()
        self.model = model
        self.api_key = api_key
        self.api_base = api_base or base_url or None
        if "ollama/" in model or self.api_base and "11434" in str(self.api_base):
            # Ollama: use host if api_base not set
            ollama_host = host or "http://localhost:11434"
            if not self.api_base:
                self.api_base = ollama_host.rstrip("/") + "/v1"
        self.timeout = timeout
        self.max_retries = max_retries
        self._current_task_id: int | None = None

    def _log(self, method: str, response, prompt_chars: int, t0: float, tool_count: int = 0):
        """统一的 LiteLLM 调用日志"""
        try:
            usage = getattr(response, "usage", None)
            content = getattr(response.choices[0].message, "content", "") or ""
            _log_llm_call(
                caller="complete",
                model=self.model,
                method=method,
                prompt_chars=prompt_chars,
                completion_chars=len(content),
                duration_ms=int((time.monotonic() - t0) * 1000),
                success=True,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
                tool_calls_count=tool_count,
                task_id=self._current_task_id,
            )
        except Exception:
            pass

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """发送对话请求 (LiteLLM 统一接口)"""
        model = kwargs.get("model", self.model)
        prompt_chars = sum(len(m.get("content", "") or "") for m in messages)
        t0 = time.monotonic()

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=self.api_key or None,
                api_base=self.api_base,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 1000),
                timeout=self.timeout,
                num_retries=self.max_retries,
            )
            content = response.choices[0].message.content or ""
            self._log("complete", response, prompt_chars, t0)
            return content
        except Exception as e:
            raise LLMException(f"LiteLLM complete failed: {e}", cause=e)

    async def stream_complete(self, messages: list[dict], **kwargs):
        """流式调用 (LiteLLM 统一接口)"""
        model = kwargs.get("model", self.model)
        t0 = time.monotonic()

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=self.api_key or None,
                api_base=self.api_base,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2048),
                stream=True,
                timeout=self.timeout + 60,
                num_retries=self.max_retries,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception as e:
            raise LLMException(f"LiteLLM stream failed: {e}", cause=e)

    async def complete_structured(
        self, messages: list[dict], schema: dict, **kwargs
    ) -> dict | list | None:
        """使用 tool calling 获取结构化 JSON 响应"""
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

        model = kwargs.get("model", self.model)
        prompt_chars = sum(len(m.get("content", "") or "") for m in messages)
        t0 = time.monotonic()

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=self.api_key or None,
                api_base=self.api_base,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": function_name}},
                temperature=kwargs.get("temperature", 0.3),
                max_tokens=kwargs.get("max_tokens", 2000),
                timeout=self.timeout,
                num_retries=self.max_retries,
            )

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
            content = message.content or ""

            if tool_calls:
                tc = tool_calls[0]
                args_str = tc.function.arguments
                try:
                    parsed = _parse_json_response(args_str)
                    self._log("complete_structured", response, prompt_chars, t0, tool_count=1)
                    return parsed
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse tool call arguments: %s", e)
                    return None

            if content.strip():
                content = _strip_thinking_tags(content)
                try:
                    parsed = _parse_json_response(content)
                    self._log("complete_structured", response, prompt_chars, t0)
                    return parsed
                except (json.JSONDecodeError, ValueError):
                    pass
            return None

        except Exception as e:
            logger.warning("complete_structured failed for model=%s: %s", model, e)
            return None

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """使用 tool_use 协议发送请求 (LiteLLM 统一接口)"""
        model = kwargs.get("model", self.model)
        prompt_chars = sum(len(m.get("content", "") or "") for m in messages)
        t0 = time.monotonic()

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=self.api_key or None,
                api_base=self.api_base,
                tools=tools,
                tool_choice=kwargs.get("tool_choice"),
                temperature=kwargs.get("temperature", 0.3),
                max_tokens=kwargs.get("max_tokens", 4096),
                timeout=self.timeout,
                num_retries=self.max_retries,
            )

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
            content = message.content or ""

            if tool_calls:
                parsed_calls = []
                tool_name_list = []
                for tc in tool_calls:
                    fn = tc.function
                    parsed_calls.append(
                        {
                            "id": tc.id or "",
                            "name": fn.name or "",
                            "arguments": fn.arguments or "{}",
                        }
                    )
                    tool_name_list.append(fn.name or "")
                usage = getattr(response, "usage", None)
                logger.info(
                    "LLM complete_with_tools: model=%s tools=%s tool_calls=%d tokens=%s",
                    model,
                    tool_name_list,
                    len(tool_calls),
                    getattr(usage, "total_tokens", "?"),
                )
                return {
                    "tool_calls": parsed_calls,
                    "assistant_message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]},
                            }
                            for tc in parsed_calls
                        ],
                    },
                }

            if content.strip():
                cleaned = _strip_thinking_tags(content)
                if cleaned.strip():
                    usage = getattr(response, "usage", None)
                    self._log("complete_with_tools", response, prompt_chars, t0)
                    return {"content": cleaned}
            return None

        except Exception as e:
            logger.warning("complete_with_tools failed for model=%s: %s", model, e)
            return None

    async def complete_vision(self, image_data: bytes, prompt: str, **kwargs) -> str:
        """发送视觉请求 (LiteLLM 统一接口)"""
        model = kwargs.get("model", self.model)
        b64_image = base64.b64encode(image_data).decode("utf-8")
        mime_type = _detect_mime_type(image_data)
        image_url = f"data:{mime_type};base64,{b64_image}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=self.api_key or None,
                api_base=self.api_base,
                max_tokens=kwargs.get("max_tokens", 1024),
                timeout=self.timeout,
                num_retries=self.max_retries,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise LLMException(f"LiteLLM vision failed: {e}", cause=e)


def create_llm_client(provider: str = "openai", **kwargs) -> LiteLLMClient:
    """工厂函数：创建 LiteLLM 统一客户端。

    LiteLLM 通过 model 参数自动路由到对应厂商，provider 参数保留向后兼容。
    """
    kwargs.pop("provider", None)
    return LiteLLMClient(**kwargs)
