# ReqRadar V2 — 项目认知资产模型

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.1 |
| 文档定位 | 项目认知资产的分层模型、数据契约与知识治理框架 |
| 前置文档 | 00_PROJECT_POSITIONING.md（项目宪法）、01_RESTRUCTURE_OVERVIEW.md（Runtime 蓝图）、02_SYSTEM_ARCHITECTURE.md（总体架构设计） |
| 核心目标 | 定义 ReqRadar 如何将原始上下文逐步提炼为可持续积累、可主动赋能、可治理演化的组织认知资产 |
| 文档职责 | 为 M-01~M-04、R-01~R-05、I-01~I-03 等详细设计文档提供统一的数据契约和设计基线 |

---

## 一、核心命题

ReqRadar 的核心价值主张是 **"让组织不再失忆"** 。这提出了一个必须回答的工程问题：

> 如何将一次性的、原始的项目材料（需求文档、代码、Git 历史）转化为**可持续积累、可跨会话复用、可主动赋能后续分析、且不会随时间腐化**的组织认知资产？

本模型定义了四个递进的加工层次，以及确保这份资产长期健康的**知识治理框架**。

---

## 二、四层认知资产模型

原始上下文本身没有长期价值——PDF 会被遗忘，代码会迭代，Git 日志会沉没。真正的资产是**从原始材料中提炼出来的、持续演化的工程知识**。

ReqRadar 采用四层递进模型：

```
┌────────────────────────────────────────────────────────────┐
│  L3: Persistent Knowledge   持久化知识（可演化、持续积累）    │
│  "活的认知大脑"——越用越聪明，但需要新陈代谢                │
├────────────────────────────────────────────────────────────┤
│  L2: Analysis Records       分析记录（可追溯、可回放）      │
│  "实验记录本"——每一次推理都有据可查                       │
├────────────────────────────────────────────────────────────┤
│  L1: Structured Facts       结构化事实（可索引、可检索）    │
│  "图书馆"——原材料被组织成可查询的事实                     │
├────────────────────────────────────────────────────────────┤
│  L0: Raw Context             原始上下文（不可变）           │
│  "档案馆"——一切分析的最终证据来源                         │
└────────────────────────────────────────────────────────────┘
```

| 层级 | 定位 | 核心问题 | 不可变性 | 存储策略 |
|------|------|---------|---------|---------|
| **L0** | 档案馆 | 原始材料是什么？ | **不可变** | MinIO（文件）+ PG（元数据指针） |
| **L1** | 图书馆 | 材料中有哪些可检索的事实？ | 随代码更新而刷新 | PG（结构化元数据）+ ChromaDB（向量）+ MinIO（大文本） |
| **L2** | 实验记录本 | 某次分析发现了什么？怎么发现的？ | **追加不可改** | PG JSONB（Checkpoint/Evidence）+ Redis Streams（Event） |
| **L3** | 认知大脑 | 关于这个项目，系统积累了什么持久化知识？ | **追加演化**（append-only） | PG（结构化知识）+ ChromaDB（语义检索）+ 接口层预留 Graph |

---

## 三、L0：Raw Context（原始上下文）— 不可变的"档案馆"

### 3.1 职责定义

L0 是 ReqRadar 的**最终证据来源**。它保证系统输出的任何结论，都能追溯到不可篡改的原始材料。

**L0 不是工作区，是档案馆。** 它只做两件事：存，和提供引用。

### 3.2 存储内容

| 数据类型 | 说明 | 典型大小 |
|---------|------|---------|
| 需求文档 | PDF、DOCX、MD、PPTX、XLSX、HTML 等原始文件 | 100KB-50MB |
| 代码仓库快照 | 特定分析时刻的完整代码副本 | 1MB-500MB |
| Git 历史 | commit 记录、diff、blame 信息 | 1MB-100MB |
| 用户上传的其他文件 | 架构图、白皮书、会议纪要等 | 不定 |

### 3.3 存储策略

| 属性 | 决策 |
|------|------|
| 文件存储 | **MinIO**（S3 兼容对象存储），路径格式：`projects/{project_id}/l0/{type}/{upload_timestamp}/{original_filename}` |
| 元数据指针 | **PostgreSQL**，`raw_context` 表：`id`、`project_id`、`type`、`uri`、`size_bytes`、`source`（upload/cli/mcp）、`ingested_at`、`content_hash` |
| 不可变性 | **写入后不可修改、不可删除**。可标记为 `superseded_by`，指向更新的版本 |

### 3.4 使用方式

