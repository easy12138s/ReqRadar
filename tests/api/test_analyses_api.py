import pytest

from reqradar.web.enums import TaskStatus
from tests.factories import build_analysis_task, build_project


@pytest.fixture
async def project(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="analysis_api_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_submit_analysis_requires_project_owner(client, auth_headers, db_session, admin_user):
    other_project = build_project(owner_id=admin_user.id, name="other_project")
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)

    response = await client.post(
        "/api/analyses",
        headers=auth_headers,
        json={"project_id": other_project.id, "requirement_text": "test"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_analysis_requires_llm_api_key(client, auth_headers, project):
    response = await client.post(
        "/api/analyses",
        headers=auth_headers,
        json={"project_id": project.id, "requirement_text": "test"},
    )

    assert response.status_code == 400
    assert "LLM API Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_analysis_rejects_large_file(client, auth_headers, project):
    response = await client.post(
        "/api/analyses/upload",
        headers=auth_headers,
        data={"project_id": str(project.id), "requirement_name": "Big", "depth": "standard"},
        files={"file": ("big.md", b"x" * (1024 * 1024 + 1), "text/markdown")},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_list_and_get_analysis(client, auth_headers, db_session, project, regular_user):
    task = build_analysis_task(
        project_id=project.id,
        user_id=regular_user.id,
        status=TaskStatus.COMPLETED,
        context_json={"step_results": {"a": {"success": True, "confidence": 0.9}}},
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    list_response = await client.get("/api/analyses", headers=auth_headers)
    get_response = await client.get(f"/api/analyses/{task.id}", headers=auth_headers)

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == task.id
    assert get_response.status_code == 200
    assert get_response.json()["step_summary"] == {"a": {"success": True, "confidence": 0.9}}


@pytest.mark.asyncio
async def test_retry_analysis_resets_failed_task(client, auth_headers, db_session, project, regular_user, monkeypatch):
    calls = []

    async def fake_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("reqradar.web.api.analyses._run_analysis_background", fake_run)
    task = build_analysis_task(
        project_id=project.id,
        user_id=regular_user.id,
        status=TaskStatus.FAILED,
        error_message="failed",
        context_json={"old": True},
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.post(f"/api/analyses/{task.id}/retry", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == TaskStatus.PENDING.value
    assert calls


@pytest.mark.asyncio
async def test_cancel_analysis_updates_pending_task(client, auth_headers, db_session, project, regular_user):
    task = build_analysis_task(
        project_id=project.id,
        user_id=regular_user.id,
        status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.post(f"/api/analyses/{task.id}/cancel", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"success": True, "status": "cancelled"}


@pytest.mark.asyncio
async def test_cancel_completed_analysis_returns_400(client, auth_headers, db_session, project, regular_user):
    task = build_analysis_task(
        project_id=project.id,
        user_id=regular_user.id,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.post(f"/api/analyses/{task.id}/cancel", headers=auth_headers)

    assert response.status_code == 400
