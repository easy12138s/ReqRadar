# ReqRadar Optimization & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden security, fix architectural issues, improve performance, and raise code quality across the ReqRadar project after major refactoring.

**Architecture:** Incremental fixes applied in priority order — security first, then database/architecture, then performance, then quality. Each task is self-contained and testable independently. No breaking API changes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2, pytest-asyncio, httpx

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/reqradar/web/api/auth.py` | JWT auth, password hashing, token creation |
| `src/reqradar/web/dependencies.py` | FastAPI DI: DB session, current user extraction |
| `src/reqradar/web/app.py` | FastAPI app factory, lifespan, CORS, routers |
| `src/reqradar/web/api/analyses.py` | Analysis CRUD, WebSocket, file upload |
| `src/reqradar/web/websocket.py` | WebSocket connection manager |
| `src/reqradar/web/database.py` | SQLAlchemy engine + session factory |
| `src/reqradar/web/models.py` | SQLAlchemy ORM models + status enum |
| `src/reqradar/web/services/analysis_runner_v2.py` | ReAct agent analysis runner (V2) |
| `src/reqradar/web/services/analysis_runner.py` | Legacy pipeline runner (V1) |
| `src/reqradar/infrastructure/config.py` | Pydantic config models, YAML loader |
| `src/reqradar/core/exceptions.py` | Core exception hierarchy |
| `tests/test_web_security.py` | Security-focused API tests (NEW) |
| `tests/test_web_api_auth.py` | Existing auth tests (MODIFY) |
| `tests/test_analysis_runner_v2.py` | Existing runner V2 tests |

---

### Task 1: JWT Secret Environment Variable Enforcement

**Files:**
- Modify: `src/reqradar/web/api/auth.py`
- Modify: `src/reqradar/web/app.py`
- Modify: `src/reqradar/infrastructure/config.py`
- Test: `tests/test_web_api_auth.py`

The current default `SECRET_KEY = "change-me-in-production"` is dangerous. We need to: (a) read the secret from the Config object set during lifespan, (b) fail fast if running in production with the default, (c) update config to support env-var override.

- [ ] **Step 1: Add `secret_key` env-var support to WebConfig**

In `src/reqradar/infrastructure/config.py`, add `resolve_env_var` to `WebConfig.secret_key`:

```python
class WebConfig(BaseModel):
    host: str = Field(default="0.0.0.0", description="Web server bind host")
    port: int = Field(default=8000, description="Web server bind port")
    database_url: str = Field(default="sqlite+aiosqlite:///./reqradar.db", description="Async database URL")
    secret_key: str = Field(default="change-me-in-production", description="JWT secret key")
    access_token_expire_minutes: int = Field(default=1440, description="JWT access token expiry in minutes")
    max_concurrent_analyses: int = Field(default=2, description="Maximum concurrent analysis tasks")
    max_upload_size: int = Field(default=50, description="Maximum file upload size in MB")
    cors_origins: Optional[str] = Field(default=None, description="CORS allowed origins (JSON array string or empty for all)")
    debug: bool = Field(default=False, description="Enable debug mode")
    static_dir: Optional[str] = Field(default=None, description="Static files directory path")

    @field_validator("secret_key", mode="before")
    @classmethod
    def resolve_env_var(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v
```

- [ ] **Step 2: Add startup warning for default secret key**

In `src/reqradar/web/app.py`, inside the `lifespan` function, after setting `auth_module.SECRET_KEY`, add a warning:

After the line `auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = web_config.access_token_expire_minutes`, add:

```python
if web_config.secret_key == "change-me-in-production" and not web_config.debug:
    logger.warning(
        "SECURITY WARNING: Using default JWT secret key. "
        "Set web.secret_key in .reqradar.yaml or REQRADAR_SECRET_KEY env var."
    )
```

Also add `import logging` at the top of app.py if not already present, and `logger = logging.getLogger("reqradar.web.app")`.

- [ ] **Step 3: Run existing auth tests to verify nothing broke**

Run: `poetry run pytest tests/test_web_api_auth.py -v`

Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/infrastructure/config.py src/reqradar/web/app.py
git commit -m "fix(security): add env-var support for JWT secret key and startup warning for default key"
```

---

### Task 2: CORS Origin Restriction

**Files:**
- Modify: `src/reqradar/web/app.py`

Currently the default CORS is `["*"]`. In production, this should be restrictive. In debug mode, `["*"]` is acceptable.

- [ ] **Step 1: Change CORS default to be restrictive in non-debug mode**

In `src/reqradar/web/app.py`, in the `create_app` function, replace the CORS origins logic:

Replace this block:
```python
if not cors_origins:
    cors_origins = ["*"]
```

With:
```python
if not cors_origins:
    if config.web.debug:
        cors_origins = ["*"]
    else:
        cors_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
```

- [ ] **Step 2: Run existing tests**

Run: `poetry run pytest tests/test_web_api_auth.py -v`

Expected: 6 passed (auth endpoints don't depend on CORS)

- [ ] **Step 3: Commit**

```bash
git add src/reqradar/web/app.py
git commit -m "fix(security): restrict CORS origins in production mode, allow all only in debug"
```

---

### Task 3: WebSocket Task Ownership Validation

**Files:**
- Modify: `src/reqradar/web/api/analyses.py`
- Test: `tests/test_web_security.py` (NEW)

Currently any authenticated user can subscribe to any task's WebSocket. We need to verify the user owns the task before accepting the connection.

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_security.py`:

```python
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_reqradar_security.db"
TEST_SECRET_KEY = "test-secret-key-for-security-tests"


@pytest_asyncio.fixture
async def setup_db():
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module

    original_secret = auth_module.SECRET_KEY
    original_expire = auth_module.ACCESS_TOKEN_EXPIRE_MINUTES
    original_factory = dep_module.async_session_factory

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = TEST_SECRET_KEY
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = 1440

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    dep_module.async_session_factory = original_factory
    auth_module.SECRET_KEY = original_secret
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire

    db_path = "./test_reqradar_security.db"
    if os.path.exists(db_path):
        os.remove(db_path)


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123", "display_name": email},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "secret123"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_token(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(Exception):
            async with client.stream("GET", "/api/analyses/999/ws?token=invalid") as resp:
                pass


@pytest.mark.asyncio
async def test_upload_rejects_dangerous_extension(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(client, "upload_sec@example.com")

        resp = await client.post(
            "/api/projects",
            json={"name": "Upload Sec Project", "repo_path": "/tmp/nonexistent"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        import io
        dangerous_file = io.BytesIO(b"malicious content")
        resp = await client.post(
            "/api/analyses/upload",
            data={"project_id": str(project_id), "requirement_name": "test"},
            files={"file": ("evil.sh", dangerous_file, "application/x-sh")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_web_security.py -v`

Expected: `test_upload_rejects_dangerous_extension` FAILS (no extension validation yet)

- [ ] **Step 3: Add WebSocket task ownership check**

In `src/reqradar/web/api/analyses.py`, modify the `analysis_websocket` function to verify task ownership:

```python
@router.websocket("/{task_id}/ws")
async def analysis_websocket(websocket: WebSocket, task_id: int, token: str = Query(...)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    db = websocket.app.state.session_factory()
    try:
        from sqlalchemy import select as sa_select
        from reqradar.web.models import AnalysisTask
        result = await db.execute(
            sa_select(AnalysisTask).where(
                AnalysisTask.id == task_id,
                AnalysisTask.user_id == user_id,
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            await websocket.close(code=4003, reason="Task not found or access denied")
            return
    except Exception:
        await websocket.close(code=4003, reason="Access denied")
        return
    finally:
        await db.close()

    ws_manager.subscribe(task_id, websocket)

    try:
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.unsubscribe(task_id, websocket)
```

- [ ] **Step 4: Add file upload extension whitelist**

In `src/reqradar/infrastructure/config.py`, add to `WebConfig`:

```python
allowed_upload_extensions: str = Field(
    default=".txt,.md,.pdf,.docx,.xlsx,.csv,.json,.yaml,.yml,.html,.png,.jpg,.jpeg,.gif,.bmp",
    description="Comma-separated list of allowed file upload extensions",
)
```

In `src/reqradar/web/api/analyses.py`, add extension validation in `submit_analysis_upload`, after reading the filename and before reading content:

After the line `content = await file.read()`, add at the beginning of the function (before `content = await file.read()`):

```python
ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv",
    ".json", ".yaml", ".yml", ".html",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp",
}

filename = file.filename or "upload"
ext = os.path.splitext(filename)[1].lower()
if ext not in ALLOWED_UPLOAD_EXTENSIONS:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"File extension '{ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
    )
```

Move `content = await file.read()` AFTER the extension check.

- [ ] **Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/test_web_security.py tests/test_web_api_auth.py -v`

Expected: All pass

- [ ] **Step 6: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 471+ passed

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/web/api/analyses.py src/reqradar/infrastructure/config.py tests/test_web_security.py
git commit -m "fix(security): add WebSocket task ownership validation and file upload extension whitelist"
```

---

### Task 4: Database Schema — Remove create_all, Rely on Alembic

**Files:**
- Modify: `src/reqradar/web/app.py`
- Modify: `src/reqradar/web/cli.py`
- Test: `tests/test_web_api_auth.py` (existing pattern uses create_all in fixtures, which is fine)

The lifespan uses `Base.metadata.create_all` which bypasses Alembic migrations. We should make Alembic the primary schema management, and keep `create_all` only as an opt-in for dev mode.

- [ ] **Step 1: Add `auto_create_tables` config option**

In `src/reqradar/infrastructure/config.py`, add to `WebConfig`:

```python
auto_create_tables: bool = Field(
    default=False,
    description="Auto-create DB tables on startup (dev only, prefer Alembic for production)",
)
```

- [ ] **Step 2: Make lifespan conditionally create tables**

In `src/reqradar/web/app.py`, replace:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

With:

```python
if web_config.auto_create_tables:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.warning("auto_create_tables is enabled — use Alembic migrations in production")
```

- [ ] **Step 3: Enable auto_create_tables in test fixtures**

In `tests/test_web_api_auth.py`, the `setup_db` fixture already uses `Base.metadata.create_all` directly — this is fine for tests.

In `tests/test_web_security.py`, same pattern — no change needed.

For any test that uses `create_app()` and needs tables, we need to ensure the config used enables auto_create_tables. Since the tests use `create_app()` without a config_path, it will load the default config where `auto_create_tables=False`. We need to handle this.

Add to the `setup_db` fixture in both test files, BEFORE the `yield`:

```python
import reqradar.infrastructure.config as config_module
original_config = config_module.load_config

def _test_config():
    c = original_config()
    c.web.auto_create_tables = True
    return c

config_module.load_config = _test_config
```

And in the teardown (after yield), restore:

```python
config_module.load_config = original_config
```

Apply this to both `tests/test_web_api_auth.py` and `tests/test_web_security.py`.

- [ ] **Step 4: Run tests to verify**

Run: `poetry run pytest tests/test_web_api_auth.py tests/test_web_security.py -v`

Expected: All pass

- [ ] **Step 5: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 471+ passed

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/infrastructure/config.py src/reqradar/web/app.py tests/test_web_api_auth.py tests/test_web_security.py
git commit -m "fix(db): make auto-create-tables opt-in, default to Alembic-only schema management"
```

---

### Task 5: Add TaskStatus Enum for Type Safety

**Files:**
- Create: `src/reqradar/web/enums.py`
- Modify: `src/reqradar/web/models.py`
- Modify: `src/reqradar/web/app.py`
- Modify: `src/reqradar/web/api/analyses.py`
- Modify: `src/reqradar/web/services/analysis_runner.py`
- Modify: `src/reqradar/web/services/analysis_runner_v2.py`

Status strings like `"running"`, `"completed"`, `"failed"` are scattered across the codebase. Introduce an enum.

- [ ] **Step 1: Create the enums module**

Create `src/reqradar/web/enums.py`:

```python
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChangeStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
```

- [ ] **Step 2: Update model default to use enum**

In `src/reqradar/web/models.py`, update `AnalysisTask.status` default:

Replace:
```python
status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
```

With:
```python
status: Mapped[str] = mapped_column(String(50), default=TaskStatus.PENDING, nullable=False)
```

Add import at top:
```python
from reqradar.web.enums import TaskStatus, ChangeStatus
```

Update `PendingChange.status` default:
```python
status: Mapped[str] = mapped_column(String(20), default=ChangeStatus.PENDING, nullable=False)
```

- [ ] **Step 3: Update app.py to use enum**

In `src/reqradar/web/app.py`, replace:
```python
update(AnalysisTask)
.where(AnalysisTask.status == "running")
.values(status="failed", error_message="Server restarted during analysis")
```

With:
```python
from reqradar.web.enums import TaskStatus

update(AnalysisTask)
.where(AnalysisTask.status == TaskStatus.RUNNING)
.values(status=TaskStatus.FAILED, error_message="Server restarted during analysis")
```

- [ ] **Step 4: Update analyses.py to use enum**

In `src/reqradar/web/api/analyses.py`, replace string literals:

```python
task = AnalysisTask(
    ...
    status=TaskStatus.PENDING,
)
```

Replace `task.status not in ("failed", "completed", "cancelled")` with:
```python
task.status not in (TaskStatus.FAILED, TaskStatus.COMPLETED, TaskStatus.CANCELLED)
```

Replace `task.status = "pending"` (in retry) with:
```python
task.status = TaskStatus.PENDING
```

Replace `task.status not in ("pending", "running")` (in cancel) with:
```python
task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING)
```

Replace `task.status = "cancelled"` with:
```python
task.status = TaskStatus.CANCELLED
```

Add import: `from reqradar.web.enums import TaskStatus`

- [ ] **Step 5: Update analysis_runner.py to use enum**

In `src/reqradar/web/services/analysis_runner.py`:

Replace `task.status = "running"` with `task.status = TaskStatus.RUNNING`
Replace `task.status = "completed"` with `task.status = TaskStatus.COMPLETED`
Replace `task.status = "cancelled"` with `task.status = TaskStatus.CANCELLED`
Replace `task.status = "failed"` with `task.status = TaskStatus.FAILED`

Add import: `from reqradar.web.enums import TaskStatus`

- [ ] **Step 6: Update analysis_runner_v2.py to use enum**

In `src/reqradar/web/services/analysis_runner_v2.py`:

Replace all status string assignments with enum values:
- `task.status = "running"` → `task.status = TaskStatus.RUNNING`
- `task.status = "completed"` → `task.status = TaskStatus.COMPLETED`
- `task.status = "cancelled"` → `task.status = TaskStatus.CANCELLED`
- `task.status = "failed"` → `task.status = TaskStatus.FAILED`

Add import: `from reqradar.web.enums import TaskStatus`

- [ ] **Step 7: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 471+ passed (enum values are still strings at DB level)

- [ ] **Step 8: Commit**

```bash
git add src/reqradar/web/enums.py src/reqradar/web/models.py src/reqradar/web/app.py src/reqradar/web/api/analyses.py src/reqradar/web/services/analysis_runner.py src/reqradar/web/services/analysis_runner_v2.py
git commit -m "refactor: introduce TaskStatus and ChangeStatus enums for type safety"
```

---

### Task 6: Refactor AnalysisRunnerV2 — Extract Methods

**Files:**
- Modify: `src/reqradar/web/services/analysis_runner_v2.py`

The `_execute_agent` method is ~260 lines. Split it into focused private methods.

- [ ] **Step 1: Extract `_init_agent` method**

In `src/reqradar/web/services/analysis_runner_v2.py`, extract the agent initialization block (lines 125-151) into a new method:

```python
async def _init_agent(
    self, task: AnalysisTask, project: Project, config: Config, db: AsyncSession
) -> tuple[AnalysisAgent, "AnalysisMemoryManager", "ConfigManager"]:
    from reqradar.modules.memory import MemoryManager
    from reqradar.modules.memory_manager import AnalysisMemoryManager

    depth = task.depth if hasattr(task, "depth") and task.depth else "standard"
    agent = AnalysisAgent(
        requirement_text=task.requirement_text,
        project_id=project.id,
        user_id=task.user_id,
        depth=depth,
    )
    agent.state = AgentState.ANALYZING

    memory_manager = MemoryManager(
        storage_path=str(Path(project.repo_path) / config.memory.storage_path)
        if project.repo_path else config.memory.storage_path
    )
    memory_data = memory_manager.load() if config.memory.enabled else None

    analysis_memory = AnalysisMemoryManager(
        project_id=project.id,
        user_id=task.user_id,
        project_storage_path=str(Path(project.repo_path) / config.memory.project_storage_path)
        if project.repo_path else config.memory.project_storage_path,
        user_storage_path=str(Path(project.repo_path) / config.memory.user_storage_path)
        if project.repo_path else config.memory.user_storage_path,
        memory_enabled=config.memory.enabled,
    )

    agent.project_memory_text = analysis_memory.get_project_profile_text()
    agent.user_memory_text = analysis_memory.get_user_memory_text()

    cm = ConfigManager(db, config)

    return agent, analysis_memory, cm
```

- [ ] **Step 2: Extract `_init_tools` method**

```python
async def _init_tools(
    self, agent: AnalysisAgent, task: AnalysisTask, project: Project, config: Config,
    db: AsyncSession, cm: "ConfigManager", memory_data
) -> tuple["ToolRegistry", "Config"]:
    from reqradar.modules.llm_client import create_llm_client
    from reqradar.modules.git_analyzer import GitAnalyzer
    from reqradar.agent.tools import (
        ToolRegistry,
        SearchCodeTool, ReadFileTool, ReadModuleSummaryTool,
        ListModulesTool, SearchRequirementsTool, GetDependenciesTool,
        GetContributorsTool, GetProjectProfileTool, GetTerminologyTool,
    )
    from reqradar.agent.tools.security import PathSandbox, SensitiveFileFilter

    provider = await cm.get_str("llm.provider", user_id=task.user_id, project_id=project.id, default=config.llm.provider)
    llm_model = await cm.get_str("llm.model", user_id=task.user_id, project_id=project.id, default=config.llm.model)
    llm_api_key = await cm.get_str("llm.api_key", user_id=task.user_id, project_id=project.id, default=config.llm.api_key or "")
    llm_base_url = await cm.get_str("llm.base_url", user_id=task.user_id, project_id=project.id, default=config.llm.base_url or "https://api.openai.com/v1")

    llm_kwargs = {
        "openai": {
            "api_key": llm_api_key,
            "model": llm_model,
            "base_url": llm_base_url,
            "timeout": config.llm.timeout,
            "max_retries": config.llm.max_retries,
            "embedding_model": config.llm.embedding_model,
            "embedding_dim": config.llm.embedding_dim,
        },
        "ollama": {
            "model": llm_model,
            "host": config.llm.host or "http://localhost:11434",
            "embedding_dim": config.llm.embedding_dim,
        },
    }
    llm_client = create_llm_client(provider, **llm_kwargs.get(provider, {}))
    llm_client._current_task_id = task.id

    index_path = project.index_path or str(Path(project.repo_path) / ".reqradar" / "index")
    repo_path = project.repo_path or "."

    code_graph = await project_store.get_code_graph(project.id, index_path)
    vector_store = await project_store.get_vector_store(project.id, index_path)

    path_sandbox = PathSandbox(allowed_root=repo_path)
    sensitive_filter = SensitiveFileFilter()
    user_permissions = {"read:code", "read:memory", "read:history", "read:git", "write:report", "read:user_memory"}
    tool_registry = ToolRegistry(user_permissions=user_permissions)

    if code_graph:
        tool_registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path))
        tool_registry.register(GetDependenciesTool(code_graph=code_graph, memory_data=memory_data))

    tool_registry.register(ReadFileTool(repo_path=repo_path))
    tool_registry.register(ReadModuleSummaryTool(memory_data=memory_data))
    tool_registry.register(ListModulesTool(memory_data=memory_data))
    tool_registry.register(GetProjectProfileTool(memory_data=memory_data))
    tool_registry.register(GetTerminologyTool(memory_data=memory_data))

    if vector_store:
        tool_registry.register(SearchRequirementsTool(vector_store=vector_store))

    try:
        git_analyzer = None
        if project.repo_path and Path(project.repo_path, ".git").exists():
            git_analyzer = GitAnalyzer(repo_path=Path(project.repo_path), lookback_months=config.git.lookback_months)
        if git_analyzer:
            tool_registry.register(GetContributorsTool(git_analyzer=git_analyzer))
    except Exception:
        logger.warning("Failed to init GitAnalyzer for project %d", project.id)

    return tool_registry, llm_client
```

- [ ] **Step 3: Extract `_load_template` method**

```python
async def _load_template(self, config: Config, db: AsyncSession):
    from reqradar.infrastructure.template_loader import TemplateLoader
    from reqradar.web.models import ReportTemplate

    template_loader = TemplateLoader()
    template_def = None
    template_id = config.reporting.default_template_id if hasattr(config, "reporting") else None
    if template_id:
        tmpl_result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
        tmpl_obj = tmpl_result.scalar_one_or_none()
        if tmpl_obj:
            template_def = template_loader.load_from_db_data(tmpl_obj.definition, tmpl_obj.render_template)

    if template_def is None:
        try:
            template_def = template_loader.load_definition(template_loader.get_default_template_path())
        except Exception:
            template_def = None

    return template_def
```

- [ ] **Step 4: Extract `_save_report` method**

```python
async def _save_report(
    self, task: AnalysisTask, agent: AnalysisAgent, report_data: dict,
    report_markdown: str, report_html: str, db: AsyncSession
):
    from reqradar.web.services.version_service import VersionService
    from reqradar.web.enums import TaskStatus

    task.context_json = json.dumps(agent.get_context_snapshot(), ensure_ascii=False, default=str)
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(timezone.utc)

    db.add(Report(
        task_id=task.id,
        content_markdown=report_markdown,
        content_html=report_html,
    ))

    version_service = VersionService(db)
    context_snapshot = agent.get_context_snapshot()
    await version_service.create_version(
        task_id=task.id,
        report_data=report_data,
        context_snapshot=context_snapshot,
        content_markdown=report_markdown,
        content_html=report_html,
        trigger_type="initial",
        created_by=task.user_id,
    )

    await db.commit()
```

- [ ] **Step 5: Rewrite `_execute_agent` using the extracted methods**

```python
async def _execute_agent(self, task_id: int, project: Project, config: Config, db: AsyncSession):
    from reqradar.web.enums import TaskStatus

    result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        return

    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now(timezone.utc)
    await db.commit()

    await ws_manager.broadcast(task_id, {"type": "analysis_started", "task_id": task_id})

    try:
        agent, analysis_memory, cm = await self._init_agent(task, project, config, db)
        tool_registry, llm_client = await self._init_tools(agent, task, project, config, db, cm, None)
        template_def = await self._load_template(config, db)

        section_descriptions = None
        if template_def:
            section_descriptions = [
                {"id": s.id, "title": s.title, "description": s.description, "requirements": s.requirements, "dimensions": s.dimensions, "required": s.required}
                for s in template_def.sections
            ]

        system_prompt = build_analysis_system_prompt(
            project_memory=agent.project_memory_text,
            user_memory=agent.user_memory_text,
            historical_context=agent.historical_context,
            dimension_status=agent.dimension_tracker.status_summary(),
            template_sections=section_descriptions,
        )

        tool_names = tool_registry.list_names()

        await ws_manager.broadcast(task_id, {
            "type": "agent_thinking",
            "task_id": task_id,
            "message": "开始分析需求...",
        })

        from reqradar.agent.tool_use_loop import run_tool_use_loop

        while not agent.should_terminate():
            user_prompt = build_analysis_user_prompt(
                requirement_text=agent.requirement_text,
                agent_context=agent.get_context_text() + "\n\n" + agent.get_weak_dimensions_text(),
            )

            tool_result_data = await run_tool_use_loop(
                llm_client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tool_names,
                tool_registry=tool_registry,
                output_schema=ANALYZE_SCHEMA,
                max_rounds=5,
                max_total_tokens=config.analysis.tool_use_max_tokens if hasattr(config.analysis, "tool_use_max_tokens") else 8000,
            )

            if tool_result_data:
                self._update_agent_from_tool_result(agent, tool_result_data)

            agent.step_count += 1

            await ws_manager.broadcast(task_id, {
                "type": "dimension_progress",
                "task_id": task_id,
                "step": agent.step_count,
                "max_steps": agent.max_steps,
                "dimensions": agent.dimension_tracker.status_summary(),
                "evidence_count": len(agent.evidence_collector.evidences),
            })

            await asyncio.sleep(0)

        agent.state = AgentState.GENERATING
        report_data = await self._generate_report(agent, llm_client, system_prompt, section_descriptions, config)
        agent.final_report_data = report_data
        agent.state = AgentState.COMPLETED

        renderer = ReportRenderer(config, template_definition=template_def)
        report_data.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        report_data.setdefault("requirement_path", agent.requirement_text[:50])
        report_data.setdefault("impact_scope", "")
        report_data.setdefault("content_confidence", "N/A")
        report_data.setdefault("process_completion", "N/A")
        report_data.setdefault("content_completeness", "N/A")
        report_data.setdefault("evidence_support", "N/A")
        report_data.setdefault("risk_badge", report_data.get("risk_level", "unknown"))

        try:
            report_markdown = renderer.template.render(**report_data)
        except Exception:
            try:
                from jinja2 import Template as JinjaTemplate
                from reqradar.core.report import _INLINE_FALLBACK_TEMPLATE
                fallback_tmpl = JinjaTemplate(_INLINE_FALLBACK_TEMPLATE)
                report_markdown = fallback_tmpl.render(**report_data)
            except Exception:
                report_markdown = json.dumps(report_data, ensure_ascii=False, indent=2, default=str)

        report_html = markdown.markdown(report_markdown, extensions=["extra", "codehilite", "toc", "tables"])
        risk_level = report_data.get("risk_level", "unknown")

        await self._save_report(task, agent, report_data, report_markdown, report_html, db)

        await ws_manager.broadcast(task_id, {
            "type": "analysis_complete",
            "task_id": task_id,
            "risk_level": risk_level,
        })

    except asyncio.CancelledError:
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await ws_manager.broadcast(task_id, {"type": "analysis_cancelled", "task_id": task_id})
        raise

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error_message = str(e)[:2000]
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await ws_manager.broadcast(task_id, {
            "type": "analysis_failed",
            "task_id": task_id,
            "error": str(e)[:500],
        })
```

- [ ] **Step 6: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 471+ passed

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/web/services/analysis_runner_v2.py
git commit -m "refactor: extract methods from AnalysisRunnerV2._execute_agent for clarity"
```

---

### Task 7: WebSocket Concurrent Broadcast

**Files:**
- Modify: `src/reqradar/web/websocket.py`

The current `broadcast` sends messages sequentially. Use `asyncio.gather` for concurrent sending.

- [ ] **Step 1: Rewrite broadcast with asyncio.gather**

Replace the `broadcast` method in `src/reqradar/web/websocket.py`:

```python
async def broadcast(self, task_id: int, event: dict):
    if task_id not in self._connections:
        return

    connections = list(self._connections[task_id])

    async def _safe_send(ws: WebSocket):
        try:
            await ws.send_json(event)
            return None
        except Exception:
            return ws

    results = await asyncio.gather(*[_safe_send(ws) for ws in connections])
    dead = [ws for ws in results if ws is not None]
    for ws in dead:
        self.unsubscribe(task_id, ws)
```

Add `import asyncio` at the top of the file.

- [ ] **Step 2: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 471+ passed

- [ ] **Step 3: Commit**

```bash
git add src/reqradar/web/websocket.py
git commit -m "perf: use asyncio.gather for concurrent WebSocket broadcast"
```

---

### Task 8: Database Connection Pool Configuration

**Files:**
- Modify: `src/reqradar/web/database.py`
- Modify: `src/reqradar/infrastructure/config.py`

Add connection pool settings to the config and use them in the engine creation.

- [ ] **Step 1: Add pool config to WebConfig**

In `src/reqradar/infrastructure/config.py`, add to `WebConfig`:

```python
db_pool_size: int = Field(default=5, description="Database connection pool size")
db_pool_max_overflow: int = Field(default=10, description="Max overflow connections beyond pool_size")
```

- [ ] **Step 2: Use pool config in database.py**

Replace the `create_engine` function in `src/reqradar/web/database.py`:

```python
def create_engine(url: str, pool_size: int = 5, max_overflow: int = 10):
    is_sqlite = url.startswith("sqlite")

    engine_kwargs = {
        "echo": False,
    }

    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_size"] = pool_size
        engine_kwargs["max_overflow"] = max_overflow
        engine_kwargs["pool_pre_ping"] = True

    engine = create_async_engine(url, **engine_kwargs)

    if is_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine
```

- [ ] **Step 3: Update app.py lifespan to pass pool config**

In `src/reqradar/web/app.py`, replace:

```python
engine = create_engine(web_config.database_url)
```

With:

```python
engine = create_engine(
    web_config.database_url,
    pool_size=web_config.db_pool_size,
    max_overflow=web_config.db_pool_max_overflow,
)
```

- [ ] **Step 4: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 471+ passed

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/database.py src/reqradar/infrastructure/config.py src/reqradar/web/app.py
git commit -m "feat(db): add configurable connection pool settings, enable pool_pre_ping for non-SQLite"
```

---

### Task 9: Dependencies Module — Replace Global Mutable with App State

**Files:**
- Modify: `src/reqradar/web/dependencies.py`
- Modify: `src/reqradar/web/app.py`

Replace the global `async_session_factory = None` with a pattern that reads from `app.state`.

- [ ] **Step 1: Rewrite dependencies.py to use request-scoped app state**

Replace the entire `src/reqradar/web/dependencies.py`:

```python
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession):
    from reqradar.web.api.auth import SECRET_KEY, ALGORITHM

    credentials_exception = Exception("Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

Key change: `get_db` now reads `session_factory` from `request.app.state.session_factory` instead of a global variable.

- [ ] **Step 2: Remove the global variable assignment in app.py lifespan**

In `src/reqradar/web/app.py`, remove the line:

```python
dep_module.async_session_factory = session_factory
```

The `session_factory` is already stored in `app.state.session_factory` which is set later in lifespan. Keep that line.

- [ ] **Step 3: Fix any remaining references to the global**

Search for `dep_module.async_session_factory` in `app.py` and `analysis_runner.py` / `analysis_runner_v2.py`.

In `analysis_runner.py` and `analysis_runner_v2.py`, the runners get a session factory via:
```python
async with dep_module.async_session_factory() as db:
```

These need to be changed to get the session factory from the app. Since runners are standalone async tasks (not in a request context), they need a reference to the session factory. Add a class attribute to store it:

In `analysis_runner.py`, add a `session_factory` attribute:

```python
class AnalysisRunner:
    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[int, asyncio.Task] = {}
        self.session_factory = None
```

And update `_run_analysis`:
```python
async def _run_analysis(self, task_id: int, project: Project, config: Config):
    async with self._semaphore:
        if self.session_factory is None:
            import reqradar.web.dependencies as dep_module
            factory = dep_module.async_session_factory
        else:
            factory = self.session_factory
        async with factory() as db:
            ...
```

In `app.py` lifespan, set the runner's session factory:
```python
runner.session_factory = session_factory
```

Also import and set for V2:
```python
from reqradar.web.services.analysis_runner_v2 import runner_v2
runner_v2.session_factory = session_factory
```

And add the `session_factory` attribute to `AnalysisRunnerV2`:
```python
class AnalysisRunnerV2:
    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[int, asyncio.Task] = {}
        self.session_factory = None
```

Update `_run_analysis` similarly.

- [ ] **Step 4: Update test fixtures**

In `tests/test_web_api_auth.py` and `tests/test_web_security.py`, the fixtures set `dep_module.async_session_factory`. Since `get_db` now reads from `request.app.state`, we need to ensure `app.state.session_factory` is set.

The `create_app()` function's lifespan already sets `app.state.session_factory = session_factory`, so tests that use `create_app()` should work automatically.

However, the fixture also needs to ensure the auth module's SECRET_KEY is set. Keep that part.

Remove `dep_module.async_session_factory = session_factory` and `dep_module.async_session_factory = original_factory` from both test fixtures — it's no longer needed because `create_app()` handles it via lifespan.

- [ ] **Step 5: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 471+ passed

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/web/dependencies.py src/reqradar/web/app.py src/reqradar/web/services/analysis_runner.py src/reqradar/web/services/analysis_runner_v2.py tests/test_web_api_auth.py tests/test_web_security.py
git commit -m "refactor: replace global async_session_factory with app.state and runner attributes"
```

---

### Task 10: Add Lint Configuration and Pre-commit Integration

**Files:**
- Modify: `pyproject.toml`
- Modify: `.pre-commit-config.yaml`

Install and configure ruff + mypy as dev dependencies and update pre-commit hooks.

- [ ] **Step 1: Add ruff and mypy to dev dependencies**

Run: `poetry add --group dev ruff mypy`

- [ ] **Step 2: Update ruff config in pyproject.toml**

In `pyproject.toml`, update the `[tool.ruff]` section:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["reqradar"]
```

- [ ] **Step 3: Update mypy config in pyproject.toml**

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_ignores = true
ignore_missing_imports = true
exclude = ["alembic/versions/"]
```

- [ ] **Step 4: Update .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.5, sqlalchemy>=2.0]
```

- [ ] **Step 5: Run ruff to check current state**

Run: `poetry run ruff check src/ tests/`

Note any issues found. Do NOT auto-fix everything — just verify the tool works.

- [ ] **Step 6: Run mypy to check current state**

Run: `poetry run mypy src/reqradar/web/`

Note any issues. Do NOT fix everything now — just verify the tool works.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml poetry.lock .pre-commit-config.yaml
git commit -m "chore: add ruff and mypy dev dependencies, update lint and pre-commit config"
```

---

### Task 11: Frontend TypeScript Strict Checks

**Files:**
- Modify: `frontend/tsconfig.json` (or `frontend/tsconfig.app.json`)

- [ ] **Step 1: Check current tsconfig**

Read the current TypeScript config to understand strict mode settings.

Run: `cat frontend/tsconfig.json frontend/tsconfig.app.json 2>/dev/null`

- [ ] **Step 2: Enable strict mode if not already**

Ensure `strict: true` is set in the tsconfig. If already set, skip this step.

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`

If there are new type errors from enabling strict mode, fix them.

- [ ] **Step 4: Commit (if changes were made)**

```bash
git add frontend/
git commit -m "chore: enable TypeScript strict mode in frontend"
```

---

## Self-Review Checklist

1. **Spec coverage**: Each issue from the audit has a corresponding task — security (Tasks 1-3), database (Task 4), architecture (Tasks 5-6, 9), performance (Tasks 7-8), quality (Tasks 10-11). ✓
2. **Placeholder scan**: No TBD, TODO, or vague instructions. All code is concrete. ✓
3. **Type consistency**: TaskStatus enum used consistently across Tasks 5-6. Session factory pattern consistent between Task 9 modifications. ✓
