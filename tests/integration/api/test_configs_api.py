import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from reqradar.web.models import Project, ProjectConfig, SystemConfig, UserConfig

pytestmark = pytest.mark.integration


class TestSystemConfig:
    """系统级配置 API — 需要管理员权限。"""

    async def test_list_system_configs_empty(self, client, admin_headers):
        resp = await client.get("/api/configs/system", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_set_and_get_system_config(self, client, admin_headers):
        resp = await client.put(
            "/api/configs/system/llm.model",
            headers=admin_headers,
            json={"value": "gpt-4o", "value_type": "string"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "llm.model"
        assert data["value"] == "gpt-4o"

        resp2 = await client.get("/api/configs/system/llm.model", headers=admin_headers)
        assert resp2.status_code == 200
        assert resp2.json()["value"] == "gpt-4o"

    async def test_list_system_configs_after_set(self, client, admin_headers):
        await client.put(
            "/api/configs/system/list.key",
            headers=admin_headers,
            json={"value": "list-val", "value_type": "string"},
        )
        resp = await client.get("/api/configs/system", headers=admin_headers)
        assert resp.status_code == 200
        keys = [item["key"] for item in resp.json()]
        assert "list.key" in keys

    async def test_delete_system_config(self, client, admin_headers):
        await client.put(
            "/api/configs/system/del.key",
            headers=admin_headers,
            json={"value": "to-delete", "value_type": "string"},
        )
        resp = await client.delete("/api/configs/system/del.key", headers=admin_headers)
        assert resp.status_code == 204

        resp2 = await client.get("/api/configs/system/del.key", headers=admin_headers)
        assert resp2.status_code == 404

    async def test_delete_nonexistent_system_config(self, client, admin_headers):
        resp = await client.delete("/api/configs/system/nonexistent.key", headers=admin_headers)
        assert resp.status_code == 404

    async def test_get_nonexistent_system_config(self, client, admin_headers):
        resp = await client.get("/api/configs/system/nonexistent.key", headers=admin_headers)
        assert resp.status_code == 404

    async def test_system_config_forbidden_for_regular_user(self, client, auth_headers):
        resp = await client.get("/api/configs/system", headers=auth_headers)
        assert resp.status_code == 403

    async def test_system_config_get_forbidden_for_regular_user(self, client, auth_headers):
        resp = await client.get("/api/configs/system/some.key", headers=auth_headers)
        assert resp.status_code == 403

    async def test_system_config_put_forbidden_for_regular_user(self, client, auth_headers):
        resp = await client.put(
            "/api/configs/system/some.key",
            headers=auth_headers,
            json={"value": "x", "value_type": "string"},
        )
        assert resp.status_code == 403

    async def test_system_config_delete_forbidden_for_regular_user(self, client, auth_headers):
        resp = await client.delete("/api/configs/system/some.key", headers=auth_headers)
        assert resp.status_code == 403

    async def test_put_empty_value_deletes_config(self, client, admin_headers):
        await client.put(
            "/api/configs/system/temp.key",
            headers=admin_headers,
            json={"value": "temp", "value_type": "string"},
        )
        resp = await client.put(
            "/api/configs/system/temp.key",
            headers=admin_headers,
            json={"value": "", "value_type": "string"},
        )
        assert resp.status_code == 204

        resp2 = await client.get("/api/configs/system/temp.key", headers=admin_headers)
        assert resp2.status_code == 404

    async def test_put_none_value_returns_existing(self, client, admin_headers):
        await client.put(
            "/api/configs/system/existing.key",
            headers=admin_headers,
            json={"value": "existing_val", "value_type": "string"},
        )
        resp = await client.put(
            "/api/configs/system/existing.key",
            headers=admin_headers,
            json={"value": None},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "existing_val"

    async def test_put_none_value_nonexistent_returns_404(self, client, admin_headers):
        resp = await client.put(
            "/api/configs/system/no.such.key",
            headers=admin_headers,
            json={"value": None},
        )
        assert resp.status_code == 404

    async def test_set_system_config_sensitive(self, client, admin_headers):
        resp = await client.put(
            "/api/configs/system/secret.key",
            headers=admin_headers,
            json={"value": "super-secret-value", "value_type": "string", "is_sensitive": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_sensitive"] is True
        assert "***" in data["value"]
        assert data["value"] != "super-secret-value"

    async def test_set_system_config_with_description(self, client, admin_headers):
        resp = await client.put(
            "/api/configs/system/desc.key",
            headers=admin_headers,
            json={"value": "val", "value_type": "string", "description": "A description"},
        )
        assert resp.status_code == 200

    async def test_system_config_unauthenticated(self, client):
        resp = await client.get("/api/configs/system")
        assert resp.status_code in (401, 403)


class TestProjectConfig:
    """项目级配置 API — 需要项目所有者权限。"""

    async def _create_project(self, client, auth_headers, sample_repo, name="cfg-proj"):
        resp = await client.post(
            "/api/projects/from-local",
            headers=auth_headers,
            json={"name": name, "description": "Test", "local_path": str(sample_repo)},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_list_project_configs_empty(self, client, auth_headers, sample_repo):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-list")
        resp = await client.get(f"/api/projects/{pid}/configs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_set_and_get_project_config(self, client, auth_headers, sample_repo):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-setget")
        resp = await client.put(
            f"/api/projects/{pid}/configs/llm.model",
            headers=auth_headers,
            json={"value": "claude-3", "value_type": "string"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "claude-3"

        resp2 = await client.get(f"/api/projects/{pid}/configs/llm.model", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["value"] == "claude-3"

    async def test_list_project_configs_after_set(self, client, auth_headers, sample_repo):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-listset")
        await client.put(
            f"/api/projects/{pid}/configs/some.key",
            headers=auth_headers,
            json={"value": "val", "value_type": "string"},
        )
        resp = await client.get(f"/api/projects/{pid}/configs", headers=auth_headers)
        assert resp.status_code == 200
        keys = [item["key"] for item in resp.json()]
        assert "some.key" in keys

    async def test_delete_project_config(self, client, auth_headers, sample_repo):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-del")
        await client.put(
            f"/api/projects/{pid}/configs/del.key",
            headers=auth_headers,
            json={"value": "to-delete", "value_type": "string"},
        )
        resp = await client.delete(f"/api/projects/{pid}/configs/del.key", headers=auth_headers)
        assert resp.status_code == 204

        resp2 = await client.get(f"/api/projects/{pid}/configs/del.key", headers=auth_headers)
        assert resp2.status_code == 404

    async def test_delete_nonexistent_project_config(self, client, auth_headers, sample_repo):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-del404")
        resp = await client.delete(
            f"/api/projects/{pid}/configs/nonexistent.key", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_get_nonexistent_project_config(self, client, auth_headers, sample_repo):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-get404")
        resp = await client.get(
            f"/api/projects/{pid}/configs/nonexistent.key", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_project_config_unauthorized(
        self, client, admin_headers, auth_headers, sample_repo
    ):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-unauth")
        resp = await client.get(f"/api/projects/{pid}/configs", headers=admin_headers)
        assert resp.status_code == 404

    async def test_project_config_put_unauthorized(
        self, client, admin_headers, auth_headers, sample_repo
    ):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-putunauth")
        resp = await client.put(
            f"/api/projects/{pid}/configs/some.key",
            headers=admin_headers,
            json={"value": "x", "value_type": "string"},
        )
        assert resp.status_code == 404

    async def test_project_config_delete_unauthorized(
        self, client, admin_headers, auth_headers, sample_repo
    ):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-delunauth")
        resp = await client.delete(f"/api/projects/{pid}/configs/some.key", headers=admin_headers)
        assert resp.status_code == 404

    async def test_project_config_nonexistent_project(self, client, auth_headers):
        resp = await client.get("/api/projects/99999/configs", headers=auth_headers)
        assert resp.status_code == 404

    async def test_put_empty_value_deletes_project_config(self, client, auth_headers, sample_repo):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-empty")
        await client.put(
            f"/api/projects/{pid}/configs/emp.key",
            headers=auth_headers,
            json={"value": "temp", "value_type": "string"},
        )
        resp = await client.put(
            f"/api/projects/{pid}/configs/emp.key",
            headers=auth_headers,
            json={"value": "", "value_type": "string"},
        )
        assert resp.status_code == 204

    async def test_put_none_value_returns_existing_project_config(
        self, client, auth_headers, sample_repo
    ):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-none")
        await client.put(
            f"/api/projects/{pid}/configs/exist.key",
            headers=auth_headers,
            json={"value": "existing", "value_type": "string"},
        )
        resp = await client.put(
            f"/api/projects/{pid}/configs/exist.key",
            headers=auth_headers,
            json={"value": None},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "existing"

    async def test_put_none_value_nonexistent_project_config_returns_404(
        self, client, auth_headers, sample_repo
    ):
        pid = await self._create_project(client, auth_headers, sample_repo, "cfg-proj-none404")
        resp = await client.put(
            f"/api/projects/{pid}/configs/no.such.key",
            headers=auth_headers,
            json={"value": None},
        )
        assert resp.status_code == 404

    async def test_project_config_unauthenticated(self, client, sample_repo):
        resp = await client.get("/api/projects/1/configs")
        assert resp.status_code in (401, 403)


class TestUserConfig:
    """用户级配置 API — 本人权限。"""

    async def test_list_user_configs_empty(self, client, auth_headers):
        resp = await client.get("/api/me/configs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_set_and_get_user_config(self, client, auth_headers):
        resp = await client.put(
            "/api/me/configs/llm.model",
            headers=auth_headers,
            json={"value": "gpt-4o-mini", "value_type": "string"},
        )
        assert resp.status_code == 200
        assert resp.json()["key"] == "llm.model"
        assert resp.json()["value"] == "gpt-4o-mini"

        resp2 = await client.get("/api/me/configs/llm.model", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["value"] == "gpt-4o-mini"

    async def test_list_user_configs_after_set(self, client, auth_headers):
        await client.put(
            "/api/me/configs/list.key",
            headers=auth_headers,
            json={"value": "list-val", "value_type": "string"},
        )
        resp = await client.get("/api/me/configs", headers=auth_headers)
        assert resp.status_code == 200
        keys = [item["key"] for item in resp.json()]
        assert "list.key" in keys

    async def test_delete_user_config(self, client, auth_headers):
        await client.put(
            "/api/me/configs/del.key",
            headers=auth_headers,
            json={"value": "temp", "value_type": "string"},
        )
        resp = await client.delete("/api/me/configs/del.key", headers=auth_headers)
        assert resp.status_code == 204

        resp2 = await client.get("/api/me/configs/del.key", headers=auth_headers)
        assert resp2.status_code == 404

    async def test_delete_nonexistent_user_config(self, client, auth_headers):
        resp = await client.delete("/api/me/configs/nonexistent.key", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_nonexistent_user_config(self, client, auth_headers):
        resp = await client.get("/api/me/configs/nonexistent.key", headers=auth_headers)
        assert resp.status_code == 404

    async def test_user_config_unauthenticated(self, client):
        resp = await client.get("/api/me/configs")
        assert resp.status_code in (401, 403)

    async def test_put_empty_value_deletes_user_config(self, client, auth_headers):
        await client.put(
            "/api/me/configs/emp.key",
            headers=auth_headers,
            json={"value": "temp", "value_type": "string"},
        )
        resp = await client.put(
            "/api/me/configs/emp.key",
            headers=auth_headers,
            json={"value": "", "value_type": "string"},
        )
        assert resp.status_code == 204

        resp2 = await client.get("/api/me/configs/emp.key", headers=auth_headers)
        assert resp2.status_code == 404

    async def test_put_none_value_returns_existing_user_config(self, client, auth_headers):
        await client.put(
            "/api/me/configs/exist.key",
            headers=auth_headers,
            json={"value": "existing", "value_type": "string"},
        )
        resp = await client.put(
            "/api/me/configs/exist.key",
            headers=auth_headers,
            json={"value": None},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "existing"

    async def test_put_none_value_nonexistent_user_config_returns_404(self, client, auth_headers):
        resp = await client.put(
            "/api/me/configs/no.such.key",
            headers=auth_headers,
            json={"value": None},
        )
        assert resp.status_code == 404

    async def test_user_config_update_existing(self, client, auth_headers):
        await client.put(
            "/api/me/configs/upd.key",
            headers=auth_headers,
            json={"value": "v1", "value_type": "string"},
        )
        resp = await client.put(
            "/api/me/configs/upd.key",
            headers=auth_headers,
            json={"value": "v2", "value_type": "string"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "v2"

    async def test_user_config_sensitive_masked(self, client, auth_headers):
        resp = await client.put(
            "/api/me/configs/secret.key",
            headers=auth_headers,
            json={"value": "super-secret-value", "value_type": "string", "is_sensitive": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_sensitive"] is True
        assert "***" in data["value"]
        assert data["value"] != "super-secret-value"

    async def test_user_configs_isolated_between_users(self, client, auth_headers, admin_headers):
        await client.put(
            "/api/me/configs/iso.key",
            headers=auth_headers,
            json={"value": "user-only", "value_type": "string"},
        )
        resp = await client.get("/api/me/configs", headers=admin_headers)
        assert resp.status_code == 200
        keys = [item["key"] for item in resp.json()]
        assert "iso.key" not in keys


class TestConfigResolve:
    """配置三级解析链路测试。"""

    async def test_resolve_default(self, client, auth_headers):
        resp = await client.get(
            "/api/configs/resolve",
            headers=auth_headers,
            params={"key": "nonexistent.resolve.key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "nonexistent.resolve.key"
        assert data["source"] in ("default", "file")

    async def test_resolve_user_overrides_default(self, client, auth_headers):
        await client.put(
            "/api/me/configs/llm.model",
            headers=auth_headers,
            json={"value": "user-model", "value_type": "string"},
        )
        resp = await client.get(
            "/api/configs/resolve",
            headers=auth_headers,
            params={"key": "llm.model"},
        )
        assert resp.status_code == 200
        assert resp.json()["source"] == "user"
        assert resp.json()["resolved_value"] == "user-model"

    async def test_resolve_project_config(self, client, auth_headers, sample_repo):
        resp = await client.post(
            "/api/projects/from-local",
            headers=auth_headers,
            json={"name": "resolve-proj", "description": "Test", "local_path": str(sample_repo)},
        )
        pid = resp.json()["id"]

        await client.put(
            f"/api/projects/{pid}/configs/resolve.key",
            headers=auth_headers,
            json={"value": "project-val", "value_type": "string"},
        )
        resp2 = await client.get(
            "/api/configs/resolve",
            headers=auth_headers,
            params={"key": "resolve.key", "project_id": pid},
        )
        assert resp2.status_code == 200
        assert resp2.json()["source"] == "project"
        assert resp2.json()["resolved_value"] == "project-val"

    async def test_resolve_user_overrides_project(self, client, auth_headers, sample_repo):
        resp = await client.post(
            "/api/projects/from-local",
            headers=auth_headers,
            json={
                "name": "resolve-override",
                "description": "Test",
                "local_path": str(sample_repo),
            },
        )
        pid = resp.json()["id"]

        await client.put(
            f"/api/projects/{pid}/configs/ovr.key",
            headers=auth_headers,
            json={"value": "project-val", "value_type": "string"},
        )
        await client.put(
            "/api/me/configs/ovr.key",
            headers=auth_headers,
            json={"value": "user-val", "value_type": "string"},
        )
        resp2 = await client.get(
            "/api/configs/resolve",
            headers=auth_headers,
            params={"key": "ovr.key", "project_id": pid},
        )
        assert resp2.status_code == 200
        assert resp2.json()["source"] == "user"
        assert resp2.json()["resolved_value"] == "user-val"

    async def test_resolve_system_config(self, client, admin_headers, auth_headers):
        await client.put(
            "/api/configs/system/sys.resolve.key",
            headers=admin_headers,
            json={"value": "sys-val", "value_type": "string"},
        )
        resp = await client.get(
            "/api/configs/resolve",
            headers=auth_headers,
            params={"key": "sys.resolve.key"},
        )
        assert resp.status_code == 200
        assert resp.json()["source"] == "system"
        assert resp.json()["resolved_value"] == "sys-val"

    async def test_resolve_unauthenticated(self, client):
        resp = await client.get(
            "/api/configs/resolve",
            params={"key": "llm.model"},
        )
        assert resp.status_code in (401, 403)


class TestTestLlm:
    """POST /api/me/test-llm 测试连接。"""

    async def test_test_llm_no_api_key(self, client, auth_headers):
        resp = await client.post(
            "/api/me/test-llm",
            headers=auth_headers,
            json={"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
        )
        assert resp.status_code == 400

    async def test_test_llm_missing_api_key_field(self, client, auth_headers):
        resp = await client.post(
            "/api/me/test-llm",
            headers=auth_headers,
            json={"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
        )
        assert resp.status_code == 400

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_test_llm_success(self, mock_completion, client, auth_headers):
        mock_completion.return_value = MagicMock(choices=[])
        resp = await client.post(
            "/api/me/test-llm",
            headers=auth_headers,
            json={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_test_llm_failure(self, mock_completion, client, auth_headers):
        mock_completion.side_effect = Exception("Connection failed")
        resp = await client.post(
            "/api/me/test-llm",
            headers=auth_headers,
            json={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        )
        assert resp.status_code == 400

    async def test_test_llm_unauthenticated(self, client):
        resp = await client.post(
            "/api/me/test-llm",
            json={
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
        )
        assert resp.status_code in (401, 403)

    @patch("litellm.acompletion", new_callable=AsyncMock)
    async def test_test_llm_with_provider(self, mock_completion, client, auth_headers):
        mock_completion.return_value = MagicMock(choices=[])
        resp = await client.post(
            "/api/me/test-llm",
            headers=auth_headers,
            json={
                "api_key": "sk-test",
                "base_url": "https://api.anthropic.com/v1",
                "model": "claude-3-haiku",
                "provider": "anthropic",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
