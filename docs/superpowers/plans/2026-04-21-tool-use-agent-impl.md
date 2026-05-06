# Tool-Use Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ReqRadar 的6步流水线中每个LLM步骤改造为"LLM+工具调用"循环，让LLM能主动查询代码/记忆/向量库，大幅提升分析质量。

**Architecture:** 保留6步调度框架不变，在每步内部嵌入tool-use循环。新增Tool抽象层封装现有能力模块（CodeParser/VectorStore/GitAnalyzer/MemoryManager），新增ToolUseLoop处理LLM与工具的多轮交互。LLM成本通过配置项+运行时监控控制。

**Tech Stack:** Python 3.12, OpenAI function calling protocol (tool_use), httpx, Pydantic, Chroma, structlog

---

## File Structure

### 新增文件

| 文件 | 职责 |
|:---|:---|
| `src/reqradar/agent/tools/__init__.py` | 工具包入口，导出所有Tool类 |
| `src/reqradar/agent/tools/base.py` | BaseTool基类、ToolResult数据类 |
| `src/reqradar/agent/tools/registry.py` | ToolRegistry：注册/查找/聚合schema |
| `src/reqradar/agent/tools/search_code.py` | search_code工具：搜索代码符号 |
| `src/reqradar/agent/tools/read_file.py` | read_file工具：读取文件内容 |
| `src/reqradar/agent/tools/read_module_summary.py` | read_module_summary工具：获取模块摘要 |
| `src/reqradar/agent/tools/list_modules.py` | list_modules工具：列出所有模块 |
| `src/reqradar/agent/tools/search_requirements.py` | search_requirements工具：语义搜索历史需求 |
| `src/reqradar/agent/tools/get_dependencies.py` | get_dependencies工具：查询模块依赖 |
| `src/reqradar/agent/tools/get_contributors.py` | get_contributors工具：查询文件贡献者 |
| `src/reqradar/agent/tools/get_project_profile.py` | get_project_profile工具：获取项目画像 |
| `src/reqradar/agent/tools/get_terminology.py` | get_terminology工具：获取已知术语 |
| `src/reqradar/agent/tool_use_loop.py` | 核心循环逻辑：LLM↔Tool多轮交互 |
| `src/reqradar/agent/tool_call_tracker.py` | ToolCallTracker：调用去重、计数、token监控 |
| `tests/test_tool_base.py` | Tool基类和ToolResult测试 |
| `tests/test_tool_registry.py` | ToolRegistry测试 |
| `tests/test_tool_implementations.py` | 9个Tool实现测试 |
| `tests/test_tool_use_loop.py` | ToolUseLoop核心逻辑测试 |
| `tests/test_tool_call_tracker.py` | ToolCallTracker测试 |

### 修改文件

| 文件 | 改动范围 |
|:---|:---|
| `src/reqradar/modules/llm_client.py:16-47,117-199` | 新增`complete_with_tools()`方法，支持OpenAI tool_use协议 |
| `src/reqradar/agent/llm_utils.py` | 新增`complete_with_tools()`封装函数 |
| `src/reqradar/agent/steps.py` | 每个LLM步骤改用`run_tool_use_loop()` |
| `src/reqradar/agent/prompts.py` | 重写system prompt，加入工具使用指引 |
| `src/reqradar/agent/schemas.py` | ANALYZE_SCHEMA增加impact_narrative/risk_narrative字段；GENERATE_SCHEMA将impact_narrative/risk_narrative/implementation_suggestion设为required |
| `src/reqradar/core/context.py:81-89` | DeepAnalysis增加impact_narrative/risk_narrative字段 |
| `src/reqradar/core/report.py:79-110` | 修复None显示、格式化tech_stack |
| `src/reqradar/infrastructure/config.py:70-73` | AnalysisConfig增加tool_use相关配置 |
| `src/reqradar/cli/main.py:309-326` | 传入ToolRegistry和工具实例到各步骤handler |

### 不改动的文件

| 文件 | 原因 |
|:---|:---|
| `modules/code_parser.py` | 只通过Tool封装调用，不改实现 |
| `modules/vector_store.py` | 同上 |
| `modules/git_analyzer.py` | 同上 |
| `modules/memory.py` | 同上 |
| `core/scheduler.py` | 6步流程不变 |
| `templates/report.md.j2` | 模板结构不变（数据由report.py传入） |

---

## Task 1: Tool基础设施 — BaseTool、ToolResult

**Files:**
- Create: `src/reqradar/agent/tools/__init__.py`
- Create: `src/reqradar/agent/tools/base.py`
- Test: `tests/test_tool_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_base.py
from reqradar.agent.tools.base import BaseTool, ToolResult


def test_tool_result_success():
    result = ToolResult(success=True, data="hello")
    assert result.success is True
    assert result.data == "hello"
    assert result.error == ""
    assert result.truncated is False


def test_tool_result_failure():
    result = ToolResult(success=False, data="", error="file not found")
    assert result.success is False
    assert result.error == "file not found"


def test_base_tool_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        BaseTool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'reqradar.agent.tools.base'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/reqradar/agent/tools/__init__.py
from reqradar.agent.tools.base import BaseTool, ToolResult

__all__ = ["BaseTool", "ToolResult"]
```

```python
# src/reqradar/agent/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    data: str
    error: str = ""
    truncated: bool = False


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters_schema: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/agent/tools/__init__.py src/reqradar/agent/tools/base.py tests/test_tool_base.py
git commit -m "feat: add BaseTool and ToolResult data model"
```

---

## Task 2: ToolRegistry — 工具注册、查找、schema聚合

**Files:**
- Create: `src/reqradar/agent/tools/registry.py`
- Test: `tests/test_tool_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_registry.py
import pytest
from reqradar.agent.tools.base import BaseTool, ToolResult
from reqradar.agent.tools.registry import ToolRegistry


class FakeTool(BaseTool):
    name = "fake_tool"
    description = "A fake tool for testing"
    parameters_schema = {
        "name": "fake_tool",
        "description": "A fake tool for testing",
        "parameters": {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data=f"echo: {kwargs.get('input', '')}")


def test_registry_register_and_get():
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)
    assert registry.get("fake_tool") is tool


def test_registry_get_nonexistent():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_registry_get_schemas():
    registry = ToolRegistry()
    registry.register(FakeTool())
    schemas = registry.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "fake_tool"


def test_registry_get_subset():
    registry = ToolRegistry()
    registry.register(FakeTool())
    schemas = registry.get_schemas(["fake_tool"])
    assert len(schemas) == 1
    schemas2 = registry.get_schemas(["nonexistent"])
    assert len(schemas2) == 0


def test_registry_list_names():
    registry = ToolRegistry()
    registry.register(FakeTool())
    assert registry.list_names() == ["fake_tool"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_registry.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/reqradar/agent/tools/registry.py
from reqradar.agent.tools.base import BaseTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_schemas(self, names: list[str] | None = None) -> list[dict]:
        if names is None:
            return [t.parameters_schema for t in self._tools.values()]
        return [
            self._tools[n].parameters_schema
            for n in names
            if n in self._tools
        ]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/agent/tools/registry.py tests/test_tool_registry.py
git commit -m "feat: add ToolRegistry for tool registration and schema aggregation"
```

---

## Task 3: ToolCallTracker — 调用去重、计数、token监控

**Files:**
- Create: `src/reqradar/agent/tool_call_tracker.py`
- Test: `tests/test_tool_call_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_call_tracker.py
from reqradar.agent.tool_call_tracker import ToolCallTracker


def test_track_call_increments_count():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    tracker.track_call("search_code", {"keyword": "auth"})
    assert tracker.call_count == 1
    assert tracker.tool_counts["search_code"] == 1


def test_dedup_same_call():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    tracker.track_call("search_code", {"keyword": "auth"})
    assert tracker.is_duplicate("search_code", {"keyword": "auth"}) is True
    assert tracker.is_duplicate("search_code", {"keyword": "memory"}) is False


def test_within_budget():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    assert tracker.within_token_budget(3000) is True
    tracker.add_tokens(4000)
    assert tracker.within_token_budget(2000) is False


def test_within_round_limit():
    tracker = ToolCallTracker(max_rounds=3, max_total_tokens=50000)
    for i in range(3):
        tracker.track_call("search_code", {"keyword": f"kw{i}"})
    assert tracker.within_round_limit() is False
    tracker2 = ToolCallTracker(max_rounds=5, max_total_tokens=50000)
    tracker2.track_call("search_code", {"keyword": "test"})
    assert tracker2.within_round_limit() is True


def test_summary():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    tracker.track_call("search_code", {"keyword": "auth"})
    tracker.add_tokens(500)
    summary = tracker.summary()
    assert "search_code" in summary
    assert "total_tokens" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_call_tracker.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/reqradar/agent/tool_call_tracker.py
import json
import logging

logger = logging.getLogger("reqradar.tool_tracker")


class ToolCallTracker:
    def __init__(self, max_rounds: int = 15, max_total_tokens: int = 8000):
        self.max_rounds = max_rounds
        self.max_total_tokens = max_total_tokens
        self.call_count = 0
        self.tool_counts: dict[str, int] = {}
        self._seen_calls: dict[str, set] = {}
        self._total_tokens = 0

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

    def add_tokens(self, tokens: int) -> None:
        self._total_tokens += tokens
        logger.debug(
            "Tool token usage: %d/%d", self._total_tokens, self.max_total_tokens
        )

    def within_token_budget(self, estimated_tokens: int) -> bool:
        return (self._total_tokens + estimated_tokens) <= self.max_total_tokens

    def within_round_limit(self) -> bool:
        return self.call_count < self.max_rounds

    def summary(self) -> str:
        lines = [f"Total tool calls: {self.call_count}/{self.max_rounds}"]
        for name, count in self.tool_counts.items():
            lines.append(f"  {name}: {count} calls")
        lines.append(f"Total tool tokens: {self._total_tokens}/{self.max_total_tokens}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_call_tracker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/agent/tool_call_tracker.py tests/test_tool_call_tracker.py
git commit -m "feat: add ToolCallTracker for dedup, counting and token budget"
```

