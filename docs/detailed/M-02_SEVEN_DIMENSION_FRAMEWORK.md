# M-02 七维度分析框架（7-Dimension Framework）详细设计

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | V2 七维度分析框架的详细设计——认知分析的评估骨架 |
| 前置文档 | 00_PROJECT_POSITIONING.md（项目宪法）、01_RESTRUCTURE_OVERVIEW.md（Runtime 蓝图）、03_COGNITIVE_ASSET_MODEL.md（认知资产模型） |
| 核心目标 | 定义 V2 中七维度框架的维度语义、状态模型、评估流程、聚合算法、L3 沉淀规则，确保认知分析的覆盖全面性与可追溯性 |
| 文档职责 | What & How — 七维度是什么、如何评估、如何聚合、如何沉淀、如何存储 |

---

## 一、概述

### 1.1 七维度框架在 V2 中的定位

ReqRadar 的核心价值主张是"证据驱动的可验证认知"。七维度框架是这一主张的**评估骨架**——它定义了"一次完整的需求分析应该覆盖哪些认知维度"，并确保 Agent 的推理过程不会遗漏关键视角。

在 V2 Runtime 架构中，七维度框架的角色从 V1 的"简单进度标记"升级为"认知分析的完整性守卫"：

| | V1 | V2 |
|---|---|---|
| 定位 | Agent 内部的进度标记 | CognitiveSession 的完整性评估骨架 |
| 状态模型 | 3 状态（pending/in_progress/sufficient/insufficient） | 4 状态 + 风险等级 + 置信度评分 |
| 评估方式 | LLM 自报 dimension_status | LLM 评估 + Evidence 驱动的自动校验 |
| 聚合能力 | 无聚合，仅展示 | 加权聚合为整体风险等级，驱动报告生成 |
| 沉淀能力 | 无 | 维度评估结果可沉淀到 L3 |
| 存储方式 | 内存 dataclass + JSON blob | PostgreSQL 持久化 + Checkpoint 快照 |

### 1.2 核心设计原则

1. **Evidence-driven**：维度状态转换必须有证据支撑，不接受无证据的 sufficient 声明
2. **Understanding-first**：understanding 维度是其他 6 个维度的基础，未达标时其他维度的评估结果置信度受限
3. **最弱维度决定**：整体风险等级由最薄弱的维度决定，而非平均值掩盖短板
4. **可沉淀**：维度评估结果中的结构化知识可沉淀到 L3，形成长期认知资产
5. **可配置**：维度列表、权重、充分性阈值均可通过 Scope x Domain 配置矩阵调整

---

## 二、七维度定义

### 2.1 维度总览

| 维度 ID | 中文名 | 定义 | 评估目标 | L3 沉淀方向 |
|---------|--------|------|---------|------------|
| understanding | 需求理解 | 对需求核心问题、术语、背景的理解程度 | "我们是否真正理解了这个需求在说什么？" | 术语表、需求谱系 |
| impact | 影响范围 | 需求对代码模块、系统架构、业务流程的影响识别 | "这个需求会影响哪些模块和系统？" | 模块画像 |
| risk | 风险识别 | 基于代码证据识别潜在风险和隐患 | "实现这个需求可能引入什么风险？" | 风险演化 |
| change | 变更评估 | 需求引起的代码变更范围、类型和复杂度评估 | "需要改什么？改动有多大？" | 模块画像 |
| decision | 决策支撑 | 为需求实现提供可操作的决策建议 | "应该怎么做？有哪些选择？" | 决策记录 |
| evidence | 证据充分性 | 支撑其他维度结论的证据是否充足、多源、可验证 | "我们的结论有足够的证据支撑吗？" | 架构约束 |
| verification | 可验证性 | 分析结论是否可被验证、测试和确认 | "怎么确认做对了？" | 事故记忆 |

### 2.2 维度详细定义

#### 2.2.1 Understanding（需求理解）

| 属性 | 说明 |
|------|------|
| 维度 ID | `understanding` |
| 中文名 | 需求理解 |
| 定义 | 评估 Agent 对需求核心问题、业务术语、上下文背景的理解深度和准确度 |
| 评估目标 | "我们是否真正理解了这个需求在说什么？" |
| 基础权重 | 1.2（最高权重，其他维度依赖此维度的充分性） |
| 依赖关系 | 无前置依赖；是 impact/risk/change/decision 的前置条件 |

**评估问题清单**：

| # | 引导性问题 |
|---|----------|
| Q1 | 需求的核心目标是什么？能否用一句话概括？ |
| Q2 | 需求中涉及哪些项目专有术语？它们的定义是什么？ |
| Q3 | 需求的业务背景和上下文是什么？为什么现在提出？ |
| Q4 | 需求是否有模糊或歧义的表述？需要与需求方确认什么？ |
| Q5 | 需求与项目现有的业务规则或架构约束是否冲突？ |

**关键证据类型**（来自 M-01 EvidenceType）：

| 证据类型 | 说明 | 证据来源 |
|---------|------|---------|
| `project_context` | 项目术语定义、业务规则 | L1 术语表、L3 术语表 |
| `requirement` | 需求原文及解析 | L0 原始文档、L1 文档 Chunk |
| `arch_doc` | 架构文档、设计规范 | L1 文档 Chunk |
| `memory` | 项目记忆中的历史需求 | L3 知识注入 |

**风险等级映射**：

| 维度状态 | 风险等级 | 含义 |
|---------|---------|------|
| INSUFFICIENT | high | 需求理解严重不足，后续分析结论不可信 |
| IN_PROGRESS | medium | 正在理解中，部分术语或背景已识别 |
| SUFFICIENT | low | 需求核心问题清晰，术语已定义，背景已理解 |

**充分性标准**：

- 至少 1 个关键术语已定义（来自 L3 术语表或 L1 术语提取）
- 需求背景拆解清晰（核心目标、业务上下文、提出原因均已识别）
- 无未解决的歧义表述（或已标注为 open_question）

---

#### 2.2.2 Impact（影响范围）

| 属性 | 说明 |
|------|------|
| 维度 ID | `impact` |
| 中文名 | 影响范围 |
| 定义 | 评估需求对代码模块、系统架构、数据流、业务流程的影响识别的完整性和准确性 |
| 评估目标 | "这个需求会影响哪些模块和系统？" |
| 基础权重 | 1.0 |
| 依赖关系 | 前置依赖 understanding |

**评估问题清单**：

