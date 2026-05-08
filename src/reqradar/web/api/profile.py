import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from reqradar.infrastructure.config import load_config
from reqradar.modules.pending_changes import PendingChangeManager
from reqradar.modules.project_memory import ProjectMemory
from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import Project, PendingChange

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


class ProfileUpdateRequest(BaseModel):
    content: str | None = None
    data: dict | None = None


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
    from reqradar.web.services.project_file_service import ProjectFileService

    file_svc = ProjectFileService(config.web)
    memory_path = file_svc.get_memory_path(project.name)
    return ProjectMemory(storage_path=str(memory_path), project_id=project.id)


@router.get("/{project_id}/profile", response_model=ProfileResponse)
async def get_profile(project_id: int, current_user: CurrentUser, db: DbSession):
    project = await _get_project(project_id, current_user.id, db)
    pm = _build_project_memory(project)
    data = pm.load()

    content = (
        pm.file_path.read_text(encoding="utf-8")
        if pm.file_path.exists()
        else pm._render_markdown(data)
    )

    return ProfileResponse(content=content, data=data)


@router.put("/{project_id}/profile", response_model=ProfileResponse)
async def update_profile(
    project_id: int,
    req: ProfileUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    project = await _get_project(project_id, current_user.id, db)
    pm = _build_project_memory(project)

    if req.data:
        existing = pm.load()
        for key, value in req.data.items():
            if value is not None:
                existing[key] = value
        content = pm._render_markdown(existing)
        pm.file_path.write_text(content, encoding="utf-8")
        pm._loaded = False

    elif req.content is not None:
        pm.file_path.write_text(req.content, encoding="utf-8")
        pm._loaded = False

    pm._loaded = False
    data = pm.load()
    content = (
        pm.file_path.read_text(encoding="utf-8")
        if pm.file_path.exists()
        else pm._render_markdown(data)
    )
    return ProfileResponse(content=content, data=data)


@router.get("/{project_id}/profile/pending", response_model=list[PendingChangeResponse])
@router.get("/{project_id}/pending-changes", response_model=list[PendingChangeResponse])
async def get_pending_changes(project_id: int, current_user: CurrentUser, db: DbSession):
    project = await _get_project(project_id, current_user.id, db)
    manager = PendingChangeManager(db)
    changes = await manager.list_pending(project.id)
    return changes


@router.post("/{project_id}/profile/pending/{change_id}", response_model=PendingChangeResponse)
@router.post(
    "/{project_id}/pending-changes/{change_id}/accept", response_model=PendingChangeResponse
)
async def accept_pending_change(
    project_id: int,
    change_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    project = await _get_project(project_id, current_user.id, db)

    result = await db.execute(
        select(PendingChange).where(
            PendingChange.id == change_id,
            PendingChange.project_id == project_id,
        )
    )
    change = result.scalar_one_or_none()
    if not change:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pending change not found"
        )

    pm = _build_project_memory(project)

    if change.change_type == "overview_updated":
        pm.update_overview(change.new_value)
    elif change.change_type == "term_added":
        pm.add_term(change.target_id, change.new_value)
    elif change.change_type == "module_added":
        pm.add_module(
            name=change.target_id
            if not change.target_id.startswith("module:")
            else change.target_id.split(":", 1)[1]
        )
    elif change.change_type == "tech_stack_updated":
        category = (
            change.target_id.split(":", 1)[1] if ":" in change.target_id else change.target_id
        )
        items = [x.strip() for x in change.new_value.split(",") if x.strip()]
        if items:
            pm.add_tech_stack(category, items)
    elif change.change_type == "profile":
        existing = pm.load()
        existing["overview"] = change.new_value
        content = pm._render_markdown(existing)
        pm.file_path.write_text(content, encoding="utf-8")
        pm._loaded = False

    change.status = "accepted"
    await db.commit()
    return change


@router.post(
    "/{project_id}/pending-changes/{change_id}/reject", response_model=PendingChangeResponse
)
async def reject_pending_change(
    project_id: int,
    change_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    project = await _get_project(project_id, current_user.id, db)
    manager = PendingChangeManager(db)
    change = await manager.reject(change_id, resolved_by=current_user.id)
    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pending change not found"
        )
    return change
