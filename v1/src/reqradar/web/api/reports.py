import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import AnalysisTask, Report

logger = logging.getLogger("reqradar.web.api.reports")

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_report_storage(request: Request):
    return getattr(request.app.state, "report_storage", None)


class ReportResponse(BaseModel):
    task_id: int
    content_markdown: str
    content_html: str
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None

    model_config = {"from_attributes": True}

    @classmethod
    async def from_report(
        cls, report: Report, task: AnalysisTask, db: AsyncSession, report_storage=None
    ) -> "ReportResponse":
        risk_level = "unknown"
        risk_score = None

        if task.current_version:
            from ..models import ReportVersion as RV

            result = await db.execute(
                select(RV).where(
                    RV.task_id == task.id,
                    RV.version_number == task.current_version,
                )
            )
            version = result.scalar_one_or_none()
            if version and version.report_data:
                risk_level = version.report_data.get("risk_level", risk_level)
                risk_score = version.report_data.get("risk_score")

        if risk_level == "unknown" and task.context_json:
            deep = task.context_json.get("deep_analysis", {})
            if isinstance(deep, dict):
                risk_level = deep.get("risk_level", "unknown")
                risk_score = deep.get("risk_score")

        content_md = report.content_markdown
        content_html = report.content_html
        if report_storage is not None:
            file_md, file_html = await report_storage.read_report(task.id)
            if file_md is not None:
                content_md = file_md
            if file_html is not None:
                content_html = file_html

        return cls(
            task_id=task.id,
            content_markdown=content_md,
            content_html=content_html,
            risk_level=risk_level,
            risk_score=risk_score,
        )


@router.get("/{task_id}", response_model=ReportResponse)
async def get_report(task_id: int, current_user: CurrentUser, db: DbSession, request: Request):
    result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    report_result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return await ReportResponse.from_report(
        report, task, db, report_storage=_get_report_storage(request)
    )


@router.get("/{task_id}/markdown", response_class=PlainTextResponse)
async def get_report_markdown(
    task_id: int, current_user: CurrentUser, db: DbSession, request: Request
):
    result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    report_result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    content = report.content_markdown
    report_storage = _get_report_storage(request)
    if report_storage is not None:
        file_md, _ = await report_storage.read_report(task_id)
        if file_md is not None:
            content = file_md

    return PlainTextResponse(content=content, media_type="text/markdown")


@router.get("/{task_id}/html")
async def get_report_html(task_id: int, current_user: CurrentUser, db: DbSession, request: Request):
    result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    report_result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    from fastapi.responses import HTMLResponse

    content = report.content_html
    report_storage = _get_report_storage(request)
    if report_storage is not None:
        _, file_html = await report_storage.read_report(task_id)
        if file_html is not None:
            content = file_html

    return HTMLResponse(content=content)