- **L1 摄取的输入源**：ingestion-service 从 L0 读取文件，解析并结构化后写入 L1
- **Evidence 的最终引用**：当 Evidence 引用某段需求原文时，引用格式为 `l0://{raw_context_id}?offset=start&length=n`
- **重新分析的基石**：当新的分析策略或更强的模型可用时，从 L0 重新摄取，无需用户重新上传

### 3.5 关键约束

- L0 不参与语义检索。检索需求由 L1（向量索引）满足。
- L0 的内容不直接注入 LLM 上下文。必须经过 L1 结构化后才能进入 Context Pipeline。
- L0 的文件不修改。文件内容变更视为新版本，追加新记录。

---

## 四、L1：Structured Facts（结构化事实）— 可索引的"图书馆"

### 4.1 职责定义

L1 是 L0 的**可检索表示层**。它将原始文件转化为结构化的、可被查询的事实。

**L1 不是书堆，是图书馆。** 每一条事实都有明确的来源、位置和类型。

### 4.2 存储内容

| 事实类型 | 内容 | 提取方式 |
|---------|------|---------|
| **文档 Chunk** | 需求文档按段落/章节切分后的文本片段，附带位置信息和来源引用 | ingestion-service 多格式 Loader + LLM 结构化整合 |
| **代码模块** | 模块/类/函数的定义、位置、签名 | code_parser（AST 解析） |
| **代码依赖** | import 图、调用图、继承关系 | code_parser + git_analyzer |
| **Git 提交事实** | 每次 commit 的 author、timestamp、message、changed_files、diff_summary | git_analyzer |
| **需求-代码关联** | 通过文件名/模块名/注释引用建立的初步关联 | LLM 辅助识别 + 规则匹配 |
| **模块元数据** | 模块的创建时间、最后修改时间、贡献者列表、修改频率 | git_analyzer 聚合 |

### 4.3 存储策略

| 数据 | 存储引擎 | 说明 |
|------|---------|------|
| 结构化元数据 | **PostgreSQL** | `chunks` 表、`modules` 表、`dependencies` 表、`commits` 表、`requirement_code_links` 表 |
| 向量嵌入 | **ChromaDB** | `requirements` 集合（chunk embedding）、`code` 集合（模块/函数 embedding） |
| 大文本（>1KB 的 chunk 原文） | **MinIO** | PG 中保留 `text_uri` 引用 |

### 4.4 数据刷新策略

| 触发条件 | 刷新范围 | 说明 |
|---------|---------|------|
| 新文件上传 | 增量新增 | 仅处理新文件 |
| 代码仓库新 commit | 增量更新 | 仅更新变更的模块/依赖 |
| 用户触发全量重新索引 | 全量重建 | 从 L0 重新摄取全部文件 |
| 策略升级（新 embedding 模型、新解析器） | 全量重建 | L0 不变，L1 重建 |

### 4.5 使用方式

- **Context Pipeline 的 Collect 阶段**：从 ChromaDB 做语义检索，从 PG 做结构化查询
- **ToolRuntime 工具的数据源**：`search_code`、`get_dependencies`、`get_git_history` 等工具从 L1 读取数据
- **Evidence 的来源引用**：当 Agent 声称"模块 A 依赖模块 B"时，证据指向 L1 的 `dependencies` 表记录
- **项目画像的数据基础**：index-service 定期从 L1 聚合生成模块列表、术语候选、技术栈识别

### 4.6 关键约束

- L1 不包含推理结论。推理结论属于 L2。
- L1 的事实可以有"过期"标记，但不可删除（保留历史事实）。
- L1 的结构化提取质量决定 L2 的分析质量上限。

---

## 五、L2：Analysis Records（分析记录）— 可追溯的"实验记录本"

### 5.1 职责定义

L2 是 ReqRadar **每次认知分析过程的完整记录**。它捕获 Agent 的每一步思考、每一次工具调用、每一条证据的发现和验证过程。

**L2 不是结论集，是实验记录本。** 它保证"AI 的输出可追溯"不是一句口号，而是一个有完整审计链的工程事实。

### 5.2 存储内容

| 记录类型 | 内容 | 产生者 |
|---------|------|--------|
| **CognitiveSession** | 会话元数据：session_id、project_id、status、created_at、context_budget、context_usage | cognitive-rt |
| **Event Stream** | 三级事件流：Session 级、Reasoning 级、Cognitive 级 | cognitive-rt |
| **Checkpoint 链** | 每个推理步骤的完整状态快照：AgentState + EvidenceState + DimensionState + ContextState | cognitive-rt |
| **Evidence 链** | 经过验证的证据条目、证据间的依赖/支撑关系、每条证据的验证状态和置信度 | cognitive-rt Evidence Aggregation |
| **7-Dimension 评估** | 每个维度的评估进度、风险等级、证据数量、分析小结 | cognitive-rt |
| **Chatback 交互** | 用户追问与 Agent 回复的完整对话历史 | cognitive-rt Interaction Layer |

### 5.3 存储策略

| 数据 | 存储引擎 | 格式 | 说明 |
|------|---------|------|------|
| Session 元数据 | **PostgreSQL** | 结构化字段 | `cognitive_sessions` 表 |
| Checkpoint（热状态） | **PostgreSQL JSONB** | JSON | AgentState、EvidenceState、DimensionState |
| Checkpoint（冷状态） | **MinIO** | JSON 文件 | 完整 Context Snapshot，PG 中保留 `full_state_uri` 引用 |
| Checkpoint（可重建状态） | **不持久化** | - | 工具返回的原始数据，恢复时重新执行 |
| Event 持久化 | **PostgreSQL** | 结构化字段 | `events` 表，按 session_id + sequence 索引 |
| Event 实时传输 | **Redis Streams** | JSON 序列化 | 传输层，非持久化 |
| Evidence | **PostgreSQL** | 结构化字段 + JSONB 详情 | `evidence_records` 表 |
| Dimension 结果 | **PostgreSQL** | 结构化字段 | `dimension_results` 表 |

### 5.4 Checkpoint 状态分区

为避免 Checkpoint 变成存储黑洞，将快照数据按访问模式和重建成本分为三类：

| 分区 | 存储位置 | 内容 | 策略 |
|------|---------|------|------|
| **热状态** | PG JSONB | AgentState、EvidenceState、DimensionState | 恢复时必须立即读取，需结构化查询 |
| **冷状态** | MinIO | 完整 Context Snapshot（上下文来源、评分、选择理由） | 恢复时可能需要，但体积大且不需结构化查询 |
| **可重建状态** | 不存储 | 工具返回的原始数据、检索 payload | 恢复时重新执行工具调用即可获得 |

### 5.5 数据生命周期

```
Session 创建 → Event Stream 实时推送 → Checkpoint 周期性快照 → Evidence 聚合 →
Dimension 更新 → 分析完成 → 完整 Event Trace 持久化 → L3 沉淀入口
```

### 5.6 使用方式

- **报告生成**：output-service 查询 Session 的 Evidence + Dimension 结果
- **推理链回放**：通过 Event Stream 按 session_id + sequence 回放整个推理过程
- **跨会话对比**：同一需求在不同时间的分析结果对比
- **Chatback 上下文恢复**：从最近的 Checkpoint 恢复完整 Runtime State
- **L3 沉淀的输入源**：index-service 从 L2 提取可沉淀为长期知识的内容

### 5.7 关键约束

- L2 记录**不可修改**。分析一旦完成，记录就是只读的。
- L2 不直接回答"项目整体风险是什么"。那是 L3 跨 Session 聚合后的产出。
- Checkpoint 的热/冷/可重建分区是强制约束，不允许将可重建数据写入持久化存储。

---

## 六、L3：Persistent Knowledge（持久化知识）— 可演化的"认知大脑"

### 6.1 职责定义

L3 是 ReqRadar **最核心的资产层**。它从每一次分析记录（L2）中沉淀出关于项目的长期知识，并在后续分析中主动注入上下文，形成**认知飞轮**。L3 同时受**知识治理框架**约束，确保知识资产不随时间腐化。

### 6.2 知识分层：Facts 与 Patterns

L3 内部按抽象层次分为两级：

```
┌────────────────────────────────────────────┐
│  L3-B: Cognitive Patterns（认知模式）        │
│  "支付链路采用最终一致性设计"               │
│  "该团队倾向在性能与一致性之间选择前者"      │
│  "所有高风险事故集中在异步链路"             │
├────────────────────────────────────────────┤
│  L3-A: Cognitive Facts（认知事实）           │
│  术语表、模块画像、风险历史、决策记录        │
│  架构约束、需求谱系、事故记忆               │
└────────────────────────────────────────────┘
```

| 层级 | 本质 | 示例 | Phase |
|------|------|------|-------|
| **L3-A** | 跨 Session 聚合的结构化事实 | "payment 模块有 3 次金额精度事故" | **Phase 1 实现** |
| **L3-B** | 跨事实抽象后的稳定模式 | "支付链路的最终一致性是架构级约束" | **Phase 3 实现**，接口预留 |

