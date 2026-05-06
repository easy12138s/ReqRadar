# ReqRadar Agent 架构重构与报告回溯系统设计

> **日期**: 2026-04-23
> **版本**: v1.0
> **状态**: 待评审

---

## 1. 概述

### 1.1 目标

将 ReqRadar 从固定流水线（Fixed Pipeline）升级为**目标驱动的自主 Agent 架构**。Agent 的核心目标是"为给定需求生成专业、可验证的分析报告"，通过 ReAct 循环自主决定信息收集策略，而非遵循预设步骤。

### 1.2 关键变更

| 维度 | 现状 | 目标 |
|:---|:---|:---|
| 分析流程 | 固定6步（read → extract → map → retrieve → analyze → generate） | ReAct 自主循环，Agent 决定下一步行动 |
| 记忆系统 | 单个 YAML 文件，无隔离 | 三层记忆（Project 表层 + User 表层 + 向量历史），按用户/项目隔离 |
| 项目画像 | 一次性构建，Top10 文件统计 | 每次分析后自动更新，记录项目概述/技术栈/模块/术语 |
| 同义词映射 | 15 个硬编码在代码中 | 数据库存储 + Web UI 管理 + Agent 自动学习 |
| 报告生成 | LLM 直接输出 Markdown | Agent 输出结构化数据 → 模板渲染 |
| 报告回溯 | 无 | 全局对话 + 段落批注 + 版本历史 |
| 工具安全 | 无显式边界 | 项目沙箱 + 零执行 + 零写入（除报告外） |

### 1.3 设计原则

1. **安全优先**: Agent 只能读取其被授权的项目内容，零代码执行，零文件写入（报告除外）
2. **证据驱动**: 每个报告结论必须附带可追溯的证据链
3. **用户可控**: 分析深度可配置，回溯过程用户可介入，画像更新需确认
4. **向后兼容**: 现有 API 和数据库结构尽可能保留，新增功能通过扩展实现。ReAct Agent 先并行运行，对比输出质量，数据支撑后再切换
   - 保留 `Scheduler` + `step_*` 作为 legacy 模式
   - 新增 `AnalysisRunnerV2` 使用 ReAct Agent
   - 配置项 `agent.mode` 控制默认模式（默认 legacy，验证后切换 react）
5. **渐进迭代**: 复杂模块分阶段交付，不追求一次性完美

### 1.4 范围与估算（修订版）

基于专家可行性评审，原 6-9 周估算过于乐观。修订后分三轮，共 **8 周**：

| 轮次 | 内容 | 时间 | 风险 |
|:---|:---|:---|:---|
| **第一轮** | 三层记忆 + 模板系统 + 同义词映射 | 2 周 | 低 |
| **第二轮** | ReAct Agent 核心（max-steps 终止）+ 工具安全沙箱 | 3 周 | 中 |
| **第三轮** | 版本管理 + 单轮全局对话 + 前端 | 3 周 | 中 |

---

## 2. 安全约束（强制）

### 2.1 项目沙箱

- Agent 的所有文件系统操作**仅限于当前分析所属项目的目录**
- 不允许访问项目目录外的任何文件
- 不允许通过路径遍历（`../` 等）突破沙箱
- 项目根目录由系统从 `Project.repo_path` 字段确定，Agent 无法修改

### 2.2 零执行

- Agent **绝对禁止**执行任何代码，包括但不限于：
  - `exec()`, `eval()`, `compile()`
  - `subprocess.run()`, `os.system()`, `os.popen()`
  - 任何动态代码加载或反射执行
- 所有工具函数必须是纯查询函数，无副作用

### 2.3 零写入（报告除外）

- Agent **禁止**修改项目代码、配置文件、Git 仓库
- Agent 的唯一写入操作是：
  1. 生成分析报告（写入 `Report` 表）
  2. 更新项目画像（需用户确认后执行）
  3. 更新用户记忆（用户自己的偏好数据）
- 所有写入操作必须通过显式 API 完成，不可通过工具函数间接写入

### 2.4 网络访问控制

- Agent 的网络访问**仅限于系统提供的工具**
- 系统未提供的网络查询工具，Agent 无权自行发起 HTTP 请求
- 如需外部查询（如 CVE 数据库），必须显式注册为工具，并配置允许的外部域名白名单

### 2.5 Git 只读

- Git 工具仅提供只读查询：
  - 提交历史（`git log`）
  - 文件贡献者（`git blame`）
  - 特定提交的文件内容（`git show`）
- 禁止：commit, push, checkout, merge, rebase 等任何修改操作

### 2.6 敏感文件过滤

- 工具层必须过滤敏感文件，禁止 Agent 读取：
  - `.env`, `.env.*`, `*.key`, `*.pem`, `*.crt`
  - `secrets/`, `credentials/`, `.aws/`, `.ssh/`
  - `config.yaml`, `config.json`（如果包含密钥）
- 敏感文件模式可配置，默认提供上述列表

---

## 3. Agent 架构

### 3.1 核心概念

#### 3.1.1 分析目标（Analysis Goal）

Agent 的单一目标是：
> "基于可用信息，为需求 `[requirement_text]` 生成一份专业、可验证的分析报告，覆盖所有必要维度。"

#### 3.1.2 分析维度（Dimensions）

报告由以下预设维度组成，Agent 必须覆盖所有维度（不可省略），但可自主决定各维度的详细程度：

| 维度 ID | 名称 | 描述 | 最小证据要求 |
|:---|:---|:---|:---|
| `understanding` | 需求理解 | 对需求文本的业务和技术理解 | 需求文本本身 |
| `impact` | 影响域分析 | 识别受影响的模块、文件、接口 | 至少1个代码文件引用 |
| `risk` | 风险评估 | 技术风险、业务风险、合规风险 | 每个风险至少1个依据 |
| `change` | 变更评估 | 具体变更点、影响等级、工作量估算 | 至少1个模块的变更建议 |
| `decision` | 决策建议 | 面向管理层的决策要点 | 至少1个明确建议 |
| `evidence` | 证据支撑 | 支撑所有结论的证据列表 | 覆盖所有其他维度 |
| `verification` | 验证要点 | 评审时需要验证的事项 | 至少3个验证点 |

#### 3.1.3 终止条件（修订版）

Phase 1（Agent 核心）采用**简化的终止机制**：

- **max-steps 硬限制**: Agent 循环达到最大步数即停止
  - **快速** (`quick`): 最大步数 10
  - **标准** (`standard`): 最大步数 15
  - **深度** (`deep`): 最大步数 25
- **LLM 自主判断**: Agent 可在任意步数判断"信息已充分"，主动终止循环
- **用户中断**: WebSocket 发送 cancel 信号，立即停止

**维度充分度评分推迟到后续迭代**：
- 原因：LLM 自评证据充分度不可靠（学术界已有研究表明效果不稳定）；机械评分公式（如"≥3 个风险得 30%"）质量不等于数量
- 替代方案：先上线运行，收集实际数据后，用规则 + 启发式方法校准评分公式
- 保留 `dimension_status` 数据结构，用于追踪各维度状态（pending/sufficient/insufficient），但不作为终止硬约束

