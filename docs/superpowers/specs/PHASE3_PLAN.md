# ReqRadar Phase 3 规划文档

> **版本**：v1.0  
> **日期**：2026-04-15  
> **状态**：规划中，尚未实施  
> **目标**：让 ReqRadar 从"玩具级原型"迈向"企业团队可用工具"

---

## 一、背景与问题分析

### 1.1 当前项目完成度概览

| 模块 | 状态 | 完成度 |
|:---|:---|:---|
| 5步固定流程调度 | ✅ 完成 | 100% |
| 配置系统（LLM/Vision/Memory/Loader） | ✅ 完成 | 100% |
| 文档加载器（MD/TXT/PDF/DOCX/Image/Chat） | ✅ 完成 | 100% |
| LLM Function Calling + 三层降级 | ✅ 完成 | 100% |
| 项目记忆系统（术语/团队/历史） | ✅ 基础版 | 40% |
| 报告生成 | ✅ 基础版 | 30% |
| 代码影响分析 | ⚠️ 仅 Python 字面匹配 | 30% |
| 风险评估 | ⚠️ 条件太苛刻常跳过 | 20% |
| 记忆注入全流程 | ⚠️ 仅 extract 步骤 | 20% |

### 1.2 核心问题诊断

通过 MiniMax-M2.5 真实 API 端到端测试，产出报告中有以下结构性问题：

#### 问题一：记忆极度匮乏

当前 `memory.yaml` 产出示例：

```yaml
terminology:
- term: IDE集成
  definition: ''           # ← 空的！没有语义定义
  context: 自动提取         # ← 没有实际业务含义
- term: OAuth2.0
  definition: ''           # ← 技术术语也没定义
```

**根因拆解**：

| 层次 | 问题 | 根因 |
|:---|:---|:---|
| 存储层 | 只有 term/definition/context 三字段 | 数据模型扁平，表达力不足 |
| 采集层 | 术语只从 keywords 提取，定义永远是空的 | EXTRACT_SCHEMA 没有要求定义，`update_from_analysis` 只存 term |
| 索引层 | `reqradar index` 构建了 code_graph.json 但从未被记忆消费 | 代码图谱在内存之外，每次分析都是"第一次见这个项目" |
| 注入层 | 术语只用简单列表注入 extract prompt | 没有架构上下文、没有模块归属、没有团队知识 |
| 更新层 | 记忆只在 analyze 结束后被动写入 | `index` 时零记忆更新，错失了最大知识来源 |

**核心矛盾**：`reqradar index` 是整个工具最深入理解项目结构的时刻——它扫描了全部代码、构建了类/函数图谱、分析了 Git 历史——但这个理解完全没有沉淀到记忆里。下一次 `analyze` 时，LLM 对"这个项目长什么样"一无所知。

#### 问题二：报告空洞，核心价值缺失

实际产出的报告：

```markdown
## 三、技术影响分析
暂无代码影响分析数据

## 四、建议评审人
*未找到相关评审人信息*

## 五、风险评估
**总体风险等级**：unknown

## 六、自然语言描述
针对登录流程安全隐患，优化认证功能...（100字复述）
```

**逐节问题**：

| 章节 | 问题 | 根因 |
|:---|:---|:---|
| 需求摘要 | 只是需求文档的复述，没有提炼 | LLM 被限制在 100 字 summarize，等于什么都没说 |
| 关键词 | 裸术语列表，没有业务含义 | keywords 是扁平列表，缺少领域归属 |
| 约束条件 | 照抄原文 | LLM 只提取了字面约束，没识别隐含约束 |
| 相似历史需求 | 自己匹配自己、没有历史结论 | 向量索引缺少 outcome 元数据 |
| 技术影响分析 | 永远"暂无" | 代码匹配链路断裂：Python AST + 字面子串匹配 + 中英文不对应 |
| 建议评审人 | 永远"未找到" | 同上 |
| 风险评估 | 永远 unknown | `step_analyze` 的 LLM 调用条件 `if llm_client and impact_modules` 太苛刻 |
| 自然语言描述 | 又是需求复述 | 100 字限制，和摘要重复 |
| 数据完整性 | 声称 100% 但核心章节全空 | 置信度衡量的是"步骤是否执行"而非"内容是否有价值" |

**最致命的矛盾**：报告声称"数据完整度 full、置信度 100%"，但核心章节全是空数据和 unknown。

#### 问题三：代码匹配能力薄弱

```python
# 当前 code_parser.py 的 find_symbols 实现
def find_symbols(self, keywords: list[str]) -> list[CodeFile]:
    for kw in keywords:
        if kw.lower() in f.path.lower():     # 路径包含关键词
            results.append(f)
        for sym in f.symbols:
            if kw.lower() in sym.name.lower(): # 函数/类名包含关键词
                results.append(f)
```