### 6.3 L3-A：认知事实类型与演化规则

#### 6.3.1 术语表

| 属性 | 说明 |
|------|------|
| 内容 | 项目专有名词及其定义、别名、使用上下文、首次出现位置 |
| 演化方式 | 每次分析发现新术语时追加；同一术语被多次引用时提升 `confidence_score` |
| 示例 | `"points_engine"` → 积分计算引擎，别名 `PE`，定义于 `src/points/engine.py` |

#### 6.3.2 模块画像

| 属性 | 说明 |
|------|------|
| 内容 | 每个模块的职责描述、依赖关系、风险历史、修改频率、关键贡献者 |
| 演化方式 | 每次分析涉及该模块时更新 `last_analyzed_at` 和 `analysis_count` |
| 示例 | `payment` 模块 → 职责：订单支付与退款处理；依赖 `user`、`notify` |

#### 6.3.3 架构约束

| 属性 | 说明 |
|------|------|
| 内容 | 不可破坏的设计规则，来源可能是历史决策、事故复盘或用户显式声明 |
| 演化方式 | 从 L2 Evidence 中提取（`constraint` 类型证据）；用户可显式声明；不可删除，只可标记为 `deprecated` |
| 示例 | "支付模块不允许直接访问数据库，必须通过 `payment-gateway` 服务" |

#### 6.3.4 决策记录

| 属性 | 说明 |
|------|------|
| 内容 | 重大设计决策的上下文、参与者、结论、关联的需求和模块 |
| 演化方式 | 从需求分析和 Chatback 中提取；按时间线组织 |
| 示例 | "2025-03 决定将积分计算从同步改为异步——原因：大促期间 RT 超时" |

#### 6.3.5 风险演化

| 属性 | 说明 |
|------|------|
| 内容 | 每个风险的生命周期：首次识别 → 多次确认 → 缓解措施 → 关闭 |
| 演化方式 | 跨 Session 追踪同一风险（通过 `canonical_risk_id` 归并）；形成演化轨迹 |
| 示例 | `RISK-012`："用户并发扣减积分" → Session #15 首次识别（高风险）→ Session #35 采用分布式锁，降为中风险 |

**风险归一化（Risk Canonicalization）**：同一风险在不同 Session 中可能以不同描述出现（如"库存超卖""并发扣减""重复消费"可能指向同一并发安全问题）。系统通过 `risk_fingerprint`（基于涉及模块 + 风险类型 + 关键词的哈希）进行自动归并。精确的语义归一化算法作为 Phase 3 专项实现。

#### 6.3.6 需求谱系

| 属性 | 说明 |
|------|------|
| 内容 | 需求之间的派生、冲突、依赖关系；需求的版本演化历史 |
| 演化方式 | 从需求文档的引用关系推断；多次分析同一需求的不同版本时建立演化链 |
| 示例 | `REQ-2025-022`（VIP 积分加速）派生自 `REQ-2025-018`（积分规则重构） |

#### 6.3.7 事故记忆

| 属性 | 说明 |
|------|------|
| 内容 | 历史线上事故的根因、影响范围、修复措施、关联模块 |
| 演化方式 | 用户通过 Chatback 录入；系统从 Git revert commit 和 hotfix 分支中自动识别候选 |
| 示例 | "2025-05-12 支付回调重复处理 → 根因：消息队列 ACK 超时 → 修复：增加幂等键" |

### 6.4 L3 知识治理框架

L3 资产必须受治理框架约束，防止知识腐化。每一条 L3 知识记录必须包含以下治理元数据：

#### 6.4.1 知识新鲜度（Freshness）

| 状态 | 含义 | Context Pipeline 行为 |
|------|------|----------------------|
| `active` | 当前仍有效，近期被验证 | **默认注入** |
| `historical` | 历史知识，保留但不主动注入 | 仅在明确查询时返回 |
| `superseded` | 已被新知识替代 | 不注入，保留引用链 |
| `deprecated` | 已废弃，但仍需记录 | 不注入 |
| `stale` | 长期未验证（超过阈值） | 不注入，触发重新验证提示 |

**默认阈值**：超过 90 天未被任何 Session 引用或验证的知识自动标记为 `stale`。阈值可通过 Scope × Domain 配置矩阵调整。

#### 6.4.2 知识置信度（Confidence）

| 字段 | 类型 | 说明 |
|------|------|------|
| `confidence_score` | float (0.0-1.0) | 综合置信度评分 |
| `verification_count` | int | 被不同 Session 验证的次数 |
| `source_session_count` | int | 产生该知识的 Session 数量 |
| `human_verified` | bool | 是否经过人工确认 |
| `last_verified_at` | timestamp | 最近一次被验证的时间 |

**置信度计算规则**（Phase 1）：
- 基础分：从 1 个 Session 产生 = 0.3，2-3 个 = 0.6，4+ 个 = 0.8
- 人工确认：`human_verified = true` 时直接提升至 0.9
- 衰减：超过 60 天未验证，每周衰减 0.05，最低至 0.1
- 精确计算模型在 M-03 中详细定义

#### 6.4.3 知识变更日志

所有 L3 知识的创建、更新、废弃必须记录在 append-only 的 `knowledge_changelog` 表中：

| 字段 | 说明 |
|------|------|
| `change_id` | 变更唯一标识 |
| `knowledge_type` | 知识类型（glossary/module_profile/constraint/decision/risk/requirement_lineage/incident） |
| `knowledge_id` | 知识记录 ID |
| `change_type` | created/updated/deprecated/superseded/verified |
| `trigger_session_id` | 触发变更的 Session ID（可空，人工变更为 NULL） |
| `changed_fields` | JSON，变更的字段和旧值 |
| `changed_at` | 变更时间 |

### 6.5 统一关系契约（Relation Contract）

L3 中所有知识节点之间的关系通过统一契约管理，无论底层存储是 PG 关联表还是未来的图数据库：

```python
class KnowledgeRelation:
    source_type: str       # 知识类型：module/risk/decision/requirement/constraint/incident/glossary
    source_id: str         # 源节点 ID
    relation_type: str     # 关系类型：DEPENDS_ON/IMPACTS/CONFLICTS_WITH/EVOLVES_FROM/MITIGATES/VIOLATES/DERIVED_FROM
    target_type: str       # 目标节点类型
    target_id: str         # 目标节点 ID
    confidence: float      # 关系置信度 0.0-1.0
    evidence_ref: str      # 支撑该关系的 L2 Evidence ID 或 "human_declared"
    created_at: timestamp
    freshness: str         # 继承知识新鲜度模型
```

Phase 1 使用 PG 关联表实现，接口层统一使用此契约。未来切换到图数据库时，接口不变。

### 6.6 存储策略

| 数据 | 存储引擎 | 说明 |
|------|---------|------|
| L3-A 知识 | **PostgreSQL** | `glossary`、`module_profiles`、`constraints`、`decisions`、`risks`、`risk_evolution`、`requirement_lineage`、`incidents` 表 |
| L3-A 语义检索 | **ChromaDB** | 术语定义、模块描述的 embedding |
| L3-B 模式 | **PostgreSQL**（Phase 3） | `cognitive_patterns` 表，Phase 1 预留 Schema |
| 知识关系 | **PostgreSQL**（当前）/ Graph 接口层预留 | `knowledge_relations` 表，使用统一 Relation Contract |
| 治理元数据 | **PostgreSQL** | 新鲜度、置信度字段内嵌于各知识表；变更日志存 `knowledge_changelog` 表 |
| Graph 查询（未来） | 接口层预留 | ADR-015：当前不引入图数据库，所有关联查询通过 Relation Contract 接口 |

### 6.7 L3 的核心使用场景

#### 场景一：Context Pipeline 的知识注入（每次分析自动触发）

当新的 CognitiveSession 启动时，Context Pipeline 的 Collect 阶段自动从 L3 拉取：

```
1. 本次需求涉及哪些模块？
   → 查询 L3 模块画像，获取这些模块的风险历史、架构约束
   → 默认只注入 freshness=active 且 confidence_score≥0.6 的知识

2. 本次需求涉及哪些术语？
   → 查询 L3 术语表，获取准确定义

3. 这些模块有什么不可破坏的约束？
   → 查询 L3 架构约束（freshness=active），注入为高优先级上下文

4. 相关的历史决策有哪些？
   → 查询 L3 决策记录，提供决策背景
```

**关键约束**：L3 知识只作为 Context Pipeline 的输入，不直接参与 L2 的推理逻辑。这保证了长期知识不会污染推理内核，避免系统自我强化和自我幻觉。

**上下文权重叠加规则**：Context Pipeline 注入的每条上下文，最终权重 = ContextKind 基础权重 × L3 confidence_score（若适用）。不同 ContextKind 的基础权重定义如下：

| ContextKind | 基础权重 | 说明 |
|-------------|---------|------|
| SOURCE_CODE | 1.0 | 强事实，代码即真相 |
| REQUIREMENT | 0.95 | 高优先级，用户显式输入 |
| ARCH_DOC | 0.9 | 高可信，架构文档 |
| GIT_HISTORY | 0.7 | 弱历史，需结合时间衰减 |
| MEMORY | 0.6 | 可污染，需 confidence 兜底 |
| INFERRED_KNOWLEDGE | 0.4 | 高风险，LLM 推断产物 |

例如：一条来自 MEMORY 类型（基础权重 0.6）且 confidence_score=0.8 的 L3 知识，最终权重为 0.6 × 0.8 = 0.48；而一条 SOURCE_CODE 类型（基础权重 1.0）的代码证据，即使没有 L3 confidence，基础权重也为 1.0。

#### 场景二：主动认知提醒（分析完成后自动触发）

当分析完成，系统自动对比 L3：

```
- "本次分析发现模块 X 存在高风险。该模块历史上已有 3 次事故记录。"
- "本次需求提到的'积分规则'与 L3 术语表中的定义存在偏差，建议确认。"
- "本次需求新增了模块 Y 对模块 Z 的依赖。L3 中模块 Z 有架构约束：不允许新增外部依赖。"
```

#### 场景三：项目知识仪表盘（前端持续展示）

前端展示 L3 的实时聚合视图：

- 项目风险热力图（哪些模块风险最高）
- 架构约束清单（哪些规则绝对不能破坏）
- 术语云（新人快速理解项目语言）
- 决策演化时间线（设计决策如何一步步走到今天）

#### 场景四：MCP 集成分发（IDE 内实时推送）

当开发者在 IDE 中打开文件时，integration-service 通过 MCP 从 L3 查询并推送：

- 该文件关联的需求和风险
- 该文件所属模块的架构约束
- 最近一次修改该文件的原因和决策背景

### 6.8 关键约束

- **L3 知识不可删除，只可标记为 `deprecated` 或 `superseded`。** 这是"组织不再失忆"的技术保障。
- **L3 知识变更必须记录在 append-only 的 `knowledge_changelog` 中。**
- **L3 知识不直接参与 L2 推理逻辑。** L3 仅作为 Context Pipeline 的输入，认知偏见的风险由 Evidence-driven 机制对冲。
- **L3 不存储原始文件或大段文本。** 它只存储知识结论和 L0/L1 的引用指针。
- **Context Pipeline 默认只注入 `freshness=active` 且 `confidence_score≥0.6` 的知识。** 防止历史噪音和低置信度知识干扰推理。

---

## 七、四层模型的数据流与认知飞轮

### 7.1 完整数据流

```
用户上传文件 / 代码仓库 / Git 历史
         │
         ▼
    ┌─────────┐
    │   L0    │  MinIO 原始文件（不可变档案馆）
    │         │  PG 元数据指针
    └────┬────┘
         │ ingestion-service 摄取
         ▼
    ┌─────────┐
    │   L1    │  PG + ChromaDB 结构化事实（可索引图书馆）
    │         │  MinIO 大文本
    └────┬────┘
         │ cognitive-rt 分析
         ▼
    ┌─────────┐
    │   L2    │  PG JSONB Checkpoint（热/冷/可重建分区）
    │         │  Redis Streams Event 实时流
    │         │  PG Evidence + Dimension
    └────┬────┘
         │ index-service 沉淀
         ▼
    ┌─────────┐
    │   L3    │  PG + ChromaDB 持久化知识（受治理框架约束）
    │         │  L3-A Facts + L3-B Patterns（预留）
    │         │  Graph 接口层预留（统一 Relation Contract）
    └────┬────┘
         │ Context Pipeline 注入（仅 active + high-confidence）
         └──────→ 回到 L2，形成闭环
```

### 7.2 认知飞轮

