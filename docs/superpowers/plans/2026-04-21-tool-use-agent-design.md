# Tool-Use Agent 重构设计

> 将 ReqRadar 的核心分析流程从"被动喂数据的6步流水线"重构为"LLM主动获取信息的工具调用架构"，在保留6步流程框架的前提下，让每步内的LLM能通过工具调用按需获取项目信息。

---

## 一、问题诊断

### 1.1 当前架构的核心缺陷

| 缺陷 | 表现 | 根因 |
|:---|:---|:---|
| LLM看不到代码 | 分析结果空洞，报告出现None | prompt只塞入模块名+符号名，无实际代码 |
| 信息逐步压缩 | extract只取4000字→keywords只有5-10个词→analyze只看摘要 | 管道式单向数据流，每步裁剪信息 |
| LLM无法追问 | 发现可疑模块但无法查看实现 | 无工具机制，LLM只能接受预设输入 |
| 步骤间强耦合 | extract失败→全链崩溃 | 下一步完全依赖上一步输出 |
| 代码索引是死数据 | CodeGraph只支持find_symbols子串匹配 | LLM无法查询索引 |

### 1.2 测试实证

使用MiniMax-M2.5对web-module需求的测试中：
- 报告2.3/3.2/5.2出现`None`——LLM未生成叙述段落
- 核心术语显示"暂无术语定义数据"——信息未正确传递
- 术语提取质量差——LLM只看到需求文本，没有代码上下文辅助理解
- 变更评估正确但泛泛——LLM只能猜，无法验证

---

## 二、设计目标

1. **LLM按需获取信息**：根据需求特点自主决定查询深度和广度
2. **保留6步流程框架**：不打破现有的可预期性和可调试性
3. **现有能力模块零改造**：CodeParser、VectorStore、GitAnalyzer、MemoryManager只需封装为Tool
4. **成本可控**：通过轮次上限和token预算限制LLM调用
5. **降级仍可用**：工具调用失败时，步骤仍可降级执行

---

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│ 调度层 (6-Step Pipeline)                                    │
│  read → extract → map_keywords → retrieve → analyze → generate│
│           ↓           ↓           ↓          ↓         ↓   │
│    ┌──────────────────────────────────────────────────┐     │
│    │          Tool Registry (工具注册表)                │     │
│    │  search_code | read_file | read_module_summary    │     │
│    │  search_requirements | get_dependencies          │     │
│    │  get_contributors | get_project_profile          │     │
│    │  get_terminology | list_modules                  │     │
│    └──────────────────────────────────────────────────┘     │
│           ↓ tool calls                                      │
│    ┌──────────────────────────────────────────────────┐     │
│    │          Capability Layer (能力层，不改造)          │     │
│    │  CodeParser | VectorStore | GitAnalyzer           │     │
│    │  MemoryManager | LLMClient                        │     │
│    └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心变化

**Before**（当前）：
```
step_extract: 直接把需求文本塞进prompt → LLM提取术语
step_analyze: 直接把模块名+符号名塞进prompt → LLM评估风险
```

**After**（重构后）：
```
step_extract: 把需求文本+工具定义塞进prompt
  → LLM提取术语
  → LLM觉得需要了解项目，调用 get_project_profile()
  → LLM发现"认证"概念，调用 search_code("auth")
  → LLM看到AuthService类，调用 read_file("src/auth/service.py")
  → LLM基于代码上下文，输出更精确的术语定义

step_analyze: 把需求理解+工具定义塞进prompt
  → LLM调用 list_modules() 了解项目结构
  → LLM调用 read_module_summary("agent") 了解模块职责
  → LLM调用 read_file("src/reqradar/agent/steps.py") 查看具体实现
  → LLM调用 get_dependencies("agent") 查看上下游
  → LLM调用 get_contributors("agent/steps.py") 找维护者
  → LLM基于实际代码，输出精准的变更评估和风险分析
```

---

## 四、Tool 接口定义

### 4.1 Tool 基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool
    data: str  # 文本结果，直接可放入LLM上下文
    error: str = ""
    truncated: bool = False  # 结果是否被截断

