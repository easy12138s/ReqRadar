# Project Management Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the project management module to support isolated file spaces per project with three independent creation entry points (ZIP upload, Git clone, local path import) and a unified directory structure.

**Architecture:** Add a `ProjectFileService` that computes all project paths from `data_root + project.name`, replacing the old `repo_path`/`index_path`/`docs_path` DB fields with `source_type`/`source_url`. Three new API endpoints replace the old single `POST /api/projects`. All analysis runners and related APIs migrate to use `ProjectFileService` for path computation.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 (async) / Pydantic v2 / Alembic / TypeScript / React + Ant Design

---

## File Structure

### New files
| File | Responsibility |
|:---|:---|
| `src/reqradar/web/services/project_file_service.py` | Core service: directory creation, ZIP extraction, Git clone, code root detection, file tree, deletion |
| `tests/test_project_file_service.py` | Unit tests for ProjectFileService |
| `tests/test_project_api_v2.py` | Integration tests for new project API endpoints |
| `alembic/versions/d4e5f6a7b8c9_add_source_type_source_url_remove_old_paths.py` | Migration: add `source_type`/`source_url`, drop `repo_path`/`docs_path`/`index_path` |

### Modified files
| File | Change |
|:---|:---|
| `src/reqradar/infrastructure/config.py` | Add `data_root` field to `WebConfig` |
| `src/reqradar/web/models.py` | Project model: add `source_type`/`source_url`, remove `repo_path`/`docs_path`/`index_path` |
| `src/reqradar/web/api/projects.py` | Rewrite: new Pydantic models, 3 creation endpoints, file tree endpoint, remove old `POST /api/projects`, adapt `trigger_index` |
| `src/reqradar/web/api/analyses.py` | Upload endpoint: save to `requirements/` dir via ProjectFileService |
| `src/reqradar/web/api/profile.py` | Replace `project.repo_path` with ProjectFileService paths |
| `src/reqradar/web/api/memory.py` | Replace `project.repo_path` with ProjectFileService paths |
| `src/reqradar/web/services/analysis_runner.py` | Replace `project.repo_path`/`project.index_path` with ProjectFileService computed paths |
| `src/reqradar/web/services/analysis_runner_v2.py` | Same replacement as runner v1 |
| `frontend/src/types/api.ts` | Replace `language`/`framework` with `source_type`/`source_url` |
| `frontend/src/pages/Projects.tsx` | Replace single modal with three entry buttons + three modals |
| `frontend/src/pages/ProjectDetail.tsx` | Replace language/framework display with source_type, add file browser tab |
| `frontend/src/api/projects.ts` | Add `createFromZip`, `createFromGit`, `createFromLocal`, `getProjectFiles` functions |
| `.reqradar.yaml.example` | Add `web.data_root` field |

### Existing test files needing updates
| File | Change |
|:---|:---|
| `tests/test_profile_api.py` | `auth_client` fixture uses old `POST /api/projects` — update to use `from-local` |
| Other API tests that create projects via `POST /api/projects` | Update to use new endpoint |

---

## Task 1: Add `data_root` to WebConfig

**Files:**
- Modify: `src/reqradar/infrastructure/config.py:111-140`
- Modify: `.reqradar.yaml.example:58-71`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add a test to `tests/test_config.py` that verifies the new `data_root` field exists on `WebConfig` with its default value:

```python
def test_web_config_data_root_default():
    from reqradar.infrastructure.config import WebConfig
    wc = WebConfig()
    assert wc.data_root == "~/.reqradar/data"


def test_web_config_data_root_custom():
    from reqradar.infrastructure.config import WebConfig
    wc = WebConfig(data_root="/custom/data")
    assert wc.data_root == "/custom/data"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_config.py::test_web_config_data_root_default tests/test_config.py::test_web_config_data_root_custom -v`

Expected: FAIL with `ValidationError: unknown field` or `AttributeError`

- [ ] **Step 3: Write minimal implementation**

In `src/reqradar/infrastructure/config.py`, add the `data_root` field to `WebConfig` (after `db_pool_max_overflow` line 131, before the validator):

```python
data_root: str = Field(default="~/.reqradar/data", description="Root directory for project file storage (supports ~ expansion)")
```

In `.reqradar.yaml.example`, add `data_root` under the `web:` section (after `db_pool_max_overflow: 10` line 71):

```yaml
  data_root: ~/.reqradar/data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_config.py::test_web_config_data_root_default tests/test_config.py::test_web_config_data_root_custom -v`

Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 473+ tests pass

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/infrastructure/config.py .reqradar.yaml.example tests/test_config.py
git commit -m "feat: add data_root field to WebConfig for project file storage"
```

---

## Task 2: Update Project model — add `source_type`/`source_url`, remove old path fields

**Files:**
- Modify: `src/reqradar/web/models.py:61-86`
- Create: `alembic/versions/d4e5f6a7b8c9_add_source_type_source_url_remove_old_paths.py`
- Test: `tests/test_new_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_new_models.py`:

```python
def test_project_model_has_source_fields():
    from reqradar.web.models import Project
    columns = {c.name for c in Project.__table__.columns}
    assert "source_type" in columns
    assert "source_url" in columns


def test_project_model_no_old_path_fields():
    from reqradar.web.models import Project
    columns = {c.name for c in Project.__table__.columns}
    assert "repo_path" not in columns
    assert "docs_path" not in columns
    assert "index_path" not in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_new_models.py::test_project_model_has_source_fields tests/test_new_models.py::test_project_model_no_old_path_fields -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

In `src/reqradar/web/models.py`, replace the Project class fields (lines 61-86). Remove `repo_path`, `docs_path`, `index_path`, `config_json`. Add `source_type` and `source_url`:

```python
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    default_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_templates.id"), nullable=True
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    analysis_tasks: Mapped[list["AnalysisTask"]] = relationship(back_populates="project")
    configs: Mapped[list["ProjectConfig"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    default_template: Mapped["ReportTemplate | None"] = relationship()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_new_models.py::test_project_model_has_source_fields tests/test_new_models.py::test_project_model_no_old_path_fields -v`

Expected: PASS

- [ ] **Step 5: Create Alembic migration**

Run: `poetry run alembic revision -m "add_source_type_source_url_remove_old_paths" --rev-id d4e5f6a7b8c9`

Then write the migration file at `alembic/versions/d4e5f6a7b8c9_add_source_type_source_url_remove_old_paths.py`:

```python
"""add source_type/source_url, remove repo_path/docs_path/index_path/config_json

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-04-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('source_type', sa.String(20), nullable=False, server_default='local'))
    op.add_column('projects', sa.Column('source_url', sa.String(1024), nullable=False, server_default=''))
    op.drop_column('projects', 'repo_path')
    op.drop_column('projects', 'docs_path')
    op.drop_column('projects', 'index_path')
    op.drop_column('projects', 'config_json')


def downgrade() -> None:
    op.add_column('projects', sa.Column('repo_path', sa.String(1024), nullable=False, server_default=''))
    op.add_column('projects', sa.Column('docs_path', sa.String(1024), nullable=False, server_default=''))
    op.add_column('projects', sa.Column('index_path', sa.String(1024), nullable=False, server_default=''))
    op.add_column('projects', sa.Column('config_json', sa.Text(), nullable=False, server_default='{}'))
    op.drop_column('projects', 'source_type')
    op.drop_column('projects', 'source_url')
```

- [ ] **Step 6: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: Some tests may fail due to the model change (e.g., tests that reference `repo_path`). We will fix those in subsequent tasks. Note any failures and proceed — the critical path is to get the model and migration in place first.

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/web/models.py alembic/versions/d4e5f6a7b8c9_add_source_type_source_url_remove_old_paths.py tests/test_new_models.py
git commit -m "feat: update Project model — add source_type/source_url, remove old path fields"
```

---

## Task 3: Create `ProjectFileService`

**Files:**
- Create: `src/reqradar/web/services/project_file_service.py`
- Create: `tests/test_project_file_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_project_file_service.py`:

```python
import os
import shutil
import zipfile
from pathlib import Path

