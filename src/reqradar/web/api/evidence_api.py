import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from reqradar.web.dependencies import DbSession, CurrentUser
from reqradar.web.models import AnalysisTask
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.api.evidence")

router = APIRouter(prefix="/api/analyses/{task_id}", tags=["evidence"])


@router.get("/evidence")
async def get_evidence_chain(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
    version_number: int | None = None,
):
    task_result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    version_num = version_number or task.current_version or 1
    service = VersionService(db)
    snapshot = await service.get_context_snapshot(task_id, version_num)
    if snapshot is None:
        return {"evidence": []}

    evidence_list = snapshot.get("evidence_list", [])
    return {
        "evidence": [
            {
                "id": ev.get("id", ""),
                "type": ev.get("type", ""),
                "source": ev.get("source", ""),
                "content": ev.get("content", ""),
                "confidence": ev.get("confidence", "medium"),
                "dimensions": ev.get("dimensions", []),
                "timestamp": ev.get("timestamp", ""),
            }
            for ev in evidence_list
        ]
    }


@router.get("/evidence/{evidence_id}")
async def get_evidence_detail(
    task_id: int,
    evidence_id: str,
    db: DbSession,
    current_user: CurrentUser,
    version_number: int | None = None,
):
    task_result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    version_num = version_number or task.current_version or 1
    service = VersionService(db)
    snapshot = await service.get_context_snapshot(task_id, version_num)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    evidence_list = snapshot.get("evidence_list", [])
    for ev in evidence_list:
        if ev.get("id") == evidence_id:
            return {
                "id": ev.get("id", ""),
                "type": ev.get("type", ""),
                "source": ev.get("source", ""),
                "content": ev.get("content", ""),
                "confidence": ev.get("confidence", "medium"),
                "dimensions": ev.get("dimensions", []),
                "timestamp": ev.get("timestamp", ""),
            }

    raise HTTPException(status_code=404, detail="Evidence not found")
