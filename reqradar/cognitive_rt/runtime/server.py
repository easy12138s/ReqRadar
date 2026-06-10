"""Cognitive-RT 服务入口 — 处理来自 BFF 的内部 API 请求。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from reqradar.cognitive_rt.cognition.llm_client import LiteLLMClient
from reqradar.cognitive_rt.runtime.checkpoint import CheckpointManager
from reqradar.cognitive_rt.runtime.checkpoint_storage import CheckpointStorage
from reqradar.cognitive_rt.runtime.event_bus import InMemoryEventBus
from reqradar.cognitive_rt.runtime.events import EventPublisher
from reqradar.cognitive_rt.runtime.runner_factory import (
    create_runner_components,
)
from reqradar.cognitive_rt.runtime.session_api import SessionInfo, SessionService
from reqradar.kernel.database import Base, create_engine, create_session_factory

logger = logging.getLogger(__name__)

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./reqradar_dev.db")


# ── Pydantic 请求/响应模型 ────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    """创建 Session 请求。"""

    project_id: str = Field(description="项目 ID")
    user_id: str = Field(default="system", description="用户 ID")
    config: dict | None = Field(default=None, description="会话配置")


class StartSessionRequest(BaseModel):
    """启动 Session 请求。"""

    requirement_text: str = Field(default="", description="需求文本")
    resume_from: int | None = Field(default=None, description="从指定步骤恢复")
    config: dict = Field(default_factory=dict, description="运行配置")


class CheckpointRequest(BaseModel):
    """创建 Checkpoint 请求。"""

    checkpoint_type: str = Field(default="step_complete", description="Checkpoint 类型")
    current_step: int = Field(default=0, description="当前步骤")
    evidence_count: int = Field(default=0, description="证据数量")
    dimension_status: dict | None = Field(default=None, description="维度状态")


class SessionResponse(BaseModel):
    """Session 信息响应。"""

    session_id: str = Field(description="Session ID")
    project_id: str = Field(description="项目 ID")
    user_id: str = Field(description="用户 ID")
    status: str = Field(description="状态")
    created_at: str | None = Field(default=None, description="创建时间")
    started_at: str | None = Field(default=None, description="启动时间")
    finished_at: str | None = Field(default=None, description="完成时间")


class EventResponse(BaseModel):
    """事件信息响应。"""

    event_id: str = Field(description="事件 ID")
    session_id: str = Field(description="Session ID")
    sequence: int = Field(description="序号")
    event_type: str = Field(description="事件类型")
    event_level: str = Field(description="事件层级")
    timestamp: str = Field(description="时间戳")
    producer: str = Field(description="生产者")
    payload: dict = Field(default_factory=dict, description="负载")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Cognitive-RT Service 启动")

    engine = create_engine(DATABASE_URL)
    app.state.db_session_factory = create_session_factory(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.llm_client = LiteLLMClient()

    # 注入 EventBus（Redis Stream 模式，降级为内存模式）
    redis_url = os.environ.get("REDIS_URL", "")
    _event_bus = InMemoryEventBus(redis_url=redis_url)
    await _event_bus.connect()

    # 注入 db_session_factory 到所有需要 PG 持久化的组件
    _publisher._bus = _event_bus
    _publisher._db_session_factory = app.state.db_session_factory
    _checkpoint_storage._db_session_factory = app.state.db_session_factory
    _service._db_session_factory = app.state.db_session_factory

    yield

    await _event_bus.close()
    await engine.dispose()
    logger.info("Cognitive-RT Service 关闭")


app = FastAPI(
    title="Cognitive-RT Service",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Internal API Key 中间件 ──────────────────────────────────────────────


@app.middleware("http")
async def verify_internal_api_key(request: Request, call_next):
    """校验入站请求的 X-Internal-API-Key 头。"""
    if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    api_key = request.headers.get("X-Internal-API-Key", "")
    if api_key != INTERNAL_API_KEY:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "UNAUTHORIZED", "message": "Invalid Internal API Key"}},
        )
    return await call_next(request)


# ── 共享基础设施（单例）─────────────────────────────────────────────────


_checkpoint_storage = CheckpointStorage()
_checkpoint_mgr = CheckpointManager(storage=_checkpoint_storage)
_publisher = EventPublisher()
_service = SessionService(
    event_publisher=_publisher,
    checkpoint_manager=_checkpoint_mgr,
    checkpoint_storage=_checkpoint_storage,
)


# ── 健康检查 ────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """服务健康检查。"""
    return {"status": "ok", "service": "cognitive-rt"}


# ── Session 端点 (I-01 §3.1-3.2) ────────────────────────────────────────


@app.post("/internal/v2/sessions", status_code=201)
async def create_session(body: CreateSessionRequest):
    """创建 Session。"""
    info = _service.create(project_id=body.project_id, user_id=body.user_id, config=body.config)
    return _info_to_dict(info)


@app.post("/internal/v2/sessions/{session_id}/start")
async def start_session(session_id: str, body: StartSessionRequest):
    """启动 Session — 创建 Runner 组件并触发真实推理。"""
    try:
        info = _service.get(session_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e

    project_id = info.project_id if hasattr(info, "project_id") else "default"
    user_id = info.user_id if hasattr(info, "user_id") else "system"

    agent, llm_client, tool_registry = create_runner_components(
        session_id=session_id,
        requirement_text=body.requirement_text,
        project_id=str(project_id),
        user_id=str(user_id),
        config=body.config,
    )

    try:
        info = await _service.start(
            session_id,
            agent=agent,
            llm_client=llm_client,
            tool_registry=tool_registry,
            requirement_text=body.requirement_text,
            resume_from=body.resume_from,
        )
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=409, detail={"error": {"code": "SESSION_INVALID_STATE", "message": str(e)}}
        ) from e

    return _info_to_dict(info)


@app.get("/internal/v2/sessions/{session_id}")
async def get_session(session_id: str):
    """查询 Session。"""
    try:
        info = _service.get(session_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e
    return _info_to_dict(info)


@app.post("/internal/v2/sessions/{session_id}/cancel", status_code=202)
async def cancel_session(session_id: str):
    """取消 Session。"""
    try:
        info = _service.cancel(session_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=409, detail={"error": {"code": "SESSION_INVALID_STATE", "message": str(e)}}
        ) from e
    return _info_to_dict(info)


@app.post("/internal/v2/sessions/{session_id}/checkpoint")
async def create_checkpoint(session_id: str):
    """手动创建 Checkpoint。"""
    try:
        cp_id = _service.checkpoint(session_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e
    return {"checkpoint_id": cp_id}


@app.get("/internal/v2/sessions/{session_id}/events")
async def get_events(session_id: str, limit: int = 100):
    """查询事件流。"""
    try:
        events = _service.get_events(session_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e
    return {"session_id": session_id, "events": events[-limit:], "total": len(events)}


@app.get("/internal/v2/sessions/{session_id}/evidence")
async def get_evidence(session_id: str, type: str | None = None, limit: int = 50):
    """获取 Session 的证据列表 (I-01 §6.5)。"""
    try:
        items = _service.get_evidence(session_id, evidence_type=type, limit=limit)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e
    return {"session_id": session_id, "items": items, "total": len(items)}


@app.get("/internal/v2/sessions/{session_id}/dimensions")
async def get_dimensions(session_id: str):
    """获取 Session 的七维度状态 (I-01 §6.6)。"""
    try:
        data = _service.get_dimensions(session_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e
    return {"session_id": session_id, "dimensions": data}


@app.get("/internal/v2/sessions/{session_id}/trace")
async def get_trace(session_id: str):
    """查询推理链 Trace。"""
    try:
        _service.get(session_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
        ) from e

    events = _service.get_events(session_id) if hasattr(_service, "get_events") else []

    steps = []
    current_step = None
    for evt in events:
        evt_type = (
            evt.get("event_type", "") if isinstance(evt, dict) else getattr(evt, "event_type", "")
        )
        payload = evt.get("payload", {}) if isinstance(evt, dict) else getattr(evt, "payload", {})
        created_at = (
            evt.get("created_at", "") if isinstance(evt, dict) else getattr(evt, "created_at", "")
        )

        if evt_type == "STEP_STARTED":
            current_step = {
                "step_id": payload.get("step_id", ""),
                "started_at": str(created_at),
                "tools": [],
            }
        elif evt_type == "STEP_COMPLETED" and current_step:
            current_step["completed_at"] = str(created_at)
            current_step["result_summary"] = payload.get("result_summary", "")
            steps.append(current_step)
            current_step = None

    return {"session_id": session_id, "steps": steps, "total": len(steps)}


# ── 工具函数 ─────────────────────────────────────────────────────────────


def _info_to_dict(info: SessionInfo) -> dict:
    """SessionInfo 转字典。"""
    return {
        "session_id": info.session_id,
        "project_id": info.project_id,
        "user_id": info.user_id,
        "status": info.status.value,
        "created_at": info.created_at.isoformat(),
        "started_at": info.started_at.isoformat() if info.started_at else None,
        "finished_at": info.finished_at.isoformat() if info.finished_at else None,
        "total_reasoning_steps": info.total_reasoning_steps,
        "last_checkpoint_version": info.last_checkpoint_version,
    }
