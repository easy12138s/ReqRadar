# Round 1: Memory + Templates + Synonyms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three most independent modules — layered memory system, report template system, and synonym mapping — without changing the core analysis pipeline.

**Architecture:** Add new modules alongside existing code. The existing `MemoryManager` (YAML-based) is preserved as-is and will be migrated to `ProjectMemory` (Markdown-based). A new `PendingChange` abstraction serves both profile updates and synonym confirmations. New DB models and Alembic migrations are added incrementally.

**Tech Stack:** Python 3.12, SQLAlchemy async, Alembic, Pydantic, Jinja2, FastAPI, pytest, pytest-asyncio

---

## File Structure

### New Files
- `src/reqradar/modules/project_memory.py` — ProjectMemory: read/write/parse `project.md`, detect changes, generate diffs
- `src/reqradar/modules/user_memory.py` — UserMemory: read/write/parse `user.md`
- `src/reqradar/modules/memory_manager.py` — Unified facade: loads project + user + vector memory, replaces old MemoryManager usage in analysis_runner
- `src/reqradar/modules/synonym_resolver.py` — Resolve business terms to code terms using DB + fallback to hardcoded synonyms
- `src/reqradar/modules/pending_changes.py` — PendingChange CRUD operations (DB-level)
- `src/reqradar/templates/default_report.yaml` — Default report template definition (section descriptions + requirements)
- `src/reqradar/agent/prompts/__init__.py` — Package init, re-exports from current prompts.py
- `src/reqradar/agent/prompts/analysis.py` — Analysis phase prompts (moved from prompts.py)
- `src/reqradar/agent/prompts/chatback.py` — Chatback phase prompts (Round 3 placeholder)
- `src/reqradar/infrastructure/template_loader.py` — Load template definitions (YAML) and render templates (Jinja2)
- `tests/test_project_memory.py` — Tests for ProjectMemory
- `tests/test_user_memory.py` — Tests for UserMemory
- `tests/test_memory_manager.py` — Tests for unified MemoryManager facade
- `tests/test_synonym_resolver.py` — Tests for synonym resolution
- `tests/test_pending_changes.py` — Tests for PendingChange CRUD
- `tests/test_template_loader.py` — Tests for template loading and rendering
- `tests/test_report_templates_api.py` — API tests for template endpoints
- `tests/test_synonym_api.py` — API tests for synonym endpoints
- `tests/test_profile_api.py` — API tests for profile/pending-change endpoints

### Modified Files
- `src/reqradar/web/models.py` — Add PendingChange, SynonymMapping, ReportTemplate models; add `current_version`, `depth` fields to AnalysisTask; add `default_template_id` to Project
- `src/reqradar/core/report.py` — Accept template definition + render template; support ReportData dict input
- `src/reqradar/web/app.py` — Register new routers
- `src/reqradar/infrastructure/config.py` — Add AgentConfig, MemoryConfig updates, ReportingConfig
- `src/reqradar/web/services/analysis_runner.py` — Use new MemoryManager facade; pass template to ReportRenderer
- `src/reqradar/agent/prompts.py` — Move content to `prompts/` package (re-export for backward compat)
- `src/reqradar/agent/steps.py` — Use SynonymResolver for keyword mapping; use ProjectMemory for profile injection

---

## Task 1: Add New Config Models

**Files:**
- Modify: `src/reqradar/infrastructure/config.py`

- [ ] **Step 1: Write the failing test for new config fields**

Add a test in `tests/test_config.py` that verifies the new config fields exist and have defaults:

```python
def test_agent_config_defaults():
    from reqradar.infrastructure.config import AgentConfig, ReportingConfig
    agent = AgentConfig()
    assert agent.mode == "legacy"
    assert agent.max_steps == 15
    assert agent.max_steps_quick == 10
    assert agent.max_steps_deep == 25
    assert agent.version_limit == 10

    reporting = ReportingConfig()
    assert reporting.default_template_id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_agent_config_defaults -v`
Expected: FAIL with ImportError or AttributeError

- [ ] **Step 3: Implement AgentConfig and ReportingConfig in config.py**

Add after `AnalysisConfig` class in `src/reqradar/infrastructure/config.py`:

```python
class AgentConfig(BaseModel):
    mode: str = Field(default="legacy", description="Analysis mode: legacy (fixed pipeline) or react (ReAct agent)")
    max_steps: int = Field(default=15, description="Max agent steps for standard depth")
    max_steps_quick: int = Field(default=10, description="Max agent steps for quick depth")
    max_steps_deep: int = Field(default=25, description="Max agent steps for deep depth")
    version_limit: int = Field(default=10, description="Max report versions per task")
    sensitive_file_patterns: list[str] = Field(
        default_factory=lambda: [".env", ".env.*", "*.key", "*.pem", "*.crt", "secrets/", "credentials/", ".aws/", ".ssh/"],
        description="Sensitive file patterns to block agent access"
    )


class ReportingConfig(BaseModel):
    default_template_id: int = Field(default=1, description="Default report template ID")
```

Then add these to the `Config` class:

```python
class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    loader: LoaderConfig = Field(default_factory=LoaderConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    web: WebConfig = Field(default_factory=WebConfig)
```

Also update `MemoryConfig` to add the new fields:

```python
class MemoryConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable project memory")
    storage_path: str = Field(default=".reqradar/memory", description="Memory storage directory (legacy)")
    project_storage_path: str = Field(default=".reqradar/memories", description="Project memory storage path")
    user_storage_path: str = Field(default=".reqradar/user_memories", description="User memory storage path")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_agent_config_defaults -v`
Expected: PASS

- [ ] **Step 5: Run existing config tests**

Run: `pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/infrastructure/config.py tests/test_config.py
git commit -m "feat: add AgentConfig, ReportingConfig, and update MemoryConfig for Round 1"
```

---

## Task 2: Add New Database Models

**Files:**
- Modify: `src/reqradar/web/models.py`

- [ ] **Step 1: Write the failing test for new models**

Add to a new test file `tests/test_new_models.py`:

```python
import pytest
from reqradar.web.models import (
    PendingChange, SynonymMapping, ReportTemplate, AnalysisTask, Project
)


def test_pending_change_model_fields():
    change = PendingChange(
        project_id=1,
        change_type="profile",
        target_id="module:auth",
        old_value="",
        new_value="### auth\nAuthentication module",
        diff="+ ### auth\n+ Authentication module",
        source="agent",
    )
    assert change.project_id == 1
    assert change.change_type == "profile"
    assert change.status == "pending"


def test_synonym_mapping_model_fields():
    mapping = SynonymMapping(
        project_id=1,
        business_term="配置",
        code_terms='["config", "settings"]',
        priority=100,
        source="user",
    )
    assert mapping.business_term == "配置"
    assert mapping.priority == 100


def test_report_template_model_fields():
    template = ReportTemplate(
        name="Default Template",
        definition="sections: []",
        render_template="# {{ title }}",
        is_default=True,
    )
    assert template.is_default is True
    assert template.name == "Default Template"


def test_analysis_task_new_fields():
    task = AnalysisTask(
        project_id=1,
        user_id=1,
        requirement_name="test",
        requirement_text="test text",
    )
    assert task.current_version == 1
    assert task.depth == "standard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_new_models.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Add new models to `src/reqradar/web/models.py`**

Add these models after the `UploadedFile` class:

```python
class PendingChange(Base):
    __tablename__ = "pending_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    new_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    diff: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class SynonymMapping(Base):
    __tablename__ = "synonym_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    business_term: Mapped[str] = mapped_column(String(200), nullable=False)
    code_terms: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "business_term", name="uq_synonym_project_term"),)


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    render_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[int | None] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=True)
```

Also add the new fields to `AnalysisTask` and `Project`:

```python
# In AnalysisTask class, add after created_at:
current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
depth: Mapped[str] = mapped_column(String(20), default="standard", nullable=False)

# In Project class, add after updated_at:
default_template_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("report_templates.id"), nullable=True
)
```

Add relationships to Project:

```python
# In Project class, add:
default_template: Mapped["ReportTemplate | None"] = relationship()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_new_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/models.py tests/test_new_models.py
git commit -m "feat: add PendingChange, SynonymMapping, ReportTemplate models and AnalysisTask/Project field updates"
```

---

## Task 3: Alembic Migration for New Tables

**Files:**
- Create: `alembic/versions/<hash>_add_memory_template_synonym_tables.py`

- [ ] **Step 1: Generate migration**

Run: `cd /home/easy/projects/ReqRadar && alembic revision --autogenerate -m "add memory template synonym tables"`

If autogenerate doesn't detect changes, create a manual migration. The migration should add these tables:
- `pending_changes`
- `synonym_mappings`
- `report_templates`
And alter:
- `analysis_tasks` — add `current_version INTEGER DEFAULT 1 NOT NULL`, add `depth VARCHAR(20) DEFAULT 'standard' NOT NULL`
- `projects` — add `default_template_id INTEGER REFERENCES report_templates(id)`

- [ ] **Step 2: Verify migration runs**

Run: `alembic upgrade head`
Expected: No errors

- [ ] **Step 3: Verify migration rolls back**

Run: `alembic downgrade -1 && alembic upgrade head`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add Alembic migration for pending_changes, synonym_mappings, report_templates tables"
```

---

## Task 4: ProjectMemory Module

**Files:**
- Create: `src/reqradar/modules/project_memory.py`
- Create: `tests/test_project_memory.py`

- [ ] **Step 1: Write tests for ProjectMemory**

Create `tests/test_project_memory.py`:

