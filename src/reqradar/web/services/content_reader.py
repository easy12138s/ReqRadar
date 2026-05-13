import logging
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.modules.project_memory import ProjectMemory
from reqradar.web.models import AnalysisTask, RequirementDocument, RequirementRelease
from reqradar.web.services.report_storage import ReportStorage

logger = logging.getLogger("reqradar.content_reader")

_TRUNCATE_LENGTH = 500


class ContentReader:
    def __init__(self, session_factory, report_storage: ReportStorage, memory_storage_path: str):
        self._session_factory = session_factory
        self._report_storage = report_storage
        self._memory_storage_path = memory_storage_path

    async def _get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_factory() as session:
            yield session

    async def read_requirement_content(self, doc_id: int) -> dict | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(RequirementDocument).where(RequirementDocument.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                return None
            return {
                "id": doc.id,
                "title": doc.title,
                "content": doc.consolidated_text or "",
                "status": doc.status,
                "version": doc.version,
            }

    async def search_published_requirements(
        self,
        project_id: int | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        async with self._session_factory() as session:
            stmt = select(RequirementRelease).where(RequirementRelease.status == "published")
            if project_id is not None:
                stmt = stmt.where(RequirementRelease.project_id == project_id)
            if query is not None:
                pattern = f"%{query}%"
                stmt = stmt.where(
                    (RequirementRelease.title.ilike(pattern))
                    | (RequirementRelease.content.ilike(pattern))
                )
            stmt = stmt.order_by(RequirementRelease.published_at.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "project_id": r.project_id,
                    "release_code": r.release_code,
                    "version": r.version,
                    "title": r.title,
                    "content": (r.content or "")[:_TRUNCATE_LENGTH],
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                }
                for r in rows
            ]

    async def get_requirement_context(self, release_id: int) -> dict | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(RequirementRelease).where(
                    RequirementRelease.id == release_id,
                    RequirementRelease.status == "published",
                )
            )
            r = result.scalar_one_or_none()
            if r is None:
                return None
            return {
                "id": r.id,
                "release_code": r.release_code,
                "version": r.version,
                "title": r.title,
                "content": r.content or "",
                "context_json": r.context_json or {},
            }

    async def read_report_markdown(self, task_id: int, version: int | None = None) -> str | None:
        if version is not None:
            md, _ = await self._report_storage.read_version(task_id, version)
        else:
            md, _ = await self._report_storage.read_report(task_id)
        return md

    async def read_context_json(self, task_id: int) -> dict | None:
        async with self._session_factory() as session:
            result = await session.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
            task = result.scalar_one_or_none()
            if task is None:
                return None
            return task.context_json  # type: ignore[no-any-return]

    async def read_project_memory(self, project_id: int) -> dict | None:
        memory = ProjectMemory(self._memory_storage_path, project_id)
        return memory.load()
