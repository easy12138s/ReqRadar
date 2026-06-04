"""Index Service — 向量检索 + Checkpoint 存储 + L3 知识管理。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Index Service 启动")
    yield
    logger.info("Index Service 关闭")


app = FastAPI(
    title="ReqRadar Index Service",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "index"}


@app.post("/internal/v2/checkpoints")
async def create_checkpoint():
    """创建 Checkpoint。"""
    return {"checkpoint_id": "stub", "version": 1}


@app.get("/internal/v2/checkpoints/{session_id}")
async def get_checkpoints(session_id: str):
    """查询 Checkpoint。"""
    return {"session_id": session_id, "checkpoints": []}


@app.post("/internal/v2/vector/search")
async def search_vector():
    """向量检索。"""
    return {"results": []}


@app.post("/internal/v2/knowledge")
async def create_knowledge():
    """创建 L3 知识。"""
    return {"knowledge_id": "stub"}


@app.get("/internal/v2/knowledge/{project_id}")
async def get_knowledge(project_id: str):
    """查询项目 L3 知识。"""
    return {"project_id": project_id, "knowledge": []}