#### 3.1.4 证据（Evidence）

证据是 Agent 收集的所有原始信息，每条证据包含：
- `type`: 证据类型（`code`, `history`, `term`, `git`, `requirement`）
- `source`: 来源标识（如 `src/web/app.py:42`, `analysis-123`）
- `content`: 证据内容摘要
- `confidence`: 可信度（`high`, `medium`, `low`）
- `timestamp`: 收集时间

### 3.2 Agent 状态机

Agent 在整个分析过程中维护以下状态：

```
AnalysisAgentState
├── goal: AnalysisGoal
├── requirement_text: str
├── project_id: int
├── user_id: int
├── depth: AnalysisDepth
├── context: AgentContext
│   ├── project_memory: ProjectMemory      # 项目表层记忆
│   ├── user_memory: UserMemory            # 用户表层记忆
│   ├── historical_memory: VectorMemory    # 向量历史记忆
│   ├── evidence_collector: EvidenceCollector  # 证据收集器
│   └── tool_registry: ToolRegistry        # 可用工具
├── dimensions: dict[str, DimensionState]
│   ├── status: "pending" | "in_progress" | "sufficient" | "insufficient"
│   ├── sufficiency_score: float (0-1)
│   ├── evidence_ids: list[str]
│   └── draft_content: any
├── step_count: int
├── max_steps: int
└── final_report: ReportData | None
```

### 3.3 ReAct 循环

Agent 的主循环遵循 ReAct（Reasoning + Acting）模式：

**Step 1: 初始化（Initialization）**
1. 加载需求文本
2. 加载项目表层记忆（`project.md`）
3. 加载用户表层记忆（`user.md`）
4. 检索相似历史分析（向量存储，top_k=5）
5. 初始化各维度状态为 `pending`

**Step 2: 思考（Reasoning）**
1. 评估各维度当前充分度
2. 识别最薄弱的维度
3. 决定下一步需要收集什么信息
4. 选择合适的工具

**Step 3: 行动（Acting）**
1. 调用选定工具
2. 记录新证据到 EvidenceCollector
3. 更新相关维度的状态和充分度

**Step 4: 终止检查（Termination）**
1. 检查是否所有维度达标
2. 检查是否达到最大步数
3. 检查是否收到用户中断信号
4. 任一条件满足则进入生成阶段

**Step 5: 报告生成（Generation）**
1. 基于所有维度的 draft_content 生成 ReportData
2. 确保每个结论都有 evidence 支撑
3. 填充预设模板
4. 保存报告到数据库

**Step 6: 记忆更新（Memory Update）**
1. 分析是否需要更新项目画像
2. 生成画像 diff，标记待确认
3. 记录分析历史到向量存储

### 3.4 工具注册与安全检查

#### 3.4.1 工具接口

每个工具必须实现以下接口：

- `name`: 工具唯一标识
- `description`: 功能描述（用于 Agent 选择）
- `parameters_schema`: JSON Schema 参数定义
- `execute(parameters) -> ToolResult`: 执行函数
- `required_permissions`: 所需权限列表

#### 3.4.2 权限模型

工具注册时声明所需权限，Agent 执行前检查：

| 权限 | 说明 | 拥有者 |
|:---|:---|:---|
| `read:code` | 读取项目代码文件 | 项目成员 |
| `read:git` | 读取 Git 历史 | 项目成员 |
| `read:history` | 读取历史分析报告 | 项目成员 |
| `read:memory` | 读取项目记忆 | 项目成员 |
| `read:user_memory` | 读取用户个人记忆 | 本人 |
| `write:report` | 生成报告 | 项目成员 |
| `write:memory` | 更新记忆（需确认） | 项目管理员 |

#### 3.4.3 工具列表（初始）

| 工具名 | 功能 | 所需权限 |
|:---|:---|:---|
| `search_code` | 搜索代码中的符号/关键词 | `read:code` |
| `read_file` | 读取文件内容（指定行范围） | `read:code` |
| `list_modules` | 列出项目模块列表 | `read:memory` |
| `read_module_summary` | 读取模块职责摘要 | `read:memory` |
| `get_project_profile` | 获取项目画像 | `read:memory` |
| `get_terminology` | 获取项目术语表 | `read:memory` |
| `search_history` | 语义搜索历史分析 | `read:history` |
| `get_dependencies` | 获取模块依赖关系 | `read:code` |
| `get_contributors` | 获取文件贡献者 | `read:git` |
| `get_git_history` | 获取文件变更历史 | `read:git` |

### 3.5 Agent Prompt 模板设计

Agent 在不同阶段使用不同的系统提示词（System Prompt），确保行为符合阶段目标。

#### 3.5.1 自主分析阶段（Analysis Phase）

**目标**: 收集充分证据，填充报告各维度

**Prompt 角色定位**: 
> "你是一位专业的需求分析架构师。你的目标是为给定需求生成一份完整、可验证的分析报告。你需要主动收集信息，评估每个维度的证据充分度，直到所有维度达标。"

**Prompt 必须包含的上下文**:
- 项目表层记忆（project.md 内容）
- 用户表层记忆（user.md 内容，如关注领域、常用纠正）
- 需求文本
- 相似历史分析摘要（top_k=5）
- 当前维度状态和证据收集器内容

**Prompt 行为约束**:
- 优先使用工具获取信息，不要猜测
- 每个结论必须有证据支撑
- 关注用户指定的关注领域（如安全性、性能）
- 达到 max-steps 时停止收集，生成报告

#### 3.5.2 报告回溯阶段（Chatback Phase）

**目标**: 回应用户提问、纠正或深入请求，更新特定维度

**Prompt 角色定位**:
> "你是一位需求分析顾问，正在与用户讨论已生成的分析报告。你的任务是理解用户的意图，基于现有证据回答问题，或在必要时补充新证据。你应当专业、谦逊，承认不确定性。"

**Prompt 必须包含的上下文**:
- 当前报告版本的完整 ReportData
- **当前报告版本绑定的 AnalysisContext 快照**（包含 EvidenceCollector 证据链、维度状态、已访问文件列表、工具调用历史）
- 本轮用户输入
- **不包含**其他报告版本的上下文（版本隔离）

**上下文累积规则**:
- 同一版本内的多轮对话，Agent 可以读取和修改该版本的 AnalysisContext
- 用户第一轮让 Agent 查了文件 A，第二轮可以问"文件 A 中的函数 X 是否需要修改"——Agent 知道文件 A 的内容
- 只有用户保存为新版本时，修改后的上下文才成为新版本的基础

**Prompt 行为约束**:
- 解释型问题：基于版本上下文中的证据回答，引用具体来源
- 纠正型问题：接受用户纠正，标记需要更新的维度
- 深入型问题：判断是否需要新证据，如需则调用工具
- 探索型问题：调用工具获取新信息，追加到版本上下文中
- 不确定时明确说"我不确定"，不要编造

