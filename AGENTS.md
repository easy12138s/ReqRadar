# AGENTS.md — ReqRadar Coding Guide

## Quick Reference (AI Agent Cheat Sheet)

### 最常用命令

```bash
poetry install                              # 安装 Python 依赖
ruff check . && ruff format --check . && mypy .   # 三件套检查
pytest -q                                   # 跑测试（覆盖率默认开启）
cd frontend && npm ci && npm run build      # 前端安装 + 构建
```

### 核心约束（编写任何代码前必须遵守）

1. **Python 3.12+ 语法**：`str | None`（不用 `Optional`），绝对导入，禁止相对导入
2. **中文注释 + 英文标识符**：Docstring/注释用中文，变量/函数/类名用英文
3. **API 端点访问全局状态**：用 `request.app.state.config`（禁止模块级 `from config import load_config`）
4. **测试必须隔离**：`tmp_path` 写文件 + mock 所有外部服务（LLM/网络/Git）+ 独立 SQLite
5. **异常体系**：使用 `core/exceptions.py` 层次结构，链式 `cause` 追踪
6. **前端 API 调用**：统一走 `frontend/src/api/client.ts` 的 `apiClient`，禁止页面组件直接 `axios`
7. **提交信息**：英文，格式 `<type>: <short description>`（feat/fix/refactor/docs/chore/style/test/ci/perf）

---

## Project Overview

ReqRadar is a requirements-analysis agent platform (需求透视). Python 3.12+ backend (FastAPI + SQLAlchemy async / LiteLLM), React 19 / TypeScript / Vite 8 / Ant Design 6 frontend. Package manager: Poetry (backend) + npm (frontend). Version: 0.8.0.

### Prerequisites

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 后端运行时（项目锁定 py312） |
| Node.js | 20+ | 前端构建与开发 |
| Poetry | 最新版 | Python 依赖管理 |
| npm | 最新版 | 前端依赖管理 |

### 初始化开发环境

```bash
git clone <repo> && cd ReqRadar
poetry install                          # Python 依赖
cd frontend && npm ci && cd ..          # 前端依赖
```

## Build / Lint / Test Commands

### Install dependencies

```bash
poetry install              # Python
cd frontend && npm ci       # Frontend
```

### Run tests