import pytest

from reqradar.infrastructure.config import WebConfig
from reqradar.web.services.project_file_service import ProjectFileService


@pytest.fixture
def service(tmp_path):
    data_root = str(tmp_path / "data")
    config = WebConfig(data_root=data_root)
    return ProjectFileService(config)


def test_get_project_path(service, tmp_path):
    result = service.get_project_path("my-project")
    assert result == Path(tmp_path / "data" / "my-project")


def test_create_project_dirs(service, tmp_path):
    service.create_project_dirs("test-proj")
    base = tmp_path / "data" / "test-proj"
    assert (base / "project_code").is_dir()
    assert (base / "requirements").is_dir()
    assert (base / "index").is_dir()
    assert (base / "memory").is_dir()


def test_create_project_dirs_idempotent(service, tmp_path):
    service.create_project_dirs("test-proj")
    service.create_project_dirs("test-proj")
    assert (tmp_path / "data" / "test-proj" / "project_code").is_dir()


def test_extract_zip(service, tmp_path):
    zip_dir = tmp_path / "zip_source"
    zip_dir.mkdir()
    (zip_dir / "main.py").write_text("print('hello')")
    (zip_dir / "README.md").write_text("# test")

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in zip_dir.iterdir():
            zf.write(f, f.name)

    zip_bytes = zip_path.read_bytes()
    service.create_project_dirs("zip-proj")
    service.extract_zip("zip-proj", zip_bytes)

    code_dir = tmp_path / "data" / "zip-proj" / "project_code"
    assert (code_dir / "main.py").exists()
    assert (code_dir / "README.md").exists()
    assert (tmp_path / "data" / "zip-proj" / "project.zip").exists()


def test_extract_zip_single_subdir(service, tmp_path):
    inner = tmp_path / "inner"
    inner.mkdir()
    subdir = inner / "my-app"
    subdir.mkdir()
    (subdir / "app.py").write_text("print('app')")

    zip_path = tmp_path / "subdir.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in subdir.rglob("*"):
            zf.write(f, f.relative_to(inner))

    zip_bytes = zip_path.read_bytes()
    service.create_project_dirs("subdir-proj")
    service.extract_zip("subdir-proj", zip_bytes)

    code_dir = tmp_path / "data" / "subdir-proj" / "project_code"
    assert (code_dir / "my-app" / "app.py").exists()


def test_detect_code_root_flat(service, tmp_path):
    service.create_project_dirs("flat-proj")
    code_dir = tmp_path / "data" / "flat-proj" / "project_code"
    (code_dir / "main.py").write_text("print('hello')")
    (code_dir / "utils.py").write_text("def util(): pass")

    result = service.detect_code_root("flat-proj")
    assert result == code_dir


def test_detect_code_root_single_subdir(service, tmp_path):
    service.create_project_dirs("sub-proj")
    code_dir = tmp_path / "data" / "sub-proj" / "project_code"
    subdir = code_dir / "cool-agent"
    subdir.mkdir()
    (subdir / "main.py").write_text("print('hello')")

    result = service.detect_code_root("sub-proj")
    assert result == subdir


def test_detect_code_root_multiple_subdirs(service, tmp_path):
    service.create_project_dirs("multi-proj")
    code_dir = tmp_path / "data" / "multi-proj" / "project_code"
    (code_dir / "dir1").mkdir()
    (code_dir / "dir2").mkdir()
    (code_dir / "main.py").write_text("print('hello')")

    result = service.detect_code_root("multi-proj")
    assert result == code_dir


def test_delete_project_files(service, tmp_path):
    service.create_project_dirs("del-proj")
    base = tmp_path / "data" / "del-proj"
    assert base.is_dir()

    service.delete_project_files("del-proj")
    assert not base.exists()


def test_delete_project_files_nonexistent(service):
    service.delete_project_files("nonexistent-proj")


def test_get_file_tree(service, tmp_path):
    service.create_project_dirs("tree-proj")
    code_dir = tmp_path / "data" / "tree-proj" / "project_code"
    (code_dir / "main.py").write_text("code")
    (code_dir / "sub").mkdir()
    (code_dir / "sub" / "helper.py").write_text("help")

    tree = service.get_file_tree("tree-proj")
    assert isinstance(tree, list)
    names = [item["name"] for item in tree]
    assert "project_code" in names


def test_is_git_available():
    config = WebConfig()
    svc = ProjectFileService(config)
    result = svc.is_git_available()
    assert isinstance(result, bool)


def test_get_project_path_tilde_expansion():
    config = WebConfig(data_root="~/reqradar_test_data")
    svc = ProjectFileService(config)
    path = svc.get_project_path("test")
    assert "~" not in str(path)
    assert str(path).endswith("test")


def test_clone_git_invalid_url(service, tmp_path):
    service.create_project_dirs("git-proj")
    with pytest.raises(Exception):
        service.clone_git("git-proj", "https://invalid-url-that-does-not-exist-12345.com/repo.git")


def test_get_index_path(service, tmp_path):
    service.create_project_dirs("idx-proj")
    result = service.get_index_path("idx-proj")
    assert result == tmp_path / "data" / "idx-proj" / "index"


def test_get_memory_path(service, tmp_path):
    service.create_project_dirs("mem-proj")
    result = service.get_memory_path("mem-proj")
    assert result == tmp_path / "data" / "mem-proj" / "memory"


def test_get_requirements_path(service, tmp_path):
    service.create_project_dirs("req-proj")
    result = service.get_requirements_path("req-proj")
    assert result == tmp_path / "data" / "req-proj" / "requirements"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_project_file_service.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'reqradar.web.services.project_file_service'`

- [ ] **Step 3: Write minimal implementation**

Create `src/reqradar/web/services/project_file_service.py`:

```python
import logging
import os
import shutil
import zipfile
from pathlib import Path

from reqradar.infrastructure.config import WebConfig

logger = logging.getLogger("reqradar.web.services.project_file_service")

VALID_SOURCE_TYPES = {"zip", "git", "local"}


class ProjectFileService:
    def __init__(self, web_config: WebConfig):
        self._data_root = Path(os.path.expanduser(web_config.data_root))

    def get_project_path(self, name: str) -> Path:
        return self._data_root / name

    def get_index_path(self, name: str) -> Path:
        return self.get_project_path(name) / "index"

    def get_memory_path(self, name: str) -> Path:
        return self.get_project_path(name) / "memory"

    def get_requirements_path(self, name: str) -> Path:
        return self.get_project_path(name) / "requirements"

    def create_project_dirs(self, name: str) -> None:
        base = self.get_project_path(name)
        for subdir in ("project_code", "requirements", "index", "memory"):
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def extract_zip(self, name: str, zip_bytes: bytes) -> None:
        base = self.get_project_path(name)
        code_dir = base / "project_code"
        zip_backup = base / "project.zip"

        zip_backup.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_backup) as zf:
            zf.extractall(code_dir)

        logger.info("Extracted zip for project '%s' to %s", name, code_dir)

    def clone_git(self, name: str, url: str, branch: str | None = None) -> None:
        if not self.is_git_available():
            raise RuntimeError("Git is not available on this system. Use ZIP upload instead.")

        base = self.get_project_path(name)
        code_dir = base / "project_code"

        cmd = ["git", "clone", url, str(code_dir)]
        if branch:
            cmd = ["git", "clone", "--branch", branch, url, str(code_dir)]

        import subprocess

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        logger.info("Cloned git repo for project '%s' from %s", name, url)

    def detect_code_root(self, name: str) -> Path:
        code_dir = self.get_project_path(name) / "project_code"
        if not code_dir.exists():
            return code_dir

        entries = list(code_dir.iterdir())
        dirs = [e for e in entries if e.is_dir()]
        files = [e for e in entries if e.is_file()]

        if len(dirs) == 1 and len(files) == 0:
            return dirs[0]

        return code_dir

    def delete_project_files(self, name: str) -> None:
        project_path = self.get_project_path(name)
        if project_path.exists():
            shutil.rmtree(project_path)
            logger.info("Deleted project files for '%s'", name)

    def get_file_tree(self, name: str) -> list[dict]:
        base = self.get_project_path(name)
        if not base.exists():
            return []

        def _build_tree(path: Path, relative: str = "") -> list[dict]:
            items = []
            try:
                for entry in sorted(path.iterdir()):
                    entry_rel = f"{relative}/{entry.name}" if relative else entry.name
                    if entry.is_dir():
                        children = _build_tree(entry, entry_rel)
                        items.append({
                            "name": entry.name,
                            "path": entry_rel,
                            "type": "directory",
                            "children": children,
                        })
                    else:
                        items.append({
                            "name": entry.name,
                            "path": entry_rel,
                            "type": "file",
                            "size": entry.stat().st_size,
                        })
            except PermissionError:
                pass
            return items

        return _build_tree(base)

    @staticmethod
    def is_git_available() -> bool:
        return shutil.which("git") is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_project_file_service.py -v`

Expected: All tests PASS except `test_clone_git_invalid_url` which should raise an Exception (this is expected behavior — it verifies the method raises on failure).

- [ ] **Step 5: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: Tests that depend on `project.repo_path` will still fail — we fix those in later tasks. The new service tests should pass.

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/web/services/project_file_service.py tests/test_project_file_service.py
git commit -m "feat: add ProjectFileService for isolated project file management"
```

