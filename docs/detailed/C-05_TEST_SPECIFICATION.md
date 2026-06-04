# C-05 测试规范

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 测试编写的强制规范，约束 AI Agent 和人类开发者的测试行为 |
| 前置文档 | AGENTS.md（测试约定章节）、tests/conftest.py（现有 fixture） |
| 核心目标 | 消除 vibe coding 模式下测试编写的随意性，确保测试可隔离、可重复、可维护 |
| 文档职责 | What & How — 测试怎么组织、怎么命名、怎么 mock、怎么断言、怎么运行 |
| 适用范围 | 所有 Python 后端测试（unit / integration / e2e），前端测试不在本文档范围 |

---

## 2. 测试总则

### 2.1 技术栈

| 组件 | 版本要求 | 用途 |
|------|---------|------|
| pytest | >= 8.0 | 测试框架 |
| pytest-asyncio | >= 0.23 | 异步测试支持，`asyncio_mode = "auto"` |
| pytest-cov | >= 5.0 | 覆盖率采集 |
| httpx | >= 0.28 | API 集成测试的 AsyncClient |
| pytest-mock | >= 3.12 | Mock 辅助（可选，提供 `mocker` fixture） |

### 2.2 核心原则

1. **测试必须隔离**：每个测试函数使用 `tmp_path` 写文件、mock 所有外部服务、独立 SQLite 数据库。不使用真实 home 目录、不使用开发数据库、不依赖执行顺序。
2. **asyncio_mode = "auto"**：无需 `@pytest.mark.asyncio` 装饰器，async 测试函数自动识别。
3. **每完成一个文件或一组相关测试就运行对应测试**：不要攒一堆再跑。
4. **测试失败先判断来源**：
   - 测试代码错误 → 修复测试
   - 环境问题（依赖缺失、端口占用等）→ 修复环境
   - 项目 bug → 修复代码，补充回归测试
5. **按真实代码写测试**：不为不存在的接口写测试，不猜测 API 行为。
6. **测试数据须可重复、可清理、可隔离**：不依赖固定自增 ID，不依赖执行顺序。

### 2.3 运行命令

```bash
pytest -q                                       # 全量测试（覆盖率默认开启）
pytest tests/unit/                               # 仅单元测试
pytest tests/integration/api/                    # 仅 API 集成测试
pytest tests/integration/api/test_auth_api.py    # 单文件
pytest tests/unit/test_evidence.py::TestEvidence::test_creation_with_defaults  # 单方法
pytest -k "test_cancel"                          # 关键字过滤
pytest --cov=reqradar --cov-report=term-missing  # 覆盖率报告（含缺失行号）
```

---

## 3. 测试目录结构

```
tests/
├── conftest.py              # 全局 fixture（DB、app、auth、临时目录）
├── factories.py             # 测试数据工厂函数
├── helpers/                 # 测试辅助模块
│   ├── __init__.py
│   ├── auth_helper.py       # 认证辅助
│   ├── db_helper.py         # 数据库辅助
│   └── file_helper.py       # 文件辅助
│
├── unit/                    # 单元测试（无 HTTP、无 DB、纯逻辑）
│   ├── kernel/              # V2 kernel 层测试
│   │   ├── test_session_lifecycle.py
│   │   ├── test_context_pipeline.py
│   │   ├── test_evidence.py
│   │   ├── test_dimension.py
│   │   └── ...
│   ├── test_config.py
│   ├── test_exceptions.py
│   ├── test_paths.py
│   └── ...
│
├── integration/             # 集成测试（有 HTTP / DB，mock 外部服务）
│   ├── conftest.py          # 集成测试专用 fixture 覆盖
│   ├── api/                 # API 端点集成测试（按路由模块拆分）
│   │   ├── test_session_endpoints.py
│   │   ├── test_auth_api.py
│   │   ├── test_projects_api.py
│   │   ├── test_analyses_api.py
│   │   └── ...
│   ├── services/            # Service 层集成测试
│   │   ├── test_report_storage.py
│   │   └── ...
│   └── cli/                 # CLI 集成测试
│       ├── test_cli_basic.py
│       └── ...
│
└── e2e/                     # 端到端测试（完整用户流程）
    ├── conftest.py          # E2E 专用 fixture（独立 DB + app + mock LLM）
    ├── test_analysis_pipeline.py
    ├── test_auth_flow.py
    └── ...
```