---

## Task 4: LLM客户端扩展 — complete_with_tools()

**Files:**
- Modify: `src/reqradar/modules/llm_client.py:16-47,117-199`
- Modify: `src/reqradar/agent/llm_utils.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_llm_client.py

class TestOpenAICompleteWithTools:
    @pytest.mark.asyncio
    async def test_complete_with_tools_returns_tool_calls(self):
        """When LLM responds with tool_calls, parse them correctly"""
        llm = OpenAIClient(api_key="test-key", model="test-model", base_url="http://localhost:9999/v1")
        # We mock httpx to return a tool_calls response
        # This is a structural test — we verify the method exists and returns correct shape
        # Full integration test would need a real or mock HTTP server
        assert hasattr(llm, "complete_with_tools")

    @pytest.mark.asyncio
    async def test_ollama_complete_with_tools_returns_none(self):
        """OllamaClient.complete_with_tools returns None (not supported)"""
        llm = OllamaClient(model="test", host="http://localhost:9999")
        result = await llm.complete_with_tools(
            messages=[{"role": "user", "content": "test"}],
            tools=[],
        )
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_llm_client.py::TestOpenAICompleteWithTools -v`
Expected: FAIL — `AttributeError: 'OpenAIClient' object has no attribute 'complete_with_tools'`

- [ ] **Step 3: Write minimal implementation**

在 `src/reqradar/modules/llm_client.py` 的 `LLMClient` 基类中增加方法：

```python
# 在 LLMClient 类中，complete_structured 方法之后添加：

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """使用 tool_use 协议发送请求，支持多轮工具调用

        Args:
            messages: 对话消息列表（可包含tool角色的消息）
            tools: 工具定义列表（OpenAI tool format）
            **kwargs: 传递给API的额外参数

        Returns:
            dict with keys:
            - "tool_calls": list of {id, name, arguments} if LLM wants to call tools
            - "content": str if LLM responded with text only
            - "structured_output": dict if LLM called the output function
            None if request fails
        """
        return None
```

在 `OpenAIClient` 类中增加实现（在 `complete_structured` 方法之后）：

```python
    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """使用 OpenAI tool_use 协议发送请求"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "tools": tools,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        if "tool_choice" in kwargs:
            payload["tool_choice"] = kwargs["tool_choice"]

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                message = result["choices"][0]["message"]
                tool_calls = message.get("tool_calls", [])
                content = message.get("content", "")

                if tool_calls:
                    parsed_calls = []
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        parsed_calls.append({
                            "id": tc.get("id", ""),
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", "{}"),
                        })
                    return {"tool_calls": parsed_calls, "assistant_message": message}
                elif content:
                    return {"content": content}
                else:
                    return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    logger.info("Tool use not supported (400), returning None")
                    return None
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
                logger.warning("complete_with_tools failed: %s", e)
                return None

        return None
```

在 `OllamaClient` 类中增加空实现（在 `embed` 方法之前）：

```python
    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], **kwargs
    ) -> dict | None:
        """Ollama暂不支持tool_use协议，返回None触发降级"""
        return None
```

同时在 `src/reqradar/agent/llm_utils.py` 中增加封装函数：

```python
async def _complete_with_tools(llm_client, messages: list[dict], tools: list[dict], **kwargs) -> dict | None:
    """调用LLM的tool_use接口，失败时返回None"""
    try:
        result = await llm_client.complete_with_tools(messages, tools, **kwargs)
        return result
    except Exception as e:
        logger.warning("complete_with_tools error: %s", e)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_llm_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/modules/llm_client.py src/reqradar/agent/llm_utils.py tests/test_llm_client.py
git commit -m "feat: add complete_with_tools() to LLMClient for tool_use protocol"
```

---

## Task 5: 9个Tool实现 — 封装现有能力模块

**Files:**
- Create: `src/reqradar/agent/tools/search_code.py`
- Create: `src/reqradar/agent/tools/read_file.py`
- Create: `src/reqradar/agent/tools/read_module_summary.py`
- Create: `src/reqradar/agent/tools/list_modules.py`
- Create: `src/reqradar/agent/tools/search_requirements.py`
- Create: `src/reqradar/agent/tools/get_dependencies.py`
- Create: `src/reqradar/agent/tools/get_contributors.py`
- Create: `src/reqradar/agent/tools/get_project_profile.py`
- Create: `src/reqradar/agent/tools/get_terminology.py`
- Test: `tests/test_tool_implementations.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_implementations.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from reqradar.agent.tools.search_code import SearchCodeTool
from reqradar.agent.tools.read_file import ReadFileTool
from reqradar.agent.tools.read_module_summary import ReadModuleSummaryTool
from reqradar.agent.tools.list_modules import ListModulesTool
from reqradar.agent.tools.search_requirements import SearchRequirementsTool
from reqradar.agent.tools.get_dependencies import GetDependenciesTool
from reqradar.agent.tools.get_contributors import GetContributorsTool
from reqradar.agent.tools.get_project_profile import GetProjectProfileTool
from reqradar.agent.tools.get_terminology import GetTerminologyTool
from reqradar.agent.tools.base import ToolResult


def _make_code_graph():
    from reqradar.modules.code_parser import CodeFile, CodeGraph, CodeSymbol
    return CodeGraph(files=[
        CodeFile(path="src/reqradar/agent/steps.py", symbols=[
            CodeSymbol(name="step_extract", type="function", line=1, end_line=10),
            CodeSymbol(name="step_analyze", type="function", line=12, end_line=20),
        ]),
        CodeFile(path="src/reqradar/modules/memory.py", symbols=[
            CodeSymbol(name="MemoryManager", type="class", line=1, end_line=50),
        ]),
    ])


def _make_memory_data():
    return {
        "project_profile": {
            "name": "ReqRadar",
            "description": "需求分析工具",
            "architecture_style": "分层架构",
            "tech_stack": {"languages": ["Python"], "frameworks": [], "key_dependencies": []},
        },
        "modules": [
            {"name": "agent", "responsibility": "Agent模块", "code_summary": "负责分析流程", "key_classes": ["StepRunner"]},
            {"name": "modules/memory", "responsibility": "记忆管理", "code_summary": "持久化存储", "key_classes": ["MemoryManager"]},
        ],
        "terminology": [
            {"term": "需求分析", "definition": "Requirement Analysis", "domain": "产品"},
        ],
    }


@pytest.mark.asyncio
async def test_search_code_tool():
    code_graph = _make_code_graph()
    tool = SearchCodeTool(code_graph=code_graph, repo_path="/tmp/fake")
    result = await tool.execute(keyword="step_extract")
    assert result.success is True
    assert "step_extract" in result.data


@pytest.mark.asyncio
async def test_search_code_no_match():
    code_graph = _make_code_graph()
    tool = SearchCodeTool(code_graph=code_graph, repo_path="/tmp/fake")
    result = await tool.execute(keyword="nonexistent_xyz")
    assert result.success is True
    assert "未找到" in result.data or "no match" in result.data.lower()


@pytest.mark.asyncio
async def test_read_module_summary_tool():
    memory_data = _make_memory_data()
    tool = ReadModuleSummaryTool(memory_data=memory_data)
    result = await tool.execute(module_name="agent")
    assert result.success is True
    assert "Agent模块" in result.data


@pytest.mark.asyncio
async def test_list_modules_tool():
    memory_data = _make_memory_data()
    tool = ListModulesTool(memory_data=memory_data)
    result = await tool.execute()
    assert result.success is True
    assert "agent" in result.data
    assert "modules/memory" in result.data


@pytest.mark.asyncio
async def test_get_project_profile_tool():
    memory_data = _make_memory_data()
    tool = GetProjectProfileTool(memory_data=memory_data)
    result = await tool.execute()
    assert result.success is True
    assert "ReqRadar" in result.data


@pytest.mark.asyncio
async def test_get_terminology_tool():
    memory_data = _make_memory_data()
    tool = GetTerminologyTool(memory_data=memory_data)
    result = await tool.execute()
    assert result.success is True
    assert "需求分析" in result.data


@pytest.mark.asyncio
async def test_get_dependencies_tool():
    code_graph = _make_code_graph()
    tool = GetDependenciesTool(code_graph=code_graph, memory_data=_make_memory_data())
    result = await tool.execute(module="agent")
    assert result.success is True


@pytest.mark.asyncio
async def test_get_contributors_tool_no_git():
    tool = GetContributorsTool(git_analyzer=None)
    result = await tool.execute(file_path="src/reqradar/agent/steps.py")
    assert result.success is False


@pytest.mark.asyncio
async def test_search_requirements_tool_no_store():
    tool = SearchRequirementsTool(vector_store=None)
    result = await tool.execute(query="web interface")
    assert result.success is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_implementations.py -v`
Expected: FAIL — ModuleNotFoundError for each tool

- [ ] **Step 3: Write minimal implementation for each tool**

每个Tool的实现模式相同：`__init__` 接收依赖的能力模块实例，`execute` 调用该实例并格式化结果为文本。