"IDE集成"匹配不到 `vscode_extension.py`，"双因素认证"匹配不到 `two_factor_auth.py`，"OAuth2.0"匹配不到 `oauth_provider.py`。**纯粹的字面子串匹配 = 在企业级代码库中几乎等于盲人摸象。**

#### 问题四：LLM 被浪费在低阶任务上

当前 LLM 的使用方式：

- `step_extract`：提取关键词 → 应该建立"需求→业务领域"的深层理解
- `step_analyze`：条件太苛刻，经常跳过 → 应该始终做风险评估
- `step_generate`：填充 100 字短段落 → 应该做综合推理叙述

LLM 最强的能力是**语义理解**，而现在它被当作"JSON 提取器"使用。

---

### 1.3 竞品与市场定位

没有与 ReqRadar 完全对标的产品。最接近的：

| 竞品类型 | 代表 | 做了什么 | ReqRadar 差异 |
|:---|:---|:---|:---|
| AI 代码助手 | GitHub Copilot, Cursor | 代码补全/生成 | ReqRadar 不生成代码，做需求→代码影响映射 |
| AI Code Review | CodeRabbit, Sweep | PR 自动审查 | 审查代码变更，不是需求文档 |
| 需求管理 | Jira + Atlassian Intelligence | 需求追踪+AI摘要 | 没有代码影响分析、没有历史需求检索 |
| 知识管理 | Notion AI, Confluence AI | 文档编写辅助 | 没有代码仓库连接、没有贡献者映射 |

**ReqRadar 的核心差异化定位**：需求评审时自动关联代码影响面和贡献者。这不仅是"更好的 AI 聊天工具"，而是一个垂直场景的结构化信息聚合器。这个定位在市场上是空白的。

---

## 二、Phase 3 总体目标

**一句话**：让 ReqRadar 从"每次分析都像第一次见这个项目"变成"我对这个项目已经了解了"；让报告从"一堆暂无和 unknown"变成"每个章节都有实质内容"。

**具体可衡量的目标**：

1. **记忆系统**：`reqradar index` 后，memory.yaml 包含完整的项目画像（架构、技术栈、模块职责、团队）；术语每个都有定义；analyze 后记忆增量更新
2. **报告质量**：不存在"暂无"和"unknown"的章节；风险评估永远有值；影响分析即使没有代码匹配也有 LLM 推断
3. **代码匹配**：语义关键词桥接（"认证"→["auth", "login", "session"]），不再纯字面匹配
4. **LLM 利用率**：每次 analyze 至少 4 次 LLM 调用（extract/analyze/generate + index 知识总结）

---

## 三、详细设计

### 3.1 记忆系统重构

#### 3.1.1 新的记忆数据结构

```yaml
# .reqradar/memory/memory.yaml

# ====== 项目画像（index 时构建，analyze 时精化）======
project_profile:
  name: "ReqRadar"
  description: "固定流程的需求分析垂直 Agent"
  tech_stack:
    languages: ["Python"]
    frameworks: ["Click", "Pydantic", "ChromaDB", "Jinja2"]
    key_dependencies: ["httpx", "sentence-transformers", "gitpython", "pyyaml"]
  architecture_style: "分层架构 - CLI/调度/能力/基础设施"
  source: "llm_inferred"        # llm_inferred / human_curated
  last_updated: "2026-04-15"

# ====== 模块知识（index 时构建）======
modules:
  - name: "agent/steps"
    responsibility: "5步工作流实现（读取→提取→检索→分析→生成）"
    key_classes: ["step_read", "step_extract", "step_retrieve", "step_analyze", "step_generate"]
    dependencies: ["core/context", "modules/llm_client", "modules/vector_store"]
    path: "src/reqradar/agent/steps.py"
    owner: null                    # 从 git 历史推断

  - name: "modules/llm_client"
    responsibility: "LLM 抽象层，支持 OpenAI/Ollama 双后端和 function calling"
    key_classes: ["LLMClient", "OpenAIClient", "OllamaClient"]
    dependencies: ["core/exceptions"]
    path: "src/reqradar/modules/llm_client.py"
    owner: null

# ====== 术语表（带语义定义和模块关联）======
terminology:
  - term: "SSO"
    definition: "Single Sign-On，统一身份认证机制"
    domain: "认证模块"
    related_modules: ["src/auth/"]
    source: "llm_extract"          # llm_extract / human_curated / index_inferred

  - term: "OAuth2.0"
    definition: "开放授权协议 2.0，用于第三方登录授权"
    domain: "认证模块"
    related_modules: ["src/auth/"]
    source: "llm_extract"

# ====== 团队知识（从 git 分析推断）======
team:
  - name: "张三"
    role: "后端负责人"            # 从 git commit 推断或人工标注
    modules: ["src/auth/", "src/user/"]
    source: "git_analyzer"

# ====== 架构约束（LLM 从需求文档提取 + 人工可补充）======
constraints:
  - description: "外部 API 契约不可变更"
    constraint_type: "api_contract"
    modules: ["src/api/"]
    source: "requirement_extraction"

  - description: "认证流程响应时间须 < 200ms"
    constraint_type: "performance"
    modules: ["src/auth/"]
    source: "requirement_extraction"

# ====== 分析历史（结构化记录）======
analysis_history:
  - date: "2026-04-15"
    requirement: "ide-integration"
    summary: "IDE集成需求，涉及 VS Code 扩展和 PyCharm 插件开发"
    risk_level: "medium"           # 不再是 unknown
    affected_modules: ["cli/", "agent/"]
    key_decisions: ["选择 VS Code Extension API 而非 Language Server"]
```