#### 3.5.3 Prompt 管理

- Prompt 模板存储在 `src/reqradar/agent/prompts/` 目录
- 分析阶段和回溯阶段的 Prompt 分别放在不同文件
- Prompt 支持变量插值（如 `{{ project_memory }}`, `{{ requirement_text }}`）
- 未来可考虑支持用户自定义 Prompt（低优先级）

---

## 4. 分层记忆系统

### 4.1 记忆层级

```
记忆系统
├── 表层记忆（Surface Memory）
│   ├── Project Memory: projects/{project_id}/memory/project.md
│   └── User Memory: users/{user_id}/memory/user.md
├── 历史记忆（Historical Memory）
│   └── Vector Store: ChromaDB collection per (project_id, user_id)
└── 运行时记忆（Runtime Memory）
    └── 内存: 当前分析会话的证据链和中间状态
```

### 4.2 Project Memory

#### 4.2.1 存储位置

`{PROJECT_MEMORY_STORAGE_PATH}/{project_id}/project.md`

默认 `PROJECT_MEMORY_STORAGE_PATH` 从配置读取，建议 `.reqradar/memories/`。

#### 4.2.2 文件格式（Markdown）

```markdown
# {项目名称}

## 概述
{项目一句话描述}

## 技术栈
- 语言: {语言列表}
- 框架: {框架列表}
- 数据库: {数据库列表}
- 关键依赖: {依赖列表}

## 模块
### {模块名}
{模块职责描述}

### {模块名}
{模块职责描述}

## 术语
- **{术语}**: {定义} [{领域}]

## 约束
- {约束描述} ({类型})

## 变更日志
- {日期}: {变更描述}
```

#### 4.2.3 更新机制

1. **自动检测**: 每次分析完成后，Agent 判断是否需要更新画像
   - 发现新模块
   - 术语表有新增
   - 技术栈有变化
   - 项目概述有修正
2. **生成 diff**: Agent 生成新旧画像的差异
3. **待确认状态**: diff 标记为 `pending`，不直接写入
4. **用户确认**: Web UI 显示 pending diff，用户可接受/拒绝/修改
5. **写入生效**: 用户确认后写入 `project.md`

#### 4.2.4 与现有记忆的关系

- 现有 `.reqradar/memory/memory.yaml` 作为迁移源
- 首次启动时读取 YAML，转换为 Markdown 格式
- 后续完全使用 Markdown 格式
- YAML 文件保留作为备份，不再更新

### 4.3 User Memory

#### 4.3.1 存储位置

`{USER_MEMORY_STORAGE_PATH}/{user_id}/user.md`

默认 `USER_MEMORY_STORAGE_PATH` 从配置读取，建议 `.reqradar/user_memories/`。

#### 4.3.2 文件格式（Markdown）

```markdown
# 用户偏好

## 常用纠正
- "{业务术语}" → [{代码术语列表}]（来源: 用户纠正 #{分析ID}）

## 关注领域
- {领域名}: {优先级}

## 分析偏好
- 默认分析深度: {quick/standard/deep}
- 报告语言: {zh/en}

## 术语偏好
- "{术语}" 应定义为: "{定义}"
```

#### 4.3.3 自动学习

- Agent 从用户纠正中提取映射关系，记录到 `user.md`
- 用户可在 Web UI 管理自己的偏好
- 用户记忆仅对该用户可见，其他用户无法访问

### 4.4 Historical Memory（向量存储）

#### 4.4.1 隔离策略

- 按 `project_id` 和 `user_id` 组合隔离
- 使用 collection 命名: `history_{project_id}_{user_id}`
- 同一项目的不同用户有独立的向量集合

#### 4.4.2 存储内容

每条历史记录存储为向量文档：
- `id`: `analysis-{task_id}`
- `content`: 需求摘要 + 关键发现 + 风险项的拼接文本
- `metadata`:
  - `task_id`
  - `requirement_path`
  - `risk_level`
  - `created_at`
  - `affected_modules`
  - `key_decisions`

#### 4.4.3 检索策略

- 使用需求文本作为查询
- `top_k` 可配置（默认 5）
- 返回相似历史分析的 metadata，Agent 可决定是否读取完整报告

### 4.5 Runtime Memory

- 仅存在于单次分析会话中
- 包含：已访问文件列表、已确认事实、证据链、维度状态
- 分析结束后丢弃，不持久化

### 4.6 PendingChange 抽象框架（新增）

画像更新和同义词映射确认都遵循"Agent 提议 → 用户确认"的模式。设计一个通用框架避免重复实现：

```python
class PendingChange(Base):
    __tablename__ = "pending_changes"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    change_type: Mapped[str] = mapped_column(String(50))  # "profile" | "synonym" | ...
    target_id: Mapped[str] = mapped_column(String(200))  # 目标标识（如模块名、术语）
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[str] = mapped_column(Text, default="")  # 人类可读的 diff
    source: Mapped[str] = mapped_column(String(50))  # "agent" | "user"
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | accepted | rejected
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
```

**使用场景**:
- 画像更新：Agent 发现新模块 → 生成 PendingChange（type="profile"）→ Web UI 显示待确认列表 → 用户接受/拒绝
- 同义词学习：Agent 从纠正中提取新映射 → 生成 PendingChange（type="synonym"）→ 用户确认后写入 `synonym_mappings` 表

---

## 5. 报告模板与 Agent 填充

### 5.1 模板系统

#### 5.1.1 模板格式

继续使用 Jinja2 模板引擎。模板文件存储在 `src/reqradar/templates/` 目录。

模板由两部分组成：
1. **模板定义**（JSON/YAML）：定义报告结构、每个章节的描述、所需数据字段
2. **模板渲染**（Jinja2）：使用 Agent 生成的 ReportData 渲染最终 Markdown/HTML

#### 5.1.2 模板定义与章节描述

每个报告模板包含一个章节列表，每个章节有明确的描述，指导 Agent 生成该章节内容：

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

**设计要点**:
- `id`: 章节唯一标识，对应 ReportData 中的字段
- `description`: **Agent Prompt 的关键输入**，告诉 Agent 这个章节的目的和受众
- `requirements`: **写作要求**，指导 Agent 生成内容的深度和格式
- `required`: 是否必须生成（false 表示可选，证据不足时可省略）
- `dimensions`: 该章节依赖的分析维度，Agent 必须确保这些维度达标

#### 5.1.3 模板变量（Agent 输出数据结构）

Agent 根据模板定义中的 `sections`，生成对应的结构化数据：

