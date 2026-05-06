# Web Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Web module to ReqRadar that enables browser-based requirement analysis, real-time progress tracking, and online report viewing, making the tool accessible to non-technical team members.

**Architecture:** Pydantic migration of core models first (enabling serialization/validation/schema), then Scheduler callback refactor (enabling step-level progress events), then FastAPI backend with SQLite via SQLAlchemy ORM, then React frontend with Vite + Ant Design, served as static files by FastAPI. All changes preserve CLI backward compatibility.

**Tech Stack:** Pydantic V2, FastAPI, Uvicorn, SQLAlchemy + aiosqlite, SQLite, JWT (python-jose), passlib[bcrypt], Alembic, React 18, TypeScript, Vite, Ant Design 5

---

## File Structure Overview

### Modified files
```
src/reqradar/core/context.py          # Pydantic migration (17 dataclasses → BaseModel)
src/reqradar/core/report.py           # Replace __dict__ with model_dump()
src/reqradar/core/scheduler.py        # Add on_step_start/on_step_complete callbacks
src/reqradar/infrastructure/config.py # Add WebConfig section
pyproject.toml                        # Add web dependencies
```

### New files
```
src/reqradar/web/__init__.py
src/reqradar/web/app.py               # FastAPI application factory
src/reqradar/web/database.py          # SQLAlchemy engine/session setup
src/reqradar/web/models.py            # SQLAlchemy ORM models (User, Project, AnalysisTask, Report)
src/reqradar/web/api/__init__.py
src/reqradar/web/api/auth.py          # Login / register / JWT
src/reqradar/web/api/projects.py      # Project CRUD
src/reqradar/web/api/analyses.py      # Analysis submit / list / detail / retry
src/reqradar/web/api/reports.py       # Report view / download
src/reqradar/web/services/__init__.py
src/reqradar/web/services/analysis_runner.py  # Async analysis executor
src/reqradar/web/services/project_store.py    # Project resource pool
src/reqradar/web/dependencies.py      # FastAPI dependency injection
src/reqradar/web/websocket.py         # WebSocket manager
src/reqradar/web/cli.py               # reqradar serve CLI command
alembic.ini
alembic/env.py
alembic/versions/001_initial.py
frontend/package.json
frontend/vite.config.ts
frontend/tsconfig.json
frontend/index.html
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/api/client.ts
frontend/src/pages/Login.tsx
frontend/src/pages/Projects.tsx
frontend/src/pages/Analysis.tsx
frontend/src/pages/Report.tsx
frontend/src/components/StepProgress.tsx
frontend/src/components/RiskBadge.tsx
frontend/src/layouts/AppLayout.tsx
docker/Dockerfile
docker/docker-compose.yml
```

### Test files
```
tests/test_context_pydantic.py
tests/test_scheduler_callback.py
tests/test_web_api_auth.py
tests/test_web_api_analyses.py
```

---

## Task 1: Pydantic Migration — Core Models (context.py)

**Files:**
- Modify: `src/reqradar/core/context.py`
- Modify: `src/reqradar/core/report.py`
- Create: `tests/test_context_pydantic.py`

- [ ] **Step 1: Write the failing test for Pydantic serialization**

Create `tests/test_context_pydantic.py`:

