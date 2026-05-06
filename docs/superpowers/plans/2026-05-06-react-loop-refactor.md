# ReAct Loop Refactoring & Memory Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the dual-loop ReAct architecture with a single CoT-guided adaptive loop, add LLM self-assessment for dimension sufficiency, and add post-analysis memory self-evolution.

**Architecture:** Single while loop in runner.py (removes tool_use_loop.py). Each step = 1 LLM call that can return tool_calls OR structured STEP_OUTPUT_SCHEMA. System prompt rebuilt each step with up-to-date dimension status and phase guidance. After the loop, a separate memory evolution step (1 LLM call) extracts durable knowledge and updates ProjectMemory.

**Tech Stack:** Python 3.12+, OpenAI-compatible tool calling, Pydantic schemas, structlog

**Spec:** `docs/superpowers/specs/2026-05-06-react-loop-refactor-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `agent/schemas.py` | Modify | Add STEP_OUTPUT_SCHEMA, MEMORY_EVOLUTION_SCHEMA |
| `agent/prompts/analysis_phase.py` | Rewrite | Dynamic CoT prompts (system + step user prompt) |
| `agent/prompts/memory_evolution.py` | Create | Memory evolution CoT prompt |
| `agent/analysis_agent.py` | Modify | New fields, new should_terminate, get_phase |
| `agent/tool_call_tracker.py` | Modify | Remove token budget, keep dedup+count |
| `agent/runner.py` | Rewrite | Single-loop run_react_analysis + memory evolution fork |
| `agent/memory_evolution.py` | Create | Extract candidates, call LLM, apply updates |
| `agent/tool_use_loop.py` | Delete | Merged into runner.py |
| `agent/prompts/__init__.py` | Modify | Update exports |
| `web/services/analysis_runner.py` | Modify | De-duplicate: call run_react_analysis instead of own loop |
| `infrastructure/config.py` | Modify | Add memory_evolution config, remove obsolete tool_use fields |
| `tests/test_tool_use_loop.py` | Rewrite | Test new single-loop behavior |
| `tests/test_round2_integration.py` | Modify | Update prompt tests |

---

### Task 1: Add STEP_OUTPUT_SCHEMA and MEMORY_EVOLUTION_SCHEMA

**Files:**
- Modify: `src/reqradar/agent/schemas.py` (append at end)

- [ ] **Step 1: Add STEP_OUTPUT_SCHEMA**

In `src/reqradar/agent/schemas.py`, append after the existing GENERATE_BATCH_MODULE_SUMMARIES_SCHEMA (line 490):

```python
STEP_OUTPUT_SCHEMA = {
    "name": "step_assessment",
    "description": "每步分析评估：维度状态、新发现、后续行动、是否终止",
    "parameters": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "本轮CoT推理摘要：当前阶段判断、缺口分析、行动理由（100字以内）",
            },
            "dimension_status": {
                "type": "object",
                "description": "各维度当前评估",
                "properties": {
                    "understanding": {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]},
                    "impact": {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]},
                    "risk": {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]},
                    "change": {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]},
                    "decision": {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]},
                    "evidence": {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]},
                    "verification": {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]},
                },
                "required": ["understanding", "impact", "risk", "change", "decision", "evidence", "verification"],
            },
            "key_findings": {
                "type": "array",
                "description": "本轮新发现（0-5条）",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string", "description": "所属维度"},
                        "finding": {"type": "string", "description": "具体发现，引用证据来源"},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["dimension", "finding", "confidence"],
                },
            },
            "next_actions": {
                "type": "array",
                "description": "建议的后续行动（0-3条）",
                "items": {
                    "type": "object",
                    "properties": {
                        "priority": {"type": "integer", "description": "1=最高"},
                        "action": {"type": "string", "description": "建议的下一步"},
                        "reason": {"type": "string"},
                        "suggested_tools": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "推荐工具",
                        },
                    },
                    "required": ["priority", "action", "reason"],
                },
            },
            "final_step": {
                "type": "boolean",
                "description": "所有维度已达sufficient，无需继续分析",
            },
        },
        "required": ["reasoning", "dimension_status"],
    },
}

MEMORY_EVOLUTION_SCHEMA = {
    "name": "evolve_memory",
    "description": "记忆进化：比对分析发现与已有记忆，产出更新操作",
    "parameters": {
        "type": "object",
        "properties": {
            "comparisons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["term", "module", "constraint", "tech_stack", "overview"]},
                        "candidate_key": {"type": "string"},
                        "existing_match": {"type": "string"},
                        "action": {"type": "string", "enum": ["add", "update", "skip", "merge"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["category", "candidate_key", "action"],
                },
            },
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "enum": ["terms", "modules", "constraints", "tech_stack", "overview"]},
                        "action": {"type": "string", "enum": ["add", "update", "skip"]},
                        "data": {"type": "object"},
                    },
                    "required": ["target", "action", "data"],
                },
            },
            "changelog_entry": {
                "type": "string",
                "description": "本次记忆变更摘要（50字以内）",
            },
        },
        "required": ["operations", "changelog_entry"],
    },
}
```

- [ ] **Step 2: Commit**

```bash
git add src/reqradar/agent/schemas.py
git commit -m "feat: add STEP_OUTPUT_SCHEMA and MEMORY_EVOLUTION_SCHEMA"
```

---

### Task 2: Rewrite prompts/analysis_phase.py with Dynamic CoT Prompts

**Files:**
- Modify: `src/reqradar/agent/prompts/analysis_phase.py` (replace entire content)

- [ ] **Step 1: Write the new prompt module**

Replace `src/reqradar/agent/prompts/analysis_phase.py` entirely:

```python
from reqradar.agent.dimension import DimensionTracker

