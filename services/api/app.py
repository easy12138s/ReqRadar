"""API-Service BFF — 纯代理层，将请求转发至下游服务。"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from services.api.client import ServiceClient

logger = logging.getLogger(__name__)

service_client = ServiceClient()
_start_time: float = 0.0


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """创建会话请求（C-04 §4.1）。"""

    project_id: str = Field(description="关联项目 ID")
    config: dict | None = Field(default=None, description="会话配置")


class StartSessionRequest(BaseModel):
    """启动/恢复会话请求（C-04 §4.1.2）。"""

    resume_from: int | None = Field(default=None, description="Checkpoint 版本号，null 从头开始")


class VerifyEvidenceRequest(BaseModel):
    """验证证据请求（C-04 §4.2.3）。"""

    verified_by: str = Field(description="验证者标识：auto 或 human:{user_id}")


class GenerateReportRequest(BaseModel):
    """报告生成请求。"""

    session_id: str = Field(description="Session ID")
    template_id: str | None = Field(default=None, description="模板 ID")
    output_format: str = Field(default="markdown", description="输出格式")


class KnowledgeSearchRequest(BaseModel):
    """知识语义检索请求（C-04 §4.5.2）。"""

    query: str = Field(description="语义检索查询文本")
    knowledge_types: list[str] | None = Field(default=None, description="限制检索的知识类型")
    freshness: str | None = Field(default=None, description="新鲜度过滤")
    min_confidence: float | None = Field(default=None, description="最低置信度")
    top_k: int | None = Field(default=None, description="返回条数")


class KnowledgeUpdateRequest(BaseModel):
    """知识更新请求（C-04 §4.5.4）。"""

    knowledge_type: str = Field(description="知识类型")
    patch: dict = Field(description="补丁内容")
    evidence_ref: str | None = Field(default=None, description="证据引用 ID")
    session_id: str | None = Field(default=None, description="触发会话 ID")


class DeprecateKnowledgeRequest(BaseModel):
    """废弃知识请求（C-04 §4.5.5）。"""

    knowledge_type: str = Field(description="知识类型")
    reason: str = Field(description="废弃原因")


class CreateProjectRequest(BaseModel):
    """创建项目请求。"""

    name: str = Field(description="项目名称")
    description: str = Field(default="", description="项目描述")
    source_type: str = Field(default="empty", description="来源类型: git/local/upload/empty")
    source_config: dict | None = Field(default=None, description="来源配置")


class UpdateProjectRequest(BaseModel):
    """更新项目请求。"""

    name: str | None = Field(default=None, description="项目名称")
    description: str | None = Field(default=None, description="项目描述")
    source_config: dict | None = Field(default=None, description="来源配置")


class ProjectResponse(BaseModel):
    """项目响应。"""

    id: str = Field(description="项目 ID")
    name: str = Field(description="项目名称")
    description: str | None = Field(description="项目描述")
    source_type: str | None = Field(description="来源类型")
    status: str = Field(description="项目状态")
    repo_path: str | None = Field(description="仓库路径")
    owner_id: str | None = Field(description="所有者 ID")
    profile_data: dict | None = Field(description="项目画像数据")
    indexed_at: str | None = Field(description="最后索引时间")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class ProjectListResponse(BaseModel):
    """项目列表响应。"""

    items: list[ProjectResponse] = Field(description="项目列表")
    total: int = Field(description="总数")


# ---------------------------------------------------------------------------
# 认证依赖
# ---------------------------------------------------------------------------


async def get_current_user(request: Request) -> dict:
    """从 Authorization 头提取 JWT，通过 auth-service 验证。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "AUTHENTICATION_REQUIRED", "message": "缺少认证 Token"}},
        )
    token = auth[7:]
    try:
        result = await service_client.verify_token(token)
    except httpx.HTTPError as exc:
        logger.error("auth-service 调用失败: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "AUTH_SERVICE_UNAVAILABLE", "message": "认证服务不可用"}},
        ) from exc
    if not result.get("valid"):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "TOKEN_INVALID",
                    "message": result.get("error", "Token 无效"),
                }
            },
        )
    return result.get("user", {})


