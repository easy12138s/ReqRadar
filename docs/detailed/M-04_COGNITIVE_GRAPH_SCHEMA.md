# M-04 Cognitive Graph Schema — 认知图谱 Schema 详细设计

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | 认知图谱的 Schema 定义、关系契约、存储设计与查询接口详细规格 |
| 前置文档 | 00_PROJECT_POSITIONING.md（项目宪法）、01_RESTRUCTURE_OVERVIEW.md（Runtime 蓝图，ADR-015）、02_SYSTEM_ARCHITECTURE.md（总体架构）、03_COGNITIVE_ASSET_MODEL.md（认知资产模型，6.5/6.6 节） |
| 核心目标 | 定义 L3 知识节点间关系的统一管理层——当前用 PG 关联表实现，接口层预留 Graph 演化能力 |
| 文档职责 | 为 index-service 的知识关系存储、cognitive-rt 的关系发现、Context Pipeline 的知识注入查询提供完整的设计基线 |

---

## 一、概述

### 1.1 认知图谱在 V2 中的定位

认知图谱（Cognitive Graph）是 ReqRadar V2 中 L3 持久化知识层的关系管理层。它不是独立的图数据库产品，而是 **L3 知识节点间关系的统一抽象层**：

- **L3-A 知识节点**：术语表、模块画像、架构约束、决策记录、风险演化、需求谱系、事故记忆——每种类型的一个实例就是一个知识节点
- **知识关系**：节点间的有向关系，由 Relation Contract 统一管理
- **当前实现**：PostgreSQL `knowledge_relations` 关联表
- **演化方向**：接口层预留 Graph 查询抽象，未来可切换到图数据库（ADR-015）

### 1.2 核心价值

认知图谱解决的核心问题：**L3 知识不是孤立的条目，而是相互关联的网络**。

没有图谱，L3 只是一堆独立的知识卡片；有了图谱，系统能够：

| 能力 | 无图谱 | 有图谱 |
|------|--------|--------|
| 影响分析 | "模块 X 有风险" | "模块 X 的风险会影响依赖它的 Y、Z 模块" |
| 冲突检测 | 无法发现 | "需求 A 与约束 B 存在冲突" |
| 知识溯源 | "这条知识从哪来？" | "这条知识由 Evidence E 支撑，且被另外 3 条知识佐证" |
| 上下文关联注入 | 只注入当前模块的知识 | 自动扩展到关联模块、关联约束、关联风险 |

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| 接口与存储分离 | Relation Contract 是稳定接口，PG 关联表是可替换实现 |
| 证据驱动 | 每条关系必须有 L2 Evidence 或人工声明支撑，不允许无来源关系 |
| 有向关系 | 所有关系都有方向语义，A → B 与 B → A 含义不同 |
| 置信度量化 | 关系本身携带置信度，低置信度关系不参与 Context Pipeline 注入 |
| 追加不可删 | 关系创建后不可删除，只可标记为 `superseded` 或 `deprecated` |

---

## 二、核心概念

### 2.1 知识节点（Knowledge Node）

L3 中每种知识类型的一个实例。节点不是独立实体表，而是对 L3-A 各知识表的统一引用：

```python
class KnowledgeNode:
    node_type: KnowledgeNodeType  # 节点类型
    node_id: str                  # 节点在其所属知识表中的主键
    project_id: str               # 所属项目
```

节点本身不存储内容，内容存储在对应的 L3-A 知识表中（`glossary`、`module_profiles`、`constraints` 等）。图谱只管理节点间的关系。

### 2.2 知识关系（Knowledge Relation）

节点间的有向关系，由统一 Relation Contract 定义：

```python
class KnowledgeRelation:
    source_type: KnowledgeNodeType
    source_id: str
    relation_type: RelationType
    target_type: KnowledgeNodeType
    target_id: str
    confidence: float
    evidence_ref: str
    created_at: datetime
    freshness: FreshnessStatus
```

### 2.3 关系置信度（Relation Confidence）

关系本身的可信程度，取值范围 0.0-1.0。置信度决定关系是否参与 Context Pipeline 注入：

| 置信度区间 | 含义 | Context Pipeline 行为 |
|-----------|------|----------------------|
| 0.8 - 1.0 | 高置信度，多次验证或人工确认 | 默认注入 |
| 0.6 - 0.8 | 中等置信度，有证据支撑 | 默认注入 |
| 0.3 - 0.6 | 低置信度，仅单次推断 | 不注入，仅查询时可见 |
| 0.0 - 0.3 | 极低置信度，待验证 | 不注入，标记为 `under_review` |

### 2.4 证据支撑（Evidence Backing）

每条关系必须有证据支撑，这是认知图谱与普通关联表的本质区别：

| 证据来源 | evidence_ref 格式 | 说明 |
|---------|-------------------|------|
| L2 Evidence | `evidence://{evidence_id}` | 从分析记录中提取的关系 |
| 人工声明 | `human_declared://{user_id}/{timestamp}` | 用户通过 UI 或 API 显式声明 |
| 系统推断 | `inferred://{session_id}/{step_id}` | cognitive-rt 在推理过程中推断，置信度上限 0.6 |

**无证据的关系不允许创建**。这是硬约束，由 API 层和数据库约束共同保证。

---

## 三、Relation Contract 详细设计

### 3.1 KnowledgeRelation Pydantic 模型

```python
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field
from reqradar.kernel.types.freshness import FreshnessStatus


class KnowledgeNodeType(StrEnum):
    MODULE = "module"
    RISK = "risk"
    DECISION = "decision"
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    INCIDENT = "incident"
    GLOSSARY = "glossary"


class RelationType(StrEnum):
    DEPENDS_ON = "DEPENDS_ON"
    IMPACTS = "IMPACTS"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    EVOLVES_FROM = "EVOLVES_FROM"
    MITIGATES = "MITIGATES"
    VIOLATES = "VIOLATES"
    DERIVED_FROM = "DERIVED_FROM"
    CORROBORATES = "CORROBORATES"
    SUPERSEDES = "SUPERSEDES"


class KnowledgeRelation(BaseModel):
    relation_id: str = Field(
        ...,
        description="关系唯一标识，UUID v4",
        min_length=36,
        max_length=36,
    )
    project_id: str = Field(
        ...,
        description="所属项目 ID",
    )
    source_type: KnowledgeNodeType = Field(
        ...,
        description="源节点类型",
    )
    source_id: str = Field(
        ...,
        description="源节点在其所属知识表中的主键",
    )
    relation_type: RelationType = Field(
        ...,
        description="关系类型",
    )
    target_type: KnowledgeNodeType = Field(
        ...,
        description="目标节点类型",
    )
    target_id: str = Field(
        ...,
        description="目标节点在其所属知识表中的主键",
    )
    confidence: float = Field(
        ...,
        description="关系置信度，取值 0.0-1.0",
        ge=0.0,
        le=1.0,
    )
    evidence_ref: str = Field(
        ...,
        description="支撑该关系的 L2 Evidence ID 或人工声明标识",
        min_length=1,
    )
    freshness: FreshnessStatus = Field(
        default=FreshnessStatus.ACTIVE,
        description="关系新鲜度，继承知识新鲜度模型",
    )
    description: str | None = Field(
        default=None,
        description="关系语义说明（可选），用于人工声明时补充上下文",
        max_length=500,
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="创建时间",
    )
    created_by: str = Field(
        ...,
        description="创建者标识：session_id 或 user_id",
    )
    superseded_by: str | None = Field(
        default=None,
        description="替代此关系的新关系 ID（仅当 freshness=SUPERSEDED 时有值）",
    )

    model_config = {"frozen": True}
```