```
┌─────────────────────────────────────────────────────┐
│                                                      │
│   ① 新分析启动                                       │
│      Context Pipeline 从 L3 注入知识                  │
│      （仅 freshness=active + confidence≥0.6）         │
│      ↓                                               │
│   ② 分析执行（L2）                                   │
│      Agent 基于 L1 事实 + L3 知识进行推理             │
│      ↓                                               │
│   ③ 分析完成                                         │
│      Evidence + Dimension 结果持久化到 L2             │
│      ↓                                               │
│   ④ 知识沉淀                                         │
│      index-service 从 L2 提取可沉淀知识              │
│      更新 L3 并记录 changelog                        │
│      ↓                                               │
│   ⑤ 知识治理                                         │
│      更新置信度、验证新鲜度、检测冲突                  │
│      ↓                                               │
│   ⑥ 认知增强                                         │
│      L3 比上一次更丰富、更准确，且无腐化              │
│      ↓                                               │
│   ⑦ 回到 ①，下一次分析站在更高的认知起点              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**飞轮效应的核心**：每次分析都在消费经过治理的 L3 知识，同时又产生新的 L2 记录，这些记录再沉淀为更丰富的 L3。认知资产不是线性增长，而是受控的指数级增值。

### 7.3 飞轮自我验证机制（L3 Self-Verification Layer）

飞轮是闭环系统，必须有自我验证机制，否则无法证明"越用越准"是工程事实而非营销话术。

**验证机制**：每次 L3 沉淀时，自动运行对比实验：

```
1. 取本次 Session 的 Context Pipeline 注入的 L3 知识
2. 构造对照组：用占位 L3（相同条目数，但内容随机化）替代
3. 对比两组在相同需求上的推理质量差异
4. 记录偏差到 verification_log 表
```

**偏差处理规则**：

| 偏差程度 | 含义 | 处理 |
|---------|------|------|
| V3 质量 > 占位质量 | L3 注入有效 | 正常，confidence +0.05 |
| V3 质量 ≈ 占位质量 | L3 注入无效 | 标记相关知识为 `under_review`，不进入下一次注入 |
| V3 质量 < 占位质量 | L3 注入有害 | 标记相关知识为 `harmful`，触发人工审核，暂停飞轮 |

**验证频率**：每 10 次 Session 沉淀运行一次完整验证，避免每次分析都做对比实验（成本过高）。

### 7.4 L3 写入语义矩阵

7 种 L3-A 知识类型的写入语义差异极大，必须统一定义，否则 P5 的 7 个子任务会各自为政。

| 知识类型 | 写入策略 | 冲突解决 | 去重键 |
|---------|---------|---------|--------|
| 术语表 | append，按 canonical_name 去重 | 别名合并 | `canonical_name` |
| 模块画像 | update 增量 + 完整 snapshot | 后写覆盖 + changelog | `module_name` |
| 架构约束 | append，标记 deprecated | 人工解决 | `constraint_hash` |
| 决策记录 | append | 时间线排序 | `decision_id` |
| 风险演化 | append + canonical_id 归并 | risk_fingerprint 哈希 | `risk_fingerprint` |
| 需求谱系 | append + 图结构 | 派生关系推断 | `requirement_pair` |
| 事故记忆 | append | 时间线排序 | `incident_id` |

**统一写入接口（L3Writer Protocol）**：

```python
class L3Writer(Protocol):
    def append(self, knowledge_type: str, payload: dict, evidence_ref: str) -> KnowledgeRecord: ...
    def update(self, knowledge_id: str, patch: dict, evidence_ref: str) -> KnowledgeRecord: ...
    def deprecate(self, knowledge_id: str, reason: str) -> KnowledgeRecord: ...
    def merge(self, knowledge_ids: list[str], strategy: str) -> KnowledgeRecord: ...
