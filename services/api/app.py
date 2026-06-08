"""API-Service BFF — 纯代理层，将请求转发至下游服务。"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket
from pydantic import BaseModel, Field

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
    config: dict = Field(default_factory=dict, description="项目配置")


class UpdateProjectRequest(BaseModel):
    """更新项目请求。"""

    name: str | None = Field(default=None, description="项目名称")
    description: str | None = Field(default=None, description="项目描述")
    config: dict | None = Field(default=None, description="项目配置")


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
    except Exception:
        body = {"error": {"code": "DOWNSTREAM_ERROR", "message": resp.text}}
    return HTTPException(status_code=resp.status_code, detail=body)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.time()
    logger.info("API-Service BFF 启动")
    yield
    await service_client.close()
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
    """WebSocket 实时事件推送（暂存桩，P3 实现）。"""
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "info",
            "data": {"message": "WebSocket 桥接暂未实现，将在 P3 阶段接入 Redis Pub/Sub"},
        }
    )
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
# MCP 管理路由（代理到 integration-service）
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
