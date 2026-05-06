# Phase 4: 智能代码匹配增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强 ReqRadar 的代码匹配能力，让 LLM 从项目全局角度分析需求与代码的关联，而不是仅依赖字面匹配。

**Architecture:** 扩展记忆系统存储模块代码摘要，在工作流中整合智能模块查询和深度关联分析，每次分析后持久化模块关联历史。

**Tech Stack:** Python 3.12, Pydantic, YAML, OpenAI/MiniMax API

---

## 文件结构

### 新增文件
- `tests/test_smart_code_matching.py` - 智能代码匹配测试

### 修改文件
- `src/reqradar/modules/memory.py` - 扩展记忆结构，新增方法
- `src/reqradar/agent/steps.py` - 新增 Schema、Prompt 和分析函数
- `src/reqradar/core/context.py` - 新增 CodeAnalysisResult 数据类
- `src/reqradar/cli/main.py` - 持久化分析结果
- `tests/test_memory.py` - 新增测试用例

---

## Task 1: 扩展记忆数据结构

**Files:**
- Modify: `src/reqradar/modules/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: 编写记忆结构扩展的测试**

在 `tests/test_memory.py` 中添加测试：

```python
class TestMemoryModuleEnhancement:
    """测试模块记忆增强功能"""

    def test_add_module_with_code_summary(self, tmp_path):
        """测试添加带代码摘要的模块"""
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_module(
            name="auth",
            responsibility="用户认证模块",
            key_classes=["AuthManager", "TokenService"],
            code_summary="提供用户登录、登出、Token 管理功能。包含 verify_2fa() 双因素认证验证。",
        )

        data = manager.load()
        auth_module = next((m for m in data["modules"] if m["name"] == "auth"), None)
        assert auth_module is not None
        assert auth_module.get("code_summary") == "提供用户登录、登出、Token 管理功能。包含 verify_2fa() 双因素认证验证。"

    def test_add_module_requirement_history(self, tmp_path):
        """测试添加模块的需求关联历史"""
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_module(name="auth", responsibility="认证模块")

        manager.add_module_requirement_history(
            module_name="auth",
            requirement_id="user-auth-enhancement",
            relevance="high",
            suggested_changes="新增 verify_2fa() 函数",
        )

        data = manager.load()
        auth_module = next((m for m in data["modules"] if m["name"] == "auth"), None)
        assert "related_requirements" in auth_module
        assert len(auth_module["related_requirements"]) == 1
        assert auth_module["related_requirements"][0]["requirement_id"] == "user-auth-enhancement"

    def test_module_history_limit(self, tmp_path):
        """测试模块历史记录限制为10条"""
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_module(name="auth", responsibility="认证模块")

        for i in range(15):
            manager.add_module_requirement_history(
                module_name="auth",
                requirement_id=f"req-{i}",
                relevance="medium",
                suggested_changes=f"change-{i}",
            )

        data = manager.load()
        auth_module = next((m for m in data["modules"] if m["name"] == "auth"), None)
        assert len(auth_module["related_requirements"]) == 10

    def test_get_module_by_name(self, tmp_path):
        """测试按名称获取模块"""
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_module(name="auth", responsibility="认证")
        manager.add_module(name="user", responsibility="用户管理")

        auth = manager.get_module("auth")
        assert auth is not None
        assert auth["responsibility"] == "认证"

        none_module = manager.get_module("nonexistent")
        assert none_module is None
```

- [ ] **Step 2: 运行测试验证失败**

运行: `PYTHONPATH=src pytest tests/test_memory.py::TestMemoryModuleEnhancement -v`

预期: FAIL - 方法不存在

- [ ] **Step 3: 扩展 add_module 方法支持 code_summary**

在 `memory.py` 中修改 `add_module` 方法：

```python
def add_module(
    self,
    name: str,
    responsibility: str = "",
    key_classes: list = None,
    dependencies: list = None,
    path: str = "",
    owner: str = None,
    code_summary: str = "",
) -> None:
    """Add or update a module"""
    self.load()
    modules = self._data["modules"]

    for existing in modules:
        if existing.get("name") == name:
            existing["responsibility"] = responsibility or existing.get("responsibility", "")
            if key_classes:
                existing["key_classes"] = key_classes
            if dependencies:
                existing["dependencies"] = dependencies
            if path:
                existing["path"] = path
            if owner:
                existing["owner"] = owner
            if code_summary:
                existing["code_summary"] = code_summary
            if "related_requirements" not in existing:
                existing["related_requirements"] = []
            self.save()
            return

    new_module = {
        "name": name,
        "responsibility": responsibility,
        "key_classes": key_classes or [],
        "dependencies": dependencies or [],
        "path": path,
        "owner": owner,
        "code_summary": code_summary,
        "related_requirements": [],
    }
    modules.append(new_module)
    self.save()