**search_code.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class SearchCodeTool(BaseTool):
    name = "search_code"
    description = "在项目代码中搜索包含指定关键词的类、函数或变量"
    parameters_schema = {
        "name": "search_code",
        "description": "在项目代码中搜索包含指定关键词的类、函数或变量",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（英文，如 auth、scheduler、memory）",
                },
                "symbol_type": {
                    "type": "string",
                    "enum": ["class", "function", "all"],
                    "description": "要搜索的符号类型，默认 all",
                },
            },
            "required": ["keyword"],
        },
    }

    def __init__(self, code_graph=None, repo_path: str = ""):
        self.code_graph = code_graph
        self.repo_path = repo_path

    async def execute(self, **kwargs) -> ToolResult:
        keyword = kwargs.get("keyword", "")
        symbol_type = kwargs.get("symbol_type", "all")

        if not self.code_graph or not keyword:
            return ToolResult(success=False, data="", error="No code graph or keyword")

        matches = self.code_graph.find_symbols([keyword])
        if not matches:
            return ToolResult(success=True, data=f"未找到包含 '{keyword}' 的代码符号")

        lines = []
        for f in matches[:10]:
            symbols = [s for s in f.symbols
                       if symbol_type == "all" or s.type == symbol_type]
            if symbols:
                sym_str = ", ".join(f"{s.name}({s.type})" for s in symbols[:5])
                lines.append(f"- {f.path}: {sym_str}")

        if not lines:
            return ToolResult(success=True, data=f"未找到类型为 '{symbol_type}' 且包含 '{keyword}' 的符号")

        return ToolResult(success=True, data="\n".join(lines))
```

**read_file.py:**
```python
from pathlib import Path

from reqradar.agent.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取项目中指定文件的源代码内容"
    parameters_schema = {
        "name": "read_file",
        "description": "读取项目中指定文件的源代码内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从1开始），不指定则从文件开头",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号，不指定则到文件末尾（最多2000行）",
                },
            },
            "required": ["path"],
        },
    }

    MAX_LINES = 2000

    def __init__(self, repo_path: str = ""):
        self.repo_path = repo_path

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("path", "")
        start_line = kwargs.get("start_line", 1)
        end_line = kwargs.get("end_line", start_line + self.MAX_LINES - 1)

        if not file_path:
            return ToolResult(success=False, data="", error="No file path provided")

        full_path = Path(self.repo_path) / file_path
        if not full_path.exists():
            return ToolResult(success=False, data="", error=f"File not found: {file_path}")

        try:
            content = full_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            total_lines = len(lines)

            start_idx = max(0, start_line - 1)
            end_idx = min(total_lines, end_line)
            selected = lines[start_idx:end_idx]

            truncated = end_idx < total_lines
            result_text = "\n".join(f"{start_idx + i + 1}: {line}" for i, line in enumerate(selected))

            if truncated:
                result_text += f"\n... (truncated, showing lines {start_line}-{end_idx} of {total_lines})"

            return ToolResult(success=True, data=result_text, truncated=truncated)

        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(success=False, data="", error=str(e))
```

**read_module_summary.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class ReadModuleSummaryTool(BaseTool):
    name = "read_module_summary"
    description = "获取指定模块的职责描述和代码摘要"
    parameters_schema = {
        "name": "read_module_summary",
        "description": "获取指定模块的职责描述和代码摘要",
        "parameters": {
            "type": "object",
            "properties": {
                "module_name": {
                    "type": "string",
                    "description": "模块名称（如 agent、modules/memory）",
                },
            },
            "required": ["module_name"],
        },
    }

    def __init__(self, memory_data: dict | None = None):
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        module_name = kwargs.get("module_name", "")
        if not self.memory_data or not module_name:
            return ToolResult(success=False, data="", error="No memory data or module name")

        for m in self.memory_data.get("modules", []):
            if m.get("name") == module_name or module_name.lower() in m.get("name", "").lower():
                lines = [f"模块: {m.get('name', '')}"]
                if m.get("responsibility"):
                    lines.append(f"职责: {m['responsibility']}")
                if m.get("code_summary"):
                    lines.append(f"代码摘要: {m['code_summary']}")
                if m.get("key_classes"):
                    lines.append(f"核心类: {', '.join(m['key_classes'])}")
                return ToolResult(success=True, data="\n".join(lines))

        return ToolResult(success=True, data=f"未找到模块: {module_name}")
```

**list_modules.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class ListModulesTool(BaseTool):
    name = "list_modules"
    description = "列出项目中的所有模块及其职责"
    parameters_schema = {
        "name": "list_modules",
        "description": "列出项目中的所有模块及其职责",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    }

    def __init__(self, memory_data: dict | None = None):
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        if not self.memory_data:
            return ToolResult(success=False, data="", error="No memory data")

        modules = self.memory_data.get("modules", [])
        if not modules:
            return ToolResult(success=True, data="项目尚未建立模块画像")

        lines = []
        for m in modules:
            line = f"- {m.get('name', 'unknown')}: {m.get('responsibility', '职责未定义')}"
            lines.append(line)

        return ToolResult(success=True, data="\n".join(lines))
```

**search_requirements.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class SearchRequirementsTool(BaseTool):
    name = "search_requirements"
    description = "在历史需求文档中进行语义搜索，查找与指定查询相似的需求"
    parameters_schema = {
        "name": "search_requirements",
        "description": "在历史需求文档中进行语义搜索，查找与指定查询相似的需求",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "语义搜索查询文本",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认5",
                },
            },
            "required": ["query"],
        },
    }

    def __init__(self, vector_store=None):
        self.vector_store = vector_store

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)

        if not self.vector_store:
            return ToolResult(success=False, data="", error="Vector store not available")

        if not query:
            return ToolResult(success=False, data="", error="No query provided")

        try:
            results = self.vector_store.search(query, top_k=top_k)
            if not results:
                return ToolResult(success=True, data="未找到相似需求")

            lines = []
            for r in results:
                title = r.metadata.get("title", r.id)
                similarity = round((1 - r.distance) * 100, 1)
                content_preview = r.content[:150].replace("\n", " ")
                lines.append(f"- [{r.id}] {title} (相似度: {similarity}%)\n  {content_preview}...")

            return ToolResult(success=True, data="\n\n".join(lines))

        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
```

**get_dependencies.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class GetDependenciesTool(BaseTool):
    name = "get_dependencies"
    description = "查询指定模块的上下游依赖关系"
    parameters_schema = {
        "name": "get_dependencies",
        "description": "查询指定模块的上下游依赖关系",
        "parameters": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "模块名称（如 agent、modules/memory）",
                },
            },
            "required": ["module"],
        },
    }

    def __init__(self, code_graph=None, memory_data: dict | None = None):
        self.code_graph = code_graph
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        module_name = kwargs.get("module", "")
        if not module_name:
            return ToolResult(success=False, data="", error="No module name")

        lines = [f"模块 '{module_name}' 的依赖分析:"]

        if self.memory_data:
            for m in self.memory_data.get("modules", []):
                if m.get("name") == module_name or module_name.lower() in m.get("name", "").lower():
                    deps = m.get("dependencies", [])
                    if deps:
                        lines.append(f"声明依赖: {', '.join(deps)}")
                    else:
                        lines.append("声明依赖: 无（可能需从代码推断）")

        if self.code_graph:
            import_lines = []
            for f in self.code_graph.files:
                if module_name.lower() in f.path.lower():
                    for imp in f.imports:
                        if "reqradar" in imp:
                            import_lines.append(f"  {imp}")
            if import_lines:
                lines.append("代码级依赖（reqradar内部）:")
                lines.extend(import_lines[:10])

        return ToolResult(success=True, data="\n".join(lines))
```

**get_contributors.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class GetContributorsTool(BaseTool):
    name = "get_contributors"
    description = "查询指定文件的主要贡献者（代码作者和维护者）"
    parameters_schema = {
        "name": "get_contributors",
        "description": "查询指定文件的主要贡献者（代码作者和维护者）",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）",
                },
            },
            "required": ["file_path"],
        },
    }

    def __init__(self, git_analyzer=None):
        self.git_analyzer = git_analyzer

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        if not self.git_analyzer:
            return ToolResult(success=False, data="", error="Git analyzer not available")

        if not file_path:
            return ToolResult(success=False, data="", error="No file path provided")

        try:
            results = self.git_analyzer.get_file_contributors([file_path])
            if not results or not results[0].primary_contributor:
                return ToolResult(success=True, data=f"未找到 {file_path} 的贡献者信息")

            lines = []
            fc = results[0]
            pc = fc.primary_contributor
            lines.append(f"文件: {file_path}")
            lines.append(f"主要贡献者: {pc.name} ({pc.email})")
            lines.append(f"  提交数: {pc.commit_count}, 行变更: +{pc.lines_added}/-{pc.lines_deleted}")

            for rc in fc.recent_contributors[:3]:
                if rc.email != pc.email:
                    lines.append(f"近期贡献者: {rc.name} ({rc.email}), 提交数: {rc.commit_count}")

            return ToolResult(success=True, data="\n".join(lines))

        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
```