class BaseTool(ABC):
    name: str
    description: str  # 供LLM理解工具用途
    parameters_schema: dict  # JSON Schema，供function calling

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...
```

### 4.2 工具清单

| 工具名 | 功能 | 参数 | 数据源 | 返回 |
|:---|:---|:---|:---|:---|
| `search_code` | 搜索代码符号 | `keyword: str`, `type?: str` (class/function/all) | CodeGraph | 匹配的符号列表+文件路径 |
| `read_file` | 读取文件内容 | `path: str`, `start_line?: int`, `end_line?: int` | 代码仓库 | 文件内容文本（最大2000行） |
| `read_module_summary` | 获取模块摘要 | `module_name: str` | Memory | 模块职责+代码摘要+核心类 |
| `list_modules` | 列出所有模块 | 无 | Memory | 模块名+职责列表 |
| `search_requirements` | 语义搜索历史需求 | `query: str`, `top_k?: int` | VectorStore | 相似需求列表+内容摘要 |
| `get_dependencies` | 查询模块依赖 | `module: str` | CodeGraph | 上下游模块列表 |
| `get_contributors` | 查询文件贡献者 | `file_path: str` | GitAnalyzer | 主要贡献者+修改频率 |
| `get_project_profile` | 获取项目画像 | 无 | Memory | 项目描述+技术栈+架构风格 |
| `get_terminology` | 获取已知术语 | 无 | Memory | 术语列表+定义 |

### 4.3 Function Calling Schema 示例

```python
SEARCH_CODE_SCHEMA = {
    "name": "search_code",
    "description": "在项目代码中搜索包含指定关键词的类、函数或变量",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词（英文，如 auth、scheduler、memory）"
            },
            "symbol_type": {
                "type": "string",
                "enum": ["class", "function", "all"],
                "description": "要搜索的符号类型，默认 all"
            }
        },
        "required": ["keyword"]
    }
}

READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "读取项目中指定文件的源代码内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径（相对于项目根目录，如 src/reqradar/agent/steps.py）"
            },
            "start_line": {
                "type": "integer",
                "description": "起始行号（从1开始），不指定则从文件开头"
            },
            "end_line": {
                "type": "integer",
                "description": "结束行号，不指定则到文件末尾（最多2000行）"
            }
        },
        "required": ["path"]
    }
}
```

---

## 五、Tool-Use 循环机制

### 5.1 核心循环

每个需要LLM参与的步骤（extract/map_keywords/retrieve/analyze/generate），内部运行一个"LLM+工具"循环：

```python
async def run_tool_use_loop(
    llm_client,
    system_prompt: str,
    user_prompt: str,
    tools: list[BaseTool],
    output_schema: dict,        # 步骤的最终输出schema
    max_rounds: int = 15,       # 最大工具调用轮次
    max_total_tokens: int = 8000 # 工具结果的总token预算
) -> dict:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    tool_schemas = [tool.parameters_schema for tool in tools]
    tool_map = {tool.name: tool for tool in tools}
    total_tool_tokens = 0

    for round in range(max_rounds):
        # LLM生成回复（可能包含tool_calls或最终输出）
        response = await llm_client.complete_with_tools(
            messages=messages,
            tools=tool_schemas,
        )

        if response.has_tool_calls:
            # LLM请求调用工具
            messages.append(response.assistant_message)
            for tool_call in response.tool_calls:
                tool = tool_map[tool_call.name]
                result = await tool.execute(**tool_call.arguments)
                # 检查token预算
                result_tokens = estimate_tokens(result.data)
                if total_tool_tokens + result_tokens > max_total_tokens:
                    result = ToolResult(
                        success=False,
                        data="",
                        error="Token budget exceeded"
                    )
                else:
                    total_tool_tokens += result_tokens
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.data if result.success else f"Error: {result.error}"
                })
        elif response.has_structured_output:
            # LLM输出了结构化结果（通过function calling的最终schema）
            return response.structured_output
        else:
            # 纯文本回复，尝试解析为JSON
            return parse_json_response(response.text)

    # 轮次耗尽，强制要求LLM输出最终结果
    messages.append({"role": "user", "content": "请基于已获取的信息，输出最终分析结果。"})
    final = await llm_client.complete_structured(messages, output_schema)
    return final
```

### 5.2 各步骤的工具权限

不同步骤暴露不同的工具子集，避免LLM在不需要的步骤中浪费调用：

| 步骤 | 可用工具 | 典型调用场景 |
|:---|:---|:---|
| step_extract | `get_project_profile`, `get_terminology`, `search_code`, `read_file` | 理解需求时查项目背景、验证术语是否存在于代码中 |
| step_map_keywords | `search_code`, `read_module_summary` | 将业务术语映射到代码层时，验证映射是否准确 |
| step_retrieve | `search_requirements`, `get_terminology` | 检索历史需求时，根据术语精确查询 |
| step_analyze | **全部工具** | 深度分析，需要全面了解代码、依赖、贡献者 |
| step_generate | `get_project_profile` | 生成叙述段落时引用项目上下文 |

### 5.3 降级策略

| 场景 | 降级行为 |
|:---|:---|
| LLM不调用任何工具 | 等同当前行为，基于prompt内容直接输出 |
| 工具调用失败 | 返回错误信息给LLM，LLM可换用其他工具或基于已有信息输出 |
| 达到轮次上限 | 强制LLM基于已获取信息输出最终结果 |
| 达到token预算 | 拒绝后续工具调用，强制输出 |
| LLM客户端不支持function calling | 回退到当前模式（不使用工具） |

---

## 六、详细步骤设计

### 6.1 step_extract（提取关键术语和结构化信息）

**当前**：只看需求文档前4000字
**改造后**：

```
输入给LLM：
  - 需求文档全文（不截断）
  - 可用工具：get_project_profile, get_terminology, search_code, read_file
  - 输出schema：同现有 EXTRACT_SCHEMA

