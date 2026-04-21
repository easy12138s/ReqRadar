# ReqRadar 项目设计文档

> 本文档记录项目的核心定位、技术决策和实现方案，作为长期维护的参考依据。
> 任何重大变更应同步更新本文档。

---

## 一、项目定位

### 1.1 愿景

ReqRadar（需求透视）是一个**固定流程的垂直领域 Agent**，服务于需求从提出到开发之间的信息对齐环节。通过聚合散落在需求文档、代码仓库、历史记录中的关键信息，在关键节点为团队提供共用的上下文参考。

### 1.2 核心特征

| 特征 | 说明 |
|:---|:---|
| **固定流程** | 每次分析严格按照预定 6 步顺序执行，不根据中间结果动态调整路径 |
| **固定模板** | 输出报告的结构、章节、字段完全预定义，LLM 仅填充自然语言内容 |
| **确定性优先** | 相同输入在任何时间执行，报告结构和关键结论一致，行为可预期 |
| **隐私优先** | 敏感数据（如聊天记录）的提取在本地完成，仅输出脱敏摘要，原始内容不外传 |
| **记忆驱动** | 自动积累项目知识（术语、模块、贡献者），后续分析可复用历史上下文 |

### 1.3 目标用户与价值

| 角色 | 价值 |
|:---|:---|
| **产品经理** | 提需求时预判技术影响面，降低沟通成本 |
| **部门领导/评审者** | 获取相似历史需求参考与风险提示，辅助评审决策 |
| **开发者** | 提前获得代码上下文、维护者信息和隐性约束，减少理解偏差 |

### 1.4 不做的事

- 不生成代码
- 不做实时监控
- 不提供自由对话式交互
- 不将原始敏感数据外传

---

## 二、整体架构

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│ 接入层 (Entrypoints)                                        │
│ CLI (index / analyze)                  │ MCP Server (未来)  │
├─────────────────────────────────────────────────────────────┤
│ 调度层 (Fixed Pipeline Executor)                            │
│ 步骤顺序执行 │ 上下文管理 │ 异常降级处理 │ 钩子机制         │
├─────────────────────────────────────────────────────────────┤
│ Agent 层 (Intelligent Analysis)                             │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│ │智能模块匹配   │ │深度关联分析   │ │代码摘要生成   │         │
│ │(LLM 主动查询) │ │(关联度评估)   │ │(批量生成)    │         │
│ └──────────────┘ └──────────────┘ └──────────────┘         │
├─────────────────────────────────────────────────────────────┤
│ 能力层 (Capabilities)                                       │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │代码解析器│ │向量检索器│ │Git 分析器│ │LLM 客户端│        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│ │记忆管理器│ │文档加载器│ │报告渲染器│                     │
│ └──────────┘ └──────────┘ └──────────┘                     │
├─────────────────────────────────────────────────────────────┤
│ 基础设施层 (Infrastructure)                                  │
│ 配置管理 │ 日志系统 │ 持久化存储 │ 错误处理 │ 插件注册表    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 技术选型 |
|:---|:---|:---|
| **代码解析器** | 扫描代码仓库，构建函数/类/模块关系图谱 | Python AST |
| **向量检索器** | 索引需求文档，返回相似需求 | Chroma + BGE-large-zh |
| **Git 分析器** | 提取文件修改热度和主要贡献者 | GitPython |
| **LLM 客户端** | 封装与 LLM 的交互，支持 Function Calling | OpenAI / Ollama |
| **记忆管理器** | 项目画像、模块、术语、历史的持久化存储 | YAML |
| **智能匹配器** | LLM 主动查询相关模块，深度分析关联度 | 自研 |
| **调度器** | 按固定顺序调用模块，管理上下文，处理异常 | 自研 |
| **报告生成器** | 加载预定义模板，渲染 Markdown 报告 | Jinja2 |

---

## 三、固定执行流程

每次 `reqradar analyze` 严格按以下顺序执行：

| 步骤 | 名称 | 动作 | 输出 |
|:---:|:---|:---|:---|
| 1 | read | 读取需求文档纯文本 | 文本内容 |
| 2 | extract | 调用 LLM 提取关键词和业务术语 | 术语列表 + 摘要 |
| 3 | map_keywords | 将中文业务术语映射为英文代码搜索词 | 扩展关键词列表 |
| 4 | retrieve | 基于术语检索相似历史需求 + 智能匹配代码模块 | 相似需求 + 影响模块 |
| 5 | analyze | 获取相关模块的 Git 贡献者信息，深度分析模块关联 | 建议评审人 + 关联分析 |
| 6 | generate | 调用 LLM 生成各模块描述，按模板渲染报告 | Markdown 报告文件 |

