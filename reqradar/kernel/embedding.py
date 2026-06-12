"""ReqRadar 嵌入函数 — API 调用模式，替代本地 ONNX 模型。

通过 HTTP API 调用 embedding 服务（支持 OpenAI / DeepSeek / Qwen 等兼容 API），
无需本地模型下载和 ONNX 运行时。

环境变量（遵循 C-03 规范，REQRADAR_ 前缀 + __ 分隔层级）：
    REQRADAR_EMBEDDING__PROVIDER:   供应商名称（默认 openai）
    REQRADAR_EMBEDDING__MODEL:      模型名称（默认 text-embedding-3-small）
    REQRADAR_EMBEDDING__API_KEY:    API Key
    REQRADAR_EMBEDDING__API_BASE:   API 地址（默认 https://api.openai.com/v1）
    REQRADAR_EMBEDDING__DIMENSIONS: 输出维度（默认 384，与现有 vector(384) 兼容）
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

# 最大重试次数
_MAX_RETRIES = 3
# 批处理大小
_BATCH_SIZE = 64


def _getenv(key_suffix: str, default: str) -> str:
    """读取环境变量，优先 REQRADAR_ 前缀版本。"""
    canonical = f"REQRADAR_{key_suffix}"
    value = os.environ.get(canonical)
    if value is not None:
        return value
    return os.environ.get(key_suffix, default)


class ReqRadarEmbeddingFunction:
    """API 调用的嵌入函数，兼容 OpenAI Embedding API 接口。

    用法::

        from reqradar.kernel.embedding import ReqRadarEmbeddingFunction

        ef = ReqRadarEmbeddingFunction()
        vectors = ef(["你好", "hello"])  # → list[list[float]]

    支持传递配置覆盖环境变量：

        ef = ReqRadarEmbeddingFunction(
            provider="openai",
            model="text-embedding-3-small",
            api_key="sk-xxx",
            api_base="https://api.openai.com/v1",
            dimensions=384,
        )
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self.provider = provider or _getenv(
            "EMBEDDING__PROVIDER", "openai"
        )
        self.model = model or _getenv(
            "EMBEDDING__MODEL", "text-embedding-3-small"
        )
        self.api_key = api_key or _getenv("EMBEDDING__API_KEY", "")
        self.api_base = api_base or _getenv(
            "EMBEDDING__API_BASE", "https://api.openai.com/v1"
        )
        self.dimensions = int(
            dimensions
            if dimensions is not None
            else int(_getenv("EMBEDDING__DIMENSIONS", "384"))
        )

        self._name = f"reqradar-{self.provider}-{self.model}"

    def name(self) -> str:
        return self._name

    def __call__(self, input: list[str]) -> list[list[float]]:
        if not input:
            return []

        import httpx

        all_embeddings: list[list[float]] = []

        for i in range(0, len(input), _BATCH_SIZE):
            batch = input[i : i + _BATCH_SIZE]
            result = self._call_api(batch, httpx)
            all_embeddings.extend(result)

        return all_embeddings

    def _call_api(self, texts: list[str], httpx_module) -> list[list[float]]:
        """调用 embedding API，含指数退避重试。"""
        url = f"{self.api_base.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
        }

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = httpx_module.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                # 按输入顺序提取 embedding
                items = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in items]

            except Exception as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        "Embedding API 调用失败 (attempt %d/%d): %s, %d 秒后重试",
                        attempt + 1, _MAX_RETRIES, e, delay,
                    )
                    time.sleep(delay)

        logger.error(
            "Embedding API 调用全部失败 (%d 次): %s", _MAX_RETRIES, last_error
        )
        return []