---

## Task 4: Rewrite projects API — new endpoints and Pydantic models

**Files:**
- Modify: `src/reqradar/web/api/projects.py`
- Create: `tests/test_project_api_v2.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_project_api_v2.py`:

```python
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_reqradar_project_v2.db"
TEST_SECRET_KEY = "test-secret-key-project-v2"


@pytest_asyncio.fixture
async def setup_db(tmp_path):
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module
    import reqradar.infrastructure.config as config_module

    original_secret = auth_module.SECRET_KEY
    original_expire = auth_module.ACCESS_TOKEN_EXPIRE_MINUTES
    original_factory = dep_module.async_session_factory
    original_config = config_module.load_config

    data_root = str(tmp_path / "data")

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = TEST_SECRET_KEY
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = 1440

    def _test_config():
        c = original_config()
        c.web.auto_create_tables = True
        c.web.debug = True
        c.web.database_url = TEST_DATABASE_URL
        c.web.data_root = data_root
        return c

    config_module.load_config = _test_config

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory, data_root

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    dep_module.async_session_factory = original_factory
    auth_module.SECRET_KEY = original_secret
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire
    config_module.load_config = original_config

    db_path = "./test_reqradar_project_v2.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest_asyncio.fixture
async def auth_client(setup_db):
    session_factory, data_root = setup_db
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={"email": "projv2@example.com", "password": "secret123", "display_name": "Proj V2 User"},
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "projv2@example.com", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        yield client, headers, data_root


@pytest.mark.asyncio
async def test_create_project_from_local(auth_client):
    client, headers, data_root = auth_client
    response = await client.post(
        "/api/projects/from-local",
        json={"name": "local-proj", "description": "A local project", "local_path": "/tmp"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "local-proj"
    assert data["source_type"] == "local"
    assert data["source_url"] == "/tmp"


@pytest.mark.asyncio
async def test_create_project_from_local_duplicate_name(auth_client):
    client, headers, data_root = auth_client
    await client.post(
        "/api/projects/from-local",
        json={"name": "dup-proj", "description": "First", "local_path": "/tmp"},
        headers=headers,
    )
    response = await client.post(
        "/api/projects/from-local",
        json={"name": "dup-proj", "description": "Second", "local_path": "/tmp"},
        headers=headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_project_invalid_name(auth_client):
    client, headers, data_root = auth_client
    response = await client.post(
        "/api/projects/from-local",
        json={"name": "bad name!", "description": "Invalid name", "local_path": "/tmp"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_from_zip(auth_client, tmp_path):
    client, headers, data_root = auth_client

    zip_dir = tmp_path / "zip_content"
    zip_dir.mkdir()
    (zip_dir / "main.py").write_text("print('hello')")

    import zipfile
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in zip_dir.iterdir():
            zf.write(f, f.name)

    with open(zip_path, "rb") as f:
        response = await client.post(
            "/api/projects/from-zip",
            data={"name": "zip-proj", "description": "A zip project"},
            files={"file": ("test.zip", f, "application/zip")},
            headers=headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "zip-proj"
    assert data["source_type"] == "zip"


@pytest.mark.asyncio
async def test_list_projects(auth_client):
    client, headers, data_root = auth_client
    await client.post(
        "/api/projects/from-local",
        json={"name": "list-proj", "description": "For listing", "local_path": "/tmp"},
        headers=headers,
    )
    response = await client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(p["name"] == "list-proj" for p in data)


@pytest.mark.asyncio
async def test_get_project(auth_client):
    client, headers, data_root = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "get-proj", "description": "For getting", "local_path": "/tmp"},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "get-proj"


@pytest.mark.asyncio
async def test_get_project_files(auth_client):
    client, headers, data_root = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "files-proj", "description": "For files", "local_path": "/tmp"},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}/files", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_delete_project(auth_client):
    client, headers, data_root = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "del-proj", "description": "For deletion", "local_path": "/tmp"},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.delete(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_project(auth_client):
    client, headers, data_root = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "upd-proj", "description": "For update", "local_path": "/tmp"},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.put(
        f"/api/projects/{project_id}",
        json={"description": "Updated description"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_project_api_v2.py -v`

Expected: FAIL with 404 or similar — endpoints don't exist yet

- [ ] **Step 3: Write minimal implementation**

Rewrite `src/reqradar/web/api/projects.py` entirely:

```python
import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import load_config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import Project
from reqradar.web.services.project_file_service import ProjectFileService

logger = logging.getLogger("reqradar.web.api.projects")

router = APIRouter(prefix="/api/projects", tags=["projects"])

PROJECT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _get_file_service() -> ProjectFileService:
    config = load_config()
    return ProjectFileService(config.web)


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    source_type: str
    source_url: str
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectFromLocal(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = ""
    local_path: str


class ProjectFromGit(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = ""
    git_url: str
    branch: Optional[str] = None


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str
    size: Optional[int] = None
    children: Optional[list["FileTreeNode"]] = None


async def _create_project_record(
    name: str, description: str, source_type: str, source_url: str, owner_id: int, db: AsyncSession
) -> Project:
    existing = await db.execute(
        select(Project).where(Project.name == name, Project.owner_id == owner_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{name}' already exists",
        )

    project = Project(
        name=name,
        description=description,
        source_type=source_type,
        source_url=source_url,
        owner_id=owner_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.owner_id == current_user.id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/from-local", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_local(req: ProjectFromLocal, current_user: CurrentUser, db: DbSession):
    svc = _get_file_service()
    local_path = Path(req.local_path)
    if not local_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Local path does not exist: {req.local_path}",
        )

    project = await _create_project_record(req.name, req.description, "local", req.local_path, current_user.id, db)
    svc.create_project_dirs(req.name)

    src_code = svc.get_project_path(req.name) / "project_code"
    try:
        import shutil
        for item in local_path.iterdir():
            if item.is_dir():
                shutil.copytree(str(item), str(src_code / item.name), dirs_exist_ok=True)
            else:
                shutil.copy2(str(item), str(src_code / item.name))
    except Exception as e:
        logger.warning("Failed to copy local path files for project '%s': %s", req.name, e)

    return project


@router.post("/from-zip", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_zip(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(lambda: None),
    db: AsyncSession = Depends(lambda: None),
):
    from reqradar.web.dependencies import get_current_user, get_db
    current_user = await get_current_user(None, db)
    if not PROJECT_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Project name must match {PROJECT_NAME_PATTERN.pattern}",
        )

    svc = _get_file_service()
    project = await _create_project_record(name, description, "zip", file.filename or "upload.zip", current_user.id, db)
    svc.create_project_dirs(name)

    zip_bytes = await file.read()
    svc.extract_zip(name, zip_bytes)

    return project
```