### 3.1 智能模块匹配（Phase 4 新增）

```mermaid
graph LR
    A[需求理解] --> B[LLM 主动查询]
    B --> C[从记忆中获取模块]
    C --> D[深度关联分析]
    D --> E[输出: relevance, relevance_reason, suggested_changes]
    E --> F[持久化到记忆]
```

**核心函数**：

| 函数 | 职责 |
|:---|:---|
| `_query_relevant_modules_from_memory()` | LLM 基于项目画像主动查询相关模块 |
| `_analyze_module_relevance()` | 深度分析模块与需求的关联，输出关联度评估 |
| `_smart_module_matching()` | 整合查询 + 分析，统一入口 |
| `_generate_batch_module_summaries()` | 批量生成模块代码摘要，减少 LLM 调用 |

**数据流**：

```
输入: RequirementUnderstanding + memory_data
处理: LLM 查询 → 模块匹配 → 深度分析
输出: impact_modules = [
  {
    "path": "src/auth",
    "symbols": ["AuthService", "TokenManager"],
    "relevance": "high",
    "relevance_reason": "直接负责认证功能",
    "suggested_changes": "新增 verify_2fa() 方法"
  }
]
持久化: memory_manager.add_module_requirement_history()
```

### 3.2 LLM 调用点（5-6 次）

| 调用 | 时机 | 输入 | 输出 | 模型 |
|:---|:---|:---|:---|:---|
| #1 | Step 2 | 需求全文 | 术语列表(5-10个) + 摘要(200字) | gpt-4o-mini |
| #2 | Step 3 | 业务术语列表 | 映射的代码搜索词 | gpt-4o-mini |
| #3 | Step 4 | 项目画像 + 模块列表 | 相关模块查询结果 | gpt-4o-mini |
| #4 | Step 4 | 候选模块详情 | 关联度评估 + 建议变更 | gpt-4o-mini |
| #5 | Step 5 | 影响模块列表 | 各模块描述(每段50字) | gpt-4o-mini |
| #6 | Step 6 | 完整上下文 | 风险总结(100字) | gpt-4o-mini |

**成本控制**：
- 单次分析约 5-8K tokens，成本 < $0.02
- 批量摘要生成：从 O(n) 次 LLM 调用优化到 O(1) 次

### 3.3 降级策略

| 步骤 | 失败时降级行为 |
|:---|:---|
| Step 2: 术语提取 | 使用 TF-IDF 规则提取关键词 |
| Step 3: 关键词映射 | 使用原始术语作为搜索词 |
| Step 4: 智能匹配 | 降级到基于关键词的符号匹配 |
| Step 5: Git 分析 | 返回空列表，报告标注 |
| Step 6: LLM 生成 | 使用模板占位文本填充 |

---

## 四、项目记忆系统

### 4.1 记忆结构

```yaml
# .reqradar/memory/memory.yaml
project_profile:
  name: "ReqRadar"
  description: "需求分析 Agent"
  architecture_style: "分层架构"
  tech_stack:
    languages: ["Python"]
    frameworks: ["Click", "Pydantic", "Chroma"]
  last_updated: "2026-04-20"

modules:
  - name: "auth"
    responsibility: "用户认证模块"
    path: "src/auth"
    key_classes: ["AuthService", "TokenManager"]
    code_summary: "提供用户登录、登出、Token 管理功能..."
    related_requirements:  # 新增：模块关联历史
      - requirement_id: "user-auth-enhancement"
        relevance: "high"
        suggested_changes: "新增 verify_2fa() 函数"
        timestamp: "2026-04-20T10:00:00"

terminology:
  - term: "双因素认证"
    definition: "Two-Factor Authentication"
    domain: "安全"
    source: "llm_extract"

team:
  - name: "张三"
    email: "zhangsan@example.com"
    role: "核心开发者"
    source: "git_analyzer"

analysis_history:
  - requirement_id: "user-auth-enhancement"
    summary: "增强用户认证安全性"
    affected_modules: ["auth", "user"]
    timestamp: "2026-04-20"
```

### 4.2 记忆更新机制

```python
# 每次分析后自动更新
scheduler.register_after_hook("analyze", persist_module_history_hook)
scheduler.register_after_hook("generate", memory_update_hook)
```

