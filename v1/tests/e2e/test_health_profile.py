"""Health、Metrics 和 Profile 端点 E2E 测试。"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


class TestHealthEndpoint:
    """GET /health — 无需认证。"""

    async def test_health_returns_200(self, client, app):
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_response_format(self, client, app):
        resp = await client.get("/health")
        assert resp.headers.get("content-type", "").startswith("application/json")
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert isinstance(data["database"], bool)

    async def test_health_status_value(self, client, app):
        resp = await client.get("/health")
        data = resp.json()
        assert data["status"] in ("ok", "degraded")

    async def test_health_no_auth_required(self, client, app):
        resp = await client.get("/health")
        assert resp.status_code != 401


class TestMetricsEndpoint:
    """GET /api/metrics — 需要认证。"""

    async def test_metrics_requires_auth(self, client, app):
        resp = await client.get("/api/metrics")
        assert resp.status_code == 401

    async def test_metrics_returns_200_with_auth(self, test_user, app):
        client, headers, _token, _user_data = test_user
        resp = await client.get("/api/metrics", headers=headers)
        assert resp.status_code == 200

    async def test_metrics_response_format(self, test_user, app):
        client, headers, _token, _user_data = test_user
        resp = await client.get("/api/metrics", headers=headers)
        data = resp.json()
        assert "project_count" in data
        assert "task_counts" in data
        assert isinstance(data["project_count"], int)
        assert isinstance(data["task_counts"], dict)

    async def test_metrics_task_counts_keys(self, test_user, app):
        client, headers, _token, _user_data = test_user
        resp = await client.get("/api/metrics", headers=headers)
        task_counts = resp.json()["task_counts"]
        for key in ("pending", "running", "completed", "failed"):
            assert key in task_counts
            assert isinstance(task_counts[key], int)


class TestProfileE2E:
    """Profile 端点 E2E 测试 — 使用 e2e fixtures。"""

    async def test_profile_lifecycle(self, e2e_client, e2e_user, tmp_path):
        client, headers, _token, _user_data, _user_id = e2e_user

        repo = tmp_path / "profile_repo"
        repo.mkdir()
        (repo / "main.py").write_text("print('hello')", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={
                "name": "profile-e2e",
                "description": "Test",
                "local_path": str(repo),
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp2 = await client.get(f"/api/projects/{pid}/profile", headers=headers)
        assert resp2.status_code == 200
        body = resp2.json()
        assert "content" in body
        assert "data" in body

        resp3 = await client.put(
            f"/api/projects/{pid}/profile",
            headers=headers,
            json={"data": {"overview": "E2E test overview"}},
        )
        assert resp3.status_code == 200
        assert resp3.json()["data"]["overview"] == "E2E test overview"

        resp4 = await client.get(f"/api/projects/{pid}/pending-changes", headers=headers)
        assert resp4.status_code == 200
        assert resp4.json() == []

    async def test_profile_requires_auth(self, e2e_client, e2e_user, tmp_path):
        client, headers, _token, _user_data, _user_id = e2e_user

        repo = tmp_path / "profile_auth_repo"
        repo.mkdir()
        (repo / "main.py").write_text("print('hello')", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={
                "name": "profile-auth-e2e",
                "description": "Test",
                "local_path": str(repo),
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp_no_auth = await client.get(f"/api/projects/{pid}/profile")
        assert resp_no_auth.status_code == 401

    async def test_profile_not_found(self, e2e_client, e2e_user):
        client, headers, _token, _user_data, _user_id = e2e_user

        resp = await client.get("/api/projects/999999/profile", headers=headers)
        assert resp.status_code == 404

    # BUG-1: Profile PUT content 分支未创建父目录
    # 发现阶段: P3-2 | 测试文件: tests/e2e/test_health_profile.py
    # 测试用例: test_profile_update_content
    # 复现步骤: PUT /api/projects/{pid}/profile 传 {"content": "..."} 时，
    # update_profile 直接写 pm.file_path 而未调用 pm.save()（后者会 mkdir -p），
    # 导致 FileNotFoundError（父目录 memories/projects/{pid}/ 不存在）。
    # 期望结果: 200 + content 更新成功 | 实际结果: 500 FileNotFoundError
    # 影响范围: Profile content 更新路径 | 是否阻塞: N
    @pytest.mark.xfail(
        reason=(
            "BUG-1: Profile PUT content 分支未创建父目录，"
            "直接写 pm.file_path 导致 FileNotFoundError"
        )
    )
    async def test_profile_update_content(self, e2e_client, e2e_user, tmp_path):
        client, headers, _token, _user_data, _user_id = e2e_user

        repo = tmp_path / "profile_content_repo"
        repo.mkdir()
        (repo / "main.py").write_text("print('hello')", encoding="utf-8")

        resp = await client.post(
            "/api/projects/from-local",
            headers=headers,
            json={
                "name": "profile-content-e2e",
                "description": "Test",
                "local_path": str(repo),
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        new_content = "# Custom Profile\n\nUpdated via content field."
        resp2 = await client.put(
            f"/api/projects/{pid}/profile",
            headers=headers,
            json={"content": new_content},
        )
        assert resp2.status_code == 200
        assert resp2.json()["content"] == new_content