### 3.1 各层职责

| 层级 | 职责 | 外部依赖 | Mock 策略 |
|------|------|---------|----------|
| unit | 纯逻辑验证：状态机、模型校验、业务规则 | 无 HTTP、无 DB | mock 所有 I/O |
| integration | API 契约验证：HTTP 状态码、请求/响应格式、权限控制 | 有 HTTP + SQLite | mock LLM/网络/外部存储 |
| e2e | 用户流程验证：完整业务路径端到端 | 有 HTTP + SQLite + mock LLM | 仅 mock LLM 和外部服务 |

---

## 4. 测试文件命名

### 4.1 规则

格式：`test_{module}_{scenario}.py`

| 部分 | 说明 | 示例 |
|------|------|------|
| `module` | 被测模块名，snake_case | `session`、`evidence`、`auth_api` |
| `scenario` | 测试场景，snake_case | `cancellation`、`creation`、`edge_cases` |

### 4.2 示例

| 文件名 | 含义 |
|--------|------|
| `test_session_lifecycle.py` | Session 生命周期相关测试 |
| `test_session_cancellation.py` | Session 取消场景测试 |
| `test_evidence_chain.py` | Evidence 链完整性测试 |
| `test_auth_api.py` | Auth API 端点测试 |
| `test_context_pipeline.py` | Context Pipeline 逻辑测试 |

### 4.3 禁止

| 禁止做法 | 原因 |
|---------|------|
| `test_utils.py`（无场景描述） | 无法从文件名判断测试内容 |
| `test_all.py`（全量堆叠） | 文件过大，定位困难 |
| `tests.py`（不符合 pytest 发现规则） | pytest 默认不发现此命名 |

---

## 5. 测试函数命名

### 5.1 规则

格式：`test_{feature}_{scenario}_{expected_result}`

| 部分 | 说明 | 示例 |
|------|------|------|
| `feature` | 被测功能 | `cancel`、`create`、`submit`、`transition` |
| `scenario` | 测试场景 | `running_session`、`invalid_status`、`empty_input` |
| `expected_result` | 预期结果 | `succeeds`、`returns_404`、`raises_error` |

### 5.2 示例

```python
# 好的命名：功能_场景_预期结果 一目了然
async def test_cancel_running_session_succeeds():
    ...

async def test_cancel_completed_session_returns_409():
    ...

async def test_create_session_without_project_returns_404():
    ...

async def test_transition_from_created_to_ready_succeeds():
    ...

async def test_transition_from_completed_to_running_raises_error():
    ...
```

### 5.3 禁止

| 禁止做法 | 正确做法 |
|---------|---------|
| `test_cancel()` | `test_cancel_running_session_succeeds` |
| `test_session_1()` | `test_create_session_with_valid_config_succeeds` |
| `test_it_works()` | `test_submit_analysis_with_llm_key_succeeds` |

---

## 6. Fixture 注册表

### 6.1 现有 Fixture（来自 conftest.py）

| Fixture 名 | 作用域 | 返回值 | 说明 |
|------------|--------|--------|------|
| `test_config` | function | `Config` | 基于 `tmp_path` 的测试配置，SQLite 数据库 |
| `db_engine` | function | `AsyncEngine` | 异步数据库引擎，自动建表 |
| `session_factory` | function | `async_sessionmaker` | 异步 session 工厂 |
| `db_session` | function | `AsyncSession` | 异步数据库 session，测试结束自动 rollback |
| `regular_user` | function | `User` | 普通用户（role="user"） |
| `admin_user` | function | `User` | 管理员用户（role="admin"） |
| `auth_headers` | function | `dict[str, str]` | 普通用户 JWT 认证头 |
| `admin_headers` | function | `dict[str, str]` | 管理员 JWT 认证头 |
| `app` | function | `FastAPI` | 配置好的 FastAPI 应用实例 |
| `client` | function | `AsyncClient` | httpx 异步客户端 |
| `sample_repo` | function | `Path` | 临时样例仓库目录 |
| `test_user` | function | `tuple` | (client, headers, token, user_data) |
| `test_project` | function | `tuple` | (client, headers, token, user_data, project_id) |

