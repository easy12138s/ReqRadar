# M-01 Evidence Model（证据模型）详细设计

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | L2 分析记录核心载体——Evidence 的数据模型、生命周期、证据链与沉淀规则的详细设计 |
| 前置文档 | 00_PROJECT_POSITIONING.md（项目宪法）、01_RESTRUCTURE_OVERVIEW.md（Runtime 蓝图）、03_COGNITIVE_ASSET_MODEL.md（认知资产模型） |
| 核心目标 | 定义 Evidence 如何作为"可追溯的工程认知单元"，使 AI 的每一条输出都具备可验证的来源链路 |
| 文档职责 | What & How — Evidence 是什么、长什么样、怎么流转、怎么沉淀；为 cognitive-rt 的 Evidence Aggregation 和 index-service 的 L3 沉淀提供实现基线 |

---

## 一、概述

### 1.1 Evidence 在 V2 中的定位

ReqRadar 的核心原则是 **"AI 不是回答，AI 是可验证认知"**。这条原则的技术保障就是 Evidence System。

在 V2 四层认知资产模型中，Evidence 属于 **L2（Analysis Records）** 层，是分析记录的核心载体：

```
L0 Raw Context     →  Evidence 的最终溯源锚点（不可变档案馆）
L1 Structured Facts →  Evidence 的直接引用来源（可索引图书馆）
L2 Analysis Records →  Evidence 的产生与存储层（实验记录本）  ★ 本文档
L3 Persistent Knowledge →  Evidence 的沉淀目标（认知大脑）
```

**Evidence 不是日志，不是中间变量，不是可选的附属品。** 它是 ReqRadar 输出"可验证认知"的工程基础——每一条分析结论都必须有一条或多条 Evidence 支撑，每条 Evidence 都必须能追溯到 L0/L1 的原始材料。

### 1.2 V1 → V2 的核心升级

| 维度 | V1 | V2 |
|------|----|----|
| 数据结构 | dataclass，内存列表 | Pydantic v2 模型，PostgreSQL 持久化 |
| 证据类型 | 5 种（code_match, module_summary, project_context, requirement_text, inference） | 10 种，覆盖 L0/L1 全部来源及推理产物 |
| 置信度 | 3 级离散（low/medium/high） | 0.0-1.0 浮点数 + 离散等级映射 |
| 生命周期 | 无状态机 | discovered → verified → challenged → superseded → deprecated |
| 证据间关系 | 无 | Evidence Chain：SUPPORTS / CONTRADICTS / DERIVED_FROM / SUPERSEDES / CORROBORATES |
| 来源追溯 | source 字符串 | 结构化 source_ref，指向 L0/L1 记录 |
| 维度关联 | dimensions 列表 | 结构化 dimension_refs，含权重和评估角色 |
| L3 沉淀 | 无 | 按类型和置信度自动沉淀到 L3 知识 |
| 持久化 | JSON 快照（嵌入 ReportVersion.context_snapshot） | 独立 evidence_records 表 + evidence_relations 表 |
| 查询能力 | 内存过滤 | SQL 多维度查询 + 索引优化 |

---

## 二、核心概念

### 2.1 Evidence 的本质：可追溯的工程认知单元

Evidence 是 Agent 在推理过程中产生的、经过验证的、可追溯到原始材料的工程认知单元。它回答三个核心问题：

1. **发现了什么？** — Evidence 的 content 和 type
2. **从哪里发现的？** — Evidence 的 source_ref，指向 L0/L1 记录
3. **有多可信？** — Evidence 的 confidence 和 status

**核心约束**：每条 Evidence 必须满足以下条件之一，否则不应被创建：

- 拥有指向 L0 Raw Context 的引用（`source_ref.context_kind` 为 SOURCE_CODE / REQUIREMENT / ARCH_DOC / GIT_HISTORY）
- 拥有指向 L1 Structured Facts 的引用（`source_ref.context_kind` 为 MEMORY）
- 明确标记为推理产物并附带推理链路（`source_ref.context_kind` 为 INFERRED_KNOWLEDGE，且 `source_ref.inference_chain` 非空）

### 2.2 Evidence Chain（证据链）

Evidence 不是孤立存在的。证据之间存在五种关系，构成证据链：

| 关系类型 | 含义 | 典型场景 |
|---------|------|---------|
| SUPPORTS | A 证据支撑 B 证据的结论 | 代码匹配证据支撑影响范围判断 |
| CONTRADICTS | A 证据与 B 证据矛盾 | 新的 Git 历史证据与旧的架构文档矛盾 |
| DERIVED_FROM | A 证据由 B 证据派生而来 | 推理证据从代码证据派生 |
| SUPERSEDES | A 证据替代 B 证据（B 已过时） | 新版本代码证据替代旧版本 |
| CORROBORATES | A 证据与 B 证据相互印证 | 两个独立来源的证据指向同一结论 |

证据链的核心价值：

- **可追溯性**：从任何结论出发，沿证据链可以回溯到原始材料
- **矛盾检测**：CONTRADICTS 关系使系统能识别推理中的冲突
- **置信度传播**：SUPPORTS / CORROBORATES 关系可以提升结论的置信度
- **报告生成**：证据链是报告"结论-推理-来源"三级结构的数据基础

### 2.3 Evidence 与 ContextKind 的关系

Evidence 的来源通过 `ContextKind` 枚举标识，与认知资产模型的上下文权重体系对齐：

| ContextKind | 基础权重 | Evidence 含义 | L0/L1 引用方式 |
|-------------|---------|--------------|---------------|
| SOURCE_CODE | 1.0 | 从代码中提取的事实 | `l1://modules/{module_id}` 或 `l1://chunks/{chunk_id}` |
| REQUIREMENT | 0.95 | 从需求文档中提取的事实 | `l1://chunks/{chunk_id}?offset={n}&length={m}` |
| ARCH_DOC | 0.9 | 从架构文档中提取的事实 | `l1://chunks/{chunk_id}` |
| GIT_HISTORY | 0.7 | 从 Git 历史中提取的事实 | `l1://commits/{commit_id}` |
| MEMORY | 0.6 | 从 L3 项目记忆中提取的事实 | `l3://{knowledge_type}/{knowledge_id}` |
| INFERRED_KNOWLEDGE | 0.4 | Agent 推理产生的结论 | 无外部引用，必须附带 `inference_chain` |

**关键约束**：INFERRED_KNOWLEDGE 类型的 Evidence 不能作为唯一证据支撑高置信度结论。任何 confidence > 0.7 的结论必须至少有一条非 INFERRED_KNOWLEDGE 类型的 Evidence 支撑。

---

## 三、数据模型

### 3.1 EvidenceType 枚举

```python
from enum import StrEnum


class EvidenceType(StrEnum):
    code_evidence = "code_evidence"
    requirement_ref = "requirement_ref"
    architecture_doc = "architecture_doc"
    git_history = "git_history"
    memory_ref = "memory_ref"
    tool_output = "tool_output"
    inference = "inference"
    constraint = "constraint"
    risk_indicator = "risk_indicator"
    verification_result = "verification_result"
```