| # | 引导性问题 |
|---|----------|
| Q1 | 需求直接涉及哪些代码模块？每个模块受影响的理由是什么？ |
| Q2 | 需求间接影响哪些模块（通过依赖链传播）？ |
| Q3 | 需求是否影响数据库 Schema、API 接口或消息协议？ |
| Q4 | 需求是否影响跨系统的数据流或业务流程？ |

**关键证据类型**：

| 证据类型 | 说明 | 证据来源 |
|---------|------|---------|
| `code_match` | 受影响模块的代码证据 | L1 代码模块、L1 依赖关系 |
| `dependency` | 模块依赖链 | L1 依赖关系 |
| `requirement` | 需求原文中的影响描述 | L0/L1 |
| `memory` | L3 模块画像中的历史影响记录 | L3 知识注入 |

**风险等级映射**：

| 维度状态 | 风险等级 | 含义 |
|---------|---------|------|
| INSUFFICIENT | high | 影响范围未识别，可能遗漏关键模块 |
| IN_PROGRESS | medium | 部分模块已识别，但依赖链或跨系统影响未覆盖 |
| SUFFICIENT | low | 影响模块完整识别，含直接和间接影响，有代码路径依据 |

**充分性标准**：

- 至少 2 个受影响模块被识别，每个模块有具体路径和影响理由
- 直接依赖链已追踪（至少 1 层间接影响已识别）
- 如涉及跨系统影响，已标注影响面

---

#### 2.2.3 Risk（风险识别）

| 属性 | 说明 |
|------|------|
| 维度 ID | `risk` |
| 中文名 | 风险识别 |
| 定义 | 基于代码证据和历史知识，识别需求实现可能引入的技术风险、业务风险和架构风险 |
| 评估目标 | "实现这个需求可能引入什么风险？" |
| 基础权重 | 1.1 |
| 依赖关系 | 前置依赖 understanding + impact |

**评估问题清单**：

| # | 引导性问题 |
|---|----------|
| Q1 | 需求实现可能引入哪些技术风险（性能、安全、并发、数据一致性）？ |
| Q2 | 受影响模块是否有历史风险记录或事故记忆？ |
| Q3 | 需求是否违反已有的架构约束？ |
| Q4 | 风险的严重程度如何？是否有缓解措施？ |
| Q5 | 是否存在被低估的隐性风险（如跨模块副作用、时序依赖）？ |

**关键证据类型**：

| 证据类型 | 说明 | 证据来源 |
|---------|------|---------|
| `code_match` | 风险相关的代码证据（如并发代码、安全敏感代码） | L1 代码模块 |
| `git_history` | 相关模块的历史变更和修复记录 | L1 Git 提交事实 |
| `constraint` | 架构约束违反的证据 | L3 架构约束 |
| `memory` | L3 风险演化和事故记忆 | L3 知识注入 |

**风险等级映射**：

| 维度状态 | 风险等级 | 含义 |
|---------|---------|------|
| INSUFFICIENT | high | 风险完全未识别，可能存在重大隐患 |
| IN_PROGRESS | medium | 部分风险已识别，但缺乏结构化评估或缓解建议 |
| SUFFICIENT | low | 风险已结构化识别（类型+严重度+缓解建议），且与代码证据关联 |

**充分性标准**：

- 至少 2 个结构化风险条目（含类型、严重度、缓解建议）
- 每个风险条目有代码证据或历史记录支撑
- 已检查 L3 架构约束是否被违反

---

#### 2.2.4 Change（变更评估）

| 属性 | 说明 |
|------|------|
| 维度 ID | `change` |
| 中文名 | 变更评估 |
| 定义 | 评估需求引起的代码变更范围、变更类型（新增/修改/重构）、变更复杂度和影响等级 |
| 评估目标 | "需要改什么？改动有多大？" |
| 基础权重 | 0.9 |
| 依赖关系 | 前置依赖 understanding + impact |

**评估问题清单**：

| # | 引导性问题 |
|---|----------|
| Q1 | 需要新增、修改还是重构代码？变更类型是什么？ |
| Q2 | 每个受影响模块的具体变更点在哪里？ |
| Q3 | 变更的复杂度如何？是否涉及核心逻辑或跨模块协调？ |
| Q4 | 变更是否需要数据库迁移、API 版本升级或配置变更？ |

**关键证据类型**：

| 证据类型 | 说明 | 证据来源 |
|---------|------|---------|
| `code_match` | 变更点的代码证据 | L1 代码模块 |
| `dependency` | 变更传播的依赖链 | L1 依赖关系 |
| `git_history` | 类似变更的历史记录和复杂度参考 | L1 Git 提交事实 |
| `memory` | L3 模块画像中的变更频率和复杂度历史 | L3 知识注入 |

**风险等级映射**：

| 维度状态 | 风险等级 | 含义 |
|---------|---------|------|
| INSUFFICIENT | high | 变更范围未评估，工作量可能严重低估 |
| IN_PROGRESS | medium | 部分变更点已识别，但变更复杂度或传播范围未评估 |
| SUFFICIENT | low | 变更点完整识别，含变更类型、复杂度和影响等级 |

**充分性标准**：

- 至少 2 个变更评估（含模块、变更类型、影响等级）
- 变更的复杂度已评估（简单/中等/复杂）
- 如涉及跨模块协调，已标注协调点

---

#### 2.2.5 Decision（决策支撑）

| 属性 | 说明 |
|------|------|
| 维度 ID | `decision` |
| 中文名 | 决策支撑 |
| 定义 | 基于前序维度的分析结论，为需求实现提供可操作的决策建议和方案选择 |
| 评估目标 | "应该怎么做？有哪些选择？" |
| 基础权重 | 0.9 |
| 依赖关系 | 前置依赖 understanding + impact + risk + change |

**评估问题清单**：

| # | 引导性问题 |
|---|----------|
| Q1 | 基于风险和变更评估，推荐的实现方案是什么？ |
| Q2 | 是否存在替代方案？各方案的 trade-off 是什么？ |
| Q3 | 有哪些需要团队决策的开放问题？ |
| Q4 | 实现的优先级和分阶段建议是什么？ |

**关键证据类型**：

| 证据类型 | 说明 | 证据来源 |
|---------|------|---------|
| `inference` | 基于证据的推理结论和决策建议 | L2 Agent 推理 |
| `constraint` | 约束决策的架构规则 | L3 架构约束 |
| `memory` | L3 决策记录中的历史决策参考 | L3 知识注入 |
| `requirement` | 需求中的约束条件 | L0/L1 |

**风险等级映射**：

| 维度状态 | 风险等级 | 含义 |
|---------|---------|------|
| INSUFFICIENT | high | 无决策建议，团队缺乏实现指导 |
| IN_PROGRESS | medium | 有初步建议，但缺乏方案对比或开放问题未列出 |
| SUFFICIENT | low | 有决策总结 + 至少 1 个决策建议项 + 开放问题清单 |

**充分性标准**：

- 有决策总结（综合前序维度结论）
- 至少 1 个决策建议项（含理由和 trade-off）
- 开放问题已列出（如有）

---

#### 2.2.6 Evidence（证据充分性）

| 属性 | 说明 |
|------|------|
| 维度 ID | `evidence` |
| 中文名 | 证据充分性 |
| 定义 | 评估支撑其他维度结论的证据是否充足、来源多样、可验证，是分析质量的元评估维度 |
| 评估目标 | "我们的结论有足够的证据支撑吗？" |
| 基础权重 | 1.0 |
| 依赖关系 | 无硬前置依赖，但评估质量与前 5 个维度的证据积累正相关 |

**评估问题清单**：

| # | 引导性问题 |
|---|----------|
| Q1 | 每个维度的结论是否有至少 1 条证据支撑？ |
| Q2 | 证据来源是否多样化（代码+文档+Git历史+项目记忆）？ |
| Q3 | 是否存在仅凭推理而无代码证据的结论？ |
| Q4 | 证据之间是否存在矛盾？是否需要进一步验证？ |

**关键证据类型**：

| 证据类型 | 说明 | 证据来源 |
|---------|------|---------|
| `code_match` | 代码级证据 | L1 代码模块 |
| `requirement` | 需求文档证据 | L0/L1 |
| `git_history` | Git 历史证据 | L1 Git 提交事实 |
| `project_context` | 项目上下文证据 | L1/L3 |
| `constraint` | 架构约束证据 | L3 架构约束 |

**风险等级映射**：

| 维度状态 | 风险等级 | 含义 |
|---------|---------|------|
| INSUFFICIENT | high | 证据严重不足，结论不可信 |
| IN_PROGRESS | medium | 证据正在积累，但来源单一或覆盖不完整 |
| SUFFICIENT | low | 至少 3 条不同来源的证据，覆盖前 5 个维度 |

**充分性标准**：

- 至少 3 条不同来源的证据（来源类型 >= 2）
- 证据覆盖前 5 个维度中的至少 4 个
- 无仅凭推理而无代码/文档证据支撑的关键结论

---

#### 2.2.7 Verification（可验证性）

| 属性 | 说明 |
|------|------|
| 维度 ID | `verification` |
| 中文名 | 可验证性 |
| 定义 | 评估分析结论是否可被验证、测试和确认，确保分析产出不是"不可验证的 AI 判断" |
| 评估目标 | "怎么确认做对了？" |
| 基础权重 | 0.8 |
| 依赖关系 | 前置依赖 understanding + risk + decision |

**评估问题清单**：

| # | 引导性问题 |
|---|----------|
| Q1 | 每个风险是否有对应的验证方法？ |
| Q2 | 是否有可执行的测试要点或验收标准？ |
| Q3 | 验证方法是否覆盖了关键风险场景？ |
| Q4 | 是否需要特殊的测试环境或数据准备？ |

**关键证据类型**：

| 证据类型 | 说明 | 证据来源 |
|---------|------|---------|
| `inference` | 基于风险和决策推导的验证要点 | L2 Agent 推理 |
| `code_match` | 现有测试代码或测试框架的证据 | L1 代码模块 |
| `memory` | L3 事故记忆中的历史验证经验 | L3 知识注入 |

**风险等级映射**：

| 维度状态 | 风险等级 | 含义 |
|---------|---------|------|
| INSUFFICIENT | high | 结论不可验证，无法确认实现正确性 |
| IN_PROGRESS | medium | 部分验证要点已列出，但覆盖不完整 |
| SUFFICIENT | low | 至少 3 条可执行的验证要点，覆盖关键风险场景 |

**充分性标准**：

- 至少 3 条可执行的验证要点
- 验证要点覆盖已识别的关键风险
- 如需特殊测试环境，已标注

---

### 2.3 维度依赖关系图

```
                    ┌───────────────┐
                    │ understanding │
                    │  (需求理解)    │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
      ┌───────────┐ ┌───────────┐ ┌───────────┐
      │  impact   │ │   risk    │ │  change   │
      │ (影响范围) │ │ (风险识别) │ │ (变更评估) │
      └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
            │             │             │
            │     ┌───────┤             │
            │     │       │             │
            ▼     ▼       ▼             │
      ┌───────────┐                     │
      │ decision  │◄────────────────────┘
      │ (决策支撑) │
      └─────┬─────┘
            │
      ┌─────┴──────┐
      ▼            ▼
┌───────────┐ ┌───────────┐
│ evidence  │ │verification│
│(证据充分性)│ │ (可验证性)  │
└───────────┘ └───────────┘
```

**依赖规则**：

| 规则 | 说明 |
|------|------|
| understanding 未达 IN_PROGRESS 时 | impact/risk/change 的状态评估结果置信度乘以 0.5 折扣因子 |
| understanding 未达 SUFFICIENT 时 | decision 的状态评估结果置信度乘以 0.7 折扣因子 |
| impact 未达 IN_PROGRESS 时 | risk 和 change 的评估缺乏影响范围基础，Agent 应优先补充 impact 证据 |
| evidence 维度独立评估 | evidence 是元评估维度，其结果不影响其他维度的状态，但影响整体风险等级 |

**循环依赖处理**：

维度间依赖关系形成有向图。在标准推理流程中，依赖链为 understanding → impact → risk → change → decision，不存在循环。但在实际推理中，risk 和 change 可能形成双向影响（risk 影响 change 评估，change 也影响 risk 重新评估）。

处理规则：
1. **依赖图是软约束，不是硬约束**：维度评估按依赖顺序推进，但后续维度的评估结果可以触发前序维度的重新评估
2. **重新评估不形成无限循环**：同一维度在单次推理步骤中最多被评估一次；跨步骤的重新评估最多 3 轮
3. **3 轮后仍有冲突**：以 risk 维度的评估结果为准（risk 是安全底线，保守优先）
4. **记录依赖冲突**：循环重新评估的次数和原因记录在 `DimensionState.evaluation_notes` 中

---

## 三、维度状态模型

### 3.1 DimensionStatus 枚举

```python
class DimensionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
```

**状态语义**：

| 状态 | 含义 | 证据要求 |
|------|------|---------|
| PENDING | 尚未开始评估 | 无 |
| IN_PROGRESS | 正在评估中，已收集部分证据 | 至少 1 条相关证据 |
| SUFFICIENT | 评估完成，维度达标 | 满足该维度的充分性标准 |
| INSUFFICIENT | 评估完成但维度未达标，或分析终止时仍 PENDING | 不满足充分性标准 |

### 3.2 RiskLevel 枚举

```python
class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

**与维度状态的映射**：

| DimensionStatus | 默认 RiskLevel | 说明 |
|----------------|---------------|------|
| PENDING | HIGH | 未评估等同于高风险 |
| IN_PROGRESS | MEDIUM | 正在评估，风险可控 |
| SUFFICIENT | LOW | 已达标，风险低 |
| INSUFFICIENT | HIGH | 未达标，风险高 |

> CRITICAL 级别不由维度状态自动映射，而由 Agent 在 risk 维度中识别到关键架构约束违反或重大安全隐患时手动标记。

### 3.3 DimensionState 数据模型（Pydantic）

```python
class DimensionState(BaseModel):
    dimension_id: str
    status: DimensionStatus = DimensionStatus.PENDING
    evidence_ids: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.HIGH
    assessment_summary: str | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    last_updated_at: datetime | None = None
    evaluation_questions: dict[str, str] = Field(default_factory=dict)
    sufficient_criteria_met: list[str] = Field(default_factory=list)
    sufficient_criteria_unmet: list[str] = Field(default_factory=list)
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `dimension_id` | str | 维度标识，如 "understanding" |
| `status` | DimensionStatus | 当前评估状态 |
| `evidence_ids` | list[str] | 关联的证据 ID 列表 |
| `risk_level` | RiskLevel | 该维度的风险等级 |
| `assessment_summary` | str \| None | 该维度的评估小结（Agent 生成） |
| `confidence_score` | float | 评估置信度 0.0-1.0，受依赖维度影响 |
| `last_updated_at` | datetime \| None | 最近一次状态变更时间 |
| `evaluation_questions` | dict[str, str] | 各引导性问题的回答摘要 |
| `sufficient_criteria_met` | list[str] | 已满足的充分性标准项 |
| `sufficient_criteria_unmet` | list[str] | 未满足的充分性标准项 |

### 3.4 维度状态转换规则

```
                    ┌──────────┐
                    │ PENDING  │
                    └────┬─────┘
                         │ 首条证据添加 / Agent 开始评估
                         ▼
                    ┌──────────┐
              ┌─────│IN_PROGRESS│─────┐
              │     └──────────┘     │
              │ 充分性标准全部满足    │ 分析终止但标准未满足
              ▼                      ▼
        ┌───────────┐         ┌─────────────┐
        │ SUFFICIENT│         │ INSUFFICIENT │
        └─────┬─────┘         └──────┬──────┘
              │                      │
              │ 新证据推翻结论        │ 补充证据后重新评估
              │                      │
              └──────────┬───────────┘
                         ▼
                    ┌──────────┐
                    │IN_PROGRESS│  (重新评估)
                    └──────────┘
```

**转换触发条件**：

| 转换 | 触发条件 | 执行者 |
|------|---------|--------|
| PENDING → IN_PROGRESS | 首条证据添加到该维度，或 Agent 在 dimension_status 中标记 in_progress | DimensionTracker |
| IN_PROGRESS → SUFFICIENT | 该维度的充分性标准全部满足（sufficient_criteria_unmet 为空） | DimensionTracker（自动校验） |
| IN_PROGRESS → INSUFFICIENT | 分析终止（Session COMPLETED/FAILED/CANCELLED）但充分性标准未满足 | DimensionTracker |
| SUFFICIENT → IN_PROGRESS | 新证据推翻已有结论（如发现矛盾证据），或 Agent 主动降级 | DimensionTracker / Agent |
| INSUFFICIENT → IN_PROGRESS | Chatback 补充分析时，新证据添加到该维度 | DimensionTracker |
| PENDING → INSUFFICIENT | 分析终止时该维度仍为 PENDING | DimensionTracker |

**关键约束**：

- SUFFICIENT 状态的转换必须经过充分性标准校验，不接受 Agent 的无证据 sufficient 声明
- INSUFFICIENT 是终态之一，仅在分析终止时设置；分析进行中不允许直接标记 INSUFFICIENT
- 状态转换必须记录 Event（`DimensionChanged` 事件），包含旧状态、新状态、触发原因

### 3.5 置信度计算

维度的 `confidence_score` 受以下因素影响：

| 因素 | 计算规则 |
|------|---------|
| 证据数量 | `min(1.0, evidence_count / min_evidence_for_sufficient)` |
| 证据来源多样性 | `source_type_count / total_source_types`，最低 0.3 |
| 依赖维度折扣 | understanding 未 SUFFICIENT 时，依赖维度乘以 0.7 折扣因子 |
| 证据质量 | 高置信度证据占比 |

**综合计算**：

```
confidence_score = (
    evidence_quantity_factor * 0.3
    + source_diversity_factor * 0.2
    + dependency_discount * 0.3
    + evidence_quality_factor * 0.2
)
```

---

## 四、维度评估流程

### 4.1 Agent 推理循环中的维度评估

维度评估嵌入在 ReAct 推理循环的每一步中，与 Evidence 聚合形成双循环：

```
┌─────────────────────────────────────────────────────┐
│  ReAct Step N                                        │
│                                                      │
│  1. Thought: Agent 思考当前分析缺口                   │
│     └── 参考 DimensionTracker.get_weak_dimensions()  │
│                                                      │
│  2. Action: Agent 选择工具调用                        │
│     └── 优先选择弱维度对应的工具                       │
│                                                      │
│  3. Observation: 工具返回结果                         │
│     └── 结果解析为 Evidence                           │
│                                                      │
│  4. Evidence Aggregation:                            │
│     ├── EvidenceCollector.add(evidence)              │
│     ├── DimensionTracker.add_evidence(dim, ev_id)    │
│     └── DimensionTracker.update_status(dim)          │
│                                                      │
│  5. Dimension Assessment:                            │
│     ├── Agent 输出 dimension_status                  │
│     ├── DimensionTracker 校验充分性标准               │
│     └── 发布 DimensionChanged 事件                   │
│                                                      │
│  6. Termination Check:                               │
│     ├── all_sufficient() → 进入报告生成               │
│     ├── max_steps reached → 标记未达标维度为 INSUFFICIENT │
│     └── continue → 进入下一步                        │
└─────────────────────────────────────────────────────┘
```

### 4.2 维度评估与 Evidence 的交互

Evidence 和 Dimension 是双向关联的：

```
Evidence ──关联──→ Dimension（evidence.dimensions 字段）
Dimension ──引用──→ Evidence（dimension.evidence_ids 字段）
```

**交互流程**：

1. Agent 通过工具调用获取信息，生成 Evidence
2. Evidence 的 `dimensions` 字段标记其支撑的维度
3. `DimensionTracker.add_evidence(dimension_id, evidence_id)` 建立反向引用
4. `DimensionTracker.update_status(dimension_id)` 基于证据数量和充分性标准自动校验状态
5. Agent 的 `dimension_status` 输出作为参考，但不直接决定维度状态（需经过充分性校验）

### 4.3 弱维度检测和补充策略

**弱维度定义**：status 为 PENDING、IN_PROGRESS 或 INSUFFICIENT 的维度。

**检测时机**：

- 每步推理结束后
- Context Pipeline 的 Collect 阶段（用于决定注入哪些上下文）
- 报告生成前（用于标注分析覆盖度）

**补充策略**：

| 策略 | 说明 | 触发条件 |
|------|------|---------|
| 优先工具推荐 | 根据弱维度推荐对应的工具集 | 每步推理开始时 |
| 上下文倾斜 | Context Pipeline 为弱维度分配更多 Token 预算 | Collect 阶段 |
| 依赖维度优先 | 优先补充被依赖的维度（如 understanding 优先于 decision） | 弱维度包含 understanding 时 |
| 降级接受 | 当 max_steps 即将耗尽时，接受 IN_PROGRESS 状态为最终状态 | step_count >= max_steps - 2 |

**工具-维度推荐映射**：

| 维度 | 推荐工具 |
|------|---------|
| understanding | get_terminology, search_requirements, get_project_profile |
| impact | search_code, list_modules, get_dependencies |
| risk | read_file, search_code, get_contributors |
| change | search_code, read_file, get_dependencies |
| decision | read_file, get_project_profile |
| evidence | （元维度，通过补充其他维度的证据间接提升） |
| verification | read_file, search_code |

### 4.4 维度评估的阶段推进

V1 的 4 阶段推进模型在 V2 中保留并增强：

| 阶段 | 目标维度 | 进入条件 | 退出条件 |
|------|---------|---------|---------|
| 理解阶段 | understanding | Session 启动 | understanding >= IN_PROGRESS |
| 范围阶段 | impact, evidence | understanding >= IN_PROGRESS | impact >= IN_PROGRESS |
| 评估阶段 | risk, change | impact >= IN_PROGRESS | risk >= IN_PROGRESS AND change >= IN_PROGRESS |
| 决策阶段 | decision, verification | risk >= IN_PROGRESS AND change >= IN_PROGRESS | decision >= IN_PROGRESS |

> 阶段推进是软引导而非硬约束。Agent 可以跨阶段工作，但 Context Pipeline 会根据当前阶段调整上下文权重。

---

## 五、维度聚合与报告

### 5.1 聚合策略

V2 采用**混合策略**聚合 7 维度结果为整体风险等级：

```
overall_risk = max(
    weighted_average_risk,
    weakest_dimension_risk
)
```

**设计理由**：

- 加权平均反映整体分析覆盖度
- 最弱维度决定确保短板不被平均值掩盖
- 取两者中较高者，保证风险不被低估

### 5.2 加权平均计算

```python
DIMENSION_WEIGHTS = {
    "understanding": 1.2,
    "impact": 1.0,
    "risk": 1.1,
    "change": 0.9,
    "decision": 0.9,
    "evidence": 1.0,
    "verification": 0.8,
}

def compute_weighted_risk(dimension_states: dict[str, DimensionState]) -> float:
    risk_score_map = {
        RiskLevel.LOW: 0.2,
        RiskLevel.MEDIUM: 0.5,
        RiskLevel.HIGH: 0.8,
        RiskLevel.CRITICAL: 1.0,
    }
    total_weight = 0.0
    weighted_sum = 0.0
    for dim_id, state in dimension_states.items():
        weight = DIMENSION_WEIGHTS.get(dim_id, 1.0)
        risk_score = risk_score_map[state.risk_level]
        weighted_sum += weight * risk_score
        total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else 0.8
```

### 5.3 整体风险等级映射

| 加权风险分数 | 整体风险等级 | 报告标注 |
|------------|------------|---------|
| 0.0 - 0.25 | LOW | 分析覆盖完整，风险可控 |
| 0.25 - 0.50 | MEDIUM | 部分维度未达标，建议关注 |
| 0.50 - 0.75 | HIGH | 多个维度未达标，结论仅供参考 |
| 0.75 - 1.0 | CRITICAL | 分析覆盖严重不足，结论不可信 |

### 5.4 报告中各维度的展示逻辑

| 报告章节 | 主要维度 | 展示内容 |
|---------|---------|---------|
| 需求理解 | understanding | 核心目标、术语清单、歧义标注 |
| 影响分析 | impact | 受影响模块列表、依赖链、影响等级 |
| 风险评估 | risk | 结构化风险条目、严重度、缓解建议 |
| 变更评估 | change | 变更点列表、变更类型、复杂度 |
| 决策建议 | decision | 推荐方案、替代方案、trade-off、开放问题 |
| 证据溯源 | evidence | 证据清单、来源分布、覆盖度热力图 |
| 验证要点 | verification | 可执行验证要点、测试建议、验收标准 |
| 维度总览 | 全部 | 7 维度状态雷达图、整体风险等级 |

---

## 六、维度与 L3 的关系

### 6.1 沉淀映射

| 维度 | 可沉淀到 L3 的知识类型 | 沉淀触发条件 | 数据转换 |
|------|---------------------|------------|---------|
| understanding | 术语表 | 发现新术语或已有术语的新别名 | `evaluation_questions` 中 Q2 的回答 → glossary append |
| understanding | 需求谱系 | 识别到需求间的派生/冲突关系 | 依赖关系 → requirement_lineage append |
| impact | 模块画像 | 识别到模块的新影响记录 | 受影响模块 + 影响理由 → module_profiles update |
| risk | 风险演化 | 识别到新风险或已有风险的状态变化 | 结构化风险条目 → risks append + risk_fingerprint 归并 |
| risk | 架构约束 | 发现架构约束违反 | constraint 类型证据 → constraints append |
| change | 模块画像 | 识别到模块的变更频率/复杂度更新 | 变更评估 → module_profiles update（变更历史追加） |
| decision | 决策记录 | 生成决策建议 | 决策建议 + 上下文 → decisions append |
| evidence | 架构约束 | 发现新的约束类型证据 | constraint 类型证据 → constraints append |
| verification | 事故记忆 | 验证要点涉及历史事故场景 | 验证场景 + 历史事故 → incidents append |