**get_project_profile.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class GetProjectProfileTool(BaseTool):
    name = "get_project_profile"
    description = "获取项目画像信息，包括项目描述、技术栈和架构风格"
    parameters_schema = {
        "name": "get_project_profile",
        "description": "获取项目画像信息，包括项目描述、技术栈和架构风格",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    }

    def __init__(self, memory_data: dict | None = None):
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        if not self.memory_data:
            return ToolResult(success=False, data="", error="No memory data")

        profile = self.memory_data.get("project_profile", {})
        if not profile or not profile.get("description"):
            return ToolResult(success=True, data="项目画像尚未建立，请先运行 reqradar index")

        lines = [f"项目名称: {profile.get('name', '未知')}"]
        lines.append(f"描述: {profile.get('description', '未知')}")
        lines.append(f"架构风格: {profile.get('architecture_style', '未知')}")

        tech_stack = profile.get("tech_stack", {})
        if tech_stack:
            langs = tech_stack.get("languages", [])
            frameworks = tech_stack.get("frameworks", [])
            deps = tech_stack.get("key_dependencies", [])
            if langs:
                lines.append(f"编程语言: {', '.join(langs)}")
            if frameworks:
                lines.append(f"框架: {', '.join(frameworks)}")
            if deps:
                lines.append(f"关键依赖: {', '.join(deps)}")

        return ToolResult(success=True, data="\n".join(lines))
```

**get_terminology.py:**
```python
from reqradar.agent.tools.base import BaseTool, ToolResult


class GetTerminologyTool(BaseTool):
    name = "get_terminology"
    description = "获取项目已知的术语定义列表"
    parameters_schema = {
        "name": "get_terminology",
        "description": "获取项目已知的术语定义列表",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    }

    def __init__(self, memory_data: dict | None = None):
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        if not self.memory_data:
            return ToolResult(success=False, data="", error="No memory data")

        terms = self.memory_data.get("terminology", [])
        if not terms:
            return ToolResult(success=True, data="项目尚未积累术语定义")

        lines = []
        for t in terms:
            line = f"- {t.get('term', '')}: {t.get('definition', '未定义')}"
            if t.get("domain"):
                line += f" [{t['domain']}]"
            lines.append(line)

        return ToolResult(success=True, data="\n".join(lines))
```

更新 `__init__.py` 导出所有工具类：

```python
# src/reqradar/agent/tools/__init__.py
from reqradar.agent.tools.base import BaseTool, ToolResult
from reqradar.agent.tools.registry import ToolRegistry
from reqradar.agent.tools.search_code import SearchCodeTool
from reqradar.agent.tools.read_file import ReadFileTool
from reqradar.agent.tools.read_module_summary import ReadModuleSummaryTool
from reqradar.agent.tools.list_modules import ListModulesTool
from reqradar.agent.tools.search_requirements import SearchRequirementsTool
from reqradar.agent.tools.get_dependencies import GetDependenciesTool
from reqradar.agent.tools.get_contributors import GetContributorsTool
from reqradar.agent.tools.get_project_profile import GetProjectProfileTool
from reqradar.agent.tools.get_terminology import GetTerminologyTool

__all__ = [
    "BaseTool", "ToolResult", "ToolRegistry",
    "SearchCodeTool", "ReadFileTool", "ReadModuleSummaryTool",
    "ListModulesTool", "SearchRequirementsTool", "GetDependenciesTool",
    "GetContributorsTool", "GetProjectProfileTool", "GetTerminologyTool",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_implementations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/agent/tools/ tests/test_tool_implementations.py
git commit -m "feat: implement 9 analysis tools wrapping existing capability modules"
```

---

## Task 6: ToolUseLoop核心 — LLM↔Tool多轮交互

**Files:**
- Create: `src/reqradar/agent/tool_use_loop.py`
- Test: `tests/test_tool_use_loop.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_use_loop.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from reqradar.agent.tool_use_loop import run_tool_use_loop
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
async def test_loop_returns_structured_output_immediately():
    """When LLM returns structured output without tool calls, return it directly"""
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(return_value={
        "content": '{"summary": "test result"}'
    })

    registry = ToolRegistry()
    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="You are a test assistant",
        user_prompt="Analyze this",
        tools=[],
        tool_registry=registry,
        output_schema={"name": "test_output", "parameters": {"type": "object"}},
    )
    assert result == {"summary": "test result"}


@pytest.mark.asyncio
async def test_loop_calls_tool_then_returns():
    """When LLM calls a tool, execute it and continue"""
    llm = AsyncMock()
    # First call: LLM wants to call a tool
    llm.complete_with_tools = AsyncMock(side_effect=[
        {
            "tool_calls": [{"id": "tc1", "name": "echo", "arguments": '{"text": "hello"}'}],
            "assistant_message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "tc1", "type": "function", "function": {"name": "echo", "arguments": '{"text": "hello"}'}}
            ]},
        },
        # Second call: LLM returns final output
        {"content": '{"result": "done with echo: hello"}'},
    ])

    registry = ToolRegistry()
    registry.register(EchoTool())

    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="test",
        user_prompt="test",
        tools=["echo"],
        tool_registry=registry,
        output_schema={"name": "test", "parameters": {"type": "object"}},
        max_rounds=5,
    )
    assert "done" in result.get("result", "")


@pytest.mark.asyncio
async def test_loop_dedup_same_tool_call():
    """Dedup same tool+arguments to prevent wasted calls"""
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(side_effect=[
        {
            "tool_calls": [
                {"id": "tc1", "name": "echo", "arguments": '{"text": "same"}'},
                {"id": "tc2", "name": "echo", "arguments": '{"text": "same"}'},
            ],
            "assistant_message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "tc1", "type": "function", "function": {"name": "echo", "arguments": '{"text": "same"}'}},
                {"id": "tc2", "type": "function", "function": {"name": "echo", "arguments": '{"text": "same"}'}},
            ]},
        },
        {"content": '{"result": "ok"}'},
    ])

    registry = ToolRegistry()
    registry.register(EchoTool())

    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="test",
        user_prompt="test",
        tools=["echo"],
        tool_registry=registry,
        output_schema={"name": "test", "parameters": {"type": "object"}},
        max_rounds=5,
    )
    assert result.get("result") == "ok"