```
ReportData
├── requirement_title: str
├── timestamp: str (ISO 格式)
├── requirement_path: str
├── requirement_understanding: str         # 对应 section: requirement_understanding
├── executive_summary: str                 # 对应 section: executive_summary
├── technical_summary: str                 # 对应 section: technical_summary
├── decision_highlights: list[str]         # 对应 section: decision_summary
├── decision_summary
│   ├── summary: str
│   ├── decisions: list[{topic, decision, rationale, implications}]
│   ├── open_questions: list[str]
│   └── follow_ups: list[str]
├── evidence_items: list[{kind, source, summary, confidence}]  # 对应 section: evidence
├── impact_domains: list[{domain, confidence, basis, inferred}]  # 对应 section: impact_analysis
├── impact_modules: list[{path, symbols, relevance, relevance_reason}]  # 对应 section: impact_analysis
├── change_assessment: list[{module, change_type, impact_level, reason}]  # 对应 section: impact_analysis
├── impact_narrative: str                  # 对应 section: impact_analysis
├── risk_level: str
├── risk_badge: str (由系统根据 risk_level 生成)
├── risks: list[{description, severity, scope, mitigation}]  # 对应 section: risk_assessment
├── risk_narrative: str                    # 对应 section: risk_assessment
├── risk_details: list[str]                # 对应 section: risk_assessment
├── verification_points: list[str]         # 对应 section: decision_summary
├── implementation_suggestion: str         # 对应 section: decision_summary
├── implementation_hints: {approach, effort_estimate, dependencies}  # 对应 section: decision_summary
├── priority: str
├── priority_reason: str
├── terms: list[{term, definition, domain}]  # 对应 section: requirement_understanding / appendix
├── keywords: list[str]
├── constraints: list[str]                 # 对应 section: requirement_understanding
├── structured_constraints: list[{description, constraint_type, source}]  # 对应 section: requirement_understanding
├── contributors: list[{name, role, file, reason}]  # 对应 section: appendix
├── similar_requirements: list             # 对应 section: appendix
├── project_profile: dict                  # 对应 section: appendix
├── warnings: list[str]
├── content_completeness: str
├── evidence_support: str
├── content_confidence: str
└── process_completion: str
```

#### 5.1.3 报告渲染流程

1. Agent 生成 `ReportData`（结构化字典）
2. `ReportRenderer` 加载模板（默认或用户自定义）
3. 模板渲染：`template.render(**report_data)`
4. 同时生成 Markdown 和 HTML 版本
5. 保存到 `Report` 表

### 5.2 自定义模板支持

#### 5.2.1 模板存储格式

每个模板包含两个文件：
- **模板定义**（`*.yaml`）：JSON/YAML 格式的章节定义，包含 `sections` 列表和每个章节的 `description`/`requirements`
- **渲染模板**（`*.j2`）：Jinja2 模板，使用 ReportData 变量渲染最终报告

存储位置：
- 系统模板：`src/reqradar/templates/`（`default_report.yaml` + `default_report.md.j2`）
- 用户自定义模板：数据库 `report_templates` 表（`definition_yaml` + `render_template` 两个字段）
- 项目级模板：可覆盖系统默认

#### 5.2.2 模板管理 API

- `GET /api/report-templates` — 列出可用模板（返回名称、描述、章节列表）
- `GET /api/report-templates/{id}` — 获取模板完整内容（定义 + 渲染模板）
- `POST /api/report-templates` — 创建自定义模板（管理员）
- `PUT /api/report-templates/{id}` — 更新模板
- `DELETE /api/report-templates/{id}` — 删除模板

#### 5.2.3 模板变量约束

自定义模板的渲染模板（Jinja2）只能使用 `ReportData` 中定义的变量。系统提供变量说明文档，帮助用户编写模板。

自定义模板必须提供完整的模板定义（YAML），包含每个章节的 `description` 和 `requirements`，否则 Agent 无法正确生成内容。

### 5.3 Agent 生成 Prompt 中的模板描述注入

Agent 在生成报告内容时，**将模板定义中的 `description` 和 `requirements` 注入到 Prompt 中**，指导 Agent 按章节要求生成内容：

**注入方式**:
```
你正在生成报告的第 X 章：{section.title}

章节描述：{section.description}
写作要求：{section.requirements}
所需维度：{section.dimensions}

请基于以下证据和上下文生成该章节内容：
{相关证据}
```

**好处**:
- Agent 明确知道每个章节的目的和受众
- 自定义模板时，用户只需修改 `description` 和 `requirements`，Agent 行为自动适配
- 不同模板（如"技术评审模板"vs"产品评审模板"）的同一章节可以有不同的生成策略

### 5.4 报告质量要求

#### 5.4.1 写作标准

Agent 必须遵守模板定义中每个章节的 `requirements` 字段：

| 章节 | 字数要求 | 深度要求 |
|:---|:---|:---|
| 需求理解 | 150-200 字 | 包含背景、核心问题、成功标准 |
| 执行摘要 | 120-180 字 | 结论先行，基于证据，避免技术细节 |
| 技术概述 | 120-180 字 | 概括影响域、风险和实施路径 |
| 影响分析 | 灵活 | 必须包含影响域列表、代码命中、变更评估 |
| 风险评估 | 灵活 | 每个风险必须有代码依据和缓解建议 |
| 决策建议 | 灵活 | 必须包含优先级、实施方向、验证要点 |
| 证据支撑 | 灵活 | 覆盖所有其他章节的结论 |

#### 5.4.2 证据引用

- 每个影响模块必须引用至少一个代码文件
- 每个风险项必须引用至少一个代码依据或历史案例
- 每个变更评估必须引用具体类/方法名
- 证据引用格式：`文件路径:行号` 或 `分析ID:维度`

#### 5.4.3 量化指标

报告应尽可能包含量化信息：
- 影响文件数
- 预计改动行数范围
- 风险概率（高/中/低 → 对应百分比范围）
- 工作量估算（人天）

---

## 6. 报告回溯

### 6.1 版本管理

#### 6.1.1 版本模型

每次报告调整生成一个新版本：

```
ReportVersion
├── id: int
├── task_id: int (关联 AnalysisTask)
├── version_number: int (从 1 开始递增)
├── report_data: JSON (ReportData 完整快照)
├── content_markdown: str
├── content_html: str
├── trigger_type: "initial" | "global_chat" | "section_annotation" | "manual_edit"
├── trigger_description: str (触发原因描述)
├── created_at: datetime
└── created_by: int (用户 ID)
```

#### 6.1.2 版本历史 API

- `GET /api/analyses/{task_id}/reports/versions` — 获取版本列表
- `GET /api/analyses/{task_id}/reports/versions/{version}` — 获取特定版本
- `POST /api/analyses/{task_id}/reports/rollback` — 回滚到指定版本

### 6.2 全局对话回溯

#### 6.2.1 交互形式

报告页面底部提供聊天输入框，支持**多轮对话**。

**核心设计**:
- **版本绑定上下文**: 每个报告版本绑定一个完整的 `AnalysisContext`（包含证据链、维度状态、已访问文件等）。对话围绕当前报告版本的上下文进行，同一版本内的多轮对话共享该上下文
- **持续探索**: 用户可要求 Agent 去查新信息（如"去看看 web/models.py 的变更历史"），Agent 会调用工具获取新证据，更新该版本的上下文和报告预览
- **显式保存**: 用户决定何时将当前探索结果保存为新版本。保存时，当前上下文快照成为新版本的基础

