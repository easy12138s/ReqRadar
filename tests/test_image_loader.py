"""测试图片加载器"""

from pathlib import Path

import pytest
from reqradar.core.exceptions import VisionNotConfiguredError
from reqradar.modules.loaders.image_loader import ImageLoader


class TestImageLoader:
    def test_supported_extensions(self):
        loader = ImageLoader()
        exts = loader.supported_extensions()
        assert ".png" in exts
        assert ".jpg" in exts
        assert ".jpeg" in exts
        assert ".webp" in exts

    def test_supports_image_files(self):
        loader = ImageLoader()
        assert loader.supports(Path("screenshot.png")) is True
        assert loader.supports(Path("photo.jpg")) is True
        assert loader.supports(Path("doc.pdf")) is False

    def test_load_image_file(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        loader = ImageLoader()
        docs = loader.load(img_file)

        assert len(docs) == 1
        assert docs[0].format == "image"
        assert docs[0].content == ""
        assert len(docs[0].images) == 1
        assert docs[0].metadata["needs_vision"] is True

    def test_load_nonexistent_file(self):
        loader = ImageLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(Path("/nonexistent/image.png"))

    @pytest.mark.asyncio
    async def test_load_with_vision_no_client(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        loader = ImageLoader()
        with pytest.raises(VisionNotConfiguredError):
            await loader.load_with_vision(img_file)

    @pytest.mark.asyncio
    async def test_load_with_vision_none_client(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        loader = ImageLoader()
        with pytest.raises(VisionNotConfiguredError):
            await loader.load_with_vision(img_file, llm_client=None)