```

- [ ] **Step 4: 新增 add_module_requirement_history 方法**

```python
def add_module_requirement_history(
    self,
    module_name: str,
    requirement_id: str,
    relevance: str,
    suggested_changes: str = "",
) -> None:
    """Add requirement relationship history to a module"""
    self.load()

    module = self.get_module(module_name)
    if module is None:
        logger.warning("Module %s not found, skipping history add", module_name)
        return

    if "related_requirements" not in module:
        module["related_requirements"] = []

    module["related_requirements"].append({
        "requirement_id": requirement_id,
        "relevance": relevance,
        "suggested_changes": suggested_changes,
        "timestamp": datetime.now().isoformat(),
    })

    module["related_requirements"] = module["related_requirements"][-10:]
    self.save()
```

- [ ] **Step 5: 新增 get_module 方法**

```python
def get_module(self, name: str) -> dict | None:
    """Get module by name"""
    self.load()
    for module in self._data.get("modules", []):
        if module.get("name") == name:
            return module
    return None
```

- [ ] **Step 6: 运行测试验证通过**

运行: `PYTHONPATH=src pytest tests/test_memory.py::TestMemoryModuleEnhancement -v`

预期: PASS

- [ ] **Step 7: 提交**

```bash
git add src/reqradar/modules/memory.py tests/test_memory.py
git commit -m "feat(memory): add code_summary and requirement history to modules"
```

---

## Task 2: 新增代码分析数据结构

**Files:**
- Modify: `src/reqradar/core/context.py`

- [ ] **Step 1: 新增 CodeAnalysisResult 数据类**

在 `context.py` 中添加：

```python
@dataclass
class ModuleAnalysisResult:
    """单个模块的分析结果"""
    path: str = ""
    symbols: list[str] = field(default_factory=list)
    relevance: str = "low"
    relevance_reason: str = ""
    suggested_changes: str = ""


@dataclass
class CodeAnalysisResult:
    """代码分析结果"""
    modules: list[ModuleAnalysisResult] = field(default_factory=list)
    overall_assessment: dict = field(default_factory=dict)
    confidence: float = 0.0
```

- [ ] **Step 2: 在 AnalysisContext 中添加 code_analysis 字段**

修改 `AnalysisContext` dataclass：

```python
@dataclass
class AnalysisContext:
    requirement_path: Path
    requirement_text: str = ""
    memory_data: Optional[dict] = None
    understanding: Optional[RequirementUnderstanding] = None
    retrieved_context: Optional[RetrievedContext] = None
    deep_analysis: Optional[DeepAnalysis] = None
    generated_content: Optional[GeneratedContent] = None
    expanded_keywords: list[str] = field(default_factory=list)
    code_analysis: Optional[CodeAnalysisResult] = None
    step_results: dict[str, StepResult] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