用户输入示例:
- 提问："为什么风险评估是中而不是高？"
- 纠正："影响模块遗漏了 web/models.py，需要补充"
- 深入："请详细分析对数据库的影响"
- 探索："去看看最近谁在修改 auth 模块"

#### 6.2.2 多轮对话流程

**版本内对话（未保存前）**:
1. 用户输入消息
2. 系统加载**当前报告版本绑定的 AnalysisContext**（包括 ReportData、EvidenceCollector、维度状态、已访问文件列表）
3. Agent 分析用户意图：
   - **解释型**: 基于版本上下文中的证据回答，引用具体来源
   - **纠正型**: 更新特定维度，触发增量分析
   - **深入型**: 在版本上下文基础上补充新证据，触发增量分析
   - **探索型**: 调用工具获取新信息，更新版本上下文
4. Agent 生成回复和更新后的报告预览（此时未保存，只是预览）
5. 用户选择：
   - **继续对话**: 在当前版本上下文基础上继续下一轮（上下文累积）
   - **保存为新版本**: 将当前上下文快照和 ReportData 写入 `report_versions` 表，version_number 递增。新版本绑定新的上下文快照
   - **丢弃**: 放弃本轮及本轮之前的所有未保存变更，回退到进入对话前的版本状态

**版本切换**:
- 用户可切换到历史版本进行对话
- 切换后，对话基于该历史版本的上下文快照开始
- 修改后可保存为新版本（从该历史版本分叉）

**关键约束**:
- 每个报告版本有且仅有一个绑定的 `AnalysisContext` 快照
- 保存新版本时，原版本上下文不变（不可变）
- 对话过程中，当前上下文是可变的（探索状态），直到用户保存或丢弃

```
ReportChat
├── id: int
├── task_id: int
├── session_id: str (会话标识，UUID)
├── round_number: int (会话内的轮次编号，从1开始)
├── role: "user" | "agent"
├── content: str
├── intent_type: "explain" | "correct" | "deepen" | "explore" | "other"
├── evidence_refs: list[str] (Agent 回复引用的证据)
├── applied: bool (本轮是否被保存为新版本)
├── version_before: int | None (保存前的版本号)
├── version_after: int | None (保存后的版本号，未保存为null)
├── created_at: datetime
```

### 6.3 段落批注回溯

#### 6.3.1 交互形式

每个报告章节右侧显示批注图标，用户可以：
- 点击批注 → 输入批注内容
- 批注内容聚焦到特定维度

#### 6.3.2 批注处理（单轮独立 + 显式保存）

1. 用户在某章节添加批注
2. 系统识别该批注关联的维度（如"风险评估"章节的批注关联 `risk` 维度）
3. Agent 针对该维度重新分析：
   - 读取当前报告版本的已有证据
   - 根据批注内容判断是否需要新证据
   - 如需新证据：调用工具（如 `read_file`, `get_git_history`）
   - 更新该维度的 `draft_content`
4. 重新生成报告预览（仅受影响章节变化，其他章节保持不变）
5. 用户选择：
   - **接受并保存**: 写入新版本
   - **拒绝**: 批注记录保留但报告不变
   - **修改批注**: 用户修改批注内容，Agent 重新分析

**约束**:
- 批注处理不加载其他批注或对话轮次的历史
- 每个批注独立处理，避免维度间的相互干扰

#### 6.3.3 批注记录

```
ReportAnnotation
├── id: int
├── task_id: int
├── dimension: str (关联维度)
├── section_title: str (章节标题)
├── user_comment: str
├── agent_response: str
├── applied: bool (是否被采纳)
├── version_before: int
├── version_after: int | None
├── created_at: datetime
```

### 6.4 证据链追溯

#### 6.4.1 证据展示

每个结论支持点击"查看证据"，显示：
- 该结论依赖的所有证据列表
- 每条证据的来源、内容摘要、可信度
- 支持跳转到具体代码文件（如果来源是代码）

#### 6.4.2 证据链 API

- `GET /api/analyses/{task_id}/evidence` — 获取完整证据链
- `GET /api/analyses/{task_id}/evidence/{evidence_id}` — 获取单条证据详情

---

## 7. 同义词映射配置化

### 7.1 数据模型

#### 7.1.1 数据库表

```sql
synonym_mappings
├── id: int PK
├── project_id: int FK (NULL = 全局默认)
├── business_term: str
├── code_terms: JSON (代码术语列表)
├── priority: int (匹配优先级，默认 100)
├── source: "system" | "user" | "agent_learned"
├── created_by: int FK (用户 ID, system 为 NULL)
├── created_at: datetime
└── updated_at: datetime
```

#### 7.1.2 约束

- `(project_id, business_term)` 唯一索引
- `code_terms` 至少包含1个元素
- `priority` 范围 1-1000，越小优先级越高

### 7.2 映射解析流程

1. Agent 提取关键词
2. 查询 `synonym_mappings` 表：
   - 先查 `project_id = 当前项目` 的映射
   - 再查 `project_id IS NULL` 的全局映射
3. 按 `priority` 排序合并
4. 去重后返回扩展关键词列表

### 7.3 自动学习

#### 7.3.1 学习触发条件

当用户在报告回溯中纠正 Agent 时：
- 用户指出某关键词的映射不准确
- Agent 提取纠正信息
- 生成新的映射条目，标记为 `agent_learned`
- 存入 `synonym_mappings` 表，等待用户确认

#### 7.3.2 确认机制

- `agent_learned` 的映射初始状态为 `pending`
- Web UI 显示待确认的映射列表
- 用户可接受、拒绝或修改
- 用户接受后状态变为 `active`

### 7.4 Web UI

项目设置页提供同义词管理：
- 表格展示当前项目的所有映射
- 支持新增、编辑、删除
- 显示来源标识（系统/用户/Agent学习）
- 导入/导出功能（支持 JSON/CSV）

---

## 8. 数据模型变更

### 8.1 新增表

#### 8.1.1 `report_versions`

```python
class ReportVersion(Base):
    __tablename__ = "report_versions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"))
    version_number: Mapped[int] = mapped_column(default=1)
    report_data: Mapped[str] = mapped_column(Text, default="{}")  # JSON: ReportData
    context_snapshot: Mapped[str] = mapped_column(Text, default="{}")  # JSON: 轻量上下文快照（evidence_list + dimension_status + visited_files）
    content_markdown: Mapped[str] = mapped_column(Text)
    content_html: Mapped[str] = mapped_column(Text, default="")
    trigger_type: Mapped[str] = mapped_column(String(50), default="initial")
    trigger_description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
```

**说明**:
- `context_snapshot` 存储**轻量上下文**，只包含：
  - `evidence_list`: 证据列表（id, type, source, content, confidence）
  - `dimension_status`: 各维度状态（pending/sufficient/insufficient）
  - `visited_files`: 已访问文件列表
  - `tool_calls`: 工具调用历史（工具名、参数、结果摘要）
