# M-03 Project Cognitive State — 项目认知状态详细设计

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | L3 持久化知识的完整 Schema 定义、知识治理框架、L3Writer Protocol 与飞轮验证机制详细设计 |
| 前置文档 | 00_PROJECT_POSITIONING.md（项目宪法）、01_RESTRUCTURE_OVERVIEW.md（Runtime 蓝图）、03_COGNITIVE_ASSET_MODEL.md（认知资产模型） |
| 核心目标 | 将 03 文档第六章定义的 L3 知识类型展开为可实现的 Pydantic 模型 + PG 表结构 + 治理算法 + 写入协议 |
| 文档职责 | What & How — L3 每种知识类型的精确数据契约、写入语义、治理规则、接口定义；为 P5 拆 index-service 的 7 个子任务提供统一实现基线 |

---

## 二、概述

### 2.1 Project Cognitive State 在 V2 中的定位

Project Cognitive State 是 ReqRadar V2 认知资产模型中 **L3: Persistent Knowledge** 层的完整实现。它承载系统的核心价值主张——"让组织不再失忆"——通过以下机制将一次性的分析记录转化为可持续积累的组织认知：

```
L2 Analysis Records（单次推理过程）
         │
         │ index-service 沉淀
         ▼
L3 Project Cognitive State（跨 Session 持久化知识）
         │
         │ Context Pipeline 注入（仅 active + confidence >= 0.6）
         ▼
L2 新的分析（站在更高的认知起点）
```

### 2.2 L3 的两层结构

| 层级 | 代号 | 本质 | Phase | 本文档覆盖范围 |
|------|------|------|-------|--------------|
| 认知事实 | L3-A | 跨 Session 聚合的结构化事实 | Phase 1 实现 | 完整 Schema + 写入协议 |
| 认知模式 | L3-B | 跨事实抽象后的稳定模式 | Phase 3 实现 | 接口预留，Schema 预留 |

### 2.3 设计原则

1. **Append-only 演化**：知识不可删除，只可标记为 `deprecated` 或 `superseded`
2. **治理先行**：每条知识必须携带新鲜度和置信度元数据，防止知识腐化
3. **写入协议统一**：7 种知识类型通过 L3Writer Protocol 统一写入接口
4. **接口预留 Graph**：当前使用 PG 关联表，接口层统一使用 Relation Contract，未来可切换图数据库（ADR-015）
5. **飞轮可验证**：通过对比实验框架验证"越用越准"是工程事实

---

## 三、L3-A 认知事实完整 Schema

### 3.1 通用治理元数据基类

所有 L3-A 知识类型共享以下治理元数据，定义为 Pydantic 基类：

```python
from datetime import datetime
from pydantic import BaseModel, Field
from enum import StrEnum


class FreshnessStatus(StrEnum):
    ACTIVE = "active"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    STALE = "stale"
    CONFLICTED = "conflicted"


class ConfidenceMetadata(BaseModel):
    confidence_score: float = Field(ge=0.0, le=1.0, description="综合置信度评分")
    verification_count: int = Field(ge=0, description="被不同 Session 验证的次数")
    source_session_count: int = Field(ge=1, description="产生该知识的 Session 数量")
    human_verified: bool = Field(default=False, description="是否经过人工确认")
    last_verified_at: datetime | None = Field(default=None, description="最近一次被验证的时间")


class L3KnowledgeBase(BaseModel):
    id: str = Field(description="知识记录唯一标识，UUID")
    project_id: str = Field(description="所属项目 ID")
    freshness: FreshnessStatus = Field(default=FreshnessStatus.ACTIVE, description="知识新鲜度状态")
    confidence: ConfidenceMetadata = Field(description="置信度元数据")
    source_session_ids: list[str] = Field(default_factory=list, description="产生该知识的 Session ID 列表")
    evidence_refs: list[str] = Field(default_factory=list, description="支撑该知识的 L2 Evidence ID 列表")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="最近更新时间")
    superseded_by: str | None = Field(default=None, description="替代本条记录的新记录 ID")
```

PG 表中治理元数据以扁平列存储（非 JSONB），便于索引和查询：

```sql
-- 所有 L3 知识表共享的治理元数据列
-- 以下列定义在各知识类型表中重复出现，不再逐一标注
--
-- freshness         VARCHAR(20)  NOT NULL DEFAULT 'active'
-- confidence_score  FLOAT        NOT NULL DEFAULT 0.3
-- verification_count INTEGER     NOT NULL DEFAULT 0
-- source_session_count INTEGER   NOT NULL DEFAULT 1
-- human_verified    BOOLEAN      NOT NULL DEFAULT FALSE
-- last_verified_at  TIMESTAMPTZ
-- superseded_by     UUID
```

---

### 3.2 术语表（Glossary）

#### 3.2.1 GlossaryEntry Pydantic 模型

```python
class GlossaryEntry(L3KnowledgeBase):
    canonical_name: str = Field(description="规范术语名，作为去重键")
    definition: str = Field(description="术语定义")
    aliases: list[str] = Field(default_factory=list, description="别名列表")
    context: str | None = Field(default=None, description="术语在项目中的使用上下文")
    first_seen_ref: str | None = Field(default=None, description="首次出现位置的 L0/L1 引用")
    related_modules: list[str] = Field(default_factory=list, description="关联模块名称列表")
    category: str | None = Field(default=None, description="术语分类（业务/技术/领域）")
```

#### 3.2.2 glossary 表结构

```sql
CREATE TABLE glossary (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID          NOT NULL REFERENCES projects(id),
    canonical_name  VARCHAR(200)  NOT NULL,
    definition      TEXT          NOT NULL,
    aliases         JSONB         NOT NULL DEFAULT '[]',
    context         TEXT,
    first_seen_ref  VARCHAR(500),
    related_modules JSONB         NOT NULL DEFAULT '[]',
    category        VARCHAR(50),

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 去重约束：同一项目内 canonical_name 唯一
    UNIQUE (project_id, canonical_name)
);

CREATE INDEX idx_glossary_project_freshness ON glossary (project_id, freshness);
CREATE INDEX idx_glossary_project_confidence ON glossary (project_id, confidence_score);
CREATE INDEX idx_glossary_aliases ON glossary USING GIN (aliases jsonb_path_ops);
```

#### 3.2.3 canonical_name 去重规则

| 规则 | 说明 |
|------|------|
| 规范化 | `canonical_name` 统一转为 `snake_case`，去除首尾空白，连续空白合并为单下划线 |
| 唯一约束 | `(project_id, canonical_name)` 构成唯一索引，同一项目内不可重复 |
| 写入时检查 | L3Writer.append 先查询 `canonical_name` 是否已存在；若存在，走别名合并逻辑 |

#### 3.2.4 别名合并逻辑

当写入的术语 `canonical_name` 已存在时，执行合并而非覆盖：

```python
def merge_glossary_entry(existing: GlossaryEntry, incoming: GlossaryEntry) -> GlossaryEntry:
    # 合并别名：将 incoming 的 canonical_name 和 aliases 追加到 existing
    new_aliases = set(existing.aliases)
    new_aliases.update(incoming.aliases)
    if incoming.canonical_name != existing.canonical_name:
        new_aliases.add(incoming.canonical_name)

    # 定义取更长的版本（信息量更大），或人工确认的版本
    definition = existing.definition
    if len(incoming.definition) > len(existing.definition) and not existing.human_verified:
        definition = incoming.definition

    # 合并关联模块
    merged_modules = list(set(existing.related_modules + incoming.related_modules))

    # 合并来源 Session
    merged_sessions = list(set(existing.source_session_ids + incoming.source_session_ids))

    # 更新置信度
    new_source_count = len(merged_sessions)
    new_verification = existing.verification_count + 1

    return existing.model_copy(update={
        "aliases": sorted(new_aliases),
        "definition": definition,
        "related_modules": sorted(merged_modules),
        "source_session_ids": merged_sessions,
        "source_session_count": new_source_count,
        "verification_count": new_verification,
        "updated_at": datetime.now(),
    })
```

---

### 3.3 模块画像（ModuleProfile）

#### 3.3.1 ModuleProfile Pydantic 模型

```python
class ModuleProfile(L3KnowledgeBase):
    module_name: str = Field(description="模块名称，作为去重键")
    responsibility: str | None = Field(default=None, description="模块职责描述")
    risk_history: list[RiskHistoryEntry] = Field(default_factory=list, description="风险历史记录")
    dependency_snapshot: list[DependencyEntry] = Field(default_factory=list, description="依赖快照")
    key_contributors: list[str] = Field(default_factory=list, description="关键贡献者列表")
    modification_frequency: float = Field(default=0.0, description="修改频率（次/周）")
    last_analyzed_at: datetime | None = Field(default=None, description="最近一次被分析的时间")
    analysis_count: int = Field(default=0, description="被分析的次数")
    tech_stack: list[str] = Field(default_factory=list, description="模块使用的技术栈")
    boundary_type: str | None = Field(default=None, description="边界类型（core/infra/adapter/interface）")


class RiskHistoryEntry(BaseModel):
    risk_id: str = Field(description="关联的风险 ID")
    risk_level: str = Field(description="风险等级（high/medium/low）")
    detected_at: datetime = Field(description="检测时间")
    session_id: str = Field(description="检测到该风险的 Session ID")
    summary: str = Field(description="风险摘要")


class DependencyEntry(BaseModel):
    target_module: str = Field(description="依赖的目标模块名")
    dep_type: str = Field(description="依赖类型（import/call/inheritance/data）")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="依赖强度")
    snapshot_at: datetime = Field(description="快照时间")
```

#### 3.3.2 module_profiles 表结构

```sql
CREATE TABLE module_profiles (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID          NOT NULL REFERENCES projects(id),
    module_name         VARCHAR(200)  NOT NULL,
    responsibility      TEXT,
    risk_history        JSONB         NOT NULL DEFAULT '[]',
    dependency_snapshot JSONB         NOT NULL DEFAULT '[]',
    key_contributors    JSONB         NOT NULL DEFAULT '[]',
    modification_frequency FLOAT      NOT NULL DEFAULT 0.0,
    last_analyzed_at    TIMESTAMPTZ,
    analysis_count      INTEGER       NOT NULL DEFAULT 0,
    tech_stack          JSONB         NOT NULL DEFAULT '[]',
    boundary_type       VARCHAR(20),

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, module_name)
);

CREATE INDEX idx_module_profiles_project_freshness ON module_profiles (project_id, freshness);
CREATE INDEX idx_module_profiles_last_analyzed ON module_profiles (project_id, last_analyzed_at);
```

