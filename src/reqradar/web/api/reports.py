import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import AnalysisTask, Report

logger = logging.getLogger("reqradar.web.api.reports")

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportResponse(BaseModel):
    task_id: int
    content_markdown: str
    content_html: str
    risk_level: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_report(cls, report: Report, task: AnalysisTask) -> "ReportResponse":
        risk_level = "unknown"
        if task.context_json:
            try:
                ctx = json.loads(task.context_json)
                deep = ctx.get("deep_analysis")
                if deep and isinstance(deep, dict):
                    risk_level = deep.get("risk_level", "unknown")
            except (json.JSONDecodeError, AttributeError):
                pass

        return cls(
            task_id=report.task_id,
            content_markdown=report.content_markdown,
            content_html=report.content_html,
            risk_level=risk_level,
        )


@router.get("/{task_id}", response_model=ReportResponse)
async def get_report(task_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(AnalysisTask).where(AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    report_result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return ReportResponse.from_report(report, task)


@router.get("/{task_id}/markdown", response_class=PlainTextResponse)
async def get_report_markdown(task_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(AnalysisTask).where(AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    report_result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return PlainTextResponse(content=report.content_markdown, media_type="text/markdown")


@router.get("/{task_id}/html")
async def get_report_html(task_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(AnalysisTask).where(AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    report_result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=report.content_html)