| 类型 | 含义 | ContextKind 映射 | 典型来源 |
|------|------|-----------------|---------|
| `code_evidence` | 代码结构/依赖/实现事实 | SOURCE_CODE | code_parser, search_code 工具 |
| `requirement_ref` | 需求文档原文引用 | REQUIREMENT | doc_reader, chunk 检索 |
| `architecture_doc` | 架构文档/设计文档引用 | ARCH_DOC | doc_reader, chunk 检索 |
| `git_history` | Git 提交/分支/变更历史 | GIT_HISTORY | git_analyzer, get_git_history 工具 |
| `memory_ref` | L3 项目记忆引用 | MEMORY | index-service 记忆查询 |
| `tool_output` | 工具执行的原始输出 | 按工具映射（见下表） | ToolRuntime 工具返回 |
| `inference` | Agent 推理产生的结论 | INFERRED_KNOWLEDGE | ReAct Thought 步骤 |
| `constraint` | 架构约束/设计规则 | 视来源而定 | 从代码/文档/记忆中识别 |
| `risk_indicator` | 风险指标/信号 | 视来源而定 | 风险分析步骤 |
| `verification_result` | 验证结果（自动/人工） | 视来源而定 | 验证步骤 |

**tool_output 的 ContextKind 映射规则**：

tool_output 类型的 Evidence，其 ContextKind 根据产生该输出的工具动态确定：

| 工具 | ContextKind 映射 | 说明 |
|------|-----------------|------|
| search_code | SOURCE_CODE | 代码搜索结果 |
| get_dependencies | SOURCE_CODE | 依赖关系 |
| read_file | SOURCE_CODE | 文件内容 |
| get_git_history | GIT_HISTORY | Git 历史 |
| doc_reader | REQUIREMENT / ARCH_DOC | 按文档类型区分 |
| memory_query | MEMORY | L3 记忆查询 |

映射规则在 `ToolCapability` 声明中通过 `output_context_kind` 字段定义（默认为 SOURCE_CODE）。未声明的工具，tool_output 的 ContextKind 默认为 SOURCE_CODE。

### 3.2 EvidenceConfidence 模型

V2 将置信度从 3 级离散值升级为 0.0-1.0 浮点数，同时保留离散等级映射以兼容人类可读性：

```python
from enum import StrEnum
from pydantic import BaseModel, Field


class ConfidenceLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    very_high = "very_high"


CONFIDENCE_LEVEL_RANGES: dict[ConfidenceLevel, tuple[float, float]] = {
    ConfidenceLevel.low: (0.0, 0.3),
    ConfidenceLevel.medium: (0.3, 0.6),
    ConfidenceLevel.high: (0.6, 0.85),
    ConfidenceLevel.very_high: (0.85, 1.0),
}


def score_to_level(score: float) -> ConfidenceLevel:
    for level, (low, high) in CONFIDENCE_LEVEL_RANGES.items():
        if low <= score < high:
            return level
    return ConfidenceLevel.very_high


class EvidenceConfidence(BaseModel):
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="置信度评分，0.0-1.0 浮点数",
    )
    level: ConfidenceLevel = Field(
        description="离散置信度等级，由 score 自动计算",
    )
    basis: str = Field(
        default="",
        description="置信度评估依据，说明为什么给出这个评分",
    )

    @classmethod
    def from_score(cls, score: float, basis: str = "") -> "EvidenceConfidence":
        return cls(
            score=score,
            level=score_to_level(score),
            basis=basis,
        )
```

**置信度初始赋值规则**：

| EvidenceType | 默认 score | 说明 |
|-------------|-----------|------|
| code_evidence | 0.85 | 代码即事实，高可信 |
| requirement_ref | 0.9 | 需求原文，最高可信 |
| architecture_doc | 0.8 | 架构文档，高可信 |
| git_history | 0.7 | 历史事实，中等偏高 |
| memory_ref | 0.5 | L3 记忆，需 confidence 兜底 |
| tool_output | 0.6 | 工具输出，中等可信 |
| inference | 0.3 | 推理产物，低可信起点 |
| constraint | 0.7 | 约束识别，中等偏高 |
| risk_indicator | 0.5 | 风险指标，中等 |
| verification_result | 0.8 | 验证结果，高可信 |

### 3.3 EvidenceStatus 枚举

```python
class EvidenceStatus(StrEnum):
    discovered = "discovered"
    verified = "verified"
    challenged = "challenged"
    superseded = "superseded"
    deprecated = "deprecated"
```

| 状态 | 含义 | 可转换到 | 置信度影响 |
|------|------|---------|-----------|
| `discovered` | 刚发现，尚未验证 | verified, challenged, deprecated | 保持初始值 |
| `verified` | 已通过自动或人工验证 | challenged, superseded | +0.1（自动验证）/ +0.15（人工验证） |
| `challenged` | 被其他证据质疑 | verified, deprecated | -0.2 |
| `superseded` | 被更新的证据替代 | deprecated | 冻结，不再参与推理 |
| `deprecated` | 已废弃 | 无（终态） | 冻结，不再参与推理 |

### 3.4 EvidenceRelationType 枚举

```python
class EvidenceRelationType(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DERIVED_FROM = "DERIVED_FROM"
    SUPERSEDES = "SUPERSEDES"
    CORROBORATES = "CORROBORATES"
```

### 3.5 SourceRef 数据模型

```python
from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    context_kind: str = Field(
        description="上下文类型：SOURCE_CODE/REQUIREMENT/ARCH_DOC/GIT_HISTORY/MEMORY/INFERRED_KNOWLEDGE",
    )
    uri: str = Field(
        description="来源引用 URI，格式：l0://{id}、l1://{type}/{id}、l3://{type}/{id}",
    )
    display_name: str = Field(
        default="",
        description="人类可读的来源描述，如 'auth.py:42' 或 '需求文档第3章'",
    )
    inference_chain: list[str] = Field(
        default_factory=list,
        description="推理链路（仅 INFERRED_KNOWLEDGE 类型需要），记录从原始证据到结论的推理步骤 ID",
    )
```

### 3.6 DimensionRef 数据模型

```python
class DimensionRef(BaseModel):
    dimension_id: str = Field(
        description="维度标识：understanding/impact/risk/change/decision/evidence/verification",
    )
    role: str = Field(
        default="supports",
        description="该证据在此维度中的角色：supports（支撑）/ challenges（质疑）/ contextual（背景）",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="该证据对此维度的贡献权重",
    )
```

