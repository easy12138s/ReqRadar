import pytest

from reqradar.web.services.report_storage import ReportStorage
from tests.factories import build_analysis_task, build_project


@pytest.mark.asyncio
async def test_save_and_read_report(tmp_path):
    storage = ReportStorage(tmp_path)

    md_path, html_path = await storage.save_report(1, "# Markdown", "<h1>HTML</h1>", {"ok": True})
    markdown, html = await storage.read_report(1)

    assert md_path == "1/report.md"
    assert html_path == "1/report.html"
    assert markdown == "# Markdown"
    assert html == "<h1>HTML</h1>"
    assert (tmp_path / "1" / "context.json").exists()


@pytest.mark.asyncio
async def test_save_and_read_version(tmp_path):
    storage = ReportStorage(tmp_path)

    md_path, html_path = await storage.save_version(1, 2, "# V2", "<h1>V2</h1>", {"v": 2})
    markdown, html = await storage.read_version(1, 2)

    assert md_path == "1/versions/v2.md"
    assert html_path == "1/versions/v2.html"
    assert markdown == "# V2"
    assert html == "<h1>V2</h1>"
    assert (tmp_path / "1" / "versions" / "v2_context.json").exists()


@pytest.mark.asyncio
async def test_delete_task_reports(tmp_path):
    storage = ReportStorage(tmp_path)
    await storage.save_report(1, "# Markdown", "<h1>HTML</h1>")

    await storage.delete_task_reports(1)

    assert not (tmp_path / "1").exists()


@pytest.mark.asyncio
async def test_delete_project_reports_removes_task_directories(tmp_path, db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="report_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    task = build_analysis_task(project_id=project.id, user_id=regular_user.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    storage = ReportStorage(tmp_path)
    await storage.save_report(task.id, "# Markdown", "<h1>HTML</h1>")

    await storage.delete_project_reports(project.id, db_session)

    assert not (tmp_path / str(task.id)).exists()
