import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import load_config
from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import Project

logger = logging.getLogger("reqradar.web.api.projects")

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    repo_path: str = ""
    docs_path: str = ""
    config_json: str = "{}"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    repo_path: Optional[str] = None
    docs_path: Optional[str] = None
    config_json: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    repo_path: str
    docs_path: str
    index_path: str
    config_json: str
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ProjectResponse])
async def list_projects(current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.owner_id == current_user.id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(req: ProjectCreate, current_user: CurrentUser, db: DbSession):
    project = Project(
        name=req.name,
        description=req.description,
        repo_path=req.repo_path,
        docs_path=req.docs_path,
        config_json=req.config_json,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
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
async def update_project(project_id: int, req: ProjectUpdate, current_user: CurrentUser, db: DbSession):
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


@router.post("/{project_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_index(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not project.repo_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no repo_path configured")

    async def _run_index():
        from reqradar.web.services.project_store import project_store
        config = load_config()
        repo_path = Path(project.repo_path)
        index_path = repo_path / ".reqradar" / "index"

        try:
            from reqradar.modules.code_parser import PythonCodeParser

            parser = PythonCodeParser()
            code_graph = parser.parse_directory(repo_path)

            index_path.mkdir(parents=True, exist_ok=True)
            graph_file = index_path / "code_graph.json"
            with open(graph_file, "w", encoding="utf-8") as f:
                f.write(code_graph.to_json())

            if config.memory.enabled:
                from reqradar.modules.memory import MemoryManager

                memory_path = repo_path / config.memory.storage_path
                memory_manager = MemoryManager(storage_path=str(memory_path))
                memory_manager.load()

            project.index_path = str(index_path)
            project.updated_at = datetime.now(timezone.utc)

            await project_store.invalidate(project_id)

            async with db.begin():
                pass

            logger.info("Index build completed for project %d", project_id)

        except Exception:
            logger.exception("Index build failed for project %d", project_id)

    asyncio.create_task(_run_index())

    return {"message": "Index build started", "project_id": project_id}