### 3.7 EvidenceRecord 完整数据模型

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class EvidenceRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: f"ev-{uuid.uuid4().hex[:12]}",
        description="证据唯一标识",
    )
    session_id: str = Field(
        description="所属 CognitiveSession ID",
    )
    type: EvidenceType = Field(
        description="证据类型",
    )
    status: EvidenceStatus = Field(
        default=EvidenceStatus.discovered,
        description="证据状态",
    )
    confidence: EvidenceConfidence = Field(
        description="置信度评估",
    )
    source_ref: SourceRef = Field(
        description="来源引用",
    )
    content: str = Field(
        description="证据内容摘要，200 字以内",
        max_length=200,
    )
    detail: dict = Field(
        default_factory=dict,
        description="证据详情（JSONB），按 type 不同而结构不同",
    )
    dimension_refs: list[DimensionRef] = Field(
        default_factory=list,
        description="关联的分析维度",
    )
    step_id: int | None = Field(
        default=None,
        description="产生该证据的推理步骤编号",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="产生该证据的工具调用 ID（如来自 ToolRuntime）",
    )
    verified_by: str = Field(
        default="",
        description="验证者标识：auto / human:{user_id} / 空（未验证）",
    )
    verified_at: datetime | None = Field(
        default=None,
        description="最近验证时间",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="最后更新时间",
    )
```

### 3.8 EvidenceRelationRecord 数据模型

```python
class EvidenceRelationRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: f"evr-{uuid.uuid4().hex[:12]}",
        description="关系唯一标识",
    )
    session_id: str = Field(
        description="所属 CognitiveSession ID",
    )
    source_evidence_id: str = Field(
        description="源证据 ID",
    )
    target_evidence_id: str = Field(
        description="目标证据 ID",
    )
    relation_type: EvidenceRelationType = Field(
        description="关系类型",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="关系置信度",
    )
    rationale: str = Field(
        default="",
        description="关系建立的理由",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="创建时间",
    )
```

### 3.9 detail 字段结构定义（按 EvidenceType）

`EvidenceRecord.detail` 为 JSONB 字段，按 `type` 不同存储不同结构：

**code_evidence**:

```json
{
  "module_name": "auth",
  "file_path": "src/auth/login.py",
  "line_range": [42, 58],
  "symbol_name": "authenticate_user",
  "symbol_type": "function",
  "code_snippet": "def authenticate_user(...)...",
  "dependencies": ["user_model", "token_service"]
}
```

**requirement_ref**:

```json
{
  "document_id": "doc-abc123",
  "section": "3.2 用户认证",
  "paragraph_index": 4,
  "original_text": "用户登录后需在 30 分钟内...",
  "l0_uri": "l0://raw_context/xyz?offset=1200&length=350"
}
```

**architecture_doc**:

```json
{
  "document_id": "doc-def456",
  "section": "2.1 系统架构",
  "diagram_ref": "l0://raw_context/aaa",
  "key_statement": "支付模块不允许直接访问数据库"
}
```

**git_history**:

```json
{
  "commit_hash": "a1b2c3d",
  "author": "zhangsan",
  "message": "fix: 修复支付回调重复处理",
  "changed_files": ["src/pay/callback.py"],
  "is_revert": false,
  "is_hotfix": true,
  "branch": "hotfix/pay-callback-dup"
}
```

**memory_ref**:

```json
{
  "knowledge_type": "constraint",
  "knowledge_id": "const-789",
  "freshness": "active",
  "l3_confidence": 0.85
}
```

**tool_output**:

```json
{
  "tool_id": "search_code",
  "tool_params": {"query": "authenticate", "top_k": 5},
  "result_summary": "找到 3 个匹配模块",
  "raw_result_uri": "l0://tool_output/xxx"
}
```

**inference**:

```json
{
  "reasoning_step": "Step 5: 风险推理",
  "premise_evidence_ids": ["ev-aaa", "ev-bbb"],
  "conclusion": "支付模块存在并发扣减风险",
  "reasoning_type": "deductive"
}
```

**constraint**:

```json
{
  "constraint_type": "architectural",
  "scope": "payment_module",
  "description": "支付模块不允许直接访问数据库，必须通过 payment-gateway 服务",
  "source_evidence_ids": ["ev-ccc"]
}
```

**risk_indicator**:

```json
{
  "risk_category": "concurrency",
  "severity": "high",
  "affected_modules": ["payment", "points"],
  "indicators": ["无分布式锁", "共享状态可变"],
  "related_incident_ids": []
}
```

**verification_result**:

```json
{
  "verification_type": "automated",
  "verifier": "code_cross_check",
  "passed": true,
  "details": "代码中确实存在 authenticate_user 函数，签名与证据描述一致"
}
```

---

## 四、Evidence 生命周期

### 4.1 状态机

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
             ┌────────────┐                         ┌────────────┐
             │ discovered │ ────── 自动验证 ────────▶│  verified  │
             └──────┬─────┘                         └──────┬─────┘
                    │                                      │
                    │ 被质疑                                │ 被质疑
                    │                                      │
                    ▼                                      ▼
             ┌────────────┐    重新验证通过    ┌────────────┐
             │ challenged │ ────────────────▶│  verified  │
             └──────┬─────┘                   └──────┬─────┘
                    │                               │
                    │ 无法验证                        │ 被替代
                    │                               │
                    ▼                               ▼
             ┌────────────┐                  ┌────────────┐
             │ deprecated │                  │ superseded │
             └────────────┘                  └──────┬─────┘
              （终态）                                │
                                                    │ 过期
                                                    ▼
                                             ┌────────────┐
                                             │ deprecated │
                                             └────────────┘
                                              （终态）
```

### 4.2 状态转换规则

| 转换 | 触发条件 | 副作用 | 置信度变化 |
|------|---------|--------|-----------|
| discovered → verified | 自动验证通过 / 人工确认 | 设置 `verified_by` 和 `verified_at`；发布 `EvidenceVerified` 事件 | +0.1（自动）/ +0.15（人工） |
| discovered → challenged | 发现矛盾证据（CONTRADICTS 关系建立） | 发布 `EvidenceChallenged` 事件 | -0.2 |
| discovered → deprecated | 创建后立即发现错误 | 发布 `EvidenceDeprecated` 事件 | 冻结 |
| verified → challenged | 新发现矛盾证据 | 发布 `EvidenceChallenged` 事件 | -0.2 |
| verified → superseded | 发现更新、更准确的证据（SUPERSEDES 关系建立） | 创建 SUPERSEDES 关系；发布 `EvidenceSuperseded` 事件 | 冻结 |
| challenged → verified | 矛盾解除，重新验证通过 | 更新 `verified_at`；发布 `EvidenceVerified` 事件 | 恢复至验证前值 + 0.1 |
| challenged → deprecated | 矛盾无法解除，或人工判定无效 | 发布 `EvidenceDeprecated` 事件 | 冻结 |
| superseded → deprecated | 替代证据稳定后，被替代证据标记为废弃 | 发布 `EvidenceDeprecated` 事件 | 冻结 |

### 4.3 Evidence 验证规则

#### 4.3.1 自动验证

自动验证在 Evidence 创建后由 cognitive-rt 的 Evidence Aggregation 阶段触发，规则如下：

