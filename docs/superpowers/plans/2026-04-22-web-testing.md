# ReqRadar Web 模块测试计划

**Goal:** 为 Web 模块建立完整的测试覆盖，确保 Pydantic 迁移、Scheduler 回调、API 端点、Service 层、WebSocket 通信的可靠性，同时保证 CLI 零回归。

**Principle:** 测试金字塔——底层单元测试覆盖核心逻辑，上层集成测试覆盖 API 和 Service 层，最小化 E2E 测试覆盖完整用户流程。所有测试通过 `PYTHONPATH=src pytest` 运行。

---

## 一、测试分层策略

```
┌──────────────────────────────────────────────────────────────┐
│  E2E 测试（playwright） — 验证完整用户流程，测试用例最少       │
├──────────────────────────────────────────────────────────────┤
│  API 集成测试（httpx + ASGITransport）— 每个端点覆盖         │
├──────────────────────────────────────────────────────────────┤
│  Service 单元测试 — ProjectStore、AnalysisRunner 隔离测试     │
├──────────────────────────────────────────────────────────────┤
│  Pydantic 序列化测试 — 核心模型 round-trip                  │
├──────────────────────────────────────────────────────────────┤
│  Scheduler 回调测试 — CLI 零回归 + 回调触发验证              │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、测试文件清单

```
tests/
├── test_context_pydantic.py          # Pydantic 序列化 round-trip
├── test_scheduler_callback.py        # Scheduler 回调触发
├── test_web_api_auth.py             # 认证 API
├── test_web_api_projects.py         # 项目 CRUD + 索引触发
├── test_web_api_analyses.py         # 分析提交/列表/重试
├── test_web_api_reports.py          # 报告获取/下载
├── test_web_services.py             # ProjectStore + AnalysisRunner
├── test_web_websocket.py           # WebSocket 消息广播
├── test_web_integration.py          # E2E（pytest-playwright，可选）
```

---

## 三、测试fixtures和基础设施

### 3.1 共享 fixtures

创建 `tests/conftest_web.py`（pytest-asyncio fixtures）：

```python
"""Web 模块共享测试 fixtures."""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_DB_FILE = tempfile.mktemp(suffix=".db")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    from reqradar.web.database import Base, create_engine
    eng = create_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session_factory):
    """完整应用测试客户端（注入 session_factory 到 dependencies）。"""
    import reqradar.web.dependencies as deps
    deps.async_session_factory = session_factory

    from reqradar.web.app import create_app
    app = create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    # 清理
    await session_factory().close()


@pytest_asyncio.fixture
async def auth_client(session_factory):
    """已认证的测试客户端（自动注册+登录）。"""
    import reqradar.web.dependencies as deps
    deps.async_session_factory = session_factory

    from reqradar.web.app import create_app
    app = create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 注册
        await c.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "secret123",
            "display_name": "Test User",
        })
        # 登录
        resp = await c.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "secret123",
        })
        token = resp.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
```

### 3.2 测试数据库隔离

每个测试文件使用独立的临时数据库文件：
```python
# conftest_web.py
TEST_DB_FILE = tempfile.mktemp(suffix=".db")
# session fixture 在 setup 时 create_all，teardown 时 drop_all + dispose
```

### 3.3 清理规则

- 测试结束后删除临时数据库文件
- 临时上传目录 `.reqradar/test_uploads/` 在 session 级别清理
- 每个测试函数有独立的 `db_session` fixture（自动回滚）

---

## 四、Task 1：Pydantic 序列化测试

**文件：** `tests/test_context_pydantic.py`

### 覆盖范围

| 测试用例 | 验证内容 |
|---------|---------|
| `test_term_definition_serialization` | 单模型 model_dump → model_validate |
| `test_step_result_timestamp_serialization` | datetime 序列化/反序列化 |
| `test_requirement_understanding_serialization` | 嵌套列表（terms）序列化 |
| `test_deep_analysis_serialization` | 完整嵌套结构（risks、decision_summary、evidence_items、impact_domains） |
| `test_analysis_context_full_round_trip` | 完整 context 序列化 + model_dump_json → model_validate_json |
| `test_analysis_context_path_coercion` | 字符串 "docs/req.md" → Path 对象 |
| `test_model_dump_excludes_private` | model_dump() 不包含 Pydantic 内部字段 |
| `test_analysis_context_properties` | `@property` 方法在序列化后仍正常工作 |
| `test_step_result_mark_failed` | 可变方法 mark_failed() 正常 |
| `test_analysis_context_store_get_result` | store_result/get_result 正常 |

### 关键断言

```python
# 路径类型自动转换
ctx = AnalysisContext.model_validate({"requirement_path": "test.md", ...})
assert isinstance(ctx.requirement_path, Path)

