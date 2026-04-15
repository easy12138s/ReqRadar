"""图片加载器 - 使用 LLM 视觉能力描述 UI 截图"""

import logging
from pathlib import Path

from reqradar.core.exceptions import VisionNotConfiguredError
from reqradar.modules.loaders.base import DocumentLoader, LoadedDocument

logger = logging.getLogger("reqradar.loaders.image")

SUPPORTED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]

VISION_PROMPT = """请分析这张 UI 截图，提取以下信息：

1. 功能描述：这个界面/功能是什么？
2. 交互元素：有哪些按钮、输入框、下拉选项等？
3. 业务约束：是否有可见的验证规则、限制条件、状态提示？
4. 用户流程：用户在这个界面上的典型操作流程是什么？

请以结构化方式输出，包含所有可见的文本内容。"""


class ImageLoader(DocumentLoader):
    def __init__(self, llm_client=None, chunk_size: int = 300, chunk_overlap: int = 50):
        self.llm_client = llm_client
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def supported_extensions(self) -> list[str]:
        return SUPPORTED_IMAGE_EXTENSIONS

    def load(self, file_path: Path, **kwargs) -> list[LoadedDocument]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            image_data = f.read()

        return [
            LoadedDocument(
                content="",
                source=str(file_path),
                format="image",
                metadata={"title": file_path.stem, "needs_vision": True},
                images=[image_data],
            )
        ]

    async def load_with_vision(
        self, file_path: Path, llm_client=None, **kwargs
    ) -> list[LoadedDocument]:
        client = llm_client or self.llm_client
        if client is None:
            raise VisionNotConfiguredError(
                "图片处理需要配置视觉 LLM。"
                "请在配置文件中添加 vision 配置块，或可通过 --no-image 跳过图片文件。"
            )

        docs = self.load(file_path, **kwargs)
        if not docs:
            return []

        doc = docs[0]
        description = await client.complete_vision(
            image_data=doc.images[0],
            prompt=VISION_PROMPT,
        )

        doc.content = description
        doc.metadata["vision_described"] = True
        return [doc]