LLM可能的行为：
  1. 阅读需求文档
  2. 调用 get_project_profile() 了解项目背景
  3. 调用 get_terminology() 获取已有术语定义
  4. 遇到"WebSocket"等术语 → 调用 search_code("websocket") 验证项目中是否已有相关实现
  5. 如果找到相关代码 → 调用 read_file() 查看实现细节
  6. 基于代码上下文，输出更精确的术语定义（如"WebSocket"→项目中的具体实现类和方法）

输出：
  - summary: 基于项目上下文的需求摘要
  - terms: 带定义的术语列表（定义来自代码验证，而非猜测）
  - keywords: 精确的搜索关键词（已验证存在于代码库中）
  - structured_constraints: 约束条件
```

### 6.2 step_map_keywords（映射关键词到代码术语）

**当前**：纯翻译，不理解项目实际结构
**改造后**：

```
输入给LLM：
  - 需求理解结果（summary, terms, keywords）
  - 可用工具：search_code, read_module_summary
  - 输出schema：同现有 KEYWORD_MAPPING_SCHEMA

LLM可能的行为：
  1. 对每个业务术语，调用 search_code() 验证映射是否正确
  2. 例如"项目记忆"→ search_code("memory") → 找到MemoryStore类
  3. 调用 read_module_summary("modules/memory") 了解模块职责
  4. 输出基于实际代码的映射，而非纯翻译

输出：同现有，但映射质量大幅提升
```

### 6.3 step_retrieve（检索相似需求与代码）

**当前**：用关键词拼接做向量搜索
**改造后**：

```
输入给LLM：
  - 需求理解结果
  - 可用工具：search_requirements, get_terminology
  - 输出schema：同现有 RETRIEVE_SCHEMA

LLM可能的行为：
  1. 基于需求理解，构造更精确的语义搜索query
  2. 调用 search_requirements() 多次，用不同角度查询
  3. 对检索结果进行相关性评估

输出：同现有，但检索质量和评估精度提升
```

### 6.4 step_analyze（深度分析）—— 改造重点

**当前**：只拿到模块名+符号名，看不到代码
**改造后**：

```
输入给LLM：
  - 需求理解 + 相似需求 + 项目画像
  - 可用工具：全部9个工具
  - 输出schema：同现有 ANALYZE_SCHEMA + 新增 impact_narrative, risk_narrative
  - max_rounds: 15（最复杂的步骤，给更多轮次）

LLM可能的行为：
  1. 调用 list_modules() 了解项目所有模块
  2. 对可能受影响的模块，逐一调用 read_module_summary() 了解职责
  3. 对关键模块调用 read_file() 查看具体实现
  4. 调用 get_dependencies() 查看模块间依赖
  5. 调用 get_contributors() 找到维护者
  6. 调用 search_requirements() 查找相似历史需求
  7. 基于实际代码上下文，输出：
     - 精准的变更评估（知道哪些类/方法需要修改）
     - 深入的风险分析（基于代码中的硬编码依赖、耦合点）
     - 具体的验证要点（基于代码中的边界条件、错误处理）
     - impact_narrative 和 risk_narrative（解决当前None问题）
```

### 6.5 step_generate（生成报告段落）

**当前**：只拿到之前步骤的摘要
**改造后**：

```
输入给LLM：
  - 所有前序步骤的结构化输出
  - 可用工具：get_project_profile
  - 输出schema：同现有 GENERATE_SCHEMA，但增加字段确保不为None

LLM可能的行为：
  1. 引用项目画像中的信息
  2. 基于前序步骤已充分分析的上下文，生成叙述段落
  3. 输出完整的 requirement_understanding, impact_narrative, risk_narrative, implementation_suggestion
```

---

## 七、数据流变化

### 7.1 当前数据流

```
需求文档 ──read──→ requirement_text
                      │
                   extract(仅看文本)
                      │
                 understanding.keywords  ──→  map_keywords(纯翻译)
                      │                            │
                      └──────→ retrieve(向量搜索) ←─┘
                                                   │
                                            analyze(看模块名)
                                                   │
                                            generate(看摘要)
                                                   │
                                                报告