SYSTEM_PROMPT_TEMPLATE = """你是一位专业需求分析架构师。你的目标是通过"思考→行动→评估"循环，对给定需求生成完整、可验证的分析。

## 分析阶段引导
按以下顺序推进，由你自主判断当前所处阶段：

阶段1——理解与提取：理解需求核心问题，提取关键术语
  [{phase1_bar}] 优先工具：get_terminology, search_requirements, get_project_profile
  目标：清晰的需求理解和术语清单

阶段2——范围定位：找到受涉及的代码模块和文件
  [{phase2_bar}] 优先工具：search_code, read_file, list_modules, get_dependencies
  目标：每个影响模块有代码依据

阶段3——风险评估：基于代码依据做风险判断
  [{phase3_bar}] 优先工具：read_file, search_code, get_contributors
  目标：至少2个结构化的风险条目（类型+严重度+缓解建议）

阶段4——综合建议：汇集证据形成决策建议
  [{phase4_bar}] 优先工具：read_file, get_project_profile
  目标：面向决策的结论和可操作的验证要点

## 工具速查
- search_code(queries: str[])          — 按关键词搜索代码图谱
- read_file(path: str)                  — 读取文件内容
- read_module_summary(module: str)      — 读取模块摘要
- list_modules()                        — 列出所有模块
- search_requirements(query: str)       — 语义搜索历史需求
- get_dependencies(module: str)         — 模块依赖图
- get_contributors(path: str)           — Git 贡献者分析
- get_project_profile()                 — 项目画像
- get_terminology(term: str)            — 术语/域名查询

## 维度充分性标准
达到以下标准后，在 dimension_status 中标记该维度为 sufficient：
- understanding: ≥1个关键术语定义 + 需求背景拆解清晰
- impact: ≥2个受影响模块/文件被识别，有具体路径和理由
- risk: ≥2个结构化风险条目（含类型、严重度、缓解建议）
- change: ≥2个变更评估（含模块、变更类型、影响等级）
- decision: 有决策总结 + ≥1个决策建议项
- evidence: ≥3条不同来源的证据，覆盖前5个维度
- verification: ≥3条可执行的验证要点

当所有维度都为 sufficient 时，设置 final_step=true 终止分析。
"""

USER_PROMPT_TEMPLATE = """## 需求
{requirement_text}

## 当前进度
步骤 {step_count}/{max_steps}
累计证据：{evidence_count} 条
{weak_dimensions_section}

## 按以下步骤思考

**第一步——理解当前状态**（先思考，不要直接行动）
回顾已收集证据，判断：
- 当前处于哪个分析阶段？为什么？
- 哪些维度仍然薄弱？需要什么类型的信息？
（用一句话简述你的判断）

**第二步——选择行动**
基于缺口判断，选择1-3个工具调用。
- 优先使用当前阶段推荐的工具
- 如果没有合适的工具，直接输出评估

**第三步——评估本轮结果**
审查收集到的信息：
- 获得了什么新发现？（记录到 key_findings）
- 修改维度状态：哪些维度已达到 sufficient？
- 是否需要下一步？（记录到 next_actions）
- 如果所有维度充足 → final_step=true"""

QUICK_MODE_NOTE = """
> *快速分析模式：聚焦风险最高的2-3个方面，在较少的步骤内产出核心结论。*
"""


def _phase_bar(percent: int) -> str:
    filled = max(percent // 10, 0)
    return "█" * filled + "░" * (10 - filled)


def _infer_phase_progress(dimension_status: dict[str, str], phase_dims: list[str]) -> int:
    if not dimension_status:
        return 0
    sufficient_count = sum(
        1 for dim in phase_dims if dimension_status.get(dim) == "sufficient"
    )
    in_progress_count = sum(
        1 for dim in phase_dims if dimension_status.get(dim) == "in_progress"
    )
    return min(sufficient_count * 40 + in_progress_count * 20, 100)


def build_dynamic_system_prompt(
    dimension_status: dict[str, str] | None = None,
    project_memory: str = "",
    user_memory: str = "",
    historical_context: str = "",
    template_sections: list[dict] | None = None,
    pending_actions: list[dict] | None = None,
) -> str:
    ds = dimension_status or {}

    phase1 = _infer_phase_progress(ds, ["understanding"])
    phase2 = _infer_phase_progress(ds, ["impact", "evidence"])
    phase3 = _infer_phase_progress(ds, ["risk", "change"])
    phase4 = _infer_phase_progress(ds, ["decision", "verification"])

    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        phase1_bar=_phase_bar(phase1),
        phase2_bar=_phase_bar(phase2),
        phase3_bar=_phase_bar(phase3),
        phase4_bar=_phase_bar(phase4),
    )

    context_parts = []

    if project_memory:
        context_parts.append(f"## 项目画像\n{project_memory}")
    if user_memory:
        context_parts.append(f"## 用户偏好\n{user_memory}")
    if historical_context:
        context_parts.append(f"## 相似历史需求\n{historical_context}")
    if ds:
        status_lines = [f"- {dim}: {status}" for dim, status in ds.items()]
        context_parts.append("## 当前维度状态\n" + "\n".join(status_lines))
    if pending_actions:
        pa_lines = [f"- [{a.get('priority', '?')}] {a.get('action', '')}" for a in pending_actions[:3]]
        if pa_lines:
            context_parts.append("## 上轮建议的后续行动\n" + "\n".join(pa_lines))

    if context_parts:
        prompt += "\n## 当前位置\n" + "\n\n".join(context_parts)

    if template_sections:
        section_lines = []
        for sec in template_sections:
            req = sec.get("requirements", "")
            dims = ", ".join(sec.get("dimensions", []))
            section_lines.append(
                f"- {sec['title']}（{sec['id']}）: {sec['description']}"
                + (f" [{dims}]" if dims else "")
            )
            if req:
                section_lines.append(f"  写作要求: {req}")
        if section_lines:
            prompt += "\n## 报告章节要求\n" + "\n".join(section_lines)

    return prompt


