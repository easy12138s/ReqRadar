"""MCP 上下文管理单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from reqradar.infrastructure.config import Config, HomeConfig, WebConfig, MCPConfig
from reqradar.mcp.context import MCPRuntimeContext


class TestMCPRuntimeContext:
    def test_init_basic(self, tmp_path):
        config = Config(
            home=HomeConfig(path=str(tmp_path)),
            web=WebConfig(),
        )
        session_factory = MagicMock()
        paths = {"home": tmp_path}
        report_storage = MagicMock()

        ctx = MCPRuntimeContext(
            config=config,
            session_factory=session_factory,
            paths=paths,
            report_storage=report_storage,
        )
        assert ctx.config is config
        assert ctx.session_factory is session_factory
        assert ctx.paths is paths
        assert ctx.report_storage is report_storage

    def test_post_init_creates_content_reader(self, tmp_path):
        from reqradar.web.services.content_reader import ContentReader

        config = Config(home=HomeConfig(path=str(tmp_path)), web=WebConfig())
        paths = {"home": tmp_path, "memories": str(tmp_path / "memories")}
        ctx = MCPRuntimeContext(
            config=config,
            session_factory=MagicMock(),
            paths=paths,
            report_storage=MagicMock(),
        )
        assert isinstance(ctx.content_reader, ContentReader)

    def test_memory_path_defaults_to_empty(self, tmp_path):
        config = Config(home=HomeConfig(path=str(tmp_path)), web=WebConfig())
        ctx = MCPRuntimeContext(
            config=config,
            session_factory=MagicMock(),
            paths={"home": tmp_path},
            report_storage=MagicMock(),
        )
        assert ctx.content_reader._memory_storage_path == ""
