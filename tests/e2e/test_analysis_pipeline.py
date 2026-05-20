"""E2E 测试 — 分析全流程 (mock-mode)"""

import pytest
from sqlalchemy import select

from reqradar.web.enums import TaskStatus
from reqradar.web.models import AnalysisTask

pytestmark = [pytest.mark.e2e]


@pytest.fixture(autouse=True)
def _suppress_background_task(monkeypatch):
    """阻止后台分析任务真正执行 — 避免损坏测试 DB。"""
    import reqradar.web.api.analyses as analyses_module

    async def _noop(*args, **kwargs):
        pass

    monkeypatch.setattr(analyses_module, "_run_analysis_background", _noop)


@pytest.fixture
async def analysis_env(
    e2e_project,
    patch_create_llm_client,
    patch_llm_reachable,
    inject_llm_config,
    setup_runner_session,
):
    """组合 fixture — 提供完整分析环境。"""
    return e2e_project


async def test_submit_analysis_returns_201(analysis_env):
    """提交分析应返回 201。"""
    client, headers, _token, _user_data, user_id, project_id = analysis_env

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-Mock分析",
            "requirement_text": "用户需要登录系统并管理个人信息",
            "depth": "quick",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["user_id"] == user_id
    assert data["status"] in ("pending", "running")
    assert data["requirement_name"] == "E2E-Mock分析"


async def test_list_analyses_after_submit(analysis_env):
    """提交分析后应能在列表中看到。"""
    client, headers, _token, _user_data, _user_id, project_id = analysis_env

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-列表测试",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    resp2 = await client.get("/api/analyses", headers=headers)
    assert resp2.status_code == 200
    tasks = resp2.json()
    assert any(t["id"] == task_id for t in tasks)


async def test_get_analysis_detail(analysis_env):
    """获取单个分析详情。"""
    client, headers, _token, _user_data, _user_id, project_id = analysis_env

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-详情测试",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    task_id = resp.json()["id"]

    resp2 = await client.get(f"/api/analyses/{task_id}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["id"] == task_id


async def test_analysis_cancel(analysis_env, e2e_session_factory):
    """取消分析应成功。"""
    client, headers, _token, _user_data, _user_id, project_id = analysis_env

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-取消测试",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    task_id = resp.json()["id"]

    async with e2e_session_factory() as db:
        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one()
        task.status = TaskStatus.PENDING
        await db.commit()

    resp2 = await client.post(f"/api/analyses/{task_id}/cancel", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "cancelled"


async def test_analysis_submit_without_llm_key(
    e2e_project, patch_llm_reachable, setup_runner_session
):
    """无 LLM API Key 应返回 400。"""
    client, headers, _token, _user_data, _user_id, project_id = e2e_project

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "No Key",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "API Key" in detail or "未配置" in detail


async def test_analysis_submit_other_user_project(analysis_env, e2e_client, e2e_session_factory):
    """非项目所有者提交分析应返回 403。"""
    _client, _headers, _token, _user_data, _user_id, project_id = analysis_env

    from tests.factories import unique_email

    other_data = {
        "email": unique_email("other"),
        "password": "OtherPass123",
        "display_name": "Other",
    }
    reg_resp = await e2e_client.post("/api/auth/register", json=other_data)
    assert reg_resp.status_code == 201

    login_resp = await e2e_client.post(
        "/api/auth/login",
        json={"email": other_data["email"], "password": other_data["password"]},
    )
    other_token = login_resp.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = await e2e_client.post(
        "/api/analyses",
        headers=other_headers,
        json={
            "project_id": project_id,
            "requirement_name": "Other User Analysis",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    assert resp.status_code == 403


async def test_analysis_retry_after_completion(
    analysis_env,
    e2e_session_factory,
    patch_create_llm_client,
    inject_llm_config,
):
    """完成后的任务可以重试。"""
    client, headers, _token, _user_data, _user_id, project_id = analysis_env

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-重试测试",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    task_id = resp.json()["id"]

    async with e2e_session_factory() as db:
        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one()
        task.status = TaskStatus.COMPLETED
        await db.commit()

    resp2 = await client.post(f"/api/analyses/{task_id}/retry", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] in ("pending", "running")


async def test_analysis_not_found(analysis_env):
    """查询不存在的分析应返回 404。"""
    client, headers, _token, _user_data, _user_id, _project_id = analysis_env

    resp = await client.get("/api/analyses/999999", headers=headers)
    assert resp.status_code == 404


async def test_analysis_cancel_not_cancellable(analysis_env, e2e_session_factory):
    """已取消的任务不能再取消，应返回 400。"""
    client, headers, _token, _user_data, _user_id, project_id = analysis_env

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-重复取消",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    task_id = resp.json()["id"]

    async with e2e_session_factory() as db:
        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one()
        task.status = TaskStatus.CANCELLED
        await db.commit()

    resp2 = await client.post(f"/api/analyses/{task_id}/cancel", headers=headers)
    assert resp2.status_code == 400


async def test_analysis_retry_not_retriable(analysis_env, e2e_session_factory):
    """运行中的任务不能重试，应返回 400。"""
    client, headers, _token, _user_data, _user_id, project_id = analysis_env

    resp = await client.post(
        "/api/analyses",
        headers=headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-运行中重试",
            "requirement_text": "需求文本",
            "depth": "quick",
        },
    )
    task_id = resp.json()["id"]

    async with e2e_session_factory() as db:
        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one()
        task.status = TaskStatus.RUNNING
        await db.commit()

    resp2 = await client.post(f"/api/analyses/{task_id}/retry", headers=headers)
    assert resp2.status_code == 400