Wait — the ZIP endpoint with Form parameters needs a different approach for dependency injection. Let me fix this properly.

Actually, let me look at the `analyses.py` pattern for `submit_analysis_upload` which uses `Form` + `File` + `Depends`. I should follow that same pattern.

Let me rewrite `projects.py` properly:

```python
import asyncio
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import load_config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import Project
from reqradar.web.services.project_file_service import ProjectFileService

logger = logging.getLogger("reqradar.web.api.projects")

router = APIRouter(prefix="/api/projects", tags=["projects"])

PROJECT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _get_file_service() -> ProjectFileService:
    config = load_config()
    return ProjectFileService(config.web)


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    source_type: str
    source_url: str
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectFromLocal(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = ""
    local_path: str


class ProjectFromGit(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = ""
    git_url: str
    branch: Optional[str] = None


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str
    size: Optional[int] = None
    children: Optional[list["FileTreeNode"]] = None


async def _create_project_record(
    name: str, description: str, source_type: str, source_url: str, owner_id: int, db: AsyncSession
) -> Project:
    existing = await db.execute(
        select(Project).where(Project.name == name, Project.owner_id == owner_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{name}' already exists",
        )

    project = Project(
        name=name,
        description=description,
        source_type=source_type,
        source_url=source_url,
        owner_id=owner_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.owner_id == current_user.id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/from-local", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_local(req: ProjectFromLocal, current_user: CurrentUser, db: DbSession):
    svc = _get_file_service()
    local_path = Path(req.local_path)
    if not local_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Local path does not exist: {req.local_path}",
        )

    project = await _create_project_record(req.name, req.description, "local", req.local_path, current_user.id, db)
    svc.create_project_dirs(req.name)

    src_code = svc.get_project_path(req.name) / "project_code"
    try:
        for item in local_path.iterdir():
            if item.is_dir():
                shutil.copytree(str(item), str(src_code / item.name), dirs_exist_ok=True)
            else:
                shutil.copy2(str(item), str(src_code / item.name))
    except Exception as e:
        logger.warning("Failed to copy local path files for project '%s': %s", req.name, e)

    return project


@router.post("/from-zip", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_zip(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(),
    db: AsyncSession = Depends(),
):
    if not PROJECT_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Project name must match {PROJECT_NAME_PATTERN.pattern}",
        )

    svc = _get_file_service()
    project = await _create_project_record(name, description, "zip", file.filename or "upload.zip", current_user.id, db)
    svc.create_project_dirs(name)

    zip_bytes = await file.read()
    svc.extract_zip(name, zip_bytes)

    return project


@router.post("/from-git", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_git(req: ProjectFromGit, current_user: CurrentUser, db: DbSession):
    svc = _get_file_service()
    if not svc.is_git_available():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Git is not available on this system. Use ZIP upload instead.",
        )

    project = await _create_project_record(req.name, req.description, "git", req.git_url, current_user.id, db)
    svc.create_project_dirs(req.name)

    try:
        svc.clone_git(req.name, req.git_url, req.branch)
    except Exception as e:
        await db.delete(project)
        await db.commit()
        svc.delete_project_files(req.name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Git clone failed: {str(e)[:500]}",
        )

    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, req: ProjectUpdate, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    project.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    svc = _get_file_service()
    await db.delete(project)
    await db.commit()
    svc.delete_project_files(project.name)

    return {"success": True, "message": f"Project '{project.name}' deleted"}


@router.get("/{project_id}/files", response_model=list[FileTreeNode])
async def get_project_files(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    svc = _get_file_service()
    tree = svc.get_file_tree(project.name)
    return tree


@router.post("/{project_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_index(project_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    async def _run_index():
        from reqradar.web.services.project_store import project_store
        config = load_config()
        svc = ProjectFileService(config.web)

        repo_path = svc.detect_code_root(project.name)
        index_path = svc.get_index_path(project.name)

        cm = ConfigManager(db, config)

        try:
            from reqradar.modules.code_parser import PythonCodeParser

            parser = PythonCodeParser()
            code_graph = parser.parse_directory(repo_path)

            index_path.mkdir(parents=True, exist_ok=True)
            graph_file = index_path / "code_graph.json"
            with open(graph_file, "w", encoding="utf-8") as f:
                f.write(code_graph.to_json())

            try:
                from reqradar.modules.vector_store import ChromaVectorStore, CHROMA_AVAILABLE
                if CHROMA_AVAILABLE:
                    req_dir = svc.get_requirements_path(project.name)
                    vectorstore_path = index_path / "vectorstore"
                    if req_dir.exists() and any(req_dir.iterdir()):
                        from reqradar.modules.loaders import LoaderRegistry
                        from reqradar.modules.vector_store import Document

                        vs = ChromaVectorStore(
                            persist_directory=str(vectorstore_path),
                            embedding_model=config.index.embedding_model,
                        )

                        for doc_path in req_dir.rglob("*"):
                            if doc_path.is_file():
                                loader = LoaderRegistry.get_for_file(doc_path)
                                if loader is None:
                                    continue
                                try:
                                    loaded_docs = loader.load(
                                        doc_path,
                                        chunk_size=config.loader.chunk_size,
                                        chunk_overlap=config.loader.chunk_overlap,
                                    )
                                    documents = [
                                        Document(
                                            id=f"{doc_path.stem}_{i}",
                                            content=doc.content,
                                            metadata={**doc.metadata, "format": doc.format},
                                        )
                                        for i, doc in enumerate(loaded_docs)
                                    ]
                                    if documents:
                                        vs.add_documents(documents)
                                except Exception:
                                    logger.warning("Failed to index file %s", doc_path)

                        vs.persist()
                        logger.info("Vector store built for project %d", project_id)
            except Exception:
                logger.warning("Vector store build failed for project %d", project_id, exc_info=True)

            memory_enabled = await cm.get_bool("memory.enabled", project_id=project_id, default=config.memory.enabled)
            if memory_enabled:
                from reqradar.modules.memory import MemoryManager

                memory_path = svc.get_memory_path(project.name)
                memory_manager = MemoryManager(storage_path=str(memory_path))
                memory_manager.load()

            await project_store.invalidate(project_id)

            logger.info("Index build completed for project %d", project_id)

        except Exception:
            logger.exception("Index build failed for project %d", project_id)

    asyncio.create_task(_run_index())

    return {"message": "Index build started", "project_id": project_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_project_api_v2.py -v`

Expected: Most tests PASS. The `create_from_zip` test may need adjustment depending on how FastAPI handles Form + Depends together. If the Depends for ZIP endpoint doesn't resolve properly, we need to use the explicit pattern from `analyses.py`:

```python
from reqradar.web.dependencies import get_current_user, get_db

@router.post("/from-zip", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_zip(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

Note: Use the explicit `Depends(get_current_user)` and `Depends(get_db)` pattern for the ZIP endpoint since it uses Form/File parameters, matching the existing pattern in `analyses.py:84-91`. The `from-zip` endpoint must import `get_current_user` and `get_db` from `dependencies.py`.

- [ ] **Step 5: Fix the ZIP endpoint dependency injection**

Update the `from-zip` endpoint to use explicit Depends (the CurrentUser/DbSession annotations don't work with Form+File params):

```python
from reqradar.web.dependencies import CurrentUser, DbSession, get_current_user, get_db
from reqradar.web.models import User