### 6.2 V2 新增 Fixture

以下 fixture 需在 V2 开发过程中逐步添加到 `conftest.py` 或各层 `conftest.py`：

| Fixture 名 | 作用域 | 返回值 | 说明 | 添加位置 |
|------------|--------|--------|------|---------|
| `mock_llm_client` | function | `MagicMock` | 可配置的 mock LLM 客户端，`complete()` 返回预设分析结果 | `tests/conftest.py` |
| `mock_redis` | function | `MagicMock` | mock Redis 客户端，模拟 Streams/Pub/Sub | `tests/conftest.py` |
| `mock_minio` | function | `MagicMock` | mock MinIO 客户端，模拟对象存储 | `tests/conftest.py` |
| `test_session` | function | `tuple` | (client, headers, token, user_data, session_id) 创建 CognitiveSession | `tests/integration/conftest.py` |
| `mock_llm_client` | function | `MagicMock` | E2E 专用 mock LLM（含 `complete`/`stream_complete`/`complete_with_tools`） | `tests/e2e/conftest.py` |
| `patch_create_llm_client` | function | `MagicMock` | Patch `create_llm_client` 返回 mock | `tests/e2e/conftest.py` |
| `patch_llm_reachable` | function | None | Patch `is_llm_reachable` 返回 True | `tests/e2e/conftest.py` |

### 6.3 Fixture 编写规范

```python
# 1. 每个 fixture 必须有中文 docstring
@pytest.fixture
async def test_session(test_user, db_session) -> tuple:
    """创建 CognitiveSession，yield (client, headers, token, user_data, session_id)。"""
    client, headers, token, user_data = test_user
    # ... 创建 session 的逻辑
    yield (client, headers, token, user_data, session_id)

# 2. 需要 cleanup 的 fixture 必须用 yield + finally
@pytest.fixture
async def db_engine(test_config: Config):
    engine = create_async_engine(test_config.web.database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()

# 3. 依赖 app.state 的 fixture 必须手动设置（httpx ASGITransport 不触发 lifespan）
@pytest.fixture
async def app(test_config: Config, session_factory, monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda path=None: test_config)
    app = create_app()
    app.state.config = test_config
    app.state.paths = get_paths(test_config)
    app.state.session_factory = session_factory
    app.state.report_storage = ReportStorage(paths["reports"])
    return app
```

---

## 7. Mock 规则

### 7.1 必须 Mock 的依赖

| 依赖 | Mock 方式 | 原因 |
|------|----------|------|
| LLM 调用（LiteLLM） | `mock_llm_client` fixture 或 `mocker.patch` | 外部付费服务，不可控延迟和结果 |
| 网络请求 | `mocker.patch("httpx.AsyncClient.get")` | 不可控，测试环境可能无网络 |
| Git 仓库操作 | `mocker.patch("reqradar.modules.git_analyzer.GitAnalyzer")` | 依赖本地 Git 和仓库状态 |
| MinIO 对象存储 | `mock_minio` fixture | 外部存储服务，测试环境不可用 |
| Redis Streams/PubSub | `mock_redis` fixture | 外部缓存服务，测试环境不可用 |
| 文件系统写入（非 tmp_path） | 使用 `tmp_path` fixture | 避免污染真实文件系统 |

### 7.2 禁止 Mock 的依赖

| 依赖 | 原因 | 替代方案 |
|------|------|---------|
| PostgreSQL/SQLite | 数据库行为是测试目标 | 使用内存 SQLite |
| Pydantic 模型验证 | 校验逻辑是测试目标 | 直接构造合法/非法数据 |
| 业务逻辑 | 被测代码本身 | 不 mock 被测函数 |
| FastAPI 依赖注入 | 路由行为是测试目标 | 使用真实 app + test client |

### 7.3 Mock 方式

优先使用 `pytest-mock` 的 `mocker` fixture，其次使用 `unittest.mock.patch`：