def build_step_user_prompt(
    requirement_text: str,
    step_count: int,
    max_steps: int,
    weak_dimensions: str = "",
    evidence_count: int = 0,
    depth: str = "standard",
) -> str:
    weak_section = f"需要补充证据的维度：{weak_dimensions}" if weak_dimensions else ""
    prompt = USER_PROMPT_TEMPLATE.format(
        requirement_text=requirement_text,
        step_count=step_count,
        max_steps=max_steps,
        evidence_count=evidence_count,
        weak_dimensions_section=weak_section,
    )
    if depth == "quick":
        prompt = QUICK_MODE_NOTE + "\n" + prompt
    return prompt


def build_termination_prompt() -> str:
    return """你已达到分析步数上限或所有维度已达标。请基于已收集的所有证据，直接输出最终分析结果。

输出要求：
1. 所有结论必须引用具体证据来源
2. 每个维度都应有明确内容
3. 风险评级必须基于代码依据
4. 提出可操作的决策建议"""
```

- [ ] **Step 2: Commit**

```bash
git add src/reqradar/agent/prompts/analysis_phase.py
git commit -m "feat: rewrite analysis prompts with CoT template and dynamic phase guidance"
```

---

### Task 3: Add memory_evolution config and remove obsolete tool_use fields

**Files:**
- Modify: `src/reqradar/infrastructure/config.py`

- [ ] **Step 1: Add MemoryEvolutionConfig and update AnalysisConfig**

In `src/reqradar/infrastructure/config.py`, add after `MemoryConfig` (line 53):

```python
class MemoryEvolutionConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable post-analysis memory self-evolution")
```

Remove `tool_use_max_rounds` and `tool_use_max_tokens` from `AnalysisConfig`, then update:

```python
class AnalysisConfig(BaseModel):
    max_similar_reqs: int = Field(default=5)
    max_code_files: int = Field(default=10)
    contributors_lookback_months: int = Field(default=6)
    tool_use_enabled: bool = Field(default=True, description="启用LLM工具调用循环")
```

Add `memory_evolution` to the `Config` model:

```python
class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    memory_evolution: MemoryEvolutionConfig = Field(default_factory=MemoryEvolutionConfig)  # NEW
    loader: LoaderConfig = Field(default_factory=LoaderConfig)
    # ... rest unchanged
```

Full context for the edits:

After line 53 (`class MemoryConfig`), insert:

```python

class MemoryEvolutionConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable post-analysis memory self-evolution")
```

Edit `AnalysisConfig` (lines 72-78) to remove the last two fields:

```python
class AnalysisConfig(BaseModel):
    max_similar_reqs: int = Field(default=5)
    max_code_files: int = Field(default=10)
    contributors_lookback_months: int = Field(default=6)
    tool_use_enabled: bool = Field(default=True, description="启用LLM工具调用循环")
```

Edit `Config` (line 146) to add the new field after `memory`:

```python
    memory_evolution: MemoryEvolutionConfig = Field(default_factory=MemoryEvolutionConfig)
```

- [ ] **Step 2: Commit**

```bash
git add src/reqradar/infrastructure/config.py
git commit -m "feat: add MemoryEvolutionConfig, remove obsolete tool_use_max fields from AnalysisConfig"
```

---

### Task 4: Modify analysis_agent.py

**Files:**
- Modify: `src/reqradar/agent/analysis_agent.py` (add fields, modify should_terminate, add get_phase)

- [ ] **Step 1: Add new fields to __init__**

In `src/reqradar/agent/analysis_agent.py`, add to `__init__` (after line 52):

```python
        self._cancelled: bool = False
        self._llm_declared_terminal: bool = False
        self._consecutive_empty_steps: int = 0
        self._consecutive_failures: int = 0
        self._pending_actions: list[dict] = []
```

- [ ] **Step 2: Rewrite should_terminate**

Replace `should_terminate()` (lines 58-65) with:

```python
    def should_terminate(self) -> bool:
        if self._cancelled:
            return True
        if self.step_count >= self.max_steps:
            return True
        if self._llm_declared_terminal:
            return True
        if self.dimension_tracker.all_sufficient():
            return True
        if self._consecutive_empty_steps >= 3:
            return True
        if self._consecutive_failures >= 3:
            return True
        return False
```

- [ ] **Step 3: Add get_phase method**

Add after `should_terminate()`:

```python
    def get_current_phase(self) -> str:
        ds = self.dimension_tracker.status_summary()
        if ds.get("understanding") != "sufficient":
            return "understand"
        if ds.get("impact") != "sufficient" or ds.get("evidence") != "sufficient":
            return "scope"
        if ds.get("risk") != "sufficient" or ds.get("change") != "sufficient":
            return "assess"
        return "decide"
```

- [ ] **Step 4: Update restore_from_snapshot to include new fields**

Add at the end of `restore_from_snapshot()` (before the last line):

```python
        if "_llm_declared_terminal" in snapshot:
            self._llm_declared_terminal = snapshot["_llm_declared_terminal"]
        if "_consecutive_empty_steps" in snapshot:
            self._consecutive_empty_steps = snapshot["_consecutive_empty_steps"]
```

- [ ] **Step 5: Update get_context_snapshot to include new fields**

Add to the returned dict in `get_context_snapshot()`:

```python
            "_llm_declared_terminal": self._llm_declared_terminal,
            "_consecutive_empty_steps": self._consecutive_empty_steps,
```

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/agent/analysis_agent.py
git commit -m "feat: add termination fields and get_phase to AnalysisAgent"
```

---

### Task 5: Simplify tool_call_tracker.py

**Files:**
- Modify: `src/reqradar/agent/tool_call_tracker.py` (remove token budget)

- [ ] **Step 1: Strip token tracking**

Replace the file content with the simplified version:

