import pytest

from reqradar.web.models import PendingChange
from reqradar.web.services.version_service import VersionService
from tests.factories import build_analysis_task, build_project


@pytest.fixture
async def owned_project(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="gap_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_synonyms_crud(client, auth_headers, owned_project):
    create_response = await client.post(
        "/api/synonyms",
        headers=auth_headers,
        json={
            "project_id": owned_project.id,
            "business_term": "客户",
            "code_terms": ["customer", "client"],
            "priority": 10,
        },
    )
    assert create_response.status_code == 201
    synonym_id = create_response.json()["id"]

    list_response = await client.get(
        "/api/synonyms", headers=auth_headers, params={"project_id": owned_project.id}
    )
    assert list_response.status_code == 200
    assert list_response.json()[0]["business_term"] == "客户"

    update_response = await client.put(
        f"/api/synonyms/{synonym_id}",
        headers=auth_headers,
        json={"business_term": "用户", "code_terms": ["user"], "priority": 5},
    )
    assert update_response.status_code == 200
    assert update_response.json()["code_terms"] == ["user"]

    delete_response = await client.delete(
        f"/api/synonyms/{synonym_id}",
        headers=auth_headers,
        params={"project_id": owned_project.id},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_synonym_update_rejects_cross_project_access(client, auth_headers, db_session, admin_user):
    from reqradar.web.models import SynonymMapping

    other_project = build_project(owner_id=admin_user.id, name="other_synonym_project")
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)
    mapping = SynonymMapping(
        project_id=other_project.id,
        business_term="越权",
        code_terms=["bad"],
        created_by=admin_user.id,
    )
    db_session.add(mapping)
    await db_session.commit()
    await db_session.refresh(mapping)

    response = await client.put(
        f"/api/synonyms/{mapping.id}", headers=auth_headers, json={"priority": 1}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_evidence_list_and_detail(client, auth_headers, db_session, owned_project, regular_user):
    task = build_analysis_task(project_id=owned_project.id, user_id=regular_user.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    service = VersionService(db_session)
    await service.create_version(
        task.id,
        {"summary": "ok"},
        {
            "evidence_list": [
                {
                    "id": "ev-1",
                    "type": "code",
                    "source": "app.py",
                    "content": "evidence content",
                    "confidence": "high",
                    "dimensions": ["scope"],
                }
            ]
        },
        "# Report",
        "<h1>Report</h1>",
    )

    list_response = await client.get(f"/api/analyses/{task.id}/evidence", headers=auth_headers)
    detail_response = await client.get(
        f"/api/analyses/{task.id}/evidence/ev-1", headers=auth_headers
    )

    assert list_response.status_code == 200
    assert list_response.json()["evidence"][0]["id"] == "ev-1"
    assert detail_response.status_code == 200
    assert detail_response.json()["content"] == "evidence content"


@pytest.mark.asyncio
async def test_evidence_detail_missing_returns_404(client, auth_headers, db_session, owned_project, regular_user):
    task = build_analysis_task(project_id=owned_project.id, user_id=regular_user.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.get(f"/api/analyses/{task.id}/evidence/missing", headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reject_pending_change(client, auth_headers, db_session, owned_project):
    change = PendingChange(
        project_id=owned_project.id,
        change_type="profile",
        target_id="overview",
        old_value="old",
        new_value="new",
        diff="diff",
        source="test",
        status="pending",
    )
    db_session.add(change)
    await db_session.commit()
    await db_session.refresh(change)

    response = await client.post(
        f"/api/projects/{owned_project.id}/pending-changes/{change.id}/reject",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
