# ReqRadar Web 后端开发计划

**Goal:** 为 ReqRadar 添加 Web 后端模块，基于 FastAPI + SQLite，使需求分析流程可通过浏览器访问，支持实时进度推送和在线报告查看。

**Architecture:** 四层架构——API Layer（FastAPI routers）→ Service Layer（业务编排、任务调度）→ Core Layer（现有，不修改）→ Data Layer（SQLAlchemy + SQLite）。Core 层仅做 Pydantic 迁移和 Scheduler 回调两处增强，Web 层通过调用 Core 层公开 API 实现功能。

**Tech Stack:** Pydantic V2, FastAPI, Uvicorn, SQLAlchemy + aiosqlite, SQLite (WAL mode), JWT (python-jose), passlib[bcrypt], Alembic

---

## 一、后端分层架构

```
┌─────────────────────────────────────────────┐
│  API Layer (FastAPI routers)                 │  请求/响应、参数校验、HTTP状态码
│  api/auth.py, projects.py, analyses.py, ...  │
├─────────────────────────────────────────────┤
│  Service Layer                               │  业务编排、任务调度、资源管理
│  services/analysis_runner.py                 │
│  services/project_store.py                   │
├─────────────────────────────────────────────┤
│  Core Layer (现有，不修改)                     │  固定流程调度、LLM 调用、工具循环
│  core/scheduler.py, agent/steps.py, ...      │
├─────────────────────────────────────────────┤
│  Data Layer (SQLAlchemy + SQLite)             │  持久化、项目隔离、用户认证
│  models.py, database.py                      │
└─────────────────────────────────────────────┘
```

**关键约束**：Core Layer 不修改（除了阶段 0 的 Pydantic 迁移和 Scheduler 回调）。Web 层通过调用 Core 层的公开 API（Scheduler、steps、ReportRenderer）实现功能。

---

## 二、开发阶段和任务拆解

### 阶段 0：基础设施准备（Pydantic 迁移 + Scheduler 回调）

这两个任务是 Web 化的前置条件，但本身不属于 Web 模块——它们是对 Core 层的增强，完成后 CLI 和 Web 都受益。

#### Task 0-1：Pydantic 迁移 context.py

- 修改 `src/reqradar/core/context.py`：17 个 dataclass → BaseModel
- 修改 `src/reqradar/core/report.py`：5 处 `__dict__` → `model_dump()`
- 新增 `tests/test_context_pydantic.py`
- 验证：296 个现有测试全通过 + 新增序列化测试

关键改造点：
- `from dataclasses import dataclass, field` → `from pydantic import BaseModel, ConfigDict, Field`
- `@dataclass` → 继承 `BaseModel`
- `field(default_factory=...)` → `Field(default_factory=...)`
- `AnalysisContext` 需 `model_config = ConfigDict(arbitrary_types_allowed=True)` 用于 `Path` 类型
- `DeepAnalysis.decision_summary` 前向引用：`DecisionSummary` 定义在 `DeepAnalysis` 之前即可解析
- 所有 `@property`、`store_result()`、`get_result()`、`finalize()`、`mark_failed()` 方法保留不变

report.py 修复：
| 行 | Before | After |
|----|--------|-------|
| 124 | `[t.__dict__ for t in understanding.terms]` | `[t.model_dump() for t in understanding.terms]` |
| 127 | `[c.__dict__ for c in understanding.structured_constraints]` | `[c.model_dump() for c in understanding.structured_constraints]` |
| 130 | `[ca.__dict__ for ca in analysis.change_assessment]` | `[ca.model_dump() for ca in analysis.change_assessment]` |
| 135 | `[r.__dict__ for r in analysis.risks]` | `[r.model_dump() for r in analysis.risks]` |
| 139 | `analysis.implementation_hints.__dict__` | `analysis.implementation_hints.model_dump()` |

#### Task 0-2：Scheduler 回调改造

- 修改 `src/reqradar/core/scheduler.py`：`run()` 增加 `on_step_start`/`on_step_complete` 可选参数
- 新增 `tests/test_scheduler_callback.py`
- 验证：CLI 零回归（不传回调时 rich.progress 正常工作）

```python
async def run(
    self,
    context: AnalysisContext,
    on_step_start: Callable[[str, str], Awaitable] = None,
    on_step_complete: Callable[[str, StepResult], Awaitable] = None,
) -> AnalysisContext:
```