@router.post("/from-zip", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_from_zip(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not PROJECT_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Project name must match {PROJECT_NAME_PATTERN.pattern}",
        )

    svc = _get_file_service()
    project = await _create_project_record(name, description, "zip", file.filename or "upload.zip", current_user.id, db)
    svc.create_project_dirs(name)

    zip_bytes = await file.read()
    svc.extract_zip(name, zip_bytes)

    return project
```

- [ ] **Step 6: Run tests again**

Run: `poetry run pytest tests/test_project_api_v2.py -v`

Expected: All PASS

- [ ] **Step 7: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: Some tests may still fail due to old `repo_path` references in other files. We'll fix those next.

- [ ] **Step 8: Commit**

```bash
git add src/reqradar/web/api/projects.py tests/test_project_api_v2.py
git commit -m "feat: rewrite projects API with three creation endpoints and file tree"
```

---

## Task 5: Migrate analysis runners to use ProjectFileService

**Files:**
- Modify: `src/reqradar/web/services/analysis_runner.py:110-187`
- Modify: `src/reqradar/web/services/analysis_runner_v2.py:111-198`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_project_file_service.py`:

```python
def test_runner_paths_computed_from_service(tmp_path):
    from reqradar.infrastructure.config import WebConfig, Config
    from reqradar.web.services.project_file_service import ProjectFileService

    config = WebConfig(data_root=str(tmp_path / "runner_data"))
    svc = ProjectFileService(config)

    svc.create_project_dirs("runner-proj")
    code_root = svc.detect_code_root("runner-proj")
    index_path = svc.get_index_path("runner-proj")
    memory_path = svc.get_memory_path("runner-proj")
    requirements_path = svc.get_requirements_path("runner-proj")

    assert str(code_root).startswith(str(tmp_path / "runner_data"))
    assert "index" in str(index_path)
    assert "memory" in str(memory_path)
    assert "requirements" in str(requirements_path)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `poetry run pytest tests/test_project_file_service.py::test_runner_paths_computed_from_service -v`

Expected: PASS (this is really verifying the service interface, not the runner itself — runner integration is verified by existing runner tests)

- [ ] **Step 3: Update analysis_runner.py**

In `src/reqradar/web/services/analysis_runner.py`, modify the `_execute_pipeline` method. Replace lines 110-187 (the section that computes `index_path`, `repo_path`, `memory_manager`, `analysis_memory`, `git_analyzer`, and `tool_registry` setup):

Replace:

```python
            index_path = project.index_path or str(Path(project.repo_path) / ".reqradar" / "index")
            repo_path = project.repo_path or "."

            code_graph = await project_store.get_code_graph(project.id, index_path)
            vector_store = await project_store.get_vector_store(project.id, index_path)

            memory_manager = MemoryManager(
                storage_path=str(Path(project.repo_path) / config.memory.storage_path)
                if project.repo_path else config.memory.storage_path
            )
            memory_data = memory_manager.load() if config.memory.enabled else None

            from reqradar.modules.memory_manager import AnalysisMemoryManager

            analysis_memory = AnalysisMemoryManager(
                project_id=project.id,
                user_id=task.user_id,
                project_storage_path=str(Path(project.repo_path) / config.memory.project_storage_path)
                if project.repo_path else config.memory.project_storage_path,
                user_storage_path=str(Path(project.repo_path) / config.memory.user_storage_path)
                if project.repo_path else config.memory.user_storage_path,
                memory_enabled=config.memory.enabled,
            )
```

With:

```python
            from reqradar.web.services.project_file_service import ProjectFileService
            file_svc = ProjectFileService(config.web)

            repo_path = str(file_svc.detect_code_root(project.name))
            index_path = str(file_svc.get_index_path(project.name))
            memory_path = str(file_svc.get_memory_path(project.name))

            code_graph = await project_store.get_code_graph(project.id, index_path)
            vector_store = await project_store.get_vector_store(project.id, index_path)

            memory_manager = MemoryManager(storage_path=memory_path)
            memory_data = memory_manager.load() if config.memory.enabled else None

            from reqradar.modules.memory_manager import AnalysisMemoryManager

            analysis_memory = AnalysisMemoryManager(
                project_id=project.id,
                user_id=task.user_id,
                project_storage_path=memory_path,
                user_storage_path=memory_path,
                memory_enabled=config.memory.enabled,
            )
```

And replace the git_analyzer and tool setup section:

```python
            git_analyzer = None
            if project.repo_path and Path(project.repo_path, ".git").exists():
```

With:

```python
            git_analyzer = None
            if Path(repo_path, ".git").exists():
```

And replace:

```python
            tool_registry = ToolRegistry()
            repo_path_str = str(project.repo_path) if project.repo_path else "."
```

With:

```python
            tool_registry = ToolRegistry()
            repo_path_str = repo_path
```

- [ ] **Step 4: Update analysis_runner_v2.py**

In `src/reqradar/web/services/analysis_runner_v2.py`, make similar replacements.

In `_init_agent` method (lines 111-131), replace:

```python
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
```

With:

```python
        from reqradar.web.services.project_file_service import ProjectFileService
        file_svc = ProjectFileService(config.web)

        memory_path = str(file_svc.get_memory_path(project.name))

        memory_manager = MemoryManager(storage_path=memory_path)
        memory_data = memory_manager.load() if config.memory.enabled else None

        analysis_memory = AnalysisMemoryManager(
            project_id=project.id,
            user_id=task.user_id,
            project_storage_path=memory_path,
            user_storage_path=memory_path,
            memory_enabled=config.memory.enabled,
        )
```

In `_init_tools` method (lines 171-198), replace:

```python
        index_path = project.index_path or str(Path(project.repo_path) / ".reqradar" / "index")
        repo_path = project.repo_path or "."
```

With:

```python
        from reqradar.web.services.project_file_service import ProjectFileService
        file_svc = ProjectFileService(config.web)

        repo_path = str(file_svc.detect_code_root(project.name))
        index_path = str(file_svc.get_index_path(project.name))
```

And replace the PathSandbox and git_analyzer setup:

```python
        path_sandbox = PathSandbox(allowed_root=repo_path)
```

With:

```python
        path_sandbox = PathSandbox(allowed_root=repo_path)
```

(No change needed for PathSandbox — it already takes `repo_path` string.)

And replace:

```python
        try:
            git_analyzer = None
            if project.repo_path and Path(project.repo_path, ".git").exists():
                git_analyzer = GitAnalyzer(repo_path=Path(project.repo_path), lookback_months=config.git.lookback_months)
```

With:

```python
        try:
            git_analyzer = None
            if Path(repo_path, ".git").exists():
                git_analyzer = GitAnalyzer(repo_path=Path(repo_path), lookback_months=config.git.lookback_months)
```

And replace the ReadFileTool and SearchCodeTool `repo_path` references:

```python
        if code_graph:
            tool_registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path))
            tool_registry.register(GetDependenciesTool(code_graph=code_graph, memory_data=memory_data))

        tool_registry.register(ReadFileTool(repo_path=repo_path))
```

(These already use the local `repo_path` variable which is now computed from ProjectFileService, so they should work as-is.)

- [ ] **Step 5: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 473+ tests pass (some may still fail due to other files referencing `repo_path`)

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/web/services/analysis_runner.py src/reqradar/web/services/analysis_runner_v2.py tests/test_project_file_service.py
git commit -m "feat: migrate analysis runners to use ProjectFileService for path computation"
```

---

## Task 6: Migrate remaining API modules — analyses, profile, memory

**Files:**
- Modify: `src/reqradar/web/api/analyses.py:115`
- Modify: `src/reqradar/web/api/profile.py:51-55`
- Modify: `src/reqradar/web/api/memory.py:56-57,80-81,104-105`

- [ ] **Step 1: Write the failing test**

No new test file needed — the existing API tests should pass after the fix. The key verification is the full test suite.

- [ ] **Step 2: Update analyses.py upload endpoint**

In `src/reqradar/web/api/analyses.py`, replace the upload directory computation at line 115:

```python
        upload_dir = os.path.join(project.repo_path or ".", ".reqradar", "uploads")
```

With:

```python
        from reqradar.web.services.project_file_service import ProjectFileService
        file_svc = ProjectFileService(config.web)
        upload_dir = str(file_svc.get_requirements_path(project.name))
```

- [ ] **Step 3: Update profile.py**

In `src/reqradar/web/api/profile.py`, replace the `_build_project_memory` function (lines 51-55):

```python
def _build_project_memory(project: Project) -> ProjectMemory:
    config = load_config()
    storage_path = project.repo_path or "."
    memory_path = Path(storage_path) / config.memory.project_storage_path
    return ProjectMemory(storage_path=str(memory_path), project_id=project.id)
```

