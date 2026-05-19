"""数据库辅助工具 — 提供测试数据快速插入、清理、断言。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import AnalysisTask, Project


async def create_test_project(
    db: AsyncSession,
    owner_id: int,
    name: str = "test-project",
    source_type: str = "local",
    source_url: str = "",
) -> Project:
    project = Project(
        name=name,
        description="Test project",
        source_type=source_type,
        source_url=source_url,
        owner_id=owner_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def create_test_analysis_task(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    requirement_text: str = "Test requirement",
    status: str = "pending",
) -> AnalysisTask:
    from reqradar.web.enums import TaskStatus

    task = AnalysisTask(
        project_id=project_id,
        user_id=user_id,
        requirement_name="Test Requirement",
        requirement_text=requirement_text,
        status=TaskStatus(status),
        context_json={},
        depth="quick",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def count_rows(db: AsyncSession, model) -> int:
    result = await db.execute(select(model))
    return len(result.scalars().all())