@pytest.mark.asyncio
async def test_loop_fallback_when_no_tool_use_support():
    """When complete_with_tools returns None, fall back to complete_structured"""
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(return_value=None)
    llm.complete_structured = AsyncMock(return_value={"summary": "fallback"})

    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="test",
        user_prompt="test",
        tools=[],
        tool_registry=ToolRegistry(),
        output_schema={"name": "test", "parameters": {"type": "object"}},
    )
    assert result == {"summary": "fallback"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_use_loop.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/reqradar/agent/tool_use_loop.py
import json
import logging

from reqradar.agent.llm_utils import _call_llm_structured, _parse_json_response, _complete_with_tools
from reqradar.agent.tool_call_tracker import ToolCallTracker
from reqradar.agent.tools.base import ToolResult

logger = logging.getLogger("reqradar.agent.tool_use_loop")


def _estimate_tokens(text: str) -> int:
    return len(text) // 3


async def run_tool_use_loop(
    llm_client,
    system_prompt: str,
    user_prompt: str,
    tools: list[str],
    tool_registry,
    output_schema: dict,
    max_rounds: int = 15,
    max_total_tokens: int = 8000,
    **kwargs,
) -> dict:
    tracker = ToolCallTracker(max_rounds=max_rounds, max_total_tokens=max_total_tokens)
    tool_schemas = tool_registry.get_schemas(tools) if tools else []
    tool_map = {t.name: t for t in (tool_registry._tools.values()) if t.name in tools} if tools else {}

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for round_idx in range(max_rounds + 1):
        if not tracker.within_round_limit() and round_idx > 0:
            logger.info("Tool use loop reached max rounds (%d), forcing final output", max_rounds)
            messages.append({"role": "user", "content": "请基于已获取的信息，直接输出最终分析结果，不要再调用工具。"})
            break

        if tool_schemas:
            response = await _complete_with_tools(llm_client, messages, tool_schemas, **kwargs)
        else:
            response = None

        if response is None:
            logger.info("Tool use not available, falling back to complete_structured")
            result = await _call_llm_structured(llm_client, messages, output_schema, **kwargs)
            return result or {}

        if "tool_calls" in response and response["tool_calls"]:
            assistant_msg = response.get("assistant_message", {})
            if assistant_msg:
                messages.append(assistant_msg)

            for tool_call in response["tool_calls"]:
                tc_name = tool_call.get("name", "")
                tc_id = tool_call.get("id", "")
                tc_args_str = tool_call.get("arguments", "{}")

                try:
                    tc_args = json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
                except json.JSONDecodeError:
                    tc_args = {}

                if tc_name not in tool_map:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"Error: Unknown tool '{tc_name}'",
                    })
                    continue

                if tracker.is_duplicate(tc_name, tc_args):
                    logger.info("Dedup: skipping duplicate call to %s with same args", tc_name)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"(此调用已去重，跳过重复请求)",
                    })
                    continue

                tracker.track_call(tc_name, tc_args)

                tool = tool_map[tc_name]
                try:
                    result = await tool.execute(**tc_args)
                    result_text = result.data if result.success else f"Error: {result.error}"
                except Exception as e:
                    result_text = f"Error executing {tc_name}: {e}"

                tokens = _estimate_tokens(result_text)
                if tracker.within_token_budget(tokens):
                    tracker.add_tokens(tokens)
                else:
                    result_text = f"Error: Token budget exceeded (used {tracker._total_tokens}/{max_total_tokens})"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_text,
                })

                logger.info("Tool call #%d: %s(%s) -> %d chars",
                            tracker.call_count, tc_name,
                            json.dumps(tc_args, ensure_ascii=False)[:80],
                            len(result_text))

        elif "content" in response:
            content = response["content"]
            try:
                parsed = _parse_json_response(content)
                return parsed
            except (json.JSONDecodeError, ValueError):
                return {"content": content}

    # Force final output
    logger.info("Generating final structured output after tool use loop")
    logger.info("Tool usage summary:\n%s", tracker.summary())
    result = await _call_llm_structured(llm_client, messages, output_schema, **kwargs)
    return result or {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_tool_use_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/agent/tool_use_loop.py tests/test_tool_use_loop.py
git commit -m "feat: add ToolUseLoop for multi-round LLM-tool interaction"
```

---

## Task 7: 配置扩展 — ToolUse相关配置项

**Files:**
- Modify: `src/reqradar/infrastructure/config.py:70-73`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_config.py` 末尾添加：

```python
def test_analysis_config_tool_use_defaults():
    from reqradar.infrastructure.config import AnalysisConfig
    config = AnalysisConfig()
    assert config.tool_use_max_rounds == 15
    assert config.tool_use_max_tokens == 8000
    assert config.tool_use_enabled is True


def test_analysis_config_tool_use_custom():
    from reqradar.infrastructure.config import AnalysisConfig
    config = AnalysisConfig(tool_use_max_rounds=5, tool_use_max_tokens=3000, tool_use_enabled=False)
    assert config.tool_use_max_rounds == 5
    assert config.tool_use_max_tokens == 3000
    assert config.tool_use_enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_config.py -v -k "tool_use"`
Expected: FAIL — `AttributeError: 'AnalysisConfig' object has no attribute 'tool_use_max_rounds'`

- [ ] **Step 3: Write minimal implementation**

在 `src/reqradar/infrastructure/config.py` 的 `AnalysisConfig` 类中增加字段：

```python
class AnalysisConfig(BaseModel):
    max_similar_reqs: int = Field(default=5)
    max_code_files: int = Field(default=10)
    contributors_lookback_months: int = Field(default=6)
    tool_use_enabled: bool = Field(default=True, description="启用LLM工具调用循环")
    tool_use_max_rounds: int = Field(default=15, description="每步最大工具调用轮次")
    tool_use_max_tokens: int = Field(default=8000, description="工具结果的总token预算")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_config.py -v -k "tool_use"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/infrastructure/config.py tests/test_config.py
git commit -m "feat: add tool_use config options to AnalysisConfig"
```

---

## Task 8: 数据模型扩展 — DeepAnalysis增加叙述字段

**Files:**
- Modify: `src/reqradar/core/context.py:81-89`
- Modify: `src/reqradar/agent/schemas.py:104-172`（ANALYZE_SCHEMA增加字段）

- [ ] **Step 1: Write the failing test**

在 `tests/test_context.py` 末尾添加：

```python
def test_deep_analysis_has_narrative_fields():
    from reqradar.core.context import DeepAnalysis
    da = DeepAnalysis()
    assert hasattr(da, "impact_narrative")
    assert hasattr(da, "risk_narrative")
    assert da.impact_narrative == ""
    assert da.risk_narrative == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_context.py -v -k "narrative"`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `src/reqradar/core/context.py` 的 `DeepAnalysis` 类中增加字段：

```python
@dataclass
class DeepAnalysis:
    impact_modules: list = field(default_factory=list)
    contributors: list = field(default_factory=list)
    risk_level: str = "unknown"
    risk_details: list = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    change_assessment: list[ChangeAssessment] = field(default_factory=list)
    verification_points: list[str] = field(default_factory=list)
    implementation_hints: ImplementationHints = field(default_factory=ImplementationHints)
    impact_narrative: str = ""
    risk_narrative: str = ""
```

在 `src/reqradar/agent/schemas.py` 的 `ANALYZE_SCHEMA` 中增加字段：

```python
ANALYZE_SCHEMA = {
    "name": "analyze_risks",
    "description": "评估技术影响和风险",
    "parameters": {
        "type": "object",
        "properties": {
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
            },
            "risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "severity": {"type": "string"},
                        "scope": {"type": "string"},
                        "mitigation": {"type": "string"},
                    },
                    "required": ["description", "severity"],
                },
            },
            "change_assessment": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module": {"type": "string"},
                        "change_type": {"type": "string", "enum": ["new", "modify", "remove", "refactor"]},
                        "impact_level": {"type": "string", "enum": ["low", "medium", "high"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["module", "change_type", "impact_level"],
                },
            },
            "verification_points": {
                "type": "array",
                "items": {"type": "string"},
            },
            "implementation_hints": {
                "type": "object",
                "properties": {
                    "approach": {"type": "string"},
                    "effort_estimate": {"type": "string"},
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                },
            },
            "impact_narrative": {
                "type": "string",
                "description": "影响范围的自然语言描述（100-150字，描述涉及的技术组件和数据流向）",
            },
            "risk_narrative": {
                "type": "string",
                "description": "风险分析的自然语言描述（150-200字，主要风险和缓解思路）",
            },
        },
        "required": ["risk_level"],
    },
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_context.py -v -k "narrative"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/core/context.py src/reqradar/agent/schemas.py tests/test_context.py
git commit -m "feat: add impact_narrative and risk_narrative to DeepAnalysis and ANALYZE_SCHEMA"
```

---

## Task 9: 改造step_analyze — Tool-Use Agent核心步骤

**Files:**
- Modify: `src/reqradar/agent/steps.py:342-476`
- Modify: `src/reqradar/agent/prompts.py`

- [ ] **Step 1: 重写ANALYZE_PROMPT，加入工具使用指引**

在 `src/reqradar/agent/prompts.py` 中替换 `ANALYZE_PROMPT`：

```python
ANALYZE_PROMPT = """你是一位资深架构师，正在分析需求对项目代码的影响。

## 当前需求
{summary}

## 项目上下文
{project_context_section}

{terminology_section}

## 你的任务
1. 使用可用工具主动查询项目代码和结构信息
2. 基于实际代码内容，评估需求的技术影响
3. 输出结构化分析结果

## 分析流程建议
- 先调用 list_modules() 了解项目整体结构
- 对可能受影响的模块，调用 read_module_summary() 了解职责
- 对关键模块，调用 read_file() 查看具体代码实现
- 调用 get_dependencies() 了解模块间依赖
- 调用 get_contributors() 找到相关维护者
- 如需参考历史，调用 search_requirements() 查找相似需求

## 输出要求
- risk_level: 总体风险等级
- risks: 至少2个结构化风险项（基于代码中的实际耦合和约束）
- change_assessment: 每个受影响模块的变更评估（基于代码中的实际类和方法）
- verification_points: 至少3个评审验证要点
- impact_narrative: 影响范围描述（100-150字，引用你查看的具体代码）
- risk_narrative: 风险分析描述（150-200字，基于代码中的实际风险点）
- implementation_hints: 实施方向建议"""
```

- [ ] **Step 2: 改造step_analyze使用tool_use_loop**

在 `src/reqradar/agent/steps.py` 中替换 `step_analyze` 函数：

```python
async def step_analyze(
    context: AnalysisContext, code_graph, git_analyzer, llm_client=None,
    tool_registry=None, analysis_config=None,
) -> DeepAnalysis:
    """Step 4: 深度分析（Tool-Use Agent版）"""
    analysis = DeepAnalysis()

    tool_use_enabled = (analysis_config.tool_use_enabled
                        if analysis_config else True)
    max_rounds = analysis_config.tool_use_max_rounds if analysis_config else 15
    max_tokens = analysis_config.tool_use_max_tokens if analysis_config else 8000

    if llm_client and context.memory_data and context.understanding:
        project_context_section = _build_project_context_section(context.memory_data)
        terminology_section = _build_terminology_section(context.memory_data)
        summary = context.understanding.summary if context.understanding else ""

        if tool_use_enabled and tool_registry:
            from reqradar.agent.tool_use_loop import run_tool_use_loop

            tool_names = [
                "search_code", "read_file", "read_module_summary",
                "list_modules", "search_requirements", "get_dependencies",
                "get_contributors", "get_project_profile", "get_terminology",
            ]
            available_tools = [n for n in tool_names if tool_registry.get(n) is not None]

            result = await run_tool_use_loop(
                llm_client=llm_client,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=ANALYZE_PROMPT.format(
                    summary=summary,
                    project_context_section=project_context_section,
                    terminology_section=terminology_section,
                ),
                tools=available_tools,
                tool_registry=tool_registry,
                output_schema=ANALYZE_SCHEMA,
                max_rounds=max_rounds,
                max_total_tokens=max_tokens,
            )
        else:
            result = await _run_analyze_fallback(
                context, code_graph, llm_client
            )

        _populate_analysis_from_result(analysis, result)

    if not analysis.impact_modules:
        keywords = context.expanded_keywords if context.expanded_keywords else (
            context.understanding.keywords if context.understanding else []
        )
        if code_graph and keywords:
            matched_files = code_graph.find_symbols(keywords)
            analysis.impact_modules = [
                {
                    "path": f.path,
                    "symbols": [s.name for s in f.symbols[:5]],
                    "relevance": "unknown",
                    "relevance_reason": "基于关键词匹配",
                    "suggested_changes": "",
                }
                for f in matched_files[:10]
            ]

    if git_analyzer and analysis.impact_modules:
        try:
            file_paths = [m["path"] for m in analysis.impact_modules]
            contributor_info = git_analyzer.get_file_contributors(file_paths)
            analysis.contributors = [
                {
                    "name": c.primary_contributor.name if c.primary_contributor else "未知",
                    "email": c.primary_contributor.email if c.primary_contributor else "",
                    "file": c.file_path,
                    "reason": "主要贡献者",
                }
                for c in contributor_info[:5]
                if c.primary_contributor
            ]
        except (GitException, OSError, AttributeError) as e:
            logger.warning("Git analysis failed: %s", e)

    return analysis


async def _run_analyze_fallback(context, code_graph, llm_client) -> dict:
    """降级：不使用工具调用的原始分析逻辑"""
    understanding = context.understanding
    memory_data = context.memory_data

    impact_modules = await _smart_module_matching(
        understanding, memory_data, code_graph, llm_client,
    )

    modules_text = ""
    if impact_modules:
        modules_text = "\n".join(
            f"- {m['path']} ({', '.join(m['symbols'][:3])})"
            for m in impact_modules[:5]
        )
    else:
        modules_text = "无匹配代码模块（请根据项目知识推断）"

    project_context_section = _build_project_context_section(memory_data)
    terminology_section = _build_terminology_section(memory_data)

    messages = [
        {
            "role": "user",
            "content": ANALYZE_PROMPT.format(
                summary=understanding.summary if understanding else "",
                project_context_section=project_context_section,
                terminology_section=terminology_section,
            ),
        },
    ]
    result = await _call_llm_structured(llm_client, messages, ANALYZE_SCHEMA, max_tokens=2048)
    if impact_modules:
        result["_impact_modules"] = impact_modules
    return result


def _populate_analysis_from_result(analysis: DeepAnalysis, result: dict):
    """从LLM结果填充DeepAnalysis对象"""
    if not result:
        return

    analysis.risk_level = result.get("risk_level", "medium")

    for r in result.get("risks", []):
        if isinstance(r, dict):
            analysis.risks.append(
                RiskItem(
                    description=r.get("description", ""),
                    severity=r.get("severity", "medium"),
                    scope=r.get("scope", ""),
                    mitigation=r.get("mitigation", ""),
                )
            )
    analysis.risk_details = [r.description for r in analysis.risks]

    for ca in result.get("change_assessment", []):
        if isinstance(ca, dict):
            analysis.change_assessment.append(
                ChangeAssessment(
                    module=ca.get("module", ""),
                    change_type=ca.get("change_type", "modify"),
                    impact_level=ca.get("impact_level", "medium"),
                    reason=ca.get("reason", ""),
                )
            )

    analysis.verification_points = result.get("verification_points", [])

    impl_hints = result.get("implementation_hints", {})
    if isinstance(impl_hints, dict):
        analysis.implementation_hints = ImplementationHints(
            approach=impl_hints.get("approach", ""),
            effort_estimate=impl_hints.get("effort_estimate", ""),
            dependencies=impl_hints.get("dependencies", []),
        )

    analysis.impact_narrative = result.get("impact_narrative", "")
    analysis.risk_narrative = result.get("risk_narrative", "")

    if "_impact_modules" in result:
        analysis.impact_modules = result["_impact_modules"]
    elif result.get("impact_modules"):
        analysis.impact_modules = result["impact_modules"]
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/ -v --ignore=tests/test_cli_integration.py`
Expected: PASS（可能需更新部分mock的签名以匹配新的可选参数）

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/agent/steps.py src/reqradar/agent/prompts.py
git commit -m "feat: refactor step_analyze to use tool-use loop with fallback"
```

---

## Task 10: 改造其他LLM步骤 — extract/map_keywords/retrieve/generate

**Files:**
- Modify: `src/reqradar/agent/steps.py`
- Modify: `src/reqradar/agent/prompts.py`

- [ ] **Step 1: 重写各步骤的prompt，加入工具使用指引**

**EXTRACT_PROMPT:**
```python
EXTRACT_PROMPT = """你是一个专业的需求分析助手，负责深入理解需求文档并提取结构化信息。

## 已知项目上下文
{terminology_section}

{project_context_section}

## 需求文档
---
{content}
---

## 任务
1. 仔细阅读需求文档
2. 可使用工具查询项目信息以辅助理解（如 get_project_profile 了解项目背景，search_code 验证术语是否存在于代码中）
3. 提取结构化信息：
   - summary: 需求的业务视角理解
   - terms: 关键术语及其定义（至少3个，定义需准确）
   - keywords: 5-10个搜索关键词
   - structured_constraints: 约束条件（按类型分类）
   - business_goals: 业务目标
   - priority_suggestion/reason: 优先级建议

术语定义应基于项目实际代码验证，而非猜测。"""
```

**KEYWORD_MAPPING_PROMPT:**
```python
KEYWORD_MAPPING_PROMPT = """请将以下业务术语映射为可能的代码搜索词。

业务术语列表：
{terms}

## 任务
对于每个业务术语，请提供至少3个可能的代码层术语。可使用 search_code 工具验证映射是否存在于项目中。

映射维度：
1. 英文翻译或同义词
2. 驼峰命名形式（camelCase）
3. 下划线命名形式（snake_case）
4. 常见缩写

请输出JSON格式的映射列表。"""
```

**RETRIEVE_PROMPT:**
```python
RETRIEVE_PROMPT = """基于以下关键词和检索到的相似需求，评估每个需求的关联度和参考价值。

关键词：{keywords}

检索到的相似需求：
{results}

输出JSON，evaluations 为数组，每个元素包含 id/title/relevance/reason。"""
```

**GENERATE_PROMPT:**
```python
GENERATE_PROMPT = """基于以下分析上下文，生成需求分析报告的关键叙述段落。

需求摘要：{summary}

影响模块：{modules}

评审人建议：{contributors}

风险评估：{risk_level} - {risk_details}

变更评估：{change_assessment}

{project_context_section}

可使用 get_project_profile 工具获取更多项目上下文信息。

请分别生成以下段落，要求有深度、有分析、有建议，不要泛泛而谈：
- requirement_understanding: 需求理解（150-200字，包含背景、核心问题、成功标准）
- impact_narrative: 影响范围描述（100-150字，描述涉及的技术组件和数据流向）
- risk_narrative: 主要风险和缓解思路的自然语言描述（150-200字）
- implementation_suggestion: 实施方向建议和注意事项（100-150字）"""
```

- [ ] **Step 2: 改造step_extract使用tool_use_loop**

在 `src/reqradar/agent/steps.py` 中替换 `step_extract` 函数签名和实现：

```python
async def step_extract(
    context: AnalysisContext, llm_client, tool_registry=None, analysis_config=None,
) -> RequirementUnderstanding:
    """Step 2: 提取关键术语和结构化信息（Tool-Use Agent版）"""
    understanding = RequirementUnderstanding()
    understanding.raw_text = context.requirement_text

    tool_use_enabled = (analysis_config.tool_use_enabled
                        if analysis_config else True)
    max_rounds = analysis_config.tool_use_max_rounds if analysis_config else 15
    max_tokens = analysis_config.tool_use_max_tokens if analysis_config else 8000

    try:
        terminology_section = _build_terminology_section(context.memory_data)
        project_context_section = _build_project_context_section(context.memory_data)

        if tool_use_enabled and tool_registry:
            from reqradar.agent.tool_use_loop import run_tool_use_loop

            extract_tool_names = [
                "get_project_profile", "get_terminology",
                "search_code", "read_file",
            ]
            available_tools = [n for n in extract_tool_names if tool_registry.get(n) is not None]

            result = await run_tool_use_loop(
                llm_client=llm_client,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=EXTRACT_PROMPT.format(
                    content=context.requirement_text,
                    terminology_section=terminology_section,
                    project_context_section=project_context_section,
                ),
                tools=available_tools,
                tool_registry=tool_registry,
                output_schema=EXTRACT_SCHEMA,
                max_rounds=min(max_rounds, 8),
                max_total_tokens=min(max_tokens, 4000),
            )
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": EXTRACT_PROMPT.format(
                        content=context.requirement_text[:4000],
                        terminology_section=terminology_section,
                        project_context_section=project_context_section,
                    ),
                },
            ]
            result = await _call_llm_structured(llm_client, messages, EXTRACT_SCHEMA, max_tokens=2048)

        understanding.summary = result.get("summary", "")
        understanding.keywords = result.get("keywords", [])
        understanding.business_goals = result.get("business_goals", "")
        understanding.priority_suggestion = result.get("priority_suggestion", "")
        understanding.priority_reason = result.get("priority_reason", "")

        for t in result.get("terms", []):
            if isinstance(t, dict) and t.get("term"):
                understanding.terms.append(
                    TermDefinition(
                        term=t.get("term", ""),
                        definition=t.get("definition", ""),
                        domain=t.get("domain", ""),
                    )
                )

        for c in result.get("structured_constraints", []):
            if isinstance(c, dict) and c.get("description"):
                understanding.structured_constraints.append(
                    StructuredConstraint(
                        description=c.get("description", ""),
                        constraint_type=c.get("constraint_type", "other"),
                        source=c.get("source", "requirement_document"),
                    )
                )

        understanding.constraints = (
            [c.description for c in understanding.structured_constraints]
            + result.get("constraints", [])
        )

        if not understanding.keywords:
            understanding.keywords = [t.term for t in understanding.terms]

    except (json.JSONDecodeError, LLMException) as e:
        logger.warning("LLM extract failed, using fallback keyword extraction: %s", e)
        understanding.keywords = _fallback_keyword_extraction(context.requirement_text)
    except (AttributeError, KeyError, TypeError) as e:
        logger.warning("Unexpected error in step_extract, using fallback: %s", e)
        understanding.keywords = _fallback_keyword_extraction(context.requirement_text)

    context.understanding = understanding
    return understanding
