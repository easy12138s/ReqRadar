"""Index Service — 向量检索 + Checkpoint 存储 + L3 知识管理。

对齐 I-01 §3 契约，实现 Checkpoint / 向量检索 / L3 知识的完整端点。
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine as sync_create_engine
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from reqradar.index_svc.knowledge.models import L3KnowledgeBase
from reqradar.index_svc.knowledge.writer import L3Writer
from reqradar.kernel.database import create_engine, create_session_factory
from reqradar.kernel.enums import FreshnessStatus, KnowledgeNodeType

logger = logging.getLogger(__name__)

_start_time: float = 0.0


# ── Pydantic 请求/响应模型 ──────────────────────────────────────────────


class ErrorDetail(BaseModel):
    """错误详情 (I-01 §2.2)。"""

    code: str = Field(description="错误码")
    message: str = Field(description="错误信息")
    details: dict = Field(default_factory=dict, description="错误详情")


class ErrorResponse(BaseModel):
    """统一错误响应 (I-01 §2.2)。"""

    error: ErrorDetail = Field(description="错误详情")


# ── Checkpoint 模型 (§3.1-3.4) ──────────────────────────────────────────


class CheckpointCreateRequest(BaseModel):
    """创建 Checkpoint 请求体 (§3.1)。"""

    session_id: str = Field(description="会话 ID")
    version: int = Field(description="版本号，同一 Session 内严格递增")
    previous_version: int | None = Field(default=None, description="前一版本号")
    type: str = Field(description="检查点类型: STEP_COMPLETE/TOOL_PRE/TOOL_POST/MANUAL/PERIODIC")
    state_summary: dict = Field(description="状态摘要，用于列表查询")
    diff: dict | None = Field(default=None, description="与前一版本的差异")
    hot_state: dict = Field(description="热状态数据，≤ 1MB")
    cold_state_json: str | None = Field(default=None, description="冷状态完整 JSON")
    metadata: dict | None = Field(default=None, description="元数据")


class CheckpointCreateResponse(BaseModel):
    """创建 Checkpoint 响应体 (§3.1)。"""

    checkpoint_id: str = Field(description="检查点 ID")
    version: int = Field(description="版本号")
    full_state_uri: str = Field(description="完整状态存储 URI")
    created_at: str = Field(description="创建时间 (ISO 8601 UTC)")


class CheckpointListItem(BaseModel):
    """Checkpoint 列表条目 (§3.3)。"""

    checkpoint_id: str = Field(description="检查点 ID")
    version: int = Field(description="版本号")
    type: str = Field(description="检查点类型")
    state_summary: dict = Field(description="状态摘要")


class CheckpointListResponse(BaseModel):
    """Checkpoint 列表响应 (§3.3)。"""

    session_id: str = Field(description="会话 ID")
    total: int = Field(description="总数")
    items: list[CheckpointListItem] = Field(description="检查点列表")
    has_more: bool = Field(description="是否有更多数据")


class CheckpointDiffVersionItem(BaseModel):
    """版本差异条目 (§3.4)。"""

    version: int = Field(description="版本号")
    type: str = Field(description="检查点类型")
    diff: dict | None = Field(default=None, description="版本差异")


class CheckpointDiffResponse(BaseModel):
    """版本差异响应 (§3.4)。"""

    from_version: int = Field(description="起始版本")
    to_version: int = Field(description="目标版本")
    diffs: list[CheckpointDiffVersionItem] = Field(description="差异列表")


# ── 向量检索模型 (§3.5) ─────────────────────────────────────────────────


class VectorSearchRequest(BaseModel):
    """向量检索请求体 (§3.5)。"""

    project_id: str = Field(description="项目 ID")
    collection: str = Field(description="集合名称: requirements / code")
    query_text: str = Field(description="查询文本")
    top_k: int = Field(default=10, description="返回数量上限")
    filters: dict | None = Field(default=None, description="ChromaDB where 条件")
    min_score: float | None = Field(default=None, description="最低相似度阈值")


class VectorSearchResultItem(BaseModel):
    """向量检索结果条目。"""

    id: str = Field(description="chunk ID")
    content: str = Field(description="内容")
    metadata: dict = Field(description="元数据")
    score: float = Field(description="相似度分数")


class VectorSearchResponse(BaseModel):
    """向量检索响应 (§3.5)。"""

    results: list[VectorSearchResultItem] = Field(description="检索结果")
    query_time_ms: int = Field(description="查询耗时 (毫秒)")


# ── 知识模型 (§3.6-3.10) ────────────────────────────────────────────────


class KnowledgeAppendRequest(BaseModel):
    """追加 L3 知识请求体 (§3.6)。"""

    project_id: str = Field(description="项目 ID")
    knowledge_type: str = Field(
        description="知识类型: glossary/module_profile/constraint/decision/risk/requirement/incident"
    )
    payload: dict = Field(description="知识内容，各类型结构见 M-03")
    evidence_ref: str = Field(description="支撑该知识的 L2 Evidence ID")
    session_id: str = Field(description="触发沉淀的 Session ID")


class KnowledgeAppendResponse(BaseModel):
    """追加 L3 知识响应体 (§3.6)。"""

    id: str = Field(description="知识 ID")
    knowledge_type: str = Field(description="知识类型")
    freshness: str = Field(description="新鲜度状态")
    confidence_score: float = Field(description="置信度评分")
    created_at: str = Field(description="创建时间 (ISO 8601 UTC)")


class KnowledgeUpdateRequest(BaseModel):
    """更新 L3 知识请求体 (§3.7)。"""

    project_id: str = Field(description="项目 ID")
    knowledge_type: str = Field(description="知识类型")
    knowledge_id: str = Field(description="知识 ID")
    payload: dict = Field(description="更新内容 (patch 语义)")
    session_id: str = Field(description="触发更新的 Session ID")


class KnowledgeUpdateResponse(BaseModel):
    """更新 L3 知识响应体 (§3.7)。"""

    id: str = Field(description="知识 ID")
    knowledge_type: str = Field(description="知识类型")
    freshness: str = Field(description="新鲜度状态")
    confidence_score: float = Field(description="置信度评分")
    updated_at: str = Field(description="更新时间 (ISO 8601 UTC)")


class KnowledgeDeprecateRequest(BaseModel):
    """废弃 L3 知识请求体 (§3.8)。"""

    project_id: str = Field(description="项目 ID")
    knowledge_type: str = Field(description="知识类型")
    knowledge_id: str = Field(description="知识 ID")
    reason: str = Field(description="废弃原因")


class KnowledgeDeprecateResponse(BaseModel):
    """废弃 L3 知识响应体 (§3.8)。"""

    id: str = Field(description="知识 ID")
    knowledge_type: str = Field(description="知识类型")
    freshness: str = Field(description="新鲜度状态")
    reason: str = Field(description="废弃原因")


class KnowledgeMergeRequest(BaseModel):
    """合并 L3 知识请求体 (§3.9)。"""

    project_id: str = Field(description="项目 ID")
    knowledge_type: str = Field(description="知识类型")
    knowledge_ids: list[str] = Field(description="待合并的知识 ID 列表")
    strategy: str = Field(default="keep_newer", description="合并策略: keep_newer / keep_older")
    payload_overrides: dict | None = Field(default=None, description="覆盖字段")


class KnowledgeMergeResponse(BaseModel):
    """合并 L3 知识响应体 (§3.9)。"""

    id: str = Field(description="合并后的知识 ID")
    merged_from: list[str] = Field(description="原始知识 ID 列表")
    knowledge_type: str = Field(description="知识类型")
    freshness: str = Field(description="新鲜度状态")
    confidence_score: float = Field(description="置信度评分")
    created_at: str = Field(description="创建时间 (ISO 8601 UTC)")


class KnowledgeQueryItem(BaseModel):
    """知识查询条目 (§3.10)。"""

    id: str = Field(description="知识 ID")
    knowledge_type: str = Field(description="知识类型")
    data: dict = Field(description="知识内容")
    freshness: str = Field(description="新鲜度状态")
    confidence_score: float = Field(description="置信度评分")
    verification_count: int = Field(description="验证次数")


class KnowledgeQueryResponse(BaseModel):
    """知识查询响应 (§3.10)。"""

    items: list[KnowledgeQueryItem] = Field(description="知识列表")
    total: int = Field(description="总数")


class EntityLinkCreate(BaseModel):
    """创建实体链接请求体。"""
    project_id: str
    source_layer: str
    source_type: str
    source_id: str
    target_layer: str
    target_type: str
    target_id: str
    relation_type: str
    confidence: float | None = None
    source_session_id: str | None = None
    evidence: str | None = None


# ── 辅助函数 ────────────────────────────────────────────────────────────

# 合法的检查点类型集合
_VALID_CHECKPOINT_TYPES = frozenset(
    {"STEP_COMPLETE", "TOOL_PRE", "TOOL_POST", "MANUAL", "PERIODIC"}
)


def _iso(dt: datetime | None) -> str | None:
    """将 datetime 转换为 ISO 8601 UTC 字符串。"""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_error(
    status_code: int, code: str, message: str, details: dict | None = None
) -> HTTPException:
    """构造统一格式的 HTTP 错误（对齐 I-01 §2.2）。"""
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _validate_checkpoint_type(value: str) -> None:
    """校验检查点类型是否合法。"""
    if value not in _VALID_CHECKPOINT_TYPES:
        raise _http_error(
            400,
            "INVALID_CHECKPOINT_TYPE",
            f"不支持的检查点类型: {value}",
            {"valid": sorted(_VALID_CHECKPOINT_TYPES)},
        )


def _validate_knowledge_type(value: str) -> KnowledgeNodeType:
    """校验知识类型并返回枚举值。"""
    try:
        return KnowledgeNodeType(value)
    except ValueError as err:
        valid = [e.value for e in KnowledgeNodeType]
        raise _http_error(
            400, "INVALID_KNOWLEDGE_TYPE", f"不支持的知识类型: {value}", {"valid": valid}
        ) from err


def _knowledge_to_dict(knowledge: L3KnowledgeBase, payloads: dict[str, dict]) -> dict:
    """将 L3KnowledgeBase 转换为 I-01 §3.10 响应格式。"""
    payload_data = payloads.get(knowledge.id, {})
    return {
        "id": knowledge.id,
        "knowledge_type": knowledge.knowledge_type.value,
        "data": payload_data.get("payload", {}),
        "freshness": knowledge.freshness.value,
        "confidence_score": knowledge.confidence.confidence_score,
        "verification_count": knowledge.confidence.verification_count,
    }


def _entity_link_to_dict(row) -> dict:
    """将 EntityLink ORM 行转换为字典。"""
    return {
        "id": row.id,
        "project_id": str(row.project_id),
        "source_layer": row.source_layer,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "target_layer": row.target_layer,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "relation_type": row.relation_type,
        "confidence": row.confidence,
        "source_session_id": row.source_session_id,
        "evidence": row.evidence,
        "is_stale": row.is_stale,
        "created_at": _iso(row.created_at),
    }


# ── 应用生命周期 ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """初始化/清理服务资源。"""
    global _start_time
    _start_time = time.time()
    logger.info("Index Service 启动 (port 8003)")
    app.state.checkpoints = {}  # session_id -> list[dict]
    app.state.knowledge_payloads = {}  # knowledge_id -> {payload, evidence_ref}

    # 初始化数据库引擎和会话工厂
    database_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./reqradar_dev.db")
    engine = create_engine(database_url)
    db_session_factory = create_session_factory(engine)
    app.state.db_session_factory = db_session_factory

    # 初始化同步 DB 会话工厂（entity_links 等同步操作使用）
    sync_db_url = database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    app.state.sync_db_session_factory = sessionmaker(sync_create_engine(sync_db_url))

    # 初始化 L3Writer 并注入 db_session_factory
    app.state.writer = L3Writer(db_session_factory)

    # 初始化 PgVectorStore（替代 ChromaDB）
    try:
        from reqradar.index_svc.vector_store import PgVectorStore

        app.state.vector_store = PgVectorStore(
            db_session_factory=db_session_factory,
            collection_name="requirements",
        )
        logger.info("PgVectorStore 已初始化")
    except Exception as e:
        logger.warning("PgVectorStore 初始化失败，检索降级为空: %s", e)
        app.state.vector_store = None

    yield
    await engine.dispose()
    logger.info("Index Service 关闭")


app = FastAPI(
    title="ReqRadar Index Service",
    version="2.0.0",
    lifespan=lifespan,
)

async def get_db(request: Request) -> AsyncSession:
    """获取数据库会话。"""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request: Request, exc: HTTPException):
    """统一错误响应格式，对齐 I-01 §2.2。"""
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")


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


# ── 健康检查 ────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """服务健康检查。"""
    return {"status": "ok", "service": "index", "uptime_seconds": int(time.time() - _start_time)}


# ── Checkpoint 端点 (§3.1-3.4) ──────────────────────────────────────────


@app.post("/internal/v2/checkpoints", status_code=201, response_model=CheckpointCreateResponse)
async def create_checkpoint(req: CheckpointCreateRequest, request: Request):
    """创建 Checkpoint (§3.1)。"""
    store: dict[str, list[dict]] = request.app.state.checkpoints
    session_cps = store.setdefault(req.session_id, [])

    _validate_checkpoint_type(req.type)

    # 版本冲突检测
    if session_cps:
        latest_version = session_cps[-1]["version"]
        if req.version <= latest_version:
            raise _http_error(
                409,
                "VERSION_CONFLICT",
                f"版本冲突: 新版本 {req.version} ≤ 最新版本 {latest_version}",
                {"expected_gt": latest_version, "actual": req.version},
            )
        if req.previous_version is not None and req.previous_version != latest_version:
            raise _http_error(
                409,
                "VERSION_CONFLICT",
                f"版本链断裂: previous_version={req.previous_version} ≠ 最新版本 {latest_version}",
                {"expected": latest_version, "actual": req.previous_version},
            )

    checkpoint_id = str(uuid4())
    now = datetime.now(UTC)

    checkpoint = {
        "checkpoint_id": checkpoint_id,
        "session_id": req.session_id,
        "version": req.version,
        "previous_version": req.previous_version,
        "type": req.type,
        "state_summary": req.state_summary,
        "diff": req.diff,
        "hot_state": req.hot_state,
        "cold_state_json": req.cold_state_json,
        "metadata": req.metadata or {},
        "created_at": now,
    }
    session_cps.append(checkpoint)
    session_cps.sort(key=lambda c: c["version"])

    # PG 持久化
    try:
        from uuid import UUID

        from reqradar.kernel.models import Checkpoint as CheckpointModel

        session = request.app.state.sync_db_session_factory()
        db_cp = CheckpointModel(
            checkpoint_id=UUID(checkpoint_id),
            session_id=UUID(req.session_id),
            version=req.version,
            previous_version=req.previous_version,
            created_by="cognitive-rt",
            type=req.type,
            state_summary=req.state_summary,
            diff=req.diff or {},
            hot_state=req.hot_state,
            full_state_uri=f"minio://checkpoints/{req.session_id}/v{req.version}/context_snapshot.json",
            metadata_=req.metadata or {},
        )
        session.add(db_cp)
        session.commit()
        session.close()
    except Exception as e:
        logger.warning("Checkpoint PG 持久化失败: %s", e)

    logger.info(
        "Checkpoint 创建: session=%s version=%d type=%s", req.session_id, req.version, req.type
    )

    return CheckpointCreateResponse(
        checkpoint_id=checkpoint_id,
        version=req.version,
        full_state_uri=f"minio://checkpoints/{req.session_id}/v{req.version}/context_snapshot.json",
        created_at=_iso(now),
    )


@app.get("/internal/v2/checkpoints/{session_id}")
async def get_checkpoint(
    session_id: str,
    request: Request,
    v: int | None = Query(default=None, description="版本号，null 表示最新"),
    include_cold: bool = Query(default=False, description="是否返回冷状态数据"),
    at: str | None = Query(default=None, description="获取特定时间点的最新版本 (ISO 8601 UTC)"),
):
    """查询 Checkpoint (§3.2)。"""
    store: dict[str, list[dict]] = request.app.state.checkpoints
    session_cps = store.get(session_id, [])

    if not session_cps:
        raise _http_error(404, "CHECKPOINT_NOT_FOUND", f"Session {session_id} 无 Checkpoint")

    target: dict | None = None

    if v is not None:
        for cp in session_cps:
            if cp["version"] == v:
                target = cp
                break
        if target is None:
            raise _http_error(
                404, "CHECKPOINT_NOT_FOUND", f"Session {session_id} 无版本 {v} 的 Checkpoint"
            )
    elif at is not None:
        try:
            at_dt = datetime.fromisoformat(at)
        except ValueError as err:
            raise _http_error(400, "INVALID_DATETIME", f"无效的时间格式: {at}") from err
        for cp in reversed(session_cps):
            if cp["created_at"] <= at_dt:
                target = cp
                break
        if target is None:
            raise _http_error(
                404, "CHECKPOINT_NOT_FOUND", f"Session {session_id} 在 {at} 之前无 Checkpoint"
            )
    else:
        target = session_cps[-1]

    cold_state = None
    if include_cold and target.get("cold_state_json"):
        try:
            cold_state = json.loads(target["cold_state_json"])
        except (json.JSONDecodeError, TypeError):
            cold_state = target["cold_state_json"]

    return {
        "checkpoint_id": target["checkpoint_id"],
        "session_id": target["session_id"],
        "version": target["version"],
        "previous_version": target.get("previous_version"),
        "created_at": _iso(target["created_at"]),
        "type": target["type"],
        "state_summary": target["state_summary"],
        "diff": target.get("diff"),
        "hot_state": target["hot_state"],
        "cold_state": cold_state,
        "metadata": target.get("metadata"),
    }


@app.get("/internal/v2/checkpoints", response_model=CheckpointListResponse)
async def list_checkpoints(
    request: Request,
    session_id: str = Query(description="会话 ID"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量上限"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    type: str | None = Query(default=None, description="按类型过滤"),
):
    """查询版本链列表 (§3.3)。"""
    store: dict[str, list[dict]] = request.app.state.checkpoints
    session_cps = store.get(session_id, [])

    filtered = session_cps
    if type is not None:
        filtered = [cp for cp in session_cps if cp["type"] == type]

    total = len(filtered)
    page = filtered[offset : offset + limit]
    has_more = offset + limit < total

    return CheckpointListResponse(
        session_id=session_id,
        total=total,
        items=[
            CheckpointListItem(
                checkpoint_id=cp["checkpoint_id"],
                version=cp["version"],
                type=cp["type"],
                state_summary=cp["state_summary"],
            )
            for cp in page
        ],
        has_more=has_more,
    )


@app.get("/internal/v2/checkpoints/{session_id}/diff", response_model=CheckpointDiffResponse)
async def diff_checkpoints(
    session_id: str,
    request: Request,
    from_version: int = Query(alias="from", description="起始版本"),
    to_version: int = Query(alias="to", description="目标版本"),
):
    """比较两个版本的差异 (§3.4)。"""
    store: dict[str, list[dict]] = request.app.state.checkpoints
    session_cps = store.get(session_id, [])

    if not session_cps:
        raise _http_error(404, "CHECKPOINT_NOT_FOUND", f"Session {session_id} 无 Checkpoint")

    in_range = [cp for cp in session_cps if from_version <= cp["version"] <= to_version]
    in_range.sort(key=lambda c: c["version"])

    if not in_range:
        raise _http_error(
            404,
            "CHECKPOINT_NOT_FOUND",
            f"Session {session_id} 在版本 {from_version}-{to_version} 范围内无 Checkpoint",
        )

    return CheckpointDiffResponse(
        from_version=from_version,
        to_version=to_version,
        diffs=[
            CheckpointDiffVersionItem(
                version=cp["version"],
                type=cp["type"],
                diff=cp.get("diff"),
            )
            for cp in in_range
        ],
    )


# ── 向量检索 (§3.5) ─────────────────────────────────────────────────────


@app.post("/internal/v2/search/vector", response_model=VectorSearchResponse)
async def search_vector(req: VectorSearchRequest, request: Request):
    """向量检索 (§3.5) — PgVectorStore 查询。"""
    start_time = time.monotonic()

    store = request.app.state.vector_store
    if store is None:
        logger.warning("向量检索: PgVectorStore 不可用，返回空结果")
        return VectorSearchResponse(results=[], query_time_ms=0)

    logger.info(
        "向量检索: project=%s collection=%s query=%s top_k=%d",
        req.project_id,
        req.collection,
        req.query_text[:50],
        req.top_k,
    )

    # 按 collection 切换集合
    if req.collection != store._collection_name:
        try:
            from reqradar.index_svc.vector_store import PgVectorStore

            store = PgVectorStore(
                db_session_factory=request.app.state.db_session_factory,
                collection_name=req.collection,
            )
        except Exception:
            return VectorSearchResponse(results=[], query_time_ms=0)

    try:
        search_results = await store.search(
            query=req.query_text,
            top_k=req.top_k,
        )
    except Exception as e:
        logger.warning("向量检索执行失败: %s", e)
        return VectorSearchResponse(results=[], query_time_ms=0)

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    items = [
        VectorSearchResultItem(
            id=r.id,
            content=r.content,
            metadata=r.metadata or {},
            score=1.0 - r.distance,
        )
        for r in search_results
    ]

    return VectorSearchResponse(results=items, query_time_ms=elapsed_ms)


# ── 知识端点 (§3.6-3.10) ────────────────────────────────────────────────


@app.post("/internal/v2/knowledge/append", status_code=201, response_model=KnowledgeAppendResponse)
async def knowledge_append(req: KnowledgeAppendRequest, request: Request):
    """追加 L3 知识 (§3.6)。"""
    writer: L3Writer = request.app.state.writer
    payloads: dict[str, dict] = request.app.state.knowledge_payloads

    knowledge_type = _validate_knowledge_type(req.knowledge_type)

    knowledge = L3KnowledgeBase(
        project_id=req.project_id,
        knowledge_type=knowledge_type,
    )
    knowledge = writer.append(knowledge, req.session_id)
    payloads[knowledge.id] = {
        "payload": req.payload,
        "evidence_ref": req.evidence_ref,
    }

    logger.info(
        "知识追加: id=%s type=%s project=%s", knowledge.id, req.knowledge_type, req.project_id
    )

    return KnowledgeAppendResponse(
        id=knowledge.id,
        knowledge_type=knowledge.knowledge_type.value,
        freshness=knowledge.freshness.value,
        confidence_score=knowledge.confidence.confidence_score,
        created_at=_iso(knowledge.created_at),
    )


@app.post("/internal/v2/knowledge/update", response_model=KnowledgeUpdateResponse)
async def knowledge_update(req: KnowledgeUpdateRequest, request: Request):
    """更新 L3 知识 (§3.7)。"""
    writer: L3Writer = request.app.state.writer
    payloads: dict[str, dict] = request.app.state.knowledge_payloads

    existing = writer.get(req.knowledge_id)
    if existing is None:
        raise _http_error(404, "KNOWLEDGE_NOT_FOUND", f"知识 {req.knowledge_id} 不存在")

    # 触发 L3Writer 的验证计数 + 变更日志
    updated = writer.update(req.knowledge_id, {}, req.session_id)
    if updated is None:
        raise _http_error(404, "KNOWLEDGE_NOT_FOUND", f"知识 {req.knowledge_id} 更新失败")

    # 更新 payload（patch 语义）
    if req.knowledge_id in payloads:
        payloads[req.knowledge_id]["payload"].update(req.payload)
    else:
        payloads[req.knowledge_id] = {"payload": req.payload, "evidence_ref": ""}

    logger.info("知识更新: id=%s", req.knowledge_id)

    return KnowledgeUpdateResponse(
        id=updated.id,
        knowledge_type=updated.knowledge_type.value,
        freshness=updated.freshness.value,
        confidence_score=updated.confidence.confidence_score,
        updated_at=_iso(updated.updated_at),
    )


@app.post("/internal/v2/knowledge/deprecate", response_model=KnowledgeDeprecateResponse)
async def knowledge_deprecate(req: KnowledgeDeprecateRequest, request: Request):
    """废弃 L3 知识 (§3.8)。"""
    writer: L3Writer = request.app.state.writer

    result = writer.deprecate(req.knowledge_id, session_id="")
    if result is None:
        raise _http_error(404, "KNOWLEDGE_NOT_FOUND", f"知识 {req.knowledge_id} 不存在")

    logger.info("知识废弃: id=%s reason=%s", req.knowledge_id, req.reason)

    return KnowledgeDeprecateResponse(
        id=result.id,
        knowledge_type=result.knowledge_type.value,
        freshness=result.freshness.value,
        reason=req.reason,
    )


@app.post("/internal/v2/knowledge/merge", status_code=201, response_model=KnowledgeMergeResponse)
async def knowledge_merge(req: KnowledgeMergeRequest, request: Request):
    """合并 L3 知识 (§3.9)。"""
    writer: L3Writer = request.app.state.writer
    payloads: dict[str, dict] = request.app.state.knowledge_payloads

    if len(req.knowledge_ids) < 2:
        raise _http_error(400, "MERGE_REQUIRES_TWO", "合并至少需要 2 条知识")

    knowledge_type = _validate_knowledge_type(req.knowledge_type)

    # 查找所有待合并的知识
    sources: list[L3KnowledgeBase] = []
    source_payloads: list[dict] = []
    for kid in req.knowledge_ids:
        k = writer.get(kid)
        if k is None:
            raise _http_error(404, "KNOWLEDGE_NOT_FOUND", f"知识 {kid} 不存在")
        sources.append(k)
        source_payloads.append(payloads.get(kid, {}).get("payload", {}))

    # 合并 payload：按策略决定覆盖顺序
    merged_payload: dict = {}
    ordered = reversed(source_payloads) if req.strategy == "keep_newer" else source_payloads
    for sp in ordered:
        merged_payload.update(sp)
    if req.payload_overrides:
        merged_payload.update(req.payload_overrides)

    # 通过 supersede 关联第一条旧知识，自动写入新条目
    new_knowledge = L3KnowledgeBase(
        project_id=req.project_id,
        knowledge_type=knowledge_type,
    )
    result = writer.supersede(sources[0].id, new_knowledge, session_id="")
    if result is not None:
        new_knowledge = result
    payloads[new_knowledge.id] = {"payload": merged_payload, "evidence_ref": ""}

    # 废弃剩余旧知识
    for old in sources[1:]:
        writer.deprecate(old.id, session_id="")

    logger.info(
        "知识合并: ids=%s -> %s strategy=%s", req.knowledge_ids, new_knowledge.id, req.strategy
    )

    return KnowledgeMergeResponse(
        id=new_knowledge.id,
        merged_from=req.knowledge_ids,
        knowledge_type=new_knowledge.knowledge_type.value,
        freshness=new_knowledge.freshness.value,
        confidence_score=new_knowledge.confidence.confidence_score,
        created_at=_iso(new_knowledge.created_at),
    )


@app.get("/internal/v2/knowledge/query", response_model=KnowledgeQueryResponse)
async def knowledge_query(
    request: Request,
    project_id: str = Query(description="项目 ID"),
    knowledge_types: str | None = Query(default=None, description="逗号分隔的知识类型"),
    freshness: str = Query(default="active", description="新鲜度过滤"),
    min_confidence: float = Query(default=0.6, description="最低置信度"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量上限"),
):
    """查询 L3 知识 (§3.10)。"""
    writer: L3Writer = request.app.state.writer
    payloads: dict[str, dict] = request.app.state.knowledge_payloads

    # 按新鲜度获取项目知识
    if freshness == FreshnessStatus.ACTIVE.value:
        items = writer.query_active(project_id)
    else:
        items = [k for k in writer.get_all() if k.project_id == project_id]

    # 类型过滤
    if knowledge_types:
        type_set = set(knowledge_types.split(","))
        items = [k for k in items if k.knowledge_type.value in type_set]

    # 新鲜度过滤（非 active 时按指定值过滤）
    if freshness != FreshnessStatus.ACTIVE.value:
        try:
            freshness_enum = FreshnessStatus(freshness)
        except ValueError as err:
            raise _http_error(
                400,
                "INVALID_FRESHNESS",
                f"不支持的新鲜度: {freshness}",
                {"valid": [e.value for e in FreshnessStatus]},
            ) from err
        items = [k for k in items if k.freshness == freshness_enum]

    # 置信度过滤
    items = [k for k in items if k.confidence.confidence_score >= min_confidence]

    total = len(items)
    page = items[:limit]

    return KnowledgeQueryResponse(
        items=[KnowledgeQueryItem(**_knowledge_to_dict(k, payloads)) for k in page],
        total=total,
    )


@app.get("/internal/v2/memory/query")
async def memory_query(
    project_id: str = Query(..., description="项目 ID"),
    query: str = Query(..., description="查询文本"),
    knowledge_types: str | None = Query(None, description="知识类型，逗号分隔"),
    top_k: int = Query(10, description="返回数量"),
):
    """查询项目记忆/知识 (I-01 §8.1)。"""
    try:
        writer: L3Writer = app.state.writer
        types_list = knowledge_types.split(",") if knowledge_types else None

        # 使用 writer 的现有方法查询知识
        all_knowledge = writer.query_active(project_id)

        # 按类型过滤
        if types_list:
            all_knowledge = [k for k in all_knowledge if k.knowledge_type.value in types_list]

        # 简单的内存查询：返回所有符合条件的知识
        results = all_knowledge[:top_k]

        items = []
        for r in results:
            items.append(
                {
                    "knowledge_id": r.id,
                    "project_id": project_id,
                    "knowledge_type": r.knowledge_type.value,
                    "topic": r.topic if hasattr(r, "topic") else "",
                    "content": r.content if hasattr(r, "content") else "",
                    "confidence": r.confidence.confidence_score,
                    "freshness": r.freshness.value,
                    "created_at": _iso(r.created_at),
                    "updated_at": _iso(r.updated_at),
                }
            )
        # I-01 §8.1：按知识类型分组返回
        grouped: dict[str, list] = {"project_id": project_id}
        for item in items:
            grouped.setdefault(item["knowledge_type"], []).append(item)
        return grouped
    except Exception as e:
        logger.warning("知识查询失败: project=%s, query=%s, error=%s", project_id, query, e)
        return {"project_id": project_id}


# ── entity_links CRUD ──────────────────────────────────────────

@app.post("/internal/v2/links/create")
async def create_link(req: EntityLinkCreate, request: Request):
    """创建一条实体链接。"""
    from reqradar.kernel.models import EntityLink as EntityLinkModel

    session = request.app.state.sync_db_session_factory()
    try:
        db_link = EntityLinkModel(
            id=str(uuid4()),
            project_id=req.project_id,
            source_layer=req.source_layer,
            source_type=req.source_type,
            source_id=req.source_id,
            target_layer=req.target_layer,
            target_type=req.target_type,
            target_id=req.target_id,
            relation_type=req.relation_type,
            confidence=req.confidence if req.confidence is not None else 0.5,
            source_session_id=req.source_session_id,
            evidence=req.evidence,
        )
        session.add(db_link)
        session.commit()
        return {"status": "ok", "id": db_link.id}
    finally:
        session.close()


@app.get("/internal/v2/links/query")
async def query_links(
    project_id: str,
    source_type: str | None = None,
    source_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    relation_type: str | None = None,
    request: Request = None,
):
    """条件查询实体链接。"""
    from reqradar.kernel.models import EntityLink as EntityLinkModel

    session = request.app.state.sync_db_session_factory()
    try:
        q = session.query(EntityLinkModel).filter(
            EntityLinkModel.project_id == project_id,
            ~EntityLinkModel.is_stale,
        )
        if source_type:
            q = q.filter(EntityLinkModel.source_type == source_type)
        if source_id:
            q = q.filter(EntityLinkModel.source_id == source_id)
        if target_type:
            q = q.filter(EntityLinkModel.target_type == target_type)
        if target_id:
            q = q.filter(EntityLinkModel.target_id == target_id)
        if relation_type:
            q = q.filter(EntityLinkModel.relation_type == relation_type)
        results = q.all()
        return {"items": [_entity_link_to_dict(r) for r in results], "total": len(results)}
    finally:
        session.close()


@app.get("/internal/v2/links/neighbors")
async def get_neighbors(
    project_id: str,
    node_type: str,
    node_id: str,
    request: Request = None,
):
    """获取指定节点的邻域链接。"""
    from sqlalchemy import or_

    from reqradar.kernel.models import EntityLink as EntityLinkModel

    session = request.app.state.sync_db_session_factory()
    try:
        direct = session.query(EntityLinkModel).filter(
            EntityLinkModel.project_id == project_id,
            ~EntityLinkModel.is_stale,
            or_(
                (EntityLinkModel.source_type == node_type) & (EntityLinkModel.source_id == node_id),
                (EntityLinkModel.target_type == node_type) & (EntityLinkModel.target_id == node_id),
            ),
        ).all()
        return {"items": [_entity_link_to_dict(r) for r in direct], "total": len(direct)}
    finally:
        session.close()


@app.put("/internal/v2/links/stale")
async def mark_stale(link_id: str, request: Request):
    """标记链接为 stale。"""
    from reqradar.kernel.models import EntityLink as EntityLinkModel

    session = request.app.state.sync_db_session_factory()
    try:
        link = session.query(EntityLinkModel).filter_by(id=link_id).first()
        if not link:
            raise HTTPException(404, "Link not found")
        link.is_stale = True
        session.commit()
        return {"status": "ok"}
    finally:
        session.close()


# ── Graph 端点 ──────────────────────────────────────────────


@app.get("/internal/v2/graph/neighbors")
async def graph_neighbors(
    project_id: str = Query(...), node_id: str = Query(...), depth: int = Query(1),
    db: AsyncSession = Depends(get_db) # noqa: B008
):
    """查询知识图谱节点邻居 (I-01 §8)。"""
    from sqlalchemy import or_

    from reqradar.kernel.models import CodeDependency, CodeModule

    # 获取节点本身
    node = await db.execute(select(CodeModule).where(CodeModule.id == node_id))
    node = node.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    neighbors = []
    visited = {node_id}
    queue = [(node_id, 0)] # (current_id, current_depth)

    while queue:
        current_id, current_depth = queue.pop(0)
        if current_depth >= depth:
            continue

        # 获取直接相连的依赖
        deps = await db.execute(
            select(CodeDependency).where(
                CodeDependency.project_id == project_id,
                or_(
                    CodeDependency.source_module_id == current_id,
                    CodeDependency.target_module_id == current_id
                )
            )
        )
        deps = deps.scalars().all()

        for dep in deps:
            next_id = dep.target_module_id if dep.source_module_id == current_id else dep.source_module_id
            if next_id not in visited:
                visited.add(next_id)
                neighbor_node = await db.execute(select(CodeModule).where(CodeModule.id == next_id))
                neighbor_node = neighbor_node.scalars().first()
                if neighbor_node:
                    neighbors.append({
                        "id": str(neighbor_node.id),
                        "name": neighbor_node.short_name,
                        "type": neighbor_node.module_type,
                        "file_path": neighbor_node.file_path,
                        "relationship": dep.dep_type
                    })
                    queue.append((next_id, current_depth + 1))

    return {
        "project_id": project_id,
        "node_id": node_id,
        "node_name": node.short_name,
        "neighbors": neighbors
    }


@app.get("/internal/v2/graph/path")
async def graph_path(
    project_id: str = Query(...), source_id: str = Query(...), target_id: str = Query(...),
    db: AsyncSession = Depends(get_db) # noqa: B008
):
    """查询两节点间路径 (I-01 §8)。"""
    from collections import deque

    from sqlalchemy import or_

    from reqradar.kernel.models import CodeDependency, CodeModule

    # 验证起始节点和目标节点存在
    source_node = await db.execute(select(CodeModule).where(CodeModule.id == source_id))
    source_node = source_node.scalars().first()
    target_node = await db.execute(select(CodeModule).where(CodeModule.id == target_id))
    target_node = target_node.scalars().first()

    if not source_node or not target_node:
        raise HTTPException(status_code=404, detail="起始或目标节点不存在")

    # BFS 查找最短路径
    # parent_map: child_id -> parent_id
    parent_map = {source_id: None}
    queue = deque([source_id])
    found = False

    while queue and not found:
        current_id = queue.popleft()

        if current_id == target_id:
            found = True
            break

        deps = await db.execute(
            select(CodeDependency).where(
                CodeDependency.project_id == project_id,
                or_(
                    CodeDependency.source_module_id == current_id,
                    CodeDependency.target_module_id == current_id
                )
            )
        )
        deps = deps.scalars().all()

        for dep in deps:
            next_id = dep.target_module_id if dep.source_module_id == current_id else dep.source_module_id
            if next_id not in parent_map:
                parent_map[next_id] = current_id
                queue.append(next_id)

    if not found:
        return {"project_id": project_id, "source_id": source_id, "target_id": target_id, "path": []}

    # 回溯路径
    path = []
    curr = target_id
    while curr is not None:
        node = await db.execute(select(CodeModule).where(CodeModule.id == curr))
        node = node.scalars().first()
        if node:
            path.append({
                "id": str(node.id),
                "name": node.short_name,
                "type": node.module_type,
                "file_path": node.file_path
            })
        curr = parent_map.get(curr)

    path.reverse()
    return {
        "project_id": project_id,
        "source_id": source_id,
        "target_id": target_id,
        "path": path
    }


@app.get("/internal/v2/graph/subgraph")
async def graph_subgraph(
    project_id: str = Query(...), center_id: str = Query(...), radius: int = Query(2),
    db: AsyncSession = Depends(get_db) # noqa: B008
):
    """查询子图 (I-01 §8)。"""
    from sqlalchemy import or_

    from reqradar.kernel.models import CodeDependency, CodeModule

    # 获取中心节点
    center_node = await db.execute(select(CodeModule).where(CodeModule.id == center_id))
    center_node = center_node.scalars().first()
    if not center_node:
        raise HTTPException(status_code=404, detail="中心节点不存在")

    nodes = []
    edges = []
    visited_nodes = {center_id}
    queue = [(center_id, 0)] # (current_id, current_depth)

    # 先添加中心节点
    nodes.append({
        "id": str(center_node.id),
        "name": center_node.short_name,
        "type": center_node.module_type,
        "file_path": center_node.file_path,
        "is_center": True
    })

    while queue:
        current_id, current_depth = queue.pop(0)
        if current_depth >= radius:
            continue

        deps = await db.execute(
            select(CodeDependency).where(
                CodeDependency.project_id == project_id,
                or_(
                    CodeDependency.source_module_id == current_id,
                    CodeDependency.target_module_id == current_id
                )
            )
        )
        deps = deps.scalars().all()

        for dep in deps:
            # 添加边
            edges.append({
                "source": str(dep.source_module_id),
                "target": str(dep.target_module_id),
                "type": dep.dep_type
            })

            next_id = dep.target_module_id if dep.source_module_id == current_id else dep.source_module_id
            if next_id not in visited_nodes:
                visited_nodes.add(next_id)
                next_node = await db.execute(select(CodeModule).where(CodeModule.id == next_id))
                next_node = next_node.scalars().first()
                if next_node:
                    nodes.append({
                        "id": str(next_node.id),
                        "name": next_node.short_name,
                        "type": next_node.module_type,
                        "file_path": next_node.file_path,
                        "is_center": False
                    })
                    queue.append((next_id, current_depth + 1))

    return {
        "project_id": project_id,
        "center_id": center_id,
        "nodes": nodes,
        "edges": edges
    }
