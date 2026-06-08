"""Output Service — 报告生成 + 版本管理 + 模板热更新。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from reqradar.kernel.enums import TaskStatus

logger = logging.getLogger(__name__)

_start_time: float = 0.0
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")


class _OutputLLMClient:
    """output-service 内部 LLM 客户端，不依赖 cognitive_rt。"""

    def __init__(self) -> None:
        self._api_key = os.environ.get("LLM_API_KEY", "")
        self._model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self._base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str | None:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                },
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content")

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """报告生成请求（I-01 §4.1）。"""

    session_id: str = Field(description="Session ID")
    template_id: str | None = Field(default=None, description="模板 ID，null 使用默认模板")
    output_format: str = Field(default="markdown", description="输出格式（markdown/html/json）")


class GenerateResponse(BaseModel):
    """报告生成响应（I-01 §4.1）。"""

    task_id: str = Field(description="任务 ID")
    status: str = Field(description="任务状态")
    estimated_duration_ms: int = Field(description="预估耗时（毫秒）")


class TaskStatusResponse(BaseModel):
    """任务状态响应（I-01 §4.2）。"""

    task_id: str = Field(description="任务 ID")
    status: str = Field(description="任务状态")
    output_uri: str | None = Field(default=None, description="报告输出 URI")
    format: str | None = Field(default=None, description="输出格式")
    size_bytes: int | None = Field(default=None, description="报告大小（字节）")
    completed_at: str | None = Field(default=None, description="完成时间")


class LatestReportResponse(BaseModel):
    """最新报告响应（I-01 §9.1）。"""

    session_id: str = Field(description="Session ID")
    output_uri: str | None = Field(default=None, description="报告 URI")
    format: str | None = Field(default=None, description="输出格式")
    size_bytes: int | None = Field(default=None, description="大小")
    generated_at: str | None = Field(default=None, description="生成时间")


# ---------------------------------------------------------------------------
# 内存任务存储
# ---------------------------------------------------------------------------


@dataclass
class ReportTask:
    """报告生成任务。"""

    task_id: str
    session_id: str
    status: str = TaskStatus.PENDING.value
    output_format: str = "markdown"
    template_id: str | None = None
    output_uri: str | None = None
    content: str = ""
    size_bytes: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str = ""


class TaskStore:
    """任务存储（内存模式，P2 后迁移到 PG）。"""

    def __init__(self) -> None:
        self._tasks: dict[str, ReportTask] = {}
        self._session_tasks: dict[str, list[str]] = {}

    def clear(self) -> None:
        self._tasks.clear()
        self._session_tasks.clear()

    def create(
        self, session_id: str, output_format: str = "markdown", template_id: str | None = None
    ) -> ReportTask:
        task = ReportTask(
            task_id=str(uuid4()),
            session_id=session_id,
            output_format=output_format,
            template_id=template_id,
        )
        self._tasks[task.task_id] = task
        if session_id not in self._session_tasks:
            self._session_tasks[session_id] = []
        self._session_tasks[session_id].append(task.task_id)
        return task

    def get(self, task_id: str) -> ReportTask | None:
        return self._tasks.get(task_id)

    def get_latest_for_session(self, session_id: str) -> ReportTask | None:
        task_ids = self._session_tasks.get(session_id, [])
        if not task_ids:
            return None
        for tid in reversed(task_ids):
            task = self._tasks.get(tid)
            if task and task.status == TaskStatus.COMPLETED.value:
                return task
        return None


# ---------------------------------------------------------------------------
# 报告生成器
# ---------------------------------------------------------------------------


class ReportGenerator:
    """报告生成器 — LLM 驱动的报告生成，模板作为降级方案。"""

    def __init__(
        self,
        template_dir: str | Path | None = None,
        llm_client: Any | None = None,
        service_url: str = "",
        internal_api_key: str = "",
    ) -> None:
        self._template_dir = Path(template_dir) if template_dir else None
        self._templates: dict[str, str] = {}
        self._llm_client = llm_client
        self._service_url = service_url or os.environ.get(
            "COGNITIVE_RT_URL", "http://localhost:8002"
        )
        self._internal_api_key = internal_api_key or os.environ.get("INTERNAL_API_KEY", "")

    @property
    def template_count(self) -> int:
        return len(self._templates)

    def load_templates(self) -> int:
        if self._template_dir and self._template_dir.exists():
            for f in self._template_dir.glob("*.md.j2"):
                try:
                    self._templates[f.stem] = f.read_text(encoding="utf-8")
                    logger.info("模板加载: %s", f.name)
                except Exception as e:
                    logger.warning("模板加载失败: %s: %s", f.name, e)
        return len(self._templates)

    async def generate(
        self,
        session_id: str,
        template_id: str | None = None,
        output_format: str = "markdown",
    ) -> str:
        try:
            session_data, events, evidence = await self._fetch_session_data(session_id)
            if self._llm_client and session_data:
                return await self._generate_with_llm(
                    session_id, session_data, events, evidence, output_format
                )
        except Exception as e:
            logger.warning("LLM 报告生成失败，降级到模板: %s", e)

        return self._generate_from_template(session_id, template_id, output_format)

    async def _fetch_session_data(
        self, session_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        headers = {"X-Internal-API-Key": self._internal_api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            session_resp = await client.get(
                f"{self._service_url}/internal/v2/sessions/{session_id}",
                headers=headers,
            )
            session_resp.raise_for_status()
            session_data = session_resp.json()

            events_resp = await client.get(
                f"{self._service_url}/internal/v2/sessions/{session_id}/events",
                headers=headers,
                params={"limit": 200},
            )
            events_data = events_resp.json() if events_resp.status_code == 200 else {}
            events = events_data.get("events", []) if isinstance(events_data, dict) else events_data

            evidence_resp = await client.get(
                f"{self._service_url}/internal/v2/sessions/{session_id}/evidence",
                headers=headers,
            )
            evidence_data = evidence_resp.json() if evidence_resp.status_code == 200 else {}
            evidence = (
                evidence_data.get("items", []) if isinstance(evidence_data, dict) else evidence_data
            )

        return session_data, events, evidence

    async def _generate_with_llm(
        self,
        session_id: str,
        session_data: dict[str, Any],
        events: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        output_format: str,
    ) -> str:
        prompt = self._build_report_prompt(
            session_id, session_data, events, evidence, output_format
        )
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是一名资深需求分析专家。根据提供的会话数据、事件和证据，"
                    "生成一份结构清晰、内容详实的 Markdown 分析报告。"
                    "报告应包含：摘要、关键发现、风险评估、建议措施。"
                ),
            },
            {"role": "user", "content": prompt},
        ]
        result = await self._llm_client.complete(messages, temperature=0.3, max_tokens=4096)
        if not result:
            raise ValueError("LLM 返回空内容")
        return result

    def _build_report_prompt(
        self,
        session_id: str,
        session_data: dict[str, Any],
        events: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        output_format: str,
    ) -> str:
        sections: list[str] = [
            f"## 会话信息\n- Session ID: {session_id}",
            f"- 状态: {session_data.get('status', 'unknown')}",
            f"- 创建时间: {session_data.get('created_at', 'N/A')}",
        ]

        if events:
            event_lines = []
            for e in events[:50]:
                etype = e.get("event_type", e.get("type", "?"))
                payload = e.get("payload", {})
                seq = e.get("sequence", "?")
                detail = payload.get("summary", payload.get("detail", payload.get("step", "")))
                event_lines.append(f"- [{seq}] {etype}: {detail}")
            sections.append("## 事件记录\n" + "\n".join(event_lines))

        if evidence:
            evidence_lines = []
            for ev in evidence[:30]:
                etype = ev.get("evidence_type", ev.get("source", "?"))
                content = ev.get("content", "")
                preview = content[:200] if isinstance(content, str) else str(content)[:200]
                evidence_lines.append(f"- [{etype}] {preview}")
            sections.append("## 证据列表\n" + "\n".join(evidence_lines))

        sections.append(
            f"## 输出要求\n- 格式: {output_format}\n- 语言: 中文\n- 请生成完整的分析报告。"
        )
        return "\n\n".join(sections)

    def _generate_from_template(
        self,
        session_id: str,
        template_id: str | None = None,
        output_format: str = "markdown",
    ) -> str:
        template_content = self._templates.get(template_id or "default", "")
        if not template_content:
            template_content = self._get_default_template(session_id, output_format)

        try:
            from jinja2 import Template

            tmpl = Template(template_content)
            return tmpl.render(
                session_id=session_id,
                timestamp=datetime.now(UTC).isoformat(),
                format=output_format,
            )
        except Exception as e:
            logger.warning("模板渲染失败: %s", e)
            return template_content

    def _get_default_template(self, session_id: str, output_format: str) -> str:
        return f"# 报告\n\n会话 {session_id} 的 {output_format} 报告内容"


# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------


_task_store = TaskStore()
_report_generator: ReportGenerator | None = None
_generate_sleep_sec = 0.5


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _report_generator, _start_time
    _start_time = time.time()
    _task_store.clear()

    llm_client = _OutputLLMClient()
    _report_generator = ReportGenerator(
        template_dir=Path(__file__).parent / "templates",
        llm_client=llm_client,
    )
    logger.info("Output Service 启动")
    _report_generator.load_templates()
    yield
    await llm_client.close()
    _task_store.clear()
    logger.info("Output Service 关闭")


app = FastAPI(
    title="ReqRadar Output Service",
    version="2.0.0",
    lifespan=lifespan,
)


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


async def _run_generation(task: ReportTask) -> None:
    task.status = TaskStatus.RUNNING.value
    await asyncio.sleep(_generate_sleep_sec)
    try:
        if _report_generator is None:
            raise RuntimeError("ReportGenerator 未初始化")
        content = await _report_generator.generate(
            task.session_id,
            task.template_id,
            task.output_format,
        )
        task.content = content
        task.size_bytes = len(content.encode("utf-8"))
        task.output_uri = f"memory://reports/{task.session_id}/{task.task_id}.{task.output_format}"
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.now(UTC)
    except Exception as e:
        task.status = TaskStatus.FAILED.value
        task.error = str(e)
        logger.error("报告生成失败: %s", e)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "output", "uptime_seconds": int(time.time() - _start_time)}


@app.post("/internal/v2/reports/generate", status_code=202)
async def generate_report(req: GenerateRequest, background_tasks: BackgroundTasks):
    """请求生成报告（I-01 §4.1）— 异步，返回 task_id。"""
    task = _task_store.create(req.session_id, req.output_format, req.template_id)
    background_tasks.add_task(_run_generation, task)

    estimated = 5000 if req.output_format != "html" else 8000
    return GenerateResponse(
        task_id=task.task_id,
        status=TaskStatus.PENDING.value,
        estimated_duration_ms=estimated,
    )


@app.get("/internal/v2/reports/{task_id}/status")
async def get_report_status(task_id: str):
    """查询报告生成状态（I-01 §4.2）。"""
    task = _task_store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "TASK_NOT_FOUND", "message": f"任务不存在: {task_id}"}},
        )

    result: dict = {
        "task_id": task.task_id,
        "status": task.status,
    }
    if task.status == TaskStatus.COMPLETED.value:
        result.update(
            output_uri=task.output_uri,
            format=task.output_format,
            size_bytes=task.size_bytes,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
        )
    return result


@app.get("/internal/v2/reports/{session_id}/latest")
async def get_latest_report(session_id: str):
    """获取最新报告（I-01 §9.1，供 MCP 使用）。"""
    task = _task_store.get_latest_for_session(session_id)
    if task is None:
        return {"session_id": session_id, "reports": []}
    return {
        "session_id": session_id,
        "output_uri": task.output_uri,
        "format": task.output_format,
        "size_bytes": task.size_bytes,
        "generated_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@app.post("/internal/v2/reports/reload-templates")
async def reload_templates():
    """热更新模板（不重启服务）。"""
    if _report_generator is None:
        return {"status": "error", "message": "ReportGenerator 未初始化"}
    count = _report_generator.load_templates()
    return {"status": "ok", "templates_loaded": count}


@app.get("/internal/v2/reports/{task_id}/content")
async def get_report_content(task_id: str):
    """获取报告内容。"""
    task = _task_store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "TASK_NOT_FOUND", "message": f"任务不存在: {task_id}"}},
        )
    if task.status != TaskStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "TASK_NOT_COMPLETED", "message": f"任务未完成: {task.status}"}
            },
        )
    return {
        "task_id": task.task_id,
        "content": task.content,
    }