### 3.2 RelationType 枚举详细定义

| 关系类型 | 语义说明 | 适用场景 | 方向性规则 |
|---------|---------|---------|-----------|
| `DEPENDS_ON` | 源节点依赖目标节点 | 模块间依赖、需求间依赖 | module → module：模块 A 依赖模块 B；requirement → requirement：需求 A 依赖需求 B |
| `IMPACTS` | 源节点影响目标节点 | 风险影响模块、决策影响需求 | risk → module：风险 R 影响模块 M；decision → requirement：决策 D 影响需求 R |
| `CONFLICTS_WITH` | 源节点与目标节点存在冲突 | 需求冲突、约束冲突 | requirement ↔ requirement：需求 A 与需求 B 冲突；constraint ↔ requirement：约束 C 与需求 R 冲突 |
| `EVOLVES_FROM` | 源节点由目标节点演化而来 | 风险演化、需求版本演化 | risk → risk：风险 R2 由风险 R1 演化而来；requirement → requirement：需求 V2 由 V1 演化而来 |
| `MITIGATES` | 源节点缓解目标节点 | 决策缓解风险、约束缓解风险 | decision → risk：决策 D 缓解风险 R；constraint → risk：约束 C 缓解风险 R |
| `VIOLATES` | 源节点违反目标节点 | 需求违反约束、代码违反约束 | requirement → constraint：需求 R 违反约束 C；incident → constraint：事故 I 违反约束 C |
| `DERIVED_FROM` | 源节点派生自目标节点 | 需求派生、决策派生 | requirement → requirement：需求 A 派生自需求 B；decision → decision：子决策派生自父决策 |
| `CORROBORATES` | 源节点佐证目标节点 | 多条证据互相佐证、知识互相印证 | glossary ↔ glossary：术语 A 佐证术语 B 的定义；risk ↔ risk：风险 R1 佐证风险 R2 的存在 |
| `SUPERSEDES` | 源节点替代目标节点 | 知识版本替代 | risk → risk：风险 R2 替代风险 R1；constraint → constraint：约束 C2 替代约束 C1 |

### 3.3 关系方向性规则

关系是有向的，但部分关系类型允许反向查询时使用对称语义：

| 关系类型 | 正向语义 | 反向语义 | 对称性 |
|---------|---------|---------|--------|
| `DEPENDS_ON` | A 依赖 B | B 被 A 依赖 | 非对称 |
| `IMPACTS` | A 影响 B | B 被 A 影响 | 非对称 |
| `CONFLICTS_WITH` | A 与 B 冲突 | B 与 A 冲突 | 对称（存储时只存一条） |
| `EVOLVES_FROM` | A 由 B 演化 | B 演化为 A | 非对称 |
| `MITIGATES` | A 缓解 B | B 被 A 缓解 | 非对称 |
| `VIOLATES` | A 违反 B | B 被 A 违反 | 非对称 |
| `DERIVED_FROM` | A 派生自 B | B 派生出 A | 非对称 |
| `CORROBORATES` | A 佐证 B | B 被 A 佐证 | 对称（存储时只存一条） |
| `SUPERSEDES` | A 替代 B | B 被 A 替代 | 非对称 |

**对称关系处理规则**：`CONFLICTS_WITH` 和 `CORROBORATES` 在存储时只保存一条记录（source_id < target_id 的字典序），查询时双向匹配。

### 3.4 关系置信度计算规则

关系置信度与 L3 知识置信度模型一致，但增加了关系特有的维度：

#### 3.4.1 初始置信度

| 证据来源 | 初始置信度 | 说明 |
|---------|-----------|------|
| L2 Evidence（强证据：代码分析、文档引用） | 0.7 | 有明确代码/文档支撑 |
| L2 Evidence（弱证据：LLM 推断） | 0.4 | 仅有推理结论，无直接代码/文档支撑 |
| 人工声明 | 0.9 | 用户显式确认 |
| 系统推断（inferred://） | 0.3 | cognitive-rt 自动推断，未经人工确认 |

#### 3.4.2 置信度提升

| 条件 | 提升幅度 | 上限 |
|------|---------|------|
| 被不同 Session 的 Evidence 再次支撑 | +0.1 / 次 | 0.9 |
| 人工确认（human_verified） | 直接提升至 0.95 | 0.95 |
| 被其他关系佐证（CORROBORATES 关系指向同一结论） | +0.05 / 条佐证 | 0.85 |

#### 3.4.3 置信度衰减

| 条件 | 衰减规则 | 下限 |
|------|---------|------|
| 超过 60 天未被任何 Session 引用或验证 | 每周衰减 0.05 | 0.1 |
| 关系涉及的任一节点被标记为 `deprecated` | 直接降至 0.1 | 0.1 |
| 关系涉及的任一节点被标记为 `superseded` | 直接降至 0.05 | 0.05 |

#### 3.4.4 置信度计算公式

```python
def calculate_relation_confidence(
    base_confidence: float,
    verification_count: int,
    human_verified: bool,
    corroboration_count: int,
    days_since_last_verification: int,
    node_freshness: FreshnessStatus,
) -> float:
    confidence = base_confidence

    # 验证次数加成
    confidence += min(verification_count * 0.1, 0.9 - confidence)

    # 人工确认加成
    if human_verified:
        confidence = 0.95

    # 佐证加成
    confidence += min(corroboration_count * 0.05, 0.85 - confidence)

    # 时间衰减
    if days_since_last_verification > 60:
        decay_weeks = (days_since_last_verification - 60) // 7
        confidence -= decay_weeks * 0.05

    # 节点新鲜度惩罚
    if node_freshness == FreshnessStatus.DEPRECATED:
        confidence = 0.1
    elif node_freshness == FreshnessStatus.SUPERSEDED:
        confidence = 0.05

    return max(0.05, min(0.95, confidence))
```

---

## 四、知识节点类型系统

### 4.1 KnowledgeNodeType 枚举

| 节点类型 | 对应 L3-A 知识表 | 核心属性 | 说明 |
|---------|----------------|---------|------|
| `module` | `module_profiles` | module_name, responsibility, dependencies | 代码模块画像 |
| `risk` | `risks` | canonical_risk_id, severity, status | 风险条目 |
| `decision` | `decisions` | decision_id, context, conclusion | 设计决策记录 |
| `requirement` | `requirement_lineage` | requirement_id, version, content | 需求条目 |
| `constraint` | `constraints` | constraint_hash, rule, scope | 架构约束 |
| `incident` | `incidents` | incident_id, root_cause, impact | 事故记忆 |
| `glossary` | `glossary` | canonical_name, definition, aliases | 术语表条目 |

### 4.2 节点类型与关系类型的合法组合矩阵

