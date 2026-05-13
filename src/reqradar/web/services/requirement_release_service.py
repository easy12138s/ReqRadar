import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.core.exceptions import ReportException
from reqradar.web.enums import ReleaseStatus
from reqradar.web.models import AnalysisTask, RequirementRelease, utc_now

logger = logging.getLogger("reqradar.requirement_release")


async def create_release(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    release_code: str,
    title: str,
    content: str,
    context_json: dict | None = None,
    task_id: int | None = None,
) -> RequirementRelease:
    result = await db.execute(
        select(func.max(RequirementRelease.version)).where(
            RequirementRelease.release_code == release_code
        )
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    release = RequirementRelease(
        project_id=project_id,
        user_id=user_id,
        task_id=task_id,
        release_code=release_code,
        version=next_version,
        title=title,
        content=content,
        context_json=context_json or {},
        status=ReleaseStatus.DRAFT,
    )
    db.add(release)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ReportException(
            f"Release code '{release_code}' version {next_version} already exists",
            cause=e,
        ) from e
    await db.refresh(release)
    return release


async def get_release(db: AsyncSession, release_id: int) -> RequirementRelease | None:
    result = await db.execute(select(RequirementRelease).where(RequirementRelease.id == release_id))
    return result.scalar_one_or_none()


async def list_releases(
    db: AsyncSession,
    project_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RequirementRelease]:
    stmt = select(RequirementRelease).order_by(RequirementRelease.created_at.desc())
    if project_id is not None:
        stmt = stmt.where(RequirementRelease.project_id == project_id)
    if status is not None:
        stmt = stmt.where(RequirementRelease.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_release(
    db: AsyncSession,
    release_id: int,
    title: str | None = None,
    content: str | None = None,
    context_json: dict | None = None,
) -> RequirementRelease | None:
    result = await db.execute(select(RequirementRelease).where(RequirementRelease.id == release_id))
    release = result.scalar_one_or_none()
    if release is None:
        return None
    if release.status != ReleaseStatus.DRAFT:
        raise ReportException("Only draft releases can be updated")
    if title is not None:
        release.title = title
    if content is not None:
        release.content = content
    if context_json is not None:
        release.context_json = context_json
    await db.commit()
    await db.refresh(release)
    return release


async def publish_release(db: AsyncSession, release_id: int) -> RequirementRelease | None:
    result = await db.execute(select(RequirementRelease).where(RequirementRelease.id == release_id))
    release = result.scalar_one_or_none()
    if release is None:
        return None
    if release.status != ReleaseStatus.DRAFT:
        raise ReportException("Only draft releases can be published")
    if release.task_id is not None:
        task_result = await db.execute(
            select(AnalysisTask).where(AnalysisTask.id == release.task_id)
        )
        task = task_result.scalar_one_or_none()
        if task is None or task.status != "completed":
            raise ReportException("Associated analysis task must be completed before publishing")
    release.status = ReleaseStatus.PUBLISHED
    release.published_at = utc_now()
    await db.commit()
    await db.refresh(release)
    return release


async def archive_release(db: AsyncSession, release_id: int) -> RequirementRelease | None:
    result = await db.execute(select(RequirementRelease).where(RequirementRelease.id == release_id))
    release = result.scalar_one_or_none()
    if release is None:
        return None
    if release.status != ReleaseStatus.PUBLISHED:
        raise ReportException("Only published releases can be archived")
    release.status = ReleaseStatus.ARCHIVED
    release.archived_at = utc_now()
    await db.commit()
    await db.refresh(release)
    return release


async def supersede_release(
    db: AsyncSession, release_id: int, superseded_by_id: int
) -> RequirementRelease | None:
    old_result = await db.execute(
        select(RequirementRelease).where(RequirementRelease.id == release_id)
    )
    old_release = old_result.scalar_one_or_none()
    if old_release is None:
        return None
    if old_release.status != ReleaseStatus.PUBLISHED:
        raise ReportException("Only published releases can be superseded")

    new_result = await db.execute(
        select(RequirementRelease).where(RequirementRelease.id == superseded_by_id)
    )
    new_release = new_result.scalar_one_or_none()
    if new_release is None:
        raise ReportException(f"Release {superseded_by_id} not found")
    if new_release.status != ReleaseStatus.PUBLISHED:
        raise ReportException("Superseding release must be published")

    old_release.superseded_by = superseded_by_id
    await db.commit()
    await db.refresh(old_release)
    return old_release


async def delete_release(db: AsyncSession, release_id: int) -> bool:
    result = await db.execute(select(RequirementRelease).where(RequirementRelease.id == release_id))
    release = result.scalar_one_or_none()
    if release is None:
        return False
    if release.status != ReleaseStatus.DRAFT:
        raise ReportException("Only draft releases can be deleted")
    await db.delete(release)
    await db.commit()
    return True
