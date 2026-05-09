import logging
from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import ReportVersion, AnalysisTask

logger = logging.getLogger("reqradar.version_service")

VERSION_LIMIT_DEFAULT = 10


class VersionService:
    def __init__(
        self,
        db: AsyncSession,
        version_limit: int = VERSION_LIMIT_DEFAULT,
        report_storage=None,
    ):
        self.db = db
        self.version_limit = version_limit
        self.report_storage = report_storage

    async def create_version(
        self,
        task_id: int,
        report_data: dict,
        context_snapshot: dict,
        content_markdown: str,
        content_html: str,
        trigger_type: str = "initial",
        trigger_description: str = "",
        created_by: int = 1,
    ) -> ReportVersion:
        result = await self.db.execute(
            select(func.max(ReportVersion.version_number)).where(ReportVersion.task_id == task_id)
        )
        max_version = result.scalar() or 0
        new_version_number = max_version + 1

        md_path = ""
        html_path = ""
        if self.report_storage is not None:
            md_path, html_path = await self.report_storage.save_version(
                task_id,
                new_version_number,
                content_markdown,
                content_html,
                context=context_snapshot,
            )

        version = ReportVersion(
            task_id=task_id,
            version_number=new_version_number,
            report_data=report_data,
            context_snapshot=context_snapshot,
            content_markdown=content_markdown,
            content_html=content_html,
            markdown_path=md_path,
            html_path=html_path,
            trigger_type=trigger_type,
            trigger_description=trigger_description,
            created_by=created_by,
        )
        self.db.add(version)
        await self._enforce_version_limit(task_id)

        task_result = await self.db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = task_result.scalar_one_or_none()
        if task:
            task.current_version = new_version_number

        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def list_versions(self, task_id: int) -> list[ReportVersion]:
        result = await self.db.execute(
            select(ReportVersion)
            .where(ReportVersion.task_id == task_id)
            .order_by(ReportVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_version(self, task_id: int, version_number: int) -> Optional[ReportVersion]:
        result = await self.db.execute(
            select(ReportVersion).where(
                ReportVersion.task_id == task_id,
                ReportVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_current_version(self, task_id: int) -> Optional[ReportVersion]:
        task_result = await self.db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = task_result.scalar_one_or_none()
        if task is None:
            return None
        current_version = task.current_version
        if current_version is None:
            return None
        return await self.get_version(task_id, current_version)

    async def rollback(
        self, task_id: int, target_version: int, user_id: int
    ) -> Optional[ReportVersion]:
        target = await self.get_version(task_id, target_version)
        if target is None:
            return None
        report_data = target.report_data
        context_snapshot = target.context_snapshot

        content_md = target.content_markdown
        content_html = target.content_html
        if self.report_storage is not None:
            file_md, file_html = await self.report_storage.read_version(task_id, target_version)
            if file_md is not None:
                content_md = file_md
            if file_html is not None:
                content_html = file_html

        new_version = await self.create_version(
            task_id=task_id,
            report_data=report_data,
            context_snapshot=context_snapshot,
            content_markdown=content_md,
            content_html=content_html,
            trigger_type="rollback",
            trigger_description=f"Rollback to version {target_version}",
            created_by=user_id,
        )
        return new_version

    async def _enforce_version_limit(self, task_id: int) -> None:
        result = await self.db.execute(
            select(func.count()).select_from(ReportVersion).where(ReportVersion.task_id == task_id)
        )
        count = result.scalar() or 0
        if count > self.version_limit:
            excess = count - self.version_limit
            oldest_result = await self.db.execute(
                select(ReportVersion)
                .where(ReportVersion.task_id == task_id)
                .order_by(ReportVersion.version_number.asc())
                .limit(excess)
            )
            old_versions = oldest_result.scalars().all()
            for old_version in old_versions:
                if self.report_storage is not None and old_version.markdown_path:
                    await self.report_storage.delete_version_files(
                        task_id, old_version.version_number
                    )
                await self.db.delete(old_version)
            logger.info(
                "Deleted %d old versions for task %d (limit: %d)",
                excess,
                task_id,
                self.version_limit,
            )

    async def get_context_snapshot(self, task_id: int, version_number: int) -> Optional[dict]:
        version = await self.get_version(task_id, version_number)
        if version is None:
            return None
        snapshot = version.context_snapshot
        if isinstance(snapshot, dict):
            return snapshot
        return {}