| EvidenceType | 自动验证条件 | 验证方法 |
|-------------|------------|---------|
| code_evidence | `detail.file_path` 和 `detail.symbol_name` 在 L1 modules 表中存在 | 交叉检查 L1 索引 |
| requirement_ref | `detail.document_id` 和 `detail.l0_uri` 在 L0/L1 中存在 | 引用完整性检查 |
| architecture_doc | `detail.document_id` 在 L0/L1 中存在 | 引用完整性检查 |
| git_history | `detail.commit_hash` 在 L1 commits 表中存在 | 交叉检查 L1 索引 |
| memory_ref | `detail.knowledge_id` 在 L3 中存在且 `freshness=active` | L3 查询验证 |
| tool_output | `detail.tool_id` 在 ToolRuntime 注册表中存在 | 工具注册表检查 |
| inference | `detail.premise_evidence_ids` 中的所有 ID 对应的 Evidence 存在且非 deprecated | 前提证据存在性检查 |
| constraint | 至少有一条非 INFERRED 类型的 Evidence 支撑 | 支撑证据检查 |
| risk_indicator | `detail.affected_modules` 中的模块在 L1 中存在 | 模块存在性检查 |
| verification_result | `detail.verifier` 是已知的验证器 | 验证器注册表检查 |

#### 4.3.2 人工验证

人工验证通过 Chatback 交互或管理界面触发：

- 用户在 Chatback 中确认某条 Evidence 的正确性
- 用户在管理界面标记 Evidence 为 verified
- 人工验证的置信度提升幅度（+0.15）高于自动验证（+0.1）
- 人工验证结果记录在 `verified_by` 字段，格式为 `human:{user_id}`

#### 4.3.3 验证冲突处理

当自动验证与人工验证结果冲突时：

1. 人工验证优先——人工确认的 Evidence 不因自动验证失败而降级
2. 但自动验证失败会记录为 warning 事件，提示用户复核
3. 冲突记录在 `detail.verification_conflicts` 中，供后续审计

---

## 五、Evidence Chain（证据链）

### 5.1 证据间关系的建立规则

| 关系类型 | 建立时机 | 建立规则 |
|---------|---------|---------|
| SUPPORTS | Agent 推理步骤中，新 Evidence 支撑已有结论 | 由 Agent 在 Thought 步骤中显式声明；或由 Evidence Aggregation 自动推断（当两条 Evidence 的 dimension_refs 重叠且结论一致） |
| CONTRADICTS | 发现两条 Evidence 内容冲突 | 由 Agent 在推理中识别；或由自动矛盾检测触发（同维度同 scope 的 Evidence，content 语义矛盾） |
| DERIVED_FROM | 推理产物 Evidence 从原始 Evidence 派生 | inference 类型 Evidence 创建时，`detail.premise_evidence_ids` 中的每条 Evidence 自动建立 DERIVED_FROM 关系 |
| SUPERSEDES | 新 Evidence 替代旧 Evidence | 当新 Evidence 与旧 Evidence 的 `source_ref.uri` 相同但内容更新时自动建立；旧 Evidence 状态转为 superseded |
| CORROBORATES | 两条独立来源的 Evidence 指向同一结论 | 由 Evidence Aggregation 阶段自动检测（不同 ContextKind 的 Evidence，dimension_refs 重叠且结论一致） |

### 5.2 证据链的完整性校验

证据链完整性校验在以下时机触发：

1. **Session 完成时**：对 Session 内所有 Evidence 执行完整性校验
2. **报告生成前**：对报告引用的所有 Evidence 执行完整性校验
3. **L3 沉淀前**：对候选沉淀的 Evidence 执行完整性校验

**校验规则**：

| 规则 | 说明 | 失败处理 |
|------|------|---------|
| 溯源可达 | 非 INFERRED 类型的 Evidence 的 `source_ref.uri` 必须可解析到 L0/L1 记录 | 标记为 challenged，发布 `EvidenceChainBroken` 事件 |
| 推理闭环 | inference 类型 Evidence 的 `detail.premise_evidence_ids` 必须全部存在且非 deprecated | 标记为 challenged，记录缺失的前提 ID |
| 无孤立证据 | 非 discovered 状态的 Evidence 必须至少有一条关系记录 | 降级为 discovered，发布 `EvidenceOrphaned` 事件 |
| 无循环依赖 | 沿 DERIVED_FROM 关系遍历不能形成环 | 打断循环中最弱的关系（confidence 最低） |
| 矛盾可解 | CONTRADICTS 关系的两条 Evidence 不能同时为 verified | 将后验证的一条降级为 challenged |

### 5.3 证据链在报告生成中的使用

报告生成时，output-service 通过证据链构建"结论-推理-来源"三级结构：

```
结论：支付模块存在并发扣减风险
├── 推理：基于代码分析和历史事故推断 (inference, confidence=0.6)
│   ├── 支撑：代码中 payment.py 无分布式锁 (code_evidence, confidence=0.85)
│   │   └── 来源：l1://modules/payment (SOURCE_CODE)
│   ├── 支撑：历史事故 2025-05-12 支付回调重复处理 (git_history, confidence=0.7)
│   │   └── 来源：l1://commits/a1b2c3d (GIT_HISTORY)
│   └── 印证：L3 记忆中支付模块有 3 次金额精度事故 (memory_ref, confidence=0.5)
│       └── 来源：l3://risks/RISK-012 (MEMORY)
```

**报告生成规则**：

- 每条结论至少展示到第二级（推理 + 直接来源）
- confidence < 0.3 的 Evidence 在报告中标记为"低可信度，需人工复核"
- CONTRADICTS 关系在报告中单独列出"矛盾证据"章节
- superseded 和 deprecated 的 Evidence 不出现在报告中

---

## 六、Evidence 与维度的关联

### 6.1 Evidence 如何关联到 7 个分析维度

V2 保留 V1 的 7 个分析维度，但将关联方式从简单的字符串列表升级为结构化的 `DimensionRef`：

| 维度 | 含义 | 期望的 Evidence 类型 | 最低证据数 |
|------|------|---------------------|-----------|
| understanding | 需求理解 | requirement_ref, architecture_doc, memory_ref | 2 |
| impact | 影响分析 | code_evidence, tool_output | 3 |
| risk | 风险评估 | code_evidence, git_history, risk_indicator | 2 |
| change | 变更评估 | code_evidence, git_history | 2 |
| decision | 决策建议 | inference, constraint, memory_ref | 1 |
| evidence | 证据充分性 | 全类型（元维度，评估证据链完整性） | 5 |
| verification | 验证可行性 | verification_result, code_evidence | 1 |

### 6.2 维度评估如何消费 Evidence

维度评估在 Evidence Aggregation 阶段执行，流程如下：

```
1. 收集：按 dimension_id 过滤当前 Session 的所有 Evidence
2. 过滤：排除 deprecated 和 superseded 状态的 Evidence
3. 加权：每条 Evidence 的有效权重 = confidence.score × dimension_ref.weight × ContextKind 基础权重
4. 聚合：
   - supports 角色的 Evidence 权重为正
   - challenges 角色的 Evidence 权重为负
   - contextual 角色的 Evidence 权重减半
5. 评估：
   - 有效证据数 ≥ 最低证据数 → sufficient
   - 有效证据数 > 0 但 < 最低证据数 → in_progress
   - 有效证据数 = 0 → insufficient
6. 冲突检测：
   - 若同一维度内存在 CONTRADICTS 关系的 Evidence 对，标记该维度为 has_conflict
   - has_conflict 的维度不能标记为 sufficient，直到矛盾解决
```