回调时机：
- 步骤开始后、handler 执行前：`if on_step_start: await on_step_start(step_name, step_desc)`
- 步骤结果存储后（成功和失败都触发）：`if on_step_complete: await on_step_complete(step_name, context.get_result(step_name))`
- FatalError 分支中，break 前调用 `on_step_complete`，确保失败事件被推送
- `with Progress()` 块和 `progress.update()` 不变——CLI 模式零改动

---

### 阶段 1：后端骨架（FastAPI + 数据库 + 认证）

#### Task 1-1：依赖和配置

修改 `pyproject.toml`，添加：
```toml
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
python-multipart = "^0.0.18"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
sqlalchemy = {extras = ["asyncio"], version = "^2.0.0"}
aiosqlite = "^0.20.0"
alembic = "^1.14.0"
markdown = "^3.7"
```

注意：`pydantic`、`httpx`、`structlog` 已在现有依赖中，无需新增。

修改 `src/reqradar/infrastructure/config.py`，添加 `WebConfig`：
```python
class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./reqradar.db"
    secret_key: str = "${REQRADAR_SECRET_KEY}"
    access_token_expire_minutes: int = 1440
    max_concurrent_analyses: int = 2
    debug: bool = False
    static_dir: Optional[str] = None
```

在 `Config` 类中添加：`web: WebConfig = Field(default_factory=WebConfig)`

更新 `.reqradar.yaml.example`，添加 web 配置段。

#### Task 1-2：数据库层

创建 `src/reqradar/web/database.py`：
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase): pass

def create_engine(url: str):
    return create_async_engine(url, echo=False, connect_args={"check_same_thread": False})

def create_session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

注意：`connect_args={"check_same_thread": False}` 是 SQLite 必需的，允许跨线程使用连接。

#### Task 1-3：ORM 模型

创建 `src/reqradar/web/models.py`：

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(20), default="editor")  # admin/editor/viewer
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    repo_path: Mapped[str] = mapped_column(String(500), default="")
    docs_path: Mapped[str] = mapped_column(String(500), default="")
    index_path: Mapped[str] = mapped_column(String(500), default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")  # 项目级配置覆盖
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    requirement_name: Mapped[str] = mapped_column(String(200), default="")
    requirement_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/completed/failed
    context_json: Mapped[str] = mapped_column(Text, default="")  # AnalysisContext.model_dump_json()
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), unique=True)
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    content_html: Mapped[str] = mapped_column(Text, default="")  # 预渲染 HTML
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"))
    filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

关键设计决策：
- `analysis_tasks.context_json` 存 `AnalysisContext.model_dump_json()`，支持完整状态恢复和历史回溯
- `reports.content_html` 预渲染 HTML，避免每次请求实时渲染 Markdown
- `projects.config_json` 存项目级配置覆盖（如不同项目用不同 LLM 模型），加载时 merge 到全局 Config
- `uploaded_files` 单独建表，一个分析任务可能对应多个上传文件

#### Task 1-4：依赖注入和异常映射

创建 `src/reqradar/web/dependencies.py`：
```python
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_db():
    async with async_session_factory() as session:
        yield session

DbSession = Annotated[AsyncSession, Depends(get_db)]

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    # JWT 解码 + 数据库查询
    ...

CurrentUser = Annotated[User, Depends(get_current_user)]
```

创建 `src/reqradar/web/exceptions.py`——将 ReqRadar 异常映射为 HTTP 响应：

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from reqradar.core.exceptions import *

EXCEPTION_STATUS_MAP = {
    ConfigException: 500,
    ParseException: 422,
    LLMException: 502,        # LLM 是上游服务
    VectorStoreException: 503,
    GitException: 500,
    IndexException: 404,
    ReportException: 500,
    LoaderException: 415,     # 不支持的文件格式
    VisionNotConfiguredError: 501,
    FatalError: 500,
}

async def reqradar_exception_handler(request: Request, exc: ReqRadarException):
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message, "type": type(exc).__name__},
    )
```

在 `app.py` 中注册：
```python
for exc_class in EXCEPTION_STATUS_MAP:
    app.add_exception_handler(exc_class, reqradar_exception_handler)
```

#### Task 1-5：认证 API

创建 `src/reqradar/web/api/auth.py`：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/auth/register` | POST | 邮箱+密码注册 |
| `/api/auth/login` | POST | 返回 JWT access_token |
| `/api/auth/me` | GET | 获取当前用户信息 |