下表定义了每种源节点类型可以发出的关系类型，以及对应的目标节点类型约束：

| 源类型 \ 关系类型 | DEPENDS_ON | IMPACTS | CONFLICTS_WITH | EVOLVES_FROM | MITIGATES | VIOLATES | DERIVED_FROM | CORROBORATES | SUPERSEDES |
|---|---|---|---|---|---|---|---|---|---|
| `module` | module | - | - | - | - | - | - | module | - |
| `risk` | - | module, requirement | risk | risk | - | - | - | risk | risk |
| `decision` | - | requirement, module | - | - | risk | - | decision | decision | decision |
| `requirement` | requirement | - | requirement, constraint | - | - | constraint | requirement | requirement | requirement |
| `constraint` | - | - | requirement | - | risk | - | - | constraint | constraint |
| `incident` | - | module | - | - | - | constraint | - | incident | - |
| `glossary` | - | - | - | - | - | - | - | glossary | - |

**矩阵解读规则**：

- 行 = 源节点类型，列 = 关系类型
- 单元格值 = 允许的目标节点类型（`-` 表示不允许该组合）
- `CONFLICTS_WITH` 和 `CORROBORATES` 为对称关系，只需检查一侧

#### 4.2.1 关键约束说明

| 约束 | 说明 |
|------|------|
| `constraint` 只能被 `VIOLATES`，不能发出 `VIOLATES` | 约束是被遵守或被违反的规则，不会主动违反其他实体 |
| `module` 只能 `DEPENDS_ON` 其他 `module` | 模块依赖关系仅存在于模块之间 |
| `incident` 不能 `SUPERSEDES` | 事故是历史事实，不存在版本替代 |
| `glossary` 只能 `CORROBORATES` 其他 `glossary` | 术语间只存在互相佐证关系 |
| `risk` 的 `IMPACTS` 目标只能是 `module` 或 `requirement` | 风险的影响对象是模块或需求 |
| `EVOLVES_FROM` 仅限同类型节点之间 | 演化关系要求源和目标类型相同 |

### 4.3 合法性校验接口

```python
class RelationValidator:
    ALLOWED_COMBINATIONS: dict[tuple[KnowledgeNodeType, RelationType], list[KnowledgeNodeType]] = {
        (KnowledgeNodeType.MODULE, RelationType.DEPENDS_ON): [KnowledgeNodeType.MODULE],
        (KnowledgeNodeType.MODULE, RelationType.CORROBORATES): [KnowledgeNodeType.MODULE],
        (KnowledgeNodeType.RISK, RelationType.IMPACTS): [KnowledgeNodeType.MODULE, KnowledgeNodeType.REQUIREMENT],
        (KnowledgeNodeType.RISK, RelationType.CONFLICTS_WITH): [KnowledgeNodeType.RISK],
        (KnowledgeNodeType.RISK, RelationType.EVOLVES_FROM): [KnowledgeNodeType.RISK],
        (KnowledgeNodeType.RISK, RelationType.CORROBORATES): [KnowledgeNodeType.RISK],
        (KnowledgeNodeType.RISK, RelationType.SUPERSEDES): [KnowledgeNodeType.RISK],
        (KnowledgeNodeType.DECISION, RelationType.IMPACTS): [KnowledgeNodeType.REQUIREMENT, KnowledgeNodeType.MODULE],
        (KnowledgeNodeType.DECISION, RelationType.MITIGATES): [KnowledgeNodeType.RISK],
        (KnowledgeNodeType.DECISION, RelationType.DERIVED_FROM): [KnowledgeNodeType.DECISION],
        (KnowledgeNodeType.DECISION, RelationType.CORROBORATES): [KnowledgeNodeType.DECISION],
        (KnowledgeNodeType.DECISION, RelationType.SUPERSEDES): [KnowledgeNodeType.DECISION],
        (KnowledgeNodeType.REQUIREMENT, RelationType.DEPENDS_ON): [KnowledgeNodeType.REQUIREMENT],
        (KnowledgeNodeType.REQUIREMENT, RelationType.CONFLICTS_WITH): [KnowledgeNodeType.REQUIREMENT, KnowledgeNodeType.CONSTRAINT],
        (KnowledgeNodeType.REQUIREMENT, RelationType.VIOLATES): [KnowledgeNodeType.CONSTRAINT],
        (KnowledgeNodeType.REQUIREMENT, RelationType.DERIVED_FROM): [KnowledgeNodeType.REQUIREMENT],
        (KnowledgeNodeType.REQUIREMENT, RelationType.CORROBORATES): [KnowledgeNodeType.REQUIREMENT],
        (KnowledgeNodeType.REQUIREMENT, RelationType.SUPERSEDES): [KnowledgeNodeType.REQUIREMENT],
        (KnowledgeNodeType.CONSTRAINT, RelationType.CONFLICTS_WITH): [KnowledgeNodeType.REQUIREMENT],
        (KnowledgeNodeType.CONSTRAINT, RelationType.MITIGATES): [KnowledgeNodeType.RISK],
        (KnowledgeNodeType.CONSTRAINT, RelationType.CORROBORATES): [KnowledgeNodeType.CONSTRAINT],
        (KnowledgeNodeType.CONSTRAINT, RelationType.SUPERSEDES): [KnowledgeNodeType.CONSTRAINT],
        (KnowledgeNodeType.INCIDENT, RelationType.IMPACTS): [KnowledgeNodeType.MODULE],
        (KnowledgeNodeType.INCIDENT, RelationType.VIOLATES): [KnowledgeNodeType.CONSTRAINT],
        (KnowledgeNodeType.INCIDENT, RelationType.CORROBORATES): [KnowledgeNodeType.INCIDENT],
        (KnowledgeNodeType.GLOSSARY, RelationType.CORROBORATES): [KnowledgeNodeType.GLOSSARY],
    }

    def validate(
        self,
        source_type: KnowledgeNodeType,
        relation_type: RelationType,
        target_type: KnowledgeNodeType,
    ) -> bool:
        allowed = self.ALLOWED_COMBINATIONS.get((source_type, relation_type))
        if allowed is None:
            return False
        return target_type in allowed
```

---

## 五、存储设计

### 5.1 PostgreSQL `knowledge_relations` 表结构