#### 3.1.2 数据模型变更

当前 `MemoryManager` 只有三个扁平列表（terminology/team/analysis_history），需要扩展为上述结构。

**新增字段对比**：

| 数据块 | 当前 | 新增 |
|:---|:---|:---|
| terminology | term, definition, context | + domain, related_modules, source |
| team | name, role, modules | + source |
| analysis_history | date, requirement, key_findings, risk_level | + affected_modules, key_decisions |
| project_profile | 无 | + 全新：name, description, tech_stack, architecture_style, source, last_updated |
| modules | 无 | + 全新：name, responsibility, key_classes, dependencies, path, owner |
| constraints | 无 | + 全新：description, constraint_type, modules, source |

#### 3.1.3 index 时自动构建项目知识

**这是最大的杠杆点**。当前 `reqradar index` 做了大量工作但理解为零：

```
index 做了什么：
  ✓ 扫描全量代码 → 序列化为 code_graph.json
  ✓ 向量化全部文档 → 写入 Chroma
  ✓ 分析 Git 历史 → 计算贡献者权重（用完即弃）
  ✗ 这些理解在 index 结束后全部丢失
  
index 应该额外做什么：
  → 调用 LLM 总结项目画像（从 code_graph + git log + 依赖文件）
  → 写入 project_profile 和 modules 到 memory.yaml
  → 推断团队角色分工（从 git contributor 活跃目录）
```

**新增 `reqradar index` 的知识总结步骤**：

1. 解析 `pyproject.toml`/`package.json`/`requirements.txt` 提取技术栈
2. 从 code_graph.json 统计模块划分、核心类、依赖关系
3. 从 git log 推断模块负责人
4. 调用 LLM 一次性总结项目画像

**LLM 总结 prompt（草案）**：

```
请根据以下项目代码结构信息，总结项目画像：

技术栈：{从依赖文件提取}
代码模块：{从 code_graph 提取的模块列表}
Git 贡献者：{从 git log 提取的活跃贡献者}

请输出 JSON：
{
  "description": "项目一句话描述",
  "architecture_style": "架构风格",
  "modules": [
    {
      "name": "模块名",
      "responsibility": "职责描述",
      "key_classes": ["类名列表"],
      "dependencies": ["依赖模块列表"]
    }
  ]
}
```

#### 3.1.4 术语带定义提取

当前 EXTRACT_SCHEMA 的 keywords 字段返回的是 `["IDE集成", "VS Code扩展"]`——光秃秃的词汇表。

**新版 EXTRACT_SCHEMA 变更**：

将 `keywords: [str]` 替换为 `terms: [{term, definition, domain}]`：

```python
EXTRACT_SCHEMA = {
    "name": "extract_requirement",
    "description": "从需求文档中提取结构化信息",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "从业务视角重新组织的需求理解：背景、要解决的问题、成功标准（200字以内）"
            },
            "terms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string", "description": "术语/关键词"},
                        "definition": {"type": "string", "description": "术语的定义或含义"},
                        "domain": {"type": "string", "description": "所属领域（如：认证、前端、数据库、部署等）"}
                    },
                    "required": ["term", "definition"]
                },
                "description": "需求涉及的关键术语及其定义"
            },
            "structured_constraints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "约束内容"},
                        "constraint_type": {
                            "type": "string",
                            "enum": ["performance", "security", "compatibility", "api_contract", "ux", "compliance", "other"],
                            "description": "约束类型"
                        },
                        "source": {
                            "type": "string",
                            "enum": ["requirement_document", "architecture", "implicit"],
                            "description": "约束来源：需求文档显式提出、架构隐含要求、或其他"
                        }
                    },
                    "required": ["description", "constraint_type"]
                },
                "description": "结构化约束条件"
            },
            "business_goals": {"type": "string", "description": "业务目标描述"},
            "priority_suggestion": {
                "type": "string",
                "enum": ["urgent", "high", "medium", "low"],
                "description": "基于需求紧急程度和业务价值的优先级建议"
            },
            "priority_reason": {
                "type": "string",
                "description": "优先级建议的理由（50字以内）"
            }
        },
        "required": ["summary", "terms"]
    },
}
```

