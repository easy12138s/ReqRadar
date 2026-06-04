"""E2E 测试 — 认证完整流程 (mock-mode)"""

import pytest

from tests.factories import unique_email

pytestmark = [pytest.mark.e2e]


class TestAuthFullLifecycle:
    """注册 → 登录 → /me → 修改密码 → 新密码登录 → 登出"""

    async def test_auth_full_lifecycle(self, e2e_client):
        """完整认证生命周期。"""
        # 1. Register
        email = unique_email("lifecycle")
        resp = await e2e_client.post(
            "/api/auth/register",
            json={"email": email, "password": "Pass1234", "display_name": "Lifecycle User"},
        )
        assert resp.status_code == 201
        resp.json()

        # 2. Login
        resp2 = await e2e_client.post(
            "/api/auth/login",
            json={"email": email, "password": "Pass1234"},
        )
        assert resp2.status_code == 200
        token = resp2.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. GET /me
        resp3 = await e2e_client.get("/api/auth/me", headers=headers)
        assert resp3.status_code == 200
        assert resp3.json()["email"] == email

        # 4. Change password (old_password / new_password)
        resp4 = await e2e_client.put(
            "/api/auth/me/password",
            headers=headers,
            json={"old_password": "Pass1234", "new_password": "NewPass5678"},
        )
        assert resp4.status_code == 200

        # 5. Login with new password
        resp5 = await e2e_client.post(
            "/api/auth/login",
            json={"email": email, "password": "NewPass5678"},
        )
        assert resp5.status_code == 200
        new_token = resp5.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}

        # 6. Logout
        resp6 = await e2e_client.post("/api/auth/logout", headers=new_headers)
        assert resp6.status_code == 200

    async def test_duplicate_email_rejected(self, e2e_client, e2e_user):
        """重复邮箱应被拒绝。"""
        _, _, _, user_data, _ = e2e_user
        resp = await e2e_client.post(
            "/api/auth/register",
            json={"email": user_data["email"], "password": "Pass1234", "display_name": "Duplicate"},
        )
        assert resp.status_code == 409

    async def test_invalid_credentials(self, e2e_client, e2e_user):
        """错误密码应返回 401。"""
        _, _, _, user_data, _ = e2e_user
        resp = await e2e_client.post(
            "/api/auth/login",
            json={"email": user_data["email"], "password": "WrongPassword"},
        )
        assert resp.status_code == 401

    async def test_missing_fields_rejected(self, e2e_client):
        """缺失字段应返回 422。"""
        resp = await e2e_client.post(
            "/api/auth/register",
            json={"email": "test@example.com"},
        )
        assert resp.status_code == 422

    async def test_unauthenticated_me(self, e2e_client):
        """无 token 访问 /me 应返回 401。"""
        resp = await e2e_client.get("/api/auth/me")
        assert resp.status_code in (401, 403)
