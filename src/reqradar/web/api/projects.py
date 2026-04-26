import asyncio
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import load_config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.dependencies import CurrentUser, DbSession, get_current_user, get_db
from reqradar.web.models import Project, User
from reqradar.web.services.project_file_service import ProjectFileService

logger = logging.getLogger("reqradar.web.api.projects")

router = APIRouter(prefix="/api/projects", tags=["projects"])

PROJECT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _get_file_service() -> ProjectFileService:
    config = load_config()
    return ProjectFileService(config.web)


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
        select(Project).where(Project.owner_id == current_user.id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/from-local", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_local(req: ProjectFromLocal, current_user: CurrentUser, db: DbSession):
    svc = _get_file_service()
    local_path = Path(req.local_path)
    if not local_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Local path does not exist: {req.local_path}",
        )

    project = await _create_project_record(req.name, req.description, "local", req.local_path, current_user.id, db)
    svc.create_project_dirs(req.name)

    src_code = svc.get_project_path(req.name) / "project_code"
    try:
        for item in local_path.iterdir():
            if item.is_dir():
                shutil.copytree(str(item), str(src_code / item.name), dirs_exist_ok=True)
            else:
                shutil.copy2(str(item), str(src_code / item.name))
    except Exception as e:
        logger.warning("Failed to copy local path files for project '%s': %s", req.name, e)

    return project


@router.post("/from-zip", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_zip(
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

    svc = _get_file_service()
    project = await _create_project_record(name, description, "zip", file.filename or "upload.zip", current_user.id, db)
    svc.create_project_dirs(name)

    zip_bytes = await file.read()
    svc.extract_zip(name, zip_bytes)

    return project


@router.post("/from-git", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_git(req: ProjectFromGit, current_user: CurrentUser, db: DbSession):
    svc = _get_file_service()
    if not svc.is_git_available():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Git is not available on this system. Use ZIP upload instead.",
        )

    project = await _create_project_record(req.name, req.description, "git", req.git_url, current_user.id, db)
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


@router.delete("/{project_id}")
async def delete_project(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    svc = _get_file_service()
    await db.delete(project)
    await db.commit()
    svc.delete_project_files(project.name)
    return {"success": True, "message": f"Project '{project.name}' deleted"}


@router.get("/{project_id}/files", response_model=list[FileTreeNode])
async def get_project_files(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    svc = _get_file_service()
    tree = svc.get_file_tree(project.name)
    return tree


@router.post("/{project_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_index(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    async def _run_index():
        from reqradar.web.services.project_store import project_store

        config = load_config()
        svc = ProjectFileService(config.web)
        repo_path = svc.detect_code_root(project.name)
        index_path = svc.get_index_path(project.name)

        cm = ConfigManager(db, config)

        try:
            from reqradar.modules.code_parser import PythonCodeParser

            parser = PythonCodeParser()
            code_graph = parser.parse_directory(repo_path)

            index_path.mkdir(parents=True, exist_ok=True)
            graph_file = index_path / "code_graph.json"
            with open(graph_file, "w", encoding="utf-8") as f:
                f.write(code_graph.to_json())

            try:
                from reqradar.modules.vector_store import ChromaVectorStore, CHROMA_AVAILABLE

                if CHROMA_AVAILABLE:
                    req_dir = svc.get_requirements_path(project.name)
                    vectorstore_path = index_path / "vectorstore"

                    if req_dir.exists() and any(req_dir.iterdir()):
                        from reqradar.modules.loaders import LoaderRegistry
                        from reqradar.modules.vector_store import Document

                        vs = ChromaVectorStore(
                            persist_directory=str(vectorstore_path),
                            embedding_model=config.index.embedding_model,
                        )

                        for doc_path in req_dir.rglob("*"):
                            if doc_path.is_file():
                                loader = LoaderRegistry.get_for_file(doc_path)
                                if loader is None:
                                    continue
                                try:
                                    loaded_docs = loader.load(
                                        doc_path,
                                        chunk_size=config.loader.chunk_size,
                                        chunk_overlap=config.loader.chunk_overlap,
                                    )
                                    documents = [
                                        Document(
                                            id=f"{doc_path.stem}_{i}",
                                            content=doc.content,
                                            metadata={**doc.metadata, "format": doc.format},
                                        )
                                        for i, doc in enumerate(loaded_docs)
                                    ]
                                    if documents:
                                        vs.add_documents(documents)
                                except Exception:
                                    logger.warning("Failed to index file %s", doc_path)

                        vs.persist()
                        logger.info("Vector store built for project %d", project_id)
            except Exception:
                logger.warning("Vector store build failed for project %d", project_id, exc_info=True)

            memory_enabled = await cm.get_bool("memory.enabled", project_id=project_id, default=config.memory.enabled)
            if memory_enabled:
                from reqradar.modules.memory import MemoryManager

                memory_path = svc.get_memory_path(project.name)
                memory_manager = MemoryManager(storage_path=str(memory_path))
                memory_manager.load()

            await project_store.invalidate(project_id)

            logger.info("Index build completed for project %d", project_id)
        except Exception:
            logger.exception("Index build failed for project %d", project_id)

    asyncio.create_task(_run_index())

    return {"message": "Index build started", "project_id": project_id}
