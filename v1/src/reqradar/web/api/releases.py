from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.core.exceptions import ReportException
from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import Project, RequirementRelease
from reqradar.web.services.requirement_release_service import (
    archive_release,
    create_release,
    delete_release,
    list_releases,
    publish_release,
    update_release,
)


class CreateReleaseRequest(BaseModel):
    project_id: int
    release_code: str
    title: str
    content: str
    context_json: dict | None = None
    task_id: int | None = None


class UpdateReleaseRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    context_json: dict | None = None


router = APIRouter(prefix="/api/releases", tags=["releases"])


async def _verify_project_owner(db: AsyncSession, project_id: int, current_user) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project",
        )


async def _verify_release_owner(
    db: AsyncSession, release_id: int, current_user
) -> RequirementRelease:
    result = await db.execute(select(RequirementRelease).where(RequirementRelease.id == release_id))
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
    await _verify_project_owner(db, release.project_id, current_user)
    return release


def _release_to_dict(release: RequirementRelease) -> dict:
    return {
        "id": release.id,
        "project_id": release.project_id,
        "user_id": release.user_id,
        "task_id": release.task_id,
        "release_code": release.release_code,
        "version": release.version,
        "title": release.title,
        "content": release.content,
        "context_json": release.context_json,
        "status": release.status,
        "superseded_by": release.superseded_by,
        "published_at": release.published_at.isoformat() if release.published_at else None,
        "archived_at": release.archived_at.isoformat() if release.archived_at else None,
        "created_at": release.created_at.isoformat() if release.created_at else None,
        "updated_at": release.updated_at.isoformat() if release.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_release_endpoint(
    body: CreateReleaseRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    await _verify_project_owner(db, body.project_id, current_user)
    try:
        release = await create_release(
            db,
            body.project_id,
            current_user.id,
            body.release_code,
            body.title,
            body.content,
            body.context_json,
            body.task_id,
        )
    except ReportException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _release_to_dict(release)


@router.get("")
async def list_releases_endpoint(
    db: DbSession,
    current_user: CurrentUser,
    project_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    if project_id is not None:
        await _verify_project_owner(db, project_id, current_user)
    releases = await list_releases(
        db, project_id=project_id, status=status, limit=limit, offset=offset
    )
    return [_release_to_dict(r) for r in releases]


@router.get("/{release_id}")
async def get_release_endpoint(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    release = await _verify_release_owner(db, release_id, current_user)
    return _release_to_dict(release)


@router.put("/{release_id}")
async def update_release_endpoint(
    release_id: int,
    body: UpdateReleaseRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    await _verify_release_owner(db, release_id, current_user)
    try:
        release = await update_release(db, release_id, body.title, body.content, body.context_json)
    except ReportException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
    return _release_to_dict(release)


@router.post("/{release_id}/publish")
async def publish_release_endpoint(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    await _verify_release_owner(db, release_id, current_user)
    try:
        release = await publish_release(db, release_id)
    except ReportException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    assert release is not None
    return _release_to_dict(release)


@router.post("/{release_id}/archive")
async def archive_release_endpoint(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    await _verify_release_owner(db, release_id, current_user)
    try:
        release = await archive_release(db, release_id)
    except ReportException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    assert release is not None
    return _release_to_dict(release)


@router.delete("/{release_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_release_endpoint(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    await _verify_release_owner(db, release_id, current_user)
    try:
        result = await delete_release(db, release_id)
    except ReportException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