```sql
CREATE TABLE knowledge_relations (
    relation_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID        NOT NULL,
    source_type       VARCHAR(20) NOT NULL,
    source_id         UUID        NOT NULL,
    relation_type     VARCHAR(20) NOT NULL,
    target_type       VARCHAR(20) NOT NULL,
    target_id         UUID        NOT NULL,
    confidence        FLOAT       NOT NULL DEFAULT 0.3
                        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence_ref      VARCHAR(255) NOT NULL,
    freshness         VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (freshness IN ('active', 'historical', 'superseded', 'deprecated', 'stale')),
    description       VARCHAR(500),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by        VARCHAR(100) NOT NULL,
    superseded_by     UUID        REFERENCES knowledge_relations(relation_id),

    -- 对称关系去重约束：CONFLICTS_WITH 和 CORROBORATES 只存一条
    -- 通过应用层保证 source_id < target_id（字典序）
    CONSTRAINT uq_relation_directed
        UNIQUE (project_id, source_type, source_id, relation_type, target_type, target_id),

    -- 对称关系反向去重约束
    CONSTRAINT uq_relation_symmetric
        EXCLUDE (
            project_id WITH =,
            LEAST(source_id::text, target_id::text) WITH =,
            GREATEST(source_id::text, target_id::text) WITH =,
            relation_type WITH =
        ) WHERE (relation_type IN ('CONFLICTS_WITH', 'CORROBORATES')),

    -- 合法 source_type 值
    CONSTRAINT chk_source_type
        CHECK (source_type IN ('module', 'risk', 'decision', 'requirement', 'constraint', 'incident', 'glossary')),

    -- 合法 target_type 值
    CONSTRAINT chk_target_type
        CHECK (target_type IN ('module', 'risk', 'decision', 'requirement', 'constraint', 'incident', 'glossary')),

    -- 合法 relation_type 值
    CONSTRAINT chk_relation_type
        CHECK (relation_type IN (
            'DEPENDS_ON', 'IMPACTS', 'CONFLICTS_WITH', 'EVOLVES_FROM',
            'MITIGATES', 'VIOLATES', 'DERIVED_FROM', 'CORROBORATES', 'SUPERSEDES'
        )),

    -- 自引用约束：源和目标不能是同一节点
    CONSTRAINT chk_no_self_reference
        CHECK (NOT (source_type = target_type AND source_id = target_id)),

    -- 外键引用项目表
    CONSTRAINT fk_project
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- 行级安全策略（按项目隔离）
ALTER TABLE knowledge_relations ENABLE ROW LEVEL SECURITY;
CREATE POLICY knowledge_relations_project_isolation ON knowledge_relations
    USING (project_id = current_setting('app.current_project_id')::UUID);
```

### 5.2 索引策略

```sql
-- 查询某节点的所有出边（最常用：邻居查询）
CREATE INDEX idx_kr_source ON knowledge_relations (source_type, source_id);

-- 查询某节点的所有入边（反向邻居查询）
CREATE INDEX idx_kr_target ON knowledge_relations (target_type, target_id);

-- 按关系类型过滤
CREATE INDEX idx_kr_relation_type ON knowledge_relations (relation_type);

-- 按置信度过滤（Context Pipeline 注入时过滤低置信度关系）
CREATE INDEX idx_kr_confidence ON knowledge_relations (confidence)
    WHERE confidence >= 0.6;

-- 按新鲜度过滤（Context Pipeline 只注入 active 关系）
CREATE INDEX idx_kr_freshness ON knowledge_relations (freshness)
    WHERE freshness = 'active';

-- 按项目 + 关系类型组合查询（影响分析场景）
CREATE INDEX idx_kr_project_type ON knowledge_relations (project_id, relation_type);

-- 按证据引用查询（从 Evidence 反查关系）
CREATE INDEX idx_kr_evidence ON knowledge_relations (evidence_ref);

-- 按创建者查询（审计场景）
CREATE INDEX idx_kr_created_by ON knowledge_relations (created_by);

-- 覆盖索引：Context Pipeline 注入时的典型查询
-- 查询某项目的所有 active 且高置信度关系的出边
CREATE INDEX idx_kr_inject_cover ON knowledge_relations (
    project_id, source_type, source_id, relation_type, target_type, target_id, confidence
) WHERE freshness = 'active' AND confidence >= 0.6;
```

### 5.3 查询模式分析

| 查询模式 | 频率 | 典型 SQL | 使用场景 |
|---------|------|---------|---------|
| 出边查询 | 极高 | `SELECT * FROM knowledge_relations WHERE source_type=? AND source_id=?` | Context Pipeline 注入、邻居查询 |
| 入边查询 | 高 | `SELECT * FROM knowledge_relations WHERE target_type=? AND target_id=?` | 反向影响分析 |
| 项目关系图 | 中 | `SELECT * FROM knowledge_relations WHERE project_id=?` | 前端知识图谱可视化 |
| 影响链路 | 中 | 递归 CTE：从某节点出发沿 IMPACTS/DEPENDS_ON 遍历 | 影响分析 |
| 冲突检测 | 低 | `SELECT * FROM knowledge_relations WHERE relation_type='CONFLICTS_WITH' AND project_id=?` | 关系冲突检测 |
| 证据溯源 | 低 | `SELECT * FROM knowledge_relations WHERE evidence_ref=?` | 从 Evidence 反查关系 |
| 置信度衰减批量更新 | 定时 | `UPDATE ... SET confidence=..., freshness='stale' WHERE ...` | 知识治理定时任务 |

#### 5.3.1 影响链路查询（递归 CTE）

```sql
-- 从指定风险节点出发，沿 IMPACTS 和 DEPENDS_ON 关系遍历影响链路
WITH RECURSIVE impact_chain AS (
    -- 起始节点
    SELECT
        relation_id, source_type, source_id, target_type, target_id,
        relation_type, confidence, 1 AS depth
    FROM knowledge_relations
    WHERE source_type = 'risk'
      AND source_id = :risk_id
      AND relation_type IN ('IMPACTS', 'DEPENDS_ON')
      AND freshness = 'active'
      AND confidence >= 0.6

    UNION ALL

    -- 递归扩展
    SELECT
        kr.relation_id, kr.source_type, kr.source_id,
        kr.target_type, kr.target_id, kr.relation_type,
        kr.confidence, ic.depth + 1
    FROM knowledge_relations kr
    JOIN impact_chain ic ON kr.source_type = ic.target_type
                         AND kr.source_id = ic.target_id
    WHERE kr.relation_type IN ('IMPACTS', 'DEPENDS_ON')
      AND kr.freshness = 'active'
      AND kr.confidence >= 0.6
      AND ic.depth < :max_depth
)
SELECT * FROM impact_chain ORDER BY depth, confidence DESC;
```

**递归深度限制**：

递归 CTE 查询必须设置最大递归深度，防止深度过大时性能急剧下降：

```sql
-- 限制最大递归深度为 8 跳
WITH RECURSIVE graph_traverse AS (
    SELECT *, 1 AS depth
    FROM knowledge_relations
    WHERE source_type = 'module' AND source_id = 'payment'

    UNION ALL

    SELECT kr.*, gt.depth + 1
    FROM knowledge_relations kr
    JOIN graph_traverse gt ON kr.source_type = gt.target_type AND kr.source_id = gt.target_id
    WHERE gt.depth < 8
)
SELECT * FROM graph_traverse;
```

| 深度 | 预估延迟 | 适用场景 |
|------|---------|---------|
| 1-3 跳 | < 50ms | 直接依赖、影响分析（最常用） |
| 4-6 跳 | < 500ms | 跨模块影响传播分析 |
| 7-8 跳 | < 2s | 全局架构约束检测（低频） |
| > 8 跳 | 不支持 | 需切换到图数据库（ADR-015） |

**物化路径优化（Phase 2 预留）**：

对于高频查询的路径模式（如"某模块的所有下游依赖"），可在 `knowledge_relations` 表增加 `materialized_path` 字段：

```sql
ALTER TABLE knowledge_relations
ADD COLUMN materialized_path text;

-- 示例：payment → order → user 的路径存储为 ".payment.order.user"
-- 查询 payment 的所有下游：WHERE materialized_path LIKE '.payment.%'
```

