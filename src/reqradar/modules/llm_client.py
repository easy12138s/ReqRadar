"""LLM 客户端 - OpenAI / Ollama"""

import time
from abc import ABC, abstractmethod

import httpx

from reqradar.core.exceptions import LLMException


class LLMClient(ABC):
    """LLM 客户端基类"""

    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """发送对话请求"""
        raise NotImplementedError

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """获取文本嵌入"""
        raise NotImplementedError


class OpenAIClient(LLMClient):
    """OpenAI API 客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """发送 OpenAI API 请求"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
        }

        for attempt in range(self.max_retries):
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
                if attempt == self.max_retries - 1:
                    raise LLMException(
                        f"OpenAI API timeout after {self.max_retries} attempts", cause=e
                    )
                time.sleep(2**attempt)
            except httpx.HTTPStatusError as e:
                raise LLMException(f"OpenAI API error: {e.response.status_code}", cause=e)
            except Exception as e:
                raise LLMException(f"OpenAI API request failed: {e}", cause=e)

        return ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """获取 OpenAI embeddings"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "text-embedding-3-small",
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
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

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
            except Exception as e:
                raise LLMException(f"Ollama request failed: {e}", cause=e)

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
                except Exception:
                    embeddings.append([0.0] * 1024)

        return embeddings


def create_llm_client(provider: str, **kwargs) -> LLMClient:
    """工厂函数：创建 LLM 客户端"""
    if provider == "openai":
        return OpenAIClient(**kwargs)
    elif provider == "ollama":
        return OllamaClient(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