```

- [ ] **Step 3: 运行测试验证**

运行: `PYTHONPATH=src pytest tests/ -v --tb=short`

预期: PASS

- [ ] **Step 4: 提交**

```bash
git add src/reqradar/core/context.py
git commit -m "feat(context): add CodeAnalysisResult dataclass"
```

---

## Task 3: 新增智能模块查询 Schema 和 Prompt

**Files:**
- Modify: `src/reqradar/agent/steps.py`

- [ ] **Step 1: 添加 QUERY_MODULES_SCHEMA**

在 `steps.py` 的 Schema 区域（约 line 500 后）添加：

```python
QUERY_MODULES_SCHEMA = {
    "name": "query_relevant_modules",
    "description": "根据需求内容，主动查询项目中相关的模块",
    "parameters": {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string", "description": "模块名称或路径"},
                        "query_reason": {"type": "string", "description": "为什么需要分析这个模块"},
                    },
                    "required": ["module_name", "query_reason"],
                },
                "description": "需要详细分析的模块列表（最多10个）",
            },
            "reasoning": {
                "type": "string",
                "description": "整体分析推理过程",
            },
        },
        "required": ["queries"],
    },
}
```

- [ ] **Step 2: 添加 QUERY_MODULES_PROMPT**

```python
QUERY_MODULES_PROMPT = """你是一位架构师，请分析需求并主动查询相关模块。

## 项目画像
{project_profile}

## 已知模块及其职责
{modules_overview}

## 当前需求
- 摘要: {summary}
- 核心术语: {terms}

## 任务
1. 分析需求的核心功能点
2. 结合项目架构和模块职责，推断可能涉及的模块
3. 考虑以下维度：
   - 直接功能相关性（模块直接实现需求功能）
   - 数据流相关性（模块处理相关数据）
   - 接口依赖相关性（模块依赖或提供相关接口）
   - 配置/基础设施相关性（涉及配置、中间件等）

请输出需要详细分析的模块列表，并说明每个模块的查询理由。
"""
```

- [ ] **Step 3: 添加 ANALYZE_MODULE_RELEVANCE_SCHEMA**

```python
ANALYZE_MODULE_RELEVANCE_SCHEMA = {
    "name": "analyze_module_relevance",
    "description": "深度分析模块与需求的关联，输出具体的代码影响",
    "parameters": {
        "type": "object",
        "properties": {
            "modules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "涉及的关键函数/类",
                        },
                        "relevance": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "关联程度",
                        },
                        "relevance_reason": {"type": "string", "description": "关联理由"},
                        "suggested_changes": {"type": "string", "description": "建议的变更内容"},
                    },
                    "required": ["path", "relevance", "relevance_reason"],
                },
            },
            "overall_assessment": {
                "type": "object",
                "properties": {
                    "impact_scope": {"type": "string", "description": "整体影响范围描述"},
                    "key_integration_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键集成点",
                    },
                },
            },
        },
        "required": ["modules"],
    },
}
```

- [ ] **Step 4: 添加 ANALYZE_MODULE_RELEVANCE_PROMPT**

```python
ANALYZE_MODULE_RELEVANCE_PROMPT = """你是一位资深开发者，请深度分析模块与需求的具体关联。

## 需求内容
{requirement_text}

## 需求理解
- 摘要: {summary}
- 核心术语: {terms}

## 候选模块详情
{modules_detail}

## 任务
对于每个模块：
1. 分析其代码摘要与需求的具体关联点
2. 识别需要修改或新增的函数/类
3. 描述建议的变更内容
4. 评估影响程度（high/medium/low）

请输出详细的模块分析结果。
"""
```

- [ ] **Step 5: 提交**

```bash
git add src/reqradar/agent/steps.py
git commit -m "feat(steps): add schemas and prompts for smart module query and analysis"
```

---

## Task 4: 实现智能模块查询函数

**Files:**
- Modify: `src/reqradar/agent/steps.py`
- Create: `tests/test_smart_code_matching.py`

- [ ] **Step 1: 创建测试文件**

创建 `tests/test_smart_code_matching.py`：

```python
"""测试智能代码匹配功能"""

import pytest
from unittest.mock import AsyncMock

from reqradar.core.context import TermDefinition, RequirementUnderstanding


class TestQueryRelevantModules:
    @pytest.mark.asyncio
    async def test_query_returns_modules(self):
        """测试查询返回相关模块"""
        from reqradar.agent.steps import _query_relevant_modules_from_memory

        understanding = RequirementUnderstanding(
            summary="用户登录需要支持双因素认证",
            terms=[TermDefinition(term="双因素认证", definition="2FA")],
        )
        memory_data = {
            "project_profile": {"name": "TestProject"},
            "modules": [
                {"name": "auth", "responsibility": "用户认证", "code_summary": "处理登录和认证"},
                {"name": "user", "responsibility": "用户管理", "code_summary": "用户信息管理"},
            ],
        }

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value={
            "queries": [
                {"module_name": "auth", "query_reason": "负责认证功能"},
                {"module_name": "user", "query_reason": "用户信息相关"},
            ],
            "reasoning": "双因素认证涉及认证模块",
        })

        result = await _query_relevant_modules_from_memory(
            understanding, memory_data, mock_llm
        )

        assert len(result) == 2
        assert result[0]["name"] == "auth"
        assert "query_reason" in result[0]

    @pytest.mark.asyncio
    async def test_query_with_empty_memory(self):
        """测试空记忆时的查询"""
        from reqradar.agent.steps import _query_relevant_modules_from_memory

        understanding = RequirementUnderstanding(summary="测试需求")
        memory_data = {"modules": []}

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value={"queries": []})

        result = await _query_relevant_modules_from_memory(
            understanding, memory_data, mock_llm
        )

        assert result == []