**维度状态与 Evidence 的关系**：

| 维度状态 | 含义 | Evidence 条件 |
|---------|------|-------------|
| pending | 尚未开始分析 | 无关联 Evidence |
| in_progress | 分析进行中 | 有关联 Evidence，但未达 sufficient 条件 |
| sufficient | 分析充分 | 有效证据数 ≥ 最低证据数，且无未解决冲突 |
| insufficient | 分析不充分 | 分析完成后仍未达 sufficient 条件 |

---

## 七、Evidence → L3 沉淀规则

### 7.1 可沉淀的 Evidence 类型与目标 L3 知识类型

| EvidenceType | 沉淀条件 | 目标 L3 知识类型 | 沉淀触发 |
|-------------|---------|----------------|---------|
| constraint | status=verified, confidence.score ≥ 0.6 | 架构约束（constraint） | Session 完成时自动 |
| risk_indicator | status=verified, confidence.score ≥ 0.5 | 风险演化（risk） | Session 完成时自动 |
| code_evidence | status=verified, 涉及模块画像更新 | 模块画像（module_profile） | Session 完成时自动 |
| git_history | status=verified, 包含 hotfix/revert 信息 | 事故记忆（incident） | Session 完成时自动 |
| requirement_ref | status=verified, 多次引用同一需求 | 需求谱系（requirement_lineage） | Session 完成时自动 |
| architecture_doc | status=verified, 包含术语定义 | 术语表（glossary） | Session 完成时自动 |
| inference | status=verified, confidence.score ≥ 0.7, 人工确认 | 决策记录（decision） | 人工触发 |

### 7.2 沉淀时的数据转换规则

#### 7.2.1 constraint Evidence → L3 架构约束

```python
def evidence_to_constraint(evidence: EvidenceRecord) -> dict:
    return {
        "constraint_type": evidence.detail.get("constraint_type", "unknown"),
        "scope": evidence.detail.get("scope", ""),
        "description": evidence.detail.get("description", evidence.content),
        "source_session_id": evidence.session_id,
        "source_evidence_ids": [evidence.id],
        "constraint_hash": _compute_constraint_hash(evidence.detail),
    }
```

#### 7.2.2 risk_indicator Evidence → L3 风险演化

```python
def evidence_to_risk(evidence: EvidenceRecord) -> dict:
    return {
        "risk_category": evidence.detail.get("risk_category", "unknown"),
        "severity": evidence.detail.get("severity", "medium"),
        "affected_modules": evidence.detail.get("affected_modules", []),
        "indicators": evidence.detail.get("indicators", []),
        "risk_fingerprint": _compute_risk_fingerprint(evidence.detail),
        "source_session_id": evidence.session_id,
        "source_evidence_ids": [evidence.id],
    }
```

#### 7.2.3 code_evidence Evidence → L3 模块画像更新

```python
def evidence_to_module_profile(evidence: EvidenceRecord) -> dict:
    return {
        "module_name": evidence.detail.get("module_name", ""),
        "last_analyzed_at": evidence.created_at.isoformat(),
        "analysis_count_delta": 1,
        "source_session_id": evidence.session_id,
    }
```

### 7.3 Evidence 的 confidence 如何映射到 L3 的 confidence_score

L3 知识的 confidence_score 不是简单继承单条 Evidence 的 confidence，而是综合计算：

```
L3 confidence_score = f(evidence_confidence, verification_count, cross_session_count, human_verified)
```

**Phase 1 计算规则**（与 03_COGNITIVE_ASSET_MODEL.md 对齐）：

| 因素 | 规则 |
|------|------|
| 基础分 | 从 1 个 Session 产生 = 0.3，2-3 个 = 0.6，4+ 个 = 0.8 |
| Evidence 置信度加权 | 基础分 × max(source_evidence_confidence)，source_evidence_confidence 取所有来源 Evidence 的 confidence.score 最大值 |
| 人工确认 | `human_verified = true` 时直接提升至 0.9 |
| 衰减 | 超过 60 天未验证，每周衰减 0.05，最低至 0.1 |

**示例**：

- 一条 constraint Evidence（confidence=0.7）首次沉淀：L3 confidence = 0.3 × 0.7 = 0.21
- 第二个 Session 再次产生相同约束：L3 confidence = 0.6 × 0.7 = 0.42
- 人工确认后：L3 confidence = 0.9

---

## 八、存储设计

### 8.1 evidence_records 表

```sql
CREATE TABLE evidence_records (
    id              VARCHAR(32)    NOT NULL PRIMARY KEY,
    session_id      VARCHAR(36)    NOT NULL,
    type            VARCHAR(32)    NOT NULL,
    status          VARCHAR(16)    NOT NULL DEFAULT 'discovered',
    confidence_score FLOAT          NOT NULL DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    confidence_level VARCHAR(16)   NOT NULL DEFAULT 'medium',
    confidence_basis TEXT           DEFAULT '',
    source_context_kind VARCHAR(32) NOT NULL,
    source_uri      TEXT           NOT NULL,
    source_display_name VARCHAR(256) DEFAULT '',
    content         VARCHAR(200)   NOT NULL,
    detail          JSONB          NOT NULL DEFAULT '{}',
    dimension_refs  JSONB          NOT NULL DEFAULT '[]',
    step_id         INTEGER,
    tool_call_id    VARCHAR(64),
    verified_by     VARCHAR(64)    DEFAULT '',
    verified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES cognitive_sessions(id) ON DELETE CASCADE,
    CONSTRAINT valid_evidence_type CHECK (type IN (
        'code_evidence', 'requirement_ref', 'architecture_doc', 'git_history',
        'memory_ref', 'tool_output', 'inference', 'constraint',
        'risk_indicator', 'verification_result'
    )),
    CONSTRAINT valid_evidence_status CHECK (status IN (
        'discovered', 'verified', 'challenged', 'superseded', 'deprecated'
    )),
    CONSTRAINT valid_confidence_level CHECK (confidence_level IN (
        'low', 'medium', 'high', 'very_high'
    )),
    CONSTRAINT valid_context_kind CHECK (source_context_kind IN (
        'SOURCE_CODE', 'REQUIREMENT', 'ARCH_DOC', 'GIT_HISTORY',
        'MEMORY', 'INFERRED_KNOWLEDGE'
    ))
);

CREATE INDEX idx_evidence_session ON evidence_records(session_id);
CREATE INDEX idx_evidence_session_type ON evidence_records(session_id, type);
CREATE INDEX idx_evidence_session_status ON evidence_records(session_id, status);
CREATE INDEX idx_evidence_dimension ON evidence_records USING GIN(dimension_refs);
CREATE INDEX idx_evidence_confidence ON evidence_records(session_id, confidence_score);
CREATE INDEX idx_evidence_source_uri ON evidence_records(source_uri);
CREATE INDEX idx_evidence_created ON evidence_records(created_at);
```

### 8.2 evidence_relations 表