- **不存储**完整的 Pydantic 模型、Path 对象、datetime 等（避免序列化膨胀和恢复复杂度）
- 回溯对话时，系统从 `context_snapshot` 重建最小可运行上下文，用户探索产生的新证据追加到 evidence_list
- 保存新版本时，将当前轻量上下文序列化为新的 `context_snapshot`
- **版本数量上限**: 每个 task 最多保留 10 个版本，超出时自动删除最旧的版本

#### 8.1.2 `report_chats`

```python
class ReportChat(Base):
    __tablename__ = "report_chats"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"))
    version_number: Mapped[int] = mapped_column(default=1)
    role: Mapped[str] = mapped_column(String(20))  # user | agent
    content: Mapped[str] = mapped_column(Text)
    evidence_refs: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
```

#### 8.1.3 `report_annotations`

```python
class ReportAnnotation(Base):
    __tablename__ = "report_annotations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"))
    dimension: Mapped[str] = mapped_column(String(50))
    section_title: Mapped[str] = mapped_column(String(200))
    user_comment: Mapped[str] = mapped_column(Text)
    agent_response: Mapped[str] = mapped_column(Text, default="")
    applied: Mapped[bool] = mapped_column(default=False)
    version_before: Mapped[int] = mapped_column(default=1)
    version_after: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
```

#### 8.1.4 `synonym_mappings`

```python
class SynonymMapping(Base):
    __tablename__ = "synonym_mappings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    business_term: Mapped[str] = mapped_column(String(200))
    code_terms: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    priority: Mapped[int] = mapped_column(default=100)
    source: Mapped[str] = mapped_column(String(50), default="user")  # system | user | agent_learned
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
```

#### 8.1.5 `report_templates`

```python
class ReportTemplate(Base):
    __tablename__ = "report_templates"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    definition: Mapped[str] = mapped_column(Text)  # YAML: 章节定义（含 description/requirements）
    render_template: Mapped[str] = mapped_column(Text)  # Jinja2: 渲染模板
    is_default: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
```

**说明**:
- `definition`: YAML 格式的模板定义，包含 `sections` 列表和每个章节的 `description`/`requirements`/`required`/`dimensions`
- `render_template`: Jinja2 模板字符串，使用 ReportData 变量渲染最终报告
- Agent 使用 `definition` 指导内容生成，ReportRenderer 使用 `render_template` 渲染输出

### 8.2 修改现有表

#### 8.2.1 `analysis_tasks`

新增字段：
- `current_version: Mapped[int] = mapped_column(default=1)` — 当前报告版本号
- `depth: Mapped[str] = mapped_column(String(20), default="standard")` — 分析深度配置

#### 8.2.2 `projects`

新增字段：
- `default_template_id: Mapped[int | None] = mapped_column(ForeignKey("report_templates.id"), nullable=True)` — 项目默认报告模板

### 8.3 废弃字段

- `Report.content_markdown` 和 `Report.content_html` — 改为从 `report_versions` 表的最新版本读取
- 保留 `Report` 表作为版本表的关联入口，但内容字段标记为废弃

---

## 9. API 接口定义

### 9.1 报告回溯 API

#### 9.1.1 全局对话

```
POST /api/analyses/{task_id}/chat
Request:
{
    "message": "为什么风险评估是中而不是高？"
}
Response:
{
    "reply": "根据代码分析...",
    "updated": true,
    "new_version": 2,
    "report_preview": "..."
}
```

#### 9.1.2 获取对话历史

```
GET /api/analyses/{task_id}/chat
Response:
{
    "messages": [
        {"role": "user", "content": "...", "created_at": "..."},
        {"role": "agent", "content": "...", "evidence_refs": [...], "created_at": "..."}
    ]
}
```

#### 9.1.3 段落批注

```
POST /api/analyses/{task_id}/annotations
Request:
{
    "dimension": "risk",
    "section_title": "风险评估",
    "comment": "遗漏了数据库锁竞争风险"
}
Response:
{
    "id": 1,
    "agent_response": "已补充数据库锁竞争风险...",
    "new_version": 3,
    "status": "applied"
}
```

#### 9.1.4 获取批注列表

```
GET /api/analyses/{task_id}/annotations
Response:
{
    "annotations": [
        {
            "id": 1,
            "dimension": "risk",
            "section_title": "风险评估",
            "user_comment": "...",
            "agent_response": "...",
            "applied": true,
            "version_before": 2,
            "version_after": 3
        }
    ]
}
```

### 9.2 版本管理 API

#### 9.2.1 获取版本列表

```
GET /api/analyses/{task_id}/reports/versions
Response:
{
    "versions": [
        {"version_number": 1, "trigger_type": "initial", "created_at": "..."},
        {"version_number": 2, "trigger_type": "global_chat", "created_at": "..."}
    ]
}
```

#### 9.2.2 获取特定版本

```
GET /api/analyses/{task_id}/reports/versions/{version}
Response:
{
    "version_number": 2,
    "content_markdown": "...",
    "content_html": "...",
    "report_data": {...},
    "trigger_type": "global_chat",
    "trigger_description": "用户纠正影响模块",
    "created_at": "..."
}
```

#### 9.2.3 回滚版本

```
POST /api/analyses/{task_id}/reports/rollback
Request:
{
    "version_number": 1
}
Response:
{
    "success": true,
    "current_version": 1
}
```

### 9.3 证据链 API

#### 9.3.1 获取证据链

```
GET /api/analyses/{task_id}/evidence
Response:
{
    "evidence": [
        {
            "id": "ev-001",
            "type": "code",
            "source": "src/web/app.py:42",
            "content": "...",
            "confidence": "high",
            "dimensions": ["impact", "change"],
            "timestamp": "..."
        }
    ]
}
```

### 9.4 同义词映射 API

#### 9.4.1 获取映射列表

```
GET /api/projects/{project_id}/synonym-mappings
Query: ?source=user&search=配置
Response:
{
    "mappings": [
        {
            "id": 1,
            "business_term": "配置",
            "code_terms": ["config", "settings"],
            "priority": 100,
            "source": "user"
        }
    ]
}
```

#### 9.4.2 创建映射

```
POST /api/projects/{project_id}/synonym-mappings
Request:
{
    "business_term": "配置",
    "code_terms": ["config", "settings", "conf"],
    "priority": 50
}
```

#### 9.4.3 更新映射

```
PUT /api/projects/{project_id}/synonym-mappings/{id}
Request:
{
    "code_terms": ["config", "settings"],
    "priority": 50
}
```

#### 9.4.4 删除映射

```
DELETE /api/projects/{project_id}/synonym-mappings/{id}
```

#### 9.4.5 批量导入

```
POST /api/projects/{project_id}/synonym-mappings/import
Content-Type: multipart/form-data
File: mappings.json
Response:
{
    "imported": 10,
    "skipped": 2,
    "errors": []
}
```