Phase 1 不实现物化路径，仅预留字段。当递归 CTE 的 P99 延迟超过 2s 时，启动物化路径优化。

---

## 六、Graph 查询接口

### 6.1 Phase 1：PG 关联表查询接口

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RelationQuery:
    project_id: str
    source_type: KnowledgeNodeType | None = None
    source_id: str | None = None
    target_type: KnowledgeNodeType | None = None
    target_id: str | None = None
    relation_types: list[RelationType] | None = None
    min_confidence: float = 0.0
    freshness_filter: list[FreshnessStatus] | None = None
    max_depth: int = 1
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class SubGraph:
    nodes: list[KnowledgeNode]
    relations: list[KnowledgeRelation]


class GraphQueryProtocol(ABC):
    """Graph 查询抽象层，Phase 1 由 PG 实现，未来可切换到图数据库"""

    @abstractmethod
    async def get_neighbors(
        self,
        query: RelationQuery,
    ) -> list[KnowledgeRelation]:
        """查询某节点的直接邻居关系"""
        ...

    @abstractmethod
    async def get_path(
        self,
        project_id: str,
        source_type: KnowledgeNodeType,
        source_id: str,
        target_type: KnowledgeNodeType,
        target_id: str,
        relation_types: list[RelationType] | None = None,
        max_depth: int = 5,
        min_confidence: float = 0.6,
    ) -> list[list[KnowledgeRelation]]:
        """查询两个节点之间的路径（返回所有路径）"""
        ...

    @abstractmethod
    async def get_subgraph(
        self,
        project_id: str,
        center_type: KnowledgeNodeType,
        center_id: str,
        max_depth: int = 2,
        min_confidence: float = 0.6,
        relation_types: list[RelationType] | None = None,
    ) -> SubGraph:
        """提取以某节点为中心的子图"""
        ...

    @abstractmethod
    async def impact_analysis(
        self,
        project_id: str,
        source_type: KnowledgeNodeType,
        source_id: str,
        max_depth: int = 3,
        min_confidence: float = 0.6,
    ) -> SubGraph:
        """影响分析：沿 IMPACTS/DEPENDS_ON 方向遍历"""
        ...

    @abstractmethod
    async def create_relation(
        self,
        relation: KnowledgeRelation,
    ) -> KnowledgeRelation:
        """创建关系（含合法性校验和冲突检测）"""
        ...

    @abstractmethod
    async def deprecate_relation(
        self,
        relation_id: str,
        reason: str,
    ) -> KnowledgeRelation:
        """废弃关系（标记 freshness=deprecated）"""
        ...

    @abstractmethod
    async def supersede_relation(
        self,
        old_relation_id: str,
        new_relation: KnowledgeRelation,
    ) -> KnowledgeRelation:
        """用新关系替代旧关系"""
        ...