```

- [ ] **Step 3: 改造step_map_keywords使用tool_use_loop**

替换 `step_map_keywords` 函数：

```python
async def step_map_keywords(
    context: AnalysisContext, llm_client, tool_registry=None, analysis_config=None,
) -> dict:
    """将业务术语映射为代码搜索词（Tool-Use Agent版）"""
    understanding = context.understanding
    if not understanding or (not understanding.terms and not understanding.keywords):
        logger.info("No terms or keywords to map")
        return {}

    terms_to_map = []
    if understanding.terms:
        terms_to_map = [t.term for t in understanding.terms]
    elif understanding.keywords:
        terms_to_map = understanding.keywords[:10]

    if not terms_to_map:
        return {}

    tool_use_enabled = (analysis_config.tool_use_enabled
                        if analysis_config else True)

    try:
        if tool_use_enabled and tool_registry:
            from reqradar.agent.tool_use_loop import run_tool_use_loop

            map_tool_names = ["search_code", "read_module_summary"]
            available_tools = [n for n in map_tool_names if tool_registry.get(n) is not None]

            result = await run_tool_use_loop(
                llm_client=llm_client,
                system_prompt="你是代码搜索专家，将业务术语映射为代码层搜索词。",
                user_prompt=KEYWORD_MAPPING_PROMPT.format(
                    terms="\n".join(f"- {t}" for t in terms_to_map),
                ),
                tools=available_tools,
                tool_registry=tool_registry,
                output_schema=KEYWORD_MAPPING_SCHEMA,
                max_rounds=8,
                max_total_tokens=3000,
            )
        else:
            messages = [
                {
                    "role": "user",
                    "content": KEYWORD_MAPPING_PROMPT.format(
                        terms="\n".join(f"- {t}" for t in terms_to_map),
                    ),
                },
            ]
            result = await _call_llm_structured(llm_client, messages, KEYWORD_MAPPING_SCHEMA, max_tokens=1024)

        mappings = {}
        if result and "mappings" in result:
            for m in result["mappings"]:
                if isinstance(m, dict) and m.get("business_term"):
                    mappings[m["business_term"]] = m.get("code_terms", [])

        if mappings:
            context.expanded_keywords = _expand_keywords(terms_to_map, mappings)
            logger.info(
                "Keyword mapping completed: %d terms mapped to %d search keywords",
                len(mappings), len(context.expanded_keywords),
            )

        return mappings

    except (LLMException, json.JSONDecodeError, KeyError) as e:
        logger.warning("Keyword mapping failed: %s", e)
        context.expanded_keywords = terms_to_map
        return {}
