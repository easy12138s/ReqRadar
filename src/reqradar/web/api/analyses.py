import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    WebSocket,
    WebSocketDisconnect,
    Query,
    status,
)
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import CurrentUser, DbSession, get_current_user, get_db
from reqradar.web.models import AnalysisTask, Project, RequirementDocument, UploadedFile, User
from reqradar.web.api.auth import SECRET_KEY, ALGORITHM
from reqradar.web.enums import TaskStatus
from reqradar.web.websocket import manager as ws_manager
from reqradar.infrastructure.config import load_config

logger = logging.getLogger("reqradar.web.api.analyses")

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
}


class AnalysisSubmit(BaseModel):
    project_id: int
    requirement_name: Optional[str] = None
    requirement_text: Optional[str] = None
    text: Optional[str] = None
    title: Optional[str] = None
    depth: str = "standard"
    template_id: Optional[int] = None
    focus_areas: Optional[list[str]] = None
    requirement_document_id: Optional[int] = None

    def get_name(self) -> str:
        return (
            self.requirement_name
            or self.title
            or f"Analysis-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )

    def get_text(self) -> str:
        return self.requirement_text or self.text or ""


class AnalysisResponse(BaseModel):
    id: int
    project_id: int
    project_name: Optional[str] = None
    user_id: int
    requirement_name: str
    requirement_text: str
    status: str
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisDetailResponse(AnalysisResponse):
    step_summary: Optional[dict] = None


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def submit_analysis(req: AnalysisSubmit, current_user: CurrentUser, db: DbSession):
    result = await db.execute(select(Project).where(Project.id == req.project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    from reqradar.infrastructure.config_manager import ConfigManager
    from reqradar.modules.llm_connectivity import is_llm_reachable

    cm = ConfigManager(db, load_config())
    provider = await cm.get_str(
        "llm.provider", user_id=current_user.id, project_id=req.project_id, default="openai"
    )
    api_key = await cm.get_str(
        "llm.api_key", user_id=current_user.id, project_id=req.project_id, default=""
    )
    base_url = await cm.get_str(
        "llm.base_url",
        user_id=current_user.id,
        project_id=req.project_id,
        default="https://api.openai.com/v1",
    )
    if provider == "openai" and not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM API Key 未配置，请先在设置页面配置大模型",
        )
    connectivity = is_llm_reachable(provider, api_key, base_url)
    if connectivity is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM 连接不通，请检查设置页面的 API 配置并使用「测试连接」按钮验证",
        )

    requirement_text = req.get_text()

    if req.requirement_document_id:
        doc = (
            await db.execute(
                select(RequirementDocument).where(
                    RequirementDocument.id == req.requirement_document_id
                )
            )
        ).scalar_one_or_none()
        if doc:
            requirement_text = doc.consolidated_text or requirement_text

    task = AnalysisTask(
        project_id=req.project_id,
        user_id=current_user.id,
        requirement_name=req.get_name(),
        requirement_text=requirement_text,
        depth=req.depth,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    config = load_config()
    asyncio.create_task(_run_analysis_background(task.id, project, config))

    return task


@router.post("/upload", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def submit_analysis_upload(
    project_id: int = Form(...),
    requirement_name: str = Form(default=""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        )

    content = await file.read()

    config = load_config()
    max_upload_bytes = config.web.max_upload_size * 1024 * 1024
    if len(content) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({len(content)} bytes) exceeds limit ({config.web.max_upload_size}MB)",
        )

    from reqradar.web.services.project_file_service import ProjectFileService

    file_svc = ProjectFileService(config.web)
    upload_dir = str(file_svc.get_requirements_path(project.name))
    os.makedirs(upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(upload_dir, f"{file_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

    task = AnalysisTask(
        project_id=project_id,
        user_id=current_user.id,
        requirement_name=requirement_name or filename.rsplit(".", 1)[0],
        requirement_text=content.decode("utf-8", errors="replace"),
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()

    db.add(
        UploadedFile(
            task_id=task.id,
            filename=file.filename or "upload",
            file_path=file_path,
            file_size=len(content),
        )
    )

    await db.commit()
    await db.refresh(task)

    asyncio.create_task(_run_analysis_background(task.id, project, config))

    return task


@router.get("", response_model=list[AnalysisResponse])
async def list_analyses(
    current_user: CurrentUser,
    db: DbSession,
    project_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
):
    query = select(AnalysisTask).where(AnalysisTask.user_id == current_user.id)
    if project_id is not None:
        query = query.where(AnalysisTask.project_id == project_id)
    if status_filter is not None:
        query = query.where(AnalysisTask.status == status_filter)
    query = query.order_by(AnalysisTask.created_at.desc())
    tasks = (await db.execute(query)).scalars().all()

    project_ids = {t.project_id for t in tasks}
    projects = {}
    if project_ids:
        proj_result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        for p in proj_result.scalars().all():
            projects[p.id] = p.name

    return [
        {
            "id": t.id,
            "project_id": t.project_id,
            "project_name": projects.get(t.project_id, "Unknown"),
            "user_id": t.user_id,
            "requirement_name": t.requirement_name,
            "requirement_text": t.requirement_text,
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "error_message": t.error_message,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.get("/{task_id}", response_model=AnalysisDetailResponse)
async def get_analysis(task_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis task not found")

    step_summary = None
    if task.context_json:
        try:
            ctx = task.context_json
            step_results = ctx.get("step_results", {})
            step_summary = {
                name: {
                    "success": r.get("success", False),
                    "confidence": r.get("confidence", 0.0),
                }
                for name, r in step_results.items()
            }
        except AttributeError:
            pass

    response = AnalysisDetailResponse.model_validate(task)
    response.step_summary = step_summary
    return response


@router.post("/{task_id}/retry", response_model=AnalysisResponse)
async def retry_analysis(task_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis task not found")

    if task.status not in (TaskStatus.FAILED, TaskStatus.COMPLETED, TaskStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed, completed, or cancelled tasks",
        )

    proj_result = await db.execute(select(Project).where(Project.id == task.project_id))
    project = proj_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task.status = TaskStatus.PENDING
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    task.context_json = {}
    await db.commit()
    await db.refresh(task)

    config = load_config()
    asyncio.create_task(_run_analysis_background(task.id, project, config))

    return task


@router.post("/{task_id}/cancel")
async def cancel_analysis(task_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise HTTPException(status_code=400, detail=f"Cannot cancel task in status: {task.status}")
    from reqradar.web.services.analysis_runner import runner

    runner.cancel(task_id)
    task.status = TaskStatus.CANCELLED
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "status": "cancelled"}


@router.websocket("/{task_id}/ws")
async def analysis_websocket(websocket: WebSocket, task_id: int, token: str = Query(...)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    session_factory = websocket.app.state.session_factory
    async with session_factory() as db:
        result = await db.execute(
            select(AnalysisTask).where(
                AnalysisTask.id == task_id,
                AnalysisTask.user_id == user_id,
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            await websocket.close(code=4003, reason="Task not found or access denied")
            return

    ws_manager.subscribe(task_id, websocket)

    try:
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.unsubscribe(task_id, websocket)


async def _run_analysis_background(task_id: int, project: Project, config):
    from reqradar.web.services.analysis_runner import runner

    runner.submit(task_id, project, config)