| 钩子 | 触发时机 | 更新内容 |
|:---|:---|:---|
| `persist_module_history_hook` | analyze 后 | 模块关联历史 (related_requirements) |
| `memory_update_hook` | generate 后 | 术语、团队、分析历史 |

---

## 五、数据模型

### 5.1 核心数据类

```python
@dataclass
class RequirementUnderstanding:
    summary: str
    raw_text: str = ""
    terms: list[TermDefinition] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

@dataclass
class ModuleAnalysisResult:
    path: str = ""
    symbols: list[str] = field(default_factory=list)
    relevance: str = "low"  # high/medium/low
    relevance_reason: str = ""
    suggested_changes: str = ""

@dataclass
class CodeAnalysisResult:
    modules: list[ModuleAnalysisResult] = field(default_factory=list)
    overall_assessment: dict = field(default_factory=dict)
    confidence: float = 0.0

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
    code_analysis: Optional[CodeAnalysisResult] = None  # 新增
    step_results: dict[str, StepResult] = field(default_factory=dict)
```

---

## 六、技术选型

| 类别 | 选型 | 说明 |
|:---|:---|:---|
| **语言** | Python 3.12 | |
| **包管理** | Poetry | 依赖锁定 |
| **CLI** | Click | 轻量、易用 |
| **配置** | PyYAML + Pydantic | 支持环境变量覆盖 |
| **代码解析** | Python AST | 第一期；未来可升级 Tree-sitter |
| **向量数据库** | Chroma（嵌入式） | 开箱即用；未来可切换 Qdrant |
| **嵌入模型** | BAAI/bge-large-zh | 本地运行，首次自动下载 |
| **LLM 客户端** | 自研抽象 | 支持 OpenAI / Ollama 双后端 + Function Calling |
| **日志** | structlog | 结构化日志 |
| **进度显示** | rich | CLI 交互体验 |
| **测试** | pytest | 220+ 测试用例 |

---

## 七、部署与索引模式

### 7.1 索引构建

```
CI/CD Pipeline (Producer)                  开发者本地 (Consumer)
┌─────────────────────┐                    ┌─────────────────────┐
│ 1. 检出代码仓库     │                    │                     │
│ 2. 解析代码结构     │                    │  reqradar analyze   │
│ 3. 构建向量索引     │──────────→ 索引 ──→│ 读取共享索引路径    │
│ 4. 构建项目画像     │                    │ 生成本地报告        │
│ 5. 上传至共享存储   │                    │                     │
└─────────────────────┘                    └─────────────────────┘
```

### 7.2 配置优先级

```
本地 .reqradar.yaml → 用户目录全局配置 → 环境变量
```

---

## 八、可扩展性设计

| 扩展点 | 机制 | 未来场景 |
|:---|:---|:---|
| 新编程语言 | `CodeParser` 抽象 + 注册表 | TypeScript、Java、Go |
| 新向量数据库 | `VectorStore` 抽象 | Qdrant、LanceDB |
| 新 LLM 后端 | `LLMProvider` 抽象 | Azure OpenAI、Claude |
| 自定义报告模板 | 配置文件指定模板路径 | 企业定制样式 |
| 步骤前后注入逻辑 | 钩子机制 | 发送通知、额外日志 |
| 新文档格式 | `DocumentLoader` 抽象 + 注册表 | Excel、Notion |

---

## 九、项目结构