```

7 种知识类型都是此接口的不同实现。P5.4 的 7 个子任务在此接口下填充具体逻辑，不是从零设计。

---

## 八、与其他架构文档的关系

| 本文档定义 | 影响的设计文档 | 具体影响 |
|-----------|--------------|---------|
| L2 Evidence 结构 | **M-01 Evidence Model** | Evidence 的 `source` 字段引用 L0/L1；Evidence 验证后沉淀到 L3 |
| L2 Dimension 结果 | **M-02 7-Dimension Framework** | 每个维度的评估结果存 L2；风险记录的 canonical_risk_id 设计 |
| **L3 全部知识类型 + 治理框架** | **M-03 Project Cognitive State** | 直接定义 L3 的完整 Schema，含新鲜度、置信度、变更日志 |
| L3 统一关系契约 | **M-04 Cognitive Graph Schema** | Relation Contract 是 Graph Schema 的核心 |
| L2 Session 管理 | **R-01 Session 生命周期** | Session 状态机管理 L2 的生成过程 |
| L1 + L3 → L2 注入 | **R-02 Context Pipeline** | Collect 阶段的知识注入规则（freshness/confidence 过滤） |
| L2 Event 存储 | **R-03 Event Stream Schema** | Event 的持久化字段设计 |
| L1 数据查询 | **R-04 ToolRuntime** | 工具的数据源接口定义 |
| L2 Checkpoint 存储 | **R-05 Checkpoint 详细设计** | Checkpoint 的热/冷/可重建状态分区 |
| L1/L3 查询接口 | **I-01 服务间 API 契约** | cognitive-rt → index-service 的查询接口（详见 [I-01_SERVICE_API_CONTRACT.md](detailed/I-01_SERVICE_API_CONTRACT.md)） |
| 全部四层 | **C-06 数据库迁移计划** + **I-03 数据迁移方案** | 各层对应的表结构和 DDL（C-06 已完成）；V1→V2 数据迁移映射（I-03 规划中） |

---

## 九、存储引擎数据主权总览

| 存储引擎 | 管理的层 | 数据类型 | 核心职责 |
|---------|---------|---------|---------|
| **MinIO** | L0（全部）、L1/L2 大对象 | 原始文件、大文本 chunk、Checkpoint 冷状态 | **不可变数据和大对象的所有者** |
| **PostgreSQL** | L1/L2/L3 结构化数据 | chunk 元数据、Session/Event/Checkpoint 热状态/Evidence/Dimension、L3 全部知识及治理元数据、知识关系、变更日志 | **结构化认知的主存储与知识治理中心** |
| **ChromaDB** | L1/L3 向量索引 | L1 的 chunk/code embedding、L3 的术语/模块语义检索 | **语义检索的唯一提供者** |
| **Redis Streams** | L2 实时事件流 | Event Stream 的传输层 | **实时事件的传输管道**，不持久化 |

---

## 十、明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| L3 引入图数据库 | 暂不引入，接口预留（统一 Relation Contract） | ADR-015：当前 PG 关联表满足需求；接口层统一访问，未来可切换 |
| L0/L1 内容直接作为 LLM 上下文 | 不做 | 必须经过 L1 结构化 + L2 Context Pipeline 的 Token 预算管理 |
| L3 知识自动覆盖 | 不做 | 所有知识变更必须追加，不可覆盖删除；append-only changelog |
| L3-B 模式层实现 | Phase 1 不做，接口预留 | 先完成 L3-A 的沉淀和治理验证，再抽象模式层 |
| 完整知识治理运行时 | Phase 1 不做 | 先建立治理元数据基础（新鲜度/置信度/changelog），治理算法逐步迭代 |
| 跨项目认知共享 | Phase 1 不做 | 先在单项目内验证飞轮效应 |
| L3 的 Graph 查询 | Phase 1 不做 | 接口预留，PG 关联表查询足够；未来按需切换 |

---

## 十一、术语规范

为避免"认知"一词过度泛化，后续文档统一使用以下术语：

| 术语 | 定义 | 所在层 |
|------|------|--------|
| Raw Context | 原始上下文，不可变的原始文件 | L0 |
| Structured Facts | 结构化事实，可检索的事实表示 | L1 |
| Analysis Records | 分析记录，单次推理的完整过程 | L2 |
| Persistent Knowledge | 持久化知识，跨 Session 积累的工程知识 | L3 |
| Cognitive Facts | 认知事实，跨 Session 聚合的结构化知识 | L3-A |
| Cognitive Patterns | 认知模式，跨事实抽象后的稳定模式 | L3-B |
| Architectural Constraint | 架构约束，不可破坏的设计规则 | L3-A |
| Risk Evolution | 风险演化，风险的生命周期追踪 | L3-A |
| Decision Record | 决策记录，重大设计决策的上下文和结论 | L3-A |
| Organizational Memory | 组织记忆，ReqRadar 长期积累的全部认知资产 | 系统整体 |

---

## 十二、总结

ReqRadar 的核心壁垒不是 Prompt 模板或 Tool 数量，而是这套**从 L0 到 L3 的认知资产加工与治理体系**。

- **L0** 保证一切有据可查
- **L1** 让原始材料可被高效检索
- **L2** 让每一次推理可追溯、可回放，Checkpoint 状态分区防止存储膨胀
- **L3** 让知识跨会话积累、受治理框架约束、不随时间腐化

L3 的知识治理框架——新鲜度模型、置信度体系、统一关系契约、append-only 变更日志——确保了"越用越聪明"的同时"不会越用越脏"。

**最终，这四层模型所支撑的核心愿景始终是：**

> **让组织不再失忆。让 AI 对项目的知识可以持续积累、追溯、演化和治理。**