```

信息逐步压缩，到analyze时LLM只能"猜"。

### 7.2 重构后数据流

```
需求文档 ──read──→ requirement_text
                      │
                   extract ──→ 可调用 get_project_profile / search_code / read_file
                      │
                 understanding
                      │
                map_keywords ──→ 可调用 search_code / read_module_summary
                      │
                 expanded_keywords
                      │
                   retrieve ──→ 可调用 search_requirements
                      │
                 retrieved_context
                      │
                   analyze ──→ 可调用全部工具，查看实际代码
                      │
                 deep_analysis (含 impact_narrative, risk_narrative)
                      │
                   generate ──→ 可调用 get_project_profile
                      │
                   报告
```

关键变化：每个步骤都能**回溯原始数据**，不依赖上一步的压缩结果。

---

## 八、实现计划

### 8.1 新增文件

```
src/reqradar/agent/
├── tools/                    # 新增目录
│   ├── __init__.py
│   ├── base.py              # BaseTool + ToolResult
│   ├── registry.py          # ToolRegistry（注册+查找+schema聚合）
│   ├── search_code.py       # search_code 工具实现
│   ├── read_file.py         # read_file 工具实现
│   ├── read_module_summary.py
│   ├── list_modules.py
│   ├── search_requirements.py
│   ├── get_dependencies.py
│   ├── get_contributors.py
│   ├── get_project_profile.py
│   └── get_terminology.py
├── tool_use_loop.py         # 新增：LLM+工具循环核心逻辑
└── steps.py                 # 修改：每步改用 tool_use_loop
```

### 8.2 需要修改的文件

| 文件 | 改动 |
|:---|:---|
| `steps.py` | 每个LLM步骤改为调用 `run_tool_use_loop()`，删除手动拼接prompt的逻辑 |
| `prompts.py` | 重写每个步骤的system prompt，加入"你可以使用以下工具"的指引 |
| `schemas.py` | 合并工具schema和输出schema；步骤输出schema增加缺失字段 |
| `llm_utils.py` | 增加 `complete_with_tools()` 方法（支持tool_calls的LLM调用） |
| `modules/llm_client.py` | 增加 `complete_with_tools()` 接口（OpenAI tool_use协议） |
| `core/context.py` | `DeepAnalysis` 增加 `impact_narrative`, `risk_narrative` 字段 |
| `core/report.py` | 修复 `None` 显示问题，格式化 tech_stack |

### 8.3 不需要改动的文件

| 文件 | 原因 |
|:---|:---|
| `modules/code_parser.py` | 只需封装为 Tool，不改实现 |
| `modules/vector_store.py` | 只需封装为 Tool，不改实现 |
| `modules/git_analyzer.py` | 只需封装为 Tool，不改实现 |
| `modules/memory.py` | 只需封装为 Tool，不改实现 |
| `core/scheduler.py` | 6步流程不变 |
| `cli/main.py` | 调度器接口不变，CLI无需改动 |
| `templates/report.md.j2` | 修复显示bug，模板结构不变 |

### 8.4 实现步骤（建议顺序）

1. **P0: Tool基础设施** — BaseTool、ToolResult、ToolRegistry
2. **P0: LLM客户端扩展** — `complete_with_tools()` 方法
3. **P0: tool_use_loop核心** — 循环逻辑、轮次控制、token预算
4. **P1: 9个Tool实现** — 封装现有能力模块
5. **P1: step_analyze改造** — 最重要的步骤，先改造验证效果
6. **P2: step_extract改造** — 提升术语和关键词质量
7. **P2: 其他步骤改造** — map_keywords, retrieve, generate
8. **P3: 报告渲染修复** — 修复None显示、tech_stack格式化
9. **P3: 测试更新** — 单元测试+集成测试

---

## 九、风险和约束

| 风险 | 缓解措施 |
|:---|:---|
| LLM调用轮次过多导致成本失控 | max_rounds=15, max_total_tokens=8000, 逐步收紧 |
| 不支持function calling的LLM（如Ollama部分模型） | 降级到当前模式（无工具调用） |
| read_file返回内容过长导致prompt溢出 | 限制2000行，token预算机制 |
| LLM"滥用"工具（反复查询同一内容） | 轮次计数+去重（同一工具+相同参数只执行一次） |
| 工具实现有bug导致返回错误 | ToolResult.error返回给LLM，LLM可换用其他工具 |

---

## 十、预期效果

| 指标 | 当前 | 重构后预期 |
|:---|:---|:---|
| 报告2.3/3.2/5.2 None问题 | 总是出现 | 消除（LLM有足够信息生成叙述） |
| 术语提取质量 | 常见词混入，定义空 | 基于代码验证，定义准确 |
| 变更评估深度 | "可能需要修改"泛泛而谈 | "需要在X类的Y方法中新增Z参数" |
| 风险分析精度 | 基于猜测 | 基于代码中的耦合和依赖 |
| 单次LLM调用次数 | 5-6次固定 | 8-15次（但每次更精准） |
| 单次分析token消耗 | ~5-8K | ~15-25K（成本约$0.03-0.05） |

---

*最后更新：2026-04-21*