#### 3.3.3 职责描述更新规则

| 规则 | 说明 |
|------|------|
| 首次写入 | 直接设置 `responsibility` |
| 后续更新 | 仅当新描述与旧描述的语义相似度 > 0.7 时，取信息量更大的版本；否则追加为补充描述 |
| 人工确认 | `human_verified = true` 时，LLM 产生的描述不可自动覆盖 |
| 变更记录 | 每次职责描述变更写入 `knowledge_changelog` |

#### 3.3.4 风险历史追加规则

风险历史采用 **追加不可删** 策略：

- 新检测到的风险追加到 `risk_history` JSONB 数组末尾
- 同一 `risk_id` 不重复追加（按 `risk_id` 去重）
- 风险等级变化时，更新对应条目的 `risk_level`，但保留变更记录到 `knowledge_changelog`
- `risk_history` 数组按 `detected_at` 升序排列

#### 3.3.5 依赖快照策略

| 策略 | 说明 |
|------|------|
| 快照触发 | 每次 Session 分析涉及该模块时，记录当前依赖快照 |
| 存储方式 | `dependency_snapshot` 数组中保留最近 N 次快照（默认 N=5），更早的快照归档到 `knowledge_changelog` |
| 对比检测 | 新快照与最近一次快照对比，检测新增/移除依赖，变更写入 `knowledge_changelog` |
| 依赖强度 | `strength` 由调用频次和耦合度综合计算，取值 0.0-1.0 |

---

### 3.4 架构约束（ArchitecturalConstraint）

#### 3.4.1 ArchitecturalConstraint Pydantic 模型

```python
class ArchitecturalConstraint(L3KnowledgeBase):
    constraint_hash: str = Field(description="约束内容哈希，作为去重键")
    title: str = Field(description="约束标题")
    description: str = Field(description="约束详细描述")
    scope: str = Field(description="约束作用范围（module/service/global）")
    scope_target: str | None = Field(default=None, description="作用目标（模块名/服务名）")
    source_type: str = Field(description="来源类型（incident_derived/decision_derived/human_declared/llm_inferred）")
    severity: str = Field(default="high", description="违反后果严重程度（critical/high/medium/low）")
    related_modules: list[str] = Field(default_factory=list, description="受约束影响的模块列表")
    related_incidents: list[str] = Field(default_factory=list, description="关联的事故 ID 列表")
    related_decisions: list[str] = Field(default_factory=list, description="关联的决策 ID 列表")
    deprecated: bool = Field(default=False, description="是否已废弃")
    deprecated_reason: str | None = Field(default=None, description="废弃原因")
    deprecated_at: datetime | None = Field(default=None, description="废弃时间")
```

#### 3.4.2 constraints 表结构

```sql
CREATE TABLE constraints (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID          NOT NULL REFERENCES projects(id),
    constraint_hash     VARCHAR(64)   NOT NULL,
    title               VARCHAR(500)  NOT NULL,
    description         TEXT          NOT NULL,
    scope               VARCHAR(20)   NOT NULL,
    scope_target        VARCHAR(200),
    source_type         VARCHAR(30)   NOT NULL,
    severity            VARCHAR(20)   NOT NULL DEFAULT 'high',
    related_modules     JSONB         NOT NULL DEFAULT '[]',
    related_incidents   JSONB         NOT NULL DEFAULT '[]',
    related_decisions   JSONB         NOT NULL DEFAULT '[]',
    deprecated          BOOLEAN       NOT NULL DEFAULT FALSE,
    deprecated_reason   TEXT,
    deprecated_at       TIMESTAMPTZ,

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, constraint_hash)
);

CREATE INDEX idx_constraints_project_freshness ON constraints (project_id, freshness);
CREATE INDEX idx_constraints_project_deprecated ON constraints (project_id, deprecated);
CREATE INDEX idx_constraints_scope ON constraints (project_id, scope, scope_target);
```

#### 3.4.3 constraint_hash 计算规则

`constraint_hash` 用于判断两条约束是否描述同一规则，避免重复写入：

```python
import hashlib


def compute_constraint_hash(
    project_id: str,
    scope: str,
    scope_target: str | None,
    description: str,
) -> str:
    # 将约束的核心属性拼接后计算 SHA-256
    # 规范化：去除首尾空白，连续空白合并，统一小写
    normalized_desc = " ".join(description.lower().strip().split())
    raw = f"{project_id}|{scope}|{scope_target or ''}|{normalized_desc}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

| 规则 | 说明 |
|------|------|
| 哈希输入 | `project_id + scope + scope_target + normalized_description` |
| 规范化 | description 转小写、去除首尾空白、连续空白合并为单空格 |
| 哈希算法 | SHA-256，取前 64 位十六进制 |
| 去重判定 | 同一 `project_id` 下 `constraint_hash` 相同视为同一约束 |

#### 3.4.4 deprecated 标记规则

| 规则 | 说明 |
|------|------|
| 标记方式 | 设置 `deprecated = true`，填写 `deprecated_reason` 和 `deprecated_at` |
| 不可删除 | 约束记录永不物理删除，只做逻辑废弃 |
| 触发条件 | 人工显式标记 / 新约束通过 `superseded_by` 替代旧约束时自动标记 |
| 注入行为 | `deprecated = true` 的约束不注入 Context Pipeline |
| 变更记录 | 废弃操作写入 `knowledge_changelog`，`change_type = 'deprecated'` |

---

### 3.5 决策记录（DecisionRecord）

#### 3.5.1 DecisionRecord Pydantic 模型

```python
class DecisionRecord(L3KnowledgeBase):
    decision_id: str = Field(description="决策唯一标识，格式 DEC-{YYYY}-{NNN}")
    title: str = Field(description="决策标题")
    context: str = Field(description="决策背景与上下文")
    decision: str = Field(description="决策结论")
    rationale: str | None = Field(default=None, description="决策理由")
    alternatives: list[str] = Field(default_factory=list, description="被否决的替代方案")
    participants: list[str] = Field(default_factory=list, description="决策参与者")
    decided_at: datetime = Field(description="决策时间")
    related_requirements: list[str] = Field(default_factory=list, description="关联的需求 ID")
    related_modules: list[str] = Field(default_factory=list, description="关联的模块名称")
    related_constraints: list[str] = Field(default_factory=list, description="产生的架构约束 ID")
    status: str = Field(default="active", description="决策状态（active/superseded/revoked）")
```

#### 3.5.2 decisions 表结构

```sql
CREATE TABLE decisions (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID          NOT NULL REFERENCES projects(id),
    decision_id         VARCHAR(30)   NOT NULL,
    title               VARCHAR(500)  NOT NULL,
    context             TEXT          NOT NULL,
    decision            TEXT          NOT NULL,
    rationale           TEXT,
    alternatives        JSONB         NOT NULL DEFAULT '[]',
    participants        JSONB         NOT NULL DEFAULT '[]',
    decided_at          TIMESTAMPTZ   NOT NULL,
    related_requirements JSONB        NOT NULL DEFAULT '[]',
    related_modules     JSONB         NOT NULL DEFAULT '[]',
    related_constraints JSONB         NOT NULL DEFAULT '[]',
    status              VARCHAR(20)   NOT NULL DEFAULT 'active',

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, decision_id)
);

CREATE INDEX idx_decisions_project_freshness ON decisions (project_id, freshness);
CREATE INDEX idx_decisions_decided_at ON decisions (project_id, decided_at);
CREATE INDEX idx_decisions_status ON decisions (project_id, status);
```

#### 3.5.3 时间线组织规则

| 规则 | 说明 |
|------|------|
| 排序 | 按 `decided_at` 升序排列，形成决策时间线 |
| 编号 | `decision_id` 格式 `DEC-{YYYY}-{NNN}`，年份内自增序号 |
| 追加 | 决策记录只追加，不修改已有记录 |
| 替代 | 当新决策替代旧决策时，旧记录 `status` 标记为 `superseded`，`superseded_by` 指向新记录 |
| 来源 | 从需求分析 Session 和 Chatback 交互中提取；用户也可显式录入 |

---

### 3.6 风险演化（RiskEvolution）

#### 3.6.1 RiskEvolution Pydantic 模型

```python
class RiskEvolution(L3KnowledgeBase):
    canonical_risk_id: str = Field(description="归一化风险 ID，格式 RISK-{NNN}")
    risk_fingerprint: str = Field(description="风险指纹哈希，用于跨 Session 归并")
    title: str = Field(description="风险标题")
    description: str = Field(description="风险描述")
    risk_type: str = Field(description="风险类型（concurrency/security/performance/logic/data/dependency）")
    current_level: str = Field(description="当前风险等级（critical/high/medium/low）")
    affected_modules: list[str] = Field(default_factory=list, description="受影响模块列表")
    evolution: list[EvolutionStep] = Field(default_factory=list, description="演化轨迹")
    mitigation_measures: list[MitigationMeasure] = Field(default_factory=list, description="缓解措施")
    status: str = Field(default="open", description="风险状态（open/mitigated/closed）")


class EvolutionStep(BaseModel):
    session_id: str = Field(description="产生该步骤的 Session ID")
    level: str = Field(description="该步骤时的风险等级")
    description: str = Field(description="该步骤的描述")
    detected_at: datetime = Field(description="检测时间")
    evidence_ref: str | None = Field(default=None, description="支撑该步骤的 Evidence ID")


class MitigationMeasure(BaseModel):
    description: str = Field(description="缓解措施描述")
    applied_at: datetime = Field(description="应用时间")
    applied_by: str = Field(description="应用者（session_id 或 human）")
    result_level: str = Field(description="缓解后的风险等级")
    evidence_ref: str | None = Field(default=None, description="支撑缓解效果的 Evidence ID")