### 9.5 项目画像 API

#### 9.5.1 获取画像

```
GET /api/projects/{project_id}/profile
Response:
{
    "content": "# 项目名称\n\n## 概述\n...",
    "parsed": {
        "overview": "...",
        "tech_stack": {"languages": [...], ...},
        "modules": [...],
        "terms": [...],
        "constraints": [...]
    }
}
```

#### 9.5.2 获取待确认变更

```
GET /api/projects/{project_id}/profile/pending
Response:
{
    "pending_changes": [
        {
            "id": "change-001",
            "type": "add_module",
            "module_name": "new_module",
            "description": "Agent 发现新模块",
            "diff": "+ ### new_module\n+ ..."
        }
    ]
}
```

#### 9.5.3 确认/拒绝变更

```
POST /api/projects/{project_id}/profile/pending/{change_id}
Request:
{
    "action": "accept" | "reject",
    "modified_content": "..."  # 可选，用户修改后的内容
}
```

### 9.6 报告模板 API

#### 9.6.1 获取模板列表

```
GET /api/report-templates
Response:
{
    "templates": [
        {"id": 1, "name": "默认模板", "is_default": true},
        {"id": 2, "name": "简洁模板", "is_default": false}
    ]
}
```

#### 9.6.2 获取模板内容

```
GET /api/report-templates/{id}
Response:
{
    "id": 1,
    "name": "默认模板",
    "content": "# 需求分析报告...",
    "variables": ["requirement_title", "executive_summary", ...]
}
```

#### 9.6.3 创建模板

```
POST /api/report-templates
Request:
{
    "name": "自定义模板",
    "description": "...",
    "content": "# {{ requirement_title }}\n..."
}
```

---

## 10. 配置项

### 10.1 新增系统配置

| 配置键 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `agent.max_steps` | int | 15 | Agent 最大步数（标准深度） |
| `agent.max_steps_quick` | int | 10 | 快速分析最大步数 |
| `agent.max_steps_deep` | int | 25 | 深度分析最大步数 |
| `agent.mode` | str | "legacy" | 分析模式：legacy（固定流水线）/ react（ReAct Agent）|
| `agent.version_limit` | int | 10 | 每个 task 最大保留版本数 |
| `memory.project_storage_path` | str | ".reqradar/memories" | 项目记忆存储路径 |
| `memory.user_storage_path` | str | ".reqradar/user_memories" | 用户记忆存储路径 |
| `security.sensitive_file_patterns` | list[str] | [".env", "*.key", ...] | 敏感文件过滤模式 |
| `reporting.default_template_id` | int | 1 | 默认报告模板 ID |

### 10.2 项目级配置

| 配置键 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `project.default_depth` | str | "standard" | 项目默认分析深度 |
| `project.default_template_id` | int | None | 项目默认报告模板 |
| `project.synonym_mappings` | list | [] | 项目级同义词映射 |

---

## 11. 前端改造

### 11.1 新增页面

#### 11.1.1 报告回溯页面（改造现有 ReportView）

布局：
- 左侧：报告渲染区（支持章节级批注按钮）
- 右侧：证据面板（可折叠，显示当前章节的证据）
- 底部：全局对话区（聊天输入框 + 历史消息）
- 顶部：版本选择器（下拉选择历史版本，显示当前版本）

功能：
- 点击章节批注图标 → 弹出批注输入框 → 提交后显示 Agent 回复和更新预览
- 版本切换时显示 diff 高亮
- 证据面板点击跳转到代码文件（如有源码权限）

#### 11.1.2 项目画像管理页（新增）

路径：`/projects/{id}/profile`

布局：
- 上半部分：Markdown 编辑器（显示当前 project.md）
- 下半部分：待确认变更列表（卡片式，显示 diff）
- 操作：保存、预览、接受/拒绝变更

#### 11.1.3 同义词管理页（新增）

路径：`/projects/{id}/synonyms`

布局：
- 表格：业务术语 | 代码术语 | 优先级 | 来源 | 操作
- 操作：新增、编辑、删除、导入、导出
- 搜索框：按业务术语或代码术语过滤

#### 11.1.4 报告模板管理页（新增）

路径：`/settings/templates`（管理员）

布局：
- 模板列表（名称、是否默认、创建时间）
- 模板编辑器（ Monaco Editor 或 CodeMirror，支持 Jinja2 语法高亮）
- 变量参考面板（列出可用变量及说明）
- 预览功能（使用模拟数据渲染预览）

#### 11.1.5 用户偏好设置页（新增）

路径：`/settings/preferences`

布局：
- 默认分析深度（快速/标准/深度）
- 报告语言偏好
- 关注领域（多选：安全性、性能、兼容性等）
- 用户记忆预览（只读，显示 user.md 内容）

### 11.2 改造页面

#### 11.2.1 分析提交页（改造 AnalysisSubmit）

新增：
- 分析深度选择器（快速/标准/深度）
- 报告模板选择器（项目默认或自定义）
- 关注领域多选（影响 Agent 的维度权重）

#### 11.2.2 分析进度页（改造 AnalysisProgress）

新增：
- 显示 Agent 当前正在分析的维度
- 显示已收集的证据数量
- 显示维度充分度进度条
- 支持"停止并生成当前报告"按钮

#### 11.2.3 项目列表页（改造 Projects）

新增：
- 项目卡片显示画像状态（是否已构建、最后更新时间）
- 一键"更新画像"按钮

### 11.3 WebSocket 消息扩展

新增消息类型：
- `agent_thinking`: Agent 正在思考下一步
- `agent_action`: Agent 执行了某个工具（显示工具名和参数摘要）
- `dimension_progress`: 维度充分度更新
- `evidence_collected`: 新证据收集通知
- `report_version`: 新版本报告生成完成

---

## 12. 分阶段实施计划（修订版）

基于专家可行性评审，实施顺序调整为**先独立模块、后核心改造、最后回溯系统**，共 **8 周**。

### 第一轮：记忆 + 模板 + 同义词（2 周）

**目标**: 完成独立性最强的三个模块，不改核心控制流

**任务**:
1. **三层记忆系统**
   - 设计 `ProjectMemory` / `UserMemory` / `VectorMemory` 接口
   - 实现 Markdown 格式的 project.md / user.md 读写
   - 实现向量存储按 (project_id, user_id) 隔离
   - 实现画像自动检测和 diff 生成
   - 实现画像管理 API
   - 迁移现有 YAML 记忆到 Markdown
2. **报告模板系统**
   - 设计模板定义 YAML 格式（含章节 description/requirements）
   - 实现模板定义与 Jinja2 渲染分离
   - 实现 `ReportTemplate` 数据库表和 API
   - 改造 `ReportRenderer` 支持模板选择
3. **同义词映射**
   - 设计 `synonym_mappings` 数据库表
   - 实现映射解析流程（项目级 → 全局级）
   - 实现同义词管理 API
   - 实现自动学习（从用户纠正提取映射）
   - 设计 `PendingChangeManager` 抽象（画像更新和同义词确认共用）