# JSON round-trip
json_str = ctx.model_dump_json()
ctx2 = AnalysisContext.model_validate_json(json_str)
assert ctx2.deep_analysis.risk_level == ctx.deep_analysis.risk_level

# 嵌套对象
assert ctx2.understanding.terms[0].term == ctx.understanding.terms[0].term
```

### 回归测试

在 `tests/test_context.py` 中添加检查，确保 Pydantic 迁移后：
- `AnalysisContext` 属性访问方式不变
- `step_results` 字典读写正常
- `@property` 计算属性返回值不变

---

## 五、Task 2：Scheduler 回调测试

**文件：** `tests/test_scheduler_callback.py`

### 覆盖范围

| 测试用例 | 验证内容 |
|---------|---------|
| `test_scheduler_calls_on_step_start` | 步骤开始时触发 on_step_start |
| `test_scheduler_calls_on_step_complete` | 步骤完成时触发 on_step_complete（成功和失败都触发） |
| `test_scheduler_no_callback_is_default` | 不传回调时 CLI 模式正常（rich.progress 不报错） |
| `test_scheduler_callback_on_failed_step` | 步骤失败时 on_step_complete 收到 success=False |
| `test_scheduler_fatal_error_delivers_callback` | FatalError 时回调在 break 前触发 |
| `test_scheduler_callback_receives_correct_step_names` | 回调收到的 step_name 与 STEPS 定义一致 |
| `test_scheduler_callback_with_all_steps` | 所有 6 个步骤都触发 start + complete |

### 关键验证

```python
@pytest.mark.asyncio
async def test_scheduler_calls_on_step_complete():
    completed_steps = []

    async def on_complete(step_name: str, result: StepResult):
        completed_steps.append((step_name, result.success))

    # 最小化 handler：sleep(0) 让出控制权
    async def step_read(ctx):
        return "content"

    async def step_extract(ctx):
        return None

    scheduler = Scheduler(
        read_handler=step_read,
        extract_handler=step_extract,
    )

    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_complete=on_complete)

    # read 和 extract 都触发
    assert len(completed_steps) >= 2
    step_names = [name for name, _ in completed_steps]
    assert "read" in step_names
    assert "extract" in step_names
    # 都是成功的
    assert all(success for _, success in completed_steps)
```

### CLI 回归验证

确保 `with Progress()` 上下文在以下场景不崩溃：
- 同步异常（handler raise）
- 异步异常（handler 返回错误）
- 空 handler（handler 为 None，跳过步骤）

---

## 六、Task 3：认证 API 测试

**文件：** `tests/test_web_api_auth.py`

### 覆盖范围

| 测试用例 | 验证内容 |
|---------|---------|
| `test_register_success` | 注册成功返回 200 + user 对象 |
| `test_register_duplicate_email` | 重复邮箱返回 400 |
| `test_register_invalid_email` | 无效邮箱格式返回 422 |
| `test_login_success` | 登录成功返回 200 + access_token |
| `test_login_wrong_password` | 错误密码返回 401 |
| `test_login_nonexistent_user` | 不存在用户返回 401 |
| `test_me_authenticated` | 带 token 访问返回用户信息 |
| `test_me_unauthenticated` | 无 token 访问返回 401 |
| `test_protected_endpoint_without_token` | 受保护端点无 token 返回 401 |
| `test_jwt_token_payload` | token payload 包含 user_id |
| `test_password_hashed_not_plaintext` | 数据库中 password_hash 不是明文 |

### 测试流程

```python
@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/api/auth/register", json={
        "email": "alice@example.com",
        "password": "secure456",
        "display_name": "Alice",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["display_name"] == "Alice"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

