import pytest

from reqradar.web.services.version_service import VersionService
from tests.factories import build_analysis_task, build_project, build_report


@pytest.fixture
async def report_task(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="report_api_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    task = build_analysis_task(project_id=project.id, user_id=regular_user.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    report = build_report(task.id, content_markdown="# DB Report", content_html="<h1>DB Report</h1>")
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest.mark.asyncio
async def test_get_report_json_markdown_and_html(client, auth_headers, report_task):
    json_response = await client.get(f"/api/reports/{report_task.id}", headers=auth_headers)
    markdown_response = await client.get(f"/api/reports/{report_task.id}/markdown", headers=auth_headers)
    html_response = await client.get(f"/api/reports/{report_task.id}/html", headers=auth_headers)

    assert json_response.status_code == 200
    assert json_response.json()["content_markdown"] == "# DB Report"
    assert markdown_response.status_code == 200
    assert markdown_response.text == "# DB Report"
    assert html_response.status_code == 200
    assert "DB Report" in html_response.text


@pytest.mark.asyncio
async def test_report_missing_task_returns_404(client, auth_headers):
    response = await client.get("/api/reports/99999", headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_get_and_rollback_versions(client, auth_headers, db_session, report_task):
    service = VersionService(db_session)
    await service.create_version(
        report_task.id,
        {"risk_level": "low"},
        {"ctx": 1},
        "# Version 1",
        "<h1>Version 1</h1>",
    )
    await service.create_version(
        report_task.id,
        {"risk_level": "high"},
        {"ctx": 2},
        "# Version 2",
        "<h1>Version 2</h1>",
    )

    list_response = await client.get(
        f"/api/analyses/{report_task.id}/reports/versions", headers=auth_headers
    )
    get_response = await client.get(
        f"/api/analyses/{report_task.id}/reports/versions/1", headers=auth_headers
    )
    rollback_response = await client.post(
        f"/api/analyses/{report_task.id}/reports/rollback",
        headers=auth_headers,
        json={"version_number": 1},
    )

    assert list_response.status_code == 200
    assert [item["version_number"] for item in list_response.json()["versions"]] == [2, 1]
    assert get_response.status_code == 200
    assert get_response.json()["content_markdown"] == "# Version 1"
    assert rollback_response.status_code == 200
    assert rollback_response.json()["current_version"] == 3


@pytest.mark.asyncio
async def test_missing_version_returns_404(client, auth_headers, report_task):
    response = await client.get(
        f"/api/analyses/{report_task.id}/reports/versions/404", headers=auth_headers
    )

    assert response.status_code == 404
