"""E2E 测试专用 fixtures — 提供 mock-mode 和 real-mode 两套基础设施。"""

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("REQRADAR_TESTING", "1")

from reqradar.infrastructure.config import Config, HomeConfig, WebConfig
from reqradar.infrastructure.paths import get_paths
from reqradar.web.api.auth import create_access_token, hash_password
from reqradar.web.app import create_app
from reqradar.web.database import Base
from reqradar.web.enums import TaskStatus
from reqradar.web.models import AnalysisTask, Project, User, UserConfig
from reqradar.web.services.report_storage import ReportStorage


# ---------------------------------------------------------------------------
# E2E 独立 DB + app fixtures (不依赖 root conftest，完全自包含)
# ---------------------------------------------------------------------------


@pytest.fixture
def e2e_config(tmp_path: Path) -> Config:
    """E2E 测试专用配置 — 所有路径指向 tmp_path 隔离目录。"""
    data_root = tmp_path / "data"
    reports_path = tmp_path / "reports"
    data_root.mkdir(parents=True, exist_ok=True)
    reports_path.mkdir(parents=True, exist_ok=True)
    return Config(
        home=HomeConfig(path=str(tmp_path / "home")),
        web=WebConfig(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'e2e.db'}",
            secret_key="e2e-test-secret-key",
            debug=True,
            auto_create_tables=False,
            data_root=str(data_root),
            reports_path=str(reports_path),
            max_upload_size=50,
        ),
    )


@pytest.fixture
async def e2e_engine(e2e_config: Config):
    """E2E 专用异步数据库引擎。"""
    engine = create_async_engine(e2e_config.web.database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def e2e_session_factory(e2e_engine):
    """E2E 专用 session factory。"""
    return async_sessionmaker(e2e_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def e2e_db(e2e_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """E2E 专用数据库 session。"""
    async with e2e_session_factory() as session:
        yield session


@pytest.fixture
async def e2e_app(e2e_config: Config, e2e_session_factory, monkeypatch):
    """E2E 专用 FastAPI app 实例。"""
    import reqradar.infrastructure.config as config_module

    monkeypatch.setattr(config_module, "load_config", lambda path=None: e2e_config)
    app = create_app()
    paths = get_paths(e2e_config)
    app.state.config = e2e_config
    app.state.paths = paths
    app.state.session_factory = e2e_session_factory
    app.state.secret_key = e2e_config.web.secret_key
    app.state.report_storage = ReportStorage(paths["reports"])
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return app


@pytest.fixture
async def e2e_client(e2e_app) -> AsyncGenerator[AsyncClient, None]:
    """E2E 专用 httpx AsyncClient。"""
    transport = httpx.ASGITransport(app=e2e_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def e2e_user(e2e_client: AsyncClient, e2e_app, e2e_session_factory) -> tuple:
    """注册 + 登录 E2E 用户，yield (client, headers, token, user_data, user_id)。"""
    from tests.factories import unique_email

    user_data = {
        "email": unique_email("e2e"),
        "password": "E2ePass123",
        "display_name": "E2E User",
    }
    resp = await e2e_client.post("/api/auth/register", json=user_data)
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    login_resp = await e2e_client.post(
        "/api/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    async with e2e_session_factory() as db:
        result = await db.execute(select(User).where(User.email == user_data["email"]))
        user = result.scalar_one()
        user_id = user.id
    yield (e2e_client, headers, token, user_data, user_id)


@pytest.fixture
async def e2e_project(e2e_user, tmp_path: Path) -> tuple:
    """创建 E2E 项目，yield (client, headers, token, user_data, user_id, project_id)。"""
    client, headers, token, user_data, user_id = e2e_user
    repo = tmp_path / "e2e_project_repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('hello')", encoding="utf-8")
    (repo / "README.md").write_text("# E2E Project\n", encoding="utf-8")
    resp = await client.post(
        "/api/projects/from-local",
        headers=headers,
        json={
            "name": "e2e-project",
            "description": "E2E test project",
            "local_path": str(repo),
        },
    )
    assert resp.status_code == 201, f"Create project failed: {resp.text}"
    project_id = resp.json()["id"]
    yield (client, headers, token, user_data, user_id, project_id)


# ---------------------------------------------------------------------------
# Mock-Mode LLM fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client():
    """可配置的 mock LLM client。

    返回一个 MagicMock，默认 complete() 返回包含分析结果的 dict。
    使用者可通过 mock_llm_client.complete.side_effect 自定义行为。
    """
    client = MagicMock()
    client.complete = AsyncMock(
        return_value={
            "risk_level": "medium",
            "risk_score": 0.5,
            "summary": "Mock analysis summary",
            "findings": [
                {"dimension": "completeness", "status": "sufficient", "confidence": 0.8},
                {"dimension": "consistency", "status": "sufficient", "confidence": 0.7},
            ],
            "recommendations": ["Add more detail to requirements"],
        }
    )
    client.complete_structured = AsyncMock(
        return_value={
            "risk_level": "medium",
            "summary": "Mock structured analysis",
        }
    )
    client.complete_with_tools = AsyncMock(
        return_value={
            "risk_level": "medium",
            "summary": "Mock tool-based analysis",
        }
    )
    client.stream_complete = AsyncMock()

    async def _mock_stream(messages):
        for token in ["Mock", " response"]:
            yield token

    client.stream_complete.return_value = _mock_stream([])
    client.stream_complete.side_effect = None
    return client


@pytest.fixture
def patch_create_llm_client(mock_llm_client, monkeypatch):
    """Patch create_llm_client to return mock_llm_client for all E2E tests."""
    import reqradar.modules.llm_client as llm_module

    monkeypatch.setattr(llm_module, "create_llm_client", lambda **kwargs: mock_llm_client)
    return mock_llm_client


@pytest.fixture
def patch_llm_reachable(monkeypatch):
    """Patch is_llm_reachable to always return True (or a configurable value)。"""
    from reqradar.modules import llm_connectivity

    monkeypatch.setattr(llm_connectivity, "is_llm_reachable", lambda *a, **kw: True)
    monkeypatch.setattr(llm_connectivity, "mark_llm_reachable", lambda *a, **kw: None)
    monkeypatch.setattr(llm_connectivity, "mark_llm_unreachable", lambda *a, **kw: None)


@pytest.fixture
async def inject_llm_config(e2e_db: AsyncSession, e2e_user):
    """通过 UserConfig 注入 mock LLM 配置，让 submit_analysis 通过 API key 检查。"""
    _client, _headers, _token, user_data, user_id = e2e_user
    configs = [
        UserConfig(
            user_id=user_id,
            config_key="llm.api_key",
            config_value="mock-api-key",
            is_sensitive=True,
        ),
        UserConfig(
            user_id=user_id,
            config_key="llm.model",
            config_value="mock-model",
        ),
    ]
    for cfg in configs:
        e2e_db.add(cfg)
    await e2e_db.commit()


@pytest.fixture
async def setup_runner_session(e2e_app, e2e_session_factory):
    """确保 analysis_runner 使用 E2E 测试数据库 session。"""
    from reqradar.web.services.analysis_runner import runner

    runner.session_factory = e2e_session_factory
    yield
    runner.session_factory = None


@pytest.fixture(autouse=True)
def _reset_llm_connectivity():
    """每个测试后清理 LLM 连接状态缓存，防止泄漏。"""
    yield
    from reqradar.modules.llm_connectivity import _cache

    _cache.clear()