```
reqradar/
├── src/reqradar/
│   ├── __init__.py
│   ├── cli/                    # CLI 入口
│   │   ├── __init__.py
│   │   └── main.py             # Click 命令定义
│ ├── core/ # 核心调度
│ │ ├── __init__.py
│ │ ├── scheduler.py # 固定流程调度器
│ │ ├── context.py # AnalysisContext + 数据模型
│ │ ├── report.py # 报告渲染器
│ │ └── exceptions.py # 错误定义
│   ├── modules/                # 能力模块
│   │   ├── __init__.py
│   │   ├── code_parser.py      # Python AST 解析
│   │   ├── vector_store.py     # Chroma 封装
│   │   ├── git_analyzer.py     # Git 贡献者分析
│   │   ├── llm_client.py       # OpenAI/Ollama 客户端 + Function Calling
│   │   ├── memory.py           # 项目记忆管理器
│   │   └── loaders/            # 文档加载器
│   │       ├── base.py         # ABC + 注册表
│   │       ├── text_loader.py  # Markdown/Text/RST
│   │       ├── pdf_loader.py   # PDF
│   │       ├── docx_loader.py  # Word DOCX
│   │       ├── image_loader.py # 图片（LLM 视觉）
│   │       └── chat_loader.py  # 飞书 JSON + 通用 CSV
│ ├── agent/ # Agent 流程
│ │ ├── __init__.py
│ │ ├── steps.py # 6步工作流（~480行，精简后）
│ │ ├── schemas.py # LLM Function Calling schemas
│ │ ├── prompts.py # Prompt 模板
│ │ ├── llm_utils.py # LLM 调用工具函数
│ │ ├── smart_matching.py # 智能模块匹配
│ │ └── project_profile.py # 项目画像构建
│ ├── infrastructure/ # 基础设施
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── errors.py
│   │   └── registry.py         # 插件注册表
│   └── templates/              # 报告模板
│       └── report.md.j2
├── tests/ # 单元测试 (220+)
├── docs/                       # 文档
├── pyproject.toml              # Poetry 配置
├── README.md                   # 项目简介
├── DESIGN.md                   # 本文档
└── .reqradar.yaml.example      # 配置示例
```

---

## 十、工程规范

### 10.1 代码质量

- **格式化**：Black（行宽 100）
- **静态检查**：Ruff + MyPy
- **测试**：pytest，核心模块覆盖率 > 80%，220+ 测试用例

### 10.2 Git 提交规范

```
feat: 新功能
fix: 修复问题
docs: 文档更新
refactor: 重构
test: 测试相关
chore: 构建/工具更新
```

---

## 十一、分阶段路线

### Phase 1（MVP）✅ 已完成

- [x] 项目骨架与工程规范
- [x] Python 代码解析器
- [x] Chroma 向量索引与检索
- [x] 固定流程调度器
- [x] 固定模板报告生成
- [x] `index` 和 `analyze` 命令

### Phase 2 ✅ 已完成

- [x] 配置系统扩展（VisionConfig、MemoryConfig、LoaderConfig）
- [x] 文档加载器框架（DocumentLoader ABC + 注册表）
- [x] TextLoader + PDFLoader + DocxLoader
- [x] ImageLoader（LLM 视觉能力）
- [x] ChatLoader（飞书 JSON + 通用 CSV）
- [x] 项目记忆系统（术语/团队/历史，自动读写）
- [x] LLM 视觉能力（complete_vision 接口）

### Phase 3 ✅ 已完成

- [x] 企业级报告模板（多角色关注点）
- [x] 关键词映射（中文术语 → 英文代码搜索词）
- [x] Function Calling 集成（结构化输出）
- [x] 记忆集成到 analyze 流程（Step 前/后钩子）

### Phase 4 ✅ 已完成

- [x] 记忆扩展：模块代码摘要 (code_summary)
- [x] 记忆扩展：模块关联历史 (related_requirements)
- [x] 智能模块查询（LLM 主动查询相关模块）
- [x] 深度关联分析（relevance, relevance_reason, suggested_changes）
- [x] 批量摘要生成（优化 LLM 调用成本）
- [x] 分析后持久化模块历史

### Phase 5（待规划）

- [ ] 完善 LLM 调用失败时的降级策略
- [ ] Tree-sitter 替代 AST（精准语法树）
- [ ] 报告模板自定义
- [ ] 图片文件自动视觉分析集成到 step_read
- [ ] MCP Server 形态
- [ ] 多向量库后端支持
- [ ] 发布 PyPI

---

## 十二、常见问题

### Q: 为什么选择固定流程而不是动态 Agent？
A: 需求分析是一个结构化任务，核心价值在于提供一致、可预期的报告。动态 Agent 虽然灵活，但行为不可预测，难以保证报告质量。

### Q: 为什么 LLM 只用于内容生成而不是流程决策？
A: 项目定位是"需求预检工具"而非"智能助手"。流程固定可以保证稳定输出，降低使用风险。

### Q: 智能模块匹配相比关键词匹配有什么优势？
A: 关键词匹配依赖字面匹配，容易漏掉语义相关但不共享关键词的模块。智能匹配通过 LLM 理解项目画像和模块职责，能发现隐含的关联关系。

### Q: Chroma 嵌入式够用吗？
A: 对于 10-50 人团队、单项目 < 1000 需求文档的场景足够。未来可切换到 Qdrant 等支持并发的方案。

---

*最后更新：2026-04-21*
