"""Integration Service — MCP 协议网关 + 密钥管理 + 审计日志。"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.integration.client import ServiceClient
from services.integration.mcp_audit import AuditLog
from services.integration.mcp_keys import KeyManager
from services.integration.mcp_server import MCPServerManager
from services.integration.mcp_tools import register_tools

logger = logging.getLogger(__name__)

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "9000"))
MCP_PATH = os.environ.get("MCP_PATH", "/mcp")

_service_client = ServiceClient()
_key_manager = KeyManager()
_audit_log = AuditLog()
_mcp_manager = MCPServerManager()
_start_time: float = 0.0


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class CreateKeyRequest(BaseModel):
    """创建 MCP 密钥请求。"""

    name: str = Field(description="密钥名称")
    scopes: list[str] | None = Field(default=None, description="权限范围")


class CreateKeyResponse(BaseModel):
    """创建 MCP 密钥响应。"""

    key_id: str = Field(description="密钥 ID")
    raw_key: str = Field(description="原始密钥（仅此处可见）")
    name: str = Field(description="密钥名称")
    scopes: list[str] = Field(description="权限范围")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.time()
    # 初始化同步 DB 会话工厂
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./reqradar_dev.db")
    sync_url = database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    app.state.sync_db_session_factory = sessionmaker(create_engine(sync_url))
    _key_manager.set_session_factory(app.state.sync_db_session_factory)
    _audit_log.set_session_factory(app.state.sync_db_session_factory)
    logger.info("Integration Service 启动")
    mcp = _mcp_manager.create_server()
    if mcp is not None:
        register_tools(mcp, _service_client, _audit_log, _key_manager)
        await _mcp_manager.start(host=MCP_HOST, port=int(MCP_PORT))
    yield
    await _mcp_manager.stop()
    await _service_client.close()
    logger.info("Integration Service 关闭")


app = FastAPI(
    title="ReqRadar Integration Service (MCP)",
    version="2.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# 中间件 — 内部 API Key 校验
# ---------------------------------------------------------------------------


@app.middleware("http")
async def verify_internal_api_key(request, call_next):
    """校验入站请求的 X-Internal-API-Key 头。"""
    if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    api_key = request.headers.get("X-Internal-API-Key", "")
    if api_key != INTERNAL_API_KEY:
        from starlette.responses import JSONResponse

        return JSONResponse(
            status_code=401,
            content={"error": {"code": "UNAUTHORIZED", "message": "Invalid Internal API Key"}},
        )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """本地健康检查。"""
    return {
        "status": "ok",
        "service": "integration",
        "uptime_seconds": int(time.time() - _start_time),
    }


# ---------------------------------------------------------------------------
# MCP 密钥管理
# ---------------------------------------------------------------------------


@app.post("/internal/v2/mcp/keys", status_code=201)
async def create_mcp_key(req: CreateKeyRequest):
    """创建 MCP 访问密钥。"""
    raw_key, ak = _key_manager.generate_key(req.name, req.scopes)
    return CreateKeyResponse(
        key_id=ak.key_id,
        raw_key=raw_key,
        name=ak.name,
        scopes=ak.scopes,
    )


@app.get("/internal/v2/mcp/keys")
async def list_mcp_keys():
    """列出所有 MCP 密钥。"""
    return {"keys": _key_manager.list_keys()}


@app.post("/internal/v2/mcp/keys/{key_id}/revoke")
async def revoke_mcp_key(key_id: str):
    """撤销 MCP 密钥。"""
    if not _key_manager.revoke_key(key_id):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "KEY_NOT_FOUND", "message": f"密钥不存在或已撤销: {key_id}"}},
        )
    return {"revoked": True, "key_id": key_id}


# ---------------------------------------------------------------------------
# MCP 审计日志
# ---------------------------------------------------------------------------


@app.get("/internal/v2/mcp/audit")
async def get_mcp_audit(tool_name: str | None = None, key_id: str | None = None, limit: int = 100):
    """查询 MCP 审计日志。"""
    entries = _audit_log.query(tool_name=tool_name, key_id=key_id, limit=limit)
    return {"entries": entries, "total": len(entries)}


@app.post("/internal/v2/mcp/audit/cleanup")
async def cleanup_mcp_audit():
    """清理审计日志。"""
    removed = _audit_log.cleanup()
    return {"removed": removed}


# ---------------------------------------------------------------------------
# MCP 配置
# ---------------------------------------------------------------------------


@app.get("/internal/v2/mcp/config")
async def get_mcp_config():
    """查询 MCP 运行时配置。"""
    return {
        "mcp_running": True,
        "mcp_host": MCP_HOST,
        "mcp_port": MCP_PORT,
        "mcp_path": MCP_PATH,
        "key_count": len(_key_manager.list_keys()),
    }