JWT 实现细节：
- `python-jose` 签发，HS256 算法
- Token payload: `{"sub": str(user_id), "exp": expire_timestamp}`
- `SECRET_KEY` 从 `WebConfig.secret_key` 读取（支持环境变量插值，复用 `config.py` 的 `resolve_env_var`）
- 密码哈希用 `passlib[bcrypt]`

Pydantic request/response models：
```python
class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    class Config:
        from_attributes = True
```

#### Task 1-6：应用工厂和 `reqradar serve` 命令

创建 `src/reqradar/web/app.py`：
```python
def create_app() -> FastAPI:
    # 1. 加载配置
    config = load_config()
    web_config = config.web

    # 2. 创建 engine + session_factory
    engine = create_engine(web_config.database_url)
    session_factory = create_session_factory(engine)
    # 注入到 dependencies 模块（模块级变量）
    deps.async_session_factory = session_factory

    # 3. 同步 auth 模块的 SECRET_KEY
    auth_module.SECRET_KEY = web_config.secret_key
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = web_config.access_token_expire_minutes

    # 4. lifespan: create_all + 异常 handler 注册 + 任务恢复
    @asynccontextmanager
    async def lifespan(app):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # 注册 ReqRadar 异常 → HTTP 映射
        for exc_class in EXCEPTION_STATUS_MAP:
            app.add_exception_handler(exc_class, reqradar_exception_handler)
        yield

    app = FastAPI(title="ReqRadar", version="0.3.0", lifespan=lifespan)

    # 5. CORS
    app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

    # 6. Routers
    app.include_router(auth_router)
    # 后续 Task 添加更多 router

    # 7. /health
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__}

    # 8. 静态文件（如果有前端产物）
    if web_config.static_dir:
        app.mount("/", StaticFiles(directory=web_config.static_dir, html=True))

    return app
```

创建 `src/reqradar/web/cli.py`：
```python
@click.command()
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
@click.option("--reload", is_flag=True)
@click.pass_context
def serve(ctx, host, port, reload):
    config = ctx.obj["config"]
    web_config = config.web
    uvicorn.run(
        "reqradar.web.app:create_app",
        host=host or web_config.host,
        port=port or web_config.port,
        reload=reload or web_config.debug,
        factory=True,
    )
```

注册到 `cli/main.py`：`from reqradar.web.cli import serve; cli.add_command(serve)`

#### Task 1-7：认证 API 测试

创建 `tests/test_web_api_auth.py`：

测试用例：
- 注册成功
- 注册重复邮箱 → 400
- 登录成功 → 返回 token
- 登录错误密码 → 401
- token 访问 /me
- 无 token 访问 /me → 401

使用 `httpx.AsyncClient` + `ASGITransport` + 测试用 SQLite 文件：
```python
TEST_DB_URL = "sqlite+aiosqlite:///./test_reqradar_auth.db"

@pytest.fixture
async def client():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 注入 session_factory 到 dependencies
    ...
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    os.remove("test_reqradar_auth.db")
```

---

### 阶段 2：核心业务 API（项目 + 分析 + 报告）

#### Task 2-1：WebSocket 管理器

创建 `src/reqradar/web/websocket.py`：

```python
class ConnectionManager:
    _connections: dict[int, set[WebSocket]]  # task_id → WebSocket set

    async def subscribe(task_id: int, ws: WebSocket):
        ...

    async def unsubscribe(task_id: int, ws: WebSocket):
        ...

    async def broadcast(task_id: int, event: dict):
        # JSON 序列化，处理断连
        ...
```

WebSocket 消息协议：

| 事件类型 | 方向 | Payload |
|---------|------|---------|
| `step_start` | Server→Client | `{"type": "step_start", "step": "extract", "description": "提取关键术语"}` |
| `step_complete` | Server→Client | `{"type": "step_complete", "step": "extract", "success": true, "error": null}` |
| `step_progress` | Server→Client | `{"type": "step_progress", "step": "analyze", "tool_call": "search_code", "round": 3}` |
| `analysis_complete` | Server→Client | `{"type": "analysis_complete", "task_id": 42}` |
| `analysis_failed` | Server→Client | `{"type": "analysis_failed", "error": "..."}` |

