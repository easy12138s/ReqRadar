"""E2E 测试 — WebSocket 进度推送"""

import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from jose import jwt
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from reqradar.web.api.auth import ALGORITHM
from reqradar.web.enums import TaskStatus
from reqradar.web.models import AnalysisTask

pytestmark = [pytest.mark.e2e]

E2E_SECRET_KEY = "e2e-test-secret-key"


def _make_ws_token(user_id: int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=60)
    return jwt.encode({"sub": str(user_id), "exp": expire}, E2E_SECRET_KEY, algorithm=ALGORITHM)


@pytest.fixture(autouse=True)
def _mock_mcp_lifecycle(monkeypatch):
    """Mock reqradar.mcp.lifecycle 以避免 fastmcp 依赖。"""
    mock_module = MagicMock()
    mock_module.maybe_start_mcp_with_web = AsyncMock(return_value=None)
    mock_module.stop_mcp_with_web = AsyncMock(return_value=None)
    monkeypatch.setitem(sys.modules, "reqradar.mcp.lifecycle", mock_module)
    monkeypatch.setitem(sys.modules, "fastmcp", MagicMock())


@pytest.fixture
async def ws_env(e2e_project, e2e_session_factory):
    """创建 WebSocket 测试环境: 用户 + 项目 + 分析任务。"""
    _client, _headers, _token, _user_data, user_id, project_id = e2e_project

    async with e2e_session_factory() as db:
        task = AnalysisTask(
            project_id=project_id,
            user_id=user_id,
            requirement_name="WS-Test任务",
            requirement_text="WebSocket测试需求",
            depth="quick",
            status=TaskStatus.PENDING,
            context_json={},
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id

    yield e2e_project, task_id


@pytest.fixture
async def other_user_task_env(e2e_project, e2e_session_factory):
    """创建属于其他用户的分析任务(用于测试访问拒绝)。"""
    _client, _headers, _token, _user_data, _user_id, project_id = e2e_project

    from tests.factories import build_user

    async with e2e_session_factory() as db:
        other = build_user()
        db.add(other)
        await db.commit()
        await db.refresh(other)

        task = AnalysisTask(
            project_id=project_id,
            user_id=other.id,
            requirement_name="Other-WS任务",
            requirement_text="其他用户的任务",
            depth="quick",
            status=TaskStatus.PENDING,
            context_json={},
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

    yield e2e_project, other.id, task.id


class TestWebSocketFlow:
    """WebSocket 进度推送测试。"""

    def test_websocket_ping_pong(self, ws_env):
        """发送 ping 应收到 pong。"""
        (client, _headers, _token, _user_data, user_id, _project_id), task_id = ws_env
        e2e_app = client._transport.app
        ws_token = _make_ws_token(user_id)

        with (
            TestClient(e2e_app) as tc,
            tc.websocket_connect(f"/api/analyses/{task_id}/ws?token={ws_token}") as ws,
        ):
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_websocket_invalid_token_rejected(self, ws_env):
        """无效 token 应被拒绝 (code 4001)。"""
        (client, _headers, _token, _user_data, _user_id, _project_id), task_id = ws_env
        e2e_app = client._transport.app

        with TestClient(e2e_app) as tc, pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: SIM117
            with tc.websocket_connect(f"/api/analyses/{task_id}/ws?token=invalid-token") as ws:
                ws.receive_json()
        assert exc_info.value.code == 4001

    def test_websocket_nonexistent_task_rejected(self, ws_env):
        """不存在的任务应被拒绝 (code 4003)。"""
        (client, _headers, _token, _user_data, user_id, _project_id), _task_id = ws_env
        e2e_app = client._transport.app
        ws_token = _make_ws_token(user_id)

        with TestClient(e2e_app) as tc, pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: SIM117
            with tc.websocket_connect(f"/api/analyses/999999/ws?token={ws_token}") as ws:
                ws.receive_json()
        assert exc_info.value.code == 4003

    def test_websocket_unauthorized_task(self, other_user_task_env):
        """非所有者的任务应被拒绝 (code 4003)。"""
        (e2e_project_tuple, _other_user_id, other_task_id) = other_user_task_env
        client, _headers, _token, _user_data, user_id, _project_id = e2e_project_tuple
        e2e_app = client._transport.app
        ws_token = _make_ws_token(user_id)

        with TestClient(e2e_app) as tc, pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: SIM117
            with tc.websocket_connect(f"/api/analyses/{other_task_id}/ws?token={ws_token}") as ws:
                ws.receive_json()
        assert exc_info.value.code == 4003

    def test_websocket_send_unknown_message_ignored(self, ws_env):
        """非 ping 的消息应被静默忽略, 不断开连接。"""
        (client, _headers, _token, _user_data, user_id, _project_id), task_id = ws_env
        e2e_app = client._transport.app
        ws_token = _make_ws_token(user_id)

        with (
            TestClient(e2e_app) as tc,
            tc.websocket_connect(f"/api/analyses/{task_id}/ws?token={ws_token}") as ws,
        ):
            ws.send_json({"type": "unknown_type", "data": "test"})
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_websocket_missing_token_rejected(self, ws_env):
        """缺少 token 参数应被拒绝。"""
        (client, _headers, _token, _user_data, _user_id, _project_id), task_id = ws_env
        e2e_app = client._transport.app

        with TestClient(e2e_app) as tc, pytest.raises((WebSocketDisconnect, TypeError)):  # noqa: SIM117
            with tc.websocket_connect(f"/api/analyses/{task_id}/ws") as ws:
                ws.receive_json()