#### 3.1.5 记忆注入全流程

当前只在 `step_extract` 注入术语列表。新版需要：

| 步骤 | 注入什么 | 为什么 |
|:---|:---|:---|
| step_extract | 术语表（带定义和领域）| 让 LLM 在已知术语基础上提取，避免重复提取和定义不一致 |
| step_analyze | project_profile + modules + constraints | 让 LLM 理解项目架构，即使没有代码匹配也能推断影响面 |
| step_generate | project_profile + team + analysis_history | 让 LLM 生成有深度的综合叙述 |

**记忆注入 prompt（草案）**：

```
项目知识上下文：
- 项目名称：{project_profile.name}
- 项目描述：{project_profile.description}
- 技术栈：{project_profile.tech_stack}
- 架构风格：{project_profile.architecture_style}

模块列表：
{modules 列表}

已知术语：
{terminology 带 definition 和 domain}

已知约束：
{constraints 列表}
```

---

### 3.2 步骤流程重构

#### 3.2.1 RequirementUnderstanding dataclass 扩展

```python
# 当前
@dataclass
class RequirementUnderstanding:
    raw_text: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    business_goals: str = ""

# 新版
@dataclass
class TermDefinition:
    term: str = ""
    definition: str = ""
    domain: str = ""

@dataclass
class StructuredConstraint:
    description: str = ""
    constraint_type: str = ""    # performance/security/compatibility/api_contract/ux/compliance/other
    source: str = ""             # requirement_document/architecture/implicit

@dataclass
class RequirementUnderstanding:
    raw_text: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)       # 保留兼容
    terms: list[TermDefinition] = field(default_factory=list) # 新增：带定义的术语
    constraints: list[str] = field(default_factory=list)      # 保留兼容
    structured_constraints: list[StructuredConstraint] = field(default_factory=list)  # 新增
    business_goals: str = ""
    priority_suggestion: str = ""   # 新增：urgent/high/medium/low
    priority_reason: str = ""       # 新增：优先级理由
```

#### 3.2.2 DeepAnalysis dataclass 扩展

```python
# 当前
@dataclass
class DeepAnalysis:
    impact_modules: list = field(default_factory=list)
    contributors: list = field(default_factory=list)
    risk_level: str = "unknown"
    risk_details: list = field(default_factory=list)

# 新版
@dataclass
class RiskItem:
    description: str = ""
    severity: str = ""          # high/medium/low
    scope: str = ""             # 影响范围描述
    mitigation: str = ""        # 缓解建议

@dataclass
class ChangeAssessment:
    module: str = ""
    change_type: str = ""       # new/modify/refactor
    impact_level: str = ""      # high/medium/low
    reason: str = ""

@dataclass
class ImplementationHints:
    approach: str = ""           # 建议实施方向
    effort_estimate: str = ""    # small/medium/large
    dependencies: list[str] = field(default_factory=list)  # 前置依赖

@dataclass
class DeepAnalysis:
    impact_modules: list = field(default_factory=list)
    contributors: list = field(default_factory=list)
    risk_level: str = "unknown"
    risk_details: list = field(default_factory=list)
    # 新增字段
    risks: list[RiskItem] = field(default_factory=list)              # 结构化风险列表
    change_assessment: list[ChangeAssessment] = field(default_factory=list) # 模块变更评估
    verification_points: list[str] = field(default_factory=list)     # 验证要点
    implementation_hints: ImplementationHints = field(default_factory=ImplementationHints)  # 实施建议
```

#### 3.2.3 GeneratedContent dataclass 扩展

```python
# 当前（本质是 dict）
# step_generate 返回 {"understanding": "...", "relation": "...", "constraints": "..."}

# 新版
@dataclass
class GeneratedContent:
    requirement_understanding: str = ""   # 200-300字业务视角理解
    impact_narrative: str = ""             # 150-200字影响范围描述
    risk_narrative: str = ""               # 150-200字风险分析描述
    implementation_suggestion: str = ""     # 100-150字实施建议
```

#### 3.2.4 step_analyze 条件拆分（最关键的单点改动）

**当前代码**：

```python
if llm_client and analysis.impact_modules:
    # ... LLM 调用 ...
```

**问题**：没有代码匹配 → impact_modules 为空 → LLM 被完全跳过 → 风险永远是 unknown。

**修改方案**：