```python
import json
import logging

logger = logging.getLogger("reqradar.tool_tracker")


class ToolCallTracker:
    def __init__(self, max_calls_per_tool: int = 10):
        self.max_calls_per_tool = max_calls_per_tool
        self.call_count = 0
        self.tool_counts: dict[str, int] = {}
        self._seen_calls: dict[str, set] = {}

    def track_call(self, tool_name: str, arguments: dict) -> None:
        self.call_count += 1
        self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
        if tool_name not in self._seen_calls:
            self._seen_calls[tool_name] = set()
        key = json.dumps(arguments, sort_keys=True)
        self._seen_calls[tool_name].add(key)

    def is_duplicate(self, tool_name: str, arguments: dict) -> bool:
        if tool_name not in self._seen_calls:
            return False
        key = json.dumps(arguments, sort_keys=True)
        return key in self._seen_calls[tool_name]

    def is_tool_over_limit(self, tool_name: str) -> bool:
        return self.tool_counts.get(tool_name, 0) >= self.max_calls_per_tool

    def summary(self) -> str:
        lines = [f"Total tool calls: {self.call_count}"]
        for name, count in self.tool_counts.items():
            lines.append(f"  {name}: {count} calls")
        return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add src/reqradar/agent/tool_call_tracker.py
git commit -m "refactor: simplify ToolCallTracker, remove token budget tracking"
```

---

### Task 6: Create memory evolution prompts

**Files:**
- Create: `src/reqradar/agent/prompts/memory_evolution.py`

- [ ] **Step 1: Create the file**

Create `src/reqradar/agent/prompts/memory_evolution.py`:

```python
MEMORY_EVOLUTION_SYSTEM_PROMPT = """你是项目记忆维护助手。你的任务是将本次需求分析中发现的持久化知识，合理地合并到项目记忆中。

## 行为规则
1. 严格比对：每条候选知识与已有记忆逐条对照
2. 质量优先：模糊、泛泛而谈的内容不要写入
3. 去重优先：已有记忆中的等价内容必须标记 skip
4. 冲突时合并：定义矛盾时取更完整/准确的内容"""


def build_memory_evolution_user_prompt(
    existing_memory: str,
    new_terms: list[dict],
    new_modules: list[dict],
    new_constraints: list[dict],
    tech_stack_additions: dict,
    overview_insights: str,
) -> str:
    parts = [
        "## 已有项目记忆",
        existing_memory or "（暂无已有记忆）",
        "",
        "## 本次分析发现的候选知识",
    ]

    if new_terms:
        parts.append("### 新术语")
        for t in new_terms:
            parts.append(
                f"- {t.get('term', '?')}: {t.get('definition', '')} "
                f"[domain: {t.get('domain', '')}]"
            )

    if new_modules:
        parts.append("### 受影响的模块")
        for m in new_modules:
            classes = ", ".join(m.get("key_classes", []))
            parts.append(
                f"- {m.get('name', '?')}: {m.get('responsibility', '')}"
                + (f" (核心类: {classes})" if classes else "")
            )

    if new_constraints:
        parts.append("### 新发现的约束")
        for c in new_constraints:
            parts.append(
                f"- [{c.get('type', 'other')}] {c.get('description', '')}"
            )

    if tech_stack_additions:
        parts.append("### 技术栈补充")
        for cat, items in tech_stack_additions.items():
            if items:
                parts.append(f"- {cat}: {', '.join(items)}")

    if overview_insights:
        parts.append(f"### 项目概览更新建议\n{overview_insights}")

    parts.extend([
        "",
        "## 按以下步骤执行",
        "",
        "**第1步——逐条比对**",
        "对每条候选知识与已有记忆对照：",
        "- 完全重复 → action: skip",
        "- 更新已有条目（新信息更完整） → action: update，写出具体更新内容",
        "- 已有记忆中不存在 → action: add",
        "- 与已有记忆冲突 → action: merge，写出合并后内容",
        "- 模糊/无实质内容 → action: skip",
        "",
        "**第2步——控制质量**",
        "- 术语定义必须 ≥10 字才写入",
        "- 模块名称必须来自代码路径或已有模块列表",
        "- 约束必须有具体描述",
        "",
        "**第3步——输出操作列表**",
        "在 operations 字段中输出具体写入操作，在 changelog_entry 中写变更摘要。",
    ])

    return "\n".join(parts)
```

- [ ] **Step 2: Commit**

```bash
git add src/reqradar/agent/prompts/memory_evolution.py
git commit -m "feat: add memory evolution prompts with CoT compare-update flow"
```

---

### Task 7: Create memory evolution module

**Files:**
- Create: `src/reqradar/agent/memory_evolution.py`

- [ ] **Step 1: Create the file**

Create `src/reqradar/agent/memory_evolution.py`:

```python
import logging
from typing import Optional

from reqradar.agent.analysis_agent import AnalysisAgent
from reqradar.agent.llm_utils import _call_llm_structured
from reqradar.agent.prompts.memory_evolution import (
    MEMORY_EVOLUTION_SYSTEM_PROMPT,
    build_memory_evolution_user_prompt,
)
from reqradar.agent.schemas import MEMORY_EVOLUTION_SCHEMA
from reqradar.modules.project_memory import ProjectMemory

logger = logging.getLogger("reqradar.agent.memory_evolution")


def extract_candidates_from_analysis(agent: AnalysisAgent) -> dict:
    report = agent.final_report_data or {}
    evidence_list = agent.evidence_collector.evidences

    terms_candidates = []
    for t in report.get("terms", []):
        if isinstance(t, dict) and t.get("term") and t.get("definition"):
            terms_candidates.append({
                "term": t["term"],
                "definition": t["definition"],
                "domain": t.get("domain", ""),
            })

    modules_candidates = []
    for m in report.get("impact_modules", []):
        if isinstance(m, dict):
            relevance = m.get("relevance", "low")
            if relevance in ("high", "medium"):
                modules_candidates.append({
                    "name": m.get("path", m.get("module", "")),
                    "responsibility": m.get("relevance_reason", ""),
                    "key_classes": m.get("symbols", []),
                })

    constraints_candidates = []
    for c in report.get("structured_constraints", []):
        if isinstance(c, dict) and c.get("description"):
            constraints_candidates.append({
                "description": c["description"],
                "type": c.get("constraint_type", "other"),
            })

    tech_stack = {}
    domains = report.get("impact_domains", [])
    if domains:
        tech_stack["frameworks"] = [
            d.get("domain", "") for d in domains
            if isinstance(d, dict) and d.get("domain")
        ]

    overview = report.get("technical_summary", "")

    return {
        "terms": terms_candidates,
        "modules": modules_candidates,
        "constraints": constraints_candidates,
        "tech_stack_additions": tech_stack,
        "overview_insights": overview,
    }


async def evolve_memory_after_analysis(
    agent: AnalysisAgent,
    project_memory: Optional[ProjectMemory],
    llm_client,
) -> None:
    if project_memory is None:
        logger.debug("No ProjectMemory available, skipping memory evolution")
        return

    candidates = extract_candidates_from_analysis(agent)

    has_any = any([
        candidates["terms"],
        candidates["modules"],
        candidates["constraints"],
        candidates["tech_stack_additions"],
        bool(candidates["overview_insights"]),
    ])
    if not has_any:
        logger.debug("No candidates extracted, skipping memory evolution")
        return

    user_prompt = build_memory_evolution_user_prompt(
        existing_memory=project_memory.to_text(),
        new_terms=candidates["terms"],
        new_modules=candidates["modules"],
        new_constraints=candidates["constraints"],
        tech_stack_additions=candidates["tech_stack_additions"],
        overview_insights=candidates["overview_insights"],
    )

    try:
        result = await _call_llm_structured(
            llm_client,
            messages=[
                {"role": "system", "content": MEMORY_EVOLUTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            schema=MEMORY_EVOLUTION_SCHEMA,
        )
    except Exception as e:
        logger.warning("Memory evolution LLM call failed: %s", e)
        return

    if not result:
        return

    for op in result.get("operations", []):
        try:
            _apply_operation(project_memory, op)
        except Exception as e:
            logger.warning("Failed to apply memory operation %s: %s", op.get("target", ""), e)

    changelog_entry = result.get("changelog_entry", "分析后记忆更新")
    project_memory._save_changelog(changelog_entry)
    project_memory.save()

    logger.info(
        "Memory evolution complete: %d operations, changelog: %s",
        len(result.get("operations", [])),
        changelog_entry,
    )


def _apply_operation(memory: ProjectMemory, op: dict) -> None:
    target = op.get("target", "")
    action = op.get("action", "")
    data = op.get("data", {})
    if action == "skip":
        return

    if target == "terms":
        term = data.get("term", "")
        definition = data.get("definition", "")
        domain = data.get("domain", "")
        if term and len(definition) >= 10:
            memory.add_term(term, definition, domain)
    elif target == "modules":
        name = data.get("name", "")
        if name:
            memory.add_module(
                name,
                data.get("responsibility", ""),
                data.get("key_classes", []),
            )
    elif target == "constraints":
        desc = data.get("description", "")
        if desc:
            memory.batch_add_constraints([{
                "description": desc,
                "type": data.get("type", "other"),
            }])
    elif target == "tech_stack":
        for cat, items in data.items():
            if isinstance(items, list) and items:
                memory.add_tech_stack(cat, items)
    elif target == "overview":
        overview = data.get("overview", "")
        if overview:
            memory.update_overview(overview)
```

- [ ] **Step 2: Commit**

```bash
git add src/reqradar/agent/memory_evolution.py
git commit -m "feat: add memory evolution module with candidate extraction and LLM-driven update"
```

---

### Task 8: Rewrite runner.py with single-loop architecture

**Files:**
- Modify: `src/reqradar/agent/runner.py` (rewrite main loop, keep helpers)

- [ ] **Step 1: Rewrite the file**

Replace `src/reqradar/agent/runner.py` entirely:

