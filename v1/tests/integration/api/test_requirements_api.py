import pytest

from tests.factories import build_project, build_requirement_document


@pytest.fixture
async def requirement_doc(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="requirement_api_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    doc = build_requirement_document(project.id, regular_user.id, title="Initial Requirement")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def test_get_update_list_and_delete_requirement(client, auth_headers, requirement_doc):
    get_response = await client.get(f"/api/requirements/{requirement_doc.id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Initial Requirement"

    update_response = await client.put(
        f"/api/requirements/{requirement_doc.id}",
        headers=auth_headers,
        json={"title": "Updated Requirement", "consolidated_text": "# Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["updated"] is True

    list_response = await client.get(
        "/api/requirements",
        headers=auth_headers,
        params={"project_id": requirement_doc.project_id},
    )
    assert list_response.status_code == 200
    assert list_response.json()[0]["title"] == "Updated Requirement"

    delete_response = await client.delete(
        f"/api/requirements/{requirement_doc.id}", headers=auth_headers
    )
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}


async def test_missing_requirement_returns_404(client, auth_headers):
    response = await client.get("/api/requirements/99999", headers=auth_headers)
    assert response.status_code == 404


async def test_put_nonexistent_requirement_returns_404(client, auth_headers):
    response = await client.put(
        "/api/requirements/99999",
        headers=auth_headers,
        json={"title": "x", "consolidated_text": "# x"},
    )
    assert response.status_code == 404


async def test_delete_nonexistent_requirement_returns_404(client, auth_headers):
    response = await client.delete("/api/requirements/99999", headers=auth_headers)
    assert response.status_code == 404


async def test_list_requirements_returns_empty_list(client, auth_headers, db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="empty_req_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    response = await client.get(
        "/api/requirements",
        headers=auth_headers,
        params={"project_id": project.id},
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_preprocess_rejects_unsupported_file_type(
    client, auth_headers, db_session, regular_user
):
    project = build_project(owner_id=regular_user.id, name="upload_requirement_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    response = await client.post(
        "/api/requirements/preprocess",
        headers=auth_headers,
        data={"project_id": str(project.id), "title": "Bad File"},
        files={"files": ("bad.exe", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


class TestUnauthenticated:
    """未认证访问应返回 401/403。"""

    async def test_preprocess_unauthenticated(self, client):
        resp = await client.post(
            "/api/requirements/preprocess",
            data={"project_id": "1", "title": "Test"},
            files={"files": ("test.md", b"test", "text/markdown")},
        )
        assert resp.status_code in (401, 403)

    async def test_get_unauthenticated(self, client):
        resp = await client.get("/api/requirements/1")
        assert resp.status_code in (401, 403)

    async def test_update_unauthenticated(self, client):
        resp = await client.put("/api/requirements/1", json={"title": "x"})
        assert resp.status_code in (401, 403)

    async def test_delete_unauthenticated(self, client):
        resp = await client.delete("/api/requirements/1")
        assert resp.status_code in (401, 403)

    async def test_list_unauthenticated(self, client):
        resp = await client.get("/api/requirements", params={"project_id": 1})
        assert resp.status_code in (401, 403)