```python
# 即使没有代码匹配，也调用 LLM 做风险评估
if llm_client:
    # 构建上下文（有代码匹配就用代码信息，没有就用项目知识）
    modules_text = "无匹配代码模块"
    if analysis.impact_modules:
        modules_text = "\n".join(
            f"- {m['path']} ({', '.join(m['symbols'][:3])})"
            for m in analysis.impact_modules[:5]
        )

    # 注入项目知识
    project_context = ""
    if context.memory_data and context.memory_data.get("project_profile"):
        profile = context.memory_data["project_profile"]
        project_context = f"项目名称：{profile.get('name', '未知')}\n"
        project_context += f"项目描述：{profile.get('description', '未知')}\n"
        project_context += f"技术栈：{profile.get('tech_stack', '未知')}\n"

    messages = [
        {"role": "user", "content": ANALYZE_PROMPT.format(
            summary=context.understanding.summary if context.understanding else "",
            modules=modules_text,
            contributors=contributors_text or "无",
            project_context=project_context,
        )},
    ]
    result = await _call_llm_structured(llm_client, messages, ANALYZE_SCHEMA, max_tokens=2048)
    # ... 解析结果到 analysis 对象 ...
```

#### 3.2.5 ANALYZE_SCHEMA 扩展

```python
ANALYZE_SCHEMA = {
    "name": "analyze_risks",
    "description": "基于需求信息和项目知识，评估技术影响和风险",
    "parameters": {
        "type": "object",
        "properties": {
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "总体风险等级"
            },
            "risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "风险描述"},
                        "severity": {"type": "string", "enum": ["high", "medium", "low"], "description": "严重程度"},
                        "scope": {"type": "string", "description": "影响范围"},
                        "mitigation": {"type": "string", "description": "缓解建议"},
                    },
                    "required": ["description", "severity"],
                },
                "description": "结构化风险列表（至少2项）"
            },
            "verification_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "评审时应重点验证的事项（至少3项）"
            },
            "change_assessment": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module": {"type": "string", "description": "受影响模块"},
                        "change_type": {"type": "string", "enum": ["new", "modify", "refactor"], "description": "变更类型"},
                        "impact_level": {"type": "string", "enum": ["high", "medium", "low"], "description": "影响等级"},
                        "reason": {"type": "string", "description": "变更原因"},
                    },
                    "required": ["module", "change_type", "impact_level"],
                },
                "description": "每个受影响模块的变更评估（即使没有代码匹配，也根据项目知识推断）"
            },
            "implementation_hints": {
                "type": "object",
                "properties": {
                    "approach": {"type": "string", "description": "建议实施方向"},
                    "effort_estimate": {"type": "string", "enum": ["small", "medium", "large"], "description": "粗略工作量评估"},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "前置依赖条件"
                    },
                },
                "description": "实施建议"
            }
        },
        "required": ["risk_level", "risks", "verification_points"],
    },
}
```

#### 3.2.6 GENERATE_SCHEMA 扩展

```python
GENERATE_SCHEMA = {
    "name": "generate_report_sections",
    "description": "基于分析结果生成需求分析报告的关键叙述段落",
    "parameters": {
        "type": "object",
        "properties": {
            "requirement_understanding": {
                "type": "string",
                "description": "从业务视角重新组织的需求理解：背景、要解决的问题、成功标准（200-300字）"
            },
            "impact_narrative": {
                "type": "string",
                "description": "用自然语言描述影响范围和关键变更点（150-200字）"
            },
            "risk_narrative": {
                "type": "string",
                "description": "用自然语言描述主要风险和缓解思路（150-200字）"
            },
            "implementation_suggestion": {
                "type": "string",
                "description": "实施方向建议和注意事项（100-150字）"
            },
        },
        "required": ["requirement_understanding"],
    },
}
```

#### 3.2.7 step_generate prompt 重写

```python
GENERATE_PROMPT = """基于以下分析上下文，生成需求分析报告的关键叙述段落。

需求摘要：{summary}

影响模块：{modules}

评审人建议：{contributors}

风险评估：{risk_level} - {risk_details}

{project_context}

请分别生成以下段落，要求有深度、有分析、有建议，不要泛泛而谈：
1. requirement_understanding：从业务视角重新组织需求理解（背景、问题、成功标准）
2. impact_narrative：描述影响范围和关键变更点
3. risk_narrative：描述主要风险和缓解思路
4. implementation_suggestion：实施方向建议和注意事项"""
```

---

### 3.3 报告模板重构

#### 3.3.1 新报告结构