注意：`step_progress` 在 Phase 1 暂不实现（需要 tool_use_loop.py 的回调改造），Phase 1 只做 step 级别进度。

#### Task 2-2：项目资源池

创建 `src/reqradar/web/services/project_store.py`：

```python
class ProjectStore:
    _code_graphs: dict[int, CodeGraph]
    _vector_stores: dict[int, ChromaVectorStore]
    _tool_registries: dict[int, ToolRegistry]
    _lock: asyncio.Lock

    async def get_code_graph(project_id, index_path) -> CodeGraph | None
    async def get_vector_store(project_id, index_path) -> ChromaVectorStore | None
    async def get_tool_registry(project_id, project, memory_data) -> ToolRegistry
    async def invalidate(project_id)
```

为什么需要 `asyncio.Lock`：多个分析任务可能同时请求同一项目资源，首次加载时需避免重复构建。

为什么缓存 `ToolRegistry`：当前 `cli/main.py:329-346` 每次分析都重建 ToolRegistry 和 9 个工具实例。Web 化后同项目的 ToolRegistry 是稳定的，可以复用。

`get_tool_registry` 核心逻辑（复用 `cli/main.py:329-346` 的注册模式）：
```python
async def get_tool_registry(self, project_id, project, memory_data):
    if project_id in self._tool_registries:
        return self._tool_registries[project_id]

    code_graph = await self.get_code_graph(project_id, project.index_path)
    vector_store = await self.get_vector_store(project_id, project.index_path)

    registry = ToolRegistry()
    repo_path = project.repo_path
    if code_graph:
        registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path))
        registry.register(GetDependenciesTool(code_graph=code_graph, memory_data=memory_data))
    registry.register(ReadFileTool(repo_path=repo_path))
    registry.register(ReadModuleSummaryTool(memory_data=memory_data))
    registry.register(ListModulesTool(memory_data=memory_data))
    registry.register(GetProjectProfileTool(memory_data=memory_data))
    registry.register(GetTerminologyTool(memory_data=memory_data))
    if vector_store:
        registry.register(SearchRequirementsTool(vector_store=vector_store))
    # GitAnalyzer 按需创建，不缓存（repo_path 可能不存在）
    self._tool_registries[project_id] = registry
    return registry
```

#### Task 2-3：异步分析执行器

创建 `src/reqradar/web/services/analysis_runner.py`——这是后端最核心的组件。

```python
class AnalysisRunner:
    _semaphore: asyncio.Semaphore  # 控制并发分析数（默认 2）
    _active_tasks: dict[int, asyncio.Task]  # task_id → asyncio.Task

    async def submit(task_id, project, config, db):
        async with self._semaphore:
            await self._run_analysis(task_id, project, config, db)

    async def _run_analysis(task_id, project, config, db):
        """核心执行逻辑"""
        # 1. 从 project_store 获取资源
        # 2. 构建 AnalysisContext
        # 3. 构建 LLM client（使用项目级配置覆盖）
        # 4. 构建 GitAnalyzer（如果 repo 有 .git）
        # 5. 从 project_store 获取 ToolRegistry
        # 6. 构建 Scheduler + wrapped handlers（复用 cli/main.py 的包装模式）
        # 7. 传入 WebSocket 回调
        # 8. 执行 scheduler.run()
        # 9. 渲染报告（ReportRenderer）
        # 10. Markdown → HTML 预渲染
        # 11. 持久化 context_json + report
        # 12. 广播 analysis_complete / analysis_failed

    async def cancel(task_id):
        task = self._active_tasks.get(task_id)
        if task:
            task.cancel()
```

关键设计细节：

1. **并发控制**：`asyncio.Semaphore(max_concurrent_analyses)`——防止同时运行过多分析导致 LLM API 限流或资源耗尽

2. **项目级配置覆盖**：从 `projects.config_json` 读取项目特有配置，merge 到全局 Config：
   ```python
   project_overrides = json.loads(project.config_json)
   if project_overrides.get("llm"):
       # merge 到 config.llm（Pydantic model 可用 model_copy(update=...)）
   ```

3. **文件上传处理**：用户上传的需求文档通过 `LoaderRegistry` 加载，转为文本后存入 `task.requirement_text`。`DocumentLoader.load()` 是同步的，需 `await asyncio.to_thread(loader.load, file_path)`

4. **错误恢复**：分析失败时，`task.context_json` 仍保存到失败前的状态，方便调试和重试

