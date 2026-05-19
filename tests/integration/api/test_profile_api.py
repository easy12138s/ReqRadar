import pytest

from reqradar.modules.project_memory import ProjectMemory
from tests.factories import build_pending_change, build_project

pytestmark = pytest.mark.integration

_seq = __import__("itertools").count(1)


@pytest.fixture
async def owned_project(db_session, regular_user, app):
    project = build_project(owner_id=regular_user.id, name=f"profile_proj_{next(_seq)}")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    pm = ProjectMemory(storage_path=str(app.state.paths["memories"]), project_id=project.id)
    pm.load()
    pm.save()
    return project


class TestProfileEndpoints:
    """项目 Profile 端点测试。"""

    async def test_get_profile(self, client, auth_headers, owned_project):
        """获取项目 profile — 应返回默认空 profile。"""
        resp = await client.get(f"/api/projects/{owned_project.id}/profile", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "data" in data
        assert "overview" in data["data"]
        assert "tech_stack" in data["data"]

    async def test_update_profile_with_data(self, client, auth_headers, owned_project):
        """通过 data 字段更新 profile。"""
        resp = await client.put(
            f"/api/projects/{owned_project.id}/profile",
            headers=auth_headers,
            json={"data": {"overview": "Updated overview"}},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["overview"] == "Updated overview"

    async def test_update_profile_with_content(self, client, auth_headers, owned_project):
        """通过 content 字段更新 profile。"""
        resp = await client.put(
            f"/api/projects/{owned_project.id}/profile",
            headers=auth_headers,
            json={"content": "# Custom Profile\n\nCustom content"},
        )
        assert resp.status_code == 200
        assert "content" in resp.json()
        assert "Custom Profile" in resp.json()["content"]

    async def test_get_pending_changes_empty(self, client, auth_headers, owned_project):
        """新项目应无待定变更。"""
        resp = await client.get(
            f"/api/projects/{owned_project.id}/pending-changes", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_pending_changes_alias(self, client, auth_headers, owned_project):
        """profile/pending 别名端点。"""
        resp = await client.get(
            f"/api/projects/{owned_project.id}/profile/pending", headers=auth_headers
        )
        assert resp.status_code == 200

    async def test_accept_pending_change_profile_type(
        self, client, auth_headers, db_session, owned_project
    ):
        """Accept a pending change of type 'profile'。"""
        change = build_pending_change(
            project_id=owned_project.id,
            change_type="profile",
            target_id="overview",
            new_value="New overview",
        )
        db_session.add(change)
        await db_session.commit()
        await db_session.refresh(change)

        resp = await client.post(
            f"/api/projects/{owned_project.id}/pending-changes/{change.id}/accept",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    async def test_accept_pending_change_overview_updated(
        self, client, auth_headers, db_session, owned_project
    ):
        """Accept a pending change of type 'overview_updated'。"""
        change = build_pending_change(
            project_id=owned_project.id,
            change_type="overview_updated",
            target_id="overview",
            new_value="Updated via pending change",
        )
        db_session.add(change)
        await db_session.commit()
        await db_session.refresh(change)

        resp = await client.post(
            f"/api/projects/{owned_project.id}/pending-changes/{change.id}/accept",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    async def test_reject_pending_change(self, client, auth_headers, db_session, owned_project):
        """Reject a pending change。"""
        change = build_pending_change(
            project_id=owned_project.id,
            change_type="overview_updated",
            target_id="overview",
            new_value="Rejected value",
        )
        db_session.add(change)
        await db_session.commit()
        await db_session.refresh(change)

        resp = await client.post(
            f"/api/projects/{owned_project.id}/pending-changes/{change.id}/reject",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_accept_nonexistent_change(self, client, auth_headers, owned_project):
        """不存在的 change_id 应返回 404。"""
        resp = await client.post(
            f"/api/projects/{owned_project.id}/pending-changes/999999/accept",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_reject_nonexistent_change(self, client, auth_headers, owned_project):
        """不存在的 change_id reject 应返回 404。"""
        resp = await client.post(
            f"/api/projects/{owned_project.id}/pending-changes/999999/reject",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_accept_pending_change_alias_path(
        self, client, auth_headers, db_session, owned_project
    ):
        """profile/pending/{id} 别名路径。"""
        change = build_pending_change(
            project_id=owned_project.id,
            change_type="profile",
            target_id="overview",
            new_value="Alias path value",
        )
        db_session.add(change)
        await db_session.commit()
        await db_session.refresh(change)

        resp = await client.post(
            f"/api/projects/{owned_project.id}/profile/pending/{change.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"


class TestProfileUnauthorized:
    """未认证和非所有者访问。"""

    async def test_get_profile_unauthenticated(self, client):
        resp = await client.get("/api/projects/1/profile")
        assert resp.status_code in (401, 403)

    async def test_update_profile_unauthenticated(self, client):
        resp = await client.put("/api/projects/1/profile", json={"content": "test"})
        assert resp.status_code in (401, 403)

    async def test_pending_changes_unauthenticated(self, client):
        resp = await client.get("/api/projects/1/pending-changes")
        assert resp.status_code in (401, 403)

    async def test_accept_pending_change_unauthenticated(self, client):
        resp = await client.post("/api/projects/1/pending-changes/1/accept")
        assert resp.status_code in (401, 403)

    async def test_reject_pending_change_unauthenticated(self, client):
        resp = await client.post("/api/projects/1/pending-changes/1/reject")
        assert resp.status_code in (401, 403)

    async def test_profile_not_found_project(self, client, auth_headers):
        """不存在的项目应返回 404。"""
        resp = await client.get("/api/projects/999999/profile", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_profile_not_found_project(self, client, auth_headers):
        """不存在的项目更新 profile 应返回 404。"""
        resp = await client.put(
            "/api/projects/999999/profile",
            headers=auth_headers,
            json={"content": "test"},
        )
        assert resp.status_code == 404

    async def test_pending_changes_not_found_project(self, client, auth_headers):
        """不存在的项目 pending-changes 应返回 404。"""
        resp = await client.get("/api/projects/999999/pending-changes", headers=auth_headers)
        assert resp.status_code == 404

    async def test_profile_wrong_owner(self, client, auth_headers, db_session, admin_user):
        """非所有者访问项目 profile 应返回 404。"""
        project = build_project(owner_id=admin_user.id, name="other_profile_project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        resp = await client.get(f"/api/projects/{project.id}/profile", headers=auth_headers)
        assert resp.status_code == 404

    async def test_pending_changes_wrong_owner(self, client, auth_headers, db_session, admin_user):
        """非所有者访问 pending-changes 应返回 404。"""
        project = build_project(owner_id=admin_user.id, name="other_pending_project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        resp = await client.get(f"/api/projects/{project.id}/pending-changes", headers=auth_headers)
        assert resp.status_code == 404