```python
import asyncio
import json
import logging

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.llm_utils import _call_llm_structured, _complete_with_tools, _parse_json_response
from reqradar.agent.prompts.analysis_phase import (
    build_dynamic_system_prompt,
    build_step_user_prompt,
    build_termination_prompt,
)
from reqradar.agent.prompts.report_phase import build_report_generation_prompt
from reqradar.agent.schemas import STEP_OUTPUT_SCHEMA
from reqradar.agent.tool_call_tracker import ToolCallTracker
from reqradar.agent.tools import ToolRegistry

logger = logging.getLogger("reqradar.agent.runner")

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

_RESULT_TRUNCATE_LENGTH = 4000


def _truncate_result(text: str, max_len: int = _RESULT_TRUNCATE_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...(截断)"


def _build_messages_chain(
    system_prompt: str,
    user_prompt: str,
    history: list[dict],
    max_history_messages: int = 6,
) -> list[dict]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if history:
        recent = history[-max_history_messages:]
        messages = messages[:1] + recent + messages[1:]
    return messages


def update_agent_from_step_result(agent: AnalysisAgent, step_data: dict) -> None:
    for dim, new_status in step_data.get("dimension_status", {}).items():
        if new_status == "sufficient":
            agent.dimension_tracker.mark_sufficient(dim)

    for finding in step_data.get("key_findings", []):
        agent.record_evidence(
            type="analysis",
            source=f"step:{agent.step_count}",
            content=finding.get("finding", ""),
            confidence=finding.get("confidence", "medium"),
            dimensions=[finding.get("dimension", "")],
        )

    agent._pending_actions = step_data.get("next_actions", [])
    agent._llm_declared_terminal = step_data.get("final_step", False)


def update_agent_from_tool_result(agent: AnalysisAgent, data: dict) -> None:
    if data.get("terms"):
        for t in data.get("terms", []):
            if isinstance(t, dict) and t.get("term"):
                agent.record_evidence(
                    type="term",
                    source=f"llm_extract:{t['term']}",
                    content=f"{t['term']}: {t.get('definition', '')}",
                    confidence="medium",
                    dimensions=["understanding"],
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


async def generate_report(
    agent: AnalysisAgent,
    llm_client,
    system_prompt: str,
    section_descriptions=None,
) -> dict:
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

    return build_fallback_report_data(agent)


def build_fallback_report_data(agent: AnalysisAgent) -> dict:
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
        "decision_summary": {
            "summary": "",
            "decisions": [],
            "open_questions": [],
            "follow_ups": [],
        },
        "evidence_items": [
            {"kind": ev.type, "source": ev.source, "summary": ev.content, "confidence": ev.confidence}
            for ev in agent.evidence_collector.evidences
        ],
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


async def _execute_tool_calls(
    tool_calls: list[dict],
    tool_registry: ToolRegistry,
    tracker: ToolCallTracker,
) -> list[dict]:
    tool_results = []
    for tc in tool_calls:
        tc_name = tc.get("name", "")
        tc_id = tc.get("id", "")
        tc_args_str = tc.get("arguments", "{}")

        try:
            tc_args = json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
        except json.JSONDecodeError:
            tc_args = {}

        if tc_name not in tool_registry._tools:
            tool_results.append({
                "role": "tool", "tool_call_id": tc_id,
                "content": f"Error: Unknown tool '{tc_name}'",
            })
            continue

        if tracker.is_duplicate(tc_name, tc_args):
            tool_results.append({
                "role": "tool", "tool_call_id": tc_id,
                "content": "(此调用已去重，跳过重复请求)",
            })
            continue

        tracker.track_call(tc_name, tc_args)

        try:
            result = await tool_registry.execute_with_permissions(tc_name, **tc_args)
            result_text = result.data if result.success else f"Error: {result.error}"
        except Exception as e:
            result_text = f"Error executing {tc_name}: {e}"

        result_text = _truncate_result(result_text)
        tool_results.append({
            "role": "tool", "tool_call_id": tc_id,
            "content": result_text,
        })

        logger.info(
            "Tool #%d: %s(%s) -> %d chars",
            tracker.call_count,
            tc_name,
            json.dumps(tc_args, ensure_ascii=False)[:60],
            len(result_text),
        )

    return tool_results


async def run_react_analysis(
    agent: AnalysisAgent,
    llm_client,
    tool_registry: ToolRegistry,
    config=None,
    section_descriptions=None,
    project_memory=None,
) -> dict:
    tool_schemas = tool_registry.get_schemas(tool_registry.list_names())
    tracker = ToolCallTracker()
    conversation_history: list[dict] = []

    agent.state = AgentState.ANALYZING

    while True:
        agent.step_count += 1

        ds = agent.dimension_tracker.status_summary()
        system_prompt = build_dynamic_system_prompt(
            dimension_status=ds,
            project_memory=agent.project_memory_text,
            user_memory=agent.user_memory_text,
            historical_context=agent.historical_context,
            template_sections=section_descriptions,
            pending_actions=agent._pending_actions,
        )

        user_prompt = build_step_user_prompt(
            requirement_text=agent.requirement_text,
            step_count=agent.step_count,
            max_steps=agent.max_steps,
            weak_dimensions=agent.get_weak_dimensions_text(),
            evidence_count=len(agent.evidence_collector.evidences),
            depth=agent.depth,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if conversation_history:
            recent = conversation_history[-6:]
            messages = messages[:1] + recent + messages[1:]

        if not tool_schemas:
            result = await _call_llm_structured(llm_client, messages, STEP_OUTPUT_SCHEMA)
            if result:
                update_agent_from_step_result(agent, result)
            if agent.should_terminate():
                break
            await asyncio.sleep(0)
            continue

        supported = await llm_client.supports_tool_calling()
        if not supported:
            result = await _call_llm_structured(llm_client, messages, STEP_OUTPUT_SCHEMA)
            if result:
                update_agent_from_step_result(agent, result)
            if agent.should_terminate():
                break
            await asyncio.sleep(0)
            continue

        response = await _complete_with_tools(llm_client, messages, tool_schemas)

        if response is None:
            agent._consecutive_failures += 1
            if agent.should_terminate():
                break
            await asyncio.sleep(0)
            continue

        agent._consecutive_failures = 0

        if "tool_calls" in response and response["tool_calls"]:
            assistant_msg = response.get("assistant_message", {})
            if assistant_msg:
                conversation_history.append(assistant_msg)

            tool_results = await _execute_tool_calls(
                response["tool_calls"], tool_registry, tracker
            )
            conversation_history.extend(tool_results)
            await asyncio.sleep(0)
            continue

        if "content" in response and response["content"]:
            try:
                parsed = _parse_json_response(response["content"])
                update_agent_from_step_result(agent, parsed)

                if len(parsed.get("key_findings", [])) == 0:
                    agent._consecutive_empty_steps += 1
                else:
                    agent._consecutive_empty_steps = 0
            except (json.JSONDecodeError, ValueError):
                agent._consecutive_empty_steps += 1
                conversation_history.append({
                    "role": "assistant",
                    "content": response["content"],
                })

        if agent.should_terminate():
            break

        await asyncio.sleep(0)

    agent.state = AgentState.GENERATING

    ds = agent.dimension_tracker.status_summary()
    final_system_prompt = build_dynamic_system_prompt(
        dimension_status=ds,
        project_memory=agent.project_memory_text,
        user_memory=agent.user_memory_text,
        historical_context=agent.historical_context,
        template_sections=section_descriptions,
    )
    report_data = await generate_report(agent, llm_client, final_system_prompt, section_descriptions)
    agent.final_report_data = report_data

    enable_memory_evolution = (
        config
        and hasattr(config, "memory_evolution")
        and config.memory_evolution.enabled
    )
    if enable_memory_evolution and project_memory is not None:
        try:
            from reqradar.agent.memory_evolution import evolve_memory_after_analysis

            await evolve_memory_after_analysis(agent, project_memory, llm_client)
        except Exception as e:
            logger.warning("Memory evolution failed: %s", e)

    agent.state = AgentState.COMPLETED
    return report_data
```