5. **Scheduler 回调到 WebSocket 的桥接**：
   ```python
   async def on_step_start(step_name, step_desc):
       await ws_manager.broadcast(task_id, {"type": "step_start", "step": step_name, "description": step_desc})

   async def on_step_complete(step_name, step_result):
       await ws_manager.broadcast(task_id, {"type": "step_complete", "step": step_name, "success": step_result.success, "error": step_result.error})
   ```

6. **`asyncio.create_task` vs 任务队列**：Phase 1 使用 `asyncio.create_task`（进程内调度），零外部依赖。`task.status = "pending"` 保存到数据库，重启后可扫描 pending/running 任务重新提交

7. **Markdown → HTML 预渲染**：
   ```python
   import markdown as md_lib
   html_content = md_lib.markdown(report_content, extensions=["toc", "tables", "fenced_code"])
   ```

#### Task 2-4：项目 API

创建 `src/reqradar/web/api/projects.py`：

| 端点 | 方法 | 功能 | 鉴权 |
|------|------|------|------|
| `/api/projects` | GET | 列表 | JWT |
| `/api/projects` | POST | 创建项目 | JWT |
| `/api/projects/{id}` | GET | 详情 | JWT |
| `/api/projects/{id}` | PUT | 更新配置 | JWT |
| `/api/projects/{id}/index` | POST | 触发索引构建 | JWT |

索引构建 API 做 Phase 1 最小实现——启动后台任务调用 `PythonCodeParser.parse_directory()` + `ChromaVectorStore`，不做进度推送。完整索引进度推送放到 Phase 2。

索引构建完成后调用 `project_store.invalidate(project_id)` 清除缓存。

```python
class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    repo_path: str = ""
    docs_path: str = ""

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    repo_path: str | None = None
    docs_path: str | None = None
    config_json: str | None = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    repo_path: str
    docs_path: str
    index_path: str
    config_json: str
    created_at: datetime
    class Config:
        from_attributes = True
```

#### Task 2-5：分析 API

创建 `src/reqradar/web/api/analyses.py`：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/analyses` | POST | 提交分析（文本 or 上传文件） |
| `/api/analyses/upload` | POST | 上传需求文档 |
| `/api/analyses` | GET | 列表（支持 project_id/status 筛选） |
| `/api/analyses/{id}` | GET | 详情（含步骤结果摘要） |
| `/api/analyses/{id}/retry` | POST | 重新执行 |
| `/api/analyses/{id}/ws` | WebSocket | 实时进度 |

文件上传流程：
```
POST /api/analyses/upload  (multipart: file + project_id + requirement_name)
  → 保存到临时目录 (.reqradar/uploads/)
  → 用 LoaderRegistry.get_for_file() 获取 loader
  → await asyncio.to_thread(loader.load, file_path)
  → 合并 chunks 为 requirement_text
  → 创建 AnalysisTask(requirement_text=加载的文本)
  → 记录 UploadedFile
  → 启动后台分析
  → 返回 task_id
```

WebSocket 鉴权：通过 query parameter `?token=xxx`，因为 WebSocket 握手不支持 Authorization header：
```python
@router.websocket("/{task_id}/ws")
async def analysis_ws(ws: WebSocket, task_id: int, token: str = Query(...)):
    # 验证 token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        await ws.close(code=4001)
        return
    await ws.accept()
    ws_manager.subscribe(task_id, ws)
    try:
        while True:
            await ws.receive_text()  # 保持连接
    except WebSocketDisconnect:
        ws_manager.unsubscribe(task_id, ws)
```

分析详情 API 返回步骤结果摘要：
```python
@router.get("/{task_id}")
async def get_analysis(task_id: int, db: DbSession, user: CurrentUser):
    task = await db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(404)
    # 从 context_json 提取步骤摘要
    step_summary = {}
    if task.context_json:
        ctx = AnalysisContext.model_validate_json(task.context_json)
        for step_name, result in ctx.step_results.items():
            step_summary[step_name] = {"success": result.success, "error": result.error}
    return {
        "id": task.id,
        "project_id": task.project_id,
        "requirement_name": task.requirement_name,
        "status": task.status,
        "error_message": task.error_message,
        "step_summary": step_summary,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }
```

分析提交的两种入口：
```python
# 入口 1：直接粘贴文本
@router.post("")
async def submit_analysis(req: AnalysisSubmit, db: DbSession, user: CurrentUser):
    ...

