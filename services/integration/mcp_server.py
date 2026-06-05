"""MCP Server 生命周期管理 — FastMCP 实例创建 / 启动 / 停止。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

logger = logging.getLogger(__name__)

_MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
_MCP_PORT = int(os.environ.get("MCP_PORT", "9000"))
_MCP_PATH = os.environ.get("MCP_PATH", "/mcp")


class MCPServerManager:
    """MCP Server 生命周期管理器。"""

    def __init__(self) -> None:
        self._mcp = None
        self._task: asyncio.Task | None = None
        self._started = False

    def create_server(self, instructions: str = "") -> object:
        """创建 FastMCP 实例。"""
        try:
            from fastmcp import FastMCP

            self._mcp = FastMCP(
                "reqradar-v2",
                instructions=instructions
                or (
                    "ReqRadar V2 MCP Server — 查询需求分析 Session、证据、知识库和报告。"
                    "所有工具均为只读。"
                ),
            )
            logger.info("FastMCP 实例创建成功")
            return self._mcp
        except ImportError:
            logger.warning("FastMCP 未安装，MCP Server 不可用")
            return None

    async def start(self, host: str | None = None, port: int | None = None) -> bool:
        """启动 MCP Server（后台任务）。"""
        if self._mcp is None:
            logger.warning("FastMCP 实例未创建，无法启动")
            return False

        if self._started:
            logger.warning("MCP Server 已在运行")
            return True

        _host = host or _MCP_HOST
        _port = port or _MCP_PORT

        async def _run():
            try:
                await self._mcp.run_http_async(
                    host=_host,
                    port=_port,
                    path=_MCP_PATH,
                    show_banner=False,
                )
            except OSError as e:
                if "Address already in use" in str(e) or "EADDRINUSE" in str(e):
                    logger.error("MCP Server 端口 %d 已被占用", _port)
                else:
                    logger.error("MCP Server 启动失败: %s", e)
            except Exception as e:
                logger.error("MCP Server 异常: %s", e)

        self._task = asyncio.create_task(_run())
        self._started = True
        logger.info("MCP Server 启动: host=%s, port=%d, path=%s", _host, _port, _MCP_PATH)
        return True

    async def stop(self) -> None:
        """停止 MCP Server。"""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._started = False
        logger.info("MCP Server 已停止")

    @property
    def is_running(self) -> bool:
        return self._started and self._task is not None and not self._task.done()