```

#### 3.6.2 risks + risk_evolution 表结构

采用主表 + 演化轨迹子表的设计，避免 JSONB 大数组膨胀：

```sql
CREATE TABLE risks (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID          NOT NULL REFERENCES projects(id),
    canonical_risk_id   VARCHAR(20)   NOT NULL,
    risk_fingerprint    VARCHAR(64)   NOT NULL,
    title               VARCHAR(500)  NOT NULL,
    description         TEXT          NOT NULL,
    risk_type           VARCHAR(30)   NOT NULL,
    current_level       VARCHAR(20)   NOT NULL,
    affected_modules    JSONB         NOT NULL DEFAULT '[]',
    status              VARCHAR(20)   NOT NULL DEFAULT 'open',

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, canonical_risk_id),
    UNIQUE (project_id, risk_fingerprint)
);

CREATE INDEX idx_risks_project_freshness ON risks (project_id, freshness);
CREATE INDEX idx_risks_project_status ON risks (project_id, status);
CREATE INDEX idx_risks_project_type ON risks (project_id, risk_type);
CREATE INDEX idx_risks_current_level ON risks (project_id, current_level);


CREATE TABLE risk_evolution (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_id         UUID          NOT NULL REFERENCES risks(id) ON DELETE CASCADE,
    session_id      UUID          NOT NULL,
    level           VARCHAR(20)   NOT NULL,
    description     TEXT          NOT NULL,
    detected_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    evidence_ref    UUID,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_risk_evolution_risk_id ON risk_evolution (risk_id, detected_at);


CREATE TABLE risk_mitigations (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_id         UUID          NOT NULL REFERENCES risks(id) ON DELETE CASCADE,
    description     TEXT          NOT NULL,
    applied_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    applied_by      VARCHAR(100)  NOT NULL,
    result_level    VARCHAR(20)   NOT NULL,
    evidence_ref    UUID,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_risk_mitigations_risk_id ON risk_mitigations (risk_id, applied_at);
```

#### 3.6.3 risk_fingerprint 计算规则

`risk_fingerprint` 用于跨 Session 自动归并同一风险的不同描述：

```python
import hashlib


def compute_risk_fingerprint(
    project_id: str,
    affected_modules: list[str],
    risk_type: str,
    description: str,
) -> str:
    # 将风险的核心属性拼接后计算 SHA-256
    # affected_modules 排序保证顺序无关
    sorted_modules = sorted(set(m.lower().strip() for m in affected_modules))
    normalized_desc = " ".join(description.lower().strip().split())
    # 提取关键词（去除停用词后的前 10 个词）
    keywords = _extract_keywords(normalized_desc, top_n=10)
    raw = f"{project_id}|{'|'.join(sorted_modules)}|{risk_type}|{'|'.join(keywords)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_keywords(text: str, top_n: int = 10) -> list[str]:
    # 简单关键词提取：去除中文/英文停用词，按词频取 top_n
    # Phase 1 使用规则方法；Phase 3 可升级为 LLM 辅助语义归一化
    stopwords = {"的", "了", "在", "是", "和", "与", "或", "不", "有", "the", "a", "an",
                 "is", "are", "was", "were", "be", "been", "have", "has", "had",
                 "do", "does", "did", "will", "would", "could", "should", "may",
                 "might", "can", "shall", "to", "of", "in", "for", "on", "with",
                 "at", "by", "from", "as", "into", "through", "during", "before",
                 "after", "above", "below", "between", "and", "but", "or", "not",
                 "no", "nor", "so", "if", "then", "than", "too", "very"}
    words = [w for w in text.split() if w not in stopwords and len(w) > 1]
    from collections import Counter
    counter = Counter(words)
    return [w for w, _ in counter.most_common(top_n)]
```

| 规则 | 说明 |
|------|------|
| 哈希输入 | `project_id + sorted(affected_modules) + risk_type + top_keywords` |
| 模块排序 | `affected_modules` 排序后拼接，保证顺序无关 |
| 关键词提取 | 去除停用词后按词频取前 10 个词 |
| 哈希算法 | SHA-256，取前 64 位十六进制 |
| 归并判定 | 同一 `project_id` 下 `risk_fingerprint` 相同视为同一风险 |

#### 3.6.4 canonical_risk_id 归并逻辑

当新检测到的风险与已有风险的 `risk_fingerprint` 匹配时，执行归并：

```python
def merge_risk(existing: RiskEvolution, incoming: RiskEvolution) -> RiskEvolution:
    # 追加演化步骤
    new_evolution = existing.evolution + incoming.evolution

    # 更新当前风险等级
    current_level = incoming.current_level

    # 合并受影响模块
    merged_modules = list(set(existing.affected_modules + incoming.affected_modules))

    # 合并来源 Session
    merged_sessions = list(set(existing.source_session_ids + incoming.source_session_ids))

    # 更新置信度
    new_source_count = len(merged_sessions)
    new_verification = existing.verification_count + 1

    # 判断风险状态
    status = existing.status
    if current_level in ("low",) and existing.current_level in ("critical", "high", "medium"):
        status = "mitigated"

    return existing.model_copy(update={
        "current_level": current_level,
        "affected_modules": sorted(merged_modules),
        "evolution": new_evolution,
        "source_session_ids": merged_sessions,
        "source_session_count": new_source_count,
        "verification_count": new_verification,
        "status": status,
        "updated_at": datetime.now(),
    })
```

| 场景 | 处理 |
|------|------|
| fingerprint 匹配 | 归并到已有 `canonical_risk_id`，追加演化步骤 |
| fingerprint 不匹配 | 创建新风险记录，分配新 `canonical_risk_id` |
| 人工归并 | 用户可通过 API 手动合并两个风险，保留一个 `canonical_risk_id` |
| 语义归一化 | Phase 3 专项实现，Phase 1 仅使用 fingerprint 哈希匹配 |

#### 3.6.5 演化轨迹记录

每次风险状态变化（等级变更、缓解措施、关闭）都追加一条 `EvolutionStep` 到 `risk_evolution` 表：

| 字段 | 说明 |
|------|------|
| `session_id` | 触发状态变化的 Session |
| `level` | 变化后的风险等级 |
| `description` | 状态变化的描述 |
| `detected_at` | 检测时间 |
| `evidence_ref` | 支撑该变化的 Evidence ID |

演化轨迹按 `detected_at` 升序排列，形成完整的风险生命周期视图：

```
RISK-012: "用户并发扣减积分"
├── Session #15: 首次识别（critical）— 发现竞态条件
├── Session #22: 确认（critical）— 代码审查确认无锁保护
├── Session #35: 缓解（medium）— 采用分布式锁
└── Session #48: 关闭（low）— 压测通过，无并发异常
```

---

### 3.7 需求谱系（RequirementLineage）

#### 3.7.1 RequirementLineage Pydantic 模型

```python
class RequirementLineage(L3KnowledgeBase):
    requirement_id: str = Field(description="需求 ID，格式 REQ-{YYYY}-{NNN}")
    title: str = Field(description="需求标题")
    version: int = Field(default=1, description="需求版本号")
    description: str | None = Field(default=None, description="需求描述")
    derived_from: list[str] = Field(default_factory=list, description="派生自的需求 ID 列表")
    conflicts_with: list[str] = Field(default_factory=list, description="冲突的需求 ID 列表")
    depends_on: list[str] = Field(default_factory=list, description="依赖的需求 ID 列表")
    related_modules: list[str] = Field(default_factory=list, description="关联模块列表")
    source_doc_ref: str | None = Field(default=None, description="来源文档的 L0 引用")
    status: str = Field(default="active", description="需求状态（active/implemented/deprecated/superseded）")


class RequirementRelation(BaseModel):
    source_requirement_id: str = Field(description="源需求 ID")
    target_requirement_id: str = Field(description="目标需求 ID")
    relation_type: str = Field(description="关系类型（derived_from/conflicts_with/depends_on/supersedes）")
    confidence: float = Field(ge=0.0, le=1.0, description="关系置信度")
    evidence_ref: str | None = Field(default=None, description="支撑该关系的 Evidence ID")
    discovered_at: datetime = Field(description="发现时间")
    discovered_by: str = Field(description="发现者（session_id 或 human）")
```

#### 3.7.2 requirement_lineage 表结构

```sql
CREATE TABLE requirement_lineage (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID          NOT NULL REFERENCES projects(id),
    requirement_id      VARCHAR(30)   NOT NULL,
    title               VARCHAR(500)  NOT NULL,
    version             INTEGER       NOT NULL DEFAULT 1,
    description         TEXT,
    derived_from        JSONB         NOT NULL DEFAULT '[]',
    conflicts_with      JSONB         NOT NULL DEFAULT '[]',
    depends_on          JSONB         NOT NULL DEFAULT '[]',
    related_modules     JSONB         NOT NULL DEFAULT '[]',
    source_doc_ref      VARCHAR(500),
    status              VARCHAR(20)   NOT NULL DEFAULT 'active',

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, requirement_id, version)
);

CREATE INDEX idx_req_lineage_project_freshness ON requirement_lineage (project_id, freshness);
CREATE INDEX idx_req_lineage_status ON requirement_lineage (project_id, status);


CREATE TABLE requirement_relations (
    id                      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID         NOT NULL REFERENCES projects(id),
    source_requirement_id   VARCHAR(30)  NOT NULL,
    target_requirement_id   VARCHAR(30)  NOT NULL,
    relation_type           VARCHAR(30)  NOT NULL,
    confidence              FLOAT        NOT NULL DEFAULT 0.5,
    evidence_ref            UUID,
    discovered_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    discovered_by           VARCHAR(100) NOT NULL,

    UNIQUE (project_id, source_requirement_id, target_requirement_id, relation_type)
);

CREATE INDEX idx_req_relations_source ON requirement_relations (project_id, source_requirement_id);
CREATE INDEX idx_req_relations_target ON requirement_relations (project_id, target_requirement_id);
```

#### 3.7.3 派生/冲突/依赖关系推断规则

| 关系类型 | 推断规则 | 置信度 |
|---------|---------|--------|
| `derived_from` | 需求文档中显式引用（"基于 REQ-xxx"） | 0.9 |
| `derived_from` | LLM 从内容语义推断（主题/目标相似） | 0.5 |
| `conflicts_with` | 两个需求对同一模块有相反的约束 | 0.7 |
| `conflicts_with` | LLM 推断潜在冲突 | 0.4 |
| `depends_on` | 需求文档中显式声明依赖 | 0.9 |
| `depends_on` | 两个需求影响同一模块的同一接口 | 0.6 |
| `supersedes` | 新版本需求替代旧版本 | 0.95 |

推断规则优先级：显式引用 > 模块关联推断 > LLM 语义推断。LLM 推断的关系需 `confidence >= 0.6` 才写入。

---

### 3.8 事故记忆（IncidentMemory）

#### 3.8.1 IncidentMemory Pydantic 模型

```python
class IncidentMemory(L3KnowledgeBase):
    incident_id: str = Field(description="事故 ID，格式 INC-{YYYY}-{NNN}")
    title: str = Field(description="事故标题")
    occurred_at: datetime = Field(description="事故发生时间")
    root_cause: str = Field(description="根因分析")
    impact_scope: str = Field(description="影响范围描述")
    affected_modules: list[str] = Field(default_factory=list, description="受影响模块列表")
    fix_description: str | None = Field(default=None, description="修复措施描述")
    fix_type: str | None = Field(default=None, description="修复类型（hotfix/revert/refactor/config_change）")
    fix_commit_ref: str | None = Field(default=None, description="修复提交的 Git 引用")
    detection_source: str = Field(description="发现来源（git_revert/git_hotfix/chatback/human_declared）")
    related_risks: list[str] = Field(default_factory=list, description="关联的风险 ID 列表")
    related_constraints: list[str] = Field(default_factory=list, description="产生的架构约束 ID 列表")
    severity: str = Field(default="high", description="事故严重程度（critical/high/medium/low）")
    lessons_learned: str | None = Field(default=None, description="经验教训")
```

#### 3.8.2 incidents 表结构

```sql
CREATE TABLE incidents (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID          NOT NULL REFERENCES projects(id),
    incident_id         VARCHAR(30)   NOT NULL,
    title               VARCHAR(500)  NOT NULL,
    occurred_at         TIMESTAMPTZ   NOT NULL,
    root_cause          TEXT          NOT NULL,
    impact_scope        TEXT          NOT NULL,
    affected_modules    JSONB         NOT NULL DEFAULT '[]',
    fix_description     TEXT,
    fix_type            VARCHAR(20),
    fix_commit_ref      VARCHAR(200),
    detection_source    VARCHAR(30)   NOT NULL,
    related_risks       JSONB         NOT NULL DEFAULT '[]',
    related_constraints JSONB         NOT NULL DEFAULT '[]',
    severity            VARCHAR(20)   NOT NULL DEFAULT 'high',
    lessons_learned     TEXT,

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, incident_id)
);