### 6.2 沉淀触发条件

沉淀由 index-service 在 Session 完成后执行，触发条件为 Session 进入 COMPLETED 状态：

```
Session COMPLETED
    │
    ▼
index-service 从 L2 提取 DimensionState
    │
    ├── 遍历每个维度的 assessment_summary 和 evaluation_questions
    ├── 识别可沉淀的结构化知识
    ├── 通过 L3Writer Protocol 写入 L3
    └── 记录 knowledge_changelog
```

### 6.3 数据转换规则

**understanding → 术语表**：

```python
def extract_glossary_from_understanding(state: DimensionState) -> list[dict]:
    terms = []
    for question_id, answer in state.evaluation_questions.items():
        if question_id == "Q2" and answer:
            for term_entry in parse_term_answer(answer):
                terms.append({
                    "canonical_name": term_entry.name,
                    "definition": term_entry.definition,
                    "aliases": term_entry.aliases,
                    "confidence": state.confidence_score,
                    "evidence_ref": state.evidence_ids,
                })
    return terms
```

**risk → 风险演化**：

```python
def extract_risks_from_dimension(state: DimensionState) -> list[dict]:
    risks = []
    if state.assessment_summary:
        for risk_item in parse_risk_summary(state.assessment_summary):
            risk_item["risk_fingerprint"] = compute_risk_fingerprint(risk_item)
            risk_item["confidence"] = state.confidence_score
            risk_item["evidence_ref"] = state.evidence_ids
            risks.append(risk_item)
    return risks
```

**decision → 决策记录**：

```python
def extract_decisions_from_dimension(state: DimensionState) -> list[dict]:
    decisions = []
    if state.assessment_summary:
        for decision_item in parse_decision_summary(state.assessment_summary):
            decision_item["confidence"] = state.confidence_score
            decision_item["evidence_ref"] = state.evidence_ids
            decisions.append(decision_item)
    return decisions
```

### 6.4 沉淀置信度继承

维度评估结果沉淀到 L3 时，知识的初始 `confidence_score` 继承自维度的 `confidence_score`，并受依赖维度折扣影响：

| 场景 | 初始 confidence_score |
|------|---------------------|
| understanding 维度 SUFFICIENT 且 confidence=0.8 | 沉淀知识 confidence=0.8 |
| risk 维度 SUFFICIENT 但 understanding 仅为 IN_PROGRESS | 沉淀知识 confidence=0.8 * 0.7=0.56 |
| 任何维度 INSUFFICIENT | 该维度的评估结果不沉淀（置信度不足） |

---

## 七、存储设计

### 7.1 PostgreSQL `dimension_results` 表结构

```sql
CREATE TABLE dimension_results (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES cognitive_sessions(id),
    dimension_id    VARCHAR(32) NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'pending',
    risk_level      VARCHAR(16) NOT NULL DEFAULT 'high',
    confidence_score FLOAT NOT NULL DEFAULT 0.0
                        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    evidence_ids    JSONB NOT NULL DEFAULT '[]',
    assessment_summary TEXT,
    evaluation_questions JSONB NOT NULL DEFAULT '{}',
    sufficient_criteria_met   JSONB NOT NULL DEFAULT '[]',
    sufficient_criteria_unmet JSONB NOT NULL DEFAULT '[]',
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_dimension_result_session_dim
        UNIQUE (session_id, dimension_id),
    CONSTRAINT chk_dimension_status
        CHECK (status IN ('pending', 'in_progress', 'sufficient', 'insufficient')),
    CONSTRAINT chk_risk_level
        CHECK (risk_level IN ('low', 'medium', 'high', 'critical'))
);
```

### 7.2 索引策略

| 索引 | 类型 | 用途 |
|------|------|------|
| `uq_dimension_result_session_dim` | UNIQUE | 保证每个 Session 每个维度只有一条记录 |
| `ix_dimension_results_session_id` | B-tree | 按 Session 查询所有维度结果 |
| `ix_dimension_results_status` | B-tree | 按状态筛选（如查找所有 INSUFFICIENT 维度） |
| `ix_dimension_results_risk_level` | B-tree | 按风险等级筛选 |
| `ix_dimension_results_dimension_id` | B-tree | 按维度 ID 查询（跨 Session 聚合） |

```sql
CREATE INDEX ix_dimension_results_session_id ON dimension_results (session_id);
CREATE INDEX ix_dimension_results_status ON dimension_results (status);
CREATE INDEX ix_dimension_results_risk_level ON dimension_results (risk_level);
CREATE INDEX ix_dimension_results_dimension_id ON dimension_results (dimension_id);
```

### 7.3 与 Checkpoint 的关系

DimensionState 是 Checkpoint 热状态的一部分：

```json
{
    "checkpoint_id": "uuid",
    "session_id": "uuid",
    "version": 42,
    "hot_state": {
        "agent_state": { ... },
        "evidence_state": { ... },
        "dimension_state": {
            "understanding": {
                "dimension_id": "understanding",
                "status": "in_progress",
                "evidence_ids": ["ev-001", "ev-003"],
                "risk_level": "medium",
                "confidence_score": 0.55,
                "assessment_summary": null,
                "last_updated_at": "2026-06-01T10:30:00Z"
            },
            "impact": { ... },
            "risk": { ... },
            "change": { ... },
            "decision": { ... },
            "evidence": { ... },
            "verification": { ... }
        }
    }
}
```

---

## 八、接口定义

### 8.1 DimensionTracker V2 接口