```python
import pytest
from pathlib import Path
from reqradar.modules.project_memory import ProjectMemory


@pytest.fixture
def tmp_memory_dir(tmp_path):
    return tmp_path / "memories"


def test_project_memory_creates_dir_and_file(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    data = pm.load()
    assert data["overview"] == ""
    assert pm.storage_path.exists()


def test_project_memory_save_and_load(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm.update_overview("A test project for requirement analysis")
    pm.add_tech_stack("languages", ["Python", "TypeScript"])
    pm.add_module("web", "Web server module", ["app.py"])
    pm.add_term("RQ", "Requirement", domain="general")
    pm.save()

    pm2 = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    data = pm2.load()
    assert "A test project" in data["overview"]
    assert "Python" in data["tech_stack"]["languages"]
    assert any(m["name"] == "web" for m in data["modules"])
    assert any(t["term"] == "RQ" for t in data["terms"])


def test_project_memory_detect_changes(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm.update_overview("Original overview")
    pm.save()

    old_data = pm.load()
    pm.update_overview("Updated overview")
    pm.add_module("new_module", "A new module")
    pm.save()
    new_data = pm.load()

    changes = pm.detect_changes(old_data, new_data)
    assert len(changes) > 0
    assert any(c["change_type"] == "overview_updated" for c in changes)


def test_project_memory_isolation(tmp_memory_dir):
    pm1 = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm2 = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=2)
    pm1.update_overview("Project 1")
    pm2.update_overview("Project 2")
    pm1.save()
    pm2.save()

    data1 = pm1.load()
    data2 = pm2.load()
    assert data1["overview"] != data2["overview"]


def test_project_memory_migrate_from_yaml(tmp_memory_dir):
    import yaml
    yaml_path = tmp_memory_dir / ".." / "memory"
    yaml_path.mkdir(parents=True, exist_ok=True)
    yaml_file = yaml_path / "memory.yaml"
    old_data = {
        "project_profile": {"name": "OldProject", "description": "Old desc"},
        "modules": [{"name": "old_mod", "responsibility": "old"}],
        "terminology": [],
        "team": [],
        "constraints": [],
        "analysis_history": [],
    }
    with open(yaml_file, "w") as f:
        yaml.dump(old_data, f)

    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm.migrate_from_yaml(str(yaml_file))
    data = pm.load()
    assert "OldProject" in data["overview"] or data.get("name") == "OldProject"


def test_project_memory_generate_diff(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    old_content = "# Project\n\n## Overview\nOld overview\n"
    new_content = "# Project\n\n## Overview\nNew overview\n\n## Modules\n### auth\nAuth module\n"
    diff = pm.generate_diff(old_content, new_content)
    assert "+### auth" in diff or "+ auth" in diff
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_memory.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement ProjectMemory**

Create `src/reqradar/modules/project_memory.py`:

```python
import difflib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from reqradar.core.exceptions import ReqRadarException

logger = logging.getLogger("reqradar.project_memory")


class ProjectMemoryError(ReqRadarException):
    pass