```sql
CREATE TABLE evidence_relations (
    id                   VARCHAR(32)    NOT NULL PRIMARY KEY,
    session_id           VARCHAR(36)    NOT NULL,
    source_evidence_id   VARCHAR(32)    NOT NULL,
    target_evidence_id   VARCHAR(32)    NOT NULL,
    relation_type        VARCHAR(16)    NOT NULL,
    confidence           FLOAT          NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    rationale            TEXT           DEFAULT '',
    created_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES cognitive_sessions(id) ON DELETE CASCADE,
    CONSTRAINT fk_source_evidence FOREIGN KEY (source_evidence_id) REFERENCES evidence_records(id) ON DELETE CASCADE,
    CONSTRAINT fk_target_evidence FOREIGN KEY (target_evidence_id) REFERENCES evidence_records(id) ON DELETE CASCADE,
    CONSTRAINT valid_relation_type CHECK (relation_type IN (
        'SUPPORTS', 'CONTRADICTS', 'DERIVED_FROM', 'SUPERSEDES', 'CORROBORATES'
    )),
    CONSTRAINT no_self_relation CHECK (source_evidence_id != target_evidence_id)
);

CREATE INDEX idx_evidence_relation_session ON evidence_relations(session_id);
CREATE INDEX idx_evidence_relation_source ON evidence_relations(source_evidence_id);
CREATE INDEX idx_evidence_relation_target ON evidence_relations(target_evidence_id);
CREATE INDEX idx_evidence_relation_type ON evidence_relations(session_id, relation_type);
CREATE UNIQUE INDEX idx_evidence_relation_unique ON evidence_relations(
    source_evidence_id, target_evidence_id, relation_type
);
```

### 8.3 JSONB detail 字段的 GIN 索引

```sql
CREATE INDEX idx_evidence_detail ON evidence_records USING GIN(detail);
```

### 8.4 索引策略说明

| 索引 | 用途 | 查询场景 |
|------|------|---------|
| `idx_evidence_session` | 按 Session 查询全部 Evidence | 报告生成、推理链回放 |
| `idx_evidence_session_type` | 按 Session + 类型查询 | 按类型过滤证据链 |
| `idx_evidence_session_status` | 按 Session + 状态查询 | 过滤有效证据（排除 deprecated） |
| `idx_evidence_dimension` | 按维度查询（GIN） | 维度评估时收集关联证据 |
| `idx_evidence_confidence` | 按置信度范围查询 | 筛选高/低置信度证据 |
| `idx_evidence_source_uri` | 按来源 URI 查询 | L0/L1 引用完整性校验 |
| `idx_evidence_created` | 按时间排序 | 时间线展示 |
| `idx_evidence_detail` | 详情字段查询（GIN） | 按 module_name、commit_hash 等字段检索 |
| `idx_evidence_relation_unique` | 防止重复关系 | 写入时去重 |

---

## 九、接口定义

### 9.1 EvidenceCollector V2 接口

```python
from abc import ABC, abstractmethod
from reqradar.kernel.evidence_types import (
    EvidenceRecord,
    EvidenceRelationRecord,
    EvidenceType,
    EvidenceConfidence,
    EvidenceStatus,
    SourceRef,
    DimensionRef,
    EvidenceRelationType,
)


class EvidenceCollectorV2(ABC):
    """Evidence 收集器 V2 接口——异步、支持持久化"""

    @abstractmethod
    async def add(
        self,
        session_id: str,
        type: EvidenceType,
        source_ref: SourceRef,
        content: str,
        confidence: EvidenceConfidence,
        dimension_refs: list[DimensionRef] | None = None,
        detail: dict | None = None,
        step_id: int | None = None,
        tool_call_id: str | None = None,
    ) -> EvidenceRecord:
        """添加一条 Evidence，返回完整记录"""
        ...

    @abstractmethod
    async def add_relation(
        self,
        session_id: str,
        source_evidence_id: str,
        target_evidence_id: str,
        relation_type: EvidenceRelationType,
        confidence: float = 1.0,
        rationale: str = "",
    ) -> EvidenceRelationRecord:
        """建立两条 Evidence 之间的关系"""
        ...

    @abstractmethod
    async def verify(
        self,
        evidence_id: str,
        verified_by: str,
    ) -> EvidenceRecord:
        """验证一条 Evidence，更新状态和置信度"""
        ...

    @abstractmethod
    async def challenge(
        self,
        evidence_id: str,
        challenger_evidence_id: str,
        rationale: str = "",
    ) -> EvidenceRecord:
        """质疑一条 Evidence，建立 CONTRADICTS 关系并更新状态"""
        ...

    @abstractmethod
    async def supersede(
        self,
        old_evidence_id: str,
        new_evidence_id: str,
        rationale: str = "",
    ) -> EvidenceRecord:
        """用新 Evidence 替代旧 Evidence"""
        ...

    @abstractmethod
    async def deprecate(
        self,
        evidence_id: str,
        reason: str = "",
    ) -> EvidenceRecord:
        """废弃一条 Evidence"""
        ...

    @abstractmethod
    async def query(
        self,
        session_id: str,
        type: EvidenceType | None = None,
        status: EvidenceStatus | None = None,
        dimension: str | None = None,
        min_confidence: float | None = None,
        context_kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvidenceRecord]:
        """多维度查询 Evidence"""
        ...

    @abstractmethod
    async def get_relations(
        self,
        evidence_id: str,
        relation_type: EvidenceRelationType | None = None,
        direction: str = "both",
    ) -> list[EvidenceRelationRecord]:
        """查询 Evidence 的关联关系"""
        ...

    @abstractmethod
    async def get_chain(
        self,
        evidence_id: str,
        max_depth: int = 5,
    ) -> dict:
        """获取以某条 Evidence 为根的完整证据链"""
        ...

    @abstractmethod
    async def validate_chain(
        self,
        session_id: str,
    ) -> list[dict]:
        """校验 Session 内所有 Evidence 的链完整性，返回校验结果列表"""
        ...

    @abstractmethod
    async def get_candidates_for_l3(
        self,
        session_id: str,
    ) -> list[EvidenceRecord]:
        """获取 Session 中可沉淀到 L3 的候选 Evidence"""
        ...
```

### 9.2 Evidence 查询 API

cognitive-rt 暴露的内部 HTTP API（供 api-service / output-service 调用）：

```
GET /internal/v2/sessions/{session_id}/evidences
    ?type=code_evidence
    &status=verified
    &dimension=risk
    &min_confidence=0.6
    &context_kind=SOURCE_CODE
    &limit=50
    &offset=0

Response:
{
    "total": 42,
    "items": [EvidenceRecord, ...]
}
```

```
GET /internal/v2/sessions/{session_id}/evidences/{evidence_id}

Response:
{
    "evidence": EvidenceRecord,
    "relations": [EvidenceRelationRecord, ...]
}
```