```python
"""Test Pydantic migration of core context models."""
import json
from datetime import datetime
from pathlib import Path

from reqradar.core.context import (
    AnalysisContext,
    ChangeAssessment,
    DecisionSummary,
    DecisionSummaryItem,
    DeepAnalysis,
    EvidenceItem,
    GeneratedContent,
    ImpactDomain,
    ImplementationHints,
    RequirementUnderstanding,
    RetrievedContext,
    RiskItem,
    StepResult,
    StructuredConstraint,
    TermDefinition,
)


def test_term_definition_serialization():
    t = TermDefinition(term="Web模块", definition="浏览器端操作界面", domain="frontend")
    data = t.model_dump()
    assert data["term"] == "Web模块"
    t2 = TermDefinition.model_validate(data)
    assert t2.term == t.term


def test_step_result_timestamp_serialization():
    sr = StepResult(step="read", success=True)
    data = sr.model_dump()
    assert "timestamp" in data
    sr2 = StepResult.model_validate(data)
    assert isinstance(sr2.timestamp, datetime)


def test_requirement_understanding_serialization():
    u = RequirementUnderstanding(
        raw_text="test",
        summary="A test requirement",
        keywords=["web", "api"],
        terms=[TermDefinition(term="web", definition="网页")],
    )
    data = u.model_dump()
    u2 = RequirementUnderstanding.model_validate(data)
    assert u2.summary == u.summary
    assert len(u2.terms) == 1


def test_deep_analysis_serialization():
    da = DeepAnalysis(
        risk_level="high",
        risks=[RiskItem(description="risk1", severity="high", scope="scope1", mitigation="mit1")],
        change_assessment=[
            ChangeAssessment(module="core", change_type="modify", impact_level="high", reason="reason1")
        ],
        decision_summary=DecisionSummary(
            summary="test decision",
            decisions=[DecisionSummaryItem(topic="t1", decision="d1", rationale="r1")],
        ),
        evidence_items=[EvidenceItem(kind="code_match", source="src/main.py", summary="found")],
        impact_domains=[ImpactDomain(domain="api", confidence="high", basis="code ref")],
    )
    data = da.model_dump()
    da2 = DeepAnalysis.model_validate(data)
    assert da2.risk_level == "high"
    assert len(da2.risks) == 1


def test_analysis_context_round_trip():
    ctx = AnalysisContext(requirement_path=Path("docs/req.md"))
    ctx.requirement_text = "test content"
    ctx.understanding = RequirementUnderstanding(summary="test")
    ctx.store_result("read", StepResult(step="read", success=True, data="ok"))
    ctx.deep_analysis = DeepAnalysis(risk_level="medium")
    ctx.generated_content = GeneratedContent(executive_summary="summary")
    ctx.decision_summary = DecisionSummary(summary="decide")

    json_str = ctx.model_dump_json()
    ctx2 = AnalysisContext.model_validate_json(json_str)
    assert isinstance(ctx2.requirement_path, Path)
    assert ctx2.understanding.summary == "test"
    assert ctx2.deep_analysis.risk_level == "medium"


def test_model_dump_excludes_private():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    data = ctx.model_dump()
    for key in data:
        assert not key.startswith("_")
        assert not key.startswith("__pydantic")


def test_step_result_mark_failed():
    sr = StepResult(step="read", success=True)
    sr.mark_failed("error msg", confidence=0.2)
    assert sr.success is False
    assert sr.error == "error msg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_context_pydantic.py -v`
Expected: FAIL — models are still dataclasses

- [ ] **Step 3: Migrate context.py — replace all dataclass with Pydantic BaseModel**

Key changes in `src/reqradar/core/context.py`:
1. `from dataclasses import dataclass, field` → `from pydantic import BaseModel, ConfigDict, Field`
2. All `@dataclass` → inherit from `BaseModel`
3. All `field(default_factory=...)` → `Field(default_factory=...)`
4. All `field(default=...)` → `Field(default=...)`
5. `AnalysisContext` needs `model_config = ConfigDict(arbitrary_types_allowed=True)` for `Path` type
6. `DeepAnalysis.decision_summary: "DecisionSummary" = Field(default_factory=DecisionSummary)` — forward ref resolved by definition order (DecisionSummary defined before DeepAnalysis)
7. All `@property`, `store_result()`, `get_result()`, `finalize()`, `mark_failed()` methods stay as-is

The complete file is provided in the self-review section below for reference.

- [ ] **Step 4: Run the Pydantic serialization tests**

Run: `PYTHONPATH=src pytest tests/test_context_pydantic.py -v`
Expected: PASS

- [ ] **Step 5: Fix report.py — replace `__dict__` with `model_dump()`**

In `src/reqradar/core/report.py`, replace 5 occurrences:

