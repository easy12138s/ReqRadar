"""ReqRadar 嵌入函数 — 从 HuggingFace 镜像下载 ONNX 模型，不依赖 S3。

设计目标：
1. 不依赖 S3（chromadb 内置 ONNXMiniLM_L6_V2 从 S3 下载，国内不可用）
2. 通过 HF_ENDPOINT 环境变量支持镜像加速
3. 支持离线模式（模型已缓存时不需要网络）
4. Docker 构建时预下载，运行时零延迟
5. 可配置模型仓库、缓存路径、精度

环境变量（遵循 C-03 规范，REQRADAR_ 前缀 + __ 分隔层级）：
    REQRADAR_EMBEDDING__HF_ENDPOINT: HuggingFace 镜像地址（默认 https://hf-mirror.com）
    REQRADAR_EMBEDDING__MODEL_REPO: ONNX 模型仓库 ID（默认 onnx-community/all-MiniLM-L6-v2-ONNX）
    REQRADAR_EMBEDDING__MODEL_CACHE: 模型缓存路径（默认 ~/.cache/reqradar/embedding）
    REQRADAR_EMBEDDING__PRECISION: 模型精度 fp32/fp16/q4（默认 fp16）

    向后兼容旧变量名（优先使用 REQRADAR_ 前缀版本）：
    HF_ENDPOINT / EMBEDDING_MODEL_REPO / EMBEDDING_MODEL_CACHE / EMBEDDING_PRECISION
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_MODEL_REPO = "onnx-community/all-MiniLM-L6-v2-ONNX"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
_DEFAULT_CACHE_DIR: str | None = None


def _get_default_cache_dir() -> str:
    """获取默认模型缓存目录（惰性计算，避免模块级环境变量读取）。"""
    global _DEFAULT_CACHE_DIR
    if _DEFAULT_CACHE_DIR is None:
        _DEFAULT_CACHE_DIR = _getenv(
            "EMBEDDING__MODEL_CACHE",
            os.path.expanduser("~/.cache/reqradar/embedding"),
        )
    return _DEFAULT_CACHE_DIR


def _getenv(key_suffix: str, default: str) -> str:
    """读取环境变量，优先 REQRADAR_ 前缀版本，向后兼容旧变量名。

    C-03 规范要求环境变量以 REQRADAR_ 为前缀、__ 分隔层级。
    例如 embedding.hf_endpoint → REQRADAR_EMBEDDING__HF_ENDPOINT。
    同时兼容旧变量名（HF_ENDPOINT 等），便于 HuggingFace 生态工具直接设置。

    Args:
        key_suffix: C-03 规范的后缀部分，如 "EMBEDDING__HF_ENDPOINT"
        default: 默认值

    Returns:
        环境变量值或默认值
    """
    # 优先使用 C-03 规范的 REQRADAR_ 前缀版本
    canonical = f"REQRADAR_{key_suffix}"
    value = os.environ.get(canonical)
    if value is not None:
        return value

    # 向后兼容：旧变量名映射
    legacy_map = {
        "EMBEDDING__HF_ENDPOINT": "HF_ENDPOINT",
        "EMBEDDING__MODEL_REPO": "EMBEDDING_MODEL_REPO",
        "EMBEDDING__MODEL_CACHE": "EMBEDDING_MODEL_CACHE",
        "EMBEDDING__PRECISION": "EMBEDDING_PRECISION",
    }
    legacy_key = legacy_map.get(key_suffix)
    if legacy_key:
        value = os.environ.get(legacy_key)
        if value is not None:
            return value

    return default


# ONNX 模型文件映射（精度 → 文件列表）
_ONNX_FILES: dict[str, list[str]] = {
    "fp32": ["model.onnx", "model.onnx_data"],
    "fp16": ["model_fp16.onnx", "model_fp16.onnx_data"],
    "q4": ["model_q4.onnx", "model_q4.onnx_data"],
}

# Tokenizer / 配置文件（位于仓库根目录）
_TOKENIZER_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
]


class ReqRadarEmbeddingFunction:
    """ChromaDB 兼容的嵌入函数，从 HuggingFace 镜像下载 ONNX 模型。

    与 chromadb 内置 ONNXMiniLM_L6_V2 的区别：
    - 下载源：HF 镜像（可配置）而非 S3（国内不可用）
    - 模型格式：支持 ONNX 外部数据格式（model.onnx + model.onnx_data）
    - 可配置精度：fp32 / fp16 / q4（量化）
    - Docker 构建时预下载，运行时零网络依赖

    用法::

        from reqradar.kernel.embedding import ReqRadarEmbeddingFunction

        ef = ReqRadarEmbeddingFunction()
        vectors = ef(["你好", "hello"])  # → list[list[float]]

        # 在 ChromaDB 中使用
        collection = client.get_or_create_collection("test", embedding_function=ef)
    """

    def __init__(
        self,
        model_repo: str | None = None,
        hf_endpoint: str | None = None,
        cache_dir: str | None = None,
        precision: str | None = None,
    ) -> None:
        self.model_repo = model_repo or _getenv(
            "EMBEDDING__MODEL_REPO",
            DEFAULT_MODEL_REPO,
        )
        self.hf_endpoint = hf_endpoint or _getenv(
            "EMBEDDING__HF_ENDPOINT",
            DEFAULT_HF_ENDPOINT,
        )
        self.cache_dir = Path(
            cache_dir or _getenv("EMBEDDING__MODEL_CACHE", _get_default_cache_dir()),
        )
        self.precision = precision or _getenv("EMBEDDING__PRECISION", "fp16")

        # ChromaDB 要求嵌入函数有 name() 方法（用于集合元数据标识）
        self._name = f"reqradar-{self.model_repo.replace('/', '-')}-{self.precision}"

        self._session = None
        self._tokenizer = None

    def name(self) -> str:
        """返回嵌入函数名称（ChromaDB 接口要求）。"""
        return self._name

    # ------------------------------------------------------------------
    # 模型下载
    # ------------------------------------------------------------------

    @property
    def _model_dir(self) -> Path:
        """模型缓存目录（按仓库+精度隔离）。"""
        repo_name = self.model_repo.replace("/", "_")
        return self.cache_dir / repo_name / self.precision

    def _download_file(self, url: str, dest: Path) -> None:
        """流式下载文件，支持大文件和断点检测。"""
        import httpx

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")

        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=300) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
            tmp.rename(dest)
            logger.info("下载完成: %s (%d bytes)", dest.name, dest.stat().st_size)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"下载文件失败: {url}") from e

    def _ensure_model_files(self) -> Path:
        """确保模型文件已下载，返回模型目录路径。"""
        model_dir = self._model_dir
        onnx_files = _ONNX_FILES.get(self.precision, _ONNX_FILES["fp16"])

        # 快速检查：主 ONNX 文件 + tokenizer.json 存在即视为已缓存
        onnx_main_exists = (model_dir / onnx_files[0]).exists()
        tokenizer_exists = (model_dir / "tokenizer.json").exists()

        if onnx_main_exists and tokenizer_exists:
            logger.info("使用缓存的嵌入模型: %s", model_dir)
            return model_dir

        logger.info(
            "下载嵌入模型: %s (精度=%s, 镜像=%s)",
            self.model_repo,
            self.precision,
            self.hf_endpoint,
        )
        base_url = f"{self.hf_endpoint}/{self.model_repo}/resolve/main"

        # 1. 下载 tokenizer / config 文件
        for fname in _TOKENIZER_FILES:
            dest = model_dir / fname
            if not dest.exists():
                self._download_file(f"{base_url}/{fname}", dest)

        # 2. 下载 ONNX 模型文件（位于 onnx/ 子目录）
        for fname in onnx_files:
            dest = model_dir / fname
            if dest.exists():
                continue
            # 优先从 onnx/ 子目录下载
            try:
                self._download_file(f"{base_url}/onnx/{fname}", dest)
            except Exception as e:
                # 外部数据文件可能不存在（单文件格式），跳过
                if "onnx_data" in fname:
                    logger.info("外部数据文件 %s 不存在，可能使用单文件格式", fname)
                else:
                    raise RuntimeError(f"下载 ONNX 模型文件失败: {fname}") from e

        logger.info("嵌入模型下载完成: %s", model_dir)
        return model_dir

    # ------------------------------------------------------------------
    # 模型加载与推理
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """延迟加载 ONNX 模型和 tokenizer（首次调用时触发）。"""
        if self._session is not None:
            return

        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = self._ensure_model_files()
        onnx_files = _ONNX_FILES.get(self.precision, _ONNX_FILES["fp16"])
        onnx_path = model_dir / onnx_files[0]

        # 加载 tokenizer
        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=512)
        self._tokenizer.enable_padding()

        # 加载 ONNX 模型（onnxruntime 自动加载同目录的 onnx_data）
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(
            str(onnx_path),
            opts,
            providers=["CPUExecutionProvider"],
        )
        logger.info("ONNX 嵌入模型加载完成 (精度=%s)", self.precision)

    def _tokenize(self, texts: list[str]) -> dict[str, "np.ndarray"]:
        """分词并转换为 ONNX 输入张量。"""
        import numpy as np  # noqa: PLR0402 — 懒加载，避免模块级依赖

        encoded = self._tokenizer.encode_batch(texts)
        max_len = max(len(e.ids) for e in encoded)

        input_ids = np.array(
            [e.ids + [0] * (max_len - len(e.ids)) for e in encoded],
            dtype=np.int64,
        )
        attention_mask = np.array(
            [e.attention_mask + [0] * (max_len - len(e.attention_mask)) for e in encoded],
            dtype=np.int64,
        )
        token_type_ids = np.array(
            [e.type_ids + [0] * (max_len - len(e.type_ids)) for e in encoded],
            dtype=np.int64,
        )

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        }

    @staticmethod
    def _mean_pooling(
        token_embeddings: "np.ndarray",
        attention_mask: "np.ndarray",
    ) -> "np.ndarray":
        """均值池化：根据 attention_mask 对 token 嵌入取加权平均。"""
        import numpy as np  # noqa: PLR0402 — 懒加载，避免模块级依赖

        mask = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
        summed = np.sum(token_embeddings * mask, axis=1)
        counts = np.clip(np.sum(mask, axis=1), a_min=1e-9, a_max=None)
        return summed / counts

    def __call__(self, input: list[str]) -> list[list[float]]:
        """计算嵌入向量（ChromaDB EmbeddingFunction 接口）。

        Args:
            input: 待嵌入的文本列表

        Returns:
            嵌入向量列表，每个向量 384 维
        """
        import numpy as np  # noqa: PLR0402 — 懒加载，避免模块级依赖

        self._load()

        batch_size = 64
        all_embeddings: list[list[float]] = []

        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            tokenized = self._tokenize(batch)

            # 只传入模型需要的输入（部分模型不需要 token_type_ids）
            input_names = {inp.name for inp in self._session.get_inputs()}
            onnx_inputs = {k: v for k, v in tokenized.items() if k in input_names}

            outputs = self._session.run(None, onnx_inputs)

            # 均值池化 + L2 归一化
            embeddings = self._mean_pooling(outputs[0], tokenized["attention_mask"])
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / np.maximum(norms, 1e-9)

            all_embeddings.extend(embeddings.tolist())

        return all_embeddings