# 入口 2：上传文件
@router.post("/upload")
async def upload_analysis(
    file: UploadFile,
    project_id: int = Form(...),
    requirement_name: str = Form(""),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ...
```

#### Task 2-6：报告 API

创建 `src/reqradar/web/api/reports.py`：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/reports/{task_id}` | GET | 获取报告（JSON，含 content_html + content_markdown） |
| `/api/reports/{task_id}/markdown` | GET | 下载原始 Markdown（`PlainTextResponse`） |
| `/api/reports/{task_id}/html` | GET | 获取渲染后的 HTML |

报告 JSON 响应格式：
```python
{
    "id": 1,
    "task_id": 42,
    "content_markdown": "# ...",
    "content_html": "<h1>...",
    "risk_level": "high",           # 从 context_json 提取
    "created_at": "2026-04-22T..."
}
```

#### Task 2-7：记忆只读 API

创建 `src/reqradar/web/api/memory.py`：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/projects/{id}/terminology` | GET | 术语列表 |
| `/api/projects/{id}/modules` | GET | 模块列表 |
| `/api/projects/{id}/team` | GET | 团队信息 |
| `/api/projects/{id}/history` | GET | 分析历史 |

Phase 1 只做只读。数据来源是 `MemoryManager`，直接读 YAML 文件：

```python
@router.get("/{project_id}/terminology")
async def get_terminology(project_id: int, db: DbSession, user: CurrentUser):
    project = await db.get(Project, project_id)
    memory_manager = MemoryManager(storage_path=str(Path(project.repo_path) / ".reqradar/memory"))
    memory_data = memory_manager.load()
    return memory_data.get("terminology", [])
```

#### Task 2-8：业务 API 测试

创建测试文件：

- `tests/test_web_api_projects.py` — 项目 CRUD + 索引触发
- `tests/test_web_api_analyses.py` — 分析提交、列表、详情、重试
- `tests/test_web_api_reports.py` — 报告获取、下载
- `tests/test_web_services.py` — ProjectStore 缓存、AnalysisRunner 并发控制
- `tests/test_web_websocket.py` — WebSocket 连接和消息广播

---

### 阶段 3：集成和部署

#### Task 3-1：服务启动时的任务恢复

在 `app.py` 的 `lifespan` 中扫描 `status="running"` 的任务（上次服务异常退出时未完成的），将它们标记为 `status="failed"` + `error_message="Server restarted during analysis"`。避免永远卡在 running 状态。

```python
@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 恢复异常退出的任务
    async with session_factory() as db:
        result = await db.execute(
            select(AnalysisTask).where(AnalysisTask.status == "running")
        )
        for task in result.scalars().all():
            task.status = "failed"
            task.error_message = "Server restarted during analysis"
        await db.commit()
    yield
```

#### Task 3-2：结构化日志适配

现有 `infrastructure/logging.py` 已有 `structlog` 的 JSON 输出模式（`use_rich=False` 时）。Web 模块启动时设置 `use_rich=False`，因为容器环境不需要终端着色。

在 `app.py` lifespan 中：
```python
setup_logging(level=config.log.level, use_rich=False)
```

#### Task 3-3：`/metrics` 端点

```python
@app.get("/metrics")
async def metrics(db: DbSession, user: CurrentUser):
    project_count = await db.scalar(select(func.count(Project.id)))
    task_counts = {}
    for status in ["pending", "running", "completed", "failed"]:
        count = await db.scalar(
            select(func.count(AnalysisTask.id)).where(AnalysisTask.status == status)
        )
        task_counts[status] = count
    return {"projects": project_count, "tasks": task_counts}
```

#### Task 3-4：Docker 部署（后端）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --only main
COPY src/ src/
EXPOSE 8000
CMD ["reqradar", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
services:
  reqradar-api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - reqradar_data:/app/.reqradar
      - reqradar_db:/app/reqradar.db
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REQRADAR_SECRET_KEY=${SECRET_KEY:-change-me-in-production}
volumes:
  reqradar_data:
  reqradar_db:
```

---

## 三、API 完整清单

| 方法 | 路径 | 鉴权 | 阶段 |
|------|------|------|------|
| POST | `/api/auth/register` | 无 | 1 |
| POST | `/api/auth/login` | 无 | 1 |
| GET | `/api/auth/me` | JWT | 1 |
| GET | `/api/projects` | JWT | 2 |
| POST | `/api/projects` | JWT | 2 |
| GET | `/api/projects/{id}` | JWT | 2 |
| PUT | `/api/projects/{id}` | JWT | 2 |
| POST | `/api/projects/{id}/index` | JWT | 2 |
| GET | `/api/projects/{id}/terminology` | JWT | 2 |
| GET | `/api/projects/{id}/modules` | JWT | 2 |
| GET | `/api/projects/{id}/team` | JWT | 2 |
| GET | `/api/projects/{id}/history` | JWT | 2 |
| POST | `/api/analyses` | JWT | 2 |
| POST | `/api/analyses/upload` | JWT | 2 |
| GET | `/api/analyses` | JWT | 2 |
| GET | `/api/analyses/{id}` | JWT | 2 |
| POST | `/api/analyses/{id}/retry` | JWT | 2 |
| WS | `/api/analyses/{id}/ws` | Query token | 2 |
| GET | `/api/reports/{task_id}` | JWT | 2 |
| GET | `/api/reports/{task_id}/markdown` | JWT | 2 |
| GET | `/api/reports/{task_id}/html` | JWT | 2 |
| GET | `/health` | 无 | 3 |
| GET | `/metrics` | JWT | 3 |

共 22 个端点。WebSocket 鉴权通过 query parameter `?token=xxx`。

---

## 四、数据库 Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) DEFAULT '',
    role VARCHAR(20) DEFAULT 'editor',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    repo_path VARCHAR(500) DEFAULT '',
    docs_path VARCHAR(500) DEFAULT '',
    index_path VARCHAR(500) DEFAULT '',
    config_json TEXT DEFAULT '{}',
    owner_id INTEGER REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE analysis_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    requirement_name VARCHAR(200) DEFAULT '',
    requirement_text TEXT DEFAULT '',
    status VARCHAR(20) DEFAULT 'pending',
    context_json TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tasks_project ON analysis_tasks(project_id);
CREATE INDEX idx_tasks_status ON analysis_tasks(status);

CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL UNIQUE REFERENCES analysis_tasks(id),
    content_markdown TEXT DEFAULT '',
    content_html TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE uploaded_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES analysis_tasks(id),
    filename VARCHAR(500) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

SQLite WAL 模式：在 `create_engine` 时通过事件监听器启用：
```python
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, cursor):
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
```

---

## 五、风险和待决问题

| 问题 | 影响 | 建议 |
|------|------|------|
| `DocumentLoader.load()` 是同步方法 | 上传文件时阻塞事件循环 | `await asyncio.to_thread(loader.load, path)` |
| `ToolCallTracker` 不是线程安全的 | 并发分析时状态混乱 | 每个 AnalysisRunner 实例创建独立 Tracker，不共享 |
| `LoaderRegistry._loaders` 是类变量 | 运行时注册可能有竞争 | 在应用启动时一次性注册所有 loader（`loaders/__init__.py` 的 import 触发），之后只读 |
| ChromaDB 并发写入 | 多个分析任务同时写入同一向量库 | 每个 project 独立 ChromaDB 实例；分析过程只读向量库，不写入 |
| 服务重启时 running 任务 | 永远卡在 running 状态 | lifespan 中扫描并标记为 failed |
| `asyncio.create_task` 不持久 | 服务重启任务丢失 | Phase 1 可接受；Phase 2 引入持久化任务队列 |
| SQLite 写入并发 | SQLite 只支持一个写入者 | aiosqlite 单写入者 + WAL 模式可支持并发读取 |
| WebSocket 鉴权 | 标准 Authorization header 在 WS 握手中不可用 | 通过 query parameter `?token=xxx` 传递 JWT |

---

## 六、后端工作量估算

| 阶段 | 任务 | 预估 |
|------|------|------|
| 0 | Pydantic 迁移 | 1.5 天 |
| 0 | Scheduler 回调 | 0.5 天 |
| 1 | 依赖+配置+数据库+异常+认证+serve 命令 | 3 天 |
| 2 | WebSocket+ProjectStore+AnalysisRunner+项目/分析/报告/记忆 API | 5-6 天 |
| 3 | 任务恢复+日志+health/metrics+Docker | 1.5 天 |
| **总计** | | **约 12 天** |

---

*Plan last updated: 2026-04-22*
