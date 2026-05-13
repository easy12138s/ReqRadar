"""MCP 生命周期管理单元测试"""

import pytest
from unittest.mock import MagicMock

from reqradar.mcp.lifecycle import MCPServerHandle, create_mcp_server, maybe_start_mcp_with_web, stop_mcp_with_web


class TestMCPServerHandle:
    def test_init(self):
        mcp_mock = MagicMock()
        handle = MCPServerHandle(mcp=mcp_mock)
        assert handle.mcp is mcp_mock
        assert handle.task is None
        assert handle.started is False


class TestCreateMCPServer:
    def test_creates_server_with_tools(self):
        from reqradar.infrastructure.config import Config, HomeConfig, WebConfig, MCPConfig
        from reqradar.mcp.context import MCPRuntimeContext
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config = Config(
                home=HomeConfig(path=tmp),
                web=WebConfig(mcp=MCPConfig()),
            )
            ctx = MCPRuntimeContext(
                config=config,
                session_factory=MagicMock(),
                paths={"home": tmp},
                report_storage=MagicMock(),
            )
            mcp = create_mcp_server(ctx)
            assert mcp is not None


class TestMaybeStartMCPWithWeb:
    @pytest.mark.asyncio
    async def test_skips_when_already_started(self):
        app = MagicMock()
        existing_handle = MagicMock()
        existing_handle.started = True
        app.state.mcp_handle = existing_handle

        await maybe_start_mcp_with_web(app)

        assert app.state.mcp_handle is existing_handle


class TestStopMCPWithWeb:
    @pytest.mark.asyncio
    async def test_handles_none_handle(self):
        app = MagicMock()
        app.state.mcp_handle = None

        await stop_mcp_with_web(app)