| Line | Before | After |
|------|--------|-------|
| 124 | `[t.__dict__ for t in understanding.terms]` | `[t.model_dump() for t in understanding.terms]` |
| 127 | `[c.__dict__ for c in understanding.structured_constraints]` | `[c.model_dump() for c in understanding.structured_constraints]` |
| 130 | `[ca.__dict__ for ca in analysis.change_assessment]` | `[ca.model_dump() for ca in analysis.change_assessment]` |
| 135 | `[r.__dict__ for r in analysis.risks]` | `[r.model_dump() for r in analysis.risks]` |
| 139 | `analysis.implementation_hints.__dict__` | `analysis.implementation_hints.model_dump()` |

- [ ] **Step 6: Run ALL existing tests for regression**

Run: `PYTHONPATH=src pytest tests/ -v --tb=short`
Expected: All 296 pass (or same 1 known async issue). Fix any:
- `dataclasses.asdict(ctx)` → `ctx.model_dump()`
- Path assertions: compare `str(path)` if needed

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/core/context.py src/reqradar/core/report.py tests/test_context_pydantic.py
git commit -m "feat: migrate core context models from dataclass to Pydantic BaseModel

Enables model_dump()/model_validate() for Web serialization,
automatic OpenAPI schema generation, and input validation.
Replaces __dict__ with model_dump() in report renderer."
```

---

## Task 2: Scheduler Callback Refactor

**Files:**
- Modify: `src/reqradar/core/scheduler.py`
- Create: `tests/test_scheduler_callback.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler_callback.py`:

```python
"""Test Scheduler callback support for Web progress push."""
import asyncio
from pathlib import Path

import pytest

from reqradar.core.context import AnalysisContext, StepResult
from reqradar.core.scheduler import Scheduler


@pytest.mark.asyncio
async def test_scheduler_calls_on_step_start():
    started_steps = []

    async def on_start(step_name: str, step_desc: str):
        started_steps.append(step_name)

    scheduler = Scheduler(
        read_handler=lambda ctx: asyncio.sleep(0, "content"),
        extract_handler=lambda ctx: asyncio.sleep(0),
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_start=on_start)
    assert "read" in started_steps


@pytest.mark.asyncio
async def test_scheduler_calls_on_step_complete():
    completed = []

    async def on_complete(step_name: str, result: StepResult):
        completed.append((step_name, result.success))

    scheduler = Scheduler(
        read_handler=lambda ctx: asyncio.sleep(0, "content"),
        extract_handler=lambda ctx: asyncio.sleep(0),
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_complete=on_complete)
    assert any(name == "read" for name, _ in completed)