```
# 需求分析报告：{{ requirement_title }}

## 报告概况

| 字段 | 内容 |
|:---|:---|
| 需求标题 | {{ title }} |
| 分析时间 | {{ timestamp }} |
| 需求来源 | {{ requirement_path }} |
| 风险等级 | {{ risk_badge }} |
| 影响范围 | {{ impact_scope }} 个模块 |
| 建议优先级 | {{ priority }} |

---

## 1. 需求理解

### 1.1 需求概述
{{ requirement_understanding }}
（从业务视角重新组织——背景、要解决的问题、成功标准）

### 1.2 核心术语
| 术语 | 定义 | 所属领域 |
|:---|:---|:---|
| {{ term }} | {{ definition }} | {{ domain }} |

### 1.3 约束条件
| 约束 | 类型 | 来源 |
|:---|:---|:---|
| {{ constraint }} | {{ type }} | {{ source }} |

---

## 2. 影响分析

### 2.1 代码影响范围
（如果有代码匹配）
| 模块 | 核心类/方法 | 变更类型 | 影响等级 |
|:---|:---|:---|:---|
| {{ module }} | {{ symbols }} | {{ change_type }} | {{ impact_level }} |

（如果没有代码匹配，则显示项目模块和 LLM 推断的影响分析）

### 2.2 变更评估
| 模块 | 变更类型 | 影响等级 | 原因 |
|:---|:---|:---|:---|
| {{ module }} | {{ change_type }} | {{ impact_level }} | {{ reason }} |

### 2.3 相似历史需求
| 需求 | 相似度 | 关键结论 | 经验教训 |
|:---|:---|:---|:---|
| {{ prev_req }} | {{ similarity }}% | {{ outcome }} | {{ lessons }} |

---

## 3. 风险评估

### 3.1 风险概览
| 风险项 | 等级 | 影响范围 | 缓解建议 |
|:---|:---|:---|:---|
| {{ risk_item }} | {{ severity }} | {{ scope }} | {{ mitigation }} |

### 3.2 验证要点
（评审时应该重点检查的事项清单）

---

## 4. 建议评审人

| 姓名 | 角色 | 负责模块 | 变更相关度 |
|:---|:---|:---|:---|
| {{ name }} | {{ role }} | {{ modules }} | {{ relevance }} |

---

## 5. 实施建议

### 5.1 建议优先级
{{ priority }}（{{ priority_reason }}）

### 5.2 预估工作量
{{ effort_estimate }}

### 5.3 关键依赖
{{ dependencies }}

---

## 附录 A. 数据完整性

- 分析置信度：{{ confidence }}%
- 数据完整度：{{ completeness }}
- LLM 调用成功：{{ llm_calls_succeeded }}/{{ llm_calls_total }}

{{ warnings }}

### 附录 B. 项目知识上下文

- 项目：{{ project_name }}
- 技术栈：{{ tech_stack }}
- 架构风格：{{ architecture_style }}

---

*本报告由 ReqRadar 自动生成，仅供参考。*
```

#### 3.3.2 报告模板的关键变化

| 变化 | 旧 | 新 | 理由 |
|:---|:---|:---|:---|
| 报告概况 | 无 | 风险等级+影响范围+优先级一览表 | 评审人 5 秒内获取关键结论 |
| 需求摘要 | 复述原文 100 字 | 业务视角重述 200-300 字 | 不是复述，是理解和提炼 |
| 核心术语 | 扁平关键词列表 | 表格：术语/定义/领域 | 信息密度 10 倍提升 |
| 约束条件 | 字符串列表 | 结构化表格：描述/类型/来源 | 区分显式/隐式/架构约束 |
| 代码影响 | 一张简单表格 | 带变更类型和影响等级的表格 | 更专业的评估维度 |
| 变更评估 | 无 | 全新章节 | LLM 推断的模块影响面 |
| 相似需求 | 只有相似度 | 表格包含关键结论和经验教训 | 有参考价值的历史信息 |
| 风险评估 | 一个等级字符串 | 结构化表格，永远有值 | 不再出现 "unknown" |
| 验证要点 | 无 | 全新章节 | 评审人的检查清单 |
| 评审人 | 简单列表 | 表格含角色和模块归属 | 更有参考价值 |
| 实施建议 | 无 | 全新章节：优先级/工作量/依赖 | 项目经理的决策依据 |
| 项目知识 | 无 | 附录 B | 展示 ReqRadar 对项目的理解深度 |

#### 3.3.3 置信度语义修正

当前 `confidence` 衡量的是"步骤是否执行"，不是"内容是否有价值"。需要新增：

```python
@dataclass
class AnalysisContext:
    # ... 现有字段 ...
    
    @property
    def content_confidence(self) -> str:
        """内容可信度（而非执行率）"""
        has_risk = self.deep_analysis and self.deep_analysis.risk_level != "unknown"
        has_impact = self.deep_analysis and len(self.deep_analysis.impact_modules) > 0
        has_terms = self.understanding and len(self.understanding.terms) > 0
        
        if has_risk and has_impact and has_terms:
            return "high"
        elif has_risk or has_terms:
            return "medium"
        else:
            return "low"
```

模板中使用 `content_confidence` 代替简单的百分比，并在报告概况中展示。

---

### 3.4 语义关键词桥接

#### 3.4.1 问题描述

