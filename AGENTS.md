# AGENTS.md — ReqRadar Coding Guide

## Project Overview

ReqRadar is a requirements-analysis agent platform (需求透视). Python 3.12+ backend (FastAPI + SQLAlchemy async + LiteLLM), React/TypeScript frontend. Package manager: Poetry. Version: 0.8.0.

## Build / Lint / Test Commands

### Install dependencies

```bash
poetry install
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

### Lint and format

```bash
ruff check .          # lint
ruff format .         # format (also: black --line-length=100 .)
mypy .                # type check (py312, ignore_missing_imports=true)
```

Pre-commit hooks (trailing-whitespace, end-of-file-fixer, black, ruff, mypy) are configured in `.pre-commit-config.yaml`.

### Build

```bash
scripts/build-package.sh   # builds frontend then Python package
poetry build               # Python package only
```

## Architecture

```
src/reqradar/
├── agent/           # Core analysis agent, tools, prompts
├── cli/             # Click CLI commands
├── core/            # Domain models (Pydantic) + exception hierarchy
├── infrastructure/  # Config (Pydantic+YAML), logging (structlog), paths, templates
├── modules/         # Feature modules: llm_client, code_parser, git_analyzer, memory, loaders
├── templates/       # Report templates (YAML + Jinja2)
└── web/             # FastAPI app, API routers, services, SQLAlchemy models, static frontend
```

- **Config**: `infrastructure/config.py` — Pydantic v2 models loaded from `~/.reqradar/config.yaml`
- **Paths**: `infrastructure/paths.py` — `get_paths()`, `ensure_dirs()`, `resolve_home()`
- **App lifespan**: `web/app.py` — sets `app.state.config`, `app.state.paths`, `app.state.report_storage`
- **DB**: SQLAlchemy 2.0 async (aiosqlite for dev), Alembic migrations
- **Auth**: JWT (python-jose) + bcrypt, `SECRET_KEY` module-level in `web/api/auth.py`

## Code Style

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
- `Optional[str]` is acceptable in older Pydantic model fields for backward compat
- SQLAlchemy columns: use `Mapped[type]` annotations
- FastAPI dependencies: `Annotated` types (`DbSession`, `CurrentUser`)

### Naming Conventions

| Element | Style | Example |
|---------|-------|---------|
| Modules/files | `snake_case` | `llm_client.py`, `analysis_agent.py` |
| Classes | `PascalCase` | `AnalysisAgent`, `LiteLLMClient`, `ReqRadarException` |
| Functions/methods | `snake_case` | `create_llm_client`, `load_config`, `hash_password` |
| Private attrs | `_leading_underscore` | `_cancelled`, `_current_task_id` |
| Constants | `UPPER_SNAKE_CASE` | `DEPTH_MAX_STEPS`, `EMBEDDING_MODELS` |
| Pydantic models | `PascalCase` | `HomeConfig`, `LLMConfig` |
| SQLAlchemy models | `PascalCase` | `AnalysisTask`, `ReportVersion` |

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

## Testing Conventions

### Test Suite Structure

```
tests/
├── conftest.py           # Shared fixtures (DB, app, auth, temp dirs)
├── factories.py          # Test data factories
├── helpers/              # Test helper modules
│   ├── auth_helper.py
│   ├── db_helper.py
│   ├── file_helper.py
│   └── bug_recorder.py   # Record project bugs found during testing
├── unit/                 # Unit tests (config, models, auth utils, dependencies)
├── integration/
│   ├── api/              # API integration tests (per router module)
│   ├── services/         # Service layer tests (report_storage, analysis_runner, etc.)
│   └── cli/              # CLI integration tests (per command group)
└── e2e/                  # End-to-end workflows
```

### Run tests

```bash
pytest                                    # all tests (coverage ON by default)
pytest tests/unit/                        # unit tests only
pytest tests/integration/api/             # API integration tests only
pytest tests/integration/api/test_auth_endpoints.py  # single file
pytest tests/integration/api/test_auth_endpoints.py::test_register  # single function
pytest tests/integration/api/test_auth_endpoints.py::TestAuth::test_register  # single class method
pytest -k "test_register"                 # keyword filter
```

Tests use pytest-asyncio with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorator needed.

### Testing Principles

- **按真实代码写测试** — 不为不存在的接口写测试
- **每完成一个文件或一组相关测试就运行对应测试**
- **测试失败先判断来源**: 测试代码错误 / 环境问题 / 项目 bug
- **发现项目 bug 只记录不修复** — 记录到 `helpers/bug_recorder.py`，用 `xfail` 标记
  - 唯一例外: 测试代码 / fixture / mock 路径 / 环境隔离问题可立即修复
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

### Bug Recording During Testing

```python
# BUG-N: 简短标题
# 发现阶段: Phase X  |  测试文件: tests/...  |  测试用例: test_xxx
# 复现步骤: ...
# 期望结果: ...  |  实际结果: ...
# 影响范围: ...  |  是否阻塞: Y/N
@pytest.mark.xfail(reason="BUG-N: 简短标题")
def test_xxx():
    ...
```

## Key Files

| File | Purpose |
|------|---------|
| `infrastructure/config.py` | Pydantic config models + `load_config()` |
| `infrastructure/paths.py` | `get_paths()`, `ensure_dirs()`, `resolve_home()` |
| `web/app.py` | `create_app()`, lifespan, route registration |
| `web/database.py` | SQLAlchemy async engine, `Base`, session factories |
| `web/dependencies.py` | `DbSession`, `CurrentUser`, `get_db`, `get_current_user` |
| `web/models.py` | SQLAlchemy ORM models |
| `web/api/` | API routers (auth, projects, analyses, reports, chatback, etc.) |
| `web/services/` | Business logic (analysis_runner, chatback_service, etc.) |
| `modules/llm_client.py` | LiteLLM unified client (`create_llm_client()` factory) |
| `core/exceptions.py` | Exception hierarchy |
| `tests/conftest.py` | Shared test fixtures |

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

## Storage Path

All data stored under `~/.reqradar/` (configurable via `home.path` in config):
- `~/.reqradar/config.yaml` — user configuration
- `~/.reqradar/reports/` — generated reports
- `~/.reqradar/memory/` — project memory data
- `~/.reqradar/indexes/` — ChromaDB vector indexes
