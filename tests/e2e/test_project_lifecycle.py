"""E2E 测试 — 项目管理全流程 (mock-mode)"""

import pytest

pytestmark = [pytest.mark.e2e]


class TestProjectFromLocalLifecycle:
    """from-local 项目完整生命周期。"""

    async def test_create_project_from_local(self, e2e_user, tmp_path):
        """创建本地项目。"""
        client, headers, *_ = e2e_user
        repo = tmp_path / "lifecycle_repo"
        repo.mkdir()
        (repo / "main.py").write_text("print('hello')", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={
                "name": "lifecycle-proj",
                "description": "E2E lifecycle",
                "local_path": str(repo),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "lifecycle-proj"
        assert data["source_type"] == "local"
        assert "id" in data

    async def test_list_projects(self, e2e_user, tmp_path):
        """创建后能在列表中看到。"""
        client, headers, *_ = e2e_user
        repo = tmp_path / "list_repo"
        repo.mkdir()
        (repo / "app.py").write_text("# app", encoding="utf-8")

        await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={"name": "list-proj", "description": "List test", "local_path": str(repo)},
        )

        resp = await client.get("/api/projects", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_project_detail(self, e2e_user, tmp_path):
        """获取项目详情。"""
        client, headers, *_ = e2e_user
        repo = tmp_path / "detail_repo"
        repo.mkdir()
        (repo / "main.py").write_text("# detail", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={"name": "detail-proj", "description": "Detail test", "local_path": str(repo)},
        )
        pid = resp.json()["id"]

        resp2 = await client.get(f"/api/projects/{pid}", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["id"] == pid

    async def test_update_project(self, e2e_user, tmp_path):
        """更新项目描述。"""
        client, headers, *_ = e2e_user
        repo = tmp_path / "update_repo"
        repo.mkdir()
        (repo / "main.py").write_text("# update", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={"name": "update-proj", "description": "Before", "local_path": str(repo)},
        )
        pid = resp.json()["id"]

        resp2 = await client.put(
            f"/api/projects/{pid}",
            headers=headers,
            json={"description": "After update"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["description"] == "After update"

    async def test_delete_project(self, e2e_user, tmp_path):
        """删除项目。"""
        client, headers, *_ = e2e_user
        repo = tmp_path / "delete_repo"
        repo.mkdir()
        (repo / "main.py").write_text("# delete", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={"name": "delete-proj", "description": "To delete", "local_path": str(repo)},
        )
        pid = resp.json()["id"]

        resp2 = await client.delete(f"/api/projects/{pid}", headers=headers)
        assert resp2.status_code == 200

        resp3 = await client.get(f"/api/projects/{pid}", headers=headers)
        assert resp3.status_code == 404

    async def test_get_project_files(self, e2e_user, tmp_path):
        """浏览项目文件。"""
        client, headers, *_ = e2e_user
        repo = tmp_path / "files_repo"
        repo.mkdir()
        (repo / "main.py").write_text("# files", encoding="utf-8")
        (repo / "README.md").write_text("# README", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={"name": "files-proj", "description": "Files test", "local_path": str(repo)},
        )
        pid = resp.json()["id"]

        resp2 = await client.get(f"/api/projects/{pid}/files", headers=headers)
        assert resp2.status_code == 200

    async def test_invalid_project_name(self, e2e_user, tmp_path):
        """项目名不符合 pattern 应被拒绝。"""
        client, headers, *_ = e2e_user

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={"name": "invalid name!", "description": "Bad name", "local_path": "/tmp"},
        )
        assert resp.status_code in (400, 422)


class TestProjectMemory:
    """项目记忆端点。"""

    async def test_terminology_empty(self, e2e_project):
        """新项目术语列表为空。"""
        client, headers, *_, project_id = e2e_project

        resp = await client.get(f"/api/projects/{project_id}/terminology", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_modules_empty(self, e2e_project):
        client, headers, *_, project_id = e2e_project

        resp = await client.get(f"/api/projects/{project_id}/modules", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_team_empty(self, e2e_project):
        client, headers, *_, project_id = e2e_project

        resp = await client.get(f"/api/projects/{project_id}/team", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_history_empty(self, e2e_project):
        client, headers, *_, project_id = e2e_project

        resp = await client.get(f"/api/projects/{project_id}/history", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []
