"""端到端真实场景测试 — 通过 API 调用完整系统流程，真实 LLM 调用。

运行方式:
    REQRADAR_TEST_LLM_API_KEY=sk-xxx REQRADAR_TEST_LLM_MODEL=MiniMax-M2.5 \
        pytest tests/integration/test_e2e_real_analysis.py -v -s

环境变量:
    REQRADAR_TEST_LLM_API_KEY   (必填) LLM API Key
    REQRADAR_TEST_LLM_MODEL     (可选) 模型名，默认 MiniMax-M2.5
    REQRADAR_TEST_LLM_BASE_URL  (可选) API Base URL
    REQRADAR_TEST_GIT_URL       (可选) 测试项目 Git 地址
    REQRADAR_TEST_PDF_PATH      (可选) 需求 PDF 文件路径
"""

import asyncio
import os
import time
from pathlib import Path

import pytest
from sqlalchemy import select

from reqradar.web.enums import TaskStatus
from reqradar.web.models import AnalysisTask, UserConfig

# ---------------------------------------------------------------------------
# 环境变量
# ---------------------------------------------------------------------------

_LLM_API_KEY = os.environ.get("REQRADAR_TEST_LLM_API_KEY", "")
_LLM_MODEL = os.environ.get("REQRADAR_TEST_LLM_MODEL", "MiniMax-M2.5")
_LLM_BASE_URL = os.environ.get("REQRADAR_TEST_LLM_BASE_URL", "")
_GIT_URL = os.environ.get(
    "REQRADAR_TEST_GIT_URL", "https://github.com/easy12138s/cool-agent.git"
)
_LOCAL_PROJECT_PATH = os.environ.get(
    "REQRADAR_TEST_LOCAL_PROJECT", str(Path(__file__).parent.parent.parent / "src")
)
_PDF_PATH = os.environ.get("REQRADAR_TEST_PDF_PATH", "")

_require_real_llm = pytest.mark.skipif(
    not _LLM_API_KEY, reason="REQRADAR_TEST_LLM_API_KEY not set"
)

_require_pdf = pytest.mark.skipif(
    not _PDF_PATH and not Path(
        r"D:\edgedownload\Cool Agent 复杂需求文档（个人全场景信息管理自动化闭环）.pdf"
    ).exists(),
    reason="Set REQRADAR_TEST_PDF_PATH to the requirement PDF",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _setup_runner_session(session_factory):
    """确保 analysis_runner 使用测试数据库 session。"""
    from reqradar.web.services.analysis_runner import runner as analysis_runner

    analysis_runner.session_factory = session_factory
    yield
    analysis_runner.session_factory = None


@pytest.fixture
async def _inject_user_llm_config(db_session, regular_user):
    """通过 UserConfig 注入 LLM 配置，复用 ConfigManager 三级解析链路。"""
    configs = [
        UserConfig(
            user_id=regular_user.id,
            config_key="llm.api_key",
            config_value=_LLM_API_KEY,
            is_sensitive=True,
        ),
        UserConfig(
            user_id=regular_user.id,
            config_key="llm.model",
            config_value=_LLM_MODEL,
        ),
    ]
    if _LLM_BASE_URL:
        configs.append(
            UserConfig(
                user_id=regular_user.id,
                config_key="llm.base_url",
                config_value=_LLM_BASE_URL,
            )
        )
    for cfg in configs:
        db_session.add(cfg)
    await db_session.commit()

    # 标记 LLM 可达，避免连通性检查阻塞
    from reqradar.modules.llm_connectivity import mark_llm_reachable

    base_url = _LLM_BASE_URL or "https://api.openai.com/v1"
    mark_llm_reachable("openai", _LLM_API_KEY, base_url)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


async def _poll_task_status(
    session_factory, task_id: int, timeout: int = 600
) -> AnalysisTask:
    """轮询等待分析任务到达终态。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with session_factory() as db:
            result = await db.execute(
                select(AnalysisTask).where(AnalysisTask.id == task_id)
            )
            task = result.scalar_one()
            if task.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                return task
        await asyncio.sleep(3)
    raise TimeoutError(f"Task {task_id} did not finish within {timeout}s")


async def _print_analysis_report(client, auth_headers, app, task, test_name: str):
    """通过 API 获取报告并输出，复用 ReportStorage 存储架构。"""
    snapshot = task.context_json or {}
    risk = snapshot.get("deep_analysis", {}).get("risk_level", "unknown")
    dims = snapshot.get("dimension_status", {})
    evidence = snapshot.get("evidence_list", [])
    dims_ok = sum(1 for v in dims.values() if v.get("status") == "sufficient")
    dims_total = len(dims)

    # 获取报告存储路径 (复用 app.state.report_storage)
    report_storage = app.state.report_storage
    report_root = report_storage._root

    print(f"\n{'=' * 80}")
    print(f"分析报告: {test_name}")
    print(f"风险等级: {risk} | 证据: {len(evidence)} 条 | 维度: {dims_ok}/{dims_total} sufficient")
    print(f"报告存储: {report_root / str(task.id)}")
    print(f"{'=' * 80}")

    # 通过 API 获取 markdown 报告 (复用 GET /api/reports/{task_id}/markdown)
    resp = await client.get(
        f"/api/reports/{task.id}/markdown", headers=auth_headers
    )
    if resp.status_code == 200:
        print(resp.text)
    else:
        # 回退: 直接从 ReportStorage 读取
        md, _ = await report_storage.read_report(task.id)
        if md:
            print(md)
        else:
            print(f"[报告获取失败] status={resp.status_code}")

    print(f"{'=' * 80}\n")


# ---------------------------------------------------------------------------
# 测试 1: 需求分析全流程 (from-git → 分析 → 报告)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@_require_real_llm
@pytest.mark.timeout(600)
async def test_full_analysis_pipeline(
    app, client, auth_headers, session_factory, regular_user, _inject_user_llm_config
):
    """真实场景: 通过 API 创建项目 → 提交需求分析 → 等待完成 → 输出报告。"""

    # 1. 通过 API 创建项目 (调用 POST /api/projects/from-local)
    resp = await client.post(
        "/api/projects/from-local",
        headers=auth_headers,
        json={
            "name": f"e2e_local_{int(time.time())}",
            "description": "E2E test project",
            "local_path": _LOCAL_PROJECT_PATH,
        },
    )
    assert resp.status_code == 201, f"Create project failed: {resp.text}"
    project_id = resp.json()["id"]

    # 2. 通过 API 提交需求分析 (调用 POST /api/analyses)
    resp = await client.post(
        "/api/analyses",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-登录功能需求",
            "requirement_text": (
                "用户需要通过邮箱和密码登录系统，登录后能查看个人信息，"
                "支持记住登录状态。安全要求：密码必须加密存储，"
                "连续失败5次锁定账户。需要支持第三方登录（GitHub/Google）。"
            ),
            "depth": "quick",
        },
    )
    assert resp.status_code == 201, f"Submit analysis failed: {resp.text}"
    task_id = resp.json()["id"]

    # 3. 轮询等待分析完成
    completed_task = await _poll_task_status(session_factory, task_id, timeout=600)
    assert completed_task.status == TaskStatus.COMPLETED, (
        f"Analysis failed: {completed_task.error_message}"
    )

    # 4. 验证维度状态和证据
    snapshot = completed_task.context_json or {}
    assert "dimension_status" in snapshot, "Snapshot should contain dimension_status"
    assert "evidence_list" in snapshot, "Snapshot should contain evidence_list"

    # 5. 输出完整报告
    await _print_analysis_report(
        client, auth_headers, app, completed_task,
        "test_full_analysis_pipeline"
    )


# ---------------------------------------------------------------------------
# 测试 2: 需求预处理 + 分析全流程 (PDF → 合并 → 分析 → 报告)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@_require_real_llm
@_require_pdf
@pytest.mark.timeout(600)
async def test_preprocess_then_analyze(
    app, client, auth_headers, session_factory, regular_user, _inject_user_llm_config
):
    """真实场景: 预处理 PDF → 通过 API 创建项目 → 提交分析 → 输出报告。"""
    from reqradar.agent.requirement_preprocessor import preprocess_requirements
    from reqradar.modules.llm_client import create_llm_client

    # 0. 准备 PDF 路径
    pdf_path = Path(_PDF_PATH) if _PDF_PATH else Path(
        r"D:\edgedownload\Cool Agent 复杂需求文档（个人全场景信息管理自动化闭环）.pdf"
    )
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")

    # 1. 调用预处理服务 (复用 agent.requirement_preprocessor)
    llm_client = create_llm_client(
        model=_LLM_MODEL,
        api_key=_LLM_API_KEY,
        base_url=_LLM_BASE_URL or None,
    )
    preprocess_result = await preprocess_requirements(
        file_paths=[pdf_path],
        llm_client=llm_client,
        title="Cool Agent 需求文档",
    )
    assert preprocess_result is not None, "Preprocess should return a result"
    consolidated = preprocess_result.get("consolidated_text", "")
    assert len(consolidated) > 100, "Consolidated text should be substantial"

    # 2. 通过 API 创建项目
    resp = await client.post(
        "/api/projects/from-local",
        headers=auth_headers,
        json={
            "name": f"e2e_pre_{int(time.time())}",
            "description": "E2E preprocess test",
            "local_path": _LOCAL_PROJECT_PATH,
        },
    )
    assert resp.status_code == 201, f"Create project failed: {resp.text}"
    project_id = resp.json()["id"]

    # 3. 通过 API 提交分析 (使用预处理后的文档)
    resp = await client.post(
        "/api/analyses",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "requirement_name": "E2E-CoolAgent需求预处理分析",
            "requirement_text": consolidated[:8000],
            "depth": "quick",
        },
    )
    assert resp.status_code == 201, f"Submit analysis failed: {resp.text}"
    task_id = resp.json()["id"]

    # 4. 轮询等待分析完成
    completed_task = await _poll_task_status(session_factory, task_id, timeout=600)
    assert completed_task.status == TaskStatus.COMPLETED, (
        f"Analysis failed: {completed_task.error_message}"
    )

    # 5. 输出完整报告
    await _print_analysis_report(
        client, auth_headers, app, completed_task,
        "test_preprocess_then_analyze"
    )
