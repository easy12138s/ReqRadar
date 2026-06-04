"""E2E 测试 — 需求发布(Release)完整生命周期：
创建→编辑→发布→归档→搜索、版本递增、仅草稿可删、跨项目 403。
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.fixture
async def release_project(e2e_user, tmp_path):
    """创建用于 release 测试的项目，yield (client, headers, project_id)。"""
    client, headers, _token, _user_data, _user_id = e2e_user
    repo = tmp_path / "release_repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('release test')", encoding="utf-8")
    resp = await client.post(
        "/api/projects/from-local",
        headers=headers,
        json={
            "name": "release-e2e-project",
            "description": "Release E2E test project",
            "local_path": str(repo),
        },
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]
    return client, headers, project_id


@pytest.fixture
async def other_user_project(e2e_client, e2e_app, e2e_session_factory, tmp_path):
    """注册另一个用户并创建项目，yield (other_client, other_headers, other_project_id)。"""
    from tests.factories import unique_email

    other_data = {
        "email": unique_email("other_release"),
        "password": "OtherPass123",
        "display_name": "Other Release User",
    }
    reg = await e2e_client.post("/api/auth/register", json=other_data)
    assert reg.status_code == 201
    login = await e2e_client.post(
        "/api/auth/login",
        json={"email": other_data["email"], "password": other_data["password"]},
    )
    assert login.status_code == 200
    other_token = login.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    repo = tmp_path / "other_release_repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('other')", encoding="utf-8")
    resp = await e2e_client.post(
        "/api/projects/from-local",
        headers=other_headers,
        json={
            "name": "other-release-project",
            "description": "Other user project",
            "local_path": str(repo),
        },
    )
    assert resp.status_code == 201
    other_project_id = resp.json()["id"]
    return e2e_client, other_headers, other_project_id


async def _create_release(client, headers, project_id, **overrides):
    """辅助：创建 release 并返回 response。"""
    data = {
        "project_id": project_id,
        "release_code": "E2E-001",
        "title": "E2E Release",
        "content": "E2E release content",
    }
    data.update(overrides)
    return await client.post("/api/releases", headers=headers, json=data)


class TestRequirementReleaseLifecycle:
    """创建 → 编辑 → 发布 → 归档 完整生命周期。"""

    async def test_full_lifecycle(self, release_project):
        client, headers, project_id = release_project

        # 1. 创建 release (draft)
        create_resp = await _create_release(client, headers, project_id)
        assert create_resp.status_code == 201
        body = create_resp.json()
        release_id = body["id"]
        assert body["status"] == "draft"
        assert body["version"] == 1
        assert body["published_at"] is None
        assert body["archived_at"] is None

        # 2. 编辑 draft release
        update_resp = await client.put(
            f"/api/releases/{release_id}",
            headers=headers,
            json={"title": "Updated E2E Release", "content": "Updated content"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Updated E2E Release"
        assert update_resp.json()["content"] == "Updated content"

        # 3. 发布 release (draft → published)
        publish_resp = await client.post(f"/api/releases/{release_id}/publish", headers=headers)
        assert publish_resp.status_code == 200
        assert publish_resp.json()["status"] == "published"
        assert publish_resp.json()["published_at"] is not None

        # 4. 归档 release (published → archived)
        archive_resp = await client.post(f"/api/releases/{release_id}/archive", headers=headers)
        assert archive_resp.status_code == 200
        assert archive_resp.json()["status"] == "archived"
        assert archive_resp.json()["archived_at"] is not None

        # 5. 验证归档后无法编辑
        edit_after_archive = await client.put(
            f"/api/releases/{release_id}",
            headers=headers,
            json={"title": "Should Fail"},
        )
        assert edit_after_archive.status_code == 400


class TestReleaseVersionIncrement:
    """多次创建相同 release_code 时版本号递增。"""

    async def test_version_auto_increment(self, release_project):
        client, headers, project_id = release_project

        first = await _create_release(client, headers, project_id, release_code="VER-INC")
        assert first.status_code == 201
        assert first.json()["version"] == 1

        second = await _create_release(client, headers, project_id, release_code="VER-INC")
        assert second.status_code == 201
        assert second.json()["version"] == 2

        third = await _create_release(client, headers, project_id, release_code="VER-INC")
        assert third.status_code == 201
        assert third.json()["version"] == 3


class TestReleaseDeleteOnlyDraft:
    """仅 draft 状态的 release 可以删除。"""

    async def test_delete_draft_succeeds(self, release_project):
        client, headers, project_id = release_project

        create_resp = await _create_release(client, headers, project_id, release_code="DEL-DRAFT")
        release_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/releases/{release_id}", headers=headers)
        assert delete_resp.status_code == 204

        get_resp = await client.get(f"/api/releases/{release_id}", headers=headers)
        assert get_resp.status_code == 404

    async def test_delete_published_returns_400(self, release_project):
        client, headers, project_id = release_project

        create_resp = await _create_release(client, headers, project_id, release_code="DEL-PUB")
        release_id = create_resp.json()["id"]
        await client.post(f"/api/releases/{release_id}/publish", headers=headers)

        delete_resp = await client.delete(f"/api/releases/{release_id}", headers=headers)
        assert delete_resp.status_code == 400

    async def test_delete_archived_returns_400(self, release_project):
        client, headers, project_id = release_project

        create_resp = await _create_release(client, headers, project_id, release_code="DEL-ARCH")
        release_id = create_resp.json()["id"]
        await client.post(f"/api/releases/{release_id}/publish", headers=headers)
        await client.post(f"/api/releases/{release_id}/archive", headers=headers)

        delete_resp = await client.delete(f"/api/releases/{release_id}", headers=headers)
        assert delete_resp.status_code == 400


class TestReleaseCrossProject403:
    """不同用户的项目之间 release 操作应返回 403。"""

    async def test_create_release_for_other_project_403(self, release_project, other_user_project):
        client, headers, _ = release_project
        _, _, other_project_id = other_user_project

        resp = await _create_release(client, headers, other_project_id, release_code="CROSS-CREATE")
        assert resp.status_code == 403

    async def test_get_other_user_release_403(self, release_project, other_user_project):
        client, headers, _ = release_project
        other_client, other_headers, other_project_id = other_user_project

        other_create = await _create_release(
            other_client, other_headers, other_project_id, release_code="CROSS-GET"
        )
        assert other_create.status_code == 201
        release_id = other_create.json()["id"]

        resp = await client.get(f"/api/releases/{release_id}", headers=headers)
        assert resp.status_code == 403

    async def test_update_other_user_release_403(self, release_project, other_user_project):
        client, headers, _ = release_project
        other_client, other_headers, other_project_id = other_user_project

        other_create = await _create_release(
            other_client, other_headers, other_project_id, release_code="CROSS-UPD"
        )
        release_id = other_create.json()["id"]

        resp = await client.put(
            f"/api/releases/{release_id}",
            headers=headers,
            json={"title": "Hacked"},
        )
        assert resp.status_code == 403

    async def test_publish_other_user_release_403(self, release_project, other_user_project):
        client, headers, _ = release_project
        other_client, other_headers, other_project_id = other_user_project

        other_create = await _create_release(
            other_client, other_headers, other_project_id, release_code="CROSS-PUB"
        )
        release_id = other_create.json()["id"]

        resp = await client.post(f"/api/releases/{release_id}/publish", headers=headers)
        assert resp.status_code == 403

    async def test_archive_other_user_release_403(self, release_project, other_user_project):
        client, headers, _ = release_project
        other_client, other_headers, other_project_id = other_user_project

        other_create = await _create_release(
            other_client, other_headers, other_project_id, release_code="CROSS-ARCH"
        )
        release_id = other_create.json()["id"]
        await other_client.post(f"/api/releases/{release_id}/publish", headers=other_headers)

        resp = await client.post(f"/api/releases/{release_id}/archive", headers=headers)
        assert resp.status_code == 403

    async def test_delete_other_user_release_403(self, release_project, other_user_project):
        client, headers, _ = release_project
        other_client, other_headers, other_project_id = other_user_project

        other_create = await _create_release(
            other_client, other_headers, other_project_id, release_code="CROSS-DEL"
        )
        release_id = other_create.json()["id"]

        resp = await client.delete(f"/api/releases/{release_id}", headers=headers)
        assert resp.status_code == 403


class TestReleaseSearch:
    """Release 列表搜索/筛选。"""

    async def test_list_releases_filter_by_status(self, release_project):
        client, headers, project_id = release_project

        await _create_release(client, headers, project_id, release_code="SEARCH-1")
        create2 = await _create_release(client, headers, project_id, release_code="SEARCH-2")
        await _create_release(client, headers, project_id, release_code="SEARCH-3")

        release_id2 = create2.json()["id"]
        await client.post(f"/api/releases/{release_id2}/publish", headers=headers)

        resp = await client.get(
            "/api/releases",
            headers=headers,
            params={"status": "published", "project_id": project_id},
        )
        assert resp.status_code == 200
        results = resp.json()
        assert all(r["status"] == "published" for r in results)
        assert len(results) == 1
        assert results[0]["release_code"] == "SEARCH-2"

    async def test_list_releases_filter_by_project(self, release_project):
        client, headers, project_id = release_project

        await _create_release(client, headers, project_id, release_code="PROJ-F-1")
        await _create_release(client, headers, project_id, release_code="PROJ-F-2")

        resp = await client.get(
            "/api/releases",
            headers=headers,
            params={"project_id": project_id},
        )
        assert resp.status_code == 200
        results = resp.json()
        assert all(r["project_id"] == project_id for r in results)
        assert len(results) >= 2