```python
# 推荐：mocker fixture（pytest-mock）
async def test_submit_analysis_calls_llm(client, auth_headers, project, mocker):
    mock_llm = mocker.patch("reqradar.modules.llm_client.create_llm_client")
    mock_llm.return_value.complete = AsyncMock(return_value={"risk_level": "low"})
    # ...

# 可接受：unittest.mock.patch（with 块）
async def test_submit_analysis_calls_llm(client, auth_headers, project):
    with patch("reqradar.modules.llm_client.create_llm_client") as mock_create:
        mock_create.return_value.complete = AsyncMock(return_value={"risk_level": "low"})
        # ...

# 禁止：模块级 mock（影响其他测试）
mock_llm = patch("reqradar.modules.llm_client.create_llm_client")  # 错误！
```

### 7.4 Mock 位置规则

| 位置 | 是否允许 | 说明 |
|------|---------|------|
| fixture 中 | 允许（推荐） | 通过 `mocker` 或 `monkeypatch` 参数 |
| `with` 块中 | 允许 | 限定 mock 作用范围 |
| 测试函数体内 | 允许 | 使用 `mocker` 或 `patch` |
| 模块级/类级 | 禁止 | mock 泄漏到其他测试 |
| conftest.py `autouse` fixture | 谨慎使用 | 仅用于清理全局状态（如 LLM 连接缓存） |

### 7.5 Module-Level Binding Trap

当被测代码使用 `from module import func` 时，运行时 monkeypatching `module.func` 不会影响已绑定的引用。解决方案：

```python
# 错误：patch 的是原始模块，但被测代码已绑定局部引用
mocker.patch("reqradar.infrastructure.config.load_config")

# 正确：patch 被测代码的局部引用
mocker.patch("reqradar.web.api.analyses.load_config")

# 最佳实践：API 端点通过 request.app.state.config 访问，避免此问题
# 所以 API 端点应使用 request.app.state.config 而非 from config import load_config
```

---

## 8. 单元测试模板

### 8.1 Kernel 层测试（状态机 / 纯逻辑）

```python
"""CognitiveSession 状态转换单元测试"""

import pytest

from reqradar.core.exceptions import InvalidTransitionError
from reqradar.kernel.session import CognitiveSession, SessionStatus


class TestSessionTransition:
    """Session 状态转换规则测试。"""

    async def test_transition_from_created_to_ready_succeeds(self):
        session = CognitiveSession(
            project_id=uuid4(),
            user_id=uuid4(),
        )
        assert session.status == SessionStatus.CREATED

        session.transition(SessionStatus.READY, trigger="config_validated")

        assert session.status == SessionStatus.READY

    async def test_transition_from_completed_to_running_raises_error(self):
        session = CognitiveSession(
            project_id=uuid4(),
            user_id=uuid4(),
            status=SessionStatus.COMPLETED,
        )

        with pytest.raises(InvalidTransitionError) as exc_info:
            session.transition(SessionStatus.RUNNING, trigger="invalid")

        assert "COMPLETED" in str(exc_info.value)
        assert session.status == SessionStatus.COMPLETED  # 状态未变

    async def test_transition_idempotent_same_status_succeeds(self):
        """幂等转换：当前状态已是目标状态时直接返回成功。"""
        session = CognitiveSession(
            project_id=uuid4(),
            user_id=uuid4(),
            status=SessionStatus.RUNNING,
        )

        session.transition(SessionStatus.RUNNING, trigger="idempotent")

        assert session.status == SessionStatus.RUNNING
        # 不产生重复事件


class TestSessionConfigValidation:
    """SessionConfig 校验测试。"""

    def test_config_with_negative_budget_raises_error(self):
        with pytest.raises(ValidationError):
            SessionConfig(context_budget=-1)

    def test_config_with_zero_max_steps_raises_error(self):
        with pytest.raises(ValidationError):
            SessionConfig(max_reasoning_steps=0)

    def test_config_default_values(self):
        config = SessionConfig()
        assert config.context_budget == 128000
        assert config.max_execution_time == 1800
        assert config.checkpoint_enabled is True
```

### 8.2 纯函数 / 工具类测试

