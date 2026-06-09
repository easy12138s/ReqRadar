"""Ingestion Service — 文档/代码/Git 数据摄取服务。

将原始数据转化为 L1 结构化事实，直接写入 PostgreSQL 和 ChromaDB。

端点：
  POST /internal/v2/ingest/document  — 文档摄取 (multipart/form-data)
  POST /internal/v2/ingest/code      — 代码摄取 (JSON)
  POST /internal/v2/ingest/git       — Git 历史摄取 (JSON)
  GET  /health                       — 健康检查
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.ingestion.chunking.chunker import MarkdownChunker
from reqradar.ingestion.parsers.code_parser import CodeParser
from reqradar.ingestion.parsers.document_parser import DocumentParser
from reqradar.ingestion.parsers.git_parser import GitParser
from reqradar.ingestion.vectorizer import IngestionVectorizer, VectorizeInput

logger = logging.getLogger(__name__)

_start_time: float = 0.0
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "change-me-to-a-random-internal-key")


# ── Pydantic 模型 ───────────────────────────────────────────────────────


class IngestCodeRequest(BaseModel):
    """代码摄取请求。"""

    project_id: str = Field(description="项目 ID")
    repo_path: str = Field(description="代码仓库路径")


class IngestGitRequest(BaseModel):
    """Git 摄取请求。"""

    project_id: str = Field(description="项目 ID")
    repo_path: str = Field(description="Git 仓库路径")
    max_commits: int = Field(default=500, description="最大提交数")


class IngestResponse(BaseModel):
    """摄取响应。"""

    raw_context_id: str = Field(description="L0 原始上下文 ID")
    items_count: int = Field(description="摄取条目数")
    embedding_ids: list[str] | None = Field(default=None, description="向量 ID 列表")


# ── 应用生命周期 ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """初始化/清理服务资源。"""
    global _start_time
    _start_time = time.time()
    logger.info("Ingestion Service 启动 (port 8007)")

    database_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./reqradar_dev.db")
    from reqradar.kernel.database import create_engine, create_session_factory

    engine = create_engine(database_url)
    app.state.db_session_factory = create_session_factory(engine)

    chromadb_path = os.environ.get("CHROMADB_PATH", ".reqradar/vectorstore")
    app.state.vectorizer = IngestionVectorizer(
        persist_directory=chromadb_path,
        use_onnx=True,
    )

    l0_storage = os.environ.get("L0_STORAGE_PATH", "data/l0")
    app.state.l0_storage_path = Path(l0_storage)

    logger.info("Ingestion Service 就绪: DB=%s, ChromaDB=%s", database_url[:50], chromadb_path)

    yield

    await engine.dispose()
    logger.info("Ingestion Service 关闭")


# ── FastAPI App ─────────────────────────────────────────────────────────


app = FastAPI(
    title="ReqRadar Ingestion Service",
    version="2.0.0",
    lifespan=lifespan,
)


# ── 中间件 ──────────────────────────────────────────────────────────────


@app.middleware("http")
async def verify_internal_api_key(request: Request, call_next):
    """内部 API Key 验证中间件。"""
    if request.url.path == "/health":
        return await call_next(request)

    api_key = request.headers.get("X-Internal-API-Key", "")
    if api_key != INTERNAL_API_KEY:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "缺少或无效的 X-Internal-API-Key",
                }
            },
        )
    return await call_next(request)


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": exc.detail}},
    )


# ── DB 依赖 ─────────────────────────────────────────────────────────────


async def get_db_session(request: Request) -> AsyncSession:
    """获取数据库会话。"""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]


# ── Health ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """本地健康检查。"""
    return {
        "status": "ok",
        "service": "ingestion",
        "uptime_seconds": int(time.time() - _start_time),
    }


# ── 摄取端点 ────────────────────────────────────────────────────────────


@app.post("/internal/v2/ingest/document")
async def ingest_document(
    session: DBSession,
    request: Request,
    project_id: str = Form(description="项目 ID"),
    file: UploadFile | None = None,
):
    """文档摄取 — 解析 → 切分 → 向量化 → PG 写入。

    支持格式: .md, .txt, .pdf, .docx, .html 等 (markitdown)
    """
    from reqradar.kernel.models import Chunk, RawContext

    if file is None:
        raise HTTPException(status_code=400, detail="请上传文档文件")

    project_uuid = UUID(project_id)

    vectorizer: IngestionVectorizer = request.app.state.vectorizer
    l0_path: Path = request.app.state.l0_storage_path

    # 1. 保存原始文件到 L0
    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()
    filename = file.filename or "document"

    raw_dir = l0_path / project_id / datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / filename
    raw_file.write_bytes(content)

    # 2. 注册 raw_context 元数据
    raw_id = uuid4()
    raw_context = RawContext(
        id=raw_id,
        project_id=project_uuid,
        type="document",
        uri=str(raw_file),
        original_filename=filename,
        size_bytes=len(content),
        content_hash=content_hash,
        source="upload",
    )
    session.add(raw_context)

    # 3. 解析文档
    parser = DocumentParser()
    markdown_text = parser.parse_file(raw_file)

    # 4. 切分
    chunker = MarkdownChunker()
    chunk_datas = chunker.chunk(markdown_text)

    # 5. 向量化（失败时降级，embedding_id 留空，后续可补索引）
    embedding_ids: list[str] = []
    try:
        vector_inputs = [
            VectorizeInput(
                id=str(uuid4()),
                content=cd.content,
                metadata={
                    "project_id": str(project_uuid),
                    "chunk_type": cd.chunk_type,
                    "section_path": cd.section_path or "",
                },
            )
            for cd in chunk_datas
        ]
        embedding_ids = vectorizer.vectorize_chunks(vector_inputs)
    except Exception as e:
        logger.warning("向量化失败（降级跳过）: %s", e)

    # 6. 写入 chunks 表
    for i, cd in enumerate(chunk_datas):
        chunk = Chunk(
            id=uuid4(),
            project_id=project_uuid,
            raw_context_id=raw_id,
            chunk_type=cd.chunk_type,
            content=cd.content,
            text_uri=str(raw_file),
            position=cd.position,
            offset_start=cd.offset_start,
            offset_end=cd.offset_end,
            section_path=cd.section_path,
            embedding_id=embedding_ids[i] if i < len(embedding_ids) else None,
        )
        session.add(chunk)

    await session.commit()

    return IngestResponse(
        raw_context_id=str(raw_id),
        items_count=len(chunk_datas),
        embedding_ids=embedding_ids,
    )


@app.post("/internal/v2/ingest/code")
async def ingest_code(
    req: IngestCodeRequest,
    session: DBSession,
    request: Request,
):
    """代码摄取 — AST 解析 → 向量化 → PG 写入。"""
    from reqradar.kernel.models import CodeModule, RawContext

    project_uuid = UUID(req.project_id)
    vectorizer: IngestionVectorizer = request.app.state.vectorizer

    repo_path = Path(req.repo_path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"路径不存在: {req.repo_path}")

    # 1. 注册 raw_context
    raw_id = uuid4()
    raw_context = RawContext(
        id=raw_id,
        project_id=project_uuid,
        type="repo_snapshot",
        uri=str(repo_path),
        original_filename=repo_path.name,
        size_bytes=0,
        content_hash="",
        source="cli",
    )
    session.add(raw_context)

    # 2. 解析代码
    parser = CodeParser()
    modules = parser.parse_directory(repo_path)

    # 3. 向量化（失败时降级）
    embedding_ids: list[str] = []
    try:
        vector_inputs = [
            VectorizeInput(
                id=str(uuid4()),
                content=f"{m.signature or m.short_name}\n{m.docstring or ''}",
                metadata={
                    "project_id": str(project_uuid),
                    "module_type": m.module_type,
                    "qualified_name": m.qualified_name,
                    "file_path": m.file_path,
                    "line_start": m.line_start,
                },
            )
            for m in modules
        ]
        embedding_ids = vectorizer.vectorize_code_modules(vector_inputs)
    except Exception as e:
        logger.warning("代码向量化失败（降级跳过）: %s", e)

    # 4. 写入 code_modules 表
    for i, m in enumerate(modules):
        code_mod = CodeModule(
            id=uuid4(),
            project_id=project_uuid,
            module_type=m.module_type,
            qualified_name=m.qualified_name,
            short_name=m.short_name,
            file_path=m.file_path,
            line_start=m.line_start,
            line_end=m.line_end,
            signature=m.signature,
            docstring=m.docstring,
            embedding_id=embedding_ids[i] if i < len(embedding_ids) else None,
        )
        session.add(code_mod)

    await session.commit()

    return IngestResponse(
        raw_context_id=str(raw_id),
        items_count=len(modules),
        embedding_ids=embedding_ids,
    )


@app.post("/internal/v2/ingest/git")
async def ingest_git(
    req: IngestGitRequest,
    session: DBSession,
    request: Request,
):
    """Git 历史摄取 — git log 解析 → PG 写入。"""
    from reqradar.kernel.models import GitCommit, RawContext

    project_uuid = UUID(req.project_id)
    repo_path = Path(req.repo_path)
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        raise HTTPException(status_code=400, detail=f"不是 Git 仓库: {req.repo_path}")

    # 1. 注册 raw_context
    raw_id = uuid4()
    raw_context = RawContext(
        id=raw_id,
        project_id=project_uuid,
        type="git_history",
        uri=str(repo_path),
        size_bytes=0,
        content_hash="",
        source="cli",
    )
    session.add(raw_context)

    # 2. 解析 Git 历史
    parser = GitParser()
    commits = parser.parse_repo(repo_path, max_commits=req.max_commits)

    # 3. 写入 git_commits 表
    for c in commits:
        git_commit = GitCommit(
            id=uuid4(),
            project_id=project_uuid,
            commit_hash=c.commit_hash,
            author=c.author,
            author_email=c.author_email,
            committed_at=c.committed_at,
            message=c.message,
            changed_files=c.changed_files or [],
        )
        session.add(git_commit)

    await session.commit()

    return IngestResponse(
        raw_context_id=str(raw_id),
        items_count=len(commits),
    )