```
GET /internal/v2/sessions/{session_id}/evidences/{evidence_id}/chain
    ?max_depth=5

Response:
{
    "root": EvidenceRecord,
    "chain": {
        "SUPPORTS": [EvidenceRecord, ...],
        "CONTRADICTS": [EvidenceRecord, ...],
        "DERIVED_FROM": [EvidenceRecord, ...],
        "CORROBORATES": [EvidenceRecord, ...]
    }
}
```

### 9.3 Evidence 验证 API

```
POST /internal/v2/sessions/{session_id}/evidences/{evidence_id}/verify

Request:
{
    "verified_by": "auto" | "human:{user_id}"
}

Response:
{
    "evidence": EvidenceRecord,
    "previous_status": "discovered",
    "confidence_delta": 0.1
}
```

```
POST /internal/v2/sessions/{session_id}/evidences/{evidence_id}/challenge

Request:
{
    "challenger_evidence_id": "ev-xxx",
    "rationale": "新发现的 Git 历史与该证据矛盾"
}

Response:
{
    "evidence": EvidenceRecord,
    "relation": EvidenceRelationRecord
}
```

```
POST /internal/v2/sessions/{session_id}/evidences/validate-chain

Response:
{
    "total_evidences": 42,
    "valid": 38,
    "issues": [
        {
            "evidence_id": "ev-yyy",
            "rule": "traceability",
            "message": "source_ref.uri 无法解析到 L0/L1 记录"
        }
    ]
}
```

---

## 十、错误处理

### 10.1 Evidence 写入失败

| 场景 | 错误类型 | 处理策略 |
|------|---------|---------|
| 数据库写入失败 | `EvidenceWriteError` | 重试 3 次（指数退避）；仍失败则发布 `EvidenceWriteFailed` 事件，将 Evidence 暂存内存队列，待恢复后补写 |
| session_id 不存在 | `SessionNotFoundError` | 拒绝写入，返回错误 |
| Evidence ID 冲突 | `EvidenceConflictError` | 生成新 ID 重试 |
| content 超过 200 字 | `ValidationError` | 截断至 200 字并记录 warning |
| detail JSONB 超过 1MB | `EvidenceDetailOversizeError` | 将大字段移至 MinIO，detail 中保留 `uri` 引用 |

### 10.2 验证冲突

| 场景 | 处理策略 |
|------|---------|
| 自动验证通过但人工标记为 challenged | 以人工判断为准，记录冲突到 `detail.verification_conflicts` |
| 两条 Evidence 互相 CONTRADICTS 且都为 verified | 将后验证的一条降级为 challenged，发布 `EvidenceConflictDetected` 事件 |
| 验证时发现 source_ref 引用已失效（L0/L1 记录被清理） | 标记为 challenged，发布 `EvidenceSourceLost` 事件 |

### 10.3 链断裂

| 场景 | 检测方式 | 处理策略 |
|------|---------|---------|
| 前提 Evidence 被删除（CASCADE） | 查询 DERIVED_FROM 关系时目标不存在 | 将 inference 类型 Evidence 标记为 challenged |
| source_ref.uri 无法解析 | 完整性校验时发现 | 标记为 challenged，发布 `EvidenceChainBroken` 事件 |
| 循环依赖 | 遍历 DERIVED_FROM 关系时检测到环 | 打断最弱关系，发布 `EvidenceCycleDetected` 事件 |
| 孤立 Evidence（无关系记录） | 完整性校验时发现 | 降级为 discovered，发布 `EvidenceOrphaned` 事件 |

### 10.4 异常体系

Evidence 相关异常继承自 `core/exceptions.py` 的 `ReqRadarException`：

```python
class EvidenceError(ReqRadarException):
    """Evidence 系统基础异常"""

class EvidenceWriteError(EvidenceError):
    """Evidence 写入失败"""

class EvidenceConflictError(EvidenceError):
    """Evidence 冲突（ID 冲突、验证冲突等）"""

class EvidenceChainError(EvidenceError):
    """证据链异常（断裂、循环等）"""

class EvidenceValidationError(EvidenceError):
    """Evidence 验证失败"""

class EvidenceDetailOversizeError(EvidenceError):
    """Evidence 详情超过存储限制"""
```

---

## 十一、配置参数

Evidence 相关配置项纳入 Scope × Domain 配置矩阵，位于 RUNTIME Domain 下：

| 配置项 | Scope | 默认值 | 说明 |
|--------|-------|--------|------|
| `evidence.max_per_session` | SYSTEM / PROJECT | 500 | 单个 Session 最大 Evidence 数量 |
| `evidence.max_relations_per_evidence` | SYSTEM | 20 | 单条 Evidence 最大关系数 |
| `evidence.auto_verify_enabled` | SYSTEM / PROJECT | true | 是否启用自动验证 |
| `evidence.auto_verify_on_creation` | SYSTEM / PROJECT | true | Evidence 创建后是否立即自动验证 |
| `evidence.min_confidence_for_l3` | SYSTEM / PROJECT | 0.5 | 沉淀到 L3 的最低置信度阈值 |
| `evidence.min_confidence_for_conclusion` | SYSTEM / PROJECT | 0.3 | 支撑结论的最低置信度阈值 |
| `evidence.high_confidence_requires_factual` | SYSTEM | true | confidence > 0.7 是否必须有一条非 INFERRED 类型 Evidence |
| `evidence.chain_validation_on_complete` | SYSTEM / PROJECT | true | Session 完成时是否执行链完整性校验 |
| `evidence.chain_max_depth` | SYSTEM | 10 | 证据链遍历最大深度 |
| `evidence.detail_max_size_bytes` | SYSTEM | 1048576 | detail JSONB 最大字节数（1MB） |
| `evidence.confidence_boost_auto_verify` | SYSTEM | 0.1 | 自动验证置信度提升值 |
| `evidence.confidence_boost_human_verify` | SYSTEM | 0.15 | 人工验证置信度提升值 |
| `evidence.confidence_penalty_challenged` | SYSTEM | 0.2 | 被质疑时置信度惩罚值 |
| `evidence.deprecated_auto_cleanup_days` | SYSTEM | 90 | deprecated Evidence 自动归档天数 |

---

## 十二、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| **R-01 Session 生命周期** | Evidence 归属于 Session | Evidence 的 `session_id` 关联到 CognitiveSession；Session 完成时触发 Evidence 链校验和 L3 沉淀 |
| **R-02 Context Pipeline** | Evidence 是 Pipeline 的输出 | Collect 阶段从 L3 注入 memory_ref 类型 Evidence；Score 阶段使用 Evidence 的 confidence 和 ContextKind 权重计算上下文评分 |
| **R-03 Event Stream** | Evidence 变更产生事件 | EvidenceAdded / EvidenceVerified / EvidenceChallenged / EvidenceSuperseded / EvidenceDeprecated / EvidenceChainBroken 均为 Cognitive 级事件 |
| **R-05 Checkpoint** | Evidence 状态是 Checkpoint 的一部分 | Checkpoint 的热状态包含 EvidenceState（当前 Session 的 Evidence 摘要：总数、各类型数、各状态数、平均置信度） |
| **M-02 7-Dimension Framework** | Evidence 支撑维度评估 | 每个维度的评估结果由关联 Evidence 的数量、权重和置信度决定；维度 insufficient 时触发补充证据的推理步骤 |
| **M-03 Project Cognitive State** | Evidence 沉淀到 L3 | Session 完成后，符合沉淀条件的 Evidence 通过 L3Writer Protocol 写入 L3 知识表；Evidence 的 confidence 映射为 L3 的 confidence_score |
| **ToolRuntime (R-04)** | 工具调用产生 Evidence | 工具执行结果通过 EvidenceCollector.add() 写入 tool_output 类型 Evidence；`tool_call_id` 关联到 ToolRuntime 的调用记录 |
| **index-service** | Evidence 的持久化存储 | evidence_records 和 evidence_relations 表由 index-service 管理；L3 沉淀由 index-service 执行 |
| **output-service** | Evidence 用于报告生成 | 报告生成时查询 Evidence 链，构建"结论-推理-来源"三级结构 |
| **ingestion-service** | L1 数据是 Evidence 的来源 | Evidence 的 source_ref.uri 指向 ingestion-service 产生的 L1 记录 |