```python
"""EvidenceCollector 单元测试"""

from reqradar.agent.evidence import Evidence, EvidenceCollector


class TestEvidence:
    def test_creation_with_defaults(self):
        ev = Evidence(id="ev1", type="code", source="file.py", content="test")
        assert ev.id == "ev1"
        assert ev.confidence == "medium"
        assert ev.dimensions == []

    def test_creation_with_all_fields(self):
        ev = Evidence(
            id="ev2",
            type="git",
            source="commit abc",
            content="change",
            confidence="high",
            dimensions=["impact", "risk"],
            timestamp="2026-01-01T00:00:00Z",
        )
        assert ev.confidence == "high"
        assert len(ev.dimensions) == 2


class TestEvidenceCollector:
    def test_add_evidence_returns_id(self):
        collector = EvidenceCollector()
        ev_id = collector.add(type="code", source="main.py", content="function")
        assert ev_id == "ev-001"

    def test_get_by_dimension(self):
        collector = EvidenceCollector()
        collector.add(type="code", source="a.py", content="x", dimensions=["risk"])
        collector.add(type="code", source="b.py", content="y", dimensions=["impact"])
        collector.add(type="git", source="c1", content="z", dimensions=["risk", "evidence"])

        risk_evs = collector.get_by_dimension("risk")
        assert len(risk_evs) == 2
```

---

## 9. API 集成测试模板

### 9.1 标准 API 测试

```python
"""Session API 端点集成测试"""

import pytest
from httpx import AsyncClient

from reqradar.kernel.session import SessionStatus
from tests.factories import build_project


@pytest.fixture
async def project(db_session, regular_user):
    """创建测试项目。"""
    project = build_project(owner_id=regular_user.id, name="session_test_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


async def test_create_session_succeeds(client, auth_headers, project):
    """成功路径：创建 Session 返回 201。"""
    response = await client.post(
        "/api/v2/sessions",
        headers=auth_headers,
        json={
            "project_id": str(project.id),
            "config": {"context_budget": 128000},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == SessionStatus.READY.value
    assert data["session_id"] is not None


async def test_create_session_nonexistent_project_returns_404(client, auth_headers):
    """不存在资源：project_id 无效返回 404。"""
    response = await client.post(
        "/api/v2/sessions",
        headers=auth_headers,
        json={
            "project_id": "00000000-0000-0000-0000-000000000000",
            "config": {},
        },
    )
    assert response.status_code == 404


async def test_create_session_invalid_config_returns_422(client, auth_headers, project):
    """无效参数：config 校验失败返回 422。"""
    response = await client.post(
        "/api/v2/sessions",
        headers=auth_headers,
        json={
            "project_id": str(project.id),
            "config": {"context_budget": -1},  # 非法值
        },
    )
    assert response.status_code == 422


async def test_cancel_session_succeeds(client, auth_headers, project, db_session, regular_user):
    """成功路径：取消运行中 Session 返回 202。"""
    # 先创建并启动 session（mock 推理循环）
    # ...
    response = await client.post(
        f"/api/v2/sessions/{session_id}/cancel",
        headers=auth_headers,
    )
    assert response.status_code == 202
    assert response.json()["status"] == SessionStatus.CANCELLING.value


class TestUnauthenticated:
    """未认证访问应返回 401/403。"""

    async def test_create_session_unauthenticated(self, client):
        resp = await client.post(
            "/api/v2/sessions",
            json={"project_id": "uuid", "config": {}},
        )
        assert resp.status_code in (401, 403)

    async def test_get_session_unauthenticated(self, client):
        resp = await client.get("/api/v2/sessions/uuid")
        assert resp.status_code in (401, 403)

    async def test_cancel_session_unauthenticated(self, client):
        resp = await client.post("/api/v2/sessions/uuid/cancel")
        assert resp.status_code in (401, 403)
```

### 9.2 httpx.ASGITransport 注意事项

httpx 0.28+ 的 `ASGITransport(app=app)` **不会**触发 FastAPI lifespan。依赖 `app.state.*` 的测试必须手动设置：

