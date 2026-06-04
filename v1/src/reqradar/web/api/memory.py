import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import AnalysisTask, Project

logger = logging.getLogger("reqradar.web.api.memory")


def _get_project_memory(project: Project, request: Request) -> "ProjectMemory":
    from reqradar.modules.project_memory import ProjectMemory

    memories_path = request.app.state.paths["memories"]
    return ProjectMemory(storage_path=str(memories_path), project_id=project.id)


router = APIRouter(prefix="/api/projects", tags=["memory"])


class TermItem(BaseModel):
    term: str
    definition: str = ""
    domain: str = ""


class ModuleItem(BaseModel):
    name: str
    responsibility: str = ""
    key_classes: list[str] = []


class ContributorItem(BaseModel):
    name: str
    role: str = ""
    files: list[str] = []


class HistoryItem(BaseModel):
    requirement_id: str
    timestamp: str = ""
    risk_level: str = ""
    summary: str = ""


@router.get("/{project_id}/terminology", response_model=list[TermItem])
async def get_terminology(
    project_id: int, current_user: CurrentUser, db: DbSession, request: Request
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    memory = _get_project_memory(project, request)
    data = memory.load()
    terms = data.get("terms", [])
    return [
        TermItem(
            term=t.get("term", ""),
            definition=t.get("definition", ""),
            domain=t.get("domain", ""),
        )
        for t in terms
    ]


@router.get("/{project_id}/modules", response_model=list[ModuleItem])
async def get_modules(project_id: int, current_user: CurrentUser, db: DbSession, request: Request):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    memory = _get_project_memory(project, request)
    data = memory.load()
    modules = data.get("modules", [])
    return [
        ModuleItem(
            name=m.get("name", ""),
            responsibility=m.get("responsibility", ""),
            key_classes=m.get("key_classes", []),
        )
        for m in modules
    ]


@router.get("/{project_id}/team", response_model=list[ContributorItem])
async def get_team(project_id: int, current_user: CurrentUser, db: DbSession, request: Request):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return []


@router.get("/{project_id}/history", response_model=list[HistoryItem])
async def get_history(project_id: int, current_user: CurrentUser, db: DbSession, request: Request):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task_result = await db.execute(
        select(AnalysisTask)
        .where(AnalysisTask.project_id == project_id, AnalysisTask.user_id == current_user.id)
        .order_by(AnalysisTask.created_at.desc())
    )
    tasks = list(task_result.scalars().all())

    history = []
    for task in tasks:
        risk_level = "unknown"
        summary = ""
        if task.context_json:
            try:
                ctx = task.context_json
                deep = ctx.get("deep_analysis")
                if deep and isinstance(deep, dict):
                    risk_level = deep.get("risk_level", "unknown")
                understanding = ctx.get("understanding")
                if understanding and isinstance(understanding, dict):
                    summary = understanding.get("summary", "")
            except AttributeError:
                pass

        history.append(
            HistoryItem(
                requirement_id=task.requirement_name,
                timestamp=task.created_at.isoformat() if task.created_at else "",
                risk_level=risk_level,
                summary=summary,
            )
        )

    return history