CREATE INDEX idx_incidents_project_freshness ON incidents (project_id, freshness);
CREATE INDEX idx_incidents_occurred_at ON incidents (project_id, occurred_at);
CREATE INDEX idx_incidents_severity ON incidents (project_id, severity);
CREATE INDEX idx_incidents_detection_source ON incidents (project_id, detection_source);
```

#### 3.8.3 Git revert/hotfix 自动识别规则

系统从 Git 历史中自动识别候选事故记录：

| 规则 | 匹配模式 | `detection_source` |
|------|---------|-------------------|
| revert 提交 | commit message 匹配 `revert` / `Revert` / `rollback` / `回滚` | `git_revert` |
| hotfix 分支 | 分支名匹配 `hotfix/*` / `fix/*` / `urgent/*` | `git_hotfix` |
| 紧急修复提交 | commit message 匹配 `fix(critical)` / `urgent fix` / `紧急修复` | `git_hotfix` |

识别流程：

```
1. git_analyzer 扫描 Git 历史，识别 revert/hotfix 提交
2. 提取候选事故信息：时间、涉及模块、commit message
3. 创建 IncidentMemory 记录，detection_source 标记为 git_revert/git_hotfix
4. confidence_score 初始设为 0.3（低置信度，需人工确认或后续 Session 验证）
5. 推送到前端，提示用户确认或补充详情
```

自动识别的事故记录初始置信度较低（0.3），需通过以下方式提升：
- 用户在 Chatback 中确认：`human_verified = true`，`confidence_score` 提升至 0.9
- 后续 Session 分析中引用：`verification_count += 1`，按置信度计算规则提升

---

## 四、知识治理元数据 Schema

### 4.1 新鲜度模型

#### 4.1.1 FreshnessStatus 枚举

```python
class FreshnessStatus(StrEnum):
    ACTIVE = "active"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    STALE = "stale"
    CONFLICTED = "conflicted"
```

#### 4.1.2 状态迁移规则

```
                    ┌──────────────────────────────────────┐
                    │           写入/验证触发               │
                    ▼                                      │
              ┌──────────┐                                 │
              │  active   │ ◄──────────────────────────────┘
              └──┬───┬────┘
                 │   │
    90天未验证   │   │ 被新知识替代
                 │   │
                 ▼   ▼
          ┌──────┐ ┌───────────┐
          │ stale│ │ superseded│
          └──┬───┘ └───────────┘
             │
  重新验证   │        人工废弃
             │        ┌───────────┐
             ▼        │           │
          ┌──────┐    │           │
          │active│    │           │
          └──────┘    │           │
                      ▼           │
                ┌────────────┐    │
                │ deprecated │ ◄──┘
                └────────────┘

         检测到冲突
    active ──────────► conflicted
    conflicted ──────► active（冲突解决后）
```

| 迁移路径 | 触发条件 | Context Pipeline 行为 |
|---------|---------|---------------------|
| → `active` | 新写入 / 重新验证通过 / 冲突解决 | 默认注入 |
| `active` → `stale` | 超过阈值天数未被引用或验证 | 不注入，触发重新验证提示 |
| `active` → `superseded` | 被新知识替代（`superseded_by` 非空） | 不注入，保留引用链 |
| `active` → `deprecated` | 人工显式废弃 | 不注入 |
| `active` → `historical` | 人工标记为历史知识 | 仅在明确查询时返回 |
| `active` → `conflicted` | 检测到与其他知识冲突 | 不注入，触发冲突解决流程 |
| `stale` → `active` | 重新验证通过 | 恢复注入 |
| `conflicted` → `active` | 冲突解决 | 恢复注入 |

#### 4.1.3 90 天阈值配置

默认 90 天未验证标记为 `stale`，可通过 Scope x Domain 配置矩阵调整：

| 配置键 | 默认值 | 说明 |
|--------|-------|------|
| `governance.freshness.stale_threshold_days` | 90 | 超过此天数未验证标记为 stale |
| `governance.freshness.stale_check_interval_hours` | 24 | stale 检查的运行间隔 |
| `governance.freshness.historical_after_days` | 180 | 超过此天数自动降级为 historical |

---

### 4.2 置信度模型

#### 4.2.1 ConfidenceMetadata Pydantic 模型

```python
class ConfidenceMetadata(BaseModel):
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="综合置信度评分，计算规则见 4.2.2"
    )
    verification_count: int = Field(
        ge=0,
        description="被不同 Session 验证的次数"
    )
    source_session_count: int = Field(
        ge=1,
        description="产生该知识的 Session 数量"
    )
    human_verified: bool = Field(
        default=False,
        description="是否经过人工确认"
    )
    last_verified_at: datetime | None = Field(
        default=None,
        description="最近一次被验证的时间"
    )
```

#### 4.2.2 置信度计算规则

置信度由三部分组成：基础分 + 人工确认加成 - 时间衰减。

```python
from datetime import datetime, timedelta


def compute_confidence(
    source_session_count: int,
    verification_count: int,
    human_verified: bool,
    last_verified_at: datetime | None,
    now: datetime | None = None,
) -> float:
    now = now or datetime.now()

    # 基础分：由产生该知识的 Session 数量决定
    if source_session_count >= 4:
        base_score = 0.8
    elif source_session_count >= 2:
        base_score = 0.6
    else:
        base_score = 0.3

    # 人工确认加成
    if human_verified:
        base_score = max(base_score, 0.9)

    # 时间衰减
    if last_verified_at is not None:
        days_since_verification = (now - last_verified_at).days
        if days_since_verification > 60:
            decay_weeks = (days_since_verification - 60) // 7
            decay = min(decay_weeks * 0.05, base_score - 0.1)
            base_score -= decay

    return round(max(base_score, 0.1), 2)
```

#### 4.2.3 衰减曲线参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 衰减起始 | 60 天 | 超过 60 天未验证开始衰减 |
| 衰减速率 | 0.05/周 | 每周衰减 0.05 |
| 衰减下限 | 0.1 | 置信度最低不低于 0.1 |
| 人工确认基线 | 0.9 | 人工确认后置信度至少为 0.9 |
| 衰减中断 | 重新验证 | 重新验证后 `last_verified_at` 更新，衰减重新计时 |

衰减曲线示意：

```
置信度
1.0 ┤
0.9 ┤ ──────── 人工确认基线
0.8 ┤ ──── 4+ Session 基础分
0.6 ┤ ──── 2-3 Session 基础分
0.5 ┤          ╲
0.4 ┤           ╲
0.3 ┤ ──── 1 Session 基础分
0.2 ┤            ╲
0.1 ┤ ────────────── 衰减下限
    └────┬────┬────┬────┬────┬───→ 天数
         0   60  120  180  240
              ↑ 衰减起始
```

---

### 4.3 变更日志

#### 4.3.1 KnowledgeChangelog Pydantic 模型

```python
class KnowledgeChangelog(BaseModel):
    change_id: str = Field(description="变更唯一标识，UUID")
    knowledge_type: str = Field(description="知识类型（glossary/module_profile/constraint/decision/risk/requirement_lineage/incident）")
    knowledge_id: str = Field(description="知识记录 ID")
    change_type: str = Field(description="变更类型（created/updated/deprecated/superseded/verified/merged）")
    trigger_session_id: str | None = Field(default=None, description="触发变更的 Session ID，人工变更为 None")
    changed_fields: dict[str, object] = Field(default_factory=dict, description="变更的字段名和旧值")
    changed_at: datetime = Field(description="变更时间")
    operator: str = Field(default="system", description="操作者（system/session_id/human）")
```

#### 4.3.2 knowledge_changelog 表结构

```sql
CREATE TABLE knowledge_changelog (
    change_id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_type      VARCHAR(30)   NOT NULL,
    knowledge_id        UUID          NOT NULL,
    change_type         VARCHAR(20)   NOT NULL,
    trigger_session_id  UUID,
    changed_fields      JSONB         NOT NULL DEFAULT '{}',
    changed_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    operator            VARCHAR(100)  NOT NULL DEFAULT 'system'
);

CREATE INDEX idx_changelog_knowledge ON knowledge_changelog (knowledge_type, knowledge_id);
CREATE INDEX idx_changelog_session ON knowledge_changelog (trigger_session_id);
CREATE INDEX idx_changelog_time ON knowledge_changelog (changed_at);
CREATE INDEX idx_changelog_type ON knowledge_changelog (change_type);
```

#### 4.3.3 append-only 约束

| 约束 | 说明 |
|------|------|
| 只追加 | 表只支持 INSERT，不支持 UPDATE 和 DELETE |
| 不可篡改 | 应用层禁止对已写入记录的任何修改操作 |
| 完整性 | 每条 L3 知识的创建、更新、废弃、验证必须记录到 changelog |
| 审计 | changelog 是知识变更的唯一审计来源 |

**变更日志保留策略**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `l3.changelog.retention_days` | 365 | 变更日志保留天数 |
| `l3.changelog.archive_after_days` | 90 | 超过此天数的日志归档到冷存储 |
| `l3.changelog.cleanup_batch_size` | 1000 | 每次清理任务处理的记录数 |

**归档流程**：

1. index-service 定时任务（每日执行）扫描 `knowledge_changelog` 表中 `created_at < now() - interval 'archive_after_days'` 的记录
2. 将匹配记录写入 MinIO 归档文件（按 `project_id` 和日期分区，Parquet 格式）
3. 归档写入成功后，从 PG 中删除已归档记录
4. 超过 `retention_days` 的归档文件从 MinIO 中删除

**查询兼容**：归档后的变更日志可通过 L3 治理 API 的 `include_archived=true` 参数查询，index-service 会同时查询 PG 和 MinIO 归档文件并合并结果。

---

### 4.5 L2→L3 沉淀触发器

L3 知识的写入不是实时发生的，而是由特定事件触发的批量沉淀操作。本节定义 Event Stream → L3 Writer 的完整衔接规则。

#### 4.5.1 沉淀触发时机

| 触发时机 | 触发条件 | 沉淀范围 | 说明 |
|---------|---------|---------|------|
| Session 完成 | `SESSION_COMPLETED` 事件 | 本次 Session 产生的所有可沉淀 Evidence | 主沉淀路径 |
| Chatback 结束 | 用户确认 Chatback 结论 | Chatback 中新产生的 Evidence + 用户显式声明的知识 | 补充沉淀 |
| 人工验证 | 用户确认某条 Evidence | 被验证的 Evidence 及其关联 | 置信度提升触发 |
| 定期治理 | index-service 定时任务 | stale 知识的重新验证、conflicted 知识的清理 | 治理维护 |

#### 4.5.2 沉淀流水线

```
SESSION_COMPLETED 事件
        │
        ▼
1. 查询本次 Session 的所有 Evidence（M-01 evidence_records 表）
        │
        ▼
2. 按类型过滤可沉淀 Evidence：
   - constraint 类型（EvidenceType.constraint）
   - risk_indicator 类型（EvidenceType.risk_indicator）
   - code_evidence 类型（EvidenceType.code_evidence）→ 模块画像
   - requirement_ref 类型（EvidenceType.requirement_ref）→ 需求谱系
   - verification_result 类型（EvidenceType.verification_result）→ 事故记忆
        │
        ▼
3. 按置信度过滤：仅沉淀 confidence ≥ 0.6 的 Evidence
        │
        ▼
4. 调用 L3Writer.append() 写入对应知识类型
   - constraint → ArchitecturalConstraint
   - risk_indicator → RiskEvolution
   - code_evidence → ModuleProfile（更新）
   - requirement_ref → RequirementLineage
   - verification_result → IncidentMemory
        │
        ▼
5. 写入 knowledge_changelog（append-only）
        │
        ▼
6. 发布 DIMENSION_CHANGED / EVIDENCE_ADDED 类型的 Cognitive 级事件（通知其他服务）
```

#### 4.5.3 沉淀与 Event Stream 的映射

| R-03 事件类型 | 是否触发 L3 沉淀 | 沉淀动作 |
|--------------|-----------------|---------|
| SESSION_COMPLETED | 是（主触发器） | 批量沉淀本次 Session 所有可沉淀 Evidence |
| SESSION_FAILED | 否 | 失败 Session 不触发沉淀 |
| SESSION_CANCELLED | 否 | 取消 Session 不触发沉淀 |
| EVIDENCE_ADDED | 否（仅记录） | Evidence 写入 L2 时不立即沉淀 |
| DIMENSION_CHANGED | 否（仅记录） | 维度状态变更不触发沉淀 |
| TOOL_RETURNED | 否 | 工具返回不直接触发沉淀 |

**设计决策**：沉淀仅在 Session 完成后批量触发，而非每条 Evidence 产生时实时触发。原因：
1. 避免推理过程中频繁写入 L3 影响推理性能
2. Session 完成前的 Evidence 可能被后续步骤推翻，实时沉淀会产生无效知识
3. 批量沉淀可以执行去重和冲突检测，减少 L3 写入次数

---

## 五、L3Writer Protocol 详细设计

### 5.1 L3Writer Protocol 接口定义

```python
from typing import Protocol


class L3Writer(Protocol):
    """L3 知识写入协议，7 种知识类型的不同实现均遵循此接口。"""

    async def append(
        self,
        knowledge_type: str,
        payload: dict,
        evidence_ref: str,
    ) -> L3KnowledgeBase:
        """追加新知识。若去重键已存在，按各类型策略处理（合并/归并/跳过）。"""
        ...

    async def update(
        self,
        knowledge_id: str,
        patch: dict,
        evidence_ref: str,
    ) -> L3KnowledgeBase:
        """更新已有知识。仅更新 patch 中指定的字段，记录 changelog。"""
        ...

    async def deprecate(
        self,
        knowledge_id: str,
        reason: str,
    ) -> L3KnowledgeBase:
        """标记知识为废弃。设置 deprecated/superseded 标记，记录 changelog。"""
        ...

    async def merge(
        self,
        knowledge_ids: list[str],
        strategy: str,
    ) -> L3KnowledgeBase:
        """合并多条知识记录。strategy 指定合并策略（latest/most_confident/manual）。"""
        ...
```

### 5.2 每种知识类型的 L3Writer 实现策略

#### 5.2.1 写入语义矩阵

| 知识类型 | append 语义 | update 语义 | deprecate 语义 | merge 语义 |
|---------|-----------|-----------|---------------|-----------|
| 术语表 | 按 `canonical_name` 去重，已存在则别名合并 | 更新定义/上下文 | 标记 `freshness=deprecated` | 合并别名，取最长定义 |
| 模块画像 | 按 `module_name` 去重，已存在则增量更新 | 后写覆盖 + changelog | 标记 `freshness=deprecated` | 合并风险历史和依赖 |
| 架构约束 | 按 `constraint_hash` 去重，已存在则提升置信度 | 仅更新 `severity`/`scope` | 标记 `deprecated=true` | 不适用（约束不可合并） |
| 决策记录 | 按 `decision_id` 追加，不覆盖 | 仅更新 `status` | 标记 `status=revoked` | 不适用（决策不可合并） |
| 风险演化 | 按 `risk_fingerprint` 归并，追加演化步骤 | 更新 `current_level`/`status` | 标记 `status=closed` | 合并演化轨迹 |
| 需求谱系 | 按 `(requirement_id, version)` 追加 | 更新关系和状态 | 标记 `status=deprecated` | 合并关系图 |
| 事故记忆 | 按 `incident_id` 追加 | 补充修复信息 | 标记 `freshness=deprecated` | 不适用（事故不可合并） |

#### 5.2.2 冲突解决规则

| 冲突类型 | 检测方式 | 解决策略 |
|---------|---------|---------|
| 术语定义冲突 | 同一 `canonical_name` 出现不同定义 | 保留 `human_verified=true` 的版本；均为 LLM 生成时保留信息量更大的版本 |
| 模块职责冲突 | 同一模块在不同 Session 中产生矛盾描述 | 标记为 `conflicted`，触发人工审核 |
| 约束冲突 | 新约束与已有约束矛盾 | 标记新约束为 `conflicted`，不自动覆盖旧约束 |
| 风险等级冲突 | 同一 `risk_fingerprint` 在不同 Session 中评级不同 | 取最高等级（保守策略），追加演化步骤记录差异 |
| 需求关系冲突 | 同一对需求同时存在 `depends_on` 和 `conflicts_with` | 标记关系为 `conflicted`，触发人工确认 |

#### 5.2.3 去重键定义

| 知识类型 | 去重键 | 唯一约束 |
|---------|--------|---------|
| 术语表 | `canonical_name` | `(project_id, canonical_name)` |
| 模块画像 | `module_name` | `(project_id, module_name)` |
| 架构约束 | `constraint_hash` | `(project_id, constraint_hash)` |
| 决策记录 | `decision_id` | `(project_id, decision_id)` |
| 风险演化 | `risk_fingerprint` | `(project_id, risk_fingerprint)` |
| 需求谱系 | `(requirement_id, version)` | `(project_id, requirement_id, version)` |
| 事故记忆 | `incident_id` | `(project_id, incident_id)` |

### 5.5 Evidence→L3 关系迁移规则

当 Evidence 沉淀为 L3 知识时，M-01 中 `evidence_relations` 表记录的证据间关系需要迁移到 M-04 中 `knowledge_relations` 表的知识间关系。

**迁移规则**：

| evidence_relations 关系类型 | knowledge_relations 关系类型 | 迁移条件 |
|---------------------------|----------------------------|---------|
| SUPPORTS | CORROBORATES | 源和目标 Evidence 均已沉淀为 L3 知识 |
| CONTRADICTS | CONFLICTS_WITH | 源和目标 Evidence 均已沉淀为 L3 知识 |
| DERIVED_FROM | EVOLVES_FROM | 源和目标 Evidence 均已沉淀为 L3 知识 |
| SUPERSEDES | SUPERSEDES | 源和目标 Evidence 均已沉淀为 L3 知识 |
| CORROBORATES | CORROBORATES | 源和目标 Evidence 均已沉淀为 L3 知识 |

**迁移流程**：

```
1. Session 完成后，批量沉淀可沉淀 Evidence 到 L3
2. 建立 Evidence ID → L3 Knowledge ID 的映射表
3. 查询 evidence_relations 中源和目标均已沉淀的关系
4. 按上述映射规则转换为 knowledge_relations 记录
5. 关系的 confidence 取源 Evidence 和目标 Evidence 中较低的 confidence
6. 关系的 evidence_ref 设为源 Evidence 的 ID
7. 写入 knowledge_relations 表
```

**冲突处理**：若迁移时发现 `knowledge_relations` 中已存在相同 source→target 的关系但类型不同，保留置信度较高的关系，较低置信度的关系标记为 `superseded_by`。

---

## 六、飞轮自我验证 Schema

### 6.1 VerificationLog Pydantic 模型

```python
class VerificationLog(BaseModel):
    verification_id: str = Field(description="验证记录 ID，UUID")
    project_id: str = Field(description="项目 ID")
    session_id: str = Field(description="触发验证的 Session ID")
    verification_type: str = Field(description="验证类型（full_comparison/sampling/consistency_check）")
    l3_knowledge_count: int = Field(description="本次验证涉及的 L3 知识条目数")
    l3_knowledge_types: list[str] = Field(description="涉及的 L3 知识类型列表")
    v3_quality_score: float = Field(ge=0.0, le=1.0, description="注入 L3 知识的推理质量评分")
    baseline_quality_score: float = Field(ge=0.0, le=1.0, description="占位 L3 的推理质量评分")
    deviation: float = Field(description="偏差值（v3_quality - baseline_quality）")
    deviation_category: str = Field(description="偏差类别（effective/ineffective/harmful）")
    affected_knowledge_ids: list[str] = Field(default_factory=list, description="受影响的知识 ID 列表")
    verified_at: datetime = Field(description="验证时间")
    details: dict[str, object] = Field(default_factory=dict, description="验证详情")
```

### 6.2 verification_log 表结构

```sql
CREATE TABLE verification_log (
    verification_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id           UUID          NOT NULL REFERENCES projects(id),
    session_id           UUID          NOT NULL,
    verification_type    VARCHAR(30)   NOT NULL,
    l3_knowledge_count   INTEGER       NOT NULL,
    l3_knowledge_types   JSONB         NOT NULL DEFAULT '[]',
    v3_quality_score     FLOAT         NOT NULL,
    baseline_quality_score FLOAT       NOT NULL,
    deviation            FLOAT         NOT NULL,
    deviation_category   VARCHAR(20)   NOT NULL,
    affected_knowledge_ids JSONB       NOT NULL DEFAULT '[]',
    verified_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    details              JSONB         NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_verification_project ON verification_log (project_id, verified_at);
CREATE INDEX idx_verification_category ON verification_log (deviation_category);
```

### 6.3 对比实验框架设计

每 10 次 Session 沉淀后自动运行一次完整对比验证：

```python
class VerificationFramework:
    """飞轮自我验证框架。"""

    VERIFICATION_INTERVAL: int = 10  # 每 10 次 Session 沉淀触发一次

    async def run_comparison(
        self,
        session_id: str,
        project_id: str,
        l3_knowledge: list[L3KnowledgeBase],
    ) -> VerificationLog:
        """
        对比实验流程：
        1. 取本次 Session 的 Context Pipeline 注入的 L3 知识
        2. 构造对照组：用占位 L3（相同条目数，但内容随机化）替代
        3. 对比两组在相同需求上的推理质量差异
        4. 记录偏差到 verification_log 表
        """
        ...

    def _randomize_knowledge(
        self,
        knowledge: list[L3KnowledgeBase],
    ) -> list[L3KnowledgeBase]:
        """生成占位 L3 知识：保持条目数和类型相同，内容替换为随机文本。"""
        ...

    def _compute_quality_score(
        self,
        evidence_chain: list,
        dimension_results: list,
    ) -> float:
        """
        计算推理质量评分，综合以下指标：
        - Evidence 覆盖率：7 维度中多少有支撑证据
        - Evidence 置信度：证据链的平均置信度
        - 风险检出率：与历史基线对比的风险检出比例
        - 推理步数效率：达到同等分析深度所需的推理步数
        """
        ...

    def classify_deviation(
        self,
        v3_score: float,
        baseline_score: float,
    ) -> str:
        """偏差分类。"""
        deviation = v3_score - baseline_score
        if deviation > 0.05:
            return "effective"
        elif deviation > -0.05:
            return "ineffective"
        else:
            return "harmful"
```

### 6.4 偏差处理规则

| 偏差类别 | 偏差程度 | 含义 | 处理 |
|---------|---------|------|------|
| `effective` | V3 质量 > 占位质量 + 0.05 | L3 注入有效 | 相关知识 `confidence_score += 0.05`（上限 1.0） |
| `ineffective` | \|V3 - 占位\| <= 0.05 | L3 注入无效 | 标记相关知识为 `under_review`，不进入下一次注入 |
| `harmful` | V3 质量 < 占位质量 - 0.05 | L3 注入有害 | 标记相关知识为 `harmful`，触发人工审核，暂停飞轮注入 |

`under_review` 和 `harmful` 不是 `FreshnessStatus` 的正式状态，而是通过 `freshness = conflicted` + 详情字段标记：

```python
# 无效偏差处理
knowledge.freshness = FreshnessStatus.CONFLICTED
knowledge.updated_at = datetime.now()
# 写入 changelog
changelog = KnowledgeChangelog(
    change_id=str(uuid4()),
    knowledge_type=knowledge.__class__.__name__,
    knowledge_id=knowledge.id,
    change_type="updated",
    changed_fields={"freshness": "active", "conflict_reason": "ineffective_in_verification"},
    changed_at=datetime.now(),
    operator="verification_framework",
)

# 有害偏差处理：暂停飞轮，触发人工审核
knowledge.freshness = FreshnessStatus.CONFLICTED
# 同时发送通知到前端，提示人工审核
```

---

## 七、L3-B Cognitive Patterns 预留接口

### 7.1 CognitivePattern Pydantic 模型

Phase 3 实现，当前仅定义接口和预留 Schema：

```python
class CognitivePattern(L3KnowledgeBase):
    """认知模式：跨事实抽象后的稳定模式。Phase 3 实现。"""
    pattern_id: str = Field(description="模式 ID，格式 PAT-{NNN}")
    pattern_type: str = Field(description="模式类型（architectural_style/behavioral_pattern/risk_pattern/decision_pattern）")
    title: str = Field(description="模式标题")
    description: str = Field(description="模式描述")
    source_fact_ids: list[str] = Field(default_factory=list, description="抽象来源的 L3-A 事实 ID 列表")
    abstraction_level: int = Field(default=1, ge=1, le=5, description="抽象层级（1=事实级，5=最高抽象）")
    applicability: str | None = Field(default=None, description="适用条件描述")
    counter_examples: list[str] = Field(default_factory=list, description="反例描述")
    validation_status: str = Field(default="candidate", description="验证状态（candidate/validated/invalidated）")
```

### 7.2 cognitive_patterns 表 Schema 预留

```sql
CREATE TABLE cognitive_patterns (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID          NOT NULL REFERENCES projects(id),
    pattern_id          VARCHAR(20)   NOT NULL,
    pattern_type        VARCHAR(30)   NOT NULL,
    title               VARCHAR(500)  NOT NULL,
    description         TEXT          NOT NULL,
    source_fact_ids     JSONB         NOT NULL DEFAULT '[]',
    abstraction_level   INTEGER       NOT NULL DEFAULT 1,
    applicability       TEXT,
    counter_examples    JSONB         NOT NULL DEFAULT '[]',
    validation_status   VARCHAR(20)   NOT NULL DEFAULT 'candidate',

    -- 治理元数据
    freshness           VARCHAR(20)  NOT NULL DEFAULT 'active',
    confidence_score    FLOAT        NOT NULL DEFAULT 0.3,
    verification_count  INTEGER      NOT NULL DEFAULT 0,
    source_session_count INTEGER     NOT NULL DEFAULT 1,
    human_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_verified_at    TIMESTAMPTZ,
    superseded_by       UUID,

    source_session_ids  JSONB        NOT NULL DEFAULT '[]',
    evidence_refs       JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, pattern_id)
);

-- Phase 3 激活时创建索引
-- CREATE INDEX idx_patterns_project_freshness ON cognitive_patterns (project_id, freshness);
-- CREATE INDEX idx_patterns_type ON cognitive_patterns (project_id, pattern_type);
-- CREATE INDEX idx_patterns_validation ON cognitive_patterns (project_id, validation_status);
```

---

## 八、存储引擎总览

### 8.1 各知识类型在 PG/ChromaDB 中的分布

| 知识类型 | PostgreSQL | ChromaDB | 说明 |
|---------|-----------|----------|------|
| 术语表 | `glossary` 表 | `glossary_embeddings` 集合 | 术语定义的语义检索 |
| 模块画像 | `module_profiles` 表 | `module_embeddings` 集合 | 模块职责描述的语义检索 |
| 架构约束 | `constraints` 表 | `constraint_embeddings` 集合 | 约束描述的语义检索 |
| 决策记录 | `decisions` 表 | `decision_embeddings` 集合 | 决策内容的语义检索 |
| 风险演化 | `risks` + `risk_evolution` + `risk_mitigations` 表 | `risk_embeddings` 集合 | 风险描述的语义检索 |
| 需求谱系 | `requirement_lineage` + `requirement_relations` 表 | `requirement_embeddings` 集合 | 需求描述的语义检索 |
| 事故记忆 | `incidents` 表 | `incident_embeddings` 集合 | 事故描述的语义检索 |
| 知识关系 | `knowledge_relations` 表 | - | 关系查询走 PG |
| 变更日志 | `knowledge_changelog` 表 | - | 纯结构化数据 |
| 验证日志 | `verification_log` 表 | - | 纯结构化数据 |
| 认知模式 | `cognitive_patterns` 表（预留） | `pattern_embeddings` 集合（预留） | Phase 3 激活 |

### 8.2 ChromaDB 集合设计

每个知识类型对应一个 ChromaDB 集合，存储该类型知识的文本 embedding：

| 集合名 | embedding 来源 | 检索场景 |
|--------|--------------|---------|
| `glossary_embeddings` | `canonical_name + definition` | Context Pipeline 术语匹配 |
| `module_embeddings` | `module_name + responsibility` | 模块关联检索 |
| `constraint_embeddings` | `title + description` | 约束匹配检索 |
| `decision_embeddings` | `title + context + decision` | 决策背景检索 |
| `risk_embeddings` | `title + description` | 风险匹配检索 |
| `requirement_embeddings` | `title + description` | 需求关联检索 |
| `incident_embeddings` | `title + root_cause` | 事故匹配检索 |

ChromaDB 集合中的每条记录与 PG 表记录通过 `id`（UUID）关联。PG 为主存储，ChromaDB 为辅助检索索引。

### 8.3 知识关系存储

```sql
CREATE TABLE knowledge_relations (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID         NOT NULL REFERENCES projects(id),
    source_type     VARCHAR(30)  NOT NULL,
    source_id       UUID         NOT NULL,
    relation_type   VARCHAR(30)  NOT NULL,
    target_type     VARCHAR(30)  NOT NULL,
    target_id       UUID         NOT NULL,
    confidence      FLOAT        NOT NULL DEFAULT 0.5,
    evidence_ref    VARCHAR(500),
    freshness       VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (project_id, source_type, source_id, relation_type, target_type, target_id)
);

CREATE INDEX idx_knowledge_relations_source ON knowledge_relations (source_type, source_id);
CREATE INDEX idx_knowledge_relations_target ON knowledge_relations (target_type, target_id);
CREATE INDEX idx_knowledge_relations_type ON knowledge_relations (relation_type);
```

关系类型枚举：

| relation_type | 含义 |
|---------------|------|
| `DEPENDS_ON` | 依赖关系 |
| `IMPACTS` | 影响关系 |
| `CONFLICTS_WITH` | 冲突关系 |
| `EVOLVES_FROM` | 演化来源 |
| `MITIGATES` | 缓解关系 |
| `VIOLATES` | 违反关系 |
| `DERIVED_FROM` | 派生关系 |

---

## 九、接口定义

### 9.1 L3 知识查询 API

所有查询 API 由 index-service 提供，cognitive-rt 和 api-service 通过内部 HTTP 调用。

#### 9.1.1 按类型查询

```
GET /api/v2/projects/{project_id}/knowledge/{knowledge_type}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `knowledge_type` | path | 知识类型（glossary/module_profile/constraint/decision/risk/requirement_lineage/incident） |
| `freshness` | query | 新鲜度过滤（默认 `active`） |
| `min_confidence` | query | 最低置信度过滤（默认 `0.6`） |
| `limit` | query | 返回条数上限（默认 `50`，最大 `200`） |
| `offset` | query | 分页偏移量 |

响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "knowledge_type": "glossary",
      "data": { "...知识类型特定字段..." },
      "freshness": "active",
      "confidence_score": 0.8,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-05-20T14:30:00Z"
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

#### 9.1.2 按项目聚合查询

```
GET /api/v2/projects/{project_id}/knowledge
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `freshness` | query | 新鲜度过滤 |
| `min_confidence` | query | 最低置信度过滤 |
| `knowledge_types` | query | 知识类型过滤（逗号分隔） |

响应：返回各类型的统计摘要和 top 条目。

#### 9.1.3 语义检索

```
POST /api/v2/projects/{project_id}/knowledge/search
```

请求体：

```json
{
  "query": "支付模块的并发风险",
  "knowledge_types": ["risk", "constraint", "incident"],
  "freshness": "active",
  "min_confidence": 0.6,
  "top_k": 10
}
```

响应：按语义相似度排序的知识条目列表。

### 9.2 L3 知识写入 API

写入操作通过 L3Writer Protocol 执行，由 index-service 暴露内部 API：

```
POST /api/v2/internal/knowledge/append
POST /api/v2/internal/knowledge/update
POST /api/v2/internal/knowledge/deprecate
POST /api/v2/internal/knowledge/merge
```

#### 9.2.1 append 请求

```json
{
  "knowledge_type": "glossary",
  "project_id": "uuid",
  "payload": {
    "canonical_name": "points_engine",
    "definition": "积分计算引擎",
    "aliases": ["PE"],
    "context": "用于处理积分的累积和扣减",
    "related_modules": ["points"]
  },
  "evidence_ref": "evidence-uuid",
  "session_id": "session-uuid"
}
```

#### 9.2.2 update 请求

```json
{
  "knowledge_id": "uuid",
  "patch": {
    "definition": "积分计算引擎，支持同步和异步两种模式",
    "aliases": ["PE", "积分引擎"]
  },
  "evidence_ref": "evidence-uuid",
  "session_id": "session-uuid"
}
```

#### 9.2.3 deprecate 请求

```json
{
  "knowledge_id": "uuid",
  "reason": "该术语已不再使用，被 points_service 替代"
}
```

#### 9.2.4 merge 请求

```json
{
  "knowledge_ids": ["uuid-1", "uuid-2"],
  "strategy": "most_confident"
}
```

### 9.3 L3 知识治理 API

#### 9.3.1 验证知识

```
POST /api/v2/projects/{project_id}/knowledge/{knowledge_id}/verify
```

请求体：

```json
{
  "verified_by": "human",
  "notes": "确认该术语定义准确"
}
```

效果：`human_verified = true`，`confidence_score` 提升至 0.9，`last_verified_at` 更新。

#### 9.3.2 标记知识新鲜度

```
PUT /api/v2/projects/{project_id}/knowledge/{knowledge_id}/freshness
```

请求体：

```json
{
  "freshness": "historical",
  "reason": "该约束已不适用于新架构"
}
```

#### 9.3.3 查询变更日志

```
GET /api/v2/projects/{project_id}/knowledge/changelog
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `knowledge_type` | query | 按知识类型过滤 |
| `knowledge_id` | query | 按知识 ID 过滤 |
| `change_type` | query | 按变更类型过滤 |
| `since` | query | 起始时间 |
| `until` | query | 截止时间 |
| `limit` | query | 返回条数上限 |

---

## 十、错误处理

### 10.1 错误类型定义

```python
class L3KnowledgeError(ReqRadarException):
    """L3 知识操作基础异常。"""
    pass


class WriteConflictError(L3KnowledgeError):
    """写入冲突：并发写入同一条知识记录。"""
    pass


class MergeFailureError(L3KnowledgeError):
    """归并失败：无法自动归并的知识记录。"""
    pass


class GovernanceInconsistencyError(L3KnowledgeError):
    """治理状态不一致：新鲜度/置信度与实际状态不符。"""
    pass


class DeprecationViolationError(L3KnowledgeError):
    """废弃违规：尝试修改已废弃的知识记录。"""
    pass


class DuplicateKeyError(L3KnowledgeError):
    """去重键冲突：写入的知识与已有记录去重键相同。"""
    pass
```

### 10.2 错误处理策略

| 错误场景 | 处理策略 |
|---------|---------|
| 写入冲突 | 乐观锁重试（3 次），仍失败则标记为 `conflicted`，记录 changelog |
| 归并失败 | 保留两条记录，标记为 `conflicted`，触发人工审核 |
| 治理状态不一致 | 定时任务扫描并修复：`stale` 状态但最近有验证的记录恢复为 `active` |
| 废弃违规 | 拒绝修改，返回 `DeprecationViolationError`，提示创建新记录替代 |
| 去重键冲突 | 按各类型的合并逻辑处理（见 5.2.1），合并失败则标记 `conflicted` |
| ChromaDB 写入失败 | PG 写入成功但 ChromaDB 失败时，标记记录为 `index_pending`，后台任务重试 |
| 批量写入部分失败 | 记录失败条目到 changelog，成功条目正常提交，返回部分成功响应 |

### 10.3 重试与补偿

```python
L3_WRITE_MAX_RETRIES = 3
L3_WRITE_RETRY_DELAY_MS = 100
CHROMADB_RETRY_MAX_ATTEMPTS = 5
CHROMADB_RETRY_DELAY_MS = 500
STALE_CHECK_INTERVAL_HOURS = 24
CONSISTENCY_CHECK_INTERVAL_HOURS = 6
```

---

## 十一、配置参数

### 11.1 治理相关配置

| 配置键 | 默认值 | 说明 |
|--------|-------|------|
| `governance.freshness.stale_threshold_days` | 90 | 超过此天数未验证标记为 stale |
| `governance.freshness.historical_after_days` | 180 | 超过此天数自动降级为 historical |
| `governance.freshness.stale_check_interval_hours` | 24 | stale 检查的运行间隔 |
| `governance.confidence.base_score_single_session` | 0.3 | 单 Session 产生知识的基础分 |
| `governance.confidence.base_score_multi_session` | 0.6 | 2-3 Session 产生知识的基础分 |
| `governance.confidence.base_score_many_sessions` | 0.8 | 4+ Session 产生知识的基础分 |
| `governance.confidence.human_verified_baseline` | 0.9 | 人工确认后的置信度基线 |
| `governance.confidence.decay_start_days` | 60 | 衰减开始天数 |
| `governance.confidence.decay_rate_per_week` | 0.05 | 每周衰减量 |
| `governance.confidence.decay_minimum` | 0.1 | 衰减下限 |
| `governance.verification.interval_sessions` | 10 | 每 N 次 Session 沉淀触发一次验证 |
| `governance.verification.effective_confidence_boost` | 0.05 | 有效验证的置信度加成 |
| `governance.verification.ineffective_threshold` | 0.05 | 无效偏差阈值 |
| `governance.verification.harmful_threshold` | -0.05 | 有害偏差阈值 |
| `governance.injection.min_confidence` | 0.6 | Context Pipeline 注入的最低置信度 |
| `governance.injection.default_freshness_filter` | `["active"]` | 默认注入的新鲜度过滤 |

### 11.2 写入相关配置

| 配置键 | 默认值 | 说明 |
|--------|-------|------|
| `l3_write.max_retries` | 3 | 写入冲突重试次数 |
| `l3_write.retry_delay_ms` | 100 | 重试间隔（毫秒） |
| `l3_write.chromadb_retry_max` | 5 | ChromaDB 写入重试次数 |
| `l3_write.chromadb_retry_delay_ms` | 500 | ChromaDB 重试间隔（毫秒） |
| `l3_write.batch_size` | 50 | 批量写入单批大小 |
| `l3_write.dependency_snapshot_max` | 5 | 模块画像保留的依赖快照数 |

### 11.3 配置矩阵位置

以上配置位于 Scope x Domain 矩阵的 `PROJECT` 和 `SYSTEM` 行、`INDEX` 列：

| | INDEX |
|--|-------|
| **SYSTEM** | 全局治理默认值 |
| **PROJECT** | 项目级治理覆盖（如高风险项目可缩短 stale 阈值） |

---

## 十二、与其他模块的关系

### 12.1 模块依赖关系图

```
                    ┌─────────────────┐
                    │  M-03 Cognitive  │
                    │     State        │
                    │  (本文档)         │
                    └──┬────┬────┬────┘
                       │    │    │
          ┌────────────┘    │    └────────────┐
          ▼                 ▼                 ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  M-01       │  │  M-04       │  │  R-02       │
   │  Evidence   │  │  Cognitive  │  │  Context    │
   │  Model      │  │  Graph      │  │  Pipeline   │
   └─────────────┘  └─────────────┘  └─────────────┘
          ▲                 ▲                 ▲
          │                 │                 │
   ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐
   │  R-01       │  │  I-01       │  │  I-03       │
   │  Session    │  │  Service    │  │  DB         │
   │  Lifecycle  │  │  API        │  │  Migration  │
   └─────────────┘  └─────────────┘  └─────────────┘
```

### 12.2 具体交互

| 交互模块 | 交互方式 | 说明 |
|---------|---------|------|
| **M-01 Evidence Model** | L3 写入时引用 | L3Writer.append/update 的 `evidence_ref` 参数引用 L2 Evidence ID；Evidence 验证后沉淀到 L3 |
| **M-04 Cognitive Graph Schema** | 共享 Relation Contract | L3 的 `knowledge_relations` 表使用 M-04 定义的统一 Relation Contract；Graph 查询接口预留 |
| **R-01 Session Lifecycle** | L3 沉淀触发 | Session 完成后，index-service 从 L2 提取可沉淀知识，调用 L3Writer 写入 L3 |
| **R-02 Context Pipeline** | L3 知识注入 | Context Pipeline 的 Collect 阶段从 L3 查询知识，按 `freshness=active` + `confidence >= 0.6` 过滤 |
| **I-01 Service API Contract** | 内部 API | cognitive-rt 通过 I-01 定义的内部 API 调用 index-service 的 L3 查询/写入接口 |
| **I-03 DB Migration** | 表结构迁移 | L3 各表的 DDL 和数据迁移策略由 I-03 管理 |

### 12.3 数据流向

```
R-01 Session 完成
    │
    ▼
index-service 从 L2 提取可沉淀知识
    │
    ▼
L3Writer.append/update 写入 L3
    │
    ├── PG 写入知识记录
    ├── ChromaDB 写入 embedding
    ├── knowledge_changelog 追加变更记录
    │
    ▼
R-02 Context Pipeline Collect 阶段
    │
    ├── PG 查询结构化知识
    ├── ChromaDB 语义检索
    │
    ▼
注入到新 Session 的上下文
```

---

## 十三、测试策略

### 13.1 测试分层

| 层级 | 覆盖范围 | 测试类型 |
|------|---------|---------|
| 单元测试 | Pydantic 模型验证、置信度计算、fingerprint 计算、去重逻辑 | pytest |
| 集成测试 | L3Writer 各实现类的 PG 读写、ChromaDB 写入检索、changelog 追加 | pytest + testcontainers |
| 服务测试 | index-service 的 L3 API 端到端验证 | httpx AsyncClient |
| 治理测试 | 新鲜度状态迁移、置信度衰减、stale 检测定时任务 | pytest + 时间 mock |
| 验证测试 | 对比实验框架、偏差分类、飞轮暂停/恢复 | pytest |

### 13.2 关键测试用例

#### 13.2.1 术语表

| 用例 | 说明 |
|------|------|
| 追加新术语 | `canonical_name` 不存在时正常追加 |
| 别名合并 | `canonical_name` 已存在时合并别名，不覆盖定义 |
| 去重规范化 | 不同大小写/空格的 `canonical_name` 归一化后去重 |
| 人工确认保护 | `human_verified=true` 的定义不被 LLM 生成内容覆盖 |

#### 13.2.2 模块画像

| 用例 | 说明 |
|------|------|
| 增量更新 | 新 Session 分析同一模块时增量更新 `analysis_count` 和 `last_analyzed_at` |
| 风险历史追加 | 新风险追加到 `risk_history`，同一 `risk_id` 不重复 |
| 依赖快照对比 | 新快照与旧快照对比，检测新增/移除依赖 |

#### 13.2.3 架构约束

| 用例 | 说明 |
|------|------|
| constraint_hash 去重 | 相同描述的约束不重复写入 |
| deprecated 标记 | 废弃后不注入 Context Pipeline |
| 不可删除 | 约束记录无 DELETE 操作 |

#### 13.2.4 风险演化

| 用例 | 说明 |
|------|------|
| fingerprint 归并 | 不同描述但同一风险自动归并 |
| 演化轨迹追加 | 每次等级变更追加 EvolutionStep |
| 缓解措施记录 | 缓解措施独立记录，关联到风险 |

#### 13.2.5 治理框架

| 用例 | 说明 |
|------|------|
| 新鲜度状态迁移 | 各状态间合法迁移路径 |
| stale 自动标记 | 超过阈值天数未验证自动标记 |
| 置信度衰减 | 60 天后按周衰减，最低 0.1 |
| 人工确认提升 | `human_verified=true` 后置信度提升至 0.9 |

#### 13.2.6 飞轮验证

| 用例 | 说明 |
|------|------|
| 有效偏差 | V3 质量显著高于基线，置信度加成 |
| 无效偏差 | V3 质量与基线持平，标记 under_review |
| 有害偏差 | V3 质量低于基线，暂停飞轮 |

#### 13.2.7 L3Writer Protocol

| 用例 | 说明 |
|------|------|
| 并发写入冲突 | 乐观锁重试机制 |
| 合并失败回退 | 无法自动合并时标记 conflicted |
| changelog 完整性 | 所有操作均记录到 changelog |

### 13.3 测试隔离要求

- 每个 L3 知识表测试使用独立 SQLite 或 PG testcontainer
- ChromaDB 测试使用临时集合，测试结束销毁
- 时间相关测试 mock `datetime.now()`
- 外部 LLM 调用全部 mock

---

## 十四、明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| L3 引入图数据库 | 暂不引入 | ADR-015：当前 PG 关联表满足需求，接口层预留切换能力 |
| L3-B 模式层实现 | Phase 1 不做 | 先完成 L3-A 的沉淀和治理验证，再抽象模式层 |
| 跨项目认知共享 | Phase 1 不做 | 先在单项目内验证飞轮效应 |
| 知识自动删除 | 永不做 | "组织不再失忆"的技术保障，只可标记废弃 |
| LLM 推断知识直接注入 | 不做 | LLM 推断的知识必须经过 `confidence >= 0.6` 过滤，`INFERRED_KNOWLEDGE` 基础权重 0.4 |
| 完整知识治理运行时 | Phase 1 不做 | 先建立治理元数据基础（新鲜度/置信度/changelog），治理算法逐步迭代 |
| 语义归一化算法 | Phase 3 实现 | Phase 1 仅使用 fingerprint 哈希匹配，精确语义归一化作为 Phase 3 专项 |
| 知识版本分支 | 不做 | L3 知识按 append-only 演化，不引入分支概念 |
| 自动化知识冲突解决 | 不做 | 冲突标记为 `conflicted`，触发人工审核，不做自动解决 |
| 知识导出/同步 | Phase 1 不做 | 后续按需实现跨实例知识同步 |

---

## 附录 A：L3 知识类型速查表

| 类型 | 去重键 | 写入策略 | 冲突解决 | PG 表 | ChromaDB 集合 |
|------|--------|---------|---------|-------|--------------|
| 术语表 | `canonical_name` | append + 别名合并 | 保留长定义 | `glossary` | `glossary_embeddings` |
| 模块画像 | `module_name` | update 增量 | 后写覆盖 + changelog | `module_profiles` | `module_embeddings` |
| 架构约束 | `constraint_hash` | append + deprecated | 人工解决 | `constraints` | `constraint_embeddings` |
| 决策记录 | `decision_id` | append | 时间线排序 | `decisions` | `decision_embeddings` |
| 风险演化 | `risk_fingerprint` | append + canonical_id 归并 | fingerprint 哈希 | `risks` + `risk_evolution` + `risk_mitigations` | `risk_embeddings` |
| 需求谱系 | `(requirement_id, version)` | append + 图结构 | 派生关系推断 | `requirement_lineage` + `requirement_relations` | `requirement_embeddings` |
| 事故记忆 | `incident_id` | append | 时间线排序 | `incidents` | `incident_embeddings` |

## 附录 B：治理状态速查表

| FreshnessStatus | 含义 | Context Pipeline 行为 | 触发条件 |
|-----------------|------|---------------------|---------|
| `active` | 当前有效 | 默认注入 | 新写入 / 重新验证 |
| `historical` | 历史知识 | 仅查询返回 | 人工标记 / 超过 180 天 |
| `superseded` | 已被替代 | 不注入 | 新知识替代 |
| `deprecated` | 已废弃 | 不注入 | 人工废弃 |
| `stale` | 长期未验证 | 不注入，触发验证 | 超过 90 天未验证 |
| `conflicted` | 存在冲突 | 不注入，触发审核 | 检测到冲突 / 验证无效 |

## 附录 C：置信度计算速查表

| 场景 | 基础分 | 人工确认 | 衰减 |
|------|--------|---------|------|
| 1 个 Session 产生 | 0.3 | - | - |
| 2-3 个 Session 产生 | 0.6 | - | - |
| 4+ 个 Session 产生 | 0.8 | - | - |
| 人工确认 | max(基础分, 0.9) | 0.9 | - |
| 60 天未验证 | - | - | 每周 -0.05 |
| 衰减下限 | - | - | 最低 0.1 |
| 验证有效 | +0.05 | - | - |
