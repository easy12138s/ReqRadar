"""E2E 测试 — Chatback 交互流程 (mock-mode)"""

import pytest
from sqlalchemy import select

from reqradar.web.enums import TaskStatus
from reqradar.web.models import AnalysisTask, ReportVersion

pytestmark = [pytest.mark.e2e]


@pytest.fixture
async def completed_task_env(
    e2e_project,
    e2e_session_factory,
    patch_create_llm_client,
    patch_llm_reachable,
    inject_llm_config,
    setup_runner_session,
):
    """创建已完成的分析任务环境。"""
    client, headers, token, user_data, user_id, project_id = e2e_project

    async with e2e_session_factory() as db:
        task = AnalysisTask(
            project_id=project_id,
            user_id=user_id,
            requirement_name="E2E-Chatback任务",
            requirement_text="测试需求文本",
            depth="quick",
            status=TaskStatus.COMPLETED,
            context_json={"risk_level": "low", "deep_analysis": {"risk_level": "low"}},
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        version = ReportVersion(
            task_id=task.id,
            version_number=1,
            report_data={"summary": "测试报告"},
            context_snapshot={},
            content_markdown="# Test Report",
            content_html="<h1>Test Report</h1>",
            trigger_type="initial",
            trigger_description="Initial",
            created_by=user_id,
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)

        task_id = task.id

    yield (client, headers, token, user_data, user_id, project_id, task_id)


class TestChatbackFlow:
    """Chatback 交互流程。"""

    async def test_get_chat_history_empty(self, completed_task_env):
        """已完成任务的聊天历史应为空。"""
        client, headers, *_, task_id = completed_task_env
        resp = await client.get(f"/api/analyses/{task_id}/chat", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert data["messages"] == []

    async def test_get_chat_history_not_found(self, e2e_client, e2e_user):
        """不存在的任务应返回 404。"""
        client, headers, *_ = e2e_user
        resp = await e2e_client.get("/api/analyses/999999/chat", headers=headers)
        assert resp.status_code == 404

    async def test_chat_static_without_llm_key(self, e2e_project, setup_runner_session):
        """无 LLM Key 时 POST /chat 应返回 400。"""
        client, headers, token, user_data, user_id, project_id = e2e_project
        resp = await client.post(
            f"/api/analyses/1/chat",
            headers=headers,
            json={"message": "hello"},
        )
        assert resp.status_code in (400, 404)

    async def test_chat_unauthenticated(self, e2e_client):
        """未认证应返回 401。"""
        resp = await e2e_client.post(
            "/api/analyses/1/chat",
            json={"message": "hello"},
        )
        assert resp.status_code in (401, 403)

    async def test_chat_stream_unauthenticated(self, e2e_client):
        """未认证应返回 401。"""
        resp = await e2e_client.post(
            "/api/analyses/1/chat/stream",
            json={"message": "hello"},
        )
        assert resp.status_code in (401, 403)

    async def test_chat_save_not_found(self, e2e_client, e2e_user):
        """不存在的任务保存应返回 404。"""
        client, headers, *_ = e2e_user
        resp = await e2e_client.post(
            "/api/analyses/999999/chat/save",
            headers=headers,
            json={"version_number": 1},
        )
        assert resp.status_code == 404
