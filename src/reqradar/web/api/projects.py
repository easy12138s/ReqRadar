import asyncio
import logging
import re
import shutil
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import CurrentUser, DbSession, get_current_user, get_db
from reqradar.web.models import PendingChange, Project, User
from reqradar.web.services.project_file_service import ProjectFileService
from reqradar.web.services.project_index_service import ProjectIndexService

logger = logging.getLogger("reqradar.web.api.projects")

router = APIRouter(prefix="/api/projects", tags=["projects"])

PROJECT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _get_file_service(request: Request) -> ProjectFileService:
    return ProjectFileService(request.app.state.paths["projects"])


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    source_type: str
    source_url: str
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectFromLocal(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = ""
    local_path: str


class ProjectFromGit(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = ""
    git_url: str
    branch: Optional[str] = None


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str
    size: Optional[int] = None
    children: Optional[list["FileTreeNode"]] = None


async def _create_project_record(
    name: str,
    description: str,
    source_type: str,
    source_url: str,
    owner_id: int,
    db: AsyncSession,
) -> Project:
    existing = await db.execute(
        select(Project).where(Project.name == name, Project.owner_id == owner_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{name}' already exists",
        )

    project = Project(
        name=name,
        description=description,
        source_type=source_type,
        source_url=source_url,
        owner_id=owner_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


class ProjectDashboardSummary(BaseModel):
    id: int
    name: str
    terms_count: int = 0
    modules_count: int = 0
    pending_changes_count: int = 0
    updated_at: str = ""


@router.get("/dashboard-summaries", response_model=list[ProjectDashboardSummary])
async def get_dashboard_summaries(current_user: CurrentUser, db: DbSession, request: Request):
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    projects = list(result.scalars().all())
    if not projects:
        return []

    project_ids = [p.id for p in projects]

    pending_counts_result = await db.execute(
        select(PendingChange.project_id, func.count())
        .where(
            PendingChange.project_id.in_(project_ids),
            PendingChange.status == "pending",
        )
        .group_by(PendingChange.project_id)
    )
    pending_counts = dict(pending_counts_result.all())

    from reqradar.modules.project_memory import ProjectMemory

    memories_path = request.app.state.paths["memories"]

    summaries: list[ProjectDashboardSummary] = []
    for p in projects:
        terms_count = 0
        modules_count = 0
        try:
            pm = ProjectMemory(storage_path=str(memories_path), project_id=p.id)
            data = pm.load()
            terms_count = len(data.get("terms", []))
            modules_count = len(data.get("modules", []))
        except Exception:
            pass

        summaries.append(
            ProjectDashboardSummary(
                id=p.id,
                name=p.name,
                terms_count=terms_count,
                modules_count=modules_count,
                pending_changes_count=pending_counts.get(p.id, 0),
                updated_at=p.updated_at.isoformat() if p.updated_at else "",
            )
        )

    return summaries


@router.post("/from-local", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_local(
    req: ProjectFromLocal, current_user: CurrentUser, db: DbSession, request: Request
):
    svc = _get_file_service(request)
    try:
        local_path = svc.validate_local_path(req.local_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    project = await _create_project_record(
        req.name, req.description, "local", req.local_path, current_user.id, db
    )
    svc.create_project_dirs(req.name)

    src_code = svc.get_project_path(req.name) / "project_code"
    copy_errors = []
    try:
        for item in local_path.iterdir():
            try:
                if item.is_dir() and not item.is_symlink():
                    await asyncio.to_thread(
                        shutil.copytree, str(item), str(src_code / item.name), dirs_exist_ok=True
                    )
                elif item.is_file() and not item.is_symlink():
                    await asyncio.to_thread(shutil.copy2, str(item), str(src_code / item.name))
            except (shutil.SpecialFileError, OSError) as e:
                logger.debug("Skipping special file %s: %s", item, e)
                copy_errors.append(str(item))
    except Exception as e:
        logger.exception("Failed to copy local path files for project '%s'", req.name)
        svc.delete_project_files(req.name)
        await db.delete(project)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to copy local path files: {str(e)[:500]}",
        )

    return project


@router.post("/from-zip", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_zip(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not PROJECT_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Project name must match {PROJECT_NAME_PATTERN.pattern}",
        )

    svc = _get_file_service(request)
    project = await _create_project_record(
        name, description, "zip", file.filename or "upload.zip", current_user.id, db
    )
    svc.create_project_dirs(name)

    zip_bytes = await file.read()
    svc.extract_zip(name, zip_bytes)

    return project


@router.post("/from-git", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_git(
    req: ProjectFromGit, current_user: CurrentUser, db: DbSession, request: Request
):
    svc = _get_file_service(request)
    if not svc.is_git_available():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Git is not available on this system. Use ZIP upload instead.",
        )

    project = await _create_project_record(
        req.name, req.description, "git", req.git_url, current_user.id, db
    )
    svc.create_project_dirs(req.name)

    try:
        svc.clone_git(req.name, req.git_url, req.branch)
    except Exception as e:
        await db.delete(project)
        await db.commit()
        svc.delete_project_files(req.name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Git clone failed: {str(e)[:500]}",
        )

    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int, req: ProjectUpdate, current_user: CurrentUser, db: DbSession
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    project.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: int, current_user: CurrentUser, db: DbSession, request: Request
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    svc = _get_file_service(request)
    project_name = project.name
    try:
        svc.delete_project_files(project_name)
    except Exception:
        logger.exception("Failed to delete files for project '%s'", project_name)

    report_storage = getattr(request.app.state, "report_storage", None)
    if report_storage is not None:
        try:
            await report_storage.delete_project_reports(project.id, db)
        except Exception:
            logger.exception("Failed to delete reports for project %d", project.id)

    await db.delete(project)
    await db.commit()
    return {"success": True, "message": f"Project '{project_name}' deleted"}


@router.get("/{project_id}/files", response_model=list[FileTreeNode])
async def get_project_files(
    project_id: int, current_user: CurrentUser, db: DbSession, request: Request
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    svc = _get_file_service(request)
    tree = svc.get_file_tree(project.name)
    return tree


@router.post("/{project_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_index(
    project_id: int, current_user: CurrentUser, db: DbSession, request: Request
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    from reqradar.infrastructure.config import load_config

    config = load_config()
    index_service = ProjectIndexService(
        projects_path=request.app.state.paths["projects"],
        memories_path=request.app.state.paths["memories"],
    )
    asyncio.create_task(index_service.build_index(project, db, config))

    return {"message": "Index build started", "project_id": project_id}
