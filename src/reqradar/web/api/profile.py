import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from reqradar.infrastructure.config import load_config
from reqradar.modules.pending_changes import PendingChangeManager
from reqradar.modules.project_memory import ProjectMemory
from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import Project

logger = logging.getLogger("reqradar.web.api.profile")

router = APIRouter(prefix="/api/projects", tags=["profile"])


class PendingChangeAction(BaseModel):
    action: str


class PendingChangeResponse(BaseModel):
    id: int
    change_type: str
    target_id: str
    old_value: str
    new_value: str
    diff: str
    source: str
    status: str

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    content: str
    data: dict


async def _get_project(project_id: int, user_id: int, db: DbSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _build_project_memory(project: Project) -> ProjectMemory:
    config = load_config()
    storage_path = project.repo_path or "."
    memory_path = Path(storage_path) / config.memory.project_storage_path
    return ProjectMemory(storage_path=str(memory_path), project_id=project.id)


@router.get("/{project_id}/profile", response_model=ProfileResponse)
async def get_profile(project_id: int, current_user: CurrentUser, db: DbSession):
    project = await _get_project(project_id, current_user.id, db)
    pm = _build_project_memory(project)
    data = pm.load()

    content = pm.file_path.read_text(encoding="utf-8") if pm.file_path.exists() else pm._render_markdown(data)

    return ProfileResponse(content=content, data=data)


@router.get("/{project_id}/profile/pending", response_model=list[PendingChangeResponse])
async def get_pending_changes(project_id: int, current_user: CurrentUser, db: DbSession):
    project = await _get_project(project_id, current_user.id, db)
    manager = PendingChangeManager(db)
    changes = await manager.list_pending(project.id)
    return changes


@router.post("/{project_id}/profile/pending/{change_id}", response_model=PendingChangeResponse)
async def resolve_pending_change(
    project_id: int,
    change_id: int,
    req: PendingChangeAction,
    current_user: CurrentUser,
    db: DbSession,
):
    project = await _get_project(project_id, current_user.id, db)
    manager = PendingChangeManager(db)

    if req.action == "accept":
        change = await manager.accept(change_id, resolved_by=current_user.id)
    elif req.action == "reject":
        change = await manager.reject(change_id, resolved_by=current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'accept' or 'reject'",
        )

    if change is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending change not found")

    return change