**验收标准**:
- project.md 和 user.md 能正确读写
- 向量存储按项目+用户隔离
- 报告能按模板定义生成
- 同义词映射 API 完整
- 所有现有测试通过

### 第二轮：Agent 核心改造（3 周）

**目标**: 将 tool_use_loop 升级为完整 ReAct 循环，保留旧流水线作为 legacy 模式

**任务**:
1. **Agent 核心**
   - 设计 `AnalysisAgent` 核心类和状态机
   - 实现 `EvidenceCollector` 证据收集器
   - 实现 `DimensionState` 维度状态追踪（不含评分）
   - 实现 ReAct 主循环（Thought-Action-Observation）
   - 终止条件：max-steps 硬限制 + LLM 自主判断
2. **工具层安全**
   - 改造工具注册：添加 `required_permissions` 声明
   - 实现工具执行前权限检查
   - 实现路径遍历防护和敏感文件过滤
   - 确保 Git 工具只读
3. **报告生成适配**
   - 改造报告生成：Agent 输出 ReportData → 模板渲染
   - 实现 Prompt 模板注入（章节 description/requirements 注入 Agent Prompt）
4. **向后兼容**
   - 保留现有 `Scheduler` 和 `step_*` 函数作为 legacy 模式
   - 新增 `AnalysisRunnerV2` 使用 ReAct Agent
   - 配置开关选择分析模式（legacy / react）
   - 并行运行对比，收集数据后再切换默认

**验收标准**:
- Agent 能自主选择工具顺序
- max-steps 达到时正确终止
- 报告通过模板渲染生成
- 工具权限检查生效
- legacy 模式仍可运行
- 所有现有测试通过

### 第三轮：报告回溯 + 前端（3 周）

**目标**: 实现版本管理和单轮全局对话，段落批注推迟

**任务**:
1. **版本管理（简化版）**
   - 设计 `ReportVersion` 数据模型（轻量 context_snapshot）
   - 实现版本管理 API（列表、获取、回滚）
   - 实现版本数量上限（10 个）和自动清理
2. **全局对话（单轮先行）**
   - 实现单轮对话：用户输入 → Agent 回复 + 预览 → 用户保存/丢弃
   - 版本内上下文累积：同一版本内多轮对话共享 context
   - 显式保存机制
3. **前端改造**
   - 改造 ReportView：版本选择器 + 单轮对话输入框
   - 新建项目画像管理页（Markdown 编辑器 + pending diff）
   - 新建同义词管理页
   - 新建报告模板管理页（简化版，无 Monaco）
   - 新建用户偏好设置页
   - 改造 AnalysisSubmit（深度选择 + 模板选择）
4. **推迟到后续迭代**
   - 段落批注（需要增量更新技术）
   - 多轮对话流式传输
   - 证据面板实时更新

**验收标准**:
- 能查看版本历史并回滚
- 单轮对话能触发报告更新
- 版本数量上限生效
- 所有新页面可用
- WebSocket 实时更新正常

---

## 13. 风险评估与缓解

| 风险 | 影响 | 缓解措施 |
|:---|:---|:---|
| Agent 循环失控（无限循环） | 高 | max_steps 硬限制 + 用户可中断 + 成本预算控制 |
| Agent 幻觉（编造不存在的代码） | 高 | 证据链强制引用 + 代码引用可验证 + 用户回溯纠正 |
| 项目画像漂移（自动更新导致信息错误） | 中 | pending 机制 + 用户确认 + 版本历史可回滚 |
| 向量存储膨胀 | 中 | 定期清理旧历史 + 可配置保留策略 |
| 安全沙箱突破 | 高 | 路径遍历防护 + 敏感文件过滤 + 代码审计 |
| 性能下降（Agent 循环比流水线慢） | 中 | 异步执行 + 缓存 + 可选快速模式 |

---

## 14. 专家评审与修订记录

### 14.1 评审摘要

**评审日期**: 2026-04-23
**评审类型**: 外部专家可行性评审
**评审结论**: 方向正确，但范围过大，时间估算不现实。建议分三轮渐进式改造。

### 14.2 采纳的修订

| 建议 | 采纳情况 | 修订位置 |
|:---|:---|:---|
| 维度充分度评分不可靠，推迟到后续迭代 | ✅ 采纳 | 3.1.3 终止条件（修订版） |
| Phase 1 先用 max-steps 硬限制 + LLM 自主判断 | ✅ 采纳 | 3.1.3 终止条件（修订版） |
| context_snapshot 轻量化，只存证据列表+维度状态+已访问文件 | ✅ 采纳 | 8.1.1 `report_versions` |
| 版本数量设上限（10个），超出自动清理 | ✅ 采纳 | 8.1.1 `report_versions` |
| 实施顺序调整：先记忆/模板/同义词 → Agent核心 → 回溯/前端 | ✅ 采纳 | 12. 分阶段实施计划（修订版） |
| PendingChange 抽象框架（画像更新和同义词确认共用） | ✅ 采纳 | 4.6 PendingChange 抽象框架 |
| 向后兼容：保留 legacy 模式，配置开关切换 | ✅ 采纳 | 1.3 设计原则、第二轮任务 |
| 报告回溯简化：单轮对话先行，段落批注推迟 | ✅ 采纳 | 第三轮任务 |
| 时间估算校准：6-9周 → 8周（2+3+3） | ✅ 采纳 | 1.4 范围与估算（修订版） |
| 删除 sufficiency_threshold 配置项 | ✅ 采纳 | 10.1 新增系统配置 |

### 14.3 未采纳/保留的建议

| 建议 | 处理 | 原因 |
|:---|:---|:---|
| context_snapshot 改为只存储 evidence_ids，不存内容 | ❌ 保留原设计 | 需要证据内容才能恢复上下文 |
| 完全删除维度充分度概念 | ❌ 保留数据结构 | 用于追踪维度状态（pending/sufficient），只是不作为终止条件 |

---

## 15. 附录

### 15.1 术语表

| 术语 | 定义 |
|:---|:---|
| ReAct | Reasoning + Acting，一种让 LLM 通过思考-行动-观察循环解决任务的范式 |
| 维度充分度 | 某个报告维度所需证据的满足程度，0-100%（Phase 1 仅追踪，不用于终止） |
| 表层记忆 | 以 Markdown 文件存储的人类可读项目知识 |
| 历史记忆 | 以向量嵌入存储的语义化历史分析记录 |
| 证据链 | 支撑报告结论的所有原始信息及其来源的可追溯链路 |
| 增量分析 | 在已有分析基础上，仅针对特定维度补充新信息的分析模式 |

### 15.2 相关文档

- `docs/requirements/config-system-refactor.md` — 配置系统重构需求
- `docs/issues/` — 已知问题记录
- `.opencode/plans/2026-04-23-config-system-design.md` — 配置系统设计文档

---

*文档版本: v1.1（已采纳专家评审修订）*