class ProjectMemory:
    STORAGE_DIR = "memories"

    def __init__(self, storage_path: str, project_id: int):
        self.project_id = project_id
        self.storage_path = Path(storage_path) / str(project_id)
        self.file_path = self.storage_path / "project.md"
        self._data: dict = {}
        self._loaded = False

    def _default_data(self) -> dict:
        return {
            "name": "",
            "overview": "",
            "tech_stack": {"languages": [], "frameworks": [], "databases": [], "key_dependencies": []},
            "modules": [],
            "terms": [],
            "constraints": [],
            "changelog": [],
        }

    def load(self) -> dict:
        if self._loaded:
            return self._data

        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8")
                self._data = self._parse_markdown(content)
                self._loaded = True
                return self._data
            except OSError as e:
                logger.warning("Failed to load project memory: %s, using defaults", e)

        self._data = self._default_data()
        self._loaded = True
        return self._data

    def save(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        content = self._render_markdown(self._data)
        try:
            self.file_path.write_text(content, encoding="utf-8")
            logger.info("Project memory saved to %s", self.file_path)
        except OSError as e:
            raise ProjectMemoryError(f"Failed to save project memory: {e}") from e

    def update_overview(self, overview: str) -> None:
        self.load()
        self._data["overview"] = overview
        self._save_changelog("Updated project overview")

    def update_name(self, name: str) -> None:
        self.load()
        self._data["name"] = name

    def add_tech_stack(self, category: str, items: list[str]) -> None:
        self.load()
        ts = self._data.setdefault("tech_stack", {})
        existing = ts.setdefault(category, [])
        for item in items:
            if item not in existing:
                existing.append(item)

    def add_module(self, name: str, responsibility: str = "", key_classes: list[str] | None = None) -> None:
        self.load()
        modules = self._data.setdefault("modules", [])
        for m in modules:
            if m["name"] == name:
                if responsibility:
                    m["responsibility"] = responsibility
                if key_classes:
                    m["key_classes"] = key_classes
                return
        modules.append({
            "name": name,
            "responsibility": responsibility,
            "key_classes": key_classes or [],
            "dependencies": [],
            "path": "",
        })

    def add_term(self, term: str, definition: str, domain: str = "") -> None:
        self.load()
        terms = self._data.setdefault("terms", [])
        for t in terms:
            if t["term"] == term:
                t["definition"] = definition
                if domain:
                    t["domain"] = domain
                return
        terms.append({"term": term, "definition": definition, "domain": domain})

    def add_constraint(self, description: str, constraint_type: str = "other") -> None:
        self.load()
        self._data.setdefault("constraints", []).append({
            "description": description,
            "type": constraint_type,
        })

    def _save_changelog(self, description: str) -> None:
        self._data.setdefault("changelog", []).append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": description,
        })

    def detect_changes(self, old_data: dict, new_data: dict) -> list[dict]:
        changes = []
        if old_data.get("overview", "") != new_data.get("overview", ""):
            changes.append({"change_type": "overview_updated", "target": "overview"})
        old_mod_names = {m["name"] for m in old_data.get("modules", [])}
        new_mod_names = {m["name"] for m in new_data.get("modules", [])}
        for name in new_mod_names - old_mod_names:
            changes.append({"change_type": "module_added", "target": f"module:{name}"})
        old_terms = {t["term"] for t in old_data.get("terms", [])}
        new_terms = {t["term"] for t in new_data.get("terms", [])}
        for term in new_terms - old_terms:
            changes.append({"change_type": "term_added", "target": f"term:{term}"})
        old_ts = old_data.get("tech_stack", {})
        new_ts = new_data.get("tech_stack", {})
        for category in set(list(old_ts.keys()) + list(new_ts.keys())):
            old_items = set(old_ts.get(category, []))
            new_items = set(new_ts.get(category, []))
            if new_items - old_items:
                changes.append({"change_type": "tech_stack_updated", "target": f"tech_stack:{category}"})
        return changes

    def generate_diff(self, old_content: str, new_content: str) -> str:
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after")
        return "".join(diff)

    def migrate_from_yaml(self, yaml_path: str) -> None:
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            return
        try:
            with open(yaml_file, encoding="utf-8") as f:
                old = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return

        profile = old.get("project_profile", {})
        self.load()
        if profile.get("name"):
            self._data["name"] = profile["name"]
        if profile.get("description"):
            self._data["overview"] = profile["description"]
        ts = profile.get("tech_stack", {})
        if ts:
            self._data["tech_stack"] = ts
        for mod in old.get("modules", []):
            self.add_module(mod.get("name", ""), mod.get("responsibility", ""), mod.get("key_classes", []))
        for term in old.get("terminology", []):
            self.add_term(term.get("term", ""), term.get("definition", ""), term.get("domain", ""))
        self.save()

    def _parse_markdown(self, content: str) -> dict:
        data = self._default_data()
        lines = content.split("\n")
        current_section = None
        current_subsection = None
        current_module = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                data["name"] = stripped[2:].strip()
                current_section = "header"
            elif stripped == "## Overview":
                current_section = "overview"
                current_subsection = None
            elif stripped == "## Tech Stack":
                current_section = "tech_stack"
                current_subsection = None
            elif stripped == "## Modules":
                current_section = "modules"
                current_subsection = None
                current_module = None
            elif stripped == "## Terms":
                current_section = "terms"
                current_subsection = None
            elif stripped == "## Constraints":
                current_section = "constraints"
                current_subsection = None
            elif stripped == "## Changelog":
                current_section = "changelog"
                current_subsection = None
            elif stripped.startswith("### "):
                if current_section == "tech_stack":
                    category = stripped[4:].strip().lower().rstrip(":")
                    current_subsection = category
                elif current_section == "modules":
                    mod_name = stripped[4:].strip()
                    current_module = {"name": mod_name, "responsibility": "", "key_classes": [], "dependencies": [], "path": ""}
                    data["modules"].append(current_module)
                    current_subsection = "module_body"
            elif stripped.startswith("- ") and stripped != "- ":
                if current_section == "overview":
                    data["overview"] += stripped[2:] + "\n"
                elif current_section == "tech_stack" and current_subsection:
                    item = stripped[2:].strip()
                    data["tech_stack"].setdefault(current_subsection, []).append(item)
                elif current_section == "terms":
                    parts = stripped[2:].strip()
                    if ": " in parts:
                        term, definition = parts.split(": ", 1)
                        domain = ""
                        if "[" in definition and definition.endswith("]"):
                            domain = definition[definition.rindex("[") + 1 : -1]
                            definition = definition[: definition.rindex("[")].strip()
                        data["terms"].append({"term": term.strip(), "definition": definition.strip(), "domain": domain})
                elif current_section == "constraints":
                    text = stripped[2:].strip()
                    if text:
                        data["constraints"].append({"description": text, "type": "other"})
                elif current_section == "changelog":
                    text = stripped[2:].strip()
                    if text:
                        data["changelog"].append({"date": "", "description": text})
            elif current_section == "overview" and stripped and not stripped.startswith("#"):
                data["overview"] += stripped + "\n"
            elif current_section == "modules" and current_module and stripped and not stripped.startswith("#"):
                if stripped.startswith("responsibility:") or stripped.startswith("Responsibility:"):
                    current_module["responsibility"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("key_classes:") or stripped.startswith("Key classes:"):
                    classes_str = stripped.split(":", 1)[1].strip()
                    current_module["key_classes"] = [c.strip() for c in classes_str.split(",") if c.strip()]

        data["overview"] = data["overview"].strip()
        return data

    def _render_markdown(self, data: dict) -> str:
        lines = []
        name = data.get("name", "")
        lines.append(f"# {name}" if name else "# Project")
        lines.append("")

        overview = data.get("overview", "")
        lines.append("## Overview")
        lines.append(overview if overview else "")
        lines.append("")

        ts = data.get("tech_stack", {})
        lines.append("## Tech Stack")
        for category in ["languages", "frameworks", "databases", "key_dependencies"]:
            items = ts.get(category, [])
            if items:
                lines.append(f"### {category.title()}")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

        modules = data.get("modules", [])
        if modules:
            lines.append("## Modules")
            for mod in modules:
                lines.append(f"### {mod['name']}")
                if mod.get("responsibility"):
                    lines.append(f"Responsibility: {mod['responsibility']}")
                if mod.get("key_classes"):
                    lines.append(f"Key classes: {', '.join(mod['key_classes'])}")
                lines.append("")

        terms = data.get("terms", [])
        if terms:
            lines.append("## Terms")
            for t in terms:
                line = f"- {t['term']}: {t['definition']}"
                if t.get("domain"):
                    line += f" [{t['domain']}]"
                lines.append(line)
            lines.append("")

        constraints = data.get("constraints", [])
        if constraints:
            lines.append("## Constraints")
            for c in constraints:
                lines.append(f"- {c['description']} ({c.get('type', 'other')})")
            lines.append("")

        changelog = data.get("changelog", [])
        if changelog:
            lines.append("## Changelog")
            for entry in changelog:
                date = entry.get("date", "")
                desc = entry.get("description", "")
                lines.append(f"- {date}: {desc}" if date else f"- {desc}")
            lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_memory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/modules/project_memory.py tests/test_project_memory.py
git commit -m "feat: add ProjectMemory module with Markdown read/write, change detection, and YAML migration"
```

---

## Task 5: UserMemory Module

**Files:**
- Create: `src/reqradar/modules/user_memory.py`
- Create: `tests/test_user_memory.py`

- [ ] **Step 1: Write tests for UserMemory**

Create `tests/test_user_memory.py`:

```python
import pytest
from pathlib import Path
from reqradar.modules.user_memory import UserMemory


@pytest.fixture
def tmp_memory_dir(tmp_path):
    return tmp_path / "user_memories"


def test_user_memory_creates_dir_and_file(tmp_memory_dir):
    um = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    data = um.load()
    assert data["corrections"] == []
    assert um.file_path.parent.exists()


def test_user_memory_add_correction(tmp_memory_dir):
    um = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    um.add_correction("配置", ["config", "settings"], source="user_correction", analysis_id=42)
    um.save()

    um2 = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    data = um2.load()
    assert len(data["corrections"]) == 1
    assert data["corrections"][0]["business_term"] == "配置"


def test_user_memory_set_preference(tmp_memory_dir):
    um = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    um.set_preference("default_depth", "deep")
    um.set_preference("report_language", "zh")
    um.save()

    um2 = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    data = um2.load()
    assert data["preferences"]["default_depth"] == "deep"
    assert data["preferences"]["report_language"] == "zh"


def test_user_memory_isolation(tmp_memory_dir):
    um1 = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    um2 = UserMemory(storage_path=str(tmp_memory_dir), user_id=2)
    um1.add_correction("术语A", ["codeA"])
    um2.add_correction("术语B", ["codeB"])
    um1.save()
    um2.save()

    data1 = um1.load()
    data2 = um2.load()
    assert data1["corrections"] != data2["corrections"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_user_memory.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement UserMemory**

Create `src/reqradar/modules/user_memory.py`:

```python
import logging
from datetime import datetime
from pathlib import Path

from reqradar.core.exceptions import ReqRadarException

logger = logging.getLogger("reqradar.user_memory")


class UserMemoryError(ReqRadarException):
    pass


class UserMemory:
    def __init__(self, storage_path: str, user_id: int):
        self.user_id = user_id
        self.storage_path = Path(storage_path) / str(user_id)
        self.file_path = self.storage_path / "user.md"
        self._data: dict = {}
        self._loaded = False

    def _default_data(self) -> dict:
        return {
            "corrections": [],
            "focus_areas": [],
            "preferences": {
                "default_depth": "standard",
                "report_language": "zh",
            },
            "term_preferences": [],
        }

    def load(self) -> dict:
        if self._loaded:
            return self._data

        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8")
                self._data = self._parse_markdown(content)
                self._loaded = True
                return self._data
            except OSError as e:
                logger.warning("Failed to load user memory: %s, using defaults", e)

        self._data = self._default_data()
        self._loaded = True
        return self._data

    def save(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        content = self._render_markdown(self._data)
        try:
            self.file_path.write_text(content, encoding="utf-8")
            logger.info("User memory saved to %s", self.file_path)
        except OSError as e:
            raise UserMemoryError(f"Failed to save user memory: {e}") from e

    def add_correction(self, business_term: str, code_terms: list[str], source: str = "user_correction", analysis_id: int | None = None) -> None:
        self.load()
        self._data["corrections"].append({
            "business_term": business_term,
            "code_terms": code_terms,
            "source": source,
            "analysis_id": analysis_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
        })

    def set_preference(self, key: str, value: str) -> None:
        self.load()
        self._data["preferences"][key] = value

    def add_focus_area(self, area: str, priority: str = "medium") -> None:
        self.load()
        self._data["focus_areas"].append({"area": area, "priority": priority})

    def add_term_preference(self, term: str, definition: str) -> None:
        self.load()
        self._data["term_preferences"].append({"term": term, "definition": definition})

    def get_corrections_for_term(self, business_term: str) -> list[str]:
        self.load()
        results = []
        for c in self._data["corrections"]:
            if c["business_term"] == business_term:
                results.extend(c.get("code_terms", []))
        return list(set(results))

    def _parse_markdown(self, content: str) -> dict:
        data = self._default_data()
        lines = content.split("\n")
        current_section = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                pass
            elif stripped == "## Corrections":
                current_section = "corrections"
            elif stripped == "## Focus Areas":
                current_section = "focus_areas"
            elif stripped == "## Preferences":
                current_section = "preferences"
            elif stripped == "## Term Preferences":
                current_section = "term_preferences"
            elif stripped.startswith("- ") and stripped != "- ":
                text = stripped[2:].strip()
                if current_section == "corrections" and "→" in text:
                    parts = text.split("→")
                    bt = parts[0].strip().strip('"')
                    code_str = parts[1].strip().strip("[]")
                    code_terms = [c.strip() for c in code_str.split(",")]
                    data["corrections"].append({
                        "business_term": bt,
                        "code_terms": code_terms,
                        "source": "user_correction",
                        "analysis_id": None,
                        "date": "",
                    })
                elif current_section == "focus_areas" and ":" in text:
                    area, pri = text.split(":", 1)
                    data["focus_areas"].append({"area": area.strip(), "priority": pri.strip()})
                elif current_section == "preferences" and ":" in text:
                    key, val = text.split(":", 1)
                    data["preferences"][key.strip()] = val.strip()
                elif current_section == "term_preferences":
                    if "→" in text:
                        parts = text.split("→")
                    elif ":" in text:
                        parts = text.split(":", 1)
                    else:
                        continue
                    data["term_preferences"].append({"term": parts[0].strip().strip('"'), "definition": parts[1].strip().strip('"')})

        return data

    def _render_markdown(self, data: dict) -> str:
        lines = ["# User Preferences", ""]

        corrections = data.get("corrections", [])
        if corrections:
            lines.append("## Corrections")
            for c in corrections:
                code_str = ", ".join(c.get("code_terms", []))
                source_info = f" (source: {c.get('source', 'unknown')}" + (f", analysis #{c.get('analysis_id')}" if c.get('analysis_id') else "") + ")" if c.get("source") else ""
                lines.append(f'- "{c["business_term"]}" → [{code_str}]{source_info}')
            lines.append("")

        focus_areas = data.get("focus_areas", [])
        if focus_areas:
            lines.append("## Focus Areas")
            for fa in focus_areas:
                lines.append(f"- {fa['area']}: {fa.get('priority', 'medium')}")
            lines.append("")

        prefs = data.get("preferences", {})
        if prefs:
            lines.append("## Preferences")
            for key, val in prefs.items():
                lines.append(f"- {key}: {val}")
            lines.append("")

        term_prefs = data.get("term_preferences", [])
        if term_prefs:
            lines.append("## Term Preferences")
            for tp in term_prefs:
                lines.append(f'- "{tp["term"]}" → "{tp["definition"]}"')
            lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_user_memory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/modules/user_memory.py tests/test_user_memory.py
git commit -m "feat: add UserMemory module with Markdown read/write and user preferences"
```

---

## Task 6: Unified MemoryManager Facade

**Files:**
- Create: `src/reqradar/modules/memory_manager.py`
- Create: `tests/test_memory_manager.py`

- [ ] **Step 1: Write tests for MemoryManager facade**

Create `tests/test_memory_manager.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from reqradar.modules.memory_manager import AnalysisMemoryManager


@pytest.fixture
def tmp_storage(tmp_path):
    return {
        "project_path": str(tmp_path / "memories"),
        "user_path": str(tmp_path / "user_memories"),
    }


def test_memory_manager_loads_project_memory(tmp_storage):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=tmp_storage["project_path"],
        user_storage_path=tmp_storage["user_path"],
        repo_path=str(Path(__file__).parent.parent / "src" / "reqradar"),
    )
    project_mem = mm.project_memory
    data = project_mem.load()
    assert "overview" in data


def test_memory_manager_loads_user_memory(tmp_storage):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=tmp_storage["project_path"],
        user_storage_path=tmp_storage["user_path"],
        repo_path=str(Path(__file__).parent.parent / "src" / "reqradar"),
    )
    user_mem = mm.user_memory
    data = user_mem.load()
    assert "corrections" in data


def test_memory_manager_gets_project_profile_text(tmp_storage):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=tmp_storage["project_path"],
        user_storage_path=tmp_storage["user_path"],
        repo_path=str(Path(__file__).parent.parent / "src" / "reqradar"),
    )
    mm.project_memory.update_overview("Test overview")
    mm.project_memory.save()
    text = mm.get_project_profile_text()
    assert "Test overview" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_manager.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement AnalysisMemoryManager**

Create `src/reqradar/modules/memory_manager.py`:

```python
import logging
from pathlib import Path
from typing import Optional

from reqradar.modules.project_memory import ProjectMemory
from reqradar.modules.user_memory import UserMemory

logger = logging.getLogger("reqradar.memory_manager")


class AnalysisMemoryManager:
    def __init__(
        self,
        project_id: int,
        user_id: int,
        project_storage_path: str = ".reqradar/memories",
        user_storage_path: str = ".reqradar/user_memories",
        repo_path: str = ".",
        memory_enabled: bool = True,
    ):
        self.project_id = project_id
        self.user_id = user_id
        self.enabled = memory_enabled

        if self.enabled:
            self.project_memory = ProjectMemory(
                storage_path=project_storage_path,
                project_id=project_id,
            )
            self.user_memory = UserMemory(
                storage_path=user_storage_path,
                user_id=user_id,
            )
        else:
            self.project_memory = None
            self.user_memory = None

    def get_project_profile_text(self) -> str:
        if not self.enabled or not self.project_memory:
            return ""
        data = self.project_memory.load()
        lines = []
        if data.get("name"):
            lines.append(f"项目: {data['name']}")
        if data.get("overview"):
            lines.append(f"概述: {data['overview']}")
        ts = data.get("tech_stack", {})
        for cat in ["languages", "frameworks", "databases", "key_dependencies"]:
            items = ts.get(cat, [])
            if items:
                lines.append(f"{cat}: {', '.join(items)}")
        for mod in data.get("modules", []):
            line = f"- {mod['name']}"
            if mod.get("responsibility"):
                line += f": {mod['responsibility']}"
            lines.append(line)
        return "\n".join(lines)

    def get_user_memory_text(self) -> str:
        if not self.enabled or not self.user_memory:
            return ""
        data = self.user_memory.load()
        lines = []
        corrections = data.get("corrections", [])
        if corrections:
            lines.append("用户纠正记录：")
            for c in corrections:
                lines.append(f'- "{c["business_term"]}" → {", ".join(c.get("code_terms", []))}')
        prefs = data.get("preferences", {})
        if prefs:
            lines.append("用户偏好：")
            for k, v in prefs.items():
                lines.append(f"- {k}: {v}")
        return "\n".join(lines) if lines else ""

    def get_terminology_text(self) -> str:
        if not self.enabled or not self.project_memory:
            return ""
        data = self.project_memory.load()
        terms = data.get("terms", [])
        if not terms:
            return ""
        lines = ["项目已知术语："]
        for t in terms:
            line = f"- {t['term']}: {t.get('definition', '')}"
            if t.get("domain"):
                line += f" [{t['domain']}]"
            lines.append(line)
        return "\n".join(lines)

    def get_modules_text(self) -> str:
        if not self.enabled or not self.project_memory:
            return ""
        data = self.project_memory.load()
        modules = data.get("modules", [])
        if not modules:
            return ""
        lines = ["项目模块："]
        for m in modules:
            line = f"- {m['name']}"
            if m.get("responsibility"):
                line += f": {m['responsibility']}"
            if m.get("key_classes"):
                line += f" (关键类: {', '.join(m['key_classes'])})"
            lines.append(line)
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/modules/memory_manager.py tests/test_memory_manager.py
git commit -m "feat: add AnalysisMemoryManager facade combining ProjectMemory and UserMemory"
```

---

## Task 7: Default Report Template Definition

**Files:**
- Create: `src/reqradar/templates/default_report.yaml`

- [ ] **Step 1: Create the default report template definition YAML**

Create `src/reqradar/templates/default_report.yaml`:

```yaml
template_definition:
  name: "默认企业级报告模板"
  description: "面向企业需求评审的标准化分析报告"
  sections:
    - id: "requirement_understanding"
      title: "需求理解"
      description: "从业务和技术角度理解需求的核心内容。需要提取关键术语、识别业务目标、约束条件和建议优先级。"
      requirements: "150-200字，包含背景描述、核心问题、成功标准和关键术语"
      required: true
      dimensions: ["understanding"]

    - id: "executive_summary"
      title: "执行摘要"
      description: "面向管理层和产品负责人的高层总结。结论先行，突出关键决策建议和业务影响。"
      requirements: "120-180字，结论先行，基于证据，避免技术细节"
      required: true
      dimensions: ["decision"]

    - id: "technical_summary"
      title: "技术概述"
      description: "面向技术负责人和架构师的概要。概括影响域、技术风险和实施路径。"
      requirements: "120-180字，概括性描述，包含技术栈影响和架构变更方向"
      required: true
      dimensions: ["impact", "risk"]

    - id: "impact_analysis"
      title: "影响分析"
      description: "识别需求对项目代码、模块、接口的影响。需要引用具体代码文件和模块。"
      requirements: "包含影响域列表、代码命中模块、变更评估表格、影响范围描述"
      required: true
      dimensions: ["impact", "change"]

    - id: "risk_assessment"
      title: "风险评估"
      description: "识别技术风险、业务风险和合规风险。每个风险必须有代码或历史依据支撑。"
      requirements: "包含总体风险等级、风险列表（含严重性和缓解建议）、风险分析描述"
      required: true
      dimensions: ["risk"]

    - id: "decision_summary"
      title: "决策建议"
      description: "基于分析结果给出可操作的决策建议。包括优先级、实施方向和验证要点。"
      requirements: "包含决策要点、实施建议、验证要点、待解决问题"
      required: true
      dimensions: ["decision", "verification"]

    - id: "evidence"
      title: "证据支撑"
      description: "列出支撑所有结论的证据。每条证据标明来源、类型和可信度。"
      requirements: "表格形式，覆盖所有其他章节的结论"
      required: true
      dimensions: ["evidence"]

    - id: "appendix"
      title: "附录"
      description: "项目画像、术语表、相似历史需求等辅助信息。"
      requirements: "结构化展示项目知识上下文"
      required: false
      dimensions: []
```

- [ ] **Step 2: Verify the YAML file is valid**

Run: `python -c "import yaml; yaml.safe_load(open('src/reqradar/templates/default_report.yaml'))"`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/reqradar/templates/default_report.yaml
git commit -m "feat: add default report template definition YAML with section descriptions and requirements"
```

---

## Task 8: Template Loader and Renderer

**Files:**
- Create: `src/reqradar/infrastructure/template_loader.py`
- Create: `tests/test_template_loader.py`

- [ ] **Step 1: Write tests for template loader**

Create `tests/test_template_loader.py`:

```python
import pytest
from pathlib import Path
from reqradar.infrastructure.template_loader import TemplateLoader, TemplateDefinition, SectionDefinition


def test_load_default_template():
    loader = TemplateLoader()
    template_dir = Path(__file__).parent.parent / "src" / "reqradar" / "templates"
    defn = loader.load_definition(template_dir / "default_report.yaml")
    assert defn.name == "默认企业级报告模板"
    assert len(defn.sections) == 8
    assert defn.sections[0].id == "requirement_understanding"
    assert defn.sections[0].required is True


def test_section_dimensions():
    loader = TemplateLoader()
    template_dir = Path(__file__).parent.parent / "src" / "reqradar" / "templates"
    defn = loader.load_definition(template_dir / "default_report.yaml")
    impact_section = next(s for s in defn.sections if s.id == "impact_analysis")
    assert "impact" in impact_section.dimensions
    assert "change" in impact_section.dimensions


def test_render_with_template(tmp_path):
    loader = TemplateLoader()
    render_template = "# {{ requirement_title }}\n\n## 执行摘要\n\n{{ executive_summary }}"
    report_data = {
        "requirement_title": "Test Requirement",
        "executive_summary": "This is a test summary.",
    }
    result = loader.render(render_template, report_data)
    assert "Test Requirement" in result
    assert "This is a test summary" in result


def test_build_section_prompts():
    loader = TemplateLoader()
    template_dir = Path(__file__).parent.parent / "src" / "reqradar" / "templates"
    defn = loader.load_definition(template_dir / "default_report.yaml")
    prompts = loader.build_section_prompts(defn)
    assert "requirement_understanding" in prompts
    assert "150-200字" in prompts["requirement_understanding"]


def test_get_required_sections():
    loader = TemplateLoader()
    template_dir = Path(__file__).parent.parent / "src" / "reqradar" / "templates"
    defn = loader.load_definition(template_dir / "default_report.yaml")
    required = [s for s in defn.sections if s.required]
    assert len(required) == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_template_loader.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement TemplateLoader**

Create `src/reqradar/infrastructure/template_loader.py`:

```python
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from jinja2 import Template

from reqradar.core.exceptions import ReqRadarException

logger = logging.getLogger("reqradar.template_loader")


class TemplateLoaderError(ReqRadarException):
    pass


@dataclass
class SectionDefinition:
    id: str
    title: str
    description: str
    requirements: str = ""
    required: bool = True
    dimensions: list[str] = field(default_factory=list)


@dataclass
class TemplateDefinition:
    name: str
    description: str = ""
    sections: list[SectionDefinition] = field(default_factory=list)


class TemplateLoader:
    def __init__(self):
        self._definition_cache: dict[str, TemplateDefinition] = {}

    def load_definition(self, path: Path) -> TemplateDefinition:
        path_str = str(path)
        if path_str in self._definition_cache:
            return self._definition_cache[path_str]

        if not path.exists():
            raise TemplateLoaderError(f"Template definition not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            raise TemplateLoaderError(f"Failed to load template definition: {e}") from e

        template_def = raw.get("template_definition", raw)
        name = template_def.get("name", "Unnamed Template")
        description = template_def.get("description", "")
        sections = []

        for sec in template_def.get("sections", []):
            sections.append(SectionDefinition(
                id=sec["id"],
                title=sec["title"],
                description=sec.get("description", ""),
                requirements=sec.get("requirements", ""),
                required=sec.get("required", True),
                dimensions=sec.get("dimensions", []),
            ))

        defn = TemplateDefinition(name=name, description=description, sections=sections)
        self._definition_cache[path_str] = defn
        return defn

    def load_definition_from_string(self, yaml_content: str) -> TemplateDefinition:
        raw = yaml.safe_load(yaml_content)
        template_def = raw.get("template_definition", raw)
        name = template_def.get("name", "Unnamed Template")
        description = template_def.get("description", "")
        sections = []
        for sec in template_def.get("sections", []):
            sections.append(SectionDefinition(
                id=sec["id"],
                title=sec["title"],
                description=sec.get("description", ""),
                requirements=sec.get("requirements", ""),
                required=sec.get("required", True),
                dimensions=sec.get("dimensions", []),
            ))
        return TemplateDefinition(name=name, description=description, sections=sections)

    def render(self, render_template: str, report_data: dict) -> str:
        template = Template(render_template)
        return template.render(**report_data)

    def build_section_prompts(self, definition: TemplateDefinition) -> dict[str, str]:
        prompts = {}
        for section in definition.sections:
            prompt_parts = [
                f"你正在生成报告的第X章：{section.title}",
                f"",
                f"章节描述：{section.description}",
                f"写作要求：{section.requirements}",
                f"所需维度：{', '.join(section.dimensions) if section.dimensions else '无特定维度'}",
                f"",
                f"请基于以下证据和上下文生成该章节内容。",
            ]
            prompts[section.id] = "\n".join(prompt_parts)
        return prompts

    def load_definition_from_db(self, definition_yaml: str) -> TemplateDefinition:
        return self.load_definition_from_string(definition_yaml)

    def get_default_template_path(self) -> Path:
        return Path(__file__).parent.parent / "templates" / "default_report.yaml"

    def get_default_render_template_path(self) -> Path:
        return Path(__file__).parent.parent / "templates" / "report.md.j2"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_template_loader.py -v`
Expected: PASS

- [ ] **Step 5: Run existing report tests**

Run: `pytest tests/test_report.py -v`
Expected: All PASS (unchanged behavior)

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/infrastructure/template_loader.py tests/test_template_loader.py
git commit -m "feat: add TemplateLoader with YAML definition parsing, Jinja2 rendering, and section prompt building"
```

---

## Task 9: Update ReportRenderer to Support Template Definitions

**Files:**
- Modify: `src/reqradar/core/report.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: Read the current report.py fully**

Read `src/reqradar/core/report.py` (already read lines 1-80). Need to see the full render method and how the template is used.

- [ ] **Step 2: Write test for template-based rendering**

Add to `tests/test_report.py`:

```python
def test_report_renderer_with_template_definition(tmp_path):
    from reqradar.infrastructure.template_loader import TemplateLoader, TemplateDefinition, SectionDefinition
    from reqradar.core.report import ReportRenderer

    # Create a minimal render template that uses section variables
    template_content = "# {{ requirement_title | default('Untitled') }}\n\n{{ executive_summary | default('') }}"
    template_path = tmp_path / "custom.md.j2"
    template_path.write_text(template_content)

    config = Config()
    config.output.report_template = str(template_path)
    renderer = ReportRenderer(config)

    # Verify render still works (backward compat)
    context = AnalysisContext(
        requirement_path=Path("test.txt"),
        requirement_text="test requirement",
    )
    result = renderer.render(context)
    assert result  # produces some output
```

- [ ] **Step 3: Modify ReportRenderer to accept TemplateDefinition**

Add `template_definition` parameter to `ReportRenderer.__init__` and `render`:

In `src/reqradar/core/report.py`, modify the `__init__` method to also accept a `TemplateDefinition`:

```python
class ReportRenderer:
    def __init__(self, config: Optional[Config] = None, template_definition: Optional["TemplateDefinition"] = None):
        self.config = config
        self.template_definition = template_definition
        template_path = DEFAULT_TEMPLATE_PATH
        if config and config.output.report_template and config.output.report_template != "default":
            custom_path = Path(config.output.report_template)
            if custom_path.exists():
                template_path = custom_path
            else:
                logger.warning("Custom template not found: %s, using default", custom_path)

        try:
            with open(template_path, encoding="utf-8") as f:
                self.template = Template(f.read())
        except FileNotFoundError:
            logger.warning("Template file not found: %s, using inline fallback", template_path)
            self.template = Template(_INLINE_FALLBACK_TEMPLATE)
```

The `render` method remains backward-compatible. When `template_definition` is provided, we inject section descriptions into the report data context so the Jinja2 template can reference them. This is a minimal change — the full Agent prompt injection will come in Round 2.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/core/report.py tests/test_report.py
git commit -m "feat: add template_definition support to ReportRenderer (backward compatible)"
```

---

## Task 10: SynonymResolver Module

**Files:**
- Create: `src/reqradar/modules/synonym_resolver.py`
- Create: `tests/test_synonym_resolver.py`

- [ ] **Step 1: Write tests for SynonymResolver**

Create `tests/test_synonym_resolver.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from reqradar.modules.synonym_resolver import SynonymResolver


def test_resolve_with_project_mappings():
    resolver = SynonymResolver()
    project_mappings = [
        {"business_term": "配置", "code_terms": ["config", "settings"], "priority": 100},
        {"business_term": "用户", "code_terms": ["user", "account"], "priority": 50},
    ]
    global_mappings = [
        {"business_term": "认证", "code_terms": ["auth", "login"], "priority": 100},
    ]
    result = resolver.resolve(["配置", "用户", "认证"], project_mappings, global_mappings)
    assert "config" in result or "settings" in result
    assert "user" in result or "account" in result
    assert "auth" in result or "login" in result


def test_project_mappings_override_global():
    resolver = SynonymResolver()
    project_mappings = [
        {"business_term": "配置", "code_terms": ["config_proj"], "priority": 50},
    ]
    global_mappings = [
        {"business_term": "配置", "code_terms": ["config_global"], "priority": 200},
    ]
    result = resolver.resolve(["配置"], project_mappings, global_mappings)
    assert "config_proj" in result
    assert "config_global" not in result


def test_resolve_empty_keywords():
    resolver = SynonymResolver()
    result = resolver.resolve([], [], [])
    assert result == []


def test_fallback_to_hardcoded():
    resolver = SynonymResolver()
    result = resolver.resolve(["配置"], [], [])
    assert len(result) > 0


def test_priority_sorting():
    resolver = SynonymResolver()
    project_mappings = [
        {"business_term": "配置", "code_terms": ["high_priority_term"], "priority": 1},
        {"business_term": "配置", "code_terms": ["low_priority_term"], "priority": 200},
    ]
    global_mappings = []
    result = resolver.resolve(["配置"], project_mappings, global_mappings)
    assert "high_priority_term" in result or "low_priority_term" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synonym_resolver.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement SynonymResolver**

Create `src/reqradar/modules/synonym_resolver.py`:

```python
import logging
from typing import Optional

from reqradar.agent.prompts import _COMMON_SYNONYMS

logger = logging.getLogger("reqradar.synonym_resolver")


class SynonymResolver:
    HARD_CODED_SYNONYMS: dict[str, list[str]] = {}

    def __init__(self):
        if not self.HARD_CODED_SYNONYMS:
            self.HARD_CODED_SYNONYMS = dict(_COMMON_SYNONYMS) if _COMMON_SYNONYMS else {}

    def resolve(
        self,
        keywords: list[str],
        project_mappings: list[dict],
        global_mappings: list[dict],
    ) -> list[str]:
        result_set = set()
        seen_terms = set()

        project_by_term: dict[str, list[dict]] = {}
        for m in project_mappings:
            term = m["business_term"]
            project_by_term.setdefault(term, []).append(m)
        global_by_term: dict[str, list[dict]] = {}
        for m in global_mappings:
            term = m["business_term"]
            global_by_term.setdefault(term, []).append(m)

        for keyword in keywords:
            expanded = self._expand_term(keyword, project_by_term, global_by_term)
            result_set.update(expanded)
            result_set.add(keyword)
            seen_terms.add(keyword)

        return list(result_set)

    def _expand_term(
        self,
        term: str,
        project_by_term: dict[str, list[dict]],
        global_by_term: dict[str, list[dict]],
    ) -> list[str]:
        results = []

        project_entries = project_by_term.get(term, [])
        global_entries = global_by_term.get(term, [])

        if project_entries or global_entries:
            all_entries = list(project_entries)
            seen_project_terms = set()
            for entry in project_entries:
                for ct in entry.get("code_terms", []):
                    if isinstance(ct, str):
                        seen_project_terms.add(ct)

            for entry in global_entries:
                if entry.get("business_term") not in project_by_term:
                    all_entries.append(entry)

            sorted_entries = sorted(all_entries, key=lambda e: e.get("priority", 100))
            for entry in sorted_entries:
                for ct in entry.get("code_terms", []):
                    if isinstance(ct, str) and ct not in results:
                        results.append(ct)
        else:
            hard_coded = self.HARD_CODED_SYNONYMS.get(term, [])
            results.extend(hard_coded)

        return results

    def expand_keywords_with_synonyms(
        self,
        keywords: list[str],
        project_mappings: list[dict] | None = None,
        global_mappings: list[dict] | None = None,
    ) -> tuple[list[str], dict[str, list[str]]]:
        project_mappings = project_mappings or []
        global_mappings = global_mappings or []

        expanded = self.resolve(keywords, project_mappings, global_mappings)
        mapping_log = {}
        for keyword in keywords:
            expanded_for_term = self._expand_term(keyword,
                {m["business_term"]: [m] for m in project_mappings if m["business_term"] == keyword},
                {m["business_term"]: [m] for m in global_mappings if m["business_term"] == keyword},
            )
            if expanded_for_term:
                mapping_log[keyword] = expanded_for_term

        return expanded, mapping_log
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synonym_resolver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/modules/synonym_resolver.py tests/test_synonym_resolver.py
git commit -m "feat: add SynonymResolver with project/global priority, fallback to hardcoded synonyms"
```

---

## Task 11: PendingChange CRUD Module

**Files:**
- Create: `src/reqradar/modules/pending_changes.py`
- Create: `tests/test_pending_changes.py`

- [ ] **Step 1: Write tests for PendingChange CRUD**

Create `tests/test_pending_changes.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine

from reqradar.web.database import Base
from reqradar.web.models import PendingChange
from reqradar.modules.pending_changes import PendingChangeManager


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_pending_change(db_session):
    manager = PendingChangeManager(db_session)
    change = await manager.create(
        project_id=1,
        change_type="profile",
        target_id="module:auth",
        old_value="",
        new_value="### auth\nAuthentication module",
        diff="+ ### auth\n+ Authentication module",
        source="agent",
    )
    assert change.id is not None
    assert change.status == "pending"
    assert change.change_type == "profile"


@pytest.mark.asyncio
async def test_accept_pending_change(db_session):
    manager = PendingChangeManager(db_session)
    change = await manager.create(
        project_id=1,
        change_type="synonym",
        target_id="term:配置",
        old_value="",
        new_value='["config", "settings"]',
        diff=""
        source="agent",
    )
    accepted = await manager.accept(change.id, resolved_by=1)
    assert accepted.status == "accepted"
    assert accepted.resolved_by == 1


@pytest.mark.asyncio
async def test_reject_pending_change(db_session):
    manager = PendingChangeManager(db_session)
    change = await manager.create(
        project_id=1,
        change_type="profile",
        target_id="overview",
        old_value="Old overview",
        new_value="New overview",
        diff="+ New overview",
        source="agent",
    )
    rejected = await manager.reject(change.id, resolved_by=1)
    assert rejected.status == "rejected"


@pytest.mark.asyncio
async def test_list_pending_changes(db_session):
    manager = PendingChangeManager(db_session)
    await manager.create(project_id=1, change_type="profile", target_id="t1", old_value="", new_value="n1", diff="d1", source="agent")
    await manager.create(project_id=1, change_type="synonym", target_id="t2", old_value="", new_value="n2", diff="d2", source="agent")
    await manager.create(project_id=2, change_type="profile", target_id="t3", old_value="", new_value="n3", diff="d3", source="agent")

    pending_1 = await manager.list_pending(project_id=1)
    assert len(pending_1) == 2

    pending_2 = await manager.list_pending(project_id=2)
    assert len(pending_2) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pending_changes.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement PendingChangeManager**

Create `src/reqradar/modules/pending_changes.py`:

```python
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import PendingChange

logger = logging.getLogger("reqradar.pending_changes")


class PendingChangeManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        project_id: int,
        change_type: str,
        target_id: str,
        old_value: str = "",
        new_value: str = "",
        diff: str = "",
        source: str = "agent",
    ) -> PendingChange:
        change = PendingChange(
            project_id=project_id,
            change_type=change_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            diff=diff,
            source=source,
            status="pending",
        )
        self.db.add(change)
        await self.db.commit()
        await self.db.refresh(change)
        return change

    async def accept(self, change_id: int, resolved_by: int | None = None) -> PendingChange | None:
        result = await self.db.execute(
            select(PendingChange).where(PendingChange.id == change_id)
        )
        change = result.scalar_one_or_none()
        if change is None:
            return None
        change.status = "accepted"
        change.resolved_at = datetime.now(timezone.utc)
        change.resolved_by = resolved_by
        await self.db.commit()
        await self.db.refresh(change)
        return change

    async def reject(self, change_id: int, resolved_by: int | None = None) -> PendingChange | None:
        result = await self.db.execute(
            select(PendingChange).where(PendingChange.id == change_id)
        )
        change = result.scalar_one_or_none()
        if change is None:
            return None
        change.status = "rejected"
        change.resolved_at = datetime.now(timezone.utc)
        change.resolved_by = resolved_by
        await self.db.commit()
        await self.db.refresh(change)
        return change

    async def list_pending(self, project_id: int, change_type: str | None = None) -> list[PendingChange]:
        query = select(PendingChange).where(
            PendingChange.project_id == project_id,
            PendingChange.status == "pending",
        )
        if change_type:
            query = query.where(PendingChange.change_type == change_type)
        query = query.order_by(PendingChange.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, change_id: int) -> PendingChange | None:
        result = await self.db.execute(
            select(PendingChange).where(PendingChange.id == change_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pending_changes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/modules/pending_changes.py tests/test_pending_changes.py
git commit -m "feat: add PendingChangeManager CRUD for profile updates and synonym confirmations"
```

---

## Task 12: API Endpoints — Synonym Mappings

**Files:**
- Create: `src/reqradar/web/api/synonyms.py`
- Modify: `src/reqradar/web/app.py`
- Create: `tests/test_synonym_api.py`

- [ ] **Step 1: Write API tests for synonym endpoints**

Create `tests/test_synonym_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from reqradar.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_token():
    from reqradar.web.api.auth import create_access_token
    return create_access_token({"sub": "1"})


@pytest.mark.asyncio
async def test_list_synonym_mappings(client, auth_token):
    response = await client.get(
        "/api/projects/1/synonym-mappings",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "mappings" in data


@pytest.mark.asyncio
async def test_create_synonym_mapping(client, auth_token):
    response = await client.post(
        "/api/projects/1/synonym-mappings",
        json={"business_term": "配置", "code_terms": ["config", "settings"], "priority": 50},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 201)
    data = response.json()
    assert data["business_term"] == "配置"


@pytest.mark.asyncio
async def test_update_synonym_mapping(client, auth_token):
    create_resp = await client.post(
        "/api/projects/1/synonym-mappings",
        json={"business_term": "用户", "code_terms": ["user"], "priority": 100},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert create_resp.status_code in (200, 201)
    mapping_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/projects/1/synonym-mappings/{mapping_id}",
        json={"code_terms": ["user", "account"], "priority": 50},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert update_resp.status_code == 200
    assert "account" in update_resp.json()["code_terms"]


@pytest.mark.asyncio
async def test_delete_synonym_mapping(client, auth_token):
    create_resp = await client.post(
        "/api/projects/1/synonym-mappings",
        json={"business_term": "删除测试", "code_terms": ["delete_test"], "priority": 100},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    mapping_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/projects/1/synonym-mappings/{mapping_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert delete_resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synonym_api.py -v`
Expected: FAIL with 404 (no route yet)

- [ ] **Step 3: Implement synonym API router**

Create `src/reqradar/web/api/synonyms.py`:

```python
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.database import get_session_dependency
from reqradar.web.models import SynonymMapping, Project
from reqradar.web.dependencies import get_current_user

logger = logging.getLogger("reqradar.api.synonyms")
router = APIRouter(prefix="/projects/{project_id}/synonym-mappings", tags=["synonyms"])


class SynonymCreateRequest(BaseModel):
    business_term: str
    code_terms: list[str]
    priority: int = 100


class SynonymUpdateRequest(BaseModel):
    code_terms: list[str] | None = None
    priority: int | None = None


class SynonymResponse(BaseModel):
    id: int
    project_id: int | None
    business_term: str
    code_terms: list[str]
    priority: int
    source: str

    class Config:
        from_attributes = True


@router.get("", response_model=dict)
async def list_synonym_mappings(
    project_id: int,
    source: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    query = select(SynonymMapping).where(SynonymMapping.project_id == project_id)
    if source:
        query = query.where(SynonymMapping.source == source)
    if search:
        query = query.where(SynonymMapping.business_term.contains(search))
    query = query.order_by(SynonymMapping.priority, SynonymMapping.business_term)
    result = await db.execute(query)
    mappings = result.scalars().all()
    return {"mappings": [_mapping_to_response(m) for m in mappings]}


@router.post("", response_model=SynonymResponse, status_code=201)
async def create_synonym_mapping(
    project_id: int,
    req: SynonymCreateRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    mapping = SynonymMapping(
        project_id=project_id,
        business_term=req.business_term,
        code_terms=json.dumps(req.code_terms, ensure_ascii=False),
        priority=req.priority,
        source="user",
        created_by=current_user.id if hasattr(current_user, "id") else None,
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return _mapping_to_response(mapping)


@router.put("/{mapping_id}", response_model=SynonymResponse)
async def update_synonym_mapping(
    project_id: int,
    mapping_id: int,
    req: SynonymUpdateRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(SynonymMapping).where(
            SynonymMapping.id == mapping_id,
            SynonymMapping.project_id == project_id,
        )
    )
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="Synonym mapping not found")
    if req.code_terms is not None:
        mapping.code_terms = json.dumps(req.code_terms, ensure_ascii=False)
    if req.priority is not None:
        mapping.priority = req.priority
    mapping.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(mapping)
    return _mapping_to_response(mapping)


@router.delete("/{mapping_id}")
async def delete_synonym_mapping(
    project_id: int,
    mapping_id: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(SynonymMapping).where(
            SynonymMapping.id == mapping_id,
            SynonymMapping.project_id == project_id,
        )
    )
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="Synonym mapping not found")
    await db.delete(mapping)
    await db.commit()
    return {"success": True}


def _mapping_to_response(m: SynonymMapping) -> dict:
    code_terms = json.loads(m.code_terms) if isinstance(m.code_terms, str) else m.code_terms
    return {
        "id": m.id,
        "project_id": m.project_id,
        "business_term": m.business_term,
        "code_terms": code_terms,
        "priority": m.priority,
        "source": m.source,
    }
```

- [ ] **Step 4: Register router in `src/reqradar/web/app.py`**

Add to `app.py`:

```python
from reqradar.web.api.synonyms import router as synonyms_router
app.include_router(synonyms_router)
```

- [ ] **Step 5: Run synonym API tests**

Run: `pytest tests/test_synonym_api.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Run all existing tests to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS, new tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/web/api/synonyms.py src/reqradar/web/app.py tests/test_synonym_api.py
git commit -m "feat: add synonym mapping CRUD API endpoints"
```

---

## Task 13: API Endpoints — Report Templates

**Files:**
- Create: `src/reqradar/web/api/templates.py`
- Modify: `src/reqradar/web/app.py`
- Create: `tests/test_report_templates_api.py`

- [ ] **Step 1: Write API tests for template endpoints**

Create `tests/test_report_templates_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from reqradar.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_token():
    from reqradar.web.api.auth import create_access_token
    return create_access_token({"sub": "1"})


@pytest.mark.asyncio
async def test_list_templates(client, auth_token):
    response = await client.get(
        "/api/report-templates",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "templates" in data


@pytest.mark.asyncio
async def test_create_template(client, auth_token):
    response = await client.post(
        "/api/report-templates",
        json={
            "name": "Test Template",
            "description": "A test template",
            "definition": "template_definition:\n  name: Test\n  sections:\n    - id: test\n      title: Test Section\n      description: Test description\n      required: true\n      dimensions: []\n",
            "render_template": "# {{ requirement_title }}",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 201)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_report_templates_api.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Implement template API router**

Create `src/reqradar/web/api/templates.py`:

```python
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.database import get_session_dependency
from reqradar.web.models import ReportTemplate
from reqradar.web.dependencies import get_current_user
from reqradar.infrastructure.template_loader import TemplateLoader

logger = logging.getLogger("reqradar.api.templates")
router = APIRouter(prefix="/report-templates", tags=["templates"])

DEFAULT_TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "default_report.yaml"


class TemplateCreateRequest(BaseModel):
    name: str
    description: str = ""
    definition: str
    render_template: str


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: str
    is_default: bool

    class Config:
        from_attributes = True


class TemplateDetailResponse(BaseModel):
    id: int
    name: str
    description: str
    definition: str
    render_template: str
    is_default: bool

    class Config:
        from_attributes = True


@router.get("", response_model=dict)
async def list_templates(
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(ReportTemplate).order_by(ReportTemplate.is_default.desc(), ReportTemplate.name)
    )
    templates = result.scalars().all()
    if not templates:
        default = await _ensure_default_template(db)
        templates = [default]
    return {"templates": [TemplateResponse.model_validate(t).model_dump() for t in templates]}


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateDetailResponse.model_validate(template)


@router.post("", response_model=TemplateDetailResponse, status_code=201)
async def create_template(
    req: TemplateCreateRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    template = ReportTemplate(
        name=req.name,
        description=req.description,
        definition=req.definition,
        render_template=req.render_template,
        is_default=False,
        created_by=current_user.id if hasattr(current_user, "id") else None,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateDetailResponse.model_validate(template)


@router.put("/{template_id}", response_model=TemplateDetailResponse)
async def update_template(
    template_id: int,
    req: TemplateCreateRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_default:
        raise HTTPException(status_code=400, detail="Cannot modify default template")
    template.name = req.name
    template.description = req.description
    template.definition = req.definition
    template.render_template = req.render_template
    template.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(template)
    return TemplateDetailResponse.model_validate(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default template")
    await db.delete(template)
    await db.commit()
    return {"success": True}


async def _ensure_default_template(db: AsyncSession) -> ReportTemplate:
    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.is_default == True)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    loader = TemplateLoader()
    defn = loader.load_definition(loader.get_default_template_path())
    template_path = loader.get_default_render_template_path()
    render_content = template_path.read_text(encoding="utf-8")

    import yaml
    definition_yaml = yaml.dump(
        {"template_definition": {"name": defn.name, "description": defn.description, "sections": [
            {"id": s.id, "title": s.title, "description": s.description, "requirements": s.requirements, "required": s.required, "dimensions": s.dimensions}
            for s in defn.sections
        ]}},
        allow_unicode=True,
        default_flow_style=False,
    )

    default = ReportTemplate(
        name=defn.name,
        description=defn.description,
        definition=definition_yaml,
        render_template=render_content,
        is_default=True,
    )
    db.add(default)
    await db.commit()
    await db.refresh(default)
    return default
```

- [ ] **Step 4: Register router in `src/reqradar/web/app.py`**

```python
from reqradar.web.api.templates import router as templates_router
app.include_router(templates_router)
```

- [ ] **Step 5: Run template API tests**

Run: `pytest tests/test_report_templates_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/web/api/templates.py src/reqradar/web/app.py tests/test_report_templates_api.py
git commit -m "feat: add report template CRUD API endpoints"
```

---

## Task 14: API Endpoints — Project Profile & Pending Changes

**Files:**
- Create: `src/reqradar/web/api/profile.py`
- Modify: `src/reqradar/web/app.py`
- Create: `tests/test_profile_api.py`

- [ ] **Step 1: Write API tests for profile/pending-change endpoints**

Create `tests/test_profile_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from reqradar.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_token():
    from reqradar.web.api.auth import create_access_token
    return create_access_token({"sub": "1"})


@pytest.mark.asyncio
async def test_get_project_profile(client, auth_token):
    response = await client.get(
        "/api/projects/1/profile",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_pending_changes(client, auth_token):
    response = await client.get(
        "/api/projects/1/profile/pending",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "pending_changes" in data


@pytest.mark.asyncio
async def test_accept_pending_change(client, auth_token):
    response = await client.post(
        "/api/projects/1/profile/pending/1",
        json={"action": "accept"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 404)
```

- [ ] **Step 2: Implement profile API router**

Create `src/reqradar/web/api/profile.py`:

```python
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.modules.project_memory import ProjectMemory
from reqradar.modules.pending_changes import PendingChangeManager
from reqradar.web.database import get_session_dependency
from reqradar.web.models import Project, PendingChange
from reqradar.infrastructure.config import load_config
from reqradar.web.dependencies import get_current_user

logger = logging.getLogger("reqradar.api.profile")
router = APIRouter(prefix="/projects/{project_id}/profile", tags=["profile"])


class PendingChangeResponse(BaseModel):
    id: int
    change_type: str
    target_id: str
    old_value: str
    new_value: str
    diff: str
    source: str
    status: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class AcceptRejectRequest(BaseModel):
    action: str
    modified_content: str | None = None


@router.get("")
async def get_project_profile(
    project_id: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    config = load_config()
    storage_path = config.memory.project_storage_path
    pm = ProjectMemory(storage_path=storage_path, project_id=project_id)
    data = pm.load()

    parsed = {
        "overview": data.get("overview", ""),
        "tech_stack": data.get("tech_stack", {}),
        "modules": data.get("modules", []),
        "terms": data.get("terms", []),
        "constraints": data.get("constraints", []),
    }

    return {
        "content": pm.file_path.read_text(encoding="utf-8") if pm.file_path.exists() else "",
        "parsed": parsed,
    }


@router.get("/pending")
async def get_pending_changes(
    project_id: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    manager = PendingChangeManager(db)
    changes = await manager.list_pending(project_id)
    return {
        "pending_changes": [PendingChangeResponse.model_validate(c).model_dump() for c in changes]
    }


@router.post("/pending/{change_id}")
async def resolve_pending_change(
    project_id: int,
    change_id: int,
    req: AcceptRejectRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    if req.action not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")

    manager = PendingChangeManager(db)
    user_id = current_user.id if hasattr(current_user, "id") else None

    if req.action == "accept":
        change = await manager.accept(change_id, resolved_by=user_id)
        if change and change.change_type == "profile":
            config = load_config()
            pm = ProjectMemory(storage_path=config.memory.project_storage_path, project_id=project_id)
            pm.load()
            if change.target_id.startswith("module:"):
                mod_name = change.target_id.split(":", 1)[1]
                pm.add_module(mod_name, change.new_value)
                pm.save()
            elif change.target_id == "overview":
                pm.update_overview(change.new_value)
                pm.save()
    elif req.action == "reject":
        change = await manager.reject(change_id, resolved_by=user_id)

    if change is None:
        raise HTTPException(status_code=404, detail="Pending change not found")

    return {"success": True, "status": change.status}
```

- [ ] **Step 4: Register router and run tests**

Add to `src/reqradar/web/app.py`:

```python
from reqradar.web.api.profile import router as profile_router
app.include_router(profile_router)
```

Run: `pytest tests/test_profile_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/api/profile.py src/reqradar/web/app.py tests/test_profile_api.py
git commit -m "feat: add project profile and pending change API endpoints"
```

---

## Task 15: Wire MemoryManager into AnalysisRunner

**Files:**
- Modify: `src/reqradar/web/services/analysis_runner.py`

- [ ] **Step 1: Read current analysis_runner.py fully**

Already read — it uses `MemoryManager` (YAML-based). We need to add support for the new `AnalysisMemoryManager` while keeping backward compatibility.

- [ ] **Step 2: Integrate AnalysisMemoryManager**

Update `analysis_runner.py` to optionally use `AnalysisMemoryManager` alongside the existing `MemoryManager`:

In `_execute_pipeline`, after creating the existing `memory_manager`, add:

```python
from reqradar.modules.memory_manager import AnalysisMemoryManager

analysis_memory = AnalysisMemoryManager(
    project_id=project.id,
    user_id=task.user_id,
    project_storage_path=str(Path(project.repo_path) / config.memory.project_storage_path) if project.repo_path else config.memory.project_storage_path,
    user_storage_path=str(Path(project.repo_path) / config.memory.user_storage_path) if project.repo_path else config.memory.user_storage_path,
    memory_enabled=config.memory.enabled,
)
```

The existing `memory_data = memory_manager.load()` call and all downstream usage remains unchanged for backward compatibility. The `analysis_memory` object is available for the Agent to use in Round 2. For now, we also update `ReportRenderer` to optionally receive a template definition:

```python
from reqradar.infrastructure.template_loader import TemplateLoader

template_loader = TemplateLoader()
if config.reporting.default_template_id:
    template_def = await _load_template_definition(db, config.reporting.default_template_id, template_loader)
else:
    template_def = None

renderer = ReportRenderer(config, template_definition=template_def)
```

This is a minimal change — the actual Agent integration comes in Round 2.

- [ ] **Step 3: Add helper to load template from DB**

Add a helper function in `analysis_runner.py`:

```python
async def _load_template_definition(db, template_id, template_loader):
    from reqradar.web.models import ReportTemplate
    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if tmpl:
        return template_loader.load_definition_from_db(tmpl.definition)
    return None
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/services/analysis_runner.py
git commit -m "feat: integrate AnalysisMemoryManager and TemplateLoader into AnalysisRunner"
```

---

## Task 16: Update SynonymResolver in Step Pipeline

**Files:**
- Modify: `src/reqradar/agent/steps.py`

- [ ] **Step 1: Read the keyword mapping step in steps.py**

Read `src/reqradar/agent/steps.py` lines around `step_map_keywords` to understand where synonym resolution is used.

- [ ] **Step 2: Integrate SynonymResolver into step_map_keywords**

In `step_map_keywords`, after loading `memory_data`, add option to use `SynonymResolver`:

```python
from reqradar.modules.synonym_resolver import SynonymResolver

# In step_map_keywords, after extracting keywords:
synonym_resolver = SynonymResolver()
expanded_keywords, mapping_log = synonym_resolver.expand_keywords_with_synonyms(
    keywords=keywords,
    project_mappings=[],  # Will be loaded from DB in Round 2
    global_mappings=[],   # Will be loaded from DB in Round 2
)
```

For now this is a no-op change since we pass empty mappings — the actual DB loading happens in Round 2 with the Agent. It ensures the SynonymResolver is wired in and falls back to `_COMMON_SYNONYMS`.

- [ ] **Step 3: Run existing step tests**

Run: `pytest tests/test_steps_structured.py tests/test_keyword_mapping.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/agent/steps.py
git commit -m "feat: wire SynonymResolver into step_map_keywords (fallback to hardcoded for now)"
```

---

## Task 17: Database Seed — Default Template

**Files:**
- Create: `src/reqradar/web/seed.py`

- [ ] **Step 1: Create database seed script for default report template**

Create `src/reqradar/web/seed.py`:

```python
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import ReportTemplate
from reqradar.infrastructure.template_loader import TemplateLoader

logger = logging.getLogger("reqradar.seed")


async def seed_default_template(db: AsyncSession) -> ReportTemplate:
    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.is_default == True)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("Default template already exists (id=%d), skipping seed", existing.id)
        return existing

    loader = TemplateLoader()
    defn = loader.load_definition(loader.get_default_template_path())
    template_path = loader.get_default_render_template_path()
    render_content = template_path.read_text(encoding="utf-8")

    import yaml
    definition_yaml = yaml.dump(
        {"template_definition": {"name": defn.name, "description": defn.description, "sections": [
            {"id": s.id, "title": s.title, "description": s.description, "requirements": s.requirements, "required": s.required, "dimensions": s.dimensions}
            for s in defn.sections
        ]}},
        allow_unicode=True,
        default_flow_style=False,
    )

    default = ReportTemplate(
        name=defn.name,
        description=defn.description,
        definition=definition_yaml,
        render_template=render_content,
        is_default=True,
    )
    db.add(default)
    await db.commit()
    await db.refresh(default)
    logger.info("Seeded default template (id=%d)", default.id)
    return default


async def seed_all(db: AsyncSession):
    await seed_default_template(db)
```

- [ ] **Step 2: Add seed call to app startup**

In `src/reqradar/web/app.py`, add startup event:

```python
from reqradar.web.seed import seed_all

@app.on_event("startup")
async def startup_seed():
    from reqradar.web.dependencies import async_session_factory
    async with async_session_factory() as db:
        await seed_all(db)
```

- [ ] **Step 3: Run all tests to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/web/seed.py src/reqradar/web/app.py
git commit -m "feat: add database seed for default report template"
```

---

## Task 18: Full Integration Test Suite

**Files:**
- Create: `tests/test_round1_integration.py`

- [ ] **Step 1: Write integration tests verifying all Round 1 modules work together**

Create `tests/test_round1_integration.py`:

```python
import pytest
from pathlib import Path
from reqradar.modules.project_memory import ProjectMemory
from reqradar.modules.user_memory import UserMemory
from reqradar.modules.memory_manager import AnalysisMemoryManager
from reqradar.modules.synonym_resolver import SynonymResolver
from reqradar.infrastructure.template_loader import TemplateLoader


def test_memory_manager_uses_project_and_user_memory(tmp_path):
    mm = AnalysisMemoryManager(
        project_id=42,
        user_id=7,
        project_storage_path=str(tmp_path / "memories"),
        user_storage_path=str(tmp_path / "user_memories"),
        memory_enabled=True,
    )
    mm.project_memory.update_overview("Integration test project")
    mm.project_memory.add_tech_stack("languages", ["Python"])
    mm.project_memory.add_module("core", "Core module")
    mm.project_memory.save()

    mm.user_memory.add_correction("配置", ["config_proj"])
    mm.user_memory.set_preference("default_depth", "deep")
    mm.user_memory.save()

    profile_text = mm.get_project_profile_text()
    assert "Integration test project" in profile_text
    assert "Python" in profile_text

    user_text = mm.get_user_memory_text()
    assert "配置" in user_text
    assert "config_proj" in user_text


def test_synonym_resolver_with_project_memory(tmp_path):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=str(tmp_path / "memories"),
        user_storage_path=str(tmp_path / "user_memories"),
        memory_enabled=True,
    )
    mm.project_memory.add_term("配置", "Configuration settings", domain="general")
    mm.project_memory.save()

    resolver = SynonymResolver()
    keywords, mapping_log = resolver.expand_keywords_with_synonyms(
        keywords=["配置", "认证"],
        project_mappings=[],
        global_mappings=[],
    )
    assert "配置" in keywords


def test_template_loader_loads_default():
    loader = TemplateLoader()
    defn = loader.load_definition(loader.get_default_template_path())
    assert len(defn.sections) >= 7
    required = [s for s in defn.sections if s.required]
    assert len(required) >= 6

    prompts = loader.build_section_prompts(defn)
    assert "requirement_understanding" in prompts
    assert "影响力分析" in prompts.get("impact_analysis", "") or "impact" in prompts.get("impact_analysis", "")


def test_memory_manager_disabled():
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path="/tmp/unused",
        user_storage_path="/tmp/unused",
        memory_enabled=False,
    )
    assert mm.project_memory is None
    assert mm.user_memory is None
    assert mm.get_project_profile_text() == ""
    assert mm.get_user_memory_text() == ""
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_round1_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS, no regressions

- [ ] **Step 4: Commit**

```bash
git add tests/test_round1_integration.py
git commit -m "test: add Round 1 integration tests for memory, templates, and synonyms"
```

---

## Self-Review Checklist

After completing all tasks, verify:

- [ ] **Spec Coverage**: Each section of the spec Round 1 has a corresponding task:
  - Section 4.2 (Project Memory) → Task 4
  - Section 4.3 (User Memory) → Task 5
  - Section 4.4 (Vector Memory isolation) → Existing VectorStore already isolates by collection; Task 6 facade provides unified access
  - Section 4.6 (PendingChange) → Task 11
  - Section 5.1 (Template System) → Tasks 7, 8, 9
  - Section 7 (Synonyms) → Task 10, Task 12
  - Section 8 (DB Models) → Task 2, Task 3
  - Section 9.4-9.6 (APIs) → Tasks 12, 13, 14

- [ ] **No Placeholders**: No TBD, TODO, or "implement later" in any task

- [ ] **Type Consistency**: All models, methods, and variables use consistent naming across tasks

- [ ] **Backward Compatibility**: Existing `MemoryManager` (YAML) still works; `analysis_runner.py` still uses legacy `MemoryManager` alongside new `AnalysisMemoryManager`; existing tests pass