class TestAnalyzeModuleRelevance:
    @pytest.mark.asyncio
    async def test_analyze_returns_detailed_results(self):
        """测试分析返回详细结果"""
        from reqradar.agent.steps import _analyze_module_relevance

        understanding = RequirementUnderstanding(
            summary="添加双因素认证",
            raw_text="用户登录需要支持双因素认证",
            terms=[TermDefinition(term="认证", definition="身份验证")],
        )
        modules = [
            {"name": "auth", "responsibility": "认证", "code_summary": "login(), verify()"},
        ]

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value={
            "modules": [
                {
                    "path": "auth",
                    "symbols": ["verify_2fa", "login"],
                    "relevance": "high",
                    "relevance_reason": "直接负责认证",
                    "suggested_changes": "新增 verify_2fa() 函数",
                }
            ],
            "overall_assessment": {
                "impact_scope": "认证模块",
                "key_integration_points": ["login 流程", "token 验证"],
            },
        })

        result = await _analyze_module_relevance(understanding, modules, mock_llm)

        assert len(result) == 1
        assert result[0]["relevance"] == "high"
        assert "verify_2fa" in result[0]["symbols"]
```

- [ ] **Step 2: 运行测试验证失败**

运行: `PYTHONPATH=src pytest tests/test_smart_code_matching.py -v`

预期: FAIL - 函数不存在

- [ ] **Step 3: 实现 _query_relevant_modules_from_memory 函数**

在 `steps.py` 中添加：

```python
async def _query_relevant_modules_from_memory(
    understanding: RequirementUnderstanding,
    memory_data: dict | None,
    llm_client,
) -> list[dict]:
    """LLM 主动查询相关模块"""
    if not memory_data or not memory_data.get("modules"):
        logger.info("No modules in memory, skipping query")
        return []

    try:
        modules_overview = "\n".join([
            f"- {m.get('name', 'unknown')}: {m.get('responsibility', '')}"
            for m in memory_data.get("modules", [])
        ])

        project_profile = memory_data.get("project_profile", {})
        project_profile_str = json.dumps(project_profile, ensure_ascii=False, indent=2)

        messages = [{
            "role": "user",
            "content": QUERY_MODULES_PROMPT.format(
                project_profile=project_profile_str,
                modules_overview=modules_overview,
                summary=understanding.summary or "",
                terms=", ".join([t.term for t in understanding.terms]) if understanding.terms else "",
            ),
        }]

        result = await _call_llm_structured(
            llm_client, messages, QUERY_MODULES_SCHEMA, max_tokens=2048
        )

        queried_modules = []
        for query in result.get("queries", []):
            module_name = query.get("module_name", "")
            module_info = _get_module_from_memory(memory_data, module_name)
            if module_info:
                module_info["query_reason"] = query.get("query_reason", "")
                queried_modules.append(module_info)

        logger.info("Queried %d relevant modules", len(queried_modules))
        return queried_modules

    except Exception as e:
        logger.warning("Failed to query relevant modules: %s", e)
        return []


def _get_module_from_memory(memory_data: dict, module_name: str) -> dict | None:
    """从记忆中获取指定模块信息"""
    for module in memory_data.get("modules", []):
        if module.get("name") == module_name or module_name.lower() in module.get("name", "").lower():
            return module.copy()
    return None
```

- [ ] **Step 4: 实现 _analyze_module_relevance 函数**

```python
async def _analyze_module_relevance(
    understanding: RequirementUnderstanding,
    modules: list[dict],
    llm_client,
) -> list[dict]:
    """深度分析模块与需求的关联"""
    if not modules:
        return []

    try:
        modules_detail = []
        for module in modules:
            detail = f"""### 模块: {module.get('name', 'unknown')}
职责: {module.get('responsibility', '未知')}
核心类: {', '.join(module.get('key_classes', []))}
代码摘要: {module.get('code_summary', '暂无')}
查询理由: {module.get('query_reason', '')}
"""
            modules_detail.append(detail)

        messages = [{
            "role": "user",
            "content": ANALYZE_MODULE_RELEVANCE_PROMPT.format(
                requirement_text=understanding.raw_text[:2000] if understanding.raw_text else "",
                summary=understanding.summary or "",
                terms=", ".join([f"{t.term}: {t.definition}" for t in understanding.terms]) if understanding.terms else "",
                modules_detail="\n\n---\n\n".join(modules_detail),
            ),
        }]

        result = await _call_llm_structured(
            llm_client, messages, ANALYZE_MODULE_RELEVANCE_SCHEMA, max_tokens=4096
        )

        analyzed_modules = []
        for m in result.get("modules", []):
            analyzed_modules.append({
                "path": m.get("path", ""),
                "symbols": m.get("symbols", []),
                "relevance": m.get("relevance", "low"),
                "relevance_reason": m.get("relevance_reason", ""),
                "suggested_changes": m.get("suggested_changes", ""),
            })

        return analyzed_modules

    except Exception as e:
        logger.warning("Failed to analyze module relevance: %s", e)
        return [
            {
                "path": m.get("name", ""),
                "symbols": [],
                "relevance": "low",
                "relevance_reason": f"分析失败: {e}",
                "suggested_changes": "",
            }
            for m in modules
        ]
```

- [ ] **Step 5: 实现 _smart_module_matching 函数**

```python
async def _smart_module_matching(
    understanding: RequirementUnderstanding,
    memory_data: dict | None,
    code_graph,
    llm_client,
) -> list[dict]:
    """智能模块匹配：LLM 主动查询 + 深度分析"""
    logger.info("Starting smart module matching")

    relevant_modules = await _query_relevant_modules_from_memory(
        understanding, memory_data, llm_client
    )

    if not relevant_modules:
        logger.info("No relevant modules found by LLM")
        return []

    analyzed_modules = await _analyze_module_relevance(
        understanding, relevant_modules, llm_client
    )

    significant_modules = [
        m for m in analyzed_modules
        if m.get("relevance") in ("high", "medium")
    ]

    logger.info(
        "Smart matching complete: %d modules (high/medium: %d)",
        len(analyzed_modules),
        len(significant_modules),
    )

    return analyzed_modules
```

- [ ] **Step 6: 运行测试验证通过**

运行: `PYTHONPATH=src pytest tests/test_smart_code_matching.py -v`

预期: PASS

- [ ] **Step 7: 提交**

```bash
git add src/reqradar/agent/steps.py tests/test_smart_code_matching.py
git commit -m "feat(steps): implement smart module query and analysis functions"
```

---

## Task 5: 整合到 step_analyze

**Files:**
- Modify: `src/reqradar/agent/steps.py`

- [ ] **Step 1: 修改 step_analyze 函数**

在 `step_analyze` 函数开头（约 line 761）添加智能模块匹配：

找到 `async def step_analyze` 函数，在 `analysis = DeepAnalysis()` 之后添加：

```python
async def step_analyze(
    context: AnalysisContext, code_graph, git_analyzer, llm_client=None
) -> DeepAnalysis:
    """Step 4: 深度分析"""
    analysis = DeepAnalysis()

    # === 新增: 智能模块匹配 ===
    if llm_client and context.memory_data and context.understanding:
        try:
            impact_modules = await _smart_module_matching(
                context.understanding,
                context.memory_data,
                code_graph,
                llm_client,
            )
            analysis.impact_modules = impact_modules
            logger.info("Smart module matching found %d modules", len(impact_modules))
        except Exception as e:
            logger.warning("Smart module matching failed, falling back: %s", e)
            # 降级到原有逻辑
            keywords = context.expanded_keywords if context.expanded_keywords else (context.understanding.keywords if context.understanding else [])
            if code_graph and keywords:
                matched_files = code_graph.find_symbols(keywords)
                analysis.impact_modules = [
                    {"path": f.path, "symbols": [s.name for s in f.symbols[:5]]}
                    for f in matched_files[:10]
                ]
    else:
        # 原有的关键词匹配逻辑
        keywords = context.expanded_keywords if context.expanded_keywords else (context.understanding.keywords if context.understanding else [])
        if code_graph and keywords:
            matched_files = code_graph.find_symbols(keywords)
            analysis.impact_modules = [
                {"path": f.path, "symbols": [s.name for s in f.symbols[:5]]}
                for f in matched_files[:10]
            ]
    # ===========================

    # ... 后续代码保持不变 ...