def _extract_jwt(request: Request) -> str | None:
    """从请求头提取原始 JWT 字符串。"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def _proxy_error(exc: httpx.HTTPStatusError) -> HTTPException:
    """将下游 HTTP 错误转换为统一格式的 HTTPException。"""
    resp = exc.response
    try:
        body = resp.json()
    except Exception as e:
        body = {"error": {"code": "DOWNSTREAM_ERROR", "message": resp.text, "detail": str(e)}}
    return HTTPException(status_code=resp.status_code, detail=body)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.time()

    # 初始化 DB session factory（项目管理 CRUD 直连 PG）
    database_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./reqradar_dev.db")
    from reqradar.kernel.database import create_engine, create_session_factory

    engine = create_engine(database_url)
    app.state.db_session_factory = create_session_factory(engine)

    logger.info("API-Service BFF 启动")
    yield
    await service_client.close()
    await engine.dispose()
    logger.info("API-Service BFF 关闭")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ReqRadar API-Service (BFF)",
    version="2.0.0",
    lifespan=lifespan,
)

CurrentUser = Annotated[dict, Depends(get_current_user)]


async def get_db_session(request: Request) -> AsyncSession:
    """获取数据库会话（项目管理 CRUD）。"""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """本地健康检查，无需认证。"""
    return {
        "status": "ok",
        "service": "api",
        "uptime_seconds": int(time.time() - _start_time),
    }


# ---------------------------------------------------------------------------
# Session 路由（C-04 §4.1）
# ---------------------------------------------------------------------------


@app.post("/api/v2/sessions", status_code=201)
async def create_session(
    req: CreateSessionRequest,
    request: Request,
    user: CurrentUser,
):
    """创建认知会话。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.create_session(req.project_id, req.config, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/sessions/{session_id}/start")
async def start_session(
    session_id: str,
    req: StartSessionRequest,
    request: Request,
    user: CurrentUser,
):
    """启动或恢复会话。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.start_session(session_id, req.resume_from, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    user: CurrentUser,
):
    """查询会话状态。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.get_session(session_id, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/sessions/{session_id}/cancel", status_code=202)
async def cancel_session(
    session_id: str,
    request: Request,
    user: CurrentUser,
):
    """取消会话。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.cancel_session(session_id, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/sessions/{session_id}/checkpoint")
async def trigger_checkpoint(
    session_id: str,
    request: Request,
    user: CurrentUser,
):
    """手动触发检查点。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.create_checkpoint(session_id, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/sessions/{session_id}/events")
async def get_events(
    session_id: str,
    request: Request,
    user: CurrentUser,
    type: str | None = Query(default=None, description="事件类型过滤"),
    level: str | None = Query(default=None, description="事件级别过滤"),
    since: int | None = Query(default=None, description="起始序列号"),
    limit: int = Query(default=100, description="返回条数上限"),
):
    """查询会话事件流。"""
    jwt = _extract_jwt(request)
    params: dict = {}
    if type is not None:
        params["type"] = type
    if level is not None:
        params["level"] = level
    if since is not None:
        params["since"] = since
    params["limit"] = limit
    try:
        return await service_client.get_events(session_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.websocket("/api/v2/sessions/{session_id}/ws")
async def session_ws(websocket: WebSocket, session_id: str):
    """WebSocket 实时事件推送 — 订阅 Redis Stream。"""
    # JWT 认证
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4003, reason="缺少认证 token")
        return

    # 验证 JWT
    jwt_secret = os.environ.get("JWT_SECRET", "")
    try:
        from reqradar.infrastructure.auth import decode_jwt_token

        user_info = decode_jwt_token(token, jwt_secret)
        if isinstance(user_info, dict) and not user_info.get("valid", True):
            await websocket.close(code=4003, reason="Token 无效")
            return
    except Exception as e:
        await websocket.close(code=4003, reason="认证失败: %s" % str(e))
        return

    await websocket.accept()
    redis_url = os.environ.get("REDIS_URL", "")

    if not redis_url:
        await websocket.send_json({"type": "error", "data": {"message": "Redis 未配置"}})
        await websocket.close()
        return

    try:
        import redis.asyncio as aioredis

        redis = aioredis.from_url(redis_url, decode_responses=True)
        stream_key = "reqradar:events:%s" % session_id
        last_id = "0"

        try:
            while True:
                messages = await redis.xread(
                    {stream_key: last_id},
                    count=10,
                    block=2000,
                )
                if messages:
                    for _stream, entries in messages:
                        for entry_id, data in entries:
                            last_id = entry_id
                            await websocket.send_json(
                                {"type": "event", "data": data, "id": entry_id}
                            )
        except Exception as e:
            logger.warning("WebSocket Redis 订阅异常: session_id=%s, error=%s", session_id, e)
        finally:
            await redis.close()
    except Exception as e:
        logger.warning("WebSocket 连接异常: session_id=%s, error=%s", session_id, e)
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


# ---------------------------------------------------------------------------
# Evidence 路由（C-04 §4.2）
# ---------------------------------------------------------------------------


@app.get("/api/v2/sessions/{session_id}/evidence")
async def get_evidence(
    session_id: str,
    request: Request,
    user: CurrentUser,
    type: str | None = Query(default=None, description="证据类型过滤"),
    status: str | None = Query(default=None, description="证据状态过滤"),
    dimension: str | None = Query(default=None, description="维度过滤"),
    min_confidence: float | None = Query(default=None, description="最低置信度"),
    context_kind: str | None = Query(default=None, description="上下文类型过滤"),
    limit: int = Query(default=100, description="返回条数上限"),
    offset: int = Query(default=0, description="偏移量"),
):
    """查询会话证据列表。"""
    jwt = _extract_jwt(request)
    params: dict = {"limit": limit, "offset": offset}
    if type is not None:
        params["type"] = type
    if status is not None:
        params["status"] = status
    if dimension is not None:
        params["dimension"] = dimension
    if min_confidence is not None:
        params["min_confidence"] = min_confidence
    if context_kind is not None:
        params["context_kind"] = context_kind
    try:
        return await service_client.get_evidence(session_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/sessions/{session_id}/evidence/{evidence_id}")
async def get_evidence_detail(
    session_id: str,
    evidence_id: str,
    request: Request,
    user: CurrentUser,
):
    """查询单条证据详情。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.get_evidence_detail(session_id, evidence_id, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/sessions/{session_id}/evidence/{evidence_id}/verify")
async def verify_evidence(
    session_id: str,
    evidence_id: str,
    req: VerifyEvidenceRequest,
    request: Request,
    user: CurrentUser,
):
    """验证证据。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.verify_evidence(session_id, evidence_id, req.verified_by, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


# ---------------------------------------------------------------------------
# Dimension 路由（C-04 §4.3）
# ---------------------------------------------------------------------------


@app.get("/api/v2/sessions/{session_id}/dimensions")
async def get_dimensions(
    session_id: str,
    request: Request,
    user: CurrentUser,
):
    """查询维度评估状态。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.get_dimensions(session_id, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


# ---------------------------------------------------------------------------
# Checkpoint 路由（C-04 §4.4）
# ---------------------------------------------------------------------------


@app.get("/api/v2/sessions/{session_id}/checkpoints")
async def get_checkpoints(
    session_id: str,
    request: Request,
    user: CurrentUser,
    limit: int = Query(default=20, description="返回条数上限"),
    offset: int = Query(default=0, description="偏移量"),
    type: str | None = Query(default=None, description="按类型过滤"),
):
    """查询检查点版本链。"""
    jwt = _extract_jwt(request)
    params: dict = {"limit": limit, "offset": offset}
    if type is not None:
        params["type"] = type
    try:
        return await service_client.get_checkpoints(session_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/sessions/{session_id}/checkpoints/{version}")
async def get_checkpoint_version(
    session_id: str,
    version: int,
    request: Request,
    user: CurrentUser,
):
    """查询特定版本检查点。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.get_checkpoint_version(session_id, version, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/sessions/{session_id}/checkpoints/{version}/restore")
async def restore_checkpoint(
    session_id: str,
    version: int,
    request: Request,
    user: CurrentUser,
):
    """从检查点恢复。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.restore_checkpoint(session_id, version, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


# ---------------------------------------------------------------------------
# Knowledge 路由（C-04 §4.5）
# ---------------------------------------------------------------------------


@app.get("/api/v2/projects/{project_id}/knowledge")
async def get_knowledge(
    project_id: str,
    request: Request,
    user: CurrentUser,
    freshness: str = Query(default="active", description="新鲜度过滤"),
    min_confidence: float = Query(default=0.6, description="最低置信度"),
    knowledge_types: str | None = Query(default=None, description="知识类型过滤（逗号分隔）"),
):
    """按项目聚合查询知识。"""
    jwt = _extract_jwt(request)
    params: dict = {"freshness": freshness, "min_confidence": min_confidence}
    if knowledge_types is not None:
        params["knowledge_types"] = knowledge_types
    try:
        return await service_client.get_knowledge(project_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/projects/{project_id}/knowledge")
async def search_knowledge(
    project_id: str,
    req: KnowledgeSearchRequest,
    request: Request,
    user: CurrentUser,
):
    """语义检索知识。"""
    jwt = _extract_jwt(request)
    body = req.model_dump(exclude_none=True)
    try:
        return await service_client.search_knowledge(project_id, body, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/projects/{project_id}/knowledge/{kid}")
async def get_knowledge_detail(
    project_id: str,
    kid: str,
    request: Request,
    user: CurrentUser,
    knowledge_type: str = Query(description="知识类型"),
):
    """查询单条知识详情。"""
    jwt = _extract_jwt(request)
    params: dict = {"knowledge_type": knowledge_type}
    try:
        return await service_client.get_knowledge_detail(project_id, kid, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.put("/api/v2/projects/{project_id}/knowledge/{kid}")
async def update_knowledge(
    project_id: str,
    kid: str,
    req: KnowledgeUpdateRequest,
    request: Request,
    user: CurrentUser,
):
    """更新知识。"""
    jwt = _extract_jwt(request)
    body = req.model_dump(exclude_none=True)
    try:
        return await service_client.update_knowledge(project_id, kid, body, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/projects/{project_id}/knowledge/{kid}/deprecate")
async def deprecate_knowledge(
    project_id: str,
    kid: str,
    req: DeprecateKnowledgeRequest,
    request: Request,
    user: CurrentUser,
):
    """废弃知识。"""
    jwt = _extract_jwt(request)
    body = req.model_dump(exclude_none=True)
    try:
        return await service_client.deprecate_knowledge(project_id, kid, body, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/projects/{project_id}/knowledge/changelog")
async def get_knowledge_changelog(
    project_id: str,
    request: Request,
    user: CurrentUser,
    knowledge_type: str | None = Query(default=None, description="按知识类型过滤"),
    knowledge_id: str | None = Query(default=None, description="按知识 ID 过滤"),
    change_type: str | None = Query(default=None, description="按变更类型过滤"),
    since: str | None = Query(default=None, description="起始时间"),
    until: str | None = Query(default=None, description="截止时间"),
    limit: int = Query(default=50, description="返回条数上限"),
):
    """查询知识变更日志。"""
    jwt = _extract_jwt(request)
    params: dict = {"limit": limit}
    if knowledge_type is not None:
        params["knowledge_type"] = knowledge_type
    if knowledge_id is not None:
        params["knowledge_id"] = knowledge_id
    if change_type is not None:
        params["change_type"] = change_type
    if since is not None:
        params["since"] = since
    if until is not None:
        params["until"] = until
    try:
        return await service_client.get_knowledge_changelog(project_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


# ---------------------------------------------------------------------------
# Graph 路由（C-04 §4.6）
# ---------------------------------------------------------------------------


@app.get("/api/v2/projects/{project_id}/graph/neighbors")
async def get_graph_neighbors(
    project_id: str,
    request: Request,
    user: CurrentUser,
    node_type: str = Query(description="节点类型"),
    node_id: str = Query(description="节点 ID"),
    relation_type: str | None = Query(default=None, description="关系类型过滤"),
    direction: str = Query(default="both", description="遍历方向"),
    depth: int = Query(default=1, description="遍历深度"),
    limit: int = Query(default=50, description="返回条数上限"),
):
    """查询图节点邻居。"""
    jwt = _extract_jwt(request)
    params: dict = {
        "node_type": node_type,
        "node_id": node_id,
        "direction": direction,
        "depth": depth,
        "limit": limit,
    }
    if relation_type is not None:
        params["relation_type"] = relation_type
    try:
        return await service_client.get_graph_neighbors(project_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/projects/{project_id}/graph/path")
async def get_graph_path(
    project_id: str,
    request: Request,
    user: CurrentUser,
    from_type: str = Query(description="起点节点类型"),
    from_id: str = Query(description="起点节点 ID"),
    to_type: str = Query(description="终点节点类型"),
    to_id: str = Query(description="终点节点 ID"),
    max_depth: int = Query(default=5, description="最大搜索深度"),
):
    """查询图两节点间路径。"""
    jwt = _extract_jwt(request)
    params: dict = {
        "from_type": from_type,
        "from_id": from_id,
        "to_type": to_type,
        "to_id": to_id,
        "max_depth": max_depth,
    }
    try:
        return await service_client.get_graph_path(project_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/projects/{project_id}/graph/subgraph")
async def get_graph_subgraph(
    project_id: str,
    request: Request,
    user: CurrentUser,
    node_types: str | None = Query(default=None, description="节点类型过滤（逗号分隔）"),
    relation_types: str | None = Query(default=None, description="关系类型过滤（逗号分隔）"),
    min_confidence: float = Query(default=0.0, description="最低置信度过滤"),
    limit: int = Query(default=100, description="最大节点数"),
):
    """查询子图。"""
    jwt = _extract_jwt(request)
    params: dict = {"min_confidence": min_confidence, "limit": limit}
    if node_types is not None:
        params["node_types"] = node_types
    if relation_types is not None:
        params["relation_types"] = relation_types
    try:
        return await service_client.get_graph_subgraph(project_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


# ---------------------------------------------------------------------------
# Trace 路由（C-04 §4.7）
# ---------------------------------------------------------------------------


@app.get("/api/v2/sessions/{session_id}/trace")
async def get_trace(
    session_id: str,
    request: Request,
    user: CurrentUser,
    step_start: int | None = Query(default=None, description="起始步骤"),
    step_end: int | None = Query(default=None, description="结束步骤"),
    include_cognitive: bool = Query(default=True, description="是否包含 Cognitive 级事件"),
    include_context: bool = Query(default=False, description="是否包含 Context Pipeline 事件"),
):
    """查询推理链 Trace。"""
    jwt = _extract_jwt(request)
    params: dict = {
        "include_cognitive": include_cognitive,
        "include_context": include_context,
    }
    if step_start is not None:
        params["step_start"] = step_start
    if step_end is not None:
        params["step_end"] = step_end
    try:
        return await service_client.get_trace(session_id, params, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


# ---------------------------------------------------------------------------
# Report 路由
# ---------------------------------------------------------------------------


@app.post("/api/v2/reports/generate", status_code=202)
async def generate_report(
    req: GenerateReportRequest,
    request: Request,
    user: CurrentUser,
):
    """请求生成报告。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.generate_report(
            req.session_id, req.template_id, req.output_format, jwt
        )
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/reports/{task_id}/status")
async def get_report_status(
    task_id: str,
    request: Request,
    user: CurrentUser,
):
    """查询报告生成状态。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.get_report_status(task_id, jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


# ---------------------------------------------------------------------------
# Project CRUD 路由（直连 PG）
# ---------------------------------------------------------------------------


@app.post("/api/v2/projects", status_code=201)
async def create_project(
    req: CreateProjectRequest,
    session: DBSession,
    user: CurrentUser,
):
    """创建项目 — 按 source_type 分流到不同创建场景。

    四种场景：
      - empty: 纯记录创建
      - git:   git clone 到 data/projects/{id}/source/
      - local: 复用本地现有目录
      - upload: 接收 zip/tar 压缩包并解压
    ingestion 不可用时降级为 status=ready，跳过索引。
    """
    from uuid import uuid4

    from reqradar.kernel.models import Project

    project_id = uuid4()
    data_dir = Path("data/projects") / str(project_id)
    source_path: str | None = None

    # ── 场景分流 ──
    if req.source_type == "git":
        source_path = await _create_from_git(
            data_dir, req.source_config or {}
        )
    elif req.source_type == "local":
        source_path = _create_from_local(req.source_config or {})
    elif req.source_type == "upload":
        # upload 场景需要 UploadFile，由单独的端点处理
        raise HTTPException(
            status_code=400,
            detail="上传场景请使用 multipart/form-data 端点: POST /api/v2/projects/upload",
        )
    # else: empty — 纯记录

    project = Project(
        id=project_id,
        name=req.name,
        description=req.description or "",
        source_type=req.source_type,
        source_config=req.source_config or {},
        repo_path=source_path,
        owner_id=user.get("user_id") if user else None,
        status="creating",  # 初始状态，场景完成后更新为 ready
    )
    session.add(project)
    await session.commit()

    # 场景完成后更新状态
    project.status = "ready"
    await session.commit()
    await session.refresh(project)
    return _project_to_response(project)


@app.post("/api/v2/projects/upload", status_code=201)
async def create_project_upload(
    session: DBSession,
    user: CurrentUser,
    name: str = Form(description="项目名称"),
    description: str = Form(default="", description="项目描述"),
    file: UploadFile | None = None,
):
    """上传压缩包创建项目（multipart/form-data）。"""
    from pathlib import Path
    from uuid import uuid4

    from reqradar.kernel.models import Project

    if file is None:
        raise HTTPException(status_code=400, detail="请上传压缩包文件")

    project_id = uuid4()
    data_dir = Path("data/projects") / str(project_id)

    source_path = await _create_from_upload(data_dir, file)

    project = Project(
        id=project_id,
        name=name,
        description=description,
        source_type="upload",
        source_config={"original_filename": file.filename},
        repo_path=source_path,
        owner_id=user.get("user_id") if user else None,
        status="creating",
    )
    session.add(project)
    await session.commit()

    # 解压完成后更新状态
    project.status = "ready"
    await session.commit()
    await session.refresh(project)
    return _project_to_response(project)


# ── 创建场景辅助函数 ──


async def _create_from_git(
    data_dir: Path, source_config: dict
) -> str:
    """git clone 场景 — 克隆仓库到本地。"""
    import asyncio

    git_url = source_config.get("git_url", "")
    branch = source_config.get("branch", "")

    if not git_url:
        raise HTTPException(status_code=400, detail="source_config.git_url 为必填项")

    data_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone"]
    if branch:
        cmd.extend(["-b", branch])
    cmd.extend([git_url, str(data_dir / "source")])

    process = await asyncio.to_thread(
        lambda: subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
    )
    if process.returncode != 0:
        raise HTTPException(
            status_code=400,
            detail=f"git clone 失败: {process.stderr}",
        )

    return str(data_dir / "source")


def _create_from_local(source_config: dict) -> str:
    """本地目录场景 — 校验存在性和可读性。"""
    local_path = source_config.get("local_path", "")

    if not local_path:
        raise HTTPException(status_code=400, detail="source_config.local_path 为必填项")

    path = Path(local_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"目录不存在: {local_path}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是目录: {local_path}")

    # 检查可读性
    try:
        next(path.iterdir(), None)
    except PermissionError:
        raise HTTPException(status_code=400, detail=f"目录不可读: {local_path}") from None

    return str(path)


async def _create_from_upload(
    data_dir: Path, file: UploadFile
) -> str:
    """压缩包上传场景 — 解压 zip/tar.gz。"""
    import asyncio

    # 校验限制
    max_size = 50 * 1024 * 1024
    max_extracted = 500 * 1024 * 1024
    max_files = 10000

    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大: {len(content)} bytes (最大 {max_size} bytes)",
        )

    filename = file.filename or "archive.zip"
    data_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = data_dir / "source"
    extract_dir.mkdir(exist_ok=True)

    # 解压
    await asyncio.to_thread(_extract_archive, content, filename, extract_dir)

    # 校验解压结果
    file_count = sum(1 for _ in extract_dir.rglob("*") if _.is_file())
    if file_count > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"文件数过多: {file_count} (最大 {max_files})",
        )

    total_size = sum(
        f.stat().st_size for f in extract_dir.rglob("*") if f.is_file()
    )
    if total_size > max_extracted:
        raise HTTPException(
            status_code=400,
            detail=f"解压后过大: {total_size} bytes (最大 {max_extracted} bytes)",
        )

    return str(extract_dir)


def _extract_archive(content: bytes, filename: str, extract_dir: Path) -> None:
    """解压 zip/tar.gz 归档文件。"""
    import io
    import tarfile
    import zipfile

    lower_name = filename.lower()

    if lower_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(extract_dir)
    elif lower_name.endswith((".tar.gz", ".tgz", ".tar")):
        mode = "r:gz" if lower_name.endswith((".tar.gz", ".tgz")) else "r:"
        with tarfile.open(fileobj=io.BytesIO(content), mode=mode) as tf:
            tf.extractall(extract_dir)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的压缩格式: {filename}（支持 .zip / .tar.gz / .tgz / .tar）",
        )


@app.get("/api/v2/projects")
async def list_projects(
    session: DBSession,
    user: CurrentUser,
    limit: int = Query(default=50, description="返回条数上限"),
    offset: int = Query(default=0, description="偏移量"),
    status: str | None = Query(default=None, description="按状态过滤"),
):
    """列出项目。"""
    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.is_active == True)  # noqa: E712
    if status:
        stmt = stmt.where(Project.status == status)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Project.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    projects = result.scalars().all()

    return ProjectListResponse(
        items=[_project_to_response(p) for p in projects],
        total=total,
    )


@app.get("/api/v2/projects/{project_id}")
async def get_project(
    project_id: str,
    session: DBSession,
    user: CurrentUser,
):
    """获取项目详情。"""
    from uuid import UUID

    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.id == UUID(project_id))
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")
    return _project_to_response(project)


@app.put("/api/v2/projects/{project_id}")
async def update_project(
    project_id: str,
    req: UpdateProjectRequest,
    session: DBSession,
    user: CurrentUser,
):
    """更新项目。"""
    from uuid import UUID

    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.id == UUID(project_id))
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    await session.commit()
    await session.refresh(project)
    return _project_to_response(project)


@app.delete("/api/v2/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: DBSession,
    user: CurrentUser,
):
    """删除项目（软删除）。"""
    from uuid import UUID

    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.id == UUID(project_id))
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    project.is_active = False
    await session.commit()


def _project_to_response(project) -> ProjectResponse:
    """将 ORM 对象转换为响应模型。"""

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        source_type=project.source_type,
        status=project.status,
        repo_path=project.repo_path,
        owner_id=str(project.owner_id) if project.owner_id else None,
        profile_data=project.profile_data,
        indexed_at=project.indexed_at.isoformat() if project.indexed_at else None,
        created_at=project.created_at.isoformat() if project.created_at else "",
        updated_at=project.updated_at.isoformat() if project.updated_at else "",
    )


# ---------------------------------------------------------------------------
# 项目索引 / 画像 / 摄取路由
# ---------------------------------------------------------------------------


@app.post("/api/v2/projects/{project_id}/index")
async def index_project(
    project_id: str,
    session: DBSession,
    user: CurrentUser,
):
    """触发代码索引 — 调用 ingestion-service 摄取代码和 Git 历史。"""
    from uuid import UUID

    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.id == UUID(project_id))
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")
    if not project.repo_path:
        raise HTTPException(status_code=400, detail="项目无 repo_path，无法索引")

    ingestion_url = os.environ.get("INGESTION_SERVICE_URL", "http://localhost:8007")
    internal_key = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")

    project.status = "indexing"
    await session.commit()

    indexing_errors: list[str] = []

    # 调 ingestion 代码摄取
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{ingestion_url}/internal/v2/ingest/code",
                json={"project_id": project_id, "repo_path": project.repo_path},
                headers={"X-Internal-API-Key": internal_key},
            )
            if resp.status_code >= 400:
                indexing_errors.append(f"代码索引失败: {resp.text}")
    except Exception as e:
        indexing_errors.append(f"ingestion 不可用: {e}")

    # 调 ingestion Git 摄取（如有 .git）
    git_dir = Path(project.repo_path) / ".git"
    if git_dir.exists():
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    f"{ingestion_url}/internal/v2/ingest/git",
                    json={"project_id": project_id, "repo_path": project.repo_path},
                    headers={"X-Internal-API-Key": internal_key},
                )
                if resp.status_code >= 400:
                    indexing_errors.append(f"Git 索引失败: {resp.text}")
        except Exception as e:
            indexing_errors.append(f"ingestion Git 不可用: {e}")

    project.status = "ready"
    project.indexed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(project)

    return {
        "project_id": project_id,
        "status": project.status,
        "indexed_at": project.indexed_at.isoformat() if project.indexed_at else None,
        "errors": indexing_errors,
    }


@app.post("/api/v2/projects/{project_id}/ingest")
async def ingest_document_to_project(
    project_id: str,
    session: DBSession,
    user: CurrentUser,
    file: UploadFile | None = None,
):
    """上传需求文档并触发摄取。"""
    from uuid import UUID

    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.id == UUID(project_id))
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")
    if file is None:
        raise HTTPException(status_code=400, detail="请上传文档文件")

    ingestion_url = os.environ.get("INGESTION_SERVICE_URL", "http://localhost:8007")
    internal_key = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")

    # 转发文件到 ingestion-service
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{ingestion_url}/internal/v2/ingest/document",
                data={"project_id": project_id},
                files={"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")},
                headers={"X-Internal-API-Key": internal_key},
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"文档摄取失败: {resp.text}",
                )
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档摄取失败: {e}") from e


@app.get("/api/v2/projects/{project_id}/profile")
async def get_project_profile(
    project_id: str,
    session: DBSession,
    user: CurrentUser,
):
    """获取项目画像。"""
    from uuid import UUID

    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.id == UUID(project_id))
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    return {
        "project_id": project_id,
        "profile_data": project.profile_data or {},
    }


@app.post("/api/v2/projects/{project_id}/profile/rebuild")
async def rebuild_project_profile(
    project_id: str,
    session: DBSession,
    user: CurrentUser,
):
    """重建项目画像 — 规则提取 + LLM 增强（降级）。"""
    from uuid import UUID

    from reqradar.kernel.models import Project

    stmt = select(Project).where(Project.id == UUID(project_id))
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    repo_path = project.repo_path
    profile: dict = {}
    internal_key = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")

    if repo_path:
        path = Path(repo_path)
        if path.exists():
            # 规则提取：文件统计
            try:
                py_files = list(path.rglob("*.py"))
                total_files = sum(1 for _ in path.rglob("*") if _.is_file())
                profile["file_count"] = total_files
                profile["python_file_count"] = len(py_files)
                profile["directory_count"] = sum(1 for _ in path.rglob("*") if _.is_dir())

                # 提取依赖文件内容
                for dep_file_name in ["pyproject.toml", "requirements.txt", "package.json"]:
                    dep_file = path / dep_file_name
                    if dep_file.exists():
                        with contextlib.suppress(Exception):
                            profile[f"_{dep_file_name}"] = dep_file.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass

            # LLM 增强（降级：LLM 不可用时仅保留规则提取结果）
            try:
                code_samples: list[str] = []
                for py_file in py_files[:5]:
                    try:
                        content = py_file.read_text(encoding="utf-8")[:2000]
                        code_samples.append(f"# {py_file.name}\n{content}")
                    except Exception:
                        pass

                if code_samples:
                    llm_prompt = (
                        "Analyze the following codebase files and provide:\n"
                        "1. A one-line project description\n"
                        "2. Architecture style (e.g., microservices, monolith, event-driven)\n"
                        "3. Tech stack (languages, frameworks)\n"
                        "4. Top 3 module responsibilities\n\n"
                        + "\n\n".join(code_samples)
                    )
                    # LLM 调用通过 cognitive-rt 代理
                    llm_url = os.environ.get("COGNITIVE_RT_URL", "http://localhost:8002")
                    async with httpx.AsyncClient(timeout=60) as client:
                        llm_resp = await client.post(
                            f"{llm_url}/internal/v2/llm/chat",
                            json={"messages": [{"role": "user", "content": llm_prompt}]},
                            headers={"X-Internal-API-Key": internal_key},
                        )
                        if llm_resp.status_code < 400:
                            llm_data = llm_resp.json()
                            profile["llm_analysis"] = llm_data.get("content", "")
            except Exception:
                profile["llm_analysis"] = None  # LLM 降级

    project.profile_data = profile
    await session.commit()

    return {
        "project_id": project_id,
        "profile_data": profile,
    }


# ---------------------------------------------------------------------------
# ── MCP 管理路由（代理到 integration-service）
# ---------------------------------------------------------------------------


@app.post("/api/v2/mcp/keys", status_code=201)
async def api_create_mcp_key(
    request: Request,
    user: CurrentUser,
):
    """创建 MCP 访问密钥。"""
    jwt = _extract_jwt(request)
    body = await request.json()
    try:
        return await service_client.create_mcp_key(
            name=body.get("name", ""),
            scopes=body.get("scopes", ["read"]),
            jwt=jwt,
        )
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/mcp/keys")
async def api_list_mcp_keys(
    request: Request,
    user: CurrentUser,
):
    """列出所有 MCP 密钥。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.list_mcp_keys(jwt=jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.post("/api/v2/mcp/keys/{key_id}/revoke")
async def api_revoke_mcp_key(
    key_id: str,
    request: Request,
    user: CurrentUser,
):
    """撤销 MCP 密钥。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.revoke_mcp_key(key_id, jwt=jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/mcp/audit")
async def api_get_mcp_audit(
    request: Request,
    user: CurrentUser,
    tool_name: str | None = Query(default=None, description="按工具名过滤"),
    key_id: str | None = Query(default=None, description="按密钥 ID 过滤"),
    limit: int = Query(default=100, description="返回条数上限"),
):
    """查询 MCP 审计日志。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.get_mcp_audit(
            tool_name=tool_name, key_id=key_id, limit=limit, jwt=jwt
        )
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc


@app.get("/api/v2/mcp/config")
async def api_get_mcp_config(
    request: Request,
    user: CurrentUser,
):
    """查询 MCP 运行时配置。"""
    jwt = _extract_jwt(request)
    try:
        return await service_client.get_mcp_config(jwt=jwt)
    except httpx.HTTPStatusError as exc:
        raise await _proxy_error(exc) from exc
