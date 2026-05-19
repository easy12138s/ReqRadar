import pytest

pytestmark = pytest.mark.integration


class TestChatbackUnauthenticated:
    async def test_chat_unauthenticated(self, client):
        resp = await client.post(
            "/api/analyses/999/chat",
            json={"message": "hello"},
        )
        assert resp.status_code in (401, 403)

    async def test_chat_stream_unauthenticated(self, client):
        resp = await client.post(
            "/api/analyses/999/chat/stream",
            json={"message": "hello"},
        )
        assert resp.status_code in (401, 403)

    async def test_get_chat_history_unauthenticated(self, client):
        resp = await client.get("/api/analyses/999/chat")
        assert resp.status_code in (401, 403)

    async def test_save_chat_unauthenticated(self, client):
        resp = await client.post(
            "/api/analyses/999/chat/save",
            json={"version_number": 1},
        )
        assert resp.status_code in (401, 403)


class TestChatbackNotFound:
    async def test_chat_task_not_found(self, client, auth_headers):
        resp = await client.post(
            "/api/analyses/999999/chat",
            headers=auth_headers,
            json={"message": "hello"},
        )
        assert resp.status_code == 404

    async def test_chat_stream_task_not_found(self, client, auth_headers):
        resp = await client.post(
            "/api/analyses/999999/chat/stream",
            headers=auth_headers,
            json={"message": "hello"},
        )
        assert resp.status_code == 404

    async def test_get_chat_history_task_not_found(self, client, auth_headers):
        resp = await client.get(
            "/api/analyses/999999/chat",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_save_chat_task_not_found(self, client, auth_headers):
        resp = await client.post(
            "/api/analyses/999999/chat/save",
            headers=auth_headers,
            json={"version_number": 1},
        )
        assert resp.status_code == 404