```python
@pytest.fixture
async def app(test_config: Config, session_factory, monkeypatch):
    import reqradar.infrastructure.config as config_module

    monkeypatch.setattr(config_module, "load_config", lambda path=None: test_config)
    app = create_app()
    paths = get_paths(test_config)
    # 手动设置 app.state（ASGITransport 不触发 lifespan）
    app.state.config = test_config
    app.state.paths = paths
    app.state.session_factory = session_factory
    app.state.secret_key = test_config.web.secret_key
    app.state.report_storage = ReportStorage(paths["reports"])
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return app
```

---

## 10. 异步测试模板

### 10.1 基本异步测试

pytest-asyncio 的 `asyncio_mode = "auto"` 模式下，`async def` 测试函数自动被识别为异步测试，**无需** `@pytest.mark.asyncio` 装饰器：

```python
# 正确：直接写 async def
async def test_create_session_succeeds(client, auth_headers, project):
    response = await client.post("/api/v2/sessions", ...)
    assert response.status_code == 201

# 错误：不需要装饰器
@pytest.mark.asyncio  # 删除此行！
async def test_create_session_succeeds(client, auth_headers, project):
    ...
```

### 10.2 异步 Fixture

```python
@pytest.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(client: AsyncClient) -> tuple:
    """注册 + 登录用户，yield (client, headers, token, user_data)。"""
    user_data = {
        "email": unique_email("testuser"),
        "password": "TestPass123",
        "display_name": "Test User",
    }
    resp = await client.post("/api/auth/register", json=user_data)
    assert resp.status_code == 201
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    yield (client, headers, token, user_data)
```

### 10.3 异步 Mock

```python
from unittest.mock import AsyncMock, MagicMock


async def test_analysis_with_mock_llm(client, auth_headers, project, mocker):
    """使用 AsyncMock 模拟 LLM 异步调用。"""
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value={
        "risk_level": "medium",
        "summary": "Mock analysis result",
    })
    mocker.patch(
        "reqradar.modules.llm_client.create_llm_client",
        return_value=mock_llm,
    )

    response = await client.post(
        "/api/analyses",
        headers=auth_headers,
        json={"project_id": project.id, "requirement_text": "test"},
    )
    assert response.status_code in (200, 201)
    mock_llm.complete.assert_called_once()
```

---

## 11. 断言约定

### 11.1 状态断言

```python
# 断言枚举状态
assert result.status == SessionStatus.RUNNING
assert task.status == TaskStatus.COMPLETED

# 断言 HTTP 状态码
assert response.status_code == 201
assert response.status_code == 404

# 断言响应体字段
data = response.json()
assert data["status"] == "RUNNING"
assert data["session_id"] is not None
assert len(data["events"]) > 0
```

### 11.2 异常断言

```python
# 断言抛出特定异常
with pytest.raises(InvalidTransitionError) as exc_info:
    session.transition(SessionStatus.RUNNING, trigger="invalid")

# 断言异常消息包含关键信息
assert "COMPLETED" in str(exc_info.value)
assert "RUNNING" in str(exc_info.value)

# 断言异常链
with pytest.raises(LLMException) as exc_info:
    await llm_client.complete(messages=[...])
assert exc_info.value.__cause__ is not None
```

### 11.3 Mock 调用断言

```python
# 断言被调用
mock_llm.complete.assert_called_once()

# 断言调用参数
mock_llm.complete.assert_called_with(
    messages=[{"role": "user", "content": "analyze"}],
    temperature=0.1,
)

# 断言调用次数
assert mock_llm.complete.call_count == 3
```

### 11.4 禁止的断言

| 禁止做法 | 原因 | 正确做法 |
|---------|------|---------|
| `assert True` | 无意义，永远通过 | 断言具体的业务状态 |
| `assert result`（对非布尔值） | 隐式布尔转换，意图不明确 | `assert result is not None` 或 `assert len(result) > 0` |
| `assert not error` | 不明确什么条件构成 error | `assert exc_info.value is None` 或 `pytest.raises` |
| `assert response` | 不验证具体内容 | `assert response.status_code == 200` |
| `try: ... except: pass` | 吞掉异常 | `pytest.raises` 或明确断言 |

---

## 12. 覆盖率要求