@pytest.mark.asyncio
async def test_login_success(client):
    # 先注册
    await client.post("/api/auth/register", json={
        "email": "bob@example.com",
        "password": "secret123",
    })
    # 再登录
    resp = await client.post("/api/auth/login", json={
        "email": "bob@example.com",
        "password": "secret123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_me_authenticated(auth_client):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"
```

---

## 七、Task 4：项目 API 测试

**文件：** `tests/test_web_api_projects.py`

### 覆盖范围

| 测试用例 | 验证内容 |
|---------|---------|
| `test_list_projects_empty` | 空项目列表返回空数组 |
| `test_create_project` | 创建项目成功 |
| `test_create_project_requires_auth` | 未登录创建返回 401 |
| `test_get_project` | 获取项目详情 |
| `test_get_project_not_found` | 不存在的项目返回 404 |
| `test_update_project` | 更新项目信息 |
| `test_update_project_partial` | 部分字段更新 |
| `test_delete_project` | 删除项目（可选，Phase 1 可跳过） |
| `test_project_fields` | 返回字段包含所有必要属性 |

### 测试流程

```python
@pytest.mark.asyncio
async def test_create_project(auth_client):
    resp = await auth_client.post("/api/projects", json={
        "name": "MyProject",
        "description": "A test project",
        "repo_path": "/path/to/repo",
        "docs_path": "/path/to/docs",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "MyProject"
    assert "id" in data
    assert data["index_path"] == ".reqradar/index/MyProject"

@pytest.mark.asyncio
async def test_get_project_not_found(auth_client):
    resp = await auth_client.get("/api/projects/99999")
    assert resp.status_code == 404
```

---

## 八、Task 5：分析 API 测试

**文件：** `tests/test_web_api_analyses.py`

### 覆盖范围

| 测试用例 | 验证内容 |
|---------|---------|
| `test_submit_analysis_text` | 提交纯文本分析 |
| `test_submit_analysis_requires_project` | 项目不存在返回 404 |
| `test_submit_analysis_requires_auth` | 未登录返回 401 |
| `test_list_analyses_empty` | 空列表 |
| `test_list_analyses_filter_by_project` | 按项目筛选 |
| `test_list_analyses_filter_by_status` | 按状态筛选 |
| `test_get_analysis` | 获取分析详情（含 step_summary） |
| `test_get_analysis_not_found` | 不存在返回 404 |
| `test_retry_analysis` | 重试失败的分析 |
| `test_retry_completed_analysis` | 重试已完成分析返回 400 |

### 分析提交测试（需 mock LLM）

```python
@pytest.mark.asyncio
async def test_submit_analysis_text(auth_client, session_factory):
    # 先创建项目
    proj_resp = await auth_client.post("/api/projects", json={
        "name": "TestProj",
    })
    project_id = proj_resp.json()["id"]

    # 提交分析（由于没有 LLM，最终会失败，但能验证 API）
    resp = await auth_client.post("/api/analyses", json={
        "project_id": project_id,
        "requirement_name": "Test Requirement",
        "requirement_text": "This is a test requirement about web module.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["pending", "running"]  # 异步任务已提交
    assert data["requirement_text"] == "This is a test requirement about web module."
```

### 文件上传测试

```python
@pytest.mark.asyncio
async def test_upload_analysis_file(auth_client):
    proj_resp = await auth_client.post("/api/projects", json={"name": "UploadTest"})
    project_id = proj_resp.json()["id"]

    # 上传 Markdown 文件
    files = {"file": ("req.md", "# Test Requirement\nThis is a test.", "text/markdown")}
    data = {"project_id": project_id, "requirement_name": "Uploaded Req"}
    resp = await auth_client.post("/api/analyses/upload", data=data, files=files)
    assert resp.status_code == 200
    result = resp.json()
    assert "task_id" in result
```

---

## 九、Task 6：报告 API 测试

**文件：** `tests/test_web_api_reports.py`

### 覆盖范围

| 测试用例 | 验证内容 |
|---------|---------|
| `test_get_report` | 获取报告 JSON（含 content_html） |
| `test_get_report_not_found` | 不存在返回 404 |
| `test_download_markdown` | 下载 Markdown 文件（responseType blob） |
| `test_get_html` | 获取预渲染 HTML |
| `test_report_includes_risk_level` | 报告 JSON 包含 risk_level（从 context_json 提取） |

### 报告获取测试

```python
@pytest.mark.asyncio
async def test_get_report(auth_client, session_factory):
    # 1. 创建项目和任务（模拟已完成的任务）
    proj_resp = await auth_client.post("/api/projects", json={"name": "ReportTest"})
    project_id = proj_resp.json()["id"]

    # 2. 直接在数据库中插入一个完成的分析任务和报告（跳过 LLM）
    from reqradar.web.models import AnalysisTask, Report
    async with session_factory() as session:
        task = AnalysisTask(
            project_id=project_id,
            user_id=1,
            requirement_name="Test",
            requirement_text="Test content",
            status="completed",
            context_json='{"requirement_path": "test.md", "step_results": {}}',
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        report = Report(
            task_id=task.id,
            content_markdown="# Test Report\nContent here",
            content_html="<h1>Test Report</h1><p>Content here</p>",
        )
        session.add(report)
        await session.commit()

    # 3. 获取报告
    resp = await auth_client.get(f"/api/reports/{task.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "content_markdown" in data
    assert "content_html" in data
    assert "Test Report" in data["content_markdown"]

@pytest.mark.asyncio
async def test_download_markdown(auth_client, session_factory):
    # 插入报告（同上）
    ...
    resp = await auth_client.get(f"/api/reports/{task.id}/markdown")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/plain; charset=utf-8"
```

---

## 十、Task 7：Service 层测试

**文件：** `tests/test_web_services.py`

### 10.1 ProjectStore 测试

| 测试用例 | 验证内容 |
|---------|---------|
| `test_project_store_caches_code_graph` | 同一 project_id 第二次调用不重新加载 |
| `test_project_store_invalidates` | invalidate 后重新加载 |
| `test_project_store_missing_index_path` | 索引不存在时返回 None |
| `test_project_store_concurrent_access` | 并发请求同一 project 不重复构建 |

```python
@pytest.mark.asyncio
async def test_project_store_caches_code_graph():
    from reqradar.web.services.project_store import ProjectStore
    store = ProjectStore()

    # 首次加载
    cg1 = await store.get_code_graph(1, str(test_index_path))
    # 第二次加载应返回缓存
    cg2 = await store.get_code_graph(1, str(test_index_path))
    assert cg1 is cg2  # 同一对象引用

@pytest.mark.asyncio
async def test_project_store_concurrent_access():
    """多个协程同时请求同一项目，应只构建一次。"""
    from reqradar.web.services.project_store import ProjectStore
    store = ProjectStore()

    async def get():
        return await store.get_code_graph(1, str(test_index_path))

    # 并发调用
    results = await asyncio.gather(get(), get(), get())
    # 应只有一个构建调用（通过 mock 验证）
```

### 10.2 AnalysisRunner 并发控制测试

| 测试用例 | 验证内容 |
|---------|---------|
| `test_runner_respects_concurrency_limit` | 超过 Semaphore 数量的并发任务被阻塞 |
| `test_runner_cancels_task` | 取消任务后不再执行 |

```python
@pytest.mark.asyncio
async def test_runner_respects_concurrency_limit(session_factory, monkeypatch):
    """验证并发数超过限制时新任务被阻塞。"""
    from reqradar.web.services.analysis_runner import AnalysisRunner

    runner = AnalysisRunner(max_concurrent=1)

    start_time = asyncio.get_event_loop().time()

    # 提交两个任务
    # 第二个任务应等待第一个完成后才能执行
    await runner.submit(task_id=1, ...)
    await runner.submit(task_id=2, ...)

    elapsed = asyncio.get_event_loop().time() - start_time
    # 至少要等一个任务完成（假设每个任务 sleep 0.1s）
    assert elapsed >= 0.1
```

---

## 十一、Task 8：WebSocket 测试

**文件：** `tests/test_web_websocket.py`

### 覆盖范围

| 测试用例 | 验证内容 |
|---------|---------|
| `test_ws_connect` | 连接建立成功 |
| `test_ws_subscribe_to_task` | 订阅任务后收到消息 |
| `test_ws_unsubscribe_on_disconnect` | 断开连接后取消订阅 |
| `test_ws_invalid_token` | 无效 token 连接拒绝 |
| `test_ws_broadcast_step_start` | step_start 事件广播 |
| `test_ws_broadcast_step_complete` | step_complete 事件广播 |
| `test_ws_broadcast_analysis_complete` | analysis_complete 事件广播 |
| `test_ws_multiple_clients` | 多个客户端同时订阅同一任务 |

### 测试实现

```python
@pytest.mark.asyncio
async def test_ws_connect(session_factory):
    import reqradar.web.dependencies as deps
    deps.async_session_factory = session_factory
    from reqradar.web.app import create_app

    app = create_app()

    async with AsyncClient(app=app) as client:
        # 先注册登录获取 token
        await client.post("/api/auth/register", json={
            "email": "ws@test.com", "password": "secret",
        })
        login_resp = await client.post("/api/auth/login", json={
            "email": "ws@test.com", "password": "secret",
        })
        token = login_resp.json()["access_token"]

        # 创建项目和任务
        proj_resp = await client.post("/api/projects", json={"name": "WSTest"})
        project_id = proj_resp.json()["id"]
        task_resp = await client.post("/api/analyses", json={
            "project_id": project_id,
            "requirement_text": "Test",
        })
        task_id = task_resp.json()["id"]

        # WebSocket 连接
        async with client.websocket_connect(f"/api/analyses/{task_id}/ws?token={token}") as ws:
            # 接收 step_start 或其他消息（分析可能已开始）
            data = await ws.receive_json()
            assert data["type"] in ["step_start", "step_complete"]

@pytest.mark.asyncio
async def test_ws_invalid_token(session_factory):
    ...
    # 连接应被拒绝（close code 4001）
```

---

## 十二、Task 9：回归测试（现有测试）

**目标：** Pydantic 迁移后所有现有测试仍通过

```bash
# 迁移后运行全部测试
PYTHONPATH=src pytest tests/ -v --tb=short
```

### 预期修复项

| 文件 | 问题 | 修复方式 |
|------|------|---------|
| `tests/test_report.py` | `dataclasses.asdict()` | 替换为 `model_dump()` |
| `tests/test_context.py` | `type(x).__name__` 检查 | 可能需要调整断言 |
| `tests/test_scheduler.py` | 回调相关 | 无需改动（不涉及 Pydantic） |
| `tests/test_llm_client.py` | 类型注解 | 可能需要调整 |

---

## 十三、Task 10：CLI 回归测试

**目标：** Scheduler 回调改造后 CLI 命令仍正常工作

```bash
# 手动测试 CLI 流程
cd /home/easy/projects/ReqRadar
PYTHONPATH=src reqradar index -r ./src -o .reqradar/test_index
PYTHONPATH=src reqradar analyze ./docs/requirements/web-module.md -i .reqradar/test_index -o ./reports_test
```

验证点：
- `reqradar index` 输出 rich 进度条正常
- `reqradar analyze` 输出 6 步进度条正常
- 报告生成到 `./reports_test/` 目录
- 没有回调相关的异常或警告

---

## 十四、执行计划

| 阶段 | 测试任务 | 前置条件 | 负责 |
|------|---------|---------|------|
| 0-1 | Pydantic 序列化测试 | Task 0-1 完成 | 后端 |
| 0-2 | Scheduler 回调测试 | Task 0-2 完成 | 后端 |
| 1 | 认证 API 测试 | Task 1 完成 | 后端 |
| 2 | 项目/分析/报告 API 测试 | Task 2 完成 | 后端 |
| 2 | Service 层测试 | Task 2 完成 | 后端 |
| 2 | WebSocket 测试 | Task 2 完成 | 后端 |
| 全部 | 回归测试（全部现有测试） | Pydantic 迁移完成 | 后端 |
| 全部 | CLI 回归手动验证 | Scheduler 回调完成 | 后端 |
| 3 | E2E 测试（可选） | 后端 + 前端完成 | 全栈 |

---

## 十五、测试数据管理

### 15.1 固定测试数据

测试 fixtures 中使用固定的测试数据，不依赖外部网络：
- 用户：`test@example.com` / `secret123`
- 项目名：`TestProject`、`ReportTest` 等固定名称
- 需求文本：简短的有意义文本

### 15.2 临时文件和目录

```python
@pytest.fixture
def temp_upload_dir():
    d = Path(".reqradar/test_uploads")
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def temp_index_dir():
    d = Path(".reqradar/test_index")
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)
```

### 15.3 Mock LLM 调用

对于需要完整分析流程的测试（耗时较长且依赖 LLM API），使用 monkeypatch mock `llm_client.complete`：

```python
@pytest.mark.asyncio
async def test_analysis_with_mocked_llm(auth_client, monkeypatch):
    async def mock_complete(*args, **kwargs):
        return '{"summary": "mocked result", "risk_level": "low"}'

    monkeypatch.setattr(
        "reqradar.modules.llm_client.OpenAIClient.complete",
        mock_complete,
    )
    # ...
```

---

## 十六、覆盖率目标

| 测试文件 | 目标行覆盖率 | 关键覆盖点 |
|---------|------------|---------|
| `test_context_pydantic.py` | 95%+ | 所有模型的 model_dump/model_validate |
| `test_scheduler_callback.py` | 90%+ | 6 个步骤的 start/complete 回调 |
| `test_web_api_auth.py` | 90%+ | 注册/登录/鉴权所有分支 |
| `test_web_api_projects.py` | 85%+ | CRUD + 边界条件 |
| `test_web_api_analyses.py` | 80%+ | 提交/列表/重试 |
| `test_web_api_reports.py` | 85%+ | JSON/HTML/Markdown 下载 |
| `test_web_services.py` | 80%+ | ProjectStore 缓存 + Runner 并发 |
| `test_web_websocket.py` | 85%+ | 连接/订阅/广播/断连 |

---

## 十七、CI 集成

在 `.github/workflows/test.yml` 中添加 Web 模块测试：

```yaml
- name: Run all tests
  run: |
    poetry install
    PYTHONPATH=src pytest tests/ -v --tb=short --cov=src/reqradar/web --cov-report=xml

- name: Frontend tests
  run: |
    cd frontend && npm install && npm run test -- --coverage
```

---

*Plan last updated: 2026-04-22*