```

- [ ] **Step 2: 运行所有测试**

运行: `PYTHONPATH=src pytest tests/ -v --tb=short`

预期: PASS

- [ ] **Step 3: 提交**

```bash
git add src/reqradar/agent/steps.py
git commit -m "feat(steps): integrate smart module matching into step_analyze"
```

---

## Task 6: 扩展 step_build_project_profile 生成代码摘要

**Files:**
- Modify: `src/reqradar/agent/steps.py`

- [ ] **Step 1: 添加 GENERATE_MODULE_SUMMARY_SCHEMA**

在 Schema 区域添加：

```python
GENERATE_MODULE_SUMMARY_SCHEMA = {
    "name": "generate_module_summary",
    "description": "生成模块的代码摘要",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "模块功能的摘要描述（100-200字）",
            },
            "key_functions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "关键函数列表",
            },
        },
        "required": ["summary"],
    },
}

GENERATE_MODULE_SUMMARY_PROMPT = """请为以下代码生成模块摘要。

## 模块名称
{module_name}

## 模块职责
{responsibility}

## 代码内容
```
{code_content}
```

## 任务
1. 总结模块的核心功能（100-200字）
2. 识别关键函数

请输出 JSON 格式的摘要。
"""
```

- [ ] **Step 2: 添加辅助函数**

```python
def _find_module_files(module_name: str, code_graph) -> list:
    """查找模块对应的代码文件"""
    matching_files = []
    for f in code_graph.files:
        if module_name.lower() in f.path.lower():
            matching_files.append(f)
    return matching_files[:5]


def _read_module_code(module_files: list, max_chars: int = 5000) -> str:
    """读取模块代码内容"""
    all_content = []
    total_chars = 0

    for code_file in module_files:
        try:
            path = Path(code_file.path)
            if path.exists():
                content = path.read_text(encoding="utf-8")
                key_content = _extract_key_code(content, code_file.symbols)
                all_content.append(f"# {code_file.path}\n{key_content}")
                total_chars += len(key_content)
                if total_chars >= max_chars:
                    break
        except Exception:
            continue

    return "\n\n".join(all_content)[:max_chars]


def _extract_key_code(content: str, symbols: list) -> str:
    """提取代码的关键部分"""
    lines = content.split("\n")
    key_lines = []

    for sym in symbols[:10]:
        sym_name = sym.get("name", "") if isinstance(sym, dict) else str(sym)
        for i, line in enumerate(lines):
            if f"def {sym_name}" in line or f"class {sym_name}" in line:
                end = i + 1
                while end < len(lines) and not lines[end].strip().startswith(("def ", "class ", "@")):
                    if lines[end].strip() and not lines[end].strip().startswith("#"):
                        end += 1
                        if end - i > 30:
                            break
                    else:
                        end += 1
                        if end - i > 5:
                            break
                key_lines.extend(lines[i:end])
                break

    return "\n".join(key_lines)


async def _generate_module_summary(
    module_name: str,
    code_content: str,
    responsibility: str,
    llm_client,
) -> str:
    """为模块生成代码摘要"""
    try:
        messages = [{
            "role": "user",
            "content": GENERATE_MODULE_SUMMARY_PROMPT.format(
                module_name=module_name,
                responsibility=responsibility or "未知",
                code_content=code_content[:5000],
            ),
        }]

        result = await _call_llm_structured(
            llm_client, messages, GENERATE_MODULE_SUMMARY_SCHEMA, max_tokens=1024
        )

        return result.get("summary", "")

    except Exception as e:
        logger.warning("Failed to generate module summary for %s: %s", module_name, e)
        return f"模块 {module_name}：{responsibility}"