### 12.1 分层覆盖率目标

| 层级 | 最低覆盖率 | 说明 |
|------|-----------|------|
| kernel 层（状态机、核心逻辑） | >= 80% | 核心业务逻辑，必须高覆盖 |
| API 层（路由、权限、参数校验） | >= 70% | HTTP 契约验证 |
| Service 层 | >= 70% | 业务编排逻辑 |
| 整体 | >= 75% | CI 门禁 |

### 12.2 覆盖率运行

```bash
# 全量覆盖率报告
pytest --cov=reqradar --cov-report=term-missing

# 仅 kernel 层覆盖率
pytest tests/unit/kernel/ --cov=reqradar.kernel --cov-report=term-missing

# HTML 报告（浏览器查看）
pytest --cov=reqradar --cov-report=html
```

### 12.3 覆盖率排除

以下代码不计入覆盖率统计（在 `pyproject.toml` 中配置 `omit`）：

```toml
[tool.coverage.run]
omit = [
    "reqradar/cli/*",           # CLI 入口，通过 e2e 测试覆盖
    "reqradar/web/static/*",    # 前端构建产物
    "tests/*",                  # 测试代码本身
]
```

---

## 13. 测试覆盖边界

每个模块的测试必须覆盖以下场景（来自 AGENTS.md）：

### 13.1 边界清单

| # | 边界场景 | HTTP 状态码 | 测试要点 |
|---|---------|------------|---------|
| 1 | 成功路径 | 200/201 | 正常输入，预期输出 |
| 2 | 未认证访问 | 401 | 无 token 或 token 过期 |
| 3 | 权限不足 | 403 | 非 owner/admin 访问他人资源 |
| 4 | 不存在资源 | 404 | ID 不存在或已删除 |
| 5 | 无效参数 | 422 | 缺失字段、错误类型、越界值 |
| 6 | 重复数据 | 409 | 唯一约束冲突（如重复注册） |
| 7 | 空列表/空内容 | 200 | 返回空列表而非 404 |
| 8 | 外部服务失败 | 500/502 | mock LLM/MinIO/Redis 失败 |
| 9 | 路径遍历攻击 | 400/403 | 文件读取类端点的 `../` 攻击 |

### 13.2 边界测试模板

```python
class TestSessionAPI:
    """Session API 完整边界测试。"""

    # 1. 成功路径
    async def test_create_session_succeeds(self, client, auth_headers, project):
        ...

    # 2. 未认证访问
    async def test_create_session_unauthenticated_returns_401(self, client):
        resp = await client.post("/api/v2/sessions", json={...})
        assert resp.status_code in (401, 403)

    # 3. 权限不足
    async def test_cancel_other_users_session_returns_403(
        self, client, auth_headers, other_user_session_id
    ):
        resp = await client.post(
            f"/api/v2/sessions/{other_user_session_id}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 403

    # 4. 不存在资源
    async def test_get_nonexistent_session_returns_404(self, client, auth_headers):
        resp = await client.get(
            "/api/v2/sessions/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    # 5. 无效参数
    async def test_create_session_with_negative_budget_returns_422(
        self, client, auth_headers, project
    ):
        resp = await client.post(
            "/api/v2/sessions",
            headers=auth_headers,
            json={"project_id": str(project.id), "config": {"context_budget": -1}},
        )
        assert resp.status_code == 422

    # 6. 重复数据
    async def test_start_already_running_session_returns_409(
        self, client, auth_headers, running_session_id
    ):
        resp = await client.post(
            f"/api/v2/sessions/{running_session_id}/start",
            headers=auth_headers,
        )
        assert resp.status_code == 409

    # 7. 空列表
    async def test_list_sessions_returns_empty_list(self, client, auth_headers):
        resp = await client.get("/api/v2/sessions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    # 8. 外部服务失败
    async def test_create_session_llm_unavailable_returns_502(
        self, client, auth_headers, project, mocker
    ):
        mock_llm = mocker.patch("reqradar.modules.llm_client.create_llm_client")
        mock_llm.side_effect = LLMException("Service unavailable")
        resp = await client.post(
            "/api/v2/sessions",
            headers=auth_headers,
            json={"project_id": str(project.id), "config": {}},
        )
        assert resp.status_code in (500, 502)

    # 9. 路径遍历攻击
    async def test_get_session_files_path_traversal_returns_400(
        self, client, auth_headers, session_id
    ):
        resp = await client.get(
            f"/api/v2/sessions/{session_id}/files?path=../../etc/passwd",
            headers=auth_headers,
        )
        assert resp.status_code in (400, 403)
```