With:

```python
def _build_project_memory(project: Project) -> ProjectMemory:
    config = load_config()
    from reqradar.web.services.project_file_service import ProjectFileService
    file_svc = ProjectFileService(config.web)
    memory_path = file_svc.get_memory_path(project.name)
    return ProjectMemory(storage_path=str(memory_path), project_id=project.id)
```

- [ ] **Step 4: Update memory.py**

In `src/reqradar/web/api/memory.py`, there are three endpoints that compute memory paths. Replace each occurrence of:

```python
        memory = MemoryManager(
            storage_path=str(Path(project.repo_path) / ".reqradar" / "memory")
            if project.repo_path else ".reqradar/memory"
        )
```

With:

```python
        from reqradar.web.services.project_file_service import ProjectFileService
        from reqradar.infrastructure.config import load_config as _load_config
        _pfs_config = _load_config()
        _file_svc = ProjectFileService(_pfs_config.web)

        memory = MemoryManager(
            storage_path=str(_file_svc.get_memory_path(project.name))
        )
```

This pattern appears three times in the file: `get_terminology` (line 56), `get_modules` (line 80), `get_team` (line 104). Apply the same replacement to all three.

To reduce duplication, extract a helper function at the top of the file (after the router definition):

```python
def _get_memory_manager(project: Project) -> "MemoryManager":
    from reqradar.modules.memory import MemoryManager
    from reqradar.web.services.project_file_service import ProjectFileService
    config = load_config()
    file_svc = ProjectFileService(config.web)
    return MemoryManager(storage_path=str(file_svc.get_memory_path(project.name)))
```

Then replace all three occurrences with:

```python
        memory = _get_memory_manager(project)
```

Also add the import for `load_config` at the top of `memory.py` if not already present:

```python
from reqradar.infrastructure.config import load_config
```

- [ ] **Step 5: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 473+ tests pass

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/web/api/analyses.py src/reqradar/web/api/profile.py src/reqradar/web/api/memory.py
git commit -m "feat: migrate analyses, profile, memory APIs to use ProjectFileService"
```

---

## Task 7: Update frontend TypeScript types

**Files:**
- Modify: `frontend/src/types/api.ts:9-32`
- Modify: `frontend/src/api/projects.ts`

- [ ] **Step 1: Write the failing test**

Frontend tests are verified via `npm run build`. No separate unit test needed.

- [ ] **Step 2: Update api.ts types**

In `frontend/src/types/api.ts`, replace the Project, ProjectCreate, and ProjectUpdate interfaces (lines 9-32):

```typescript
export interface Project {
  id: string;
  name: string;
  description: string;
  source_type: 'zip' | 'git' | 'local';
  source_url: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
}

export interface ProjectCreateFromLocal {
  name: string;
  description: string;
  local_path: string;
}

export interface ProjectCreateFromGit {
  name: string;
  description: string;
  git_url: string;
  branch?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
}
```

Add a `FileTreeNode` type:

```typescript
export interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileTreeNode[];
}
```

- [ ] **Step 3: Update projects.ts API functions**

Rewrite `frontend/src/api/projects.ts`:

```typescript
import { apiClient } from './client';
import type {
  FileTreeNode,
  HistoryEntry,
  ModuleEntry,
  Project,
  ProjectCreateFromGit,
  ProjectCreateFromLocal,
  ProjectMemory,
  ProjectUpdate,
  TeamMember,
  TermEntry,
} from '@/types/api';

export async function getProjects(): Promise<Project[]> {
  const response = await apiClient.get<Project[]>('/projects');
  return response.data;
}

export async function createFromLocal(data: ProjectCreateFromLocal): Promise<Project> {
  const response = await apiClient.post<Project>('/projects/from-local', data);
  return response.data;
}

export async function createFromGit(data: ProjectCreateFromGit): Promise<Project> {
  const response = await apiClient.post<Project>('/projects/from-git', data);
  return response.data;
}