```

- [ ] **Step 3: 修改 step_build_project_profile**

在模块循环中添加代码摘要生成。找到 `for module in result.get("modules", []):` 循环，修改为：

```python
for module in result.get("modules", []):
    if isinstance(module, dict) and module.get("name"):
        module_name = module.get("name", "")
        responsibility = module.get("responsibility", "")

        # === 新增: 生成代码摘要 ===
        module_files = _find_module_files(module_name, code_graph)
        if module_files:
            code_content = _read_module_code(module_files, max_chars=5000)
            if code_content:
                code_summary = await _generate_module_summary(
                    module_name,
                    code_content,
                    responsibility,
                    llm_client,
                )
            else:
                code_summary = f"模块 {module_name}：{responsibility}"
        else:
            code_summary = f"模块 {module_name}：{responsibility}"
        # ============================

        memory_manager.add_module(
            name=module_name,
            responsibility=responsibility,
            key_classes=module.get("key_classes", []),
            dependencies=module.get("dependencies", []),
            path=_infer_module_path(module_name, code_graph),
            code_summary=code_summary,
        )
```

- [ ] **Step 4: 运行测试**

运行: `PYTHONPATH=src pytest tests/test_project_profile.py -v`

预期: PASS

- [ ] **Step 5: 提交**

```bash
git add src/reqradar/agent/steps.py
git commit -m "feat(steps): generate code summary for modules during project profiling"
```

---

## Task 7: 实现分析后持久化

**Files:**
- Modify: `src/reqradar/cli/main.py`

- [ ] **Step 1: 添加持久化钩子函数**

在 `analyze` 命令的 `run_analysis()` 内部，找到 `scheduler.register_after_hook("generate", memory_update_hook)` 之前，添加：

```python
async def persist_module_history_hook(ctx):
    """持久化模块关联历史"""
    if not ctx.deep_analysis or not ctx.deep_analysis.impact_modules:
        return

    try:
        for module in ctx.deep_analysis.impact_modules:
            module_path = module.get("path", "")
            if module_path:
                memory_manager.add_module_requirement_history(
                    module_name=module_path,
                    requirement_id=ctx.requirement_path.stem,
                    relevance=module.get("relevance", "unknown"),
                    suggested_changes=module.get("suggested_changes", ""),
                )

        logger.info("Module requirement history persisted")

    except Exception as e:
        logger.warning("Failed to persist module history: %s", e)
```

- [ ] **Step 2: 注册钩子**

在 scheduler 初始化后添加：

```python
scheduler.register_after_hook("analyze", persist_module_history_hook)
```

- [ ] **Step 3: 运行测试**

运行: `PYTHONPATH=src pytest tests/ -v --tb=short`

预期: PASS

- [ ] **Step 4: 提交**

```bash
git add src/reqradar/cli/main.py
git commit -m "feat(cli): persist module requirement history after analysis"
```

---

## Task 8: 端到端测试验证

- [ ] **Step 1: 运行端到端测试**

运行: `PYTHONPATH=src OPENAI_API_KEY=<your-key> python test_e2e.py`

预期: 成功生成报告

- [ ] **Step 2: 检查 memory.yaml**

运行: `cat .reqradar/memory/memory.yaml`

验证:
- modules 中有 `code_summary` 字段
- modules 中有 `related_requirements` 字段

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "test(e2e): verify smart module matching works"
```

---

## Task 9: 运行完整测试套件

- [ ] **Step 1: 运行所有测试**

运行: `PYTHONPATH=src pytest tests/ -v`

预期: 全部通过

- [ ] **Step 2: 最终提交**

```bash
git add -A
git commit -m "feat(phase4): complete smart code matching implementation

- Extended memory structure with code_summary and related_requirements
- Added QUERY_MODULES_SCHEMA and ANALYZE_MODULE_RELEVANCE_SCHEMA
- Implemented _query_relevant_modules_from_memory and _analyze_module_relevance
- Integrated smart matching into step_analyze
- Added code summary generation in step_build_project_profile
- Persisted module requirement history after analysis
- Added comprehensive tests for smart code matching"
```

---

## 验收标准

| 标准 | 验证方法 |
|:---|:---|
| 记忆扩展完成 | memory.yaml 包含 code_summary, related_requirements |
| 智能查询正常 | LLM 能基于项目画像主动查询相关模块 |
| 深度分析正常 | LLM 能输出模块的 relevance, relevance_reason, suggested_changes |
| 持久化正常 | 分析后 memory.yaml 中模块有 related_requirements 记录 |
| 测试全部通过 | `pytest tests/ -v` 显示所有测试 PASS |
| 端到端可用 | MiniMax API 测试成功生成报告 |
