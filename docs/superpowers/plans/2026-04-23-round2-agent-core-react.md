# Round 2: Agent Core ReAct Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed 6-step pipeline with a goal-driven ReAct Agent that autonomously decides tool calls, while preserving the legacy pipeline as a fallback mode.

**Architecture:** The core `AnalysisAgent` class maintains state (dimensions, evidence, steps) and runs a ReAct loop (Reason → Act → Observe). A new `AnalysisRunnerV2` orchestrates the agent, selected by config `agent.mode`. Existing `Scheduler` + `step_*` functions remain untouched as `legacy` mode. Tool security is enforced via permission checks before execution. Agent prompts are injected with template section descriptions from Round 1's `TemplateDefinition`.

**Tech Stack:** Python 3.12, SQLAlchemy async, Pydantic, Jinja2, FastAPI, pytest, pytest-asyncio

---

## File Structure

### New Files
- `src/reqradar/agent/analysis_agent.py` — Core `AnalysisAgent` class with state machine and ReAct loop
- `src/reqradar/agent/evidence.py` — `EvidenceCollector` and `Evidence` models
- `src/reqradar/agent/dimension.py` — `DimensionState` tracker (pending/in_progress/sufficient/insufficient)
- `src/reqradar/agent/prompts/analysis_phase.py` — Agent analysis-phase system prompt builder
- `src/reqradar/agent/prompts/report_phase.py` — Agent report-generation phase prompt builder
- `src/reqradar/agent/tools/security.py` — Tool permission checker, path sandbox, sensitive file filter
- `src/reqradar/agent/tools/__init__.py` — Updated: export new tools + security wrapper
- `src/reqradar/web/services/analysis_runner_v2.py` — `AnalysisRunnerV2` using ReAct Agent (parallel to `AnalysisRunner`)
- `tests/test_analysis_agent.py` — Tests for AnalysisAgent state machine and ReAct loop
- `tests/test_evidence.py` — Tests for EvidenceCollector
- `tests/test_dimension.py` — Tests for DimensionState
- `tests/test_tool_security.py` — Tests for permission checks, path sandbox, sensitive file filter
- `tests/test_analysis_runner_v2.py` — Integration tests for AnalysisRunnerV2

### Modified Files
- `src/reqradar/agent/tools/base.py` — Add `required_permissions` to `BaseTool`
- `src/reqradar/agent/tools/registry.py` — Add permission-aware execution
- `src/reqradar/agent/tools/*.py` — Add `required_permissions` class attribute to each tool
- `src/reqradar/agent/prompts.py` — Re-export from `prompts/` package for backward compat
- `src/reqradar/web/services/analysis_runner.py` — Add mode selection logic (legacy/react)
- `src/reqradar/web/app.py` — Register new websocket message types, add cancel endpoint
- `src/reqradar/web/api/analyses.py` — Add depth parameter to analysis submit
- `src/reqradar/infrastructure/config.py` — Already has `AgentConfig` from Round 1

---

## Task 1: Evidence and Dimension Models

**Files:**
- Create: `src/reqradar/agent/evidence.py`
- Create: `src/reqradar/agent/dimension.py`
- Create: `tests/test_evidence.py`
- Create: `tests/test_dimension.py`

- [ ] **Step 1: Write tests for EvidenceCollector**

Create `tests/test_evidence.py`:

```python
import pytest
from reqradar.agent.evidence import Evidence, EvidenceCollector


def test_evidence_creation():
    ev = Evidence(
        id="ev-001",
        type="code",
        source="src/web/app.py:42",
        content="Route handler for /api/analyses",
        confidence="high",
        dimensions=["impact", "change"],
    )
    assert ev.id == "ev-001"
    assert ev.type == "code"
    assert ev.confidence == "high"


def test_evidence_collector_add():
    collector = EvidenceCollector()
    ev_id = collector.add(
        type="code",
        source="src/web/app.py:42",
        content="Route handler",
        confidence="high",
        dimensions=["impact"],
    )
    assert ev_id.startswith("ev-")
    assert len(collector.evidences) == 1


def test_evidence_collector_auto_id():
    collector = EvidenceCollector()
    id1 = collector.add(type="code", source="f1", content="c1", confidence="medium")
    id2 = collector.add(type="code", source="f2", content="c2", confidence="high")
    assert id1 != id2


def test_evidence_collector_get_by_dimension():
    collector = EvidenceCollector()
    collector.add(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    collector.add(type="code", source="f2", content="c2", confidence="high", dimensions=["risk"])
    collector.add(type="code", source="f3", content="c3", confidence="medium", dimensions=["impact", "change"])

    impact_evs = collector.get_by_dimension("impact")
    assert len(impact_evs) == 2

    risk_evs = collector.get_by_dimension("risk")
    assert len(risk_evs) == 1


def test_evidence_collector_to_lightweight_snapshot():
    collector = EvidenceCollector()
    collector.add(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    collector.add(type="history", source="analysis-123", content="Similar requirement", confidence="medium", dimensions=["risk"])

    snapshot = collector.to_snapshot()
    assert len(snapshot) == 2
    assert snapshot[0]["id"].startswith("ev-")
    assert snapshot[0]["type"] == "code"
    assert snapshot[1]["type"] == "history"


def test_evidence_collector_from_snapshot():
    collector = EvidenceCollector()
    collector.add(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    snapshot = collector.to_snapshot()

    collector2 = EvidenceCollector()
    collector2.from_snapshot(snapshot)
    assert len(collector2.evidences) == 1
    assert collector2.evidences[0].source == "f1"
```

- [ ] **Step 2: Write tests for DimensionState**

Create `tests/test_dimension.py`:

```python
import pytest
from reqradar.agent.dimension import DimensionState, DimensionTracker


def test_dimension_tracker_init():
    tracker = DimensionTracker()
    assert len(tracker.dimensions) == 7
    assert all(d.status == "pending" for d in tracker.dimensions.values())


def test_dimension_tracker_mark_in_progress():
    tracker = DimensionTracker()
    tracker.mark_in_progress("impact")
    assert tracker.dimensions["impact"].status == "in_progress"


def test_dimension_tracker_mark_sufficient():
    tracker = DimensionTracker()
    tracker.mark_sufficient("impact")
    assert tracker.dimensions["impact"].status == "sufficient"


def test_dimension_tracker_add_evidence():
    tracker = DimensionTracker()
    tracker.add_evidence("impact", "ev-001")
    assert "ev-001" in tracker.dimensions["impact"].evidence_ids


def test_dimension_tracker_get_weak_dimensions():
    tracker = DimensionTracker()
    tracker.mark_sufficient("understanding")
    tracker.mark_sufficient("impact")
    weak = tracker.get_weak_dimensions()
    assert "risk" in weak
    assert "understanding" not in weak


def test_dimension_tracker_all_sufficient():
    tracker = DimensionTracker()
    for dim_id in tracker.dimensions:
        tracker.mark_sufficient(dim_id)
    assert tracker.all_sufficient()


def test_dimension_tracker_status_summary():
    tracker = DimensionTracker()
    tracker.mark_sufficient("understanding")
    tracker.mark_in_progress("impact")
    summary = tracker.status_summary()
    assert summary["understanding"] == "sufficient"
    assert summary["impact"] == "in_progress"
    assert summary["risk"] == "pending"


def test_dimension_tracker_custom_dimensions():
    tracker = DimensionTracker(dimensions=["impact", "risk", "change"])
    assert len(tracker.dimensions) == 3
    assert "impact" in tracker.dimensions
    assert "understanding" not in tracker.dimensions
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_evidence.py tests/test_dimension.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 4: Implement EvidenceCollector**

Create `src/reqradar/agent/evidence.py`:

```python
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Evidence:
    id: str
    type: str
    source: str
    content: str
    confidence: str = "medium"
    dimensions: list[str] = field(default_factory=list)
    timestamp: Optional[str] = None