> 详细命令与说明见 [Testing Conventions](#testing-conventions) 章节。快速开始: `pytest -q`

Tests use pytest-asyncio with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorator needed.

### Lint and format

```bash
ruff check .          # lint
ruff format .         # format (also: black --line-length=100 .)
mypy .                # type check (py312, ignore_missing_imports=true)
cd frontend && npm run lint   # ESLint + TypeScript check
```

Pre-commit hooks (trailing-whitespace, end-of-file-fixer, black, ruff, mypy) are configured in `.pre-commit-config.yaml`.

CI pipeline: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — runs on push/PR to main/master.

### Build

```bash
scripts/build-package.sh   # builds frontend then Python package
poetry build               # Python package only
cd frontend && npm run build   # frontend only (output → src/reqradar/web/static)
```

## Architecture

```
ReqRadar/
├── frontend/                   # React/TypeScript 前端
│   └── src/
│       ├── api/                # API 客户端模块（每后端路由一文件）
│       ├── components/         # 通用 UI 组件
│       ├── context/            # React Context (Auth, Theme)
│       ├── hooks/              # 自定义 Hooks
│       ├── pages/              # 页面组件（路由级，懒加载）
│       ├── types/              # TypeScript 类型定义
│       ├── constants/          # 常量定义
│       ├── App.tsx             # 路由 + Provider 嵌套
│       └── main.tsx            # 入口
│
├── src/reqradar/
│   ├── agent/           # Core analysis agent, tools, prompts
│   ├── cli/             # Click CLI commands
│   ├── core/            # Domain models (Pydantic) + exception hierarchy
│   ├── infrastructure/  # Config (Pydantic+YAML), logging (structlog), paths, templates
│   ├── modules/         # Feature modules: llm_client, code_parser, git_analyzer, memory, loaders
│   ├── templates/       # Report templates (YAML + Jinja2)
│   └── web/             # FastAPI app, API routers, services, SQLAlchemy models, static frontend
│
├── tests/               # 测试套件
├── alembic/             # 数据库迁移
└── .github/workflows/   # CI 配置
```

- **Config**: `infrastructure/config.py` — Pydantic v2 models loaded from `~/.reqradar/config.yaml`
- **Paths**: `infrastructure/paths.py` — `get_paths()`, `ensure_dirs()`, `resolve_home()`
- **App lifespan**: `web/app.py` — sets `app.state.config`, `app.state.paths`, `app.state.report_storage`
- **DB**: SQLAlchemy 2.0 async (aiosqlite for dev), Alembic migrations
- **Auth**: JWT (python-jose) + bcrypt, `SECRET_KEY` module-level in `web/api/auth.py`
- **Frontend build output**: `src/reqradar/web/static` (served by FastAPI StaticFiles)

## Code Style

### Language Policy

| 内容 | 语言 | 示例 |
|------|------|------|
| 代码注释 / Docstring | 中文 | `# 用户密码哈希` |
| 代码标识符 | 英文 | `hash_password`, `UserModel`, `AnalysisAgent` |
| Git 提交信息 | 英文 | `feat: add analysis retry mechanism` |
| PR 标题 / 描述 | 英文 | — |
| 测试函数名 | 英文 | `test_login_success`, `test_create_project_duplicate_name` |
| AGENTS.md / 文档 | 中文 | 本文件 |

### Formatting

- Line length: **100** (Black + Ruff)
- Ruff lint rules: `E, F, W, I, N, UP, B, SIM, RUF` (E501 ignored — Black handles line length)
- No emojis in code unless user explicitly requests

### Imports

- **Absolute imports only** — never use relative imports
- Import order (enforced by Ruff isort): stdlib → third-party → first-party (`reqradar.*`)
- `known-first-party = ["reqradar"]`
- Example:
  ```python
  import os
  from pathlib import Path
  from fastapi import APIRouter, Depends
  from pydantic import BaseModel, Field
  from reqradar.core.exceptions import LLMException
  from reqradar.web.dependencies import DbSession, CurrentUser
  ```

### Type Hints

- Use **Python 3.12+ union syntax**: `str | None` (not `Optional[str]`), `int | None`, `list[dict]`
- `Optional[T]` 仅在以下场景可接受：
  - 与外部库交互时的类型适配层（需要做 typing bridge）
  - **所有新代码必须使用 `T | None` 语法**
- SQLAlchemy columns: use `Mapped[type]` annotations
- FastAPI dependencies: `Annotated` types (`DbSession`, `CurrentUser`)

### Naming Conventions

| Element           | Style                 | Example                                               |
| ----------------- | --------------------- | ----------------------------------------------------- |
| Modules/files     | `snake_case`          | `llm_client.py`, `analysis_agent.py`                  |
| Classes           | `PascalCase`          | `AnalysisAgent`, `LiteLLMClient`, `ReqRadarException` |
| Functions/methods | `snake_case`          | `create_llm_client`, `load_config`, `hash_password`   |
| Private attrs     | `_leading_underscore` | `_cancelled`, `_current_task_id`                      |
| Constants         | `UPPER_SNAKE_CASE`    | `DEPTH_MAX_STEPS`, `EMBEDDING_MODELS`                 |
| Pydantic models   | `PascalCase`          | `HomeConfig`, `LLMConfig`                             |
| SQLAlchemy models | `PascalCase`          | `AnalysisTask`, `ReportVersion`                       |

### Error Handling

- Use the **custom exception hierarchy** in `core/exceptions.py`:
  `ReqRadarException(message, cause=...)` — base class; subclasses: `FatalError`, `ConfigException`, `LLMException`, `VectorStoreException`, `GitException`, `IndexException`, `ReportException`, `LoaderException`, `ParseException`, `VisionNotConfiguredError`
- Chain with `cause` param: `LLMException(f"LiteLLM failed: {e}", cause=e)`
- FastAPI exception handler in `web/exceptions.py` maps domain exceptions → HTTP status codes
- Logger pattern: `logger = logging.getLogger("reqradar.<module>")`

### API Endpoint Conventions

- Access config via `request.app.state.config` (NOT `load_config()` direct calls)
- Access paths via `request.app.state.paths`
- Access report storage via `request.app.state.report_storage`
- Background tasks: `asyncio.create_task(...)` for fire-and-forget analysis runs

### Pydantic Models

- Use Pydantic v2 (`BaseModel`, `Field`, `field_validator`, `model_validator`)
- Docstrings/comments are in **Chinese (Mandarin)**; code identifiers in English

## Frontend Conventions

### Tech Stack

React 19 + TypeScript + Vite 8 + Ant Design 6 + React Query 5 + React Router 7 + Axios

### Directory Structure

```
frontend/src/
├── api/            # API 客户端模块（每个后端路由一个文件）
│   ├── client.ts   # axios 实例，统一拦截器（token 注入 / 错误处理）
│   ├── auth.ts
│   ├── projects.ts
│   ├── analyses.ts
│   └── ...
├── components/     # 通用 UI 组件（AppShell, ChatPanel, FileUploader 等）
├── context/        # React Context（AuthContext 认证, ThemeContext 主题）
├── hooks/          # 自定义 Hooks（useWebSocket 等）
├── pages/          # 页面组件（路由级，全部 lazy() 懒加载）
├── types/          # TypeScript 类型定义（API 响应、WebSocket 消息等）
├── constants/      # 常量定义（focusAreas 等）
├── App.tsx         # 路由定义 + Provider 嵌套（QueryClient → Theme → Auth → Router）
└── main.tsx        # 入口
```

### Code Style

- 组件文件: `PascalCase.tsx`（`Login.tsx`, `ChatPanel.tsx`）
- 工具函数 / Hook: `camelCase.ts`（`useWebSocket.ts`）
- API 模块: `camelCase.ts`（`auth.ts`, `analyses.ts`）
- 路径别名: 使用 `@` 映射到 `src/`（vite.config.ts 配置），如 `import { foo } from '@/components/foo'`
- 页面组件全部通过 `React.lazy()` + `Suspense` 懒加载（见 App.tsx）

### State Management

| 类型 | 方案 | 说明 |
|------|------|------|
| 服务端状态 | @tanstack/react-query | 全局 queryClient，staleTime=5min，refetchOnWindowFocus=false |
| 客户端全局状态 | React Context | AuthContext（认证）, ThemeContext（主题） |
| 组件本地状态 | useState/useReducer | 仅限纯 UI 状态 |

**禁止在页面组件中用 useState 管理应来自服务端的状态**（应通过 react-query 管理）。

### API Call Pattern

- 统一使用 `frontend/src/api/client.ts` 的 `apiClient`（基于 axios 的实例）
- 请求拦截器: 自动从 localStorage 读取 `access_token` 并注入 `Bearer` 头
- 响应拦截器: 自动处理 401（跳转登录）/ 403（权限提示）/ 422（参数错误）/ 5xx（服务器错误）/ 网络异常
- 各业务模块的 API 函数按路由拆分到 `api/` 目录下对应文件
- WebSocket 连接管理: `hooks/useWebSocket.ts`

### Component Conventions

| 类别 | 选型 | 说明 |
|------|------|------|
| UI 库 | Ant Design 6 | AppShell 布局, message 全局提示, Form/Table/Modal 等 |
| 动画 | framer-motion | 页面过渡动画 |
| 图表 | recharts | 数据可视化 |
| Markdown 渲染 | react-markdown | 报告内容展示 |
| PDF 导出 | html2pdf.js | 报告导出 |
| 路由 | react-router-dom 7 | BrowserRouter, basename=/app |
| 错误边界 | components/ErrorBoundary | 按 location.key 重置 |
| 骨架屏 | SkeletonCard/SkeletonTable/SkeletonStat/PageLoader | 加载态占位 |

### Build & Dev

```bash
cd frontend
npm run dev          # 开发服务器（代理 /api → localhost:8000, /ws → ws://localhost:8000）
npm run build        # 生产构建 → ../src/reqradar/web/static
npm run lint         # ESLint + TypeScript 类型检查
npm run test         # Vitest 单元测试
```

## Testing Conventions

### Test Suite Structure

```
tests/
├── conftest.py           # Shared fixtures (DB, app, auth, temp dirs)
├── factories.py          # Test data factories
├── helpers/              # Test helper modules
│   ├── auth_helper.py
│   ├── db_helper.py
│   └── file_helper.py
├── unit/                 # Unit tests (config, models, auth utils, dependencies)
├── integration/
│   ├── api/              # API integration tests (per router module)
│   ├── services/         # Service layer tests (report_storage, analysis_runner, etc.)
│   └── cli/              # CLI integration tests (per command group)
└── e2e/                  # End-to-end workflows
```

### Run tests

```bash
pytest                                        # all tests (coverage ON by default)
pytest tests/unit/                            # unit tests only
pytest tests/integration/api/                 # API integration tests only
pytest tests/integration/api/test_auth_endpoints.py   # single file
pytest tests/integration/api/test_auth_endpoints.py::test_register    # single function
pytest tests/integration/api/test_auth_endpoints.py::TestAuth::test_register  # single class method
pytest -k "test_register"                     # keyword filter
```

Tests use pytest-asyncio with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorator needed.

### Testing Principles

- **按真实代码写测试** — 不为不存在的接口写测试
- **每完成一个文件或一组相关测试就运行对应测试**
- **测试失败先判断来源**: 测试代码错误 / 环境问题 / 项目 bug
- **测试数据须可重复、可清理、可隔离** — 不使用真实 home 目录或开发数据库

### Fixtures (conftest.py)

- `setup_db` — creates in-memory SQLite, patches `dep_module.async_session_factory` and `config_module.load_config`
- `db_session` — yields an async SQLAlchemy session
- `client` — httpx `AsyncClient` with `ASGITransport(app=app)`
- `test_user` — registers + logs in a user, yields `(client, headers, token, user_data)`
- `test_project` — creates a project, yields `(client, headers, token, user_data, project_id)`

### Test Data Isolation

1. **数据库**: 每个测试函数使用独立 SQLite 或独立事务，测试结束后释放。不保留业务表数据，不依赖执行顺序，不依赖固定自增 ID。
2. **文件**: 所有写入必须使用 `tmp_path` 或测试专用临时目录。不写入真实工作区、home 目录或 `.reqradar` 目录。
3. **外部服务**: LLM 调用必须 mock。网络请求必须 mock。Git 仓库使用临时初始化仓库或 mock。上传文件使用临时样例数据。

### httpx.ASGITransport Lifespan Caveat

httpx 0.28+ `ASGITransport(app=app)` does **NOT** trigger FastAPI lifespan. Tests that depend on `app.state.*` must set them manually:

```python
app = create_app()
app.state.config = config
app.state.paths = paths
app.state.report_storage = report_storage
```

### Module-Level Binding Trap

When code uses `from module import func`, monkeypatching `module.func` at runtime won't affect the already-bound reference. This is why API endpoints were refactored to use `request.app.state.config` instead of importing `load_config` directly.

### Test Coverage Boundaries Per Module

Each module's tests must cover: **成功路径** / **未认证访问(401)** / **权限不足(403)** / **不存在资源(404)** / **无效参数(400/422, 含缺失字段、错误类型、边界值)** / **重复数据(唯一约束冲突)** / **空列表/空内容** / **外部服务失败(mock)** / **路径遍历攻击(文件读取类端点)**

## Key Files

| File                       | Purpose                                                         |
| -------------------------- | --------------------------------------------------------------- |
| `infrastructure/config.py` | Pydantic config models + `load_config()`                        |
| `infrastructure/paths.py`  | `get_paths()`, `ensure_dirs()`, `resolve_home()`                |
| `web/app.py`               | `create_app()`, lifespan, route registration                    |
| `web/database.py`          | SQLAlchemy async engine, `Base`, session factories              |
| `web/dependencies.py`      | `DbSession`, `CurrentUser`, `get_db`, `get_current_user`        |
| `web/models.py`            | SQLAlchemy ORM models                                           |
| `web/api/`                 | API routers (auth, projects, analyses, reports, chatback, etc.) |
| `web/services/`            | Business logic (analysis\_runner, chatback\_service, etc.)      |
| `modules/llm_client.py`    | LiteLLM unified client (`create_llm_client()` factory)          |
| `core/exceptions.py`       | Exception hierarchy                                             |
| `tests/conftest.py`        | Shared test fixtures                                            |
| `frontend/src/api/client.ts` | Axios 实例，统一 token 注入与错误拦截                         |
| `frontend/src/App.tsx`      | 前端路由定义 + Provider 嵌套                                    |

## Real API Endpoints (for test reference)

Auth: `POST /register`, `POST /login`, `GET /me`, `POST /logout`, `PUT /me/password` — prefix `/api/auth`
Users: `GET /`, `PUT /{user_id}`, `DELETE /{user_id}` — prefix `/api/users`
Projects: `GET /`, `GET /dashboard-summaries`, `POST /from-local`, `POST /from-zip`, `POST /from-git`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`, `GET /{id}/files`, `POST /{id}/index` — prefix `/api/projects`
Analyses: `POST /`, `POST /upload`, `GET /`, `GET /{task_id}`, `POST /{task_id}/retry`, `POST /{task_id}/cancel`, `WS /{task_id}/ws` — prefix `/api/analyses`
Reports: `GET /{task_id}`, `GET /{task_id}/markdown`, `GET /{task_id}/html` — prefix `/api/reports`
Versions: `GET /{task_id}/reports/versions`, `GET /{task_id}/reports/versions/{ver}`, `POST /{task_id}/reports/rollback` — prefix `/api/analyses`
Requirements: `POST /preprocess`, `GET /{doc_id}`, `PUT /{doc_id}`, `DELETE /{doc_id}`, `GET /` — prefix `/api/requirements`
Chatback: `POST /{task_id}/chat`, `POST /{task_id}/chat/stream`, `GET /{task_id}/chat`, `POST /{task_id}/chat/save` — prefix `/api/analyses`
Profile: `GET /{pid}/profile`, `PUT /{pid}/profile`, `GET /{pid}/profile/pending` (alias `/pending-changes`), `POST /{pid}/profile/pending/{cid}` (alias `/pending-changes/{cid}/accept`), `POST /{pid}/pending-changes/{cid}/reject` — prefix `/api/projects`
Memory: `GET /{pid}/terminology`, `GET /{pid}/modules`, `GET /{pid}/team`, `GET /{pid}/history` — prefix `/api/projects`
Configs: `GET /system`, `GET|PUT|DELETE /system/{key}`, `GET /{pid}/configs`, `GET|PUT|DELETE /{pid}/configs/{key}`, `GET /me/configs`, `GET|PUT|DELETE /me/configs/{key}`, `GET /resolve`, `POST /me/test-llm` — prefix `/api/configs` (project/user scoped under `/api`)
Templates: `GET /`, `POST /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`, `POST /{id}/set-default` — prefix `/api/templates`
Synonyms: `GET /?project_id=`, `POST /`, `PUT /{sid}`, `DELETE /{sid}?project_id=` — prefix `/api/synonyms`
Evidence: `GET /{task_id}/evidence`, `GET /{task_id}/evidence/{eid}` — prefix `/api/analyses`
Other: `GET /health`, `GET /api/metrics`

## Real CLI Commands (for test reference)

```
reqradar
├── --version
├── index
├── serve                (from web/cli.py)
├── createsuperuser      (from web/cli.py)
├── project
│   ├── create
│   ├── list
│   ├── show
│   ├── delete
│   └── index
├── analyze
│   ├── submit
│   ├── list
│   ├── status
│   ├── cancel
│   └── file
├── report
│   ├── get
│   ├── versions
│   └── evidence
├── config
│   ├── init
│   ├── list
│   ├── get
│   ├── set
│   └── delete
└── requirement
    └── preprocess
```

## Git Workflow

- **分支模型**: `main`（稳定分支，受 CI 保护）← `feature/*` / `fix/*`（功能分支）
- **提交格式**: `<type>(<scope>): <short description>`
  - type: `feat` / `fix` / `refactor` / `docs` / `chore` / `style` / `test` / `ci` / `perf`
  - scope: 可选，影响模块名（如 `feat(auth): add OAuth2 support`）
- **版本号**: 语义化 MAJOR.MINOR.PATCH，手动同步更新 `pyproject.toml` version 与本文件 Version 字段
- **Alembic 迁移**: 功能分支合并到 main 前生成，migration message 用英文
- **PR 标题**: 英文，格式同 commit message

## Storage Path

All data stored under `~/.reqradar/` (configurable via `home.path` in config):

- `~/.reqradar/config.yaml` — user configuration
- `~/.reqradar/reports/` — generated reports
- `~/.reqradar/memory/` — project memory data
- `~/.reqradar/indexes/` — ChromaDB vector indexes