```python
class DimensionTracker:
    """七维度状态管理器 V2"""

    def __init__(
        self,
        dimensions: list[str] | None = None,
        weights: dict[str, float] | None = None,
        sufficiency_criteria: dict[str, list[str]] | None = None,
    ): ...

    def mark_in_progress(self, dimension_id: str) -> None:
        """将维度标记为 IN_PROGRESS（仅 PENDING → IN_PROGRESS 有效）"""

    def mark_sufficient(self, dimension_id: str) -> None:
        """将维度标记为 SUFFICIENT（需经过充分性校验）"""

    def mark_insufficient(self, dimension_id: str) -> None:
        """将维度标记为 INSUFFICIENT（仅分析终止时调用）"""

    def add_evidence(self, dimension_id: str, evidence_id: str) -> None:
        """向维度添加证据引用（去重）"""

    def update_assessment(
        self,
        dimension_id: str,
        summary: str,
        evaluation_questions: dict[str, str],
    ) -> None:
        """更新维度的评估小结和引导问题回答"""

    def check_sufficiency(self, dimension_id: str) -> bool:
        """检查维度是否满足充分性标准"""

    def get_weak_dimensions(self) -> list[str]:
        """获取弱维度列表（PENDING/IN_PROGRESS/INSUFFICIENT）"""

    def get_weak_dimensions_sorted(self) -> list[str]:
        """获取按依赖优先级排序的弱维度列表"""

    def all_sufficient(self) -> bool:
        """所有维度是否均已达标"""

    def compute_overall_risk(self) -> tuple[RiskLevel, float]:
        """计算整体风险等级和加权风险分数"""

    def get_status_summary(self) -> dict[str, str]:
        """获取各维度状态摘要"""

    def get_dimension_detail(self, dimension_id: str) -> DimensionState | None:
        """获取指定维度的完整状态"""

    def apply_dependency_discount(self) -> None:
        """根据依赖维度状态调整置信度折扣"""

    def finalize(self) -> None:
        """分析终止时，将所有 PENDING/IN_PROGRESS 维度标记为 INSUFFICIENT"""

    def to_snapshot(self) -> dict:
        """序列化为快照（用于 Checkpoint）"""

    def from_snapshot(self, snapshot: dict) -> None:
        """从快照恢复"""

    def to_db_records(self, session_id: str) -> list[dict]:
        """转换为数据库记录格式"""

    def from_db_records(self, records: list[dict]) -> None:
        """从数据库记录恢复"""
```

### 8.2 维度查询 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/sessions/{session_id}/dimensions` | 获取 Session 的所有维度状态 |
| GET | `/api/v2/sessions/{session_id}/dimensions/{dimension_id}` | 获取指定维度详情 |
| GET | `/api/v2/sessions/{session_id}/dimensions/summary` | 获取维度状态摘要和整体风险等级 |
| GET | `/api/v2/sessions/{session_id}/dimensions/radar` | 获取雷达图数据（维度+置信度） |
| GET | `/api/v2/projects/{project_id}/dimensions/history` | 获取项目维度的跨 Session 历史趋势 |

**响应示例**：

```json
GET /api/v2/sessions/{session_id}/dimensions/summary

{
    "session_id": "uuid",
    "dimensions": {
        "understanding": {"status": "sufficient", "risk_level": "low", "confidence": 0.85},
        "impact": {"status": "sufficient", "risk_level": "low", "confidence": 0.72},
        "risk": {"status": "in_progress", "risk_level": "medium", "confidence": 0.55},
        "change": {"status": "in_progress", "risk_level": "medium", "confidence": 0.48},
        "decision": {"status": "pending", "risk_level": "high", "confidence": 0.0},
        "evidence": {"status": "in_progress", "risk_level": "medium", "confidence": 0.60},
        "verification": {"status": "pending", "risk_level": "high", "confidence": 0.0}
    },
    "overall_risk": {
        "level": "high",
        "weighted_score": 0.52,
        "weakest_dimension": "decision",
        "sufficient_count": 2,
        "total_count": 7
    }
}
```

---

## 九、配置参数

### 9.1 维度配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dimensions.enabled` | list[str] | 7 个标准维度 | 启用的维度列表（可自定义） |
| `dimensions.weights` | dict[str, float] | 见 5.2 节 | 各维度权重 |
| `dimensions.sufficiency_criteria` | dict[str, list[str]] | 见各维度定义 | 各维度的充分性标准描述 |

### 9.2 阈值配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dimensions.min_evidence_for_sufficient` | int | 2 | 维度达标所需最少证据数 |
| `dimensions.min_source_types` | int | 2 | evidence 维度达标所需最少来源类型数 |
| `dimensions.confidence_threshold` | float | 0.6 | 维度评估置信度阈值（低于此值标记为低置信度） |
| `dimensions.dependency_discount_factor` | float | 0.7 | 依赖维度未达标时的置信度折扣因子 |
| `dimensions.stale_step_threshold` | int | 3 | 连续多少步某维度无新证据时触发弱维度提醒 |

### 9.3 聚合配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `aggregation.strategy` | str | "hybrid" | 聚合策略：weighted_average / weakest_dimension / hybrid |
| `aggregation.risk_thresholds` | dict | 见 5.3 节 | 风险分数到等级的映射阈值 |

### 9.4 Scope x Domain 配置矩阵

维度配置支持 Scope 层级覆盖：

| Scope | 可配置项 | 说明 |
|-------|---------|------|
| SYSTEM | 全部默认值 | 系统级默认 |
| PROJECT | weights, sufficiency_criteria | 项目可自定义维度权重和充分性标准 |
| USER | 无 | 维度配置不对用户开放 |
| SESSION | 无 | 维度配置不对单次会话开放 |

---

## 十、与其他模块的关系

| 模块 | 关系 | 交互方式 |
|------|------|---------|
| **M-01 Evidence Model** | Evidence 是 Dimension 的输入 | Evidence.dimensions 标记支撑的维度；Dimension.evidence_ids 引用证据 |
| **M-03 Project Cognitive State** | Dimension 结果沉淀到 L3 | Session 完成后，维度评估结果通过 L3Writer 沉淀为术语表/风险演化/决策记录等 |
| **R-01 Session** | Dimension 是 Session 的子状态 | DimensionState 存储在 Checkpoint 热状态中；Session 终止时触发 DimensionTracker.finalize() |
| **R-02 Context Pipeline** | Dimension 状态影响上下文选择 | Collect 阶段参考弱维度决定上下文权重；Score 阶段为弱维度分配更多预算 |
| **R-03 Event Stream** | Dimension 状态变更产生事件 | 状态转换时发布 DimensionChanged 事件 |
| **R-05 Checkpoint** | DimensionState 是 Checkpoint 的一部分 | Checkpoint 热状态包含完整 DimensionState 快照 |
| **I-01 服务间 API** | cognitive-rt → index-service | 维度结果持久化由 cognitive-rt 写入，L3 沉淀由 index-service 执行 |