- [ ] **Step 2: Commit**

```bash
git add src/reqradar/agent/runner.py
git commit -m "feat: rewrite run_react_analysis with single-loop CoT-guided architecture"
```

---

### Task 9: Delete tool_use_loop.py and update prompts/__init__.py

**Files:**
- Delete: `src/reqradar/agent/tool_use_loop.py`
- Modify: `src/reqradar/agent/prompts/__init__.py`

- [ ] **Step 1: Delete tool_use_loop.py**

```bash
git rm src/reqradar/agent/tool_use_loop.py
```

- [ ] **Step 2: Update prompts/__init__.py**

Replace `src/reqradar/agent/prompts/__init__.py` entirely:

```python
from reqradar.agent.prompts.analysis_phase import (
    build_dynamic_system_prompt,
    build_step_user_prompt,
    build_termination_prompt,
)

__all__ = [
    "build_dynamic_system_prompt",
    "build_step_user_prompt",
    "build_termination_prompt",
]
```

- [ ] **Step 3: Commit**

```bash
git add src/reqradar/agent/tool_use_loop.py src/reqradar/agent/prompts/__init__.py
git commit -m "refactor: remove tool_use_loop.py, update prompts exports"
```

---

### Task 10: Update web/services/analysis_runner.py to use shared run_react_analysis

**Files:**
- Modify: `src/reqradar/web/services/analysis_runner.py` (lines 257-340 area)

- [ ] **Step 1: Replace `_execute_agent` to call `run_react_analysis`**

In `src/reqradar/web/services/analysis_runner.py`, replace the `_execute_agent` method (lines 256-340 area) with the version that delegates to `run_react_analysis`:

First, update the imports at the top of the file (remove old tool_use_loop import, add runner import):

After line 13 (`from reqradar.agent.prompts.analysis_phase import ...`), replace with:

```python
from reqradar.agent.runner import run_react_analysis, update_agent_from_tool_result as _runner_update_agent_from_tool_result
from reqradar.agent.schemas import STEP_OUTPUT_SCHEMA
```

Remove the old import of `ANALYZE_SCHEMA` on any future line, and also remove the old prompt imports that are no longer used directly.

Then replace the `_execute_agent` method body. Find the method starting around line 256. Replace the loop logic (lines 282-324) with a call to `run_react_analysis`. The full replacement:

```python
    async def _execute_agent(self, task_id: int, project: Project, config: Config, db: AsyncSession):
        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        await ws_manager.broadcast(task_id, {"type": "analysis_started", "task_id": task_id})

        try:
            agent, analysis_memory, cm, memory_data = await self._init_agent(task, project, config, db)
            tool_registry, llm_client = await self._init_tools(agent, task, project, config, db, cm, memory_data)
            template_def = await self._load_template(config, db)

            section_descriptions = None
            if template_def:
                section_descriptions = [
                    {
                        "id": s.id, "title": s.title, "description": s.description,
                        "requirements": s.requirements, "dimensions": s.dimensions,
                        "required": s.required,
                    }
                    for s in template_def.sections
                ]

            await ws_manager.broadcast(task_id, {
                "type": "agent_thinking", "task_id": task_id,
                "message": "开始分析需求...",
            })

            report_data = await run_react_analysis(
                agent=agent,
                llm_client=llm_client,
                tool_registry=tool_registry,
                config=config,
                section_descriptions=section_descriptions,
                project_memory=analysis_memory.project_memory if analysis_memory else None,
            )

            report_markdown = self._render_report(report_data, template_def)
            report_html = self._render_markdown_to_html(report_markdown)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            context_snapshot = agent.get_context_snapshot()
            task.context_json = json.dumps(context_snapshot, default=str)
            task.risk_level = report_data.get("risk_level", "unknown")

            await self._save_report(
                db=db, task=task, task_id=task_id, report_data=report_data,
                context_snapshot=context_snapshot,
                content_markdown=report_markdown, content_html=report_html,
                trigger_type="initial", created_by=task.user_id,
            )

            await ws_manager.broadcast(task_id, {
                "type": "analysis_complete", "task_id": task_id,
                "risk_level": report_data.get("risk_level", "unknown"),
            })

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await ws_manager.broadcast(task_id, {
                "type": "analysis_cancelled", "task_id": task_id,
            })
        except Exception as e:
            logger.exception("Analysis failed for task %d", task_id)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            task.error_message = str(e)[:500]
            await db.commit()
            await ws_manager.broadcast(task_id, {
                "type": "analysis_failed", "task_id": task_id,
                "error": str(e)[:200],
            })
```

Note: The `_update_agent_from_tool_result` method on the class (around line 396-423) can stay as-is since it's still used for evidence ingestion from the old report system, but it's no longer called from `_execute_agent`. Remove it if unused, or leave it for internal use.

- [ ] **Step 2: Verify the import for run_react_analysis works**

Run:

```bash
python -c "from reqradar.agent.runner import run_react_analysis; print('import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/reqradar/web/services/analysis_runner.py
git commit -m "refactor: deduplicate analysis runner to call shared run_react_analysis"
```

---

### Task 11: Update tests

**Files:**
- Modify: `tests/test_tool_use_loop.py` (rewrite for new behavior)
- Modify: `tests/test_round2_integration.py` (update prompt tests)

- [ ] **Step 1: Rewrite test_tool_use_loop.py**

Replace `tests/test_tool_use_loop.py` entirely:

```python
import pytest
from unittest.mock import AsyncMock

from reqradar.agent.analysis_agent import AnalysisAgent
from reqradar.agent.runner import run_react_analysis, update_agent_from_step_result
from reqradar.agent.tools.base import BaseTool, ToolResult
from reqradar.agent.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo back the input"
    parameters_schema = {
        "name": "echo",
        "description": "Echo back the input",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data=f"echo: {kwargs.get('text', '')}")


@pytest.mark.asyncio
async def test_single_call_returns_step_output_immediately():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(return_value={
        "content": '{"reasoning": "test", "dimension_status": {"understanding": "sufficient", "impact": "in_progress", "risk": "insufficient", "change": "insufficient", "decision": "insufficient", "evidence": "insufficient", "verification": "insufficient"}, "final_step": true}'
    })
    llm.complete_structured = AsyncMock(return_value={
        "reasoning": "test",
        "dimension_status": {},
        "final_step": False,
    })
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test requirement", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    result = await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert isinstance(result, dict)
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_tool_call_then_step_output():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(side_effect=[
        {
            "tool_calls": [
                {"id": "tc1", "name": "echo", "arguments": '{"text": "hello"}'}
            ],
            "assistant_message": {
                "role": "assistant", "content": None,
                "tool_calls": [
                    {
                        "id": "tc1", "type": "function",
                        "function": {"name": "echo", "arguments": '{"text": "hello"}'},
                    }
                ],
            },
        },
        {
            "content": '{"reasoning": "got echo", "dimension_status": {}, "final_step": false}',
        },
        {
            "content": '{"reasoning": "done", "dimension_status": {"understanding": "sufficient", "impact": "sufficient", "risk": "sufficient", "change": "sufficient", "decision": "sufficient", "evidence": "sufficient", "verification": "sufficient"}, "final_step": true}',
        },
    ])
    llm.complete_structured = AsyncMock(return_value={
        "requirement_title": "test",
        "risk_level": "medium",
    })
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test requirement", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()
    registry.register(EchoTool())

    result = await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert isinstance(result, dict)
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_terminates_on_max_steps():
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "content": f'{{"reasoning": "step {call_count}", "dimension_status": {{}}, "final_step": false}}',
        }

    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(side_effect=side_effect)
    llm.complete_structured = AsyncMock(return_value={
        "requirement_title": "test",
        "risk_level": "medium",
    })
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    result = await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert agent.step_count <= agent.max_steps
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_dimension_sufficiency_updated():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")

    step_data = {
        "reasoning": "test",
        "dimension_status": {
            "understanding": "sufficient",
            "impact": "sufficient",
            "risk": "sufficient",
            "change": "sufficient",
            "decision": "sufficient",
            "evidence": "sufficient",
            "verification": "sufficient",
        },
        "key_findings": [
            {"dimension": "impact", "finding": "Found auth module", "confidence": "high"}
        ],
        "final_step": False,
    }
    update_agent_from_step_result(agent, step_data)
    assert agent.dimension_tracker.all_sufficient()
    assert len(agent.evidence_collector.evidences) == 1


@pytest.mark.asyncio
async def test_no_tools_falls_back_to_structured():
    llm = AsyncMock()
    llm.complete_structured = AsyncMock(return_value={
        "reasoning": "no tools",
        "dimension_status": {},
        "final_step": False,
    })
    llm.supports_tool_calling = AsyncMock(return_value=False)

    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_consecutive_failures_terminate():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(return_value=None)
    llm.complete_structured = AsyncMock(return_value={
        "requirement_title": "test",
        "risk_level": "medium",
    })
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert agent.state.value == "completed"
    assert agent._consecutive_failures >= 3 or agent.step_count >= agent.max_steps
```

- [ ] **Step 2: Update test_round2_integration.py**

In `tests/test_round2_integration.py`, update the imports on lines 7-8:

Replace:
```python
from reqradar.agent.prompts.analysis_phase import build_analysis_system_prompt, build_analysis_user_prompt, build_termination_prompt
```
With:
```python
from reqradar.agent.prompts.analysis_phase import build_dynamic_system_prompt, build_step_user_prompt, build_termination_prompt
```

Update the test at line 62-68:
```python
def test_prompt_builders():
    sys_prompt = build_dynamic_system_prompt(
        dimension_status={"understanding": "sufficient", "impact": "in_progress"},
        project_memory="Project: ReqRadar\nLanguages: Python",
        user_memory="User prefers deep analysis",
    )
    assert "ReqRadar" in sys_prompt
    assert "understanding" in sys_prompt

    user_prompt = build_step_user_prompt("Add SSO support", step_count=1, max_steps=15, weak_dimensions="impact, risk", evidence_count=3)
    assert "SSO" in user_prompt
```

Update line 91:
```python
    prompt = build_dynamic_system_prompt(template_sections=section_descs)
    assert "需求理解" in prompt or "understanding" in prompt
```

- [ ] **Step 3: Run tests to verify**

```bash
python -m pytest tests/test_tool_use_loop.py tests/test_round2_integration.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_tool_use_loop.py tests/test_round2_integration.py
git commit -m "test: rewrite tests for new single-loop architecture and dynamic prompts"
```

---

### Task 12: Lint, format, and full test run

- [ ] **Step 1: Lint**

```bash
ruff check src/reqradar/agent/ src/reqradar/infrastructure/config.py
```

Fix any issues found.

- [ ] **Step 2: Format**

```bash
ruff format src/reqradar/agent/ src/reqradar/infrastructure/config.py
```

- [ ] **Step 3: Run all agent tests**

```bash
python -m pytest tests/ -v --timeout=60
```

- [ ] **Step 4: Verify imports**

```bash
python -c "
from reqradar.agent.runner import run_react_analysis, update_agent_from_step_result
from reqradar.agent.prompts.analysis_phase import build_dynamic_system_prompt, build_step_user_prompt
from reqradar.agent.schemas import STEP_OUTPUT_SCHEMA, MEMORY_EVOLUTION_SCHEMA
from reqradar.agent.tool_call_tracker import ToolCallTracker
from reqradar.agent.memory_evolution import extract_candidates_from_analysis, evolve_memory_after_analysis
from reqradar.infrastructure.config import MemoryEvolutionConfig
print('All imports OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: lint, format, and verify all imports"
```