export async function createFromZip(
  name: string,
  description: string,
  file: File,
): Promise<Project> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('description', description);
  formData.append('file', file);
  const response = await apiClient.post<Project>('/projects/from-zip', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function getProject(id: string): Promise<Project> {
  const response = await apiClient.get<Project>(`/projects/${id}`);
  return response.data;
}

export async function updateProject(
  id: string,
  data: ProjectUpdate,
): Promise<Project> {
  const response = await apiClient.put<Project>(`/projects/${id}`, data);
  return response.data;
}

export async function deleteProject(id: string): Promise<void> {
  await apiClient.delete(`/projects/${id}`);
}

export async function getProjectFiles(id: string): Promise<FileTreeNode[]> {
  const response = await apiClient.get<FileTreeNode[]>(`/projects/${id}/files`);
  return response.data;
}

export async function getProjectMemory(id: string): Promise<ProjectMemory> {
  const [terminologyRes, modulesRes, teamRes, historyRes] = await Promise.all([
    apiClient.get<TermEntry[]>(`/projects/${id}/terminology`),
    apiClient.get<ModuleEntry[]>(`/projects/${id}/modules`),
    apiClient.get<TeamMember[]>(`/projects/${id}/team`),
    apiClient.get<HistoryEntry[]>(`/projects/${id}/history`),
  ]);

  return {
    terminology: terminologyRes.data,
    modules: modulesRes.data,
    team: teamRes.data,
    history: historyRes.data,
  };
}
```

- [ ] **Step 4: Verify frontend build**

Run: `cd frontend && npm run build`

Expected: Build succeeds with 0 TypeScript errors (though Projects.tsx and ProjectDetail.tsx will have compile errors until we update them in Task 8 — fix those imports first)

Actually, the old imports in Projects.tsx and ProjectDetail.tsx reference `ProjectCreate` and `createProject` which no longer exist. We need to update those files too. Let's handle this as part of Task 8, but for now we should at least make the types compile. The `ProjectCreate` type is still referenced in `Projects.tsx` line 27 — but we removed it. So we need to do Tasks 7 and 8 together.

Let me restructure: **Task 7 updates types + API client + both page components together** since they're tightly coupled.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/projects.ts
git commit -m "feat: update frontend types and API client for new project creation endpoints"
```

---

## Task 8: Rewrite Projects page with three creation modals

**Files:**
- Modify: `frontend/src/pages/Projects.tsx`
- Modify: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: Rewrite Projects.tsx**

Replace the entire content of `frontend/src/pages/Projects.tsx`:

```tsx
import { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Typography,
  Empty,
  Spin,
  Tag,
  message,
  Modal,
  Form,
  Input,
  Upload,
  Space,
} from 'antd';
import {
  PlusOutlined,
  CodeOutlined,
  CalendarOutlined,
  ProfileOutlined,
  SyncOutlined,
  BookOutlined,
  UploadOutlined,
  GithubOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import type { Project, ProjectCreateFromLocal, ProjectCreateFromGit } from '@/types/api';
import { getProjects, createFromZip, createFromGit, createFromLocal } from '@/api/projects';

const { Title, Text, Paragraph } = Typography;

const SOURCE_TYPE_LABELS: Record<string, { text: string; color: string }> = {
  zip: { text: 'ZIP', color: 'orange' },
  git: { text: 'Git', color: 'green' },
  local: { text: '本地路径', color: 'blue' },
};

export function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [zipModalVisible, setZipModalVisible] = useState(false);
  const [gitModalVisible, setGitModalVisible] = useState(false);
  const [localModalVisible, setLocalModalVisible] = useState(false);
  const [zipForm] = Form.useForm();
  const [gitForm] = Form.useForm();
  const [localForm] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const navigate = useNavigate();

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const data = await getProjects();
      setProjects(data);
    } catch {
      message.error('加载项目列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateFromZip = async (values: { name: string; description: string }) => {
    if (!zipFile) {
      message.error('请选择 ZIP 文件');
      return;
    }
    setSubmitting(true);
    try {
      await createFromZip(values.name, values.description, zipFile);
      message.success('项目创建成功');
      setZipModalVisible(false);
      zipForm.resetFields();
      setZipFile(null);
      fetchProjects();
    } catch {
      message.error('创建项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFromGit = async (values: ProjectCreateFromGit) => {
    setSubmitting(true);
    try {
      await createFromGit(values);
      message.success('项目创建成功');
      setGitModalVisible(false);
      gitForm.resetFields();
      fetchProjects();
    } catch {
      message.error('创建项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFromLocal = async (values: ProjectCreateFromLocal) => {
    setSubmitting(true);
    try {
      await createFromLocal(values);
      message.success('项目创建成功');
      setLocalModalVisible(false);
      localForm.resetFields();
      fetchProjects();
    } catch {
      message.error('创建项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          项目
        </Title>
        <Space>
          <Button icon={<UploadOutlined />} onClick={() => setZipModalVisible(true)}>
            上传 ZIP
          </Button>
          <Button icon={<GithubOutlined />} onClick={() => setGitModalVisible(true)}>
            Git 克隆
          </Button>
          <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => setLocalModalVisible(true)}>
            本地路径
          </Button>
        </Space>
      </div>

      {projects.length === 0 ? (
        <Empty
          description="暂无项目"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Space>
            <Button icon={<UploadOutlined />} onClick={() => setZipModalVisible(true)}>
              上传 ZIP
            </Button>
            <Button icon={<GithubOutlined />} onClick={() => setGitModalVisible(true)}>
              Git 克隆
            </Button>
            <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => setLocalModalVisible(true)}>
              本地路径
            </Button>
          </Space>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((project) => (
            <Col xs={24} sm={12} lg={8} key={project.id}>
              <Card
                hoverable
                onClick={() => navigate(`/projects/${project.id}`)}
                title={project.name}
                extra={<CodeOutlined />}
              >
                <Paragraph ellipsis={{ rows: 2 }}>{project.description}</Paragraph>
                <div style={{ marginTop: 12 }}>
                  <Tag color={SOURCE_TYPE_LABELS[project.source_type]?.color || 'default'}>
                    {SOURCE_TYPE_LABELS[project.source_type]?.text || project.source_type}
                  </Tag>
                </div>
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <CalendarOutlined />{' '}
                    {new Date(project.created_at).toLocaleDateString()}
                  </Text>
                </div>
                <div style={{ marginTop: 12 }}>
                  <Space size="small" onClick={(e) => e.stopPropagation()}>
                    <Link to={`/projects/${project.id}/profile`}>
                      <Button icon={<ProfileOutlined />} size="small">画像管理</Button>
                    </Link>
                    <Link to={`/projects/${project.id}/synonyms`}>
                      <Button icon={<BookOutlined />} size="small">同义词</Button>
                    </Link>
                    <Button icon={<SyncOutlined />} size="small">更新画像</Button>
                  </Space>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="上传 ZIP 创建项目"
        open={zipModalVisible}
        onCancel={() => { setZipModalVisible(false); zipForm.resetFields(); setZipFile(null); }}
        footer={null}
      >
        <Form form={zipForm} onFinish={handleCreateFromZip} layout="vertical">
          <Form.Item
            label="项目名称"
            name="name"
            rules={[
              { required: true, message: '请输入项目名称' },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: '仅支持字母、数字、下划线、连字符，1-64字符' },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入项目描述" />
          </Form.Item>
          <Form.Item
            label="ZIP 文件"
            required
          >
            <Upload
              beforeUpload={(file) => {
                setZipFile(file);
                return false;
              }}
              accept=".zip"
              maxCount={1}
              onRemove={() => setZipFile(null)}
            >
              <Button icon={<UploadOutlined />}>选择 ZIP 文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Git 克隆创建项目"
        open={gitModalVisible}
        onCancel={() => { setGitModalVisible(false); gitForm.resetFields(); }}
        footer={null}
      >
        <Form form={gitForm} onFinish={handleCreateFromGit} layout="vertical">
          <Form.Item
            label="项目名称"
            name="name"
            rules={[
              { required: true, message: '请输入项目名称' },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: '仅支持字母、数字、下划线、连字符，1-64字符' },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入项目描述" />
          </Form.Item>
          <Form.Item
            label="Git 仓库地址"
            name="git_url"
            rules={[{ required: true, message: '请输入 Git 仓库地址' }]}
          >
            <Input placeholder="https://github.com/user/repo.git" />
          </Form.Item>
          <Form.Item label="分支（可选）" name="branch">
            <Input placeholder="main" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              克隆并创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="本地路径创建项目"
        open={localModalVisible}
        onCancel={() => { setLocalModalVisible(false); localForm.resetFields(); }}
        footer={null}
      >
        <Form form={localForm} onFinish={handleCreateFromLocal} layout="vertical">
          <Form.Item
            label="项目名称"
            name="name"
            rules={[
              { required: true, message: '请输入项目名称' },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: '仅支持字母、数字、下划线、连字符，1-64字符' },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入项目描述" />
          </Form.Item>
          <Form.Item
            label="本地路径"
            name="local_path"
            rules={[{ required: true, message: '请输入本地路径' }]}
          >
            <Input placeholder="/path/to/your/project" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
```

- [ ] **Step 2: Rewrite ProjectDetail.tsx**

Replace the entire content of `frontend/src/pages/ProjectDetail.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Tabs,
  Typography,
  Descriptions,
  Tag,
  Table,
  Spin,
  Empty,
  Button,
  Form,
  Input,
  message,
  Tree,
} from 'antd';
import {
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  FolderOutlined,
  FileOutlined,
} from '@ant-design/icons';
import type {
  Project,
  ProjectMemory,
  ProjectUpdate,
  TermEntry,
  ModuleEntry,
  TeamMember,
  HistoryEntry,
  FileTreeNode,
} from '@/types/api';
import { getProject, updateProject, getProjectMemory, getProjectFiles } from '@/api/projects';

const { Title, Paragraph } = Typography;

const SOURCE_TYPE_LABELS: Record<string, { text: string; color: string }> = {
  zip: { text: 'ZIP', color: 'orange' },
  git: { text: 'Git', color: 'green' },
  local: { text: '本地路径', color: 'blue' },
};

function buildAntTree(nodes: FileTreeNode[]): import('antd').TreeDataNode[] {
  return nodes.map((node) => ({
    key: node.path,
    title: node.name,
    icon: node.type === 'directory' ? <FolderOutlined /> : <FileOutlined />,
    children: node.children ? buildAntTree(node.children) : undefined,
  }));
}

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [memory, setMemory] = useState<ProjectMemory | null>(null);
  const [fileTree, setFileTree] = useState<FileTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [projectData, memoryData, filesData] = await Promise.all([
        getProject(id),
        getProjectMemory(id),
        getProjectFiles(id).catch(() => []),
      ]);
      setProject(projectData);
      setMemory(memoryData);
      setFileTree(filesData);
      form.setFieldsValue(projectData);
    } catch {
      message.error('加载项目失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleSave = async (values: ProjectUpdate) => {
    if (!id) return;
    setSaving(true);
    try {
      const updated = await updateProject(id, values);
      setProject(updated);
      setEditing(false);
      message.success('项目更新成功');
    } catch {
      message.error('更新项目失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!project) {
    return <Empty description="项目未找到" />;
  }

  const overviewContent = editing ? (
    <Form
      form={form}
      onFinish={handleSave}
      layout="vertical"
      initialValues={project}
    >
      <Form.Item
        label="项目名称"
        name="name"
        rules={[{ required: true }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        label="项目描述"
        name="description"
      >
        <Input.TextArea rows={4} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={saving} icon={<SaveOutlined />}>
          保存
        </Button>
        <Button
          icon={<CloseOutlined />}
          onClick={() => {
            setEditing(false);
            form.resetFields();
          }}
          style={{ marginLeft: 8 }}
        >
          取消
        </Button>
      </Form.Item>
    </Form>
  ) : (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>
          编辑
        </Button>
      </div>
      <Descriptions bordered column={1}>
        <Descriptions.Item label="项目名称">{project.name}</Descriptions.Item>
        <Descriptions.Item label="项目描述">
          <Paragraph>{project.description}</Paragraph>
        </Descriptions.Item>
        <Descriptions.Item label="来源类型">
          <Tag color={SOURCE_TYPE_LABELS[project.source_type]?.color || 'default'}>
            {SOURCE_TYPE_LABELS[project.source_type]?.text || project.source_type}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="来源地址">{project.source_url || '-'}</Descriptions.Item>
        <Descriptions.Item label="创建时间">
          {new Date(project.created_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="更新时间">
          {new Date(project.updated_at).toLocaleString()}
        </Descriptions.Item>
      </Descriptions>
    </div>
  );

  const tabItems = [
    {
      key: 'overview',
      label: '概览',
      children: overviewContent,
    },
    {
      key: 'files',
      label: '文件浏览',
      children: fileTree.length > 0 ? (
        <Tree
          showIcon
          defaultExpandKeys={[fileTree[0]?.path]}
          treeData={buildAntTree(fileTree)}
        />
      ) : (
        <Empty description="暂无文件" />
      ),
    },
    {
      key: 'memory',
      label: '知识库',
      children: (
        <Tabs
          items={[
            {
              key: 'terminology',
              label: '术语',
              children: (
                <Table<TermEntry>
                  dataSource={memory?.terminology || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '术语', dataIndex: 'term', key: 'term' },
                    { title: '定义', dataIndex: 'definition', key: 'definition' },
                    { title: '上下文', dataIndex: 'context', key: 'context' },
                  ]}
                  locale={{ emptyText: '暂无术语记录' }}
                />
              ),
            },
            {
              key: 'modules',
              label: '模块',
              children: (
                <Table<ModuleEntry>
                  dataSource={memory?.modules || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '名称', dataIndex: 'name', key: 'name' },
                    { title: '描述', dataIndex: 'description', key: 'description' },
                    {
                      title: '职责',
                      dataIndex: 'responsibilities',
                      key: 'responsibilities',
                      render: (v: string[]) => v?.map((r) => <Tag key={r}>{r}</Tag>) || '-',
                    },
                  ]}
                  locale={{ emptyText: '暂无模块记录' }}
                />
              ),
            },
            {
              key: 'team',
              label: '团队',
              children: (
                <Table<TeamMember>
                  dataSource={memory?.team || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '姓名', dataIndex: 'name', key: 'name' },
                    { title: '角色', dataIndex: 'role', key: 'role' },
                    {
                      title: '专长',
                      dataIndex: 'expertise',
                      key: 'expertise',
                      render: (v: string[]) => v?.map((e) => <Tag key={e}>{e}</Tag>) || '-',
                    },
                  ]}
                  locale={{ emptyText: '暂无团队成员' }}
                />
              ),
            },
            {
              key: 'history',
              label: '历史',
              children: (
                <Table<HistoryEntry>
                  dataSource={memory?.history || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '事件', dataIndex: 'event', key: 'event' },
                    { title: '详情', dataIndex: 'details', key: 'details' },
                    {
                      title: '时间',
                      dataIndex: 'timestamp',
                      key: 'timestamp',
                      render: (v: string) => new Date(v).toLocaleString(),
                    },
                  ]}
                  locale={{ emptyText: '暂无历史记录' }}
                />
              ),
            },
          ]}
        />
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>{project.name}</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Verify frontend build**

Run: `cd frontend && npm run build`

Expected: 0 TypeScript errors

- [ ] **Step 4: Run full backend test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 473+ tests pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Projects.tsx frontend/src/pages/ProjectDetail.tsx
git commit -m "feat: rewrite Projects page with three creation modals and add file browser"
```

---

## Task 9: Fix existing tests that reference old project fields

**Files:**
- Modify: `tests/test_profile_api.py:77-82`
- Modify: any other test files that use `POST /api/projects` or reference `repo_path`

- [ ] **Step 1: Find all test files that reference old endpoints**

Search for `POST /api/projects` or `repo_path` in test files:

Run: `rg -l 'repo_path|/api/projects.*json' tests/`

- [ ] **Step 2: Update test_profile_api.py**

The `auth_client` fixture at line 77 creates a project via the old endpoint. Update it:

Replace:

```python
    proj_resp = await client.post(
        "/api/projects",
        json={"name": "Profile Project", "description": "test"},
        headers=headers,
    )
    project_id = proj_resp.json()["id"]
```

With:

```python
    proj_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "Profile-Project", "description": "test", "local_path": "/tmp"},
        headers=headers,
    )
    project_id = proj_resp.json()["id"]
```

- [ ] **Step 3: Update any other test files found in Step 1**

Apply the same pattern: replace `POST /api/projects` with `POST /api/projects/from-local`, adding `local_path: "/tmp"` to the JSON body. Update project names to use only `[a-zA-Z0-9_-]` characters.

Check and update these files (if they exist):
- `tests/test_round1_integration.py`
- `tests/test_round2_integration.py`
- `tests/test_round3_integration.py`
- `tests/test_chatback_api.py`
- `tests/test_version_api.py`
- `tests/test_evidence_api.py`
- `tests/test_report_templates_api.py`
- `tests/test_synonym_api.py`
- `tests/test_web_api_auth.py` (only if it creates projects)

- [ ] **Step 4: Run full test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 473+ tests pass

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "fix: update existing tests to use new project creation endpoint"
```

---

## Task 10: Final integration verification

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `poetry run pytest tests/ -x -q`

Expected: 473+ tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: 0 TypeScript errors

- [ ] **Step 3: Verify migration chain**

Run: `poetry run alembic heads`

Expected: Single head at `d4e5f6a7b8c9`

- [ ] **Step 4: Verify no references to old fields remain**

Run: `rg -l 'repo_path|docs_path|index_path|config_json' src/reqradar/web/ --include '*.py'`

Expected: No results (all old field references removed)

Run: `rg -l 'project\.repo_path|project\.index_path|project\.docs_path' src/reqradar/ --include '*.py'`

Expected: No results

- [ ] **Step 5: Final commit (if any stragglers fixed)**

```bash
git add -A
git commit -m "chore: final integration verification for project management refactor"
```

---

## Self-Review Checklist

### Spec Coverage
- [x] Directory structure: `data/<project_name>/project_code/`, `requirements/`, `index/`, `memory/`, `profile.yaml`, `project.zip` — Task 3
- [x] `project_code/` auto-detection — Task 3 (detect_code_root)
- [x] `web.data_root` config — Task 1
- [x] Project model changes (add source_type/source_url, remove old fields) — Task 2
- [x] Project name validation `^[a-zA-Z0-9_-]{1,64}$` — Task 4 (Pydantic field validators)
- [x] ProjectFileService with all methods — Task 3
- [x] Three new API endpoints — Task 4
- [x] `GET /api/projects/{id}/files` — Task 4
- [x] Remove old `POST /api/projects` — Task 4
- [x] Adapt `trigger_index` — Task 4
- [x] Frontend three creation modals — Task 8
- [x] Frontend file browser — Task 8
- [x] Frontend type updates — Task 7
- [x] Analysis runner integration — Task 5
- [x] PathSandbox `allowed_root` = `project_code/` dir — Task 5 (uses detect_code_root)
- [x] Git env detection — Task 3 (is_git_available)
- [x] Upload endpoint migration — Task 6
- [x] Memory/profile API migration — Task 6
- [x] Alembic migration — Task 2

### Placeholder Scan
No TBD, TODO, "implement later", or "add appropriate error handling" found.

### Type Consistency
- `ProjectFileService` methods return `Path` objects — consistent across Tasks 3, 4, 5, 6
- `ProjectResponse.source_type: str` — matches frontend `source_type: 'zip' | 'git' | 'local'`
- `ProjectResponse.source_url: str` — matches frontend `source_url: string`
- `FileTreeNode` type defined in both backend (Pydantic) and frontend (TypeScript) — consistent
- `_create_project_record` takes `source_type: str, source_url: str` — matches Project model fields
- `detect_code_root` returns `Path` — callers use `str()` conversion consistently
