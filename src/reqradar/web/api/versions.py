import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import DbSession, CurrentUser
from reqradar.web.models import AnalysisTask, ReportVersion
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.api.versions")

router = APIRouter(prefix="/api/analyses/{task_id}/reports", tags=["versions"])


class RollbackRequest(BaseModel):
    version_number: int


@router.get("/versions")
async def list_versions(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    service = VersionService(db)
    versions = await service.list_versions(task_id)
    return {
        "versions": [
            {
                "version_number": v.version_number,
                "trigger_type": v.trigger_type,
                "trigger_description": v.trigger_description,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]
    }


@router.get("/versions/{version_number}")
async def get_version(
    task_id: int,
    version_number: int,
    db: DbSession,
    current_user: CurrentUser,
):
    service = VersionService(db)
    version = await service.get_version(task_id, version_number)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    report_data = version.report_data
    if isinstance(report_data, str):
        try:
            report_data = json.loads(report_data)
        except (json.JSONDecodeError, TypeError):
            report_data = {}

    return {
        "version_number": version.version_number,
        "content_markdown": version.content_markdown,
        "content_html": version.content_html,
        "report_data": report_data,
        "trigger_type": version.trigger_type,
        "trigger_description": version.trigger_description,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "created_by": version.created_by,
    }


@router.post("/rollback")
async def rollback_version(
    task_id: int,
    req: RollbackRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    service = VersionService(db)
    user_id = current_user.id if hasattr(current_user, "id") else 1
    new_version = await service.rollback(task_id, req.version_number, user_id=user_id)
    if new_version is None:
        raise HTTPException(status_code=404, detail="Target version not found")
    return {
        "success": True,
        "current_version": new_version.version_number,
    }
