import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import PendingChange

logger = logging.getLogger("reqradar.pending_changes")


class PendingChangeManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, project_id, change_type, target_id, old_value="", new_value="", diff="", source="agent"
    ) -> PendingChange:
        change = PendingChange(
            project_id=project_id,
            change_type=change_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            diff=diff,
            source=source,
            status="pending",
        )
        self.db.add(change)
        await self.db.commit()
        await self.db.refresh(change)
        return change

    async def accept(self, change_id, resolved_by=None) -> PendingChange | None:
        result = await self.db.execute(select(PendingChange).where(PendingChange.id == change_id))
        change = result.scalar_one_or_none()
        if change is None:
            return None
        change.status = "accepted"
        change.resolved_at = datetime.now(timezone.utc)
        change.resolved_by = resolved_by
        await self.db.commit()
        await self.db.refresh(change)
        return change

    async def reject(self, change_id, resolved_by=None) -> PendingChange | None:
        result = await self.db.execute(select(PendingChange).where(PendingChange.id == change_id))
        change = result.scalar_one_or_none()
        if change is None:
            return None
        change.status = "rejected"
        change.resolved_at = datetime.now(timezone.utc)
        change.resolved_by = resolved_by
        await self.db.commit()
        await self.db.refresh(change)
        return change

    async def list_pending(self, project_id, change_type=None) -> list[PendingChange]:
        query = select(PendingChange).where(PendingChange.project_id == project_id, PendingChange.status == "pending")
        if change_type:
            query = query.where(PendingChange.change_type == change_type)
        query = query.order_by(PendingChange.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, change_id) -> PendingChange | None:
        result = await self.db.execute(select(PendingChange).where(PendingChange.id == change_id))
        return result.scalar_one_or_none()