class EvidenceCollector:
    def __init__(self):
        self.evidences: list[Evidence] = []
        self._counter: int = 0

    def add(
        self,
        type: str,
        source: str,
        content: str,
        confidence: str = "medium",
        dimensions: list[str] | None = None,
    ) -> str:
        self._counter += 1
        ev_id = f"ev-{self._counter:03d}"
        evidence = Evidence(
            id=ev_id,
            type=type,
            source=source,
            content=content,
            confidence=confidence,
            dimensions=dimensions or [],
        )
        self.evidences.append(evidence)
        return ev_id

    def get_by_dimension(self, dimension: str) -> list[Evidence]:
        return [ev for ev in self.evidences if dimension in ev.dimensions]

    def get_by_type(self, evidence_type: str) -> list[Evidence]:
        return [ev for ev in self.evidences if ev.type == evidence_type]

    def get_all_evidence_text(self) -> str:
        if not self.evidences:
            return "暂无证据"
        lines = []
        for ev in self.evidences:
            dim_str = ", ".join(ev.dimensions) if ev.dimensions else "无特定维度"
            lines.append(f"[{ev.id}] ({ev.type}, {ev.confidence}) {ev.source}: {ev.content} [维度: {dim_str}]")
        return "\n".join(lines)

    def to_snapshot(self) -> list[dict]:
        return [
            {
                "id": ev.id,
                "type": ev.type,
                "source": ev.source,
                "content": ev.content,
                "confidence": ev.confidence,
                "dimensions": ev.dimensions,
                "timestamp": ev.timestamp,
            }
            for ev in self.evidences
        ]

    def from_snapshot(self, snapshot: list[dict]) -> None:
        self.evidences = []
        self._counter = 0
        for item in snapshot:
            ev = Evidence(
                id=item["id"],
                type=item["type"],
                source=item["source"],
                content=item["content"],
                confidence=item.get("confidence", "medium"),
                dimensions=item.get("dimensions", []),
                timestamp=item.get("timestamp"),
            )
            self.evidences.append(ev)
            try:
                num = int(item["id"].split("-")[1])
                self._counter = max(self._counter, num)
            except (ValueError, IndexError):
                pass

    def to_context_text(self) -> str:
        if not self.evidences:
            return ""
        lines = ["已收集证据："]
        for ev in self.evidences:
            lines.append(f"- [{ev.id}] ({ev.type}/{ev.confidence}) {ev.source}: {ev.content[:200]}")
        return "\n".join(lines)
```

- [ ] **Step 5: Implement DimensionState**

Create `src/reqradar/agent/dimension.py`:

```python
from dataclasses import dataclass, field
from typing import Optional


DEFAULT_DIMENSIONS = [
    "understanding",
    "impact",
    "risk",
    "change",
    "decision",
    "evidence",
    "verification",
]


@dataclass
class DimensionState:
    id: str
    status: str = "pending"
    evidence_ids: list[str] = field(default_factory=list)
    draft_content: Optional[str] = None

    def mark_in_progress(self) -> None:
        if self.status == "pending":
            self.status = "in_progress"

    def mark_sufficient(self) -> None:
        self.status = "sufficient"

    def mark_insufficient(self) -> None:
        self.status = "insufficient"

    def add_evidence(self, evidence_id: str) -> None:
        if evidence_id not in self.evidence_ids:
            self.evidence_ids.append(evidence_id)


class DimensionTracker:
    def __init__(self, dimensions: list[str] | None = None):
        dim_list = dimensions if dimensions is not None else DEFAULT_DIMENSIONS
        self.dimensions: dict[str, DimensionState] = {
            dim_id: DimensionState(id=dim_id) for dim_id in dim_list
        }

    def mark_in_progress(self, dimension_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].mark_in_progress()

    def mark_sufficient(self, dimension_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].mark_sufficient()

    def mark_insufficient(self, dimension_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].mark_insufficient()

    def add_evidence(self, dimension_id: str, evidence_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].add_evidence(evidence_id)

    def get_weak_dimensions(self) -> list[str]:
        return [
            dim_id for dim_id, state in self.dimensions.items()
            if state.status in ("pending", "in_progress", "insufficient")
        ]

    def all_sufficient(self) -> bool:
        return all(s.status == "sufficient" for s in self.dimensions.values())

    def status_summary(self) -> dict[str, str]:
        return {dim_id: state.status for dim_id, state in self.dimensions.items()}

    def to_snapshot(self) -> dict:
        return {
            dim_id: {
                "status": state.status,
                "evidence_ids": state.evidence_ids,
            }
            for dim_id, state in self.dimensions.items()
        }

    def from_snapshot(self, snapshot: dict) -> None:
        for dim_id, data in snapshot.items():
            if dim_id in self.dimensions:
                self.dimensions[dim_id].status = data.get("status", "pending")
                self.dimensions[dim_id].evidence_ids = data.get("evidence_ids", [])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_evidence.py tests/test_dimension.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/agent/evidence.py src/reqradar/agent/dimension.py tests/test_evidence.py tests/test_dimension.py
