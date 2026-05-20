import pytest

from reqradar.web.enums import TaskStatus
from tests.factories import build_analysis_task, build_project

pytestmark = pytest.mark.integration


class TestMemoryEndpoints:
    """项目记忆端点 — 术语/模块/团队/历史。"""

    async def test_get_terminology_empty(self, client, auth_headers, sample_repo):
        """新项目应返回空术语列表。"""
        resp = await client.post(
            "/api/projects/from-local",
            headers=auth_headers,
            json={
                "name": "memory-test-proj",
                "description": "Test",
                "local_path": str(sample_repo),
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp2 = await client.get(f"/api/projects/{pid}/terminology", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json() == []

    async def test_get_modules_empty(self, client, auth_headers, sample_repo):
        """新项目应返回空模块列表。"""
        resp = await client.post(
            "/api/projects/from-local",
            headers=auth_headers,
            json={
                "name": "memory-test-proj2",
                "description": "Test",
                "local_path": str(sample_repo),
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp2 = await client.get(f"/api/projects/{pid}/modules", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json() == []

    async def test_get_team_empty(self, client, auth_headers, sample_repo):
        """get_team 硬编码返回空列表。"""
        resp = await client.post(
            "/api/projects/from-local",
            headers=auth_headers,
            json={
                "name": "memory-test-proj3",
                "description": "Test",
                "local_path": str(sample_repo),
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp2 = await client.get(f"/api/projects/{pid}/team", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json() == []

    async def test_get_history_empty(self, client, auth_headers, sample_repo):
        """无分析任务时应返回空历史。"""
        resp = await client.post(
            "/api/projects/from-local",
            headers=auth_headers,
            json={
                "name": "memory-test-proj4",
                "description": "Test",
                "local_path": str(sample_repo),
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp2 = await client.get(f"/api/projects/{pid}/history", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json() == []

    async def test_get_history_with_task(self, client, auth_headers, db_session, regular_user):
        """有分析任务时应返回历史记录。"""
        project = build_project(owner_id=regular_user.id, name="history-proj")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        task = build_analysis_task(
            project_id=project.id,
            user_id=regular_user.id,
            status=TaskStatus.COMPLETED,
            requirement_name="REQ-001",
            context_json={
                "deep_analysis": {"risk_level": "high"},
                "understanding": {"summary": "Test summary"},
            },
        )
        db_session.add(task)
        await db_session.commit()

        resp = await client.get(f"/api/projects/{project.id}/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["requirement_id"] == "REQ-001"
        assert data[0]["risk_level"] == "high"
        assert data[0]["summary"] == "Test summary"


class TestMemoryUnauthorized:
    """未认证和非所有者访问。"""

    async def test_terminology_unauthenticated(self, client):
        resp = await client.get("/api/projects/1/terminology")
        assert resp.status_code in (401, 403)

    async def test_modules_unauthenticated(self, client):
        resp = await client.get("/api/projects/1/modules")
        assert resp.status_code in (401, 403)

    async def test_team_unauthenticated(self, client):
        resp = await client.get("/api/projects/1/team")
        assert resp.status_code in (401, 403)

    async def test_history_unauthenticated(self, client):
        resp = await client.get("/api/projects/1/history")
        assert resp.status_code in (401, 403)

    async def test_terminology_not_found(self, client, auth_headers):
        """不存在的项目应返回 404。"""
        resp = await client.get("/api/projects/999999/terminology", headers=auth_headers)
        assert resp.status_code == 404

    async def test_modules_not_found(self, client, auth_headers):
        resp = await client.get("/api/projects/999999/modules", headers=auth_headers)
        assert resp.status_code == 404

    async def test_team_not_found(self, client, auth_headers):
        resp = await client.get("/api/projects/999999/team", headers=auth_headers)
        assert resp.status_code == 404

    async def test_history_not_found(self, client, auth_headers):
        resp = await client.get("/api/projects/999999/history", headers=auth_headers)
        assert resp.status_code == 404
