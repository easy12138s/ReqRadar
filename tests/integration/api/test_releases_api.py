import pytest

from tests.factories import build_project

@pytest.fixture
async def project(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="releases_api_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project

@pytest.fixture
async def release_data(project):
    return {
        "project_id": project.id,
        "release_code": "REQ-001",
        "title": "Initial Release",
        "content": "Release content here",
    }

@pytest.fixture
async def create_release(client, auth_headers, release_data):
    async def _create(**overrides):
        data = {**release_data, **overrides}
        return await client.post("/api/releases", headers=auth_headers, json=data)

    return _create
async def test_create_release_returns_201(client, auth_headers, release_data):
    response = await client.post("/api/releases", headers=auth_headers, json=release_data)

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == release_data["project_id"]
    assert body["release_code"] == release_data["release_code"]
    assert body["title"] == release_data["title"]
    assert body["content"] == release_data["content"]
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["published_at"] is None
    assert body["archived_at"] is None
    assert body["id"] is not None
    assert body["created_at"] is not None
async def test_create_release_auto_increments_version(client, auth_headers, release_data):
    first = await client.post("/api/releases", headers=auth_headers, json=release_data)
    second = await client.post("/api/releases", headers=auth_headers, json=release_data)

    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
async def test_create_release_with_optional_fields(client, auth_headers, project):
    response = await client.post(
        "/api/releases",
        headers=auth_headers,
        json={
            "project_id": project.id,
            "release_code": "REQ-OPT",
            "title": "With Options",
            "content": "Content",
            "context_json": {"key": "value"},
        },
    )

    assert response.status_code == 201
    assert response.json()["context_json"] == {"key": "value"}
async def test_create_release_unauthenticated(client, release_data):
    response = await client.post("/api/releases", json=release_data)

    assert response.status_code == 401
async def test_create_release_missing_required_fields(client, auth_headers):
    response = await client.post(
        "/api/releases",
        headers=auth_headers,
        json={"release_code": "REQ-MISSING"},
    )

    assert response.status_code == 422
async def test_create_release_invalid_field_types(client, auth_headers, project):
    response = await client.post(
        "/api/releases",
        headers=auth_headers,
        json={
            "project_id": "not_an_int",
            "release_code": "REQ-BAD",
            "title": "Bad",
            "content": "Bad",
        },
    )

    assert response.status_code == 422
async def test_list_releases_returns_list(client, auth_headers, create_release):
    await create_release()
    await create_release()

    response = await client.get("/api/releases", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) == 2
async def test_list_releases_empty(client, auth_headers):
    response = await client.get("/api/releases", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []
async def test_list_releases_unauthenticated(client):
    response = await client.get("/api/releases")

    assert response.status_code == 401
async def test_list_releases_filter_by_project(
    client, auth_headers, create_release, db_session, regular_user
):
    other_project = build_project(owner_id=regular_user.id, name="other_releases_project")
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)

    await create_release()
    await create_release(project_id=other_project.id, release_code="REQ-OTHER")

    response = await client.get(
        "/api/releases",
        headers=auth_headers,
        params={"project_id": other_project.id},
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["project_id"] == other_project.id
async def test_list_releases_filter_by_status(client, auth_headers, create_release):
    await create_release()
    create_resp = await create_release(release_code="REQ-002")
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    response = await client.get(
        "/api/releases",
        headers=auth_headers,
        params={"status": "published"},
    )

    assert response.status_code == 200
    results = response.json()
    assert all(r["status"] == "published" for r in results)
async def test_list_releases_pagination(client, auth_headers, create_release):
    for i in range(5):
        await create_release(release_code=f"REQ-PAGE-{i}")

    page1 = await client.get(
        "/api/releases", headers=auth_headers, params={"limit": 2, "offset": 0}
    )
    page2 = await client.get(
        "/api/releases", headers=auth_headers, params={"limit": 2, "offset": 2}
    )

    assert page1.status_code == 200
    assert page2.status_code == 200
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    assert page1.json()[0]["id"] != page2.json()[0]["id"]
async def test_get_release_returns_single(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.get(f"/api/releases/{release_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == release_id
    assert response.json()["release_code"] == "REQ-001"
async def test_get_release_not_found(client, auth_headers):
    response = await client.get("/api/releases/99999", headers=auth_headers)

    assert response.status_code == 404
async def test_get_release_unauthenticated(client, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.get(f"/api/releases/{release_id}")

    assert response.status_code == 401
async def test_update_release_draft_success(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/releases/{release_id}",
        headers=auth_headers,
        json={"title": "Updated Title", "content": "Updated Content"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["content"] == "Updated Content"
async def test_update_release_partial(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/releases/{release_id}",
        headers=auth_headers,
        json={"title": "New Title Only"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "New Title Only"
    assert response.json()["content"] == create_resp.json()["content"]
async def test_update_release_context_json(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/releases/{release_id}",
        headers=auth_headers,
        json={"context_json": {"updated": True}},
    )

    assert response.status_code == 200
    assert response.json()["context_json"] == {"updated": True}
async def test_update_release_not_found(client, auth_headers):
    response = await client.put(
        "/api/releases/99999",
        headers=auth_headers,
        json={"title": "Ghost"},
    )

    assert response.status_code == 404
async def test_update_release_non_draft_returns_400(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    response = await client.put(
        f"/api/releases/{release_id}",
        headers=auth_headers,
        json={"title": "Blocked Update"},
    )

    assert response.status_code == 400
async def test_update_release_unauthenticated(client, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/releases/{release_id}",
        json={"title": "No Auth"},
    )

    assert response.status_code == 401
async def test_publish_release_draft_to_published(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None
async def test_publish_release_non_draft_returns_400(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    response = await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    assert response.status_code == 400
async def test_publish_release_unauthenticated(client, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.post(f"/api/releases/{release_id}/publish")

    assert response.status_code == 401
async def test_archive_release_published_to_archived(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    response = await client.post(f"/api/releases/{release_id}/archive", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "archived"
    assert body["archived_at"] is not None
async def test_archive_release_draft_returns_400(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.post(f"/api/releases/{release_id}/archive", headers=auth_headers)

    assert response.status_code == 400
async def test_archive_release_unauthenticated(client, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.post(f"/api/releases/{release_id}/archive")

    assert response.status_code == 401
async def test_delete_release_draft_success(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.delete(f"/api/releases/{release_id}", headers=auth_headers)

    assert response.status_code == 204

    get_response = await client.get(f"/api/releases/{release_id}", headers=auth_headers)
    assert get_response.status_code == 404
async def test_delete_release_non_draft_returns_400(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    response = await client.delete(f"/api/releases/{release_id}", headers=auth_headers)

    assert response.status_code == 400
async def test_delete_release_not_found(client, auth_headers):
    response = await client.delete("/api/releases/99999", headers=auth_headers)

    assert response.status_code == 404
async def test_delete_release_unauthenticated(client, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]

    response = await client.delete(f"/api/releases/{release_id}")

    assert response.status_code == 401
async def test_full_lifecycle_draft_publish_archive(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    body = create_resp.json()

    assert body["status"] == "draft"
    assert body["published_at"] is None
    assert body["archived_at"] is None

    publish_resp = await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)
    assert publish_resp.json()["status"] == "published"
    assert publish_resp.json()["published_at"] is not None

    archive_resp = await client.post(f"/api/releases/{release_id}/archive", headers=auth_headers)
    assert archive_resp.json()["status"] == "archived"
    assert archive_resp.json()["archived_at"] is not None
async def test_cannot_update_published_release(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    response = await client.put(
        f"/api/releases/{release_id}",
        headers=auth_headers,
        json={"content": "blocked"},
    )

    assert response.status_code == 400
async def test_cannot_update_archived_release(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)
    await client.post(f"/api/releases/{release_id}/archive", headers=auth_headers)

    response = await client.put(
        f"/api/releases/{release_id}",
        headers=auth_headers,
        json={"content": "blocked"},
    )

    assert response.status_code == 400
async def test_cannot_delete_published_release(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)

    response = await client.delete(f"/api/releases/{release_id}", headers=auth_headers)

    assert response.status_code == 400
async def test_cannot_delete_archived_release(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)
    await client.post(f"/api/releases/{release_id}/archive", headers=auth_headers)

    response = await client.delete(f"/api/releases/{release_id}", headers=auth_headers)

    assert response.status_code == 400
async def test_cannot_archive_already_archived(client, auth_headers, create_release):
    create_resp = await create_release()
    release_id = create_resp.json()["id"]
    await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)
    await client.post(f"/api/releases/{release_id}/archive", headers=auth_headers)

    response = await client.post(f"/api/releases/{release_id}/archive", headers=auth_headers)

    assert response.status_code == 400

class TestReleaseAuthorization:
    async def test_create_release_for_other_user_project_returns_403(
        self, client, admin_headers, db_session, regular_user
    ):
        project = build_project(owner_id=regular_user.id, name="authz_test_project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        response = await client.post(
            "/api/releases",
            headers=admin_headers,
            json={
                "project_id": project.id,
                "release_code": "AUTH-001",
                "title": "Unauthorized",
                "content": "test",
            },
        )
        assert response.status_code == 403
    async def test_get_other_user_release_returns_403(self, client, admin_headers, create_release):
        create_resp = await create_release()
        release_id = create_resp.json()["id"]
        response = await client.get(f"/api/releases/{release_id}", headers=admin_headers)
        assert response.status_code == 403
    async def test_update_other_user_release_returns_403(
        self, client, admin_headers, create_release
    ):
        create_resp = await create_release()
        release_id = create_resp.json()["id"]
        response = await client.put(
            f"/api/releases/{release_id}", headers=admin_headers, json={"title": "Hacked"}
        )
        assert response.status_code == 403
    async def test_publish_other_user_release_returns_403(
        self, client, admin_headers, create_release
    ):
        create_resp = await create_release()
        release_id = create_resp.json()["id"]
        response = await client.post(f"/api/releases/{release_id}/publish", headers=admin_headers)
        assert response.status_code == 403
    async def test_archive_other_user_release_returns_403(
        self, client, admin_headers, auth_headers, create_release
    ):
        create_resp = await create_release()
        release_id = create_resp.json()["id"]
        await client.post(f"/api/releases/{release_id}/publish", headers=auth_headers)
        response = await client.post(f"/api/releases/{release_id}/archive", headers=admin_headers)
        assert response.status_code == 403
    async def test_delete_other_user_release_returns_403(
        self, client, admin_headers, create_release
    ):
        create_resp = await create_release()
        release_id = create_resp.json()["id"]
        response = await client.delete(f"/api/releases/{release_id}", headers=admin_headers)
        assert response.status_code == 403
    async def test_list_releases_with_unauthorized_project_filter_returns_403(
        self, client, admin_headers, db_session, regular_user
    ):
        project = build_project(owner_id=regular_user.id, name="authz_list_project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        response = await client.get(
            "/api/releases", headers=admin_headers, params={"project_id": project.id}
        )
        assert response.status_code == 403