```

### 6.2 Phase 1 PG 实现

```python
class PGGraphQuery(GraphQueryProtocol):
    """基于 PostgreSQL 关联表的 Graph 查询实现"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get_neighbors(self, query: RelationQuery) -> list[KnowledgeRelation]:
        async with self._session_factory() as session:
            stmt = select(KnowledgeRelationModel).where(
                KnowledgeRelationModel.project_id == query.project_id,
            )
            if query.source_type and query.source_id:
                stmt = stmt.where(
                    KnowledgeRelationModel.source_type == query.source_type,
                    KnowledgeRelationModel.source_id == query.source_id,
                )
            if query.target_type and query.target_id:
                stmt = stmt.where(
                    KnowledgeRelationModel.target_type == query.target_type,
                    KnowledgeRelationModel.target_id == query.target_id,
                )
            if query.relation_types:
                stmt = stmt.where(
                    KnowledgeRelationModel.relation_type.in_(query.relation_types),
                )
            if query.min_confidence > 0:
                stmt = stmt.where(
                    KnowledgeRelationModel.confidence >= query.min_confidence,
                )
            if query.freshness_filter:
                stmt = stmt.where(
                    KnowledgeRelationModel.freshness.in_(query.freshness_filter),
                )
            stmt = stmt.limit(query.limit).offset(query.offset)
            result = await session.execute(stmt)
            return [self._to_domain(r) for r in result.scalars().all()]

    async def get_path(
        self,
        project_id: str,
        source_type: KnowledgeNodeType,
        source_id: str,
        target_type: KnowledgeNodeType,
        target_id: str,
        relation_types: list[RelationType] | None = None,
        max_depth: int = 5,
        min_confidence: float = 0.6,
    ) -> list[list[KnowledgeRelation]]:
        async with self._session_factory() as session:
            cte_sql = self._build_path_cte(
                project_id, source_type, source_id,
                target_type, target_id,
                relation_types, max_depth, min_confidence,
            )
            result = await session.execute(text(cte_sql))
            return self._reconstruct_paths(result.fetchall())

    async def impact_analysis(
        self,
        project_id: str,
        source_type: KnowledgeNodeType,
        source_id: str,
        max_depth: int = 3,
        min_confidence: float = 0.6,
    ) -> SubGraph:
        async with self._session_factory() as session:
            cte_sql = self._build_impact_cte(
                project_id, source_type, source_id,
                max_depth, min_confidence,
            )
            result = await session.execute(text(cte_sql))
            relations = [self._to_domain_from_row(r) for r in result.fetchall()]
            nodes = self._extract_nodes(relations)
            return SubGraph(nodes=nodes, relations=relations)
```

### 6.3 常用查询模式

#### 6.3.1 邻居查询

查询某节点的所有直接关联节点。最常用的查询模式，用于 Context Pipeline 注入。

```
输入：node_type + node_id
输出：所有 relation 中 source 或 target 为该节点的关系列表
性能要求：< 10ms（索引命中）
```

#### 6.3.2 路径查询

查询两个节点之间的所有路径，用于知识溯源和影响链路分析。

```
输入：source_node + target_node + max_depth
输出：所有路径（每条路径为关系列表）
性能要求：< 100ms（depth <= 3）
限制：max_depth 默认 5，硬上限 10
```

#### 6.3.3 子图提取

提取以某节点为中心的 N 跳子图，用于前端知识图谱可视化。

```
输入：center_node + max_depth + relation_types
输出：SubGraph（nodes + relations）
性能要求：< 200ms（depth <= 2, 节点数 <= 500）
限制：子图节点数硬上限 1000，超出时截断低置信度节点
```

#### 6.3.4 影响分析

从指定节点出发，沿特定关系类型（IMPACTS、DEPENDS_ON）遍历影响链路。

```
输入：source_node + max_depth + min_confidence
输出：SubGraph（受影响的节点和关系）
性能要求：< 500ms（depth <= 3）
限制：结果节点数硬上限 2000
```

---

## 七、Graph 演化预留

### 7.1 ADR-015 详细展开

#### Context

L3 知识节点间存在复杂的多跳关系（模块依赖链、风险影响链、需求派生树），理论上图数据库（Neo4j / Age / Apache Spark GraphX）能提供更高效的关系遍历和路径查询。

#### Decision

**Phase 1 不引入图数据库，使用 PG 关联表 + 递归 CTE 实现，接口层统一使用 GraphQueryProtocol。**

#### Reasoning

| 因素 | 分析 |
|------|------|
| 数据规模 | 单项目知识节点数通常 < 10,000，关系数 < 50,000。PG 关联表在此规模下性能完全满足 |
| 运维复杂度 | 引入 Neo4j 等图数据库增加部署依赖、备份策略、监控体系，与 Phase 1 最小化部署目标冲突 |
| 查询模式 | 当前 80% 的查询是 1-2 跳邻居查询，PG 索引即可高效完成；递归 CTE 可覆盖 3-5 跳路径查询 |
| 团队熟悉度 | 团队对 SQL 和 PG 优化更熟悉，图查询语言（Cypher）学习曲线陡峭 |
| 数据一致性 | PG 关联表与 L3 知识表在同一数据库中，可利用事务保证一致性；图数据库需要双写或同步机制 |

#### Consequence

- Phase 1 的关系查询性能在 5 跳以内完全满足
- 5 跳以上的深度遍历性能可能不足，但当前无此场景
- 接口层抽象保证了未来切换的可行性

#### Tradeoff

- 优势：零额外部署成本、事务一致性、团队熟悉度高
- 劣势：深度遍历（>5 跳）性能不如原生图数据库、图算法（PageRank、社区发现）需自行实现

### 7.2 切换到图数据库时的接口不变保证

GraphQueryProtocol 是稳定接口契约。切换存储后端时：

| 保证项 | 说明 |
|--------|------|
| 接口签名不变 | `get_neighbors`、`get_path`、`get_subgraph`、`impact_analysis` 等方法签名保持不变 |
| 数据模型不变 | `KnowledgeRelation`、`KnowledgeNode`、`SubGraph` 等 Pydantic 模型保持不变 |
| 查询语义不变 | 相同输入产生相同输出（允许性能差异） |
| 迁移脚本 | 提供从 PG 关联表到图数据库的数据迁移脚本 |
| 双写过渡 | 过渡期可同时写入 PG 和图数据库，读取从图数据库，PG 作为回退 |

切换实现只需新增一个 `GraphQueryProtocol` 的实现类（如 `Neo4jGraphQuery`），替换依赖注入即可。

### 7.3 性能边界

PG 关联表在不同规模下的性能表现：

| 规模 | 节点数 | 关系数 | 1 跳邻居 | 3 跳路径 | 5 跳路径 | 建议 |
|------|--------|--------|----------|----------|----------|------|
| 小型 | < 1,000 | < 5,000 | < 5ms | < 50ms | < 200ms | PG 足够 |
| 中型 | 1,000-10,000 | 5,000-50,000 | < 10ms | < 100ms | < 500ms | PG 足够 |
| 大型 | 10,000-100,000 | 50,000-500,000 | < 50ms | < 500ms | 2-5s | PG 可用，考虑图数据库 |
| 超大型 | > 100,000 | > 500,000 | < 100ms | 1-3s | > 10s | 建议切换图数据库 |

**切换触发条件**：

- 单项目关系数超过 100,000 条
- 3 跳路径查询 P99 超过 1 秒
- 子图提取查询 P99 超过 2 秒

满足以上任一条件时，启动图数据库切换评估。

---

## 八、关系建立规则

### 8.1 自动关系发现

从 L2 Evidence 中自动提取关系，由 index-service 在 L3 沉淀阶段执行：

```python
class RelationDiscoveryService:
    """从 L2 Evidence 中自动发现知识关系"""

    async def discover_from_evidence(
        self,
        session_id: str,
        evidence_records: list[EvidenceRecord],
    ) -> list[KnowledgeRelation]:
        discovered: list[KnowledgeRelation] = []
        for evidence in evidence_records:
            relations = await self._extract_relations(evidence)
            for rel in relations:
                if await self._validate_relation(rel):
                    discovered.append(rel)
        return discovered

    async def _extract_relations(
        self,
        evidence: EvidenceRecord,
    ) -> list[KnowledgeRelation]:
        """
        从 Evidence 中提取关系的策略：
        1. evidence.type 为 'dependency' → DEPENDS_ON 关系
        2. evidence.type 为 'risk_impact' → IMPACTS 关系
        3. evidence.type 为 'constraint_violation' → VIOLATES 关系
        4. evidence.type 为 'requirement_conflict' → CONFLICTS_WITH 关系
        5. evidence.type 为 'risk_evolution' → EVOLVES_FROM 关系
        6. evidence.type 为 'mitigation' → MITIGATES 关系
        7. evidence.type 为 'requirement_derivation' → DERIVED_FROM 关系
        """
        ...

    async def _validate_relation(
        self,
        relation: KnowledgeRelation,
    ) -> bool:
        """校验关系的合法性：类型组合、节点存在性、无重复"""
        ...
```

**自动发现的置信度规则**：

| Evidence 类型 | 初始置信度 | 说明 |
|--------------|-----------|------|
| 代码分析结果（AST 解析） | 0.7 | 强事实，代码即真相 |
| 文档引用提取 | 0.6 | 有文档支撑但可能过时 |
| LLM 推断 | 0.4 | 需要后续验证 |
| Git 历史分析 | 0.5 | 历史事实但可能已不相关 |

### 8.2 人工声明关系

用户通过 UI 或 API 显式声明关系：

```python
class HumanDeclaredRelation(BaseModel):
    project_id: str
    source_type: KnowledgeNodeType
    source_id: str
    relation_type: RelationType
    target_type: KnowledgeNodeType
    target_id: str
    description: str | None = None
```

**人工声明规则**：

| 规则 | 说明 |
|------|------|
| 置信度 | 人工声明的关系初始置信度为 0.9 |
| 证据引用 | evidence_ref 格式为 `human_declared://{user_id}/{timestamp}` |
| 合法性校验 | 仍需通过 RelationValidator 校验类型组合合法性 |
| 冲突检测 | 与已有关系冲突时提示用户确认 |
| 不可自指 | 源和目标不能是同一节点 |

### 8.3 关系冲突检测和解决

#### 8.3.1 冲突类型

| 冲突类型 | 定义 | 示例 |
|---------|------|------|
| 语义冲突 | 同一对节点间存在互斥关系 | A DEPENDS_ON B 且 A CONFLICTS_WITH B |
| 方向冲突 | 同一对节点间存在反向关系 | A IMPACTS B 且 B IMPACTS A（非对称关系） |
| 置信度冲突 | 同一对节点间存在多条相同类型关系 | 重复创建（应由唯一约束阻止） |
| 逻辑冲突 | 关系链路产生逻辑矛盾 | A DEPENDS_ON B, B DEPENDS_ON C, C DEPENDS_ON A（循环依赖） |

#### 8.3.2 冲突检测规则

```python
class ConflictDetector:
    SEMANTIC_CONFLICTS: dict[RelationType, list[RelationType]] = {
        RelationType.DEPENDS_ON: [RelationType.CONFLICTS_WITH],
        RelationType.MITIGATES: [RelationType.VIOLATES],
        RelationType.CORROBORATES: [RelationType.CONFLICTS_WITH],
    }

    async def detect_conflicts(
        self,
        new_relation: KnowledgeRelation,
    ) -> list[ConflictReport]:
        conflicts: list[ConflictReport] = []

        # 1. 语义冲突检测
        existing = await self._find_existing_relations(
            new_relation.source_type, new_relation.source_id,
            new_relation.target_type, new_relation.target_id,
        )
        for rel in existing:
            if self._is_semantic_conflict(new_relation.relation_type, rel.relation_type):
                conflicts.append(ConflictReport(
                    conflict_type="semantic",
                    existing_relation=rel,
                    new_relation=new_relation,
                    severity="warning",
                ))

        # 2. 循环依赖检测（仅 DEPENDS_ON 和 DERIVED_FROM）
        if new_relation.relation_type in (RelationType.DEPENDS_ON, RelationType.DERIVED_FROM):
            if await self._would_create_cycle(new_relation):
                conflicts.append(ConflictReport(
                    conflict_type="cyclic",
                    new_relation=new_relation,
                    severity="error",
                ))

        return conflicts
```

#### 8.3.3 冲突解决策略

| 冲突类型 | 严重度 | 解决策略 |
|---------|--------|---------|
| 语义冲突 | warning | 允许创建，但标记为 `under_review`，置信度降为 0.3 |
| 方向冲突 | warning | 允许创建（有向关系允许双向），但提示用户确认 |
| 循环依赖 | error | 拒绝创建，返回错误信息 |
| 逻辑冲突 | warning | 允许创建，但触发知识治理审核流程 |

---

## 九、错误处理

### 9.1 异常体系

认知图谱相关的异常继承自 `ReqRadarException`：

```python
class GraphException(ReqRadarException):
    """认知图谱基础异常"""

class RelationValidationException(GraphException):
    """关系合法性校验失败（类型组合不合法、自引用等）"""

class CyclicDependencyException(GraphException):
    """循环依赖检测失败"""

class RelationConflictException(GraphException):
    """关系冲突（语义冲突需人工确认）"""

class OrphanNodeException(GraphException):
    """孤儿节点检测（节点无任何关系且长期未被引用）"""

class RelationNotFoundException(GraphException):
    """关系不存在"""

class EvidenceRefInvalidException(GraphException):
    """证据引用无效（evidence_ref 指向不存在的 Evidence）"""
```

### 9.2 错误场景与处理

| 场景 | 异常类型 | HTTP 状态码 | 处理方式 |
|------|---------|------------|---------|
| 创建关系时类型组合不合法 | `RelationValidationException` | 422 | 返回合法组合矩阵提示 |
| 创建关系时检测到循环依赖 | `CyclicDependencyException` | 422 | 返回循环链路信息，拒绝创建 |
| 创建关系时存在语义冲突 | `RelationConflictException` | 409 | 返回冲突关系详情，提示用户确认 |
| 查询关系时节点不存在 | `RelationNotFoundException` | 404 | 返回标准 404 响应 |
| 证据引用无效 | `EvidenceRefInvalidException` | 422 | 返回证据引用格式要求 |
| 孤儿节点检测 | `OrphanNodeException` | - | 不阻断操作，记录到治理日志，触发审核提示 |

### 9.3 孤儿节点处理

孤儿节点是指 L3 中没有任何关系且长期（>30 天）未被任何 Session 引用的知识节点。孤儿节点不代表错误，但可能暗示知识沉淀不完整：

| 检测频率 | 每周一次（知识治理定时任务） |
|---------|--------------------------|
| 检测范围 | 所有 L3-A 知识表 |
| 判定条件 | 节点无任何 knowledge_relations 记录 + 超过 30 天未被 Session 引用 |
| 处理方式 | 记录到 `knowledge_changelog`（change_type=orphan_detected），不自动删除 |
| 前端展示 | 项目知识仪表盘中展示孤儿节点列表，提示用户补充关系 |

---

## 十、配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `graph.max_path_depth` | 5 | 路径查询最大深度，硬上限 10 |
| `graph.max_subgraph_nodes` | 1000 | 子图提取最大节点数 |
| `graph.max_impact_nodes` | 2000 | 影响分析最大节点数 |
| `graph.default_min_confidence` | 0.6 | Context Pipeline 注入的最低置信度 |
| `graph.confidence_decay_threshold_days` | 60 | 置信度开始衰减的天数阈值 |
| `graph.confidence_decay_rate` | 0.05 | 每周衰减幅度 |
| `graph.confidence_min` | 0.1 | 置信度衰减下限 |
| `graph.orphan_detection_days` | 30 | 孤儿节点检测天数阈值 |
| `graph.auto_discover_enabled` | true | 是否启用自动关系发现 |
| `graph.cycle_detection_enabled` | true | 是否启用循环依赖检测 |
| `graph.conflict_detection_enabled` | true | 是否启用语义冲突检测 |
| `graph.human_declared_confidence` | 0.9 | 人工声明关系的初始置信度 |
| `graph.inferred_confidence_cap` | 0.6 | 系统推断关系的置信度上限 |
| `graph.switch_threshold_relations` | 100000 | 触发图数据库切换评估的关系数阈值 |
| `graph.switch_threshold_path_ms` | 1000 | 触发图数据库切换评估的 3 跳路径查询 P99 延迟阈值（毫秒） |

配置参数通过 Scope x Domain 配置矩阵管理，支持 SYSTEM 和 PROJECT 两个作用域。

---

## 十一、与其他模块的关系

| 模块 | 关系说明 | 接口依赖 |
|------|---------|---------|
| **M-03 Project Cognitive State** | M-04 是 M-03 的关系管理层。M-03 定义 L3 知识节点的 Schema 和治理框架，M-04 定义节点间的关系 Schema 和查询接口 | M-04 读取 M-03 定义的 FreshnessStatus、KnowledgeNodeType；M-03 的 L3Writer 在写入知识时触发 M-04 的关系发现 |
| **M-01 Evidence Model** | M-04 的每条关系必须有 M-01 的 Evidence 支撑。evidence_ref 引用 M-01 的 evidence_id | M-04 的 `evidence_ref` 字段引用 M-01 的 Evidence ID；M-01 的 Evidence 聚合完成后触发 M-04 的自动关系发现 |
| **R-01 Session** | Session 完成后触发 L3 沉淀，沉淀过程中调用 M-04 的关系发现和创建接口 | R-01 的 Session 生命周期事件（SESSION_COMPLETED）触发 M-04 的 `discover_from_evidence` |
| **R-02 Context Pipeline** | Context Pipeline 的 Collect 阶段从 M-04 查询关联知识，注入到推理上下文 | R-02 调用 M-04 的 `get_neighbors` 和 `impact_analysis` 接口获取关联知识 |
| **I-01 服务间 API 契约** | cognitive-rt 通过 I-01 定义的接口调用 index-service 的图谱查询 | M-04 的 GraphQueryProtocol 实现部署在 index-service |
| **I-03 数据库迁移计划** | M-04 的 `knowledge_relations` 表结构纳入 I-03 的迁移计划 | I-03 负责 `knowledge_relations` 表的创建和索引管理 |

### 依赖方向

```
M-01 Evidence ──────→ M-04 Cognitive Graph（evidence_ref 引用）
M-03 Cognitive State ← M-04 Cognitive Graph（关系查询服务）
R-01 Session ────────→ M-04 Cognitive Graph（触发关系发现）
R-02 Context Pipeline ← M-04 Cognitive Graph（知识注入查询）
```

---

## 十二、测试策略

### 12.1 单元测试

| 测试类别 | 覆盖范围 | 优先级 |
|---------|---------|--------|
| RelationValidator | 所有合法/非法类型组合、边界条件 | P0 |
| 置信度计算 | 初始值、提升、衰减、公式正确性 | P0 |
| ConflictDetector | 语义冲突、循环依赖、方向冲突 | P0 |
| 对称关系处理 | CONFLICTS_WITH/CORROBORATES 去重 | P1 |
| 关系建立规则 | 自动发现、人工声明、证据引用校验 | P1 |

### 12.2 集成测试

| 测试类别 | 覆盖范围 | 优先级 |
|---------|---------|--------|
| PGGraphQuery.get_neighbors | 出边/入边/双向邻居查询 | P0 |
| PGGraphQuery.get_path | 1-5 跳路径查询、无路径场景 | P0 |
| PGGraphQuery.get_subgraph | 子图提取、节点数截断 | P1 |
| PGGraphQuery.impact_analysis | 影响链路遍历、深度限制 | P1 |
| 关系创建全流程 | 合法性校验 → 冲突检测 → 持久化 → 查询验证 | P0 |
| 关系废弃/替代 | freshness 状态流转、superseded_by 引用 | P1 |

### 12.3 性能测试

| 测试场景 | 数据规模 | 性能基线 |
|---------|---------|---------|
| 1 跳邻居查询 | 10,000 节点 / 50,000 关系 | P99 < 10ms |
| 3 跳路径查询 | 10,000 节点 / 50,000 关系 | P99 < 100ms |
| 子图提取（2 跳） | 10,000 节点 / 50,000 关系 | P99 < 200ms |
| 影响分析（3 跳） | 10,000 节点 / 50,000 关系 | P99 < 500ms |
| 批量关系创建 | 1,000 条关系 | < 5s |

### 12.4 测试数据隔离

- 每个测试函数使用独立 SQLite 或独立事务
- 关系数据使用 `tmp_path` 或测试专用临时目录
- L3 知识节点使用测试工厂创建，不依赖真实项目数据
- Evidence 引用使用 mock 或测试专用 Evidence 记录

---

## 十三、明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| 引入图数据库 | Phase 1 不做 | ADR-015：PG 关联表在当前规模下足够；接口层预留切换能力 |
| 图算法（PageRank、社区发现等） | Phase 1 不做 | 当前无业务场景需要；预留接口，Phase 3 按需实现 |
| 跨项目关系 | Phase 1 不做 | 关系严格按 project_id 隔离；跨项目认知共享是 Phase 3+ 能力 |
| 关系权重（除置信度外的权重维度） | Phase 1 不做 | 置信度已覆盖主要权重需求；额外权重维度待业务场景验证 |
| 关系版本历史 | Phase 1 不做 | 关系变更通过 superseded_by 追踪，不需要完整版本链 |
| 自动关系修复 | Phase 1 不做 | 关系冲突仅检测和提示，不自动修复；自动修复风险过高 |
| 实时关系推送 | Phase 1 不做 | 关系变更通过知识治理定时任务处理，不需要实时推送 |
| L3-B 模式层的关系 | Phase 1 不做 | L3-B 模式层本身 Phase 1 不实现 |
| 关系的自然语言描述自动生成 | Phase 1 不做 | description 字段为可选项，人工声明时手动填写 |
| 多关系并发写入锁优化 | Phase 1 不做 | 当前写入频率低，PG 行级锁足够 |

---

## 附录 A：RelationType 与 KnowledgeNodeType 合法组合速查表

以下为完整合法组合，格式为 `(source_type, relation_type) → [allowed_target_types]`：

```
(module, DEPENDS_ON)       → [module]
(module, CORROBORATES)     → [module]
(risk, IMPACTS)            → [module, requirement]
(risk, CONFLICTS_WITH)     → [risk]
(risk, EVOLVES_FROM)       → [risk]
(risk, CORROBORATES)       → [risk]
(risk, SUPERSEDES)         → [risk]
(decision, IMPACTS)        → [requirement, module]
(decision, MITIGATES)      → [risk]
(decision, DERIVED_FROM)   → [decision]
(decision, CORROBORATES)   → [decision]
(decision, SUPERSEDES)     → [decision]
(requirement, DEPENDS_ON)  → [requirement]
(requirement, CONFLICTS_WITH) → [requirement, constraint]
(requirement, VIOLATES)    → [constraint]
(requirement, DERIVED_FROM) → [requirement]
(requirement, CORROBORATES) → [requirement]
(requirement, SUPERSEDES)  → [requirement]
(constraint, CONFLICTS_WITH) → [requirement]
(constraint, MITIGATES)    → [risk]
(constraint, CORROBORATES) → [constraint]
(constraint, SUPERSEDES)   → [constraint]
(incident, IMPACTS)        → [module]
(incident, VIOLATES)       → [constraint]
(incident, CORROBORATES)   → [incident]
(glossary, CORROBORATES)   → [glossary]
```

## 附录 B：状态流转图

### B.1 关系新鲜度状态流转

```
                    ┌──────────┐
                    │  active  │  创建时默认状态
                    └────┬─────┘
                         │
            ┌────────────┼────────────┐
            │            │            │
            ▼            ▼            ▼
    ┌──────────┐  ┌───────────┐  ┌───────────┐
    │historical│  │ superseded│  │   stale   │
    │(长期未引用)│  │(被新关系替代)│  │(长期未验证)│
    └──────────┘  └───────────┘  └─────┬─────┘
                                       │
                                       ▼
                                ┌───────────┐
                                │ deprecated│
                                │(已废弃)    │
                                └───────────┘
```

**状态转换规则**：

| 从 | 到 | 触发条件 |
|----|-----|---------|
| active | historical | 超过 90 天未被 Session 引用 |
| active | superseded | 被新关系替代（superseded_by 非空） |
| active | stale | 超过 90 天未被验证且置信度 < 0.3 |
| historical | stale | 超过 180 天未被引用 |
| stale | deprecated | 人工确认废弃 |
| stale | active | 被新 Session 的 Evidence 再次验证 |

### B.2 关系创建流程

```
创建请求
    │
    ▼
合法性校验（RelationValidator）
    │
    ├─ 不合法 → 返回 RelationValidationException
    │
    ▼ 合法
证据引用校验（evidence_ref 有效性）
    │
    ├─ 无效 → 返回 EvidenceRefInvalidException
    │
    ▼ 有效
冲突检测（ConflictDetector）
    │
    ├─ 循环依赖 → 返回 CyclicDependencyException
    │
    ├─ 语义冲突 → 标记 under_review，置信度降为 0.3
    │
    ▼ 无严重冲突
对称关系去重（CONFLICTS_WITH / CORROBORATES）
    │
    ├─ 已存在 → 返回已有关系
    │
    ▼ 不存在
持久化到 knowledge_relations 表
    │
    ▼
记录到 knowledge_changelog
    │
    ▼
返回 KnowledgeRelation
```