---

## 十三、测试策略

### 13.1 单元测试

| 测试类 | 关键测试场景 |
|--------|------------|
| TestEvidenceRecord | 字段默认值、类型校验、content 长度限制、confidence 范围校验 |
| TestEvidenceConfidence | score → level 映射、边界值（0.0, 0.3, 0.6, 0.85, 1.0）、from_score 工厂方法 |
| TestEvidenceStatus | 合法状态转换、非法状态转换拒绝、终态不可转换 |
| TestSourceRef | ContextKind 校验、URI 格式校验、INFERRED_KNOWLEDGE 必须有 inference_chain |
| TestDimensionRef | dimension_id 校验、role 校验、weight 范围校验 |
| TestEvidenceRelationRecord | 关系类型校验、自引用拒绝、confidence 范围校验 |

### 13.2 集成测试

| 测试类 | 关键测试场景 |
|--------|------------|
| TestEvidenceCollectorV2 | 添加 Evidence 并持久化、查询过滤、关系建立、验证流程、废弃流程 |
| TestEvidenceChain | 链完整性校验（溯源可达、推理闭环、无孤立、无循环）、链断裂检测与修复 |
| TestEvidenceLifecycle | discovered → verified → challenged → verified 恢复、discovered → superseded → deprecated 完整流程 |
| TestEvidenceDimension | 维度评估（sufficient/in_progress/insufficient）、冲突检测、权重计算 |
| TestEvidenceL3Sedimentation | 沉淀候选筛选、数据转换正确性、confidence 映射、跨 Session 聚合 |

### 13.3 关键测试场景

1. **证据链矛盾检测**：创建两条 CONTRADICTS 关系的 Evidence，验证 challenged 状态转换和置信度变化
2. **高置信度结论必须有事实支撑**：创建仅含 INFERRED 类型 Evidence 的结论，验证 confidence 上限约束
3. **L0/L1 引用失效**：删除 L1 记录后验证 Evidence 链完整性校验能检测到 source_ref 失效
4. **跨 Session Evidence 聚合**：同一约束在多个 Session 中被识别，验证 L3 confidence 递增
5. **证据链深度遍历**：构建 5 层 DERIVED_FROM 关系链，验证链遍历和循环检测
6. **并发写入**：两个推理步骤同时写入 Evidence，验证 ID 生成唯一性和数据一致性
7. **大 detail 处理**：detail 超过 1MB 时验证自动迁移到 MinIO 的行为
8. **维度冲突阻断**：同一维度内存在 CONTRADICTS 关系，验证维度不能标记为 sufficient

---

## 十四、明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| Evidence 自动删除 | 不做 | Evidence 是 L2 追溯性的基础，append-only，只可标记 deprecated |
| Evidence 跨项目共享 | 不做 | 先在单项目内验证 Evidence 链和沉淀机制 |
| Evidence 语义去重 | Phase 1 不做 | 同一事实可能被多个工具/步骤发现，记录多条 Evidence 是合理的；去重通过 evidence_relations 的 CORROBORATES 关系体现 |
| 证据链可视化 API | Phase 1 不做 | 前端可视化依赖 M-04 Cognitive Graph Schema，Phase 1 只提供链数据查询 |
| Evidence 版本化 | 不做 | Evidence 本身不可修改，更新通过 superseded 机制实现 |
| L3-B 模式层沉淀 | Phase 1 不做 | 先完成 L3-A 事实层沉淀，模式层抽象在 Phase 3 |
| Evidence 评分的 LLM 辅助 | Phase 1 不做 | confidence 初始赋值使用规则引擎，LLM 辅助评分在 Phase 2 探索 |
| 证据链的图数据库存储 | Phase 1 不做 | PG 关联表满足当前需求，接口层预留 Graph 演化（ADR-015） |
| Evidence 的细粒度权限控制 | Phase 1 不做 | Evidence 权限跟随 Session 权限，不单独控制 |

---

## 十五、V1 迁移映射

为便于从 V1 迁移，以下映射表定义 V1 字段到 V2 字段的对应关系：

| V1 字段 | V2 字段 | 转换规则 |
|---------|---------|---------|
| `id` (ev-001) | `id` (ev-{uuid_hex[:12]}) | 格式变更，迁移时生成新 ID，保留映射表 |
| `type` (code_match) | `type` (code_evidence) | 类型映射见下表 |
| `source` (字符串) | `source_ref` (结构化) | 解析字符串生成 SourceRef |
| `content` | `content` | 直接迁移，超 200 字截断 |
| `confidence` (low/medium/high) | `confidence.score` + `confidence.level` | low→0.2, medium→0.5, high→0.8 |
| `dimensions` (字符串列表) | `dimension_refs` (结构化列表) | 每个 dimension 转为 DimensionRef，role 默认 supports |
| `timestamp` | `created_at` | 直接迁移 |

**V1 类型 → V2 类型映射**：

| V1 类型 | V2 类型 |
|---------|---------|
| code_match | code_evidence |
| module_summary | code_evidence（detail 中包含模块摘要信息） |
| project_context | memory_ref |
| requirement_text | requirement_ref |
| inference | inference |

---

## 十六、总结

Evidence Model 是 ReqRadar "可验证认知"承诺的技术基石。V2 的核心升级体现在五个方面：

1. **结构化来源引用**：SourceRef 替代自由文本，使每条 Evidence 可精确追溯到 L0/L1
2. **生命周期状态机**：discovered → verified → challenged → superseded → deprecated，使 Evidence 的可信度可追踪
3. **证据链关系**：五种关系类型使推理过程可追溯、矛盾可检测、结论可验证
4. **L3 沉淀通道**：按类型和置信度自动沉淀，使单次分析的知识可跨 Session 积累
5. **持久化与查询**：独立表结构 + 多维索引，替代 V1 的内存列表 + JSON 快照

这些升级共同确保了 ReqRadar 的输出不是"AI 的回答"，而是"可验证的工程认知"——每一条结论都有据可查，每一步推理都可追溯，每一份知识都可积累。