"双因素认证" 匹配不到 `two_factor_auth.py`，"IDE集成" 匹配不到 `vscode_extension.py`。纯字面子串匹配等于盲人摸象。

#### 3.4.2 解决方案：extract 阶段让 LLM 做关键词映射

新增一个 `KEYWORD_MAPPING_SCHEMA`：

```python
KEYWORD_MAPPING_SCHEMA = {
    "name": "map_keywords_to_code",
    "description": "将业务术语映射为可能对应的代码层术语，用于代码搜索",
    "parameters": {
        "type": "object",
        "properties": {
            "mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "business_term": {"type": "string", "description": "业务术语"},
                        "code_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "可能对应的代码层术语（英文、驼峰、下划线）"
                        },
                    },
                    "required": ["business_term", "code_terms"],
                },
                "description": "每个业务术语对应的代码搜索词"
            }
        },
        "required": ["mappings"],
    },
}
```

**在 step_extract 之后、step_retrieve 之前新增映射步骤**：

```python
# pseudo code
async def step_map_keywords(context, llm_client):
    """将业务术语映射为代码搜索词"""
    terms = context.understanding.terms  # 或 keywords
    mappings = await _call_llm_structured(llm_client, messages, KEYWORD_MAPPING_SCHEMA)
    # "双因素认证" → ["two_factor", "2fa", "mfa", "auth", "otp", "totp"]
    # "IDE集成" → ["extension", "plugin", "vscode", "ide", "language_server"]
    context.search_keywords = expand_keywords(terms, mappings)
```

搜索时同时使用原始关键词和映射后的代码术语：

```python
# code_parser.py
def find_symbols(self, keywords: list[str], expanded_keywords: list[str] = None) -> list[CodeFile]:
    search_terms = keywords + (expanded_keywords or [])
    # ... 同时搜索原始关键词和映射后的代码术语
```

---

### 3.5 相似需求增加历史结论

**当前问题**：相似需求只显示相似度和标题，没有"这个需求后来怎么样了"的结论。

**解决**：在内存的 `analysis_history` 中存储结构化结论，检索到相似需求时关联历史结果：

```yaml
analysis_history:
  - date: "2026-04-15"
    requirement: "user-auth-enhancement"
    summary: "认证功能优化需求"
    risk_level: "medium"
    affected_modules: ["auth/", "user/"]
    key_decisions: ["选择 TOTP 实现双因素认证"]
    outcome: "实施中"               # 新增：需求最终结局
    lessons: "需注意与现有 Session 机制的兼容"  # 新增：经验教训
```

---

## 四、实施步骤

### Phase 3A：数据模型 + Schema + 步骤重构（2天）

| 顺序 | 任务 | 优先级 | 预估 |
|:---|:---|:---|:---|
| A1 | 扩展 `RequirementUnderstanding` dataclass | P0 | 0.5天 |
| A2 | 扩展 `DeepAnalysis` dataclass | P0 | 0.5天 |
| A3 | 新增 `GeneratedContent` dataclass | P0 | 0.5天 |
| A4 | 重写 `EXTRACT_SCHEMA` 和 `step_extract` | P0 | 0.5天 |
| A5 | **拆分 step_analyze 条件，始终调用 LLM** | P0 | 0.5天 |
| A6 | 重写 `ANALYZE_SCHEMA` | P0 | 0.5天 |
| A7 | 重写 `GENERATE_SCHEMA` 和 `step_generate` | P0 | 0.5天 |
| A8 | 让 analyze/generate 也注入项目知识 | P0 | 0.5天 |

### Phase 3B：记忆重构 + index 构建知识（2天）

| 顺序 | 任务 | 优先级 | 预估 |
|:---|:---|:---|:---|
| B1 | 重构 `MemoryManager` 数据结构 | P0 | 1天 |
| B2 | `reqradar index` 结束后调用 LLM 构建项目画像 | P0 | 1天 |
| B3 | 术语写入时带定义（从 LLM 提取结果写入） | P0 | 0.5天 |
| B4 | 记忆注入到 extract/analyze/generate 全流程 | P0 | 0.5天 |

### Phase 3C：报告模板重写（1.5天）

| 顺序 | 任务 | 优先级 | 预估 |
|:---|:---|:---|:---|
| C1 | 重写 `report.md.j2` | P0 | 0.5天 |
| C2 | 扩展 `ReportRenderer.render()` 传入新数据字段 | P0 | 0.5天 |
| C3 | 新增内容可信度 (`content_confidence`) | P1 | 0.25天 |
| C4 | 更新 CLI analyze 命令的数据传递 | P0 | 0.25天 |

### Phase 3D：语义桥接 + 质量保障（1.5天）

