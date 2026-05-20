"""MCP 工具注册单元测试"""

from unittest.mock import MagicMock


class TestSetContext:
    def test_sets_global_context(self):
        import tempfile

        from reqradar.mcp.context import MCPRuntimeContext
        from reqradar.mcp.tools import set_context

        with tempfile.TemporaryDirectory() as tmp:
            ctx = MCPRuntimeContext(
                config=MagicMock(),
                session_factory=MagicMock(),
                paths={"home": tmp},
                report_storage=MagicMock(),
            )
            set_context(ctx)

    def test_overwrites_existing(self):
        import tempfile

        from reqradar.mcp.context import MCPRuntimeContext
        from reqradar.mcp.tools import set_context

        with tempfile.TemporaryDirectory():
            ctx1 = MCPRuntimeContext(config=MagicMock(), session_factory=MagicMock(), paths={}, report_storage=MagicMock())
            ctx2 = MCPRuntimeContext(config=MagicMock(), session_factory=MagicMock(), paths={}, report_storage=MagicMock())
            set_context(ctx1)
            set_context(ctx2)