**交互时序**：

```
cognitive-rt                          index-service
    │                                      │
    │  ReAct Step                          │
    │  ├── Agent 评估 dimension_status     │
    │  ├── DimensionTracker 校验           │
    │  ├── 发布 DimensionChanged Event     │
    │  └── 写入 dimension_results          │
    │                                      │
    │  Session COMPLETED                   │
    │──────────────────────────────────────>│
    │  请求 L3 沉淀                        │
    │                                      │
    │                                      │  从 L2 提取维度结果
    │                                      │  ├── understanding → 术语表
    │                                      │  ├── risk → 风险演化
    │                                      │  ├── decision → 决策记录
    │                                      │  └── 记录 changelog
    │<──────────────────────────────────────│
    │  沉淀完成确认                         │
```

---

## 十一、测试策略

### 11.1 单元测试

| 测试类 | 覆盖范围 |
|--------|---------|
| TestDimensionState | 状态转换规则、置信度计算、充分性校验 |
| TestDimensionTracker | 维度管理、弱维度检测、聚合计算、快照序列化/反序列化 |
| TestDimensionDependency | 依赖维度折扣、优先级排序 |
| TestDimensionAggregation | 加权平均、最弱维度决定、混合策略、风险等级映射 |
| TestSufficiencyCriteria | 各维度的充分性标准校验逻辑 |

### 11.2 集成测试

| 测试场景 | 说明 |
|---------|------|
| 维度状态随推理步骤推进 | 模拟 ReAct 循环，验证维度从 PENDING → IN_PROGRESS → SUFFICIENT 的完整流程 |
| Evidence 添加驱动维度更新 | 添加不同类型证据，验证维度状态和置信度的变化 |
| 依赖维度折扣生效 | understanding 为 PENDING 时，验证其他维度的置信度折扣 |
| 分析终止时 finalize | 验证 PENDING/IN_PROGRESS 维度正确标记为 INSUFFICIENT |
| Checkpoint 恢复后维度状态一致 | 从 Checkpoint 恢复后，验证维度状态与快照一致 |
| 维度结果持久化到 PG | 验证 to_db_records / from_db_records 的正确性 |

### 11.3 端到端测试

| 测试场景 | 说明 |
|---------|------|
| 完整分析流程的维度覆盖 | 上传需求 → 分析完成 → 验证 7 维度状态和整体风险等级 |
| L3 沉淀验证 | 分析完成后，验证维度结果正确沉淀到 L3 对应知识类型 |
| Chatback 补充分析 | 验证 Chatback 中新证据驱动维度状态从 INSUFFICIENT → IN_PROGRESS |

### 11.4 测试覆盖边界

每个维度相关接口必须覆盖：

| 边界 | 说明 |
|------|------|
| 成功路径 | 维度正常推进到 SUFFICIENT |
| 未达标路径 | 分析终止时维度仍为 PENDING/IN_PROGRESS |
| 依赖折扣 | understanding 未达标时其他维度的置信度折扣 |
| 充分性校验拒绝 | Agent 声明 sufficient 但证据不足时拒绝转换 |
| 快照一致性 | to_snapshot / from_snapshot 往返一致 |
| 自定义维度 | 使用非标准维度列表时的行为 |
| 空证据 | 无任何证据时各维度的默认状态和风险等级 |

---

## 十二、明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| 动态维度发现 | 不做 | 维度列表由配置决定，不在运行时动态增减 |
| 维度间权重自动调整 | 不做 | 权重由配置决定，不做运行时自适应 |
| 跨项目维度对比 | Phase 1 不做 | 先在单项目内验证维度评估的准确性 |
| 维度评估结果直接驱动自动化操作 | 不做 | 维度评估仅产出认知结论，不触发代码修改或部署 |
| L3-B 模式层的维度抽象 | Phase 1 不做 | 先完成 L3-A 的事实沉淀，再抽象模式 |
| 维度评估的 A/B 测试框架 | Phase 1 不做 | 先建立基础评估能力，后续按需引入 |
| 自定义维度的充分性标准自动推导 | 不做 | 自定义维度的充分性标准必须由用户显式配置 |
| 维度评估结果的自动回滚 | 不做 | 维度状态转换是追加式的，不回滚到历史状态 |

---

## 十三、V1 到 V2 的迁移要点

| V1 概念 | V2 对应 | 迁移说明 |
|---------|---------|---------|
| `DimensionState(id, status, evidence_ids, draft_content)` | `DimensionState(dimension_id, status, evidence_ids, risk_level, assessment_summary, confidence_score, ...)` | 新增 risk_level、confidence_score、evaluation_questions 等字段；draft_content 更名为 assessment_summary |
| `DimensionTracker` (内存 dataclass) | `DimensionTracker` V2 (Pydantic + PG 持久化) | 接口兼容扩展，新增 check_sufficiency、compute_overall_risk、finalize 等方法 |
| `STEP_OUTPUT_SCHEMA.dimension_status` (3 状态) | `DimensionStatus` (4 状态 + PENDING) | 新增 PENDING 状态；insufficient 仅在分析终止时设置 |
| Agent 自报 dimension_status | Agent 评估 + DimensionTracker 校验 | Agent 的 dimension_status 作为参考输入，不直接决定维度状态 |
| 无聚合 | 混合策略聚合 | 新增整体风险等级计算 |
| 无 L3 沉淀 | 维度结果沉淀到 L3 | 新增沉淀映射和触发机制 |
| 内存 JSON blob | PostgreSQL dimension_results 表 | 新增持久化存储 |

---

## 十四、术语规范

| 术语 | 定义 |
|------|------|
| Dimension | 分析维度，需求分析应覆盖的认知视角 |
| DimensionState | 单个维度的评估状态，包含状态、证据、风险等级、置信度等 |
| DimensionStatus | 维度的评估进度枚举（PENDING/IN_PROGRESS/SUFFICIENT/INSUFFICIENT） |
| RiskLevel | 维度的风险等级枚举（LOW/MEDIUM/HIGH/CRITICAL） |
| Weak Dimension | 弱维度，状态为 PENDING/IN_PROGRESS/INSUFFICIENT 的维度 |
| Sufficiency Criteria | 充分性标准，维度达标所需满足的条件清单 |
| Dependency Discount | 依赖维度折扣，前置维度未达标时对后续维度置信度的折扣 |
| Overall Risk | 整体风险等级，7 维度聚合后的综合风险评级 |