| 顺序 | 任务 | 优先级 | 预估 |
|:---|:---|:---|:---|
| D1 | 新增 `KEYWORD_MAPPING_SCHEMA` 和映射步骤 | P1 | 1天 |
| D2 | 修复 JSON 降级解析边界情况 | P0 | 0.5天 |
| D3 | 端到端测试 + 对比新旧报告质量 | P0 | 0.5天 |
| D4 | 更新测试用例 | P0 | 0.5天 |
| D5 | 更新 DESIGN.md 和 README.md | P1 | 0.5天 |

**总计：约 7 天**

---

## 五、预期效果对比

### 5.1 当前产出 vs 目标产出

以"IDE 集成支持"需求为例：

**当前报告关键章节**：
```
## 三、技术影响分析
暂无代码影响分析数据

## 四、建议评审人
*未找到相关评审人信息*

## 五、风险评估
**总体风险等级**：unknown
```

**目标报告关键章节**：
```
## 报告概况
| 风险等级 | 🟡 中 | 影响范围 | 2个模块 | 建议优先级 | 中 |

## 1.1 需求概述
ReqRadar 需要扩展使用场景从 CLI 到 IDE 集成。核心目标是让开发者无需切换
终端即可完成需求分析。成功标准：开发者能在 IDE 内触发分析并查看报告。

## 1.2 核心术语
| 术语 | 定义 | 领域 |
|:---|:---|:---|
| IDE集成 | 将分析能力嵌入 VS Code/PyCharm 开发环境 | 工具链 |
| CLI解耦 | IDE 扩展与命令行工具独立运行 | 架构约束 |

## 2.2 变更评估
| 模块 | 变更类型 | 影响等级 | 原因 |
|:---|:---|:---|:---|
| cli/ | 修改 | 低 | 需确保 CLI 接口可被外部调用 |
| agent/ | 无变更 | - | 5步流程保持兼容 |

## 3.1 风险概览
| 风险项 | 等级 | 影响范围 | 缓解建议 |
|:---|:---|:---|:---|
| 双 IDE 适配工作量大 | 中 | 开发周期 | 优先 VS Code |
| 技术栈不匹配 | 中 | 开发效率 | 子进程调用 CLI |

## 5.1 建议优先级
中 — 非核心功能增强，但显著提升开发者体验
```

### 5.2 记忆系统对比

**当前 memory.yaml**：
```yaml
terminology:
- term: IDE集成
  definition: ''           # 空！
  context: 自动提取         # 无语义
team: []                   # 空！
```

**目标 memory.yaml**：
```yaml
project_profile:
  name: ReqRadar
  description: "固定流程的需求分析垂直 Agent"
  tech_stack:
    languages: ["Python"]
    frameworks: ["Click", "Pydantic", "ChromaDB", "Jinja2"]
  architecture_style: "分层架构 - CLI/调度/能力/基础设施"

modules:
  - name: "agent/steps"
    responsibility: "5步工作流实现"
    key_classes: ["step_read", "step_extract", "step_retrieve", "step_analyze", "step_generate"]

terminology:
  - term: "IDE集成"
    definition: "将分析能力嵌入 VS Code/PyCharm 开发环境"
    domain: "工具链"
    source: "llm_extract"
```

---

## 六、风险与缓解

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| LLM 调用成本增加 | 每次 index 多 1 次 LLM 调用；analyze 多 1 次关键词映射 | 成本仍可控：index 总结约 2K tokens，关键词映射约 1K tokens |
| LLM 返回结构不稳定 | 新 Schema 字段更多，function calling 降级概率可能增加 | 三层降级兜底：function calling → 文本 JSON → 规则提取 |
| 记忆文件膨胀 | 多次 index/analyze 后 memory.yaml 可能很大 | analysis_history 上限 50 条；模块信息只在 index 时刷新 |
| 报告模板渲染 复杂度 | 模板逻辑变多，空值处理更复杂 | Jinja2 默认值和条件渲染保证健壮性 |

---

## 七、验收标准

Phase 3 完成后，需满足以下条件才算通过：

1. **记忆系统**：`reqradar index` 后 memory.yaml 包含 `project_profile`（name/description/tech_stack/architecture_style）和 `modules` 列表
2. **术语质量**：分析后术语每个都有 `definition`，不再有空定义
3. **风险评估**：任何分析场景下 `risk_level` 不再是 "unknown"，至少有 2 个结构化风险项
4. **报告内容**：新报告中不存在"暂无"或"unknown"的章节；风险等级、变更评估、验证要点永远有值
5. **端到端测试**：用 MiniMax-M2.5 真实 API 跑一遍 `reqradar analyze`，产出报告的每一节都有实质内容
6. **现有测试**：99+ 测试全部通过
7. **降级路径**：断开 LLM 连接后，分析仍能产出报告（内容降级但格式完整）

---

*本文档为 Phase 3 的完整规划，实施前需要团队评审确认优先级和工期。*