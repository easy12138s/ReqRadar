# ReqRadar 架构设计

## 概述

ReqRadar 是一个固定流程的垂直领域 Agent，专注于需求分析。核心理念：

- **流程固定**：6步工作流不变，确保分析结果可预测
- **模板固定**：报告结构固定，LLM 仅填充内容
- **记忆积累**：每次分析后自动积累术语、约束、历史发现

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Layer                               │
│  reqradar index | reqradar analyze                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Scheduler (6-Step)                        │
│  read → extract → map_keywords → retrieve → analyze → generate  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  Code Parser  │     │ Vector Store  │     │  Git Analyzer │
│   (AST/AST)   │     │   (Chroma)    │     │   (GitPython) │
└───────────────┘     └───────────────┘     └───────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │  LLM Client   │
                    │ (OpenAI/MiniMax/Ollama)  │
                    └───────────────┘
```

## 核心组件

### 1. Scheduler（调度器）

`src/reqradar/core/scheduler.py`

固定6步工作流：

| 步骤 | 名称 | 输入 | 输出 |
|:---|:---|:---|:---|
| 1 | read | 需求文件路径 | 原始文本 |
| 2 | extract | 原始文本 + 记忆术语 | 术语、约束、摘要 |
| 3 | map_keywords | 术语列表 | 扩展关键词（中文→英文代码词） |
| 4 | retrieve | 关键词 | 相似需求、代码模块 |
| 5 | analyze | 代码模块 + 贡献者 | 风险、变更评估、验证要点 |
| 6 | generate | 分析结果 | 报告段落 |

### 2. Context（上下文）

`src/reqradar/core/context.py`

数据模型定义：

```python
@dataclass
class AnalysisContext:
    requirement_path: Path
    requirement_text: str
    memory_data: dict
    understanding: RequirementUnderstanding
    retrieved_context: RetrievedContext
    deep_analysis: DeepAnalysis
    generated_content: GeneratedContent
    expanded_keywords: list[str]
    step_results: dict[str, StepResult]
```

关键数据结构：

- `TermDefinition`: term, definition, domain
- `StructuredConstraint`: description, constraint_type, source
- `RiskItem`: description, severity, scope, mitigation
- `ChangeAssessment`: module, change_type, impact_level, reason
- `ImplementationHints`: approach, effort_estimate, dependencies

### 3. Memory（记忆系统）

`src/reqradar/modules/memory.py`

存储结构：

```yaml
project_profile:
  name: ReqRadar
  description: 需求分析工具
  tech_stack:
    languages: [Python]
    frameworks: [Click, Pydantic, ChromaDB]
  architecture_style: 分层架构

modules:
  - name: agent/steps
    responsibility: 6步工作流实现
    key_classes: [step_extract, step_analyze]

terminology:
  - term: API
    definition: Application Programming Interface
    domain: 技术基础

constraints:
  - description: API响应时间<200ms
    constraint_type: performance
    source: requirement_document

analysis_history:
  - requirement_id: user-auth
    findings: [...]
    outcome: 已通过评审
```

### 4. Report Renderer（报告渲染）

`src/reqradar/core/report.py` + `templates/report.md.j2`

报告结构：

1. **报告概况** - 风险徽章（🔴🟠🟡🟢⚪）、影响范围、优先级
2. **需求理解** - 术语表、约束表
3. **影响分析** - 代码影响、变更评估、相似需求
4. **风险评估** - 风险表、验证要点
5. **建议评审人** - 贡献者列表
6. **实施建议** - 优先级、工作量、依赖
7. **附录** - 数据完整性、项目知识

## LLM 调用策略

### Function Calling 优先

```python
async def _call_llm_structured(llm_client, messages, schema, **kwargs):
    # 1. 尝试 function calling
    structured = await llm_client.complete_structured(messages, schema)
    if structured:
        return structured
    
    # 2. 降级到文本解析
    response = await llm_client.complete(messages)
    return _parse_json_response(response)
```

### JSON 解析降级

```python
def _parse_json_response(response):
    # 处理 markdown 代码块
    if response.startswith("```"):
        response = extract_from_code_block(response)
    
    # 提取 JSON 对象或数组
    if "{" in response:
        return extract_json_object(response)
    if "[" in response:
        return extract_json_array(response)
```

## 关键词映射

`src/reqradar/agent/steps.py` - `step_map_keywords`

将中文业务术语映射为英文代码搜索词：

```
"双因素认证" → ["two_factor", "2fa", "mfa", "auth", "totp"]
"用户登录" → ["login", "signin", "auth", "user_auth"]
"IDE集成" → ["extension", "plugin", "vscode", "ide"]
```

流程：
1. 从 `understanding.terms` 获取术语列表
2. 调用 LLM 使用 `KEYWORD_MAPPING_SCHEMA` 映射
3. 合并原始术语和映射结果到 `context.expanded_keywords`
4. 在 `step_retrieve` 中使用扩展关键词搜索代码

## 项目画像构建

`src/reqradar/agent/steps.py` - `step_build_project_profile`

在 `reqradar index` 时自动构建：

1. 解析代码结构（文件、类、函数）
2. 提取依赖信息（pyproject.toml、requirements.txt）
3. 调用 LLM 总结：
   - 项目描述
   - 架构风格
   - 技术栈
   - 模块划分

## 测试策略

| 测试文件 | 覆盖内容 |
|:---|:---|
| `test_memory.py` | 记忆系统 CRUD |
| `test_project_profile.py` | 项目画像构建 |
| `test_keyword_mapping.py` | 关键词映射 |
| `test_report.py` | 报告渲染 |
| `test_steps_structured.py` | JSON 解析 |

当前测试数量：**154 个**

## 扩展点

### 添加新的文档加载器

1. 继承 `BaseLoader`
2. 实现 `supports(path)` 和 `load(path)`
3. 在 `LoaderRegistry` 注册

### 添加新的 LLM 后端

1. 继承 `LLMClient`
2. 实现 `complete()`, `complete_structured()`, `embed()`
3. 在 `create_llm_client()` 添加分支

### 添加新的分析步骤

1. 在 `steps.py` 定义 schema 和步骤函数
2. 在 `Scheduler.STEPS` 添加步骤
3. 在 CLI 传入 handler

## 已知限制

1. **MiniMax function calling 不稳定**：复杂 prompt 可能返回空 tool_calls
2. **代码匹配依赖文件名**：语义匹配需要显式映射
3. **记忆文件膨胀**：多次分析后 memory.yaml 可能变大

## 未来规划

- [ ] 支持 OpenAI GPT-4 获得更稳定的 function calling
- [ ] 添加 `reqradar config` 命令管理配置
- [ ] 支持 GitHub/GitLab 集成获取贡献者信息
- [ ] 添加 Web UI 预览报告