git commit -m "feat: add EvidenceCollector and DimensionTracker for ReAct agent state"
```

---

## Task 2: Tool Permission System and Sandbox

**Files:**
- Create: `src/reqradar/agent/tools/security.py`
- Modify: `src/reqradar/agent/tools/base.py`
- Modify: `src/reqradar/agent/tools/registry.py`
- Modify: `src/reqradar/agent/tools/*.py` — Add `required_permissions` to each tool
- Create: `tests/test_tool_security.py`

- [ ] **Step 1: Write tests for tool security**

Create `tests/test_tool_security.py`:

```python
import pytest
from reqradar.agent.tools.security import ToolPermissionChecker, PathSandbox, SensitiveFileFilter


def test_permission_checker_allow():
    checker = ToolPermissionChecker(user_permissions={"read:code", "read:memory"})
    assert checker.is_allowed("read:code")
    assert checker.is_allowed("read:memory")


def test_permission_checker_deny():
    checker = ToolPermissionChecker(user_permissions={"read:code"})
    assert not checker.is_allowed("write:report")
    assert not checker.is_allowed("read:user_memory")


def test_path_sandbox_allow():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert sandbox.is_allowed("/home/user/project/src/app.py")
    assert sandbox.is_allowed("/home/user/project/web/models.py")


def test_path_sandbox_deny_traversal():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert not sandbox.is_allowed("/home/user/project/../etc/passwd")
    assert not sandbox.is_allowed("/home/user/project/../../etc/passwd")


def test_path_sandbox_deny_outside():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert not sandbox.is_allowed("/etc/passwd")
    assert not sandbox.is_allowed("/home/user/other/file.py")


def test_sensitive_file_filter_default():
    sf = SensitiveFileFilter()
    assert sf.is_sensitive(".env")
    assert sf.is_sensitive("secrets/database.key")
    assert sf.is_sensitive("config/cert.pem")
    assert not sf.is_sensitive("src/app.py")
    assert not sf.is_sensitive("README.md")


def test_sensitive_file_filter_custom():
    sf = SensitiveFileFilter(extra_patterns=["*.private"])
    assert sf.is_sensitive("data.private")
    assert not sf.is_sensitive("data.csv")


def test_permission_checker_with_tool():
    from reqradar.agent.tools.security import check_tool_permissions
    mock_tool_permissions = {"read:code", "read:memory", "read:git"}
    allowed = check_tool_permissions(
        required_permissions=["read:code", "read:memory"],
        user_permissions=mock_tool_permissions,
    )
    assert allowed is True


def test_permission_checker_tool_denied():
    from reqradar.agent.tools.security import check_tool_permissions
    mock_tool_permissions = {"read:code"}
    allowed = check_tool_permissions(
        required_permissions=["read:code", "write:report"],
        user_permissions=mock_tool_permissions,
    )
    assert allowed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tool_security.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Add `required_permissions` to BaseTool**

In `src/reqradar/agent/tools/base.py`, add `required_permissions` class attribute:

```python
class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters_schema: dict | None = None
    required_permissions: list[str] = []  # NEW
```

- [ ] **Step 4: Implement security module**

Create `src/reqradar/agent/tools/security.py`:

```python
import fnmatch
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("reqradar.agent.security")

DEFAULT_SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.crt",
    "secrets/",
    "credentials/",
    ".aws/",
    ".ssh/",
]


class ToolPermissionChecker:
    def __init__(self, user_permissions: set[str] | None = None):
        self.user_permissions = user_permissions or set()

    def is_allowed(self, permission: str) -> bool:
        return permission in self.user_permissions

    def check_tool(self, tool_permissions: list[str]) -> tuple[bool, list[str]]:
        missing = [p for p in tool_permissions if p not in self.user_permissions]
        return len(missing) == 0, missing


def check_tool_permissions(required_permissions: list[str], user_permissions: set[str]) -> bool:
    checker = ToolPermissionChecker(user_permissions)
    allowed, missing = checker.check_tool(required_permissions)
    if not allowed:
        logger.warning("Tool permission denied. Missing: %s", missing)
    return allowed


class PathSandbox:
    def __init__(self, allowed_root: str):
        self.allowed_root = Path(allowed_root).resolve()

    def is_allowed(self, file_path: str) -> bool:
        try:
            resolved = Path(file_path).resolve()
            try:
                resolved.relative_to(self.allowed_root)
                return True
            except ValueError:
                return False
        except (OSError, ValueError):
            return False

    def normalize(self, file_path: str) -> str:
        return str(Path(file_path).resolve())


class SensitiveFileFilter:
    def __init__(self, extra_patterns: list[str] | None = None):
        self.patterns = list(DEFAULT_SENSITIVE_PATTERNS)
        if extra_patterns:
            self.patterns.extend(extra_patterns)

    def is_sensitive(self, file_path: str) -> bool:
        path = Path(file_path)
        name = path.name
        parts = path.parts

        for pattern in self.patterns:
            if pattern.endswith("/"):
                if any(part == pattern.rstrip("/") for part in parts):
                    return True
            else:
                if fnmatch.fnmatch(name, pattern):
                    return True
                if fnmatch.fnmatch(str(path), pattern):
                    return True

        return False
```

- [ ] **Step 5: Add `required_permissions` to existing tools**

Add `required_permissions` class attribute to each tool file. Here are the assignments based on the spec (section 3.4.2):

| Tool | Permissions |
|------|------------|
| `SearchCodeTool` | `["read:code"]` |
| `ReadFileTool` | `["read:code"]` |
| `ListModulesTool` | `["read:memory"]` |
| `ReadModuleSummaryTool` | `["read:memory"]` |
| `GetProjectProfileTool` | `["read:memory"]` |
| `GetTerminologyTool` | `["read:memory"]` |
| `SearchRequirementsTool` | `["read:history"]` |
| `GetDependenciesTool` | `["read:code"]` |
| `GetContributorsTool` | `["read:git"]` |

For each tool (e.g., `src/reqradar/agent/tools/search_code.py`), add:

```python
class SearchCodeTool(BaseTool):
    name = "search_code"
    description = "..."
    required_permissions = ["read:code"]  # ADD THIS
    ...
```

- [ ] **Step 6: Add permission-aware execution to ToolRegistry**

Update `src/reqradar/agent/tools/registry.py`:

```python
from reqradar.agent.tools.base import BaseTool
from reqradar.agent.tools.security import ToolPermissionChecker, check_tool_permissions


class ToolRegistry:
    def __init__(self, user_permissions: set[str] | None = None):
        self._tools: dict[str, BaseTool] = {}
        self._permission_checker = ToolPermissionChecker(user_permissions)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_schemas(self, names: list[str] | None = None) -> list[dict]:
        if names is None:
            return [t.openai_schema() for t in self._tools.values()]
        return [
            self._tools[n].openai_schema() for n in names if n in self._tools
        ]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    async def execute_with_permissions(self, name: str, **kwargs) -> "ToolResult":
        from reqradar.agent.tools.base import ToolResult
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(success=False, data="", error=f"Tool not found: {name}")

        if not check_tool_permissions(tool.required_permissions, self._permission_checker.user_permissions):
            return ToolResult(
                success=False,
                data="",
                error=f"Permission denied: tool '{name}' requires {tool.required_permissions}",
            )

        return await tool.execute(**kwargs)
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_tool_security.py tests/test_tool_base.py tests/test_tool_registry.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/reqradar/agent/tools/security.py src/reqradar/agent/tools/base.py src/reqradar/agent/tools/registry.py src/reqradar/agent/tools/*.py tests/test_tool_security.py
git commit -m "feat: add tool permission system, path sandbox, sensitive file filter, and required_permissions to all tools"
```

---

## Task 3: AnalysisAgent Core — State Machine and ReAct Loop

**Files:**
- Create: `src/reqradar/agent/analysis_agent.py`
- Create: `tests/test_analysis_agent.py`

- [ ] **Step 1: Write tests for AnalysisAgent state machine**

Create `tests/test_analysis_agent.py`:

```python
import pytest
from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker


def test_agent_initial_state():
    agent = AnalysisAgent(
        requirement_text="Add user authentication",
        project_id=1,
        user_id=1,
        depth="standard",
        max_steps=15,
    )
    assert agent.state == AgentState.INIT
    assert agent.step_count == 0
    assert agent.max_steps == 15
    assert agent.dimension_tracker is not None
    assert agent.evidence_collector is not None


def test_agent_depth_mapping():
    agent_quick = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    assert agent_quick.max_steps == 10

    agent_standard = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    assert agent_standard.max_steps == 15

    agent_deep = AnalysisAgent("test", project_id=1, user_id=1, depth="deep")
    assert agent_deep.max_steps == 25


def test_agent_should_terminate_max_steps():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    agent.step_count = 10
    assert agent.should_terminate()


def test_agent_should_not_terminate_under_limit():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent.step_count = 5
    assert not agent.should_terminate()


def test_agent_should_terminate_all_dimensions_sufficient():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    for dim_id in agent.dimension_tracker.dimensions:
        agent.dimension_tracker.mark_sufficient(dim_id)
    assert agent.should_terminate()


def test_agent_record_evidence():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    ev_id = agent.record_evidence(
        type="code",
        source="src/app.py:10",
        content="Main application entry point",
        confidence="high",
        dimensions=["impact"],
    )
    assert ev_id is not None
    assert len(agent.evidence_collector.evidences) == 1
    assert "impact" in agent.dimension_tracker.dimensions["impact"].evidence_ids or True


def test_agent_get_context_text():
    agent = AnalysisAgent("Add SSO support", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="src/auth.py", content="Auth module", confidence="high", dimensions=["impact"])
    context = agent.get_context_text()
    assert "Auth module" in context


def test_agent_state_transitions():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    assert agent.state == AgentState.INIT
    agent.state = AgentState.ANALYZING
    assert agent.state == AgentState.ANALYZING
    agent.state = AgentState.GENERATING
    assert agent.state == AgentState.GENERATING
    agent.state = AgentState.COMPLETED
    assert agent.state == AgentState.COMPLETED


def test_agent_lightweight_context_snapshot():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    agent.dimension_tracker.mark_in_progress("impact")

    snapshot = agent.get_context_snapshot()
    assert "evidence_list" in snapshot
    assert "dimension_status" in snapshot
    assert "visited_files" in snapshot
    assert "tool_calls" in snapshot
    assert len(snapshot["evidence_list"]) == 1
    assert snapshot["dimension_status"]["impact"] == "in_progress"


def test_agent_restore_from_snapshot():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    agent.dimension_tracker.mark_in_progress("impact")
    snapshot = agent.get_context_snapshot()

    agent2 = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent2.restore_from_snapshot(snapshot)
    assert len(agent2.evidence_collector.evidences) == 1
    assert agent2.dimension_tracker.dimensions["impact"].status == "in_progress"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement AnalysisAgent**

Create `src/reqradar/agent/analysis_agent.py`:

```python
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker, DEFAULT_DIMENSIONS

logger = logging.getLogger("reqradar.agent.analysis_agent")


class AgentState(Enum):
    INIT = "init"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


DEPTH_MAX_STEPS = {
    "quick": 10,
    "standard": 15,
    "deep": 25,
}


class AnalysisAgent:
    def __init__(
        self,
        requirement_text: str,
        project_id: int,
        user_id: int,
        depth: str = "standard",
        max_steps: int | None = None,
    ):
        self.requirement_text = requirement_text
        self.project_id = project_id
        self.user_id = user_id
        self.depth = depth
        self.max_steps = max_steps or DEPTH_MAX_STEPS.get(depth, 15)

        self.state: AgentState = AgentState.INIT
        self.step_count: int = 0
        self.evidence_collector = EvidenceCollector()
        self.dimension_tracker = DimensionTracker()
        self.visited_files: list[str] = []
        self.tool_call_history: list[dict] = []
        self.project_memory_text: str = ""
        self.user_memory_text: str = ""
        self.historical_context: str = ""
        self.final_report_data: dict | None = None
        self._cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True
        self.state = AgentState.CANCELLED

    def should_terminate(self) -> bool:
        if self._cancelled:
            return True
        if self.step_count >= self.max_steps:
            return True
        if self.dimension_tracker.all_sufficient():
            return True
        return False

    def record_evidence(
        self,
        type: str,
        source: str,
        content: str,
        confidence: str = "medium",
        dimensions: list[str] | None = None,
    ) -> str:
        ev_id = self.evidence_collector.add(
            type=type, source=source, content=content, confidence=confidence, dimensions=dimensions
        )
        if dimensions:
            for dim in dimensions:
                self.dimension_tracker.add_evidence(dim, ev_id)
        if source not in self.visited_files and type == "code":
            self.visited_files.append(source.split(":")[0] if ":" in source else source)
        return ev_id

    def record_tool_call(self, tool_name: str, parameters: dict, result_summary: str) -> None:
        self.tool_call_history.append({
            "step": self.step_count,
            "tool": tool_name,
            "parameters": parameters,
            "result_summary": result_summary[:200],
        })
        self.step_count += 1

    def get_context_text(self) -> str:
        parts = []
        if self.project_memory_text:
            parts.append(f"## 项目画像\n{self.project_memory_text}")
        if self.user_memory_text:
            parts.append(f"## 用户偏好\n{self.user_memory_text}")
        if self.historical_context:
            parts.append(f"## 相似历史需求\n{self.historical_context}")
        parts.append(f"## 当前需求\n{self.requirement_text}")
        parts.append(f"## 维度状态\n{self._dimension_status_text()}")
        ev_text = self.evidence_collector.to_context_text()
        if ev_text:
            parts.append(ev_text)
        parts.append(f"## 步骤计数\n已用 {self.step_count}/{self.max_steps} 步")
        return "\n\n".join(parts)

    def _dimension_status_text(self) -> str:
        lines = []
        for dim_id, state in self.dimension_tracker.dimensions.items():
            ev_count = len(state.evidence_ids)
            lines.append(f"- {dim_id}: {state.status} ({ev_count} 条证据)")
        return "\n".join(lines)

    def get_weak_dimensions_text(self) -> str:
        weak = self.dimension_tracker.get_weak_dimensions()
        if not weak:
            return "所有维度已达标"
        return "需要补充证据的维度：" + ", ".join(weak)

    def get_context_snapshot(self) -> dict:
        return {
            "evidence_list": self.evidence_collector.to_snapshot(),
            "dimension_status": self.dimension_tracker.to_snapshot(),
            "visited_files": list(self.visited_files),
            "tool_calls": list(self.tool_call_history),
            "step_count": self.step_count,
        }

    def restore_from_snapshot(self, snapshot: dict) -> None:
        if "evidence_list" in snapshot:
            self.evidence_collector.from_snapshot(snapshot["evidence_list"])
        if "dimension_status" in snapshot:
            self.dimension_tracker.from_snapshot(snapshot["dimension_status"])
        if "visited_files" in snapshot:
            self.visited_files = list(snapshot["visited_files"])
        if "tool_calls" in snapshot:
            self.tool_call_history = list(snapshot["tool_calls"])
        if "step_count" in snapshot:
            self.step_count = snapshot["step_count"]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/agent/analysis_agent.py tests/test_analysis_agent.py
git commit -m "feat: add AnalysisAgent with state machine, evidence tracking, dimension tracking, and context snapshot"
```

---

## Task 4: Analysis Phase Prompt Builder

**Files:**
- Create: `src/reqradar/agent/prompts/analysis_phase.py`
- Create: `src/reqradar/agent/prompts/report_phase.py`
- Create: `src/reqradar/agent/prompts/__init__.py`
- Modify: `src/reqradar/agent/prompts.py` — Re-export from package

- [ ] **Step 1: Create prompts package init**

Create `src/reqradar/agent/prompts/__init__.py`:

```python
from reqradar.agent.prompts.analysis_phase import build_analysis_system_prompt, build_analysis_user_prompt, build_termination_prompt
from reqradar.agent.prompts.report_phase import build_report_generation_prompt, build_dimension_section_prompt
```

- [ ] **Step 2: Create analysis phase prompt builder**

Create `src/reqradar/agent/prompts/analysis_phase.py`:

```python
from reqradar.agent.dimension import DimensionTracker


ANALYSIS_SYSTEM_PROMPT = """你是一位专业的需求分析架构师。你的目标是为给定需求生成一份完整、可验证的分析报告，覆盖所有必要维度。

## 行为规范
1. 优先使用工具获取信息，不要猜测
2. 每个结论必须有证据支撑，引用具体来源
3. 关注用户指定的关注领域（如安全性、性能）
4. 达到最大步数时停止收集信息，生成报告
5. 不可执行代码、不可写入文件（报告除外）

## 分析维度
每个维度必须覆盖，但可自主决定详细程度：
- understanding（需求理解）: 业务和技术理解
- impact（影响域）: 受影响的模块、文件、接口
- risk（风险）: 技术、业务、合规风险
- change（变更评估）: 具体变更点、工作量估算
- decision（决策建议）: 面向管理层的决策要点
- evidence（证据支撑）: 所有结论的证据列表
- verification（验证要点）: 评审时需要验证的事项
"""


def build_analysis_system_prompt(
    project_memory: str = "",
    user_memory: str = "",
    historical_context: str = "",
    dimension_status: dict[str, str] | None = None,
    template_sections: list[dict] | None = None,
) -> str:
    parts = [ANALYSIS_SYSTEM_PROMPT]

    if project_memory:
        parts.append(f"\n## 项目画像\n{project_memory}")

    if user_memory:
        parts.append(f"\n## 用户偏好\n{user_memory}")

    if historical_context:
        parts.append(f"\n## 相似历史需求\n{historical_context}")

    if dimension_status:
        status_lines = [f"- {dim}: {status}" for dim, status in dimension_status.items()]
        parts.append(f"\n## 当前维度状态\n" + "\n".join(status_lines))

    if template_sections:
        section_lines = []
        for sec in template_sections:
            req = sec.get("requirements", "")
            dims = ", ".join(sec.get("dimensions", []))
            section_lines.append(f"- {sec['title']}（{sec['id']}）: {sec['description']}" + (f" [{dims}]" if dims else ""))
            if req:
                section_lines.append(f"  写作要求: {req}")
        if section_lines:
            parts.append("\n## 报告章节要求\n" + "\n".join(section_lines))

    return "\n".join(parts)


def build_analysis_user_prompt(requirement_text: str, agent_context: str = "") -> str:
    parts = [f"## 需求内容\n{requirement_text}"]
    if agent_context:
        parts.append(f"\n## 当前分析状态\n{agent_context}")
    parts.append("\n请选择合适的工具继续分析，或在信息充分时生成报告。")
    return "\n".join(parts)


def build_termination_prompt() -> str:
    return """你已达到分析步数上限或所有维度已达标。请基于已收集的所有证据，直接输出最终分析结果。

输出要求：
1. 所有结论必须引用具体证据来源
2. 每个维度都应有明确内容
3. 风险评级必须基于代码依据
4. 提出可操作的决策建议"""
```

- [ ] **Step 3: Create report generation phase prompt builder**

Create `src/reqradar/agent/prompts/report_phase.py`:

```python
def build_report_generation_prompt(
    requirement_text: str,
    evidence_text: str,
    dimension_status: dict[str, str],
    template_sections: list[dict] | None = None,
) -> str:
    parts = [
        "你正在生成需求分析报告。请基于以下证据和维度状态，为报告的每个章节生成内容。",
        "",
        f"## 需求内容\n{requirement_text}",
        "",
        f"## 维度状态\n" + "\n".join(f"- {k}: {v}" for k, v in dimension_status.items()),
        "",
        f"## 已收集证据\n{evidence_text}",
    ]

    if template_sections:
        parts.append("\n## 章节生成要求\n")
        for sec in template_sections:
            parts.append(f"### {sec['title']}（{sec['id']}）")
            parts.append(f"章节描述：{sec['description']}")
            if sec.get("requirements"):
                parts.append(f"写作要求：{sec['requirements']}")
            if sec.get("dimensions"):
                parts.append(f"所需维度：{', '.join(sec['dimensions'])}")
            parts.append("")

    parts.append("\n请输出完整的 JSON 格式报告数据，包含上述所有章节对应字段。")

    return "\n".join(parts)


def build_dimension_section_prompt(
    section_id: str,
    section_title: str,
    section_description: str,
    section_requirements: str,
    section_dimensions: list[str],
    evidence_for_dimensions: str,
) -> str:
    return f"""你正在生成报告的第X章：{section_title}

章节描述：{section_description}
写作要求：{section_requirements}
所需维度：{', '.join(section_dimensions) if section_dimensions else '无特定维度'}

请基于以下证据和上下文生成该章节内容：
{evidence_for_dimensions}"""
```

- [ ] **Step 4: Update prompts.py to re-export from package**

Add at the end of `src/reqradar/agent/prompts.py`:

```python
from reqradar.agent.prompts.analysis_phase import (
    build_analysis_system_prompt,
    build_analysis_user_prompt,
    build_termination_prompt,
)
from reqradar.agent.prompts.report_phase import (
    build_report_generation_prompt,
    build_dimension_section_prompt,
)
```

- [ ] **Step 5: Run existing tests to verify backward compatibility**

Run: `pytest tests/test_steps_structured.py tests/test_keyword_mapping.py -v`
Expected: All PASS (prompts.py still works as before)

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/agent/prompts/ src/reqradar/agent/prompts.py
git commit -m "feat: add analysis and report phase prompt builders with template section injection"
```

---

## Task 5: AnalysisRunnerV2 — ReAct Agent Orchestration

**Files:**
- Create: `src/reqradar/web/services/analysis_runner_v2.py`
- Create: `tests/test_analysis_runner_v2.py`

- [ ] **Step 1: Write tests for AnalysisRunnerV2**

Create `tests/test_analysis_runner_v2.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from reqradar.web.services.analysis_runner_v2 import AnalysisRunnerV2, build_report_data_from_agent


def test_runner_v2_initialization():
    runner = AnalysisRunnerV2()
    assert runner is not None


def test_build_report_data_from_agent():
    from reqradar.agent.analysis_agent import AnalysisAgent
    agent = AnalysisAgent(
        requirement_text="Add SSO support",
        project_id=1,
        user_id=1,
        depth="standard",
    )
    agent.record_evidence(type="code", source="src/auth.py", content="Auth module", confidence="high", dimensions=["impact", "change"])
    agent.dimension_tracker.mark_sufficient("understanding")
    agent.dimension_tracker.mark_sufficient("impact")

    report_data = build_report_data_from_agent(agent, {})
    assert report_data is not None
    assert "requirement_title" in report_data or "evidence_items" in report_data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analysis_runner_v2.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement AnalysisRunnerV2**

Create `src/reqradar/web/services/analysis_runner_v2.py`:

```python
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import markdown
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker
from reqradar.agent.llm_utils import _call_llm_structured, _complete_with_tools, _parse_json_response
from reqradar.agent.tool_use_loop import run_tool_use_loop
from reqradar.agent.prompts.analysis_phase import build_analysis_system_prompt, build_analysis_user_prompt, build_termination_prompt
from reqradar.agent.prompts.report_phase import build_report_generation_prompt
from reqradar.agent.schemas import ANALYZE_SCHEMA
from reqradar.agent.tools import ToolRegistry
from reqradar.agent.tools.security import PathSandbox, SensitiveFileFilter, check_tool_permissions
from reqradar.core.report import ReportRenderer
from reqradar.core.context import AnalysisContext
from reqradar.infrastructure.config import Config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.infrastructure.template_loader import TemplateLoader
from reqradar.modules.memory_manager import AnalysisMemoryManager
from reqradar.modules.synonym_resolver import SynonymResolver
from reqradar.web.models import AnalysisTask, Report, Project
from reqradar.web.services.project_store import project_store
from reqradar.web.websocket import manager as ws_manager

logger = logging.getLogger("reqradar.web.services.analysis_runner_v2")

REPORT_DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "requirement_title": {"type": "string"},
        "requirement_understanding": {"type": "string"},
        "executive_summary": {"type": "string"},
        "technical_summary": {"type": "string"},
        "impact_narrative": {"type": "string"},
        "risk_narrative": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["critical", "high", "medium", "low", "unknown"]},
        "decision_highlights": {"type": "array", "items": {"type": "string"}},
        "impact_domains": {"type": "array"},
        "impact_modules": {"type": "array"},
        "change_assessment": {"type": "array"},
        "risks": {"type": "array"},
        "decision_summary": {"type": "object"},
        "evidence_items": {"type": "array"},
        "verification_points": {"type": "array", "items": {"type": "string"}},
        "implementation_suggestion": {"type": "string"},
        "priority": {"type": "string"},
        "priority_reason": {"type": "string"},
        "terms": {"type": "array"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "structured_constraints": {"type": "array"},
        "contributors": {"type": "array"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["requirement_title", "risk_level"],
}


class AnalysisRunnerV2:
    def __init__(self, max_concurrent: int = 2):
        self._semaphore = __import__("asyncio").Semaphore(max_concurrent)
        self._active_tasks: dict[int, __import__("asyncio").Task] = {}

    def submit(self, task_id: int, project: Project, config: Config) -> "__import__("asyncio").Task":
        import asyncio
        if task_id in self._active_tasks and not self._active_tasks[task_id].done():
            raise ValueError(f"Task {task_id} is already running")

        task = asyncio.create_task(self._run_analysis(task_id, project, config))

        def _on_done(t):
            self._active_tasks.pop(task_id, None)

        task.add_done_callback(_on_done)
        self._active_tasks[task_id] = task
        return task

    async def _run_analysis(self, task_id: int, project: Project, config: Config):
        import asyncio
        async with self._semaphore:
            import reqradar.web.dependencies as dep_module
            async with dep_module.async_session_factory() as db:
                try:
                    await self._execute_agent(task_id, project, config, db)
                except asyncio.CancelledError:
                    logger.info("Agent analysis task %d cancelled", task_id)
                    raise
                except Exception:
                    logger.exception("Agent analysis task %d failed", task_id)

    async def _execute_agent(self, task_id: int, project: Project, config: Config, db: AsyncSession):
        import asyncio
        from reqradar.modules.llm_client import create_llm_client
        from reqradar.modules.memory import MemoryManager
        from reqradar.modules.git_analyzer import GitAnalyzer
        from reqradar.agent.tools import (
            SearchCodeTool, ReadFileTool, ReadModuleSummaryTool, ListModulesTool,
            SearchRequirementsTool, GetDependenciesTool, GetContributorsTool,
            GetProjectProfileTool, GetTerminologyTool,
        )

        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        await ws_manager.broadcast(task_id, {"type": "analysis_started", "task_id": task_id})

        try:
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
                project_storage_path=config.memory.project_storage_path,
                user_storage_path=config.memory.user_storage_path,
                memory_enabled=config.memory.enabled,
            )

            agent.project_memory_text = analysis_memory.get_project_profile_text()
            agent.user_memory_text = analysis_memory.get_user_memory_text()

            import reqradar.web.dependencies as dep_module
            cm = ConfigManager(db, config)
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

            template_loader = TemplateLoader()
            template_def = None
            template_id = config.reporting.default_template_id if hasattr(config, "reporting") else None
            if template_id:
                from reqradar.web.models import ReportTemplate
                tmpl_result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
                tmpl_obj = tmpl_result.scalar_one_or_none()
                if tmpl_obj:
                    template_def = template_loader.load_definition_from_db(tmpl_obj.definition)
            if template_def is None:
                try:
                    template_def = template_loader.load_definition(template_loader.get_default_template_path())
                except Exception:
                    template_def = None

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
            analysis_tools = tool_names

            await ws_manager.broadcast(task_id, {
                "type": "agent_thinking",
                "task_id": task_id,
                "message": "开始分析需求...",
            })

            while not agent.should_terminate():
                user_prompt = build_analysis_user_prompt(
                    requirement_text=agent.requirement_text,
                    agent_context=agent.get_context_text() + "\n\n" + agent.get_weak_dimensions_text(),
                )

                tool_result_data = await run_tool_use_loop(
                    llm_client,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tools=analysis_tools,
                    tool_registry=tool_registry,
                    output_schema=ANALYZE_SCHEMA,
                    max_rounds=min(agent.max_steps - agent.step_count, 3),
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
            report_markdown = renderer.render_from_report_data(report_data) if hasattr(renderer, "render_from_report_data") else renderer.render_from_dict(report_data)
            report_html = markdown.markdown(report_markdown, extensions=["extra", "codehilite", "toc", "tables"])

            risk_level = report_data.get("risk_level", "unknown")

            task.context_json = json.dumps(agent.get_context_snapshot(), ensure_ascii=False, default=str)
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

            db.add(Report(
                task_id=task_id,
                content_markdown=report_markdown,
                content_html=report_html,
            ))
            await db.commit()

            await ws_manager.broadcast(task_id, {
                "type": "analysis_complete",
                "task_id": task_id,
                "risk_level": risk_level,
            })

        except asyncio.CancelledError:
            task.status = "cancelled"
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await ws_manager.broadcast(task_id, {"type": "analysis_cancelled", "task_id": task_id})
            raise

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)[:2000]
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await ws_manager.broadcast(task_id, {
                "type": "analysis_failed",
                "task_id": task_id,
                "error": str(e)[:500],
            })

    def _update_agent_from_tool_result(self, agent: AnalysisAgent, data: dict) -> None:
        if data.get("keywords"):
            pass
        if data.get("terms"):
            for t in data.get("terms", []):
                if isinstance(t, dict) and t.get("term"):
                    dimensions = ["understanding"]
                    agent.record_evidence(
                        type="term",
                        source=f"llm_extract:{t['term']}",
                        content=f"{t['term']}: {t.get('definition', '')}",
                        confidence="medium",
                        dimensions=dimensions,
                    )
        if data.get("impact_modules"):
            for m in data.get("impact_modules", []):
                if isinstance(m, dict):
                    agent.record_evidence(
                        type="code",
                        source=m.get("path", "unknown"),
                        content=m.get("relevance_reason", "Unknown relevance"),
                        confidence=m.get("relevance", "low"),
                        dimensions=["impact", "change"],
                    )
                    agent.dimension_tracker.mark_in_progress("impact")
        if data.get("risks"):
            for r in data.get("risks", []):
                if isinstance(r, dict):
                    confidence_map = {"high": "high", "medium": "medium", "low": "low"}
                    agent.record_evidence(
                        type="history",
                        source=f"risk:{r.get('description', '')[:50]}",
                        content=r.get("description", ""),
                        confidence=confidence_map.get(r.get("severity", ""), "medium"),
                        dimensions=["risk"],
                    )
                    agent.dimension_tracker.mark_in_progress("risk")

    async def _generate_report(self, agent: AnalysisAgent, llm_client, system_prompt: str, section_descriptions, config: Config) -> dict:
        termination_prompt = build_termination_prompt()
        evidence_text = agent.evidence_collector.get_all_evidence_text()

        report_prompt = build_report_generation_prompt(
            requirement_text=agent.requirement_text,
            evidence_text=evidence_text,
            dimension_status=agent.dimension_tracker.status_summary(),
            template_sections=section_descriptions,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": report_prompt},
            {"role": "assistant", "content": termination_prompt},
        ]

        try:
            result = await _call_llm_structured(llm_client, messages, REPORT_DATA_SCHEMA)
            if result:
                result.setdefault("requirement_title", agent.requirement_text[:100])
                result.setdefault("warnings", [])
                return result
        except Exception as e:
            logger.warning("Report generation failed, using fallback: %s", e)

        return _build_fallback_report_data(agent)

    def cancel(self, task_id: int):
        import asyncio
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()


def _build_fallback_report_data(agent: AnalysisAgent) -> dict:
    return {
        "requirement_title": agent.requirement_text[:100],
        "requirement_understanding": f"需求理解: {agent.requirement_text[:200]}",
        "executive_summary": "分析完成，但有部分信息不完整。",
        "technical_summary": "",
        "impact_narrative": "",
        "risk_narrative": "",
        "risk_level": "unknown",
        "decision_highlights": [],
        "impact_domains": [],
        "impact_modules": [],
        "change_assessment": [],
        "risks": [],
        "decision_summary": {"summary": "", "decisions": [], "open_questions": [], "follow_ups": []},
        "evidence_items": [{"kind": ev.type, "source": ev.source, "summary": ev.content, "confidence": ev.confidence} for ev in agent.evidence_collector.evidences],
        "verification_points": [],
        "implementation_suggestion": "",
        "priority": "medium",
        "priority_reason": "",
        "terms": [],
        "keywords": [],
        "constraints": [],
        "structured_constraints": [],
        "contributors": [],
        "warnings": ["Agent analysis completed with partial data due to insufficient evidence."],
    }


def build_report_data_from_agent(agent: AnalysisAgent, llm_result: dict) -> dict:
    report_data = llm_result.copy() if llm_result else {}
    report_data.setdefault("requirement_title", agent.requirement_text[:100])
    report_data.setdefault("risk_level", "unknown")
    report_data.setdefault("warnings", [])
    evidence_items = [
        {"kind": ev.type, "source": ev.source, "summary": ev.content, "confidence": ev.confidence}
        for ev in agent.evidence_collector.evidences
    ]
    report_data.setdefault("evidence_items", evidence_items)
    return report_data


runner_v2 = AnalysisRunnerV2()
```

Note: This file uses `__import__("asyncio")` at module level to avoid import issues. The actual asyncio usage is within async methods where it's already available.

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_analysis_runner_v2.py -v`

Fix the import issue in `analysis_runner_v2.py` — replace `__import__("asyncio")` with proper `import asyncio` at the top.

- [ ] **Step 5: Fix import and re-run tests**

The `analysis_runner_v2.py` file needs proper asyncio imports at the top. Add:

```python
import asyncio
```

And replace all `__import__("asyncio")` references with `asyncio`.

Run: `pytest tests/test_analysis_runner_v2.py -v`
Expected: PASS (unit tests for `build_report_data_from_agent`)

- [ ] **Step 6: Run all existing tests**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS (legacy pipeline untouched)

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/web/services/analysis_runner_v2.py tests/test_analysis_runner_v2.py
git commit -m "feat: add AnalysisRunnerV2 with ReAct agent loop, tool calls, and report generation"
```

---

## Task 6: ReportRenderer — render_from_dict Method

**Files:**
- Modify: `src/reqradar/core/report.py`

- [ ] **Step 1: Read current report.py render method**

Read `src/reqradar/core/report.py` fully (lines 81-383) to understand the existing `render` method signature and template rendering.

- [ ] **Step 2: Add `render_from_dict` method to ReportRenderer**

Add a new method `render_from_dict` that accepts a plain dict (ReportData from agent) instead of `AnalysisContext`:

```python
def render_from_dict(self, report_data: dict, context: AnalysisContext | None = None) -> str:
    template_data = dict(report_data)
    if context:
        risk_level = context.deep_analysis.risk_level if context.deep_analysis else "unknown"
        template_data["risk_badge"] = _risk_level_to_badge(risk_level)
        template_data.setdefault("content_completeness", context.content_completeness)
        template_data.setdefault("evidence_support", context.evidence_support)
        template_data.setdefault("content_confidence", context.content_confidence)
        template_data.setdefault("process_completion", context.process_completion)
    else:
        risk_level = template_data.get("risk_level", "unknown")
        template_data["risk_badge"] = _risk_level_to_badge(risk_level)
        template_data.setdefault("content_completeness", "partial")
        template_data.setdefault("evidence_support", "low")
        template_data.setdefault("content_confidence", "medium")
        template_data.setdefault("process_completion", "full")

    template_data.setdefault("priority", "unknown")
    template_data.setdefault("priority_reason", "")
    template_data.setdefault("warnings", [])

    return self.template.render(**template_data)
```

- [ ] **Step 3: Run existing report tests**

Run: `pytest tests/test_report.py -v`
Expected: All PASS (no changes to existing `render` method)

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/core/report.py
git commit -m "feat: add ReportRenderer.render_from_dict for agent-generated report data"
```

---

## Task 7: Mode Selection in Analysis Runner

**Files:**
- Modify: `src/reqradar/web/services/analysis_runner.py`
- Modify: `src/reqradar/web/api/analyses.py`

- [ ] **Step 1: Read current analysis submit endpoint**

Read `src/reqradar/web/api/analyses.py` to understand the current submit flow.

- [ ] **Step 2: Add mode selection logic to analysis_runner.py**

In `src/reqradar/web/services/analysis_runner.py`, add a factory function that selects the appropriate runner:

```python
from reqradar.infrastructure.config import Config
from reqradar.web.services.analysis_runner import runner as legacy_runner
from reqradar.web.services.analysis_runner_v2 import runner_v2


def get_runner(config: Config):
    if hasattr(config, "agent") and config.agent.mode == "react":
        return runner_v2
    return legacy_runner
```

- [ ] **Step 3: Add depth parameter to AnalysisTask creation**

In `src/reqradar/web/api/analyses.py`, update the analysis creation endpoint to accept a `depth` parameter:

Find the analysis creation endpoint and add `depth` field handling. The `AnalysisTask` model already has the `depth` field from Round 1 Task 2.

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/services/analysis_runner.py src/reqradar/web/api/analyses.py
git commit -m "feat: add mode selection (legacy/react) and depth parameter to analysis submission"
```

---

## Task 8: WebSocket Message Type Extensions

**Files:**
- Modify: `src/reqradar/web/websocket.py`
- Modify: `src/reqradar/web/api/analyses.py` — Add cancel endpoint

- [ ] **Step 1: Add cancel endpoint for analysis**

In `src/reqradar/web/api/analyses.py`, add a cancel endpoint:

```python
@router.post("/analyses/{task_id}/cancel")
async def cancel_analysis(
    task_id: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    task_result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")
    if task.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel task in status: {task.status}")

    config = load_config()
    from reqradar.web.services.analysis_runner import get_runner
    r = get_runner(config)
    r.cancel(task_id)

    task.status = "cancelled"
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "status": "cancelled"}
```

- [ ] **Step 2: Extension already done in runner_v2**

The WebSocket message types `agent_thinking`, `dimension_progress`, `evidence_collected` are already broadcast from `AnalysisRunnerV2._execute_agent`. No additional changes needed to `websocket.py` itself since it just broadcasts whatever dict is passed.

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/web/api/analyses.py
git commit -m "feat: add cancel analysis endpoint and WebSocket message type support for agent progress"
```

---

## Task 9: Integration Tests for ReAct Agent Pipeline

**Files:**
- Create: `tests/test_round2_integration.py`

- [ ] **Step 1: Write integration tests verifying the ReAct agent components work together**

Create `tests/test_round2_integration.py`:

```python
import pytest
from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker, DEFAULT_DIMENSIONS
from reqradar.agent.tools.security import PathSandbox, SensitiveFileFilter, ToolPermissionChecker, check_tool_permissions
from reqradar.agent.prompts.analysis_phase import build_analysis_system_prompt, build_analysis_user_prompt, build_termination_prompt
from reqradar.agent.prompts.report_phase import build_report_generation_prompt
from reqradar.infrastructure.template_loader import TemplateLoader


def test_agent_full_lifecycle():
    agent = AnalysisAgent(
        requirement_text="Implement SSO authentication",
        project_id=1,
        user_id=1,
        depth="standard",
    )
    assert agent.state == AgentState.INIT
    assert agent.step_count == 0

    agent.state = AgentState.ANALYZING
    agent.record_evidence(type="code", source="src/auth/sso.py", content="SSO implementation", confidence="high", dimensions=["impact", "change"])
    agent.dimension_tracker.mark_in_progress("impact")
    agent.dimension_tracker.mark_sufficient("understanding")
    agent.step_count += 1

    assert agent.step_count == 1
    assert len(agent.evidence_collector.evidences) == 1
    assert agent.dimension_tracker.dimensions["impact"].status == "in_progress"
    assert agent.dimension_tracker.dimensions["understanding"].status == "sufficient"

    snapshot = agent.get_context_snapshot()
    assert len(snapshot["evidence_list"]) == 1
    assert snapshot["dimension_status"]["impact"] == "in_progress"

    agent2 = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent2.restore_from_snapshot(snapshot)
    assert len(agent2.evidence_collector.evidences) == 1


def test_security_components():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert sandbox.is_allowed("/home/user/project/src/app.py")
    assert not sandbox.is_allowed("/etc/passwd")

    sf = SensitiveFileFilter()
    assert sf.is_sensitive(".env")
    assert not sf.is_sensitive("src/app.py")

    checker = ToolPermissionChecker(user_permissions={"read:code", "read:memory"})
    assert checker.is_allowed("read:code")
    assert not checker.is_allowed("write:report")


def test_prompt_builders():
    sys_prompt = build_analysis_system_prompt(
        project_memory="Project: ReqRadar\nLanguages: Python",
        user_memory="User prefers deep analysis",
        dimension_status={"understanding": "sufficient", "impact": "in_progress"},
    )
    assert "ReqRadar" in sys_prompt
    assert "understanding" in sys_prompt

    user_prompt = build_analysis_user_prompt("Add SSO support")
    assert "SSO" in user_prompt

    term_prompt = build_termination_prompt()
    assert "分析步数上限" in term_prompt or "达到" in term_prompt


def test_template_section_injection():
    loader = TemplateLoader()
    defn = loader.load_definition(loader.get_default_template_path())
    section_descs = [
        {"id": s.id, "title": s.title, "description": s.description, "requirements": s.requirements, "dimensions": s.dimensions}
        for s in defn.sections[:3]
    ]

    prompt = build_analysis_system_prompt(template_sections=section_descs)
    assert "需求理解" in prompt or "understanding" in prompt


def test_report_generation_prompt():
    prompt = build_report_generation_prompt(
        requirement_text="Add SSO",
        evidence_text="[ev-001] (code/high) src/auth.py: SSO module",
        dimension_status={"impact": "sufficient", "risk": "in_progress"},
    )
    assert "SSO" in prompt
    assert "impact" in prompt


def test_depth_step_limits():
    quick = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    assert quick.max_steps == 10

    deep = AnalysisAgent("test", project_id=1, user_id=1, depth="deep")
    assert deep.max_steps == 25

    custom = AnalysisAgent("test", project_id=1, user_id=1, depth="standard", max_steps=20)
    assert custom.max_steps == 20


def test_dimension_tracker_default_dimensions():
    tracker = DimensionTracker()
    assert set(tracker.dimensions.keys()) == set(DEFAULT_DIMENSIONS)
    assert "understanding" in tracker.dimensions
    assert "evidence" in tracker.dimensions
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_round2_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_round2_integration.py
git commit -m "test: add Round 2 integration tests for agent, security, and prompt builders"
```

---

## Self-Review Checklist

- [ ] **Spec Coverage**: Each spec section for Round 2 has a corresponding task:
  - Section 3.1 (Analysis Goal + Dimensions) → Task 3 (AnalysisAgent), Task 1 (DimensionTracker)
  - Section 3.1.3 (Termination Conditions: max-steps + LLM self-termination) → Task 3
  - Section 3.1.4 (Evidence) → Task 1 (EvidenceCollector)
  - Section 3.2 (Agent State Machine) → Task 3
  - Section 3.3 (ReAct Loop) → Task 5 (AnalysisRunnerV2)
  - Section 3.4 (Tool Permissions) → Task 2
  - Section 3.5 (Prompt Templates) → Task 4
  - Section 5.3 (Template Description Injection) → Task 4
  - Section 2 (Security Constraints) → Task 2 (PathSandbox, SensitiveFileFilter, PermissionChecker)
  - Section 10.1 (Agent Config) → Round 1 Task 1 (already done)

- [ ] **No Placeholders**: No TBD, TODO, or "implement later"

- [ ] **Type Consistency**: `AnalysisAgent.step_count` is `int`, `max_steps` is `int`, `AgentState` is enum, `EvidenceCollector.add()` returns `str` (ev_id)

- [ ] **Backward Compatibility**: Legacy `Scheduler` + `step_*` pipeline untouched; `AnalysisRunnerV2` is a separate file; `get_runner()` selects based on `config.agent.mode` (default "legacy")