```

- [ ] **Step 4: 改造step_retrieve使用tool_use_loop**

替换 `step_retrieve` 函数：

```python
async def step_retrieve(
    context: AnalysisContext, vector_store, llm_client=None,
    tool_registry=None, analysis_config=None,
) -> RetrievedContext:
    """Step 3: 检索相似需求与代码（Tool-Use Agent版）"""
    retrieved = RetrievedContext()

    keywords = context.understanding.keywords if context.understanding else []
    expanded_keywords = context.expanded_keywords if context.expanded_keywords else keywords

    if not keywords:
        logger.info("No keywords extracted, skipping retrieval")
        return retrieved

    if vector_store:
        try:
            search_terms = expanded_keywords if expanded_keywords else keywords
            query = " ".join(search_terms[:10])
            results = vector_store.search(query, top_k=5)

            raw_reqs = [
                {
                    "id": r.id,
                    "content": r.content,
                    "metadata": r.metadata,
                    "distance": r.distance,
                }
                for r in results
            ]

            if llm_client and raw_reqs:
                tool_use_enabled = (analysis_config.tool_use_enabled
                                    if analysis_config else True)

                if tool_use_enabled and tool_registry:
                    from reqradar.agent.tool_use_loop import run_tool_use_loop

                    retrieve_tool_names = ["search_requirements", "get_terminology"]
                    available_tools = [n for n in retrieve_tool_names if tool_registry.get(n) is not None]

                    results_text = "\n".join(
                        f"- [{r['id']}] {r['metadata'].get('title', 'Unknown')}: {r['content'][:200]}"
                        for r in raw_reqs[:5]
                    )

                    result = await run_tool_use_loop(
                        llm_client=llm_client,
                        system_prompt="你是需求关联分析专家。",
                        user_prompt=RETRIEVE_PROMPT.format(
                            keywords=", ".join(keywords[:5]),
                            results=results_text,
                        ),
                        tools=available_tools,
                        tool_registry=tool_registry,
                        output_schema=RETRIEVE_SCHEMA,
                        max_rounds=5,
                        max_total_tokens=2000,
                    )

                    evaluations = result.get("evaluations", result) if isinstance(result, dict) else []
                    if isinstance(evaluations, list):
                        for ev in evaluations:
                            for r in raw_reqs:
                                if r["id"] == ev.get("id", ""):
                                    r["relevance"] = ev.get("relevance", "unknown")
                                    r["reason"] = ev.get("reason", "")
                                    break
                else:
                    try:
                        results_text = "\n".join(
                            f"- [{r['id']}] {r['metadata'].get('title', 'Unknown')}: {r['content'][:200]}"
                            for r in raw_reqs[:5]
                        )
                        messages = [
                            {
                                "role": "user",
                                "content": RETRIEVE_PROMPT.format(
                                    keywords=", ".join(keywords[:5]),
                                    results=results_text,
                                ),
                            },
                        ]
                        evaluated = await _call_llm_structured(
                            llm_client, messages, RETRIEVE_SCHEMA, max_tokens=1024
                        )
                        evaluations = evaluated.get("evaluations", evaluated)
                        if isinstance(evaluations, list):
                            for ev in evaluations:
                                for r in raw_reqs:
                                    if r["id"] == ev.get("id", ""):
                                        r["relevance"] = ev.get("relevance", "unknown")
                                        r["reason"] = ev.get("reason", "")
                                        break
                    except (json.JSONDecodeError, LLMException, AttributeError, KeyError, TypeError) as e:
                        logger.warning("LLM retrieve evaluation failed, using raw results: %s", e)

            retrieved.similar_requirements = raw_reqs
        except (VectorStoreException, OSError, KeyError) as e:
            logger.warning("Vector search failed: %s", e)
            retrieved.similar_requirements = []

    return retrieved
```

- [ ] **Step 5: 改造step_generate使用tool_use_loop**

替换 `step_generate` 函数：

```python
async def step_generate(
    context: AnalysisContext, llm_client, tool_registry=None, analysis_config=None,
) -> GeneratedContent:
    """Step 5: 生成报告段落（Tool-Use Agent版）"""
    understanding = context.understanding
    analysis = context.deep_analysis
    retrieved = context.retrieved_context

    similar_reqs_str = ""
    if retrieved and retrieved.similar_requirements:
        for req in retrieved.similar_requirements[:3]:
            similar_reqs_str += f"- {req.get('metadata', {}).get('title', 'Unknown')}\n"

    modules_str = ""
    if analysis and analysis.impact_modules:
        for m in analysis.impact_modules[:5]:
            modules_str += f"- {m['path']}\n"

    contributors_str = ""
    if analysis and analysis.contributors:
        for c in analysis.contributors[:3]:
            contributors_str += f"- {c['name']} ({c['file']})\n"

    risk_analysis = "待评估"
    if analysis and analysis.risk_level != "unknown":
        risk_analysis = analysis.risk_level
        if analysis.risk_details:
            risk_analysis += ": " + ", ".join(analysis.risk_details[:3])

    change_assessment_str = ""
    if analysis and analysis.change_assessment:
        for ca in analysis.change_assessment[:3]:
            change_assessment_str += f"- {ca.module}: {ca.change_type} ({ca.impact_level})\n"

    project_context_section = _build_project_context_section(context.memory_data)

    prompt = GENERATE_PROMPT.format(
        summary=understanding.summary if understanding else "",
        modules=modules_str or "无",
        contributors=contributors_str or "无",
        risk_level=analysis.risk_level if analysis else "unknown",
        risk_details=risk_analysis,
        change_assessment=change_assessment_str or "无",
        project_context_section=project_context_section,
    )

    tool_use_enabled = (analysis_config.tool_use_enabled
                        if analysis_config else True)

    try:
        if tool_use_enabled and tool_registry:
            from reqradar.agent.tool_use_loop import run_tool_use_loop

            gen_tool_names = ["get_project_profile"]
            available_tools = [n for n in gen_tool_names if tool_registry.get(n) is not None]

            result = await run_tool_use_loop(
                llm_client=llm_client,
                system_prompt="你是需求分析报告撰写专家。",
                user_prompt=prompt,
                tools=available_tools,
                tool_registry=tool_registry,
                output_schema=GENERATE_SCHEMA,
                max_rounds=3,
                max_total_tokens=2000,
            )
        else:
            messages = [{"role": "user", "content": prompt}]
            result = await _call_llm_structured(llm_client, messages, GENERATE_SCHEMA, max_tokens=2048)

        return GeneratedContent(
            requirement_understanding=result.get("requirement_understanding", ""),
            impact_narrative=result.get("impact_narrative", ""),
            risk_narrative=result.get("risk_narrative", ""),
            implementation_suggestion=result.get("implementation_suggestion", ""),
        )

    except (json.JSONDecodeError, LLMException, AttributeError, KeyError, TypeError) as e:
        logger.warning("LLM generate failed, using fallback: %s", e)
        return GeneratedContent(
            requirement_understanding=understanding.summary if understanding else "无法生成",
            impact_narrative=analysis.impact_narrative if analysis else "",
            risk_narrative=analysis.risk_narrative if analysis else "",
            implementation_suggestion="",
        )
```

- [ ] **Step 6: Run existing tests to verify no regressions**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/ -v --ignore=tests/test_cli_integration.py`
Expected: PASS（可能需更新mock签名匹配新的可选参数）

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/agent/steps.py src/reqradar/agent/prompts.py
git commit -m "feat: refactor all LLM steps to use tool-use loop with per-step tool subsets"
```

---

## Task 11: CLI集成 — 传入ToolRegistry和工具实例

**Files:**
- Modify: `src/reqradar/cli/main.py:222-412`

- [ ] **Step 1: 在analyze命令中构建ToolRegistry和工具实例**

在 `src/reqradar/cli/main.py` 的 `run_analysis()` 函数中，在创建 `context` 之后、创建 `scheduler` 之前，添加工具注册逻辑：

```python
        # Build tool registry
        from reqradar.agent.tools import (
            ToolRegistry, SearchCodeTool, ReadFileTool,
            ReadModuleSummaryTool, ListModulesTool,
            SearchRequirementsTool, GetDependenciesTool,
            GetContributorsTool, GetProjectProfileTool,
            GetTerminologyTool,
        )

        tool_registry = ToolRegistry()
        repo_path_str = str(repo_path)

        if code_graph:
            tool_registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path_str))
            tool_registry.register(GetDependenciesTool(code_graph=code_graph, memory_data=memory_data))

        tool_registry.register(ReadFileTool(repo_path=repo_path_str))
        tool_registry.register(ReadModuleSummaryTool(memory_data=memory_data))
        tool_registry.register(ListModulesTool(memory_data=memory_data))
        tool_registry.register(GetProjectProfileTool(memory_data=memory_data))
        tool_registry.register(GetTerminologyTool(memory_data=memory_data))

        if vector_store:
            tool_registry.register(SearchRequirementsTool(vector_store=vector_store))

        if git_analyzer:
            tool_registry.register(GetContributorsTool(git_analyzer=git_analyzer))
```

然后修改各 `wrapped_*` 函数传入 `tool_registry` 和 `analysis_config`：

```python
        async def wrapped_extract(ctx):
            return await step_extract(ctx, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)

        async def wrapped_map_keywords(ctx):
            return await step_map_keywords(ctx, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)

        async def wrapped_retrieve(ctx):
            result = await step_retrieve(ctx, vector_store, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)
            ctx.retrieved_context = result
            return result

        async def wrapped_analyze(ctx):
            result = await step_analyze(ctx, code_graph, git_analyzer, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)
            ctx.deep_analysis = result
            return result

        async def wrapped_generate(ctx):
            return await step_generate(ctx, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)
```

- [ ] **Step 2: Run existing tests**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/ -v --ignore=tests/test_cli_integration.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/reqradar/cli/main.py
git commit -m "feat: integrate ToolRegistry into CLI analyze command"
```

---

## Task 12: 报告渲染修复 — 消除None显示、格式化tech_stack

**Files:**
- Modify: `src/reqradar/core/report.py:79-110`

- [ ] **Step 1: 修复report.py中的None显示和tech_stack格式化**

在 `src/reqradar/core/report.py` 的 `render` 方法中，修改 `template_data` 构建：

```python
        impact_narrative = gen.impact_narrative if gen and gen.impact_narrative else ""
        if not impact_narrative and analysis and hasattr(analysis, "impact_narrative") and analysis.impact_narrative:
            impact_narrative = analysis.impact_narrative

        risk_narrative = gen.risk_narrative if gen and gen.risk_narrative else ""
        if not risk_narrative and analysis and hasattr(analysis, "risk_narrative") and analysis.risk_narrative:
            risk_narrative = analysis.risk_narrative

        implementation_suggestion = gen.implementation_suggestion if gen and gen.implementation_suggestion else ""
```

以及修复 `tech_stack` 的格式化：

```python
        tech_stack_str = ""
        if project_profile and isinstance(project_profile, dict):
            ts = project_profile.get("tech_stack", {})
            if isinstance(ts, dict):
                parts = []
                if ts.get("languages"):
                    parts.append("语言: " + ", ".join(ts["languages"]))
                if ts.get("frameworks"):
                    parts.append("框架: " + ", ".join(ts["frameworks"]))
                if ts.get("key_dependencies"):
                    parts.append("依赖: " + ", ".join(ts["key_dependencies"]))
                tech_stack_str = "; ".join(parts) if parts else "未知"
            else:
                tech_stack_str = str(ts)
```

在 `template_data` 中替换对应字段：

```python
        template_data = {
            # ... existing fields ...
            "impact_narrative": impact_narrative,
            "risk_narrative": risk_narrative,
            "implementation_suggestion": implementation_suggestion,
            # ... existing fields ...
        }
```

同时在 `template_data` 中替换 `project_profile` 相关：

```python
        template_data["project_profile"] = project_profile
        template_data["tech_stack_str"] = tech_stack_str
```

注意：由于模板 `report.md.j2` 第198行直接输出 `project_profile.tech_stack`，需要更新模板或传入格式化后的字符串。最简方案：在 `template_data` 中直接修改 `project_profile` 的 `tech_stack` 为格式化字符串：

```python
        if project_profile and isinstance(project_profile, dict):
            project_profile = dict(project_profile)
            ts = project_profile.get("tech_stack", {})
            if isinstance(ts, dict):
                parts = []
                if ts.get("languages"):
                    parts.append("语言: " + ", ".join(ts["languages"]))
                if ts.get("frameworks"):
                    parts.append("框架: " + ", ".join(ts["frameworks"]))
                if ts.get("key_dependencies"):
                    parts.append("依赖: " + ", ".join(ts["key_dependencies"]))
                project_profile["tech_stack"] = "; ".join(parts) if parts else "未知"
```

- [ ] **Step 2: Run tests**

Run: `cd /home/easy/projects/ReqRadar && python -m pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/reqradar/core/report.py
git commit -m "fix: eliminate None in report narrative fields and format tech_stack"
```

---

## Task 13: 更新配置文件示例

**Files:**
- Modify: `.reqradar.yaml`

- [ ] **Step 1: 在配置文件中增加tool_use相关配置**

在 `.reqradar.yaml` 的 `analysis:` 节下增加：

```yaml
analysis:
  max_similar_reqs: 5
  max_code_files: 10
  contributors_lookback_months: 6
  tool_use_enabled: true
  tool_use_max_rounds: 15
  tool_use_max_tokens: 8000
```

- [ ] **Step 2: Commit**

```bash
git add .reqradar.yaml
git commit -m "chore: add tool_use config options to .reqradar.yaml"
```

---

## Task 14: 端到端验证

**Files:** 无新增

- [ ] **Step 1: 设置API Key并运行index**

```bash
export OPENAI_API_KEY=<your-key>
cd /home/easy/projects/ReqRadar && reqradar index -r ./src -d ./docs/requirements -o .reqradar/index
```

Expected: 索引构建成功，项目画像已构建

- [ ] **Step 2: 运行analyze并观察工具调用日志**

```bash
reqradar analyze docs/requirements/web-module.md -i .reqradar/index -o reports -v
```

Expected: 
- 日志中可见 `Tool call #N: search_code(...)` 等工具调用记录
- 日志中可见 `Tool usage summary` 包含调用计数和token消耗
- 报告中 `2.3 影响范围描述`、`3.2 风险分析描述`、`5.2 实施方向` 不再显示 `None`
- 报告附录中技术栈显示格式化字符串而非dict

- [ ] **Step 3: 清除API Key**

```bash
unset OPENAI_API_KEY
```

- [ ] **Step 4: 验证降级模式（不设API Key时仍可运行）**

```bash
reqradar analyze docs/requirements/web-module.md -i .reqradar/index -o reports
```

Expected: 降级模式运行，不使用工具调用，报告生成成功（质量较低但不崩溃）

- [ ] **Step 5: 更新DESIGN.md**

在 `DESIGN.md` 的 Phase 5 部分标记已完成项，在 "LLM 调用点" 部分更新为 Tool-Use 架构说明。

- [ ] **Step 6: 最终提交**

```bash
git add DESIGN.md
git commit -m "docs: update DESIGN.md with tool-use agent architecture"
```

---

## Self-Review

### Spec Coverage Check

| 设计文档要求 | 对应Task |
|:---|:---|
| Tool基类和ToolResult | Task 1 |
| ToolRegistry | Task 2 |
| ToolCallTracker（去重/计数/token监控） | Task 3 |
| LLM complete_with_tools() | Task 4 |
| 9个Tool实现 | Task 5 |
| ToolUseLoop核心循环 | Task 6 |
| 配置项（可配置max_rounds/max_tokens/enabled） | Task 7 |
| DeepAnalysis增加impact_narrative/risk_narrative | Task 8 |
| step_analyze改造 | Task 9 |
| 其他步骤改造 | Task 10 |
| CLI集成ToolRegistry | Task 11 |
| 报告渲染修复（None/tech_stack） | Task 12 |
| 配置文件更新 | Task 13 |
| 端到端验证 | Task 14 |

### Placeholder Scan
No TBD/TODO found. All steps contain complete code.

### Type Consistency Check
- `ToolResult(success, data, error, truncated)` — consistent across all tools and tests
- `BaseTool.name`, `BaseTool.parameters_schema` — consistent across all 9 tools
- `ToolRegistry.get(name) -> BaseTool | None` — consistent with usage in tool_use_loop
- `ToolCallTracker(max_rounds, max_total_tokens)` — consistent between config and instantiation
- `AnalysisConfig.tool_use_max_rounds/tool_use_max_tokens/tool_use_enabled` — consistent in config.py, .reqradar.yaml, and steps.py
- `DeepAnalysis.impact_narrative/risk_narrative` — consistent in context.py, schemas.py, steps.py, report.py