### 13.3 边界覆盖检查清单

每个 API 模块完成后，使用以下清单自查：

```
[ ] 成功路径：至少 1 个正向测试
[ ] 未认证(401)：所有端点的无 token 访问
[ ] 权限不足(403)：跨用户访问、普通用户访问管理接口
[ ] 不存在(404)：GET/PUT/DELETE 不存在的 ID
[ ] 无效参数(422)：缺失必填字段、类型错误、越界值
[ ] 重复数据(409)：唯一约束冲突
[ ] 空列表(200)：无数据时返回空列表
[ ] 外部服务失败：mock LLM/存储失败
[ ] 路径遍历：文件读取类端点的 `../` 攻击
```

---

## 附录 A：测试数据工厂

使用 `tests/factories.py` 中的工厂函数构造测试数据，禁止在测试中手写大段数据构造代码：

| 工厂函数 | 用途 | 示例 |
|---------|------|------|
| `build_user(**overrides)` | 构造 User ORM 对象 | `build_user(role="admin")` |
| `build_project(owner_id, **overrides)` | 构造 Project ORM 对象 | `build_project(owner_id=user.id, name="test")` |
| `build_analysis_task(project_id, user_id, **overrides)` | 构造 AnalysisTask | `build_analysis_task(..., status=TaskStatus.FAILED)` |
| `build_report(task_id, **overrides)` | 构造 Report | `build_report(task_id=task.id)` |
| `build_report_version(task_id, created_by, **overrides)` | 构造 ReportVersion | `build_report_version(..., version_number=2)` |
| `unique_email(prefix)` | 生成唯一邮箱 | `unique_email("test")` → `"test1@example.com"` |

**工厂函数使用原则**：
- 只传入需要覆盖的字段，其余使用默认值
- 不依赖自增 ID，工厂内部维护计数器
- 返回 ORM 对象但**不写入数据库**，由测试决定何时 `add + commit`

---

## 附录 B：常见陷阱与解决方案

### B.1 httpx.ASGITransport 不触发 lifespan

**问题**：httpx 0.28+ 的 `ASGITransport(app=app)` 不触发 FastAPI lifespan，导致 `app.state.*` 未初始化。

**解决**：手动设置 `app.state`：

```python
app = create_app()
app.state.config = config
app.state.paths = paths
app.state.session_factory = session_factory
app.state.report_storage = report_storage
```

### B.2 Module-Level Binding Trap

**问题**：`from module import func` 在导入时绑定引用，运行时 monkeypatching `module.func` 不影响已绑定引用。

**解决**：API 端点使用 `request.app.state.config` 而非 `from config import load_config`。

### B.3 异步测试中的 db_session 泄漏

**问题**：测试中未 rollback 的 session 会影响后续测试。

**解决**：fixture 中使用 `yield + rollback`：

```python
@pytest.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
        await session.rollback()
```

### B.4 Mock 泄漏到其他测试

**问题**：模块级 mock 或未正确清理的 fixture 导致 mock 影响其他测试。

**解决**：
- 使用 `mocker` fixture（自动清理）
- 使用 `monkeypatch` fixture（自动清理）
- 使用 `with patch(...)` 块（限定作用范围）
- 禁止模块级 `patch()` 调用

### B.5 SQLite 与 PostgreSQL 行为差异

**问题**：开发用 SQLite，生产用 PostgreSQL，部分 SQL 特性不一致（如 JSONB 索引、部分索引）。

**解决**：
- 测试中不依赖 PostgreSQL 特有特性
- JSONB 查询使用 SQLAlchemy ORM 而非原生 SQL
- 需要验证 PG 特有行为的测试标记为 `@pytest.mark.postgres` 并在 CI 中单独运行