@pytest.mark.asyncio
async def test_scheduler_no_callback_is_default():
    scheduler = Scheduler(
        read_handler=lambda ctx: asyncio.sleep(0, "content"),
        extract_handler=lambda ctx: asyncio.sleep(0),
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    result = await scheduler.run(context)
    assert result.is_complete


@pytest.mark.asyncio
async def test_scheduler_callback_on_failed_step():
    failed_step = None

    async def on_complete(step_name: str, result: StepResult):
        nonlocal failed_step
        if not result.success:
            failed_step = step_name

    scheduler = Scheduler(
        read_handler=lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
        extract_handler=lambda ctx: asyncio.sleep(0),
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_complete=on_complete)
    assert failed_step == "read"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_scheduler_callback.py -v`
Expected: FAIL — `TypeError: run() got unexpected keyword arguments`

- [ ] **Step 3: Modify scheduler.py**

Add two optional parameters to `run()`:

```python
async def run(
    self,
    context: AnalysisContext,
    on_step_start: Callable[[str, str], Awaitable] = None,
    on_step_complete: Callable[[str, StepResult], Awaitable] = None,
) -> AnalysisContext:
```

In the step loop body, add callback invocations:
- After `logger.info("Step %s started", step_name)`: `if on_step_start: await on_step_start(step_name, step_desc)`
- After `context.store_result(step_name, step_result)` in both success and failure branches: `if on_step_complete: await on_step_complete(step_name, context.get_result(step_name))`
- On FatalError, call `on_step_complete` before `break` so failure is delivered

The `with Progress()` block and `progress.update()` calls remain unchanged — CLI mode (no callbacks) still uses rich progress.

- [ ] **Step 4: Run callback tests**

Run: `PYTHONPATH=src pytest tests/test_scheduler_callback.py -v`
Expected: PASS

- [ ] **Step 5: Run existing scheduler tests for regression**

Run: `PYTHONPATH=src pytest tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `PYTHONPATH=src pytest tests/ -v --tb=short`
Expected: ALL pass

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/core/scheduler.py tests/test_scheduler_callback.py
git commit -m "feat: add on_step_start/on_step_complete callbacks to Scheduler

Enables external observers (WebSocket) to track pipeline progress.
CLI behavior unchanged — callbacks are optional, default to None."
```

---

## Task 3: Web Backend — Foundation (FastAPI + DB + Auth)

**Files:**
- Modify: `src/reqradar/infrastructure/config.py`
- Modify: `pyproject.toml`
- Modify: `src/reqradar/cli/main.py`
- Create: `src/reqradar/web/__init__.py`
- Create: `src/reqradar/web/app.py`
- Create: `src/reqradar/web/database.py`
- Create: `src/reqradar/web/models.py`
- Create: `src/reqradar/web/dependencies.py`
- Create: `src/reqradar/web/api/__init__.py`
- Create: `src/reqradar/web/api/auth.py`
- Create: `tests/test_web_api_auth.py`

- [ ] **Step 1: Add web dependencies to pyproject.toml**

```toml
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
python-multipart = "^0.0.18"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
sqlalchemy = {extras = ["asyncio"], version = "^2.0.0"}
aiosqlite = "^0.20.0"
alembic = "^1.14.0"
```

Run: `poetry install`

- [ ] **Step 2: Add WebConfig to infrastructure/config.py**

```python
class WebConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    database_url: str = Field(default="sqlite+aiosqlite:///./reqradar.db")
    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = Field(default=1440)
    debug: bool = Field(default=False)
    static_dir: Optional[str] = Field(default=None)
```

Add `web: WebConfig = Field(default_factory=WebConfig)` to `Config` class.

- [ ] **Step 3: Create database.py**

SQLAlchemy async engine + session factory + DeclarativeBase. SQLite via aiosqlite.

- [ ] **Step 4: Create models.py (SQLAlchemy ORM)**

Tables: `users`, `projects`, `analysis_tasks`, `reports`. `analysis_tasks.context_json` stores serialized AnalysisContext.

- [ ] **Step 5: Create dependencies.py**

`DbSession` type (async session), `CurrentUser` type (JWT-decoded user), `oauth2_scheme`.

- [ ] **Step 6: Create api/auth.py**

`/api/auth/register`, `/api/auth/login`, `/api/auth/me`. JWT with python-jose, bcrypt with passlib.

- [ ] **Step 7: Create app.py**

FastAPI factory: lifespan creates tables, includes routers, serves static files, adds CORS middleware, adds `/health` endpoint.

- [ ] **Step 8: Add `reqradar serve` CLI command**

`src/reqradar/web/cli.py` + register in `cli/main.py`.

- [ ] **Step 9: Write and run auth tests**

`tests/test_web_api_auth.py` — register, login, duplicate, wrong password.

Run: `PYTHONPATH=src pytest tests/test_web_api_auth.py -v`

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: add Web module foundation — FastAPI, SQLite, auth API"
```

---

## Task 4: Web Backend — Analysis API + WebSocket

**Files:**
- Create: `src/reqradar/web/api/projects.py`
- Create: `src/reqradar/web/api/analyses.py`
- Create: `src/reqradar/web/api/reports.py`
- Create: `src/reqradar/web/services/__init__.py`
- Create: `src/reqradar/web/services/analysis_runner.py`
- Create: `src/reqradar/web/services/project_store.py`
- Create: `src/reqradar/web/websocket.py`
- Modify: `src/reqradar/web/app.py`
- Create: `tests/test_web_api_analyses.py`

- [ ] **Step 1: Create websocket.py** — ConnectionManager: subscribe/unsubscribe/broadcast by task_id

- [ ] **Step 2: Create project_store.py** — Cache CodeGraph and VectorStore per project_id

- [ ] **Step 3: Create analysis_runner.py** — Wire Scheduler with callbacks that broadcast via WebSocket. Save AnalysisContext as JSON to task.context_json. Render report and save to Report table. Add asyncio.Semaphore for concurrent limit (default 2).

- [ ] **Step 4: Create api/projects.py** — CRUD: list, create, get

- [ ] **Step 5: Create api/analyses.py** — submit (creates task + launches asyncio.create_task), list, get, retry. WebSocket endpoint at `/{task_id}/ws`. File upload via UploadFile for requirement documents.

- [ ] **Step 6: Create api/reports.py** — get report JSON, download as Markdown

- [ ] **Step 7: Wire routers into app.py**

- [ ] **Step 8: Write and run analysis API tests**

- [ ] **Step 9: Commit**

```bash
git commit -m "feat: add analysis API, WebSocket progress, project management"
```

---

## Task 5: Frontend — React + Vite + Ant Design

**Files:**
- Create: `frontend/` directory with all source files
- Modify: `src/reqradar/web/app.py` (static file serving)

- [ ] **Step 1: Initialize Vite + React + TypeScript project**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install antd @ant-design/icons react-router-dom axios
```

- [ ] **Step 2: Configure vite.config.ts** — proxy `/api` and `/ws` to backend, build output to `src/reqradar/web/static/`

- [ ] **Step 3: Create API client** — `frontend/src/api/client.ts` with axios + JWT interceptor

- [ ] **Step 4: Create pages** — Login, Projects (list + create), Analysis (submit + StepProgress), Report (Markdown rendering with react-markdown)

- [ ] **Step 5: Create StepProgress component** — WebSocket connection per task, real-time step status display using Ant Design Steps

- [ ] **Step 6: Create RiskBadge component** — Color-coded risk level label

- [ ] **Step 7: Build and verify**

```bash
cd frontend && npm run build
PYTHONPATH=src reqradar serve
```

- [ ] **Step 8: Commit**

```bash
git commit -m "feat: add React frontend with Vite + Ant Design"
```

---

## Task 6: Docker Deployment

**Files:**
- Create: `docker/Dockerfile`
- Create: `docker/docker-compose.yml`

- [ ] **Step 1: Create Dockerfile** — Python 3.12-slim, poetry install, npm build, expose 8000

- [ ] **Step 2: Create docker-compose.yml** — Single service, volumes for .reqradar data and SQLite, environment variables for API key and JWT secret

- [ ] **Step 3: Test Docker build and run**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add Docker deployment with docker-compose"
```

---

## Self-Review

### Spec Coverage

| Requirement | Status | Task |
|------------|--------|------|
| 项目列表与索引管理 | Partial (CRUD, index trigger deferred) | Task 4 |
| 需求分析任务管理 | Full (submit + WebSocket + retry + file upload) | Task 4 |
| 分析报告在线查看 | Full (view + download) | Task 4+5 |
| 项目记忆可视化 | Deferred Phase 2 | — |
| 多人协作与权限控制 | Partial (auth, RBAC deferred) | Task 3 |
| API 接口层 | Full (OpenAPI auto-generated) | Task 3+4 |
| SQLite | Done | Task 3 |
| FastAPI + Uvicorn | Done | Task 3 |
| React + TypeScript + Ant Design | Done | Task 5 |
| Docker Compose | Done | Task 6 |
| 向后兼容 | CLI unchanged | Task 1+2 |
| /health endpoint | Add in Task 3 app.py | Task 3 |
| WebSocket < 500ms | FastAPI native | Task 4 |

### Known Gaps for Phase 2

- Index trigger from Web (CPU-intensive, needs progress push)
- Memory CRUD (term/module/team edit pages)
- RBAC (admin/editor/viewer roles)
- Report PDF export
- Report history comparison
- OAuth2.0 login
- Webhook
- Mobile responsive layout

---

*Plan last updated: 2026-04-22*
