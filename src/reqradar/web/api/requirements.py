import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from reqradar.agent.requirement_preprocessor import preprocess_requirements
from reqradar.agent.llm_utils import _call_llm_structured
from reqradar.modules.llm_client import LiteLLMClient
from reqradar.web.dependencies import get_current_user, get_db
from reqradar.web.models import RequirementDocument, Project, User
from reqradar.web.enums import PreprocessStatus
from reqradar.infrastructure.config import load_config

router = APIRouter(prefix="/api/requirements", tags=["requirements"])

ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".epub",
    ".xml",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
}


class PreprocessResponse(BaseModel):
    id: int
    title: str
    consolidated_text: str
    source_files: list | None
    status: str
    version: int
    created_at: str


class UpdateRequirementRequest(BaseModel):
    consolidated_text: str = Field(..., description="编辑后的 Markdown 文档")
    title: str | None = None


@router.post("/preprocess", response_model=PreprocessResponse)
async def preprocess_requirements_endpoint(
    project_id: int = Form(...),
    files: list[UploadFile] = File(...),
    title: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    config = load_config()
    data_root = (
        Path(config.web.data_root) if hasattr(config, "web") else Path.home() / ".reqradar" / "data"
    )
    req_dir = data_root / project.name / "requirements"
    req_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    source_files = []

    for upload_file in files:
        ext = Path(upload_file.filename or "").suffix.lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {ext}")

        unique_name = f"{uuid.uuid4().hex[:8]}_{upload_file.filename}"
        file_path = req_dir / unique_name

        content = await upload_file.read()
        file_path.write_bytes(content)

        source_files.append(
            {
                "filename": upload_file.filename,
                "type": ext,
                "size": len(content),
                "stored_path": str(file_path),
            }
        )
        saved_paths.append(file_path)

    llm_client = LiteLLMClient(
        api_key=config.llm.api_key or "",
        model=config.llm.model,
        base_url=config.llm.base_url or "https://api.openai.com/v1",
        timeout=config.llm.timeout,
        max_retries=config.llm.max_retries,
    )

    if not title:
        title = files[0].filename.rsplit(".", 1)[0] if files else "未命名需求"

    try:
        result = await preprocess_requirements(saved_paths, llm_client, title)
        consolidated_text = result.get("consolidated_text", "")
    except Exception as e:
        consolidated_text = f"# {title}\n\n预处理失败: {str(e)}"
        status = PreprocessStatus.FAILED
    else:
        status = PreprocessStatus.READY

    doc = RequirementDocument(
        project_id=project_id,
        user_id=current_user.id,
        title=title,
        consolidated_text=consolidated_text,
        source_files=source_files,
        status=status.value,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return PreprocessResponse(
        id=doc.id,
        title=doc.title,
        consolidated_text=doc.consolidated_text,
        source_files=doc.source_files,
        status=doc.status,
        version=doc.version,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
    )


@router.get("/{doc_id}")
async def get_requirement(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(RequirementDocument).where(RequirementDocument.id == doc_id))
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Requirement document not found")
    return {
        "id": doc.id,
        "project_id": doc.project_id,
        "title": doc.title,
        "consolidated_text": doc.consolidated_text,
        "source_files": doc.source_files,
        "status": doc.status,
        "version": doc.version,
        "created_at": doc.created_at.isoformat() if doc.created_at else "",
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
    }


@router.put("/{doc_id}")
async def update_requirement(
    doc_id: int,
    body: UpdateRequirementRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(RequirementDocument).where(RequirementDocument.id == doc_id))
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Requirement document not found")

    doc.consolidated_text = body.consolidated_text
    doc.version = (doc.version or 0) + 1
    doc.updated_at = datetime.now(timezone.utc)
    if body.title is not None:
        doc.title = body.title
    await db.commit()
    return {"id": doc.id, "updated": True}


@router.delete("/{doc_id}")
async def delete_requirement(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(RequirementDocument).where(RequirementDocument.id == doc_id))
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Requirement document not found")
    await db.delete(doc)
    await db.commit()
    return {"deleted": True}


@router.get("")
async def list_requirements(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = (
        (
            await db.execute(
                select(RequirementDocument)
                .where(RequirementDocument.project_id == project_id)
                .order_by(RequirementDocument.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "status": d.status,
            "version": d.version,
            "source_files": d.source_files,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        }
        for d in docs
    ]
