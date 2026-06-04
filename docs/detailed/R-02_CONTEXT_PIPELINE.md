# R-02 Context Pipeline（上下文管线）详细设计

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | Context Pipeline 五阶段流水线的详细设计规格，为 P1.6（Context Pipeline 实现）提供精确蓝图 |
| 前置文档 | 01_RESTRUCTURE_OVERVIEW.md（6.1 Context Pipeline）、02_SYSTEM_ARCHITECTURE.md（4.2 Context Pipeline）、03_COGNITIVE_ASSET_MODEL.md（6.7 场景一：知识注入、ContextKind 权重叠加规则）、04_IMPLEMENTATION_ROADMAP.md（P1.6 五阶段流水线、P1.6a ContextKind 枚举、P1.6a.5 Quality Gate、P1.6b Score 阶段权重叠加） |
| 核心目标 | 将"拼凑 Prompt"升级为"工程化的上下文管理"，实现 Token 预算感知的上下文工程 |
| 文档职责 | What & How — Pipeline 是什么、五阶段如何执行、Token 预算如何管控、权重如何叠加、Quality Gate 如何判定、策略如何切换 |

---

## 2. 概述

### 2.1 Context Pipeline 在 V2 中的定位

V1 的 Prompt 构建方式是 f-string 拼接——将 project_memory、user_memory、代码片段、需求文本等按固定模板拼入 Prompt。这种方式存在三个根本问题：

1. **无预算感知**：拼接结果可能远超模型上下文窗口，导致截断丢失关键信息
2. **无质量评估**：所有上下文片段被平等对待，低价值噪音和高价值信号混杂
3. **无策略适配**：不同推理阶段（风险分析 vs 架构理解）需要不同的上下文组合，但 f-string 无法动态调整

Context Pipeline 的本质是**将"拼凑 Prompt"升级为"工程化的上下文管理"**，通过五阶段流水线实现：

- **Token Budget Awareness**：任何步骤不超上限，保留高价值上下文
- **Dynamic Attention Allocation**：根据当前推理阶段使用不同 Context Strategy
- **Stage-aware Context Scheduling**：不同步骤注入不同上下文源组合

### 2.2 V1 → V2 的核心升级

| 维度 | V1 | V2 |
|------|----|----|
| Prompt 构建 | f-string 拼接 | 五阶段流水线：Collect → Score → Select → Compress → Assemble |
| Token 管理 | 无预算感知，截断兜底 | 严格 Token Budget 约束，输出 token_count ≤ context_budget |
| 上下文评分 | 无评分，所有片段平等 | 综合评分：语义相似度 + 时间衰减 + 用户标记 + ContextKind 权重 |
| 上下文选择 | 全量拼入或硬编码截断 | 贪心选择 + 最低质量阈值 + 多样性保证 |
| 上下文压缩 | 无压缩 | 摘要生成 / 关键词提取 / 结构化转换 / 截断 |
| 策略适配 | 无策略 | Context Strategy 模式，按推理阶段切换 |
| 质量保障 | 无 | Quality Gate 检查，不满足时进入 LOW_CONTEXT_CONFIDENCE 模式 |
| 数据源 | 硬编码 memory 查询 | ContextSource 抽象接口，可插拔适配器 |

---

## 3. 核心概念

### 3.1 五阶段流水线总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Context Pipeline                                  │
│                                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  │ Collect  │──▶│  Score   │──▶│  Select  │──▶│ Compress │──▶│ Assemble │
│  │          │   │          │   │          │   │          │   │          │
│  │ 多源收集  │   │ 综合评分  │   │ 预算选择  │   │ 压缩优化  │   │ 格式组装  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
│       ▲              ▲              ▲              ▲              │
│       │              │              │              │              │
│  ContextSource   ScoreConfig   Token Budget   CompressConfig  AssembleConfig
│  适配器集合       权重参数       约束条件        压缩策略         格式规则
│                                                                          │
│  ┌──────────────┐                                                       │
│  │ Quality Gate │  Collect 后、Score 前执行质量检查                       │
│  │              │  不满足 → LOW_CONTEXT_CONFIDENCE 模式                  │
│  └──────────────┘                                                       │
│                                                                          │
│  ┌──────────────┐                                                       │
│  │   Context    │  按推理阶段选择策略                                     │
│  │   Strategy   │  RiskAnalysis / ArchitectureUnderstanding / EvidenceAggregation │
│  └──────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

| 阶段 | 输入 | 输出 | 核心职责 |
|------|------|------|---------|
| Collect | ContextSource 适配器集合 | `list[ContextItem]` | 从多个数据源收集所有潜在上下文片段 |
| Quality Gate | `list[ContextItem]` | QualityGateResult | 检查上下文质量是否满足最低标准 |
| Score | `list[ContextItem]` + ScoreConfig | `list[ScoredContextItem]` | 为每个片段计算综合相关性评分 |
| Select | `list[ScoredContextItem]` + Token Budget | `list[ScoredContextItem]` | 在 Token 预算约束下选择最优子集 |
| Compress | `list[ScoredContextItem]` + CompressConfig | `list[CompressedContextItem]` | 压缩选中片段以适应预算 |
| Assemble | `list[CompressedContextItem]` + AssembleConfig | `str`（最终上下文） | 按优先级排序、添加元数据、格式标准化 |

### 3.2 Token Budget 机制

Token Budget 是 Context Pipeline 的硬约束。Pipeline 的输出必须严格满足：

```
token_count(assembled_context) ≤ context_budget
```

Token Budget 的来源：

| 来源 | 优先级 | 说明 |
|------|--------|------|
| 请求体 `config.context_budget` | 最高 | 创建 Session 时显式指定 |
| SESSION scope 配置 | 次高 | Scope × Domain 配置矩阵 |
| USER scope 配置 | 中 | 用户级偏好 |
| PROJECT scope 配置 | 较低 | 项目级默认 |
| SYSTEM scope 配置 | 最低 | 系统级默认（128000） |

**预算分配策略**：context_budget 不是全部用于当前推理步骤，而是按比例分配给四个分区：

| 分区 | 默认占比 | 说明 |
|------|---------|------|
| 系统提示 | 15% | 分析框架、维度定义、输出格式要求 |
| 历史上下文 | 25% | 前序推理步骤的 Thought/Observation 摘要 |
| 当前推理 | 45% | 当前步骤需要的上下文（Context Pipeline 的主要输出） |
| 工具输出预留 | 15% | 预留给工具调用返回的结果 |

Context Pipeline 管控的是"当前推理"分区（45%），即 Pipeline 的有效预算为：

```
effective_budget = context_budget × current_reasoning_ratio
```

### 3.3 Context Strategy 模式

不同推理阶段对上下文的需求不同。Context Strategy 定义了每个推理阶段的上下文偏好：

```
┌───────────────────────────────────────────────────────┐
│                  Context Strategy                       │
│                                                         │
│  ┌─────────────────────┐  风险分析阶段                   │
│  │ RiskAnalysisStrategy│  偏好：代码证据、Git 历史、L3 风险记忆 │
│  └─────────────────────┘                                │
│                                                         │
│  ┌──────────────────────────────┐  架构理解阶段           │
│  │ ArchitectureUnderstandingStrategy│  偏好：架构文档、代码依赖、L3 约束 │
│  └──────────────────────────────┘                       │
│                                                         │
│  ┌──────────────────────────┐  证据聚合阶段              │
│  │ EvidenceAggregationStrategy│  偏好：需求原文、代码匹配、验证结果 │
│  └──────────────────────────┘                           │
└───────────────────────────────────────────────────────┘
```

每种策略通过以下维度差异化：

- **Context 源组合偏好**：Collect 阶段激活哪些 ContextSource
- **权重配置**：Score 阶段的 w1/w2/w3/w4 参数
- **预算分配**：各 ContextKind 在 Token 预算中的占比上限
- **Quality Gate 阈值**：不同策略对质量标准的严格程度

---

## 4. ContextKind 枚举与权重体系

### 4.1 ContextKind 完整枚举定义

```python
from enum import StrEnum


class ContextKind(StrEnum):
    SOURCE_CODE = "SOURCE_CODE"
    REQUIREMENT = "REQUIREMENT"
    ARCH_DOC = "ARCH_DOC"
    GIT_HISTORY = "GIT_HISTORY"
    MEMORY = "MEMORY"
    INFERRED_KNOWLEDGE = "INFERRED_KNOWLEDGE"
```

### 4.2 基础权重定义和设计理由

| ContextKind | 基础权重 | 设计理由 |
|-------------|---------|---------|
| SOURCE_CODE | 1.0 | 强事实，代码即真相。代码结构、依赖、实现是最可靠的上下文来源 |
| REQUIREMENT | 0.95 | 高优先级，用户显式输入。需求文档是分析的目标和锚点 |
| ARCH_DOC | 0.9 | 高可信，架构文档。设计决策的权威来源，但可能过时 |
| GIT_HISTORY | 0.7 | 弱历史，需结合时间衰减。提交历史反映变更趋势，但单条 commit 信息量有限 |
| MEMORY | 0.6 | 可污染，需 confidence 兜底。L3 项目记忆有价值但存在腐化风险 |
| INFERRED_KNOWLEDGE | 0.4 | 高风险，LLM 推断产物。推理结论未经事实验证，仅作辅助参考 |

**权重设计原则**：

1. **事实优先**：可验证的事实来源（代码、需求文档）权重最高
2. **衰减递减**：间接性越强的来源权重越低（代码 > 文档 > 历史 > 记忆 > 推断）
3. **防污染**：MEMORY 和 INFERRED_KNOWLEDGE 的低权重防止认知飞轮的自我强化和自我幻觉
4. **可组合**：权重作为乘法因子，与 L3 confidence_score 叠加时不会放大噪音

### 4.3 权重叠加规则

最终权重 = ContextKind 基础权重 × L3 confidence_score（若适用）

```python
def compute_final_weight(context_kind: ContextKind, l3_confidence: float | None = None) -> float:
    base_weight = CONTEXT_KIND_WEIGHTS[context_kind]
    if l3_confidence is not None and context_kind == ContextKind.MEMORY:
        return base_weight * l3_confidence
    return base_weight
```

**叠加规则说明**：

| 场景 | 计算方式 | 示例 |
|------|---------|------|
| 非 MEMORY 类型（无 L3 confidence） | 最终权重 = 基础权重 | SOURCE_CODE → 1.0 |
| MEMORY 类型 + L3 confidence | 最终权重 = 0.6 × confidence | MEMORY + confidence=0.8 → 0.48 |
| MEMORY 类型 + 无 L3 confidence | 最终权重 = 基础权重 | MEMORY → 0.6 |
| INFERRED_KNOWLEDGE 类型 | 最终权重 = 基础权重 | INFERRED_KNOWLEDGE → 0.4 |

**为什么只有 MEMORY 类型叠加 L3 confidence**：

- SOURCE_CODE / REQUIREMENT / ARCH_DOC / GIT_HISTORY 是 L0/L1 层的事实来源，不存在 confidence 概念
- INFERRED_KNOWLEDGE 是当前推理步骤的产物，不属于 L3 沉淀知识，不适用 L3 confidence
- MEMORY 类型特指从 L3 项目记忆注入的上下文，其可信度直接由 L3 的 confidence_score 衡量

### 4.4 权重在 Score 阶段的应用方式

Score 阶段的综合评分公式中，ContextKind 最终权重作为 `w4` 维度的乘法因子：

```
综合得分 = semantic_similarity × w1
        + time_decay × w2
        + user_mark × w3
        + final_weight × w4
```

其中 `final_weight` 即为第 4.3 节计算的最终权重。详见第 6 节 Score 阶段详细设计。

---

## 5. Collect 阶段详细设计

### 5.1 ContextSource 抽象接口定义

```python
from abc import ABC, abstractmethod
from reqradar.kernel.context_types import ContextItem, ContextKind


class ContextSource(ABC):
    """上下文源抽象接口——所有数据源适配器的基类"""

    @abstractmethod
    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind,
        max_items: int = 50,
    ) -> list[ContextItem]:
        """从数据源收集上下文片段

        参数:
            session_id: 当前 Session ID
            project_id: 项目 ID
            query: 当前推理步骤的查询意图
            context_kind: 该数据源对应的上下文类型
            max_items: 最大返回条目数

        返回:
            标准化的 ContextItem 列表
        """
        ...

    @abstractmethod
    def supported_kind(self) -> ContextKind:
        """返回该数据源支持的 ContextKind"""
        ...

    @abstractmethod
    def is_available(self, project_id: str) -> bool:
        """检查该数据源对指定项目是否可用"""
        ...
```

### 5.2 V1 数据源适配器

P1 阶段通过 ContextSource 接口适配 V1 的现有数据源，保证 Pipeline 可立即运行：

#### 5.2.1 ProjectMemorySource

```python
class ProjectMemorySource(ContextSource):
    """项目记忆数据源——适配 V1 的 project_memory"""

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # 从 V1 project_memory 读取：术语表、模块画像、架构约束
        # 按 query 做关键词匹配和语义检索
        # 转换为标准 ContextItem 格式
        ...

    def supported_kind(self) -> ContextKind:
        return ContextKind.MEMORY

    def is_available(self, project_id: str) -> bool:
        # 检查项目是否有 project_memory 数据
        ...
```

| 属性 | 说明 |
|------|------|
| 数据来源 | V1 `project_memory` JSON 文件 |
| ContextKind | MEMORY |
| 收集内容 | 术语表、模块画像、架构约束、风险历史 |
| 过滤规则 | 仅注入 freshness=active 且 confidence_score >= 0.6 的知识（P5 后由 L3ContextSource 替代） |

#### 5.2.2 UserMemorySource

```python
class UserMemorySource(ContextSource):
    """用户记忆数据源——适配 V1 的 user_memory"""

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # 从 V1 user_memory 读取：用户偏好、历史分析摘要
        ...

    def supported_kind(self) -> ContextKind:
        return ContextKind.MEMORY

    def is_available(self, project_id: str) -> bool:
        # 检查用户是否有 user_memory 数据
        ...
```

| 属性 | 说明 |
|------|------|
| 数据来源 | V1 `user_memory` JSON 文件 |
| ContextKind | MEMORY |
| 收集内容 | 用户偏好、历史分析摘要、关注重点 |
| 过滤规则 | 仅注入与当前项目相关的用户记忆 |

#### 5.2.3 CodeGraphSource

```python
class CodeGraphSource(ContextSource):
    """代码图数据源——适配 V1 的 code_parser 和向量检索"""

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # 从 ChromaDB code 集合做语义检索
        # 从 PG modules 表查结构化依赖信息
        # 合并为标准 ContextItem
        ...

    def supported_kind(self) -> ContextKind:
        return ContextKind.SOURCE_CODE

    def is_available(self, project_id: str) -> bool:
        # 检查项目是否有代码索引
        ...
```

| 属性 | 说明 |
|------|------|
| 数据来源 | V1 ChromaDB code 集合 + PG modules 表 |
| ContextKind | SOURCE_CODE |
| 收集内容 | 模块定义、函数签名、依赖关系、代码片段 |
| 检索方式 | 语义检索（Embedding cosine similarity）+ 结构化查询（模块名/文件路径） |

#### 5.2.4 VectorResultSource

```python
class VectorResultSource(ContextSource):
    """向量检索数据源——适配 V1 的需求文档向量检索"""

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # 从 ChromaDB requirements 集合做语义检索
        # 按 query 检索最相关的需求文档 chunk
        ...

    def supported_kind(self) -> ContextKind:
        return ContextKind.REQUIREMENT

    def is_available(self, project_id: str) -> bool:
        # 检查项目是否有需求文档索引
        ...
```

| 属性 | 说明 |
|------|------|
| 数据来源 | V1 ChromaDB requirements 集合 |
| ContextKind | REQUIREMENT |
| 收集内容 | 需求文档 chunk、章节段落、需求-代码关联 |
| 检索方式 | 语义检索（Embedding cosine similarity） |

#### 5.2.5 GitHistorySource

```python
class GitHistorySource(ContextSource):
    """Git 历史数据源——适配 V1 的 git_analyzer"""

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # 从 PG commits 表查询最近提交
        # 按 query 过滤相关提交（关键词匹配 commit message）
        # 识别 hotfix/revert 提交作为风险信号
        ...

    def supported_kind(self) -> ContextKind:
        return ContextKind.GIT_HISTORY

    def is_available(self, project_id: str) -> bool:
        # 检查项目是否有 Git 历史
        ...
```

| 属性 | 说明 |
|------|------|
| 数据来源 | V1 PG commits 表 + git_analyzer |
| ContextKind | GIT_HISTORY |
| 收集内容 | 提交记录、变更文件、hotfix/revert 标记、贡献者信息 |
| 检索方式 | 时间范围查询 + 关键词过滤 |

### 5.3 L3ContextSource 适配器（P5 后启用）

P5 完成 L3 知识治理后，新增 L3ContextSource 替代 ProjectMemorySource 和 UserMemorySource 的部分职责：

```python
class L3ContextSource(ContextSource):
    """L3 持久化知识数据源——P5 后启用，替代 ProjectMemorySource 的 L3 注入职责"""

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # 从 L3 知识表查询：
        # 1. 模块画像（涉及模块的风险历史、架构约束）
        # 2. 术语表（涉及术语的准确定义）
        # 3. 架构约束（freshness=active 的高优先级约束）
        # 4. 决策记录（相关历史决策背景）
        # 5. 风险演化（涉及模块的风险演化轨迹）
        # 过滤条件：freshness=active AND confidence_score >= 0.6
        ...

    def supported_kind(self) -> ContextKind:
        return ContextKind.MEMORY

    def is_available(self, project_id: str) -> bool:
        # 检查项目是否有 L3 知识数据
        ...
```

**过渡策略**：

| 阶段 | MEMORY 类型数据源 | 说明 |
|------|------------------|------|
| P1 | ProjectMemorySource + UserMemorySource | 从 V1 memory JSON 读取 |
| P5 后 | L3ContextSource（主）+ UserMemorySource（辅） | L3 替代 ProjectMemorySource，通过配置切换 |
| 切换方式 | Context Pipeline 的 source_registry 配置 | 替换适配器注册，无需重构 Pipeline 代码 |

### 5.4 Collect 阶段的执行流程

```
┌────────────────────────────────────────────────────────────────┐
│                    Collect 阶段执行流程                          │
│                                                                │
│  1. ContextStrategy 确定激活的 ContextSource 列表               │
│     └── 策略定义了每种 ContextKind 的 max_items 预算            │
│                                                                │
│  2. 并行调用所有激活的 ContextSource.collect()                  │
│     ├── ProjectMemorySource.collect()  → list[ContextItem]     │
│     ├── CodeGraphSource.collect()      → list[ContextItem]     │
│     ├── VectorResultSource.collect()   → list[ContextItem]     │
│     ├── GitHistorySource.collect()     → list[ContextItem]     │
│     └── UserMemorySource.collect()     → list[ContextItem]     │
│                                                                │
│  3. 合并所有结果                                                │
│     └── 合并为统一的 list[ContextItem]                          │
│                                                                │
│  4. 去重（按 content_hash 去重）                                │
│     └── 相同内容来自不同数据源时保留来源更权威的                  │
│                                                                │
│  5. 输出 → Quality Gate 检查                                   │
└────────────────────────────────────────────────────────────────┘
```

**并行收集的容错**：单个 ContextSource 失败不阻塞整个 Collect 阶段。失败的 Source 返回空列表并记录 warning 日志，Pipeline 继续使用其他可用 Source 的结果。

### 5.5 收集结果的标准化格式（ContextItem）

```python
from datetime import datetime
from pydantic import BaseModel, Field
from reqradar.kernel.context_types import ContextKind


class ContextItem(BaseModel):
    """Collect 阶段输出的标准化上下文条目"""

    item_id: str = Field(
        description="条目唯一标识，格式：ctx-{uuid_hex[:12]}",
    )
    context_kind: ContextKind = Field(
        description="上下文类型",
    )
    source_name: str = Field(
        description="来源适配器名称，如 ProjectMemorySource",
    )
    content: str = Field(
        description="上下文内容文本",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="元数据（来源 URI、时间戳、模块名等）",
    )
    token_count: int = Field(
        default=0,
        ge=0,
        description="内容的 Token 数量",
    )
    embedding: list[float] | None = Field(
        default=None,
        description="内容的向量嵌入（用于 Score 阶段语义相似度计算）",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="内容的时间戳（用于时间衰减计算）",
    )
    user_marked: bool = Field(
        default=False,
        description="用户是否显式标记为重要",
    )
    l3_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="L3 知识的置信度（仅 MEMORY 类型适用）",
    )
    content_hash: str = Field(
        default="",
        description="内容哈希，用于去重",
    )
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `item_id` | str | 唯一标识，贯穿 Pipeline 全流程 |
| `context_kind` | ContextKind | 上下文类型，决定基础权重 |
| `source_name` | str | 来源适配器名称，用于溯源和调试 |
| `content` | str | 上下文内容文本，最终注入 LLM 的内容 |
| `metadata` | dict | 来源元数据（URI、模块名、文件路径等） |
| `token_count` | int | Token 数量，由 TokenCounter 计算 |
| `embedding` | list[float] \| None | 向量嵌入，用于 Score 阶段语义相似度 |
| `timestamp` | datetime | 时间戳，用于 Score 阶段时间衰减 |
| `user_marked` | bool | 用户显式标记，Score 阶段加分 |
| `l3_confidence` | float \| None | L3 置信度，MEMORY 类型叠加权重用 |
| `content_hash` | str | 内容哈希，Collect 阶段去重用 |

---

## 6. Score 阶段详细设计

### 6.1 评分算法

综合得分由四个维度加权求和：

```
综合得分 = semantic_similarity × w1 + time_decay × w2 + user_mark × w3 + final_weight × w4
```

| 维度 | 符号 | 范围 | 说明 |
|------|------|------|------|
| 语义相似度 | `semantic_similarity` | [0.0, 1.0] | 内容与当前推理意图的语义相关性 |
| 时间衰减 | `time_decay` | [0.0, 1.0] | 内容的新鲜程度，越新越高 |
| 用户标记 | `user_mark` | {0.0, 1.0} | 用户是否显式标记为重要 |
| ContextKind 最终权重 | `final_weight` | [0.0, 1.0] | 基于上下文类型的权威性权重 |

**默认权重配置**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| w1 | 0.4 | 语义相似度权重——最重要的维度 |
| w2 | 0.15 | 时间衰减权重——辅助维度 |
| w3 | 0.15 | 用户标记权重——人工信号 |
| w4 | 0.3 | ContextKind 权重——来源权威性 |

**综合得分范围**：[0.0, 1.0]。各维度归一化后加权求和，结果 clamp 到 [0.0, 1.0]。

### 6.2 语义相似度计算

使用 Embedding cosine similarity 衡量上下文内容与当前推理意图的语义相关性：

```python
import numpy as np


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def compute_semantic_similarity(
    item_embedding: list[float],
    query_embedding: list[float],
) -> float:
    """计算上下文条目与查询意图的语义相似度

    返回值范围 [0.0, 1.0]，cosine similarity 原始范围 [-1.0, 1.0]
    归一化：(sim + 1) / 2
    """
    raw_sim = cosine_similarity(item_embedding, query_embedding)
    return (raw_sim + 1.0) / 2.0
```

**Embedding 来源**：

| 场景 | Embedding 来源 |
|------|---------------|
| ContextItem 已有 embedding | Collect 阶段由 ContextSource 预计算 |
| ContextItem 无 embedding | Score 阶段调用 Embedding 模型实时计算 |
| query_embedding | 当前推理步骤的查询意图，由 Agent 生成后调用 Embedding 模型计算 |

**性能优化**：Collect 阶段预计算 embedding，避免 Score 阶段重复调用 Embedding 模型。仅对无 embedding 的条目实时计算。

### 6.3 时间衰减函数

时间衰减衡量上下文的新鲜程度。越新的内容越可能与当前代码状态一致：

```python
from datetime import datetime, timedelta


def compute_time_decay(
    item_timestamp: datetime,
    now: datetime,
    half_life_days: float = 30.0,
) -> float:
    """指数时间衰减函数

    参数:
        item_timestamp: 上下文条目的时间戳
        now: 当前时间
        half_life_days: 半衰期（天），默认 30 天

    返回值范围 (0.0, 1.0]
    - 刚产生的内容：1.0
    - half_life_days 天前：0.5
    - 2 × half_life_days 天前：0.25
    """
    age_days = (now - item_timestamp).total_seconds() / 86400.0
    if age_days < 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)
```

**半衰期参数**：

| ContextKind | 默认半衰期 | 说明 |
|-------------|-----------|------|
| SOURCE_CODE | 90 天 | 代码变更频率相对稳定 |
| REQUIREMENT | 180 天 | 需求文档更新频率低 |
| ARCH_DOC | 120 天 | 架构文档介于代码和需求之间 |
| GIT_HISTORY | 30 天 | Git 历史越近越相关 |
| MEMORY | 60 天 | L3 记忆需要较新的验证 |
| INFERRED_KNOWLEDGE | 7 天 | 推理结论时效性最短 |

### 6.4 ContextKind 基础权重叠加

ContextKind 最终权重直接作为 Score 公式的 w4 维度输入：

```python
def compute_final_weight(context_kind: ContextKind, l3_confidence: float | None = None) -> float:
    base_weights: dict[ContextKind, float] = {
        ContextKind.SOURCE_CODE: 1.0,
        ContextKind.REQUIREMENT: 0.95,
        ContextKind.ARCH_DOC: 0.9,
        ContextKind.GIT_HISTORY: 0.7,
        ContextKind.MEMORY: 0.6,
        ContextKind.INFERRED_KNOWLEDGE: 0.4,
    }
    weight = base_weights[context_kind]
    if l3_confidence is not None and context_kind == ContextKind.MEMORY:
        weight *= l3_confidence
    return weight
```

### 6.5 L3 confidence_score 叠加

L3 confidence_score 仅在 MEMORY 类型上下文中叠加，计算方式见 6.4 节。叠加效果示例：

| 场景 | 基础权重 | L3 confidence | 最终权重 | 对综合得分的影响 |
|------|---------|---------------|---------|----------------|
| 高置信度 L3 约束 | 0.6 | 0.9 | 0.54 | 中等偏上 |
| 低置信度 L3 记忆 | 0.6 | 0.3 | 0.18 | 显著降低 |
| 代码证据 | 1.0 | - | 1.0 | 最高 |
| 推理产物 | 0.4 | - | 0.4 | 最低 |

### 6.6 Score 阶段输出

```python
class ScoredContextItem(ContextItem):
    """Score 阶段输出——携带综合评分的上下文条目"""

    semantic_similarity: float = Field(ge=0.0, le=1.0, description="语义相似度")
    time_decay: float = Field(ge=0.0, le=1.0, description="时间衰减值")
    final_weight: float = Field(ge=0.0, le=1.0, description="ContextKind 最终权重")
    composite_score: float = Field(ge=0.0, le=1.0, description="综合得分")
```

### 6.7 权重配置参数

Score 阶段的权重参数纳入 Scope × Domain 配置矩阵，位于 RUNTIME Domain：

| 配置项 | 默认值 | 范围 | 说明 |
|--------|--------|------|------|
| `pipeline.score.w1_semantic` | 0.4 | 0.0-1.0 | 语义相似度权重 |
| `pipeline.score.w2_time_decay` | 0.15 | 0.0-1.0 | 时间衰减权重 |
| `pipeline.score.w3_user_mark` | 0.15 | 0.0-1.0 | 用户标记权重 |
| `pipeline.score.w4_context_kind` | 0.3 | 0.0-1.0 | ContextKind 权重 |
| `pipeline.score.half_life.source_code` | 90 | 1-365 | SOURCE_CODE 半衰期（天） |
| `pipeline.score.half_life.requirement` | 180 | 1-730 | REQUIREMENT 半衰期（天） |
| `pipeline.score.half_life.arch_doc` | 120 | 1-365 | ARCH_DOC 半衰期（天） |
| `pipeline.score.half_life.git_history` | 30 | 1-180 | GIT_HISTORY 半衰期（天） |
| `pipeline.score.half_life.memory` | 60 | 1-365 | MEMORY 半衰期（天） |
| `pipeline.score.half_life.inferred` | 7 | 1-90 | INFERRED_KNOWLEDGE 半衰期（天） |

**约束**：w1 + w2 + w3 + w4 = 1.0。配置校验时检查权重之和是否为 1.0。

---

## 7. Select 阶段详细设计

### 7.1 Token 预算约束下的贪心选择算法

Select 阶段在 Token 预算约束下，从评分后的上下文条目中选择最优子集：

```python
def select_context(
    items: list[ScoredContextItem],
    token_budget: int,
    min_score: float = 0.3,
    diversity_config: DiversityConfig | None = None,
) -> list[ScoredContextItem]:
    """贪心选择算法

    策略：
    1. 按综合得分降序排列
    2. 过滤低于最低质量阈值的条目
    3. 贪心填充：从最高分开始，逐条加入，直到 Token 预算用尽
    4. 多样性检查：避免同质上下文占满预算
    """
    # 步骤 1：按综合得分降序排列
    sorted_items = sorted(items, key=lambda x: x.composite_score, reverse=True)

    # 步骤 2：最低质量阈值过滤
    qualified_items = [item for item in sorted_items if item.composite_score >= min_score]

    # 步骤 3：贪心填充
    selected: list[ScoredContextItem] = []
    used_tokens = 0
    kind_counts: dict[ContextKind, int] = {}

    for item in qualified_items:
        if used_tokens + item.token_count > token_budget:
            continue

        # 步骤 4：多样性检查
        if diversity_config and not _check_diversity(item, selected, kind_counts, diversity_config):
            continue

        selected.append(item)
        used_tokens += item.token_count
        kind_counts[item.context_kind] = kind_counts.get(item.context_kind, 0) + 1

    return selected
```

### 7.2 选择策略详解

**按综合得分降序，贪心填充直到 Token 预算用尽**：

```
输入：ScoredContextItem 列表（已按 composite_score 降序排列）
预算：effective_budget tokens

┌──────────────────────────────────────────────────────────┐
│  composite_score                                          │
│  1.0 ┤  ■                                                │
│  0.9 ┤  ■  ■                                             │
│  0.8 ┤  ■  ■  ■                                          │
│  0.7 ┤  ■  ■  ■  ■  ■                                    │
│  0.6 ┤  ■  ■  ■  ■  ■  ■  ■                             │
│  0.5 ┤  ■  ■  ■  ■  ■  ■  ■  ■  ■                       │
│  0.4 ┤  ■  ■  ■  ■  ■  ■  ■  ■  ■  ■  ■                 │
│  0.3 ┤  ■  ■  ■  ■  ■  ■  ■  ■  ■  ■  ■  ■  ■  ■       │
│  0.2 ┤  ×  ×  ×  ×  （低于 min_score，过滤）             │
│  0.1 ┤  ×  ×  ×  ×  ×                                    │
│  0.0 ┤                                                    │
│      └──────────────────────────────────────────────►     │
│        选中条目（贪心填充，直到 Token 预算用尽）            │
└──────────────────────────────────────────────────────────┘
```

### 7.3 最低质量阈值过滤

低于 `min_score` 的条目直接过滤，不参与选择：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `pipeline.select.min_score` | 0.3 | 最低综合得分阈值 |
| `pipeline.select.min_score_risk_analysis` | 0.35 | 风险分析策略的最低阈值（更严格） |
| `pipeline.select.min_score_arch_understanding` | 0.25 | 架构理解策略的最低阈值（更宽松） |

**设计理由**：风险分析需要更可靠的证据，低分上下文可能引入噪音；架构理解需要更广泛的背景，允许较低分但有参考价值的上下文。

### 7.4 多样性保证

避免同质上下文占满预算，确保上下文类型的多样性：

```python
class DiversityConfig(BaseModel):
    """多样性配置"""

    max_same_kind_ratio: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="同一 ContextKind 占选中条目的最大比例",
    )
    min_kinds: int = Field(
        default=2,
        ge=1,
        le=6,
        description="选中条目中至少包含的 ContextKind 种类数",
    )
    required_kinds: list[ContextKind] = Field(
        default_factory=lambda: [ContextKind.SOURCE_CODE],
        description="必须包含的 ContextKind（如果数据源可用）",
    )


def _check_diversity(
    item: ScoredContextItem,
    selected: list[ScoredContextItem],
    kind_counts: dict[ContextKind, int],
    config: DiversityConfig,
) -> bool:
    """检查添加该条目后是否满足多样性约束"""
    total = len(selected) + 1
    new_count = kind_counts.get(item.context_kind, 0) + 1

    # 同一类型占比不超过上限
    if new_count / total > config.max_same_kind_ratio:
        return False

    return True
```

**多样性约束**：

| 约束 | 默认值 | 说明 |
|------|--------|------|
| 同一 ContextKind 最大占比 | 40% | 防止代码片段占满全部预算 |
| 最少 ContextKind 种类数 | 2 | 至少包含两种不同类型的上下文 |
| 必须包含的 ContextKind | SOURCE_CODE | 代码证据是分析的基础 |

---

## 8. Compress 阶段详细设计

### 8.1 压缩策略

Compress 阶段提供四种压缩策略，按优先级尝试：

| 策略 | 压缩比 | Token 成本 | 质量损失 | 适用场景 |
|------|--------|-----------|---------|---------|
| 结构化转换 | 高（50-70%） | 无 | 低 | 代码片段、Git 历史 |
| 关键词提取 | 中（40-60%） | 无 | 中 | 长文档 chunk |
| 摘要生成 | 高（60-80%） | 有（LLM 调用） | 中 | 需求文档、架构描述 |
| 截断 | 可控 | 无 | 高 | 最后兜底 |

#### 8.1.1 结构化转换

将冗长的自然语言描述转换为结构化格式，减少 Token 数量：

```python
def compress_structured(item: ScoredContextItem) -> CompressedContextItem:
    """结构化转换——将内容转为 YAML/JSON 结构"""

    # 代码片段 → 函数签名 + 关键注释
    # Git 历史 → commit_hash + message + changed_files 列表
    # 模块描述 → 模块名 + 职责 + 依赖列表

    ...
```

**示例**：

```
原始内容（150 tokens）：
"用户认证模块位于 src/auth/login.py，包含 authenticate_user 函数，
该函数接收 username 和 password 参数，返回认证令牌。该模块依赖
user_model 和 token_service 两个模块。"

压缩后（60 tokens）：
module: auth
file: src/auth/login.py
function: authenticate_user(username, password) -> Token
deps: [user_model, token_service]
```

#### 8.1.2 关键词提取

从长文本中提取关键词和核心语句：

```python
def compress_keywords(item: ScoredContextItem, max_tokens: int) -> CompressedContextItem:
    """关键词提取——保留核心关键词和关键句"""
    # 使用 TF-IDF 或 TextRank 提取关键词
    # 保留包含关键词的原始句子
    # 截断到 max_tokens
    ...
```

#### 8.1.3 摘要生成

调用 LLM 生成摘要，压缩比最高但需要额外 Token 成本：

```python
async def compress_summary(
    item: ScoredContextItem,
    max_tokens: int,
    llm_client: LLMClient,
) -> CompressedContextItem:
    """摘要生成——调用 LLM 压缩内容"""
    prompt = (
        f"请将以下内容压缩为不超过 {max_tokens} tokens 的摘要，"
        f"保留关键事实、数据和结论：\n\n{item.content}"
    )
    summary = await llm_client.generate(prompt, max_tokens=max_tokens)
    ...
```

**摘要生成的 Token 成本控制**：

- 摘要生成使用的 Token 计入 Session 的 `context_usage`
- 单次摘要调用的 max_tokens 上限为原始内容的 30%
- 如果摘要生成的 Token 成本超过节省的 Token，则跳过摘要，改用截断

**Compress 阶段的 Token 消耗归属**：

Compress 阶段的四种压缩策略中，"结构化转换"和"关键词提取"无 Token 消耗，"截断"无 Token 消耗。仅"摘要生成"（SemanticCompressor）需要调用 LLM，产生 Token 消耗。

| 压缩策略 | Token 消耗 | 归属 |
|---------|-----------|------|
| 结构化转换 | 0 | 无 |
| 关键词提取 | 0 | 无 |
| 摘要生成 | 有 | 系统开销，不计入 context_budget |
| 截断 | 0 | 无 |

摘要生成的 LLM 调用属于**系统开销**，不计入 Session 的 `context_budget`。原因：
1. context_budget 是推理循环的输入预算，Compress 是 Pipeline 的内部操作
2. 摘要生成的输入/输出 Token 计入 Session 的 `total_token_consumed`（成本追踪）
3. 摘要生成的调用受 `pipeline.compress.max_llm_calls` 限制（默认 3 次），避免无限消耗

**成本控制**：每次摘要生成的输入不超过 2000 tokens，输出不超过 500 tokens。超过此限制的条目直接降级为关键词提取或截断。

#### 8.1.4 截断

最后兜底策略，直接截断内容：

```python
def compress_truncate(item: ScoredContextItem, max_tokens: int) -> CompressedContextItem:
    """截断——直接截断到 max_tokens"""
    truncated = truncate_to_tokens(item.content, max_tokens)
    ...
```

### 8.2 压缩触发条件

当 Select 阶段完成后，如果选中条目的总 Token 数仍超过预算，触发 Compress：

```python
async def should_compress(selected: list[ScoredContextItem], token_budget: int) -> bool:
    total_tokens = sum(item.token_count for item in selected)
    return total_tokens > token_budget
```

### 8.3 压缩优先级

低分条目先压缩，高分条目尽量保留原始内容：

```
1. 计算超出预算的 Token 数：overflow = total_tokens - token_budget
2. 按综合得分升序排列选中条目（低分优先压缩）
3. 对低分条目依次尝试压缩策略：
   a. 结构化转换（无 Token 成本）
   b. 关键词提取（无 Token 成本）
   c. 摘要生成（有 Token 成本，需评估性价比）
   d. 截断（最后兜底）
4. 每次压缩后重新计算总 Token 数
5. 当总 Token 数 <= token_budget 时停止压缩
```

### 8.4 压缩质量保证

| 保证 | 说明 |
|------|------|
| 最低保留信息 | 压缩后的条目必须保留 `item_id`、`context_kind`、`source_name` 元数据 |
| 压缩标记 | 压缩后的条目标记 `compressed=True` 和 `compression_method` |
| 原始内容引用 | 压缩后的条目保留 `original_item_id`，可追溯原始内容 |
| 质量衰减记录 | 记录压缩前后的 Token 数和预估信息损失比 |

### 8.5 Compress 阶段输出

```python
class CompressedContextItem(BaseModel):
    """Compress 阶段输出——压缩后的上下文条目"""

    item_id: str = Field(description="原始条目 ID")
    context_kind: ContextKind = Field(description="上下文类型")
    source_name: str = Field(description="来源适配器名称")
    content: str = Field(description="压缩后的内容")
    metadata: dict = Field(default_factory=dict, description="元数据")
    token_count: int = Field(ge=0, description="压缩后的 Token 数")
    composite_score: float = Field(ge=0.0, le=1.0, description="综合得分")
    compressed: bool = Field(default=False, description="是否经过压缩")
    compression_method: str = Field(default="", description="压缩方法")
    original_token_count: int = Field(default=0, description="压缩前的 Token 数")
```

---

## 9. Assemble 阶段详细设计

### 9.1 按优先级排序

Assemble 阶段首先按综合得分降序排列压缩后的上下文条目，确保高价值内容在上下文窗口的前部（LLM 对前部内容的注意力更强）：

```python
def sort_by_priority(items: list[CompressedContextItem]) -> list[CompressedContextItem]:
    """按综合得分降序排列，高价值内容在前"""
    return sorted(items, key=lambda x: x.composite_score, reverse=True)
```

### 9.2 添加元数据标记

为每个上下文片段添加元数据标记，使 LLM 能识别来源和可信度：

```python
def add_metadata_markers(item: CompressedContextItem) -> str:
    """为上下文片段添加元数据标记"""
    confidence_label = "high" if item.composite_score >= 0.7 else "medium" if item.composite_score >= 0.4 else "low"
    markers = [
        f"[Source: {item.source_name}]",
        f"[Type: {item.context_kind.value}]",
        f"[Confidence: {confidence_label}]",
    ]
    if item.compressed:
        markers.append(f"[Compressed: {item.compression_method}]")
    header = " ".join(markers)
    return f"{header}\n{item.content}"
```

**标记格式示例**：

```
[Source: CodeGraphSource] [Type: SOURCE_CODE] [Confidence: high]
module: auth
file: src/auth/login.py
function: authenticate_user(username, password) -> Token
deps: [user_model, token_service]

[Source: ProjectMemorySource] [Type: MEMORY] [Confidence: medium] [Compressed: structured]
constraint: 支付模块不允许直接访问数据库
scope: payment_module
```

### 9.3 格式标准化

最终上下文按 Markdown 结构组织，分为清晰的区块：

```python
def assemble_context(
    items: list[CompressedContextItem],
    session_metadata: dict,
    low_context_confidence: bool = False,
) -> str:
    """组装最终上下文"""
    sections: list[str] = []

    # 区块 1：会话元信息
    sections.append(_format_session_header(session_metadata))

    # 区块 2：按 ContextKind 分组展示上下文
    kind_groups = _group_by_kind(items)
    for kind in [
        ContextKind.REQUIREMENT,
        ContextKind.SOURCE_CODE,
        ContextKind.ARCH_DOC,
        ContextKind.GIT_HISTORY,
        ContextKind.MEMORY,
        ContextKind.INFERRED_KNOWLEDGE,
    ]:
        if kind in kind_groups:
            sections.append(_format_kind_section(kind, kind_groups[kind]))

    # 区块 3：LOW_CONTEXT_CONFIDENCE 免责声明（如适用）
    if low_context_confidence:
        sections.append(_format_low_confidence_disclaimer())

    return "\n\n".join(sections)
```

**组装后的上下文结构**：

```markdown
## Session Context
Project: {project_name}
Analysis Phase: {current_phase}
Token Budget: {used}/{total}

## Requirement Context
[Source: VectorResultSource] [Type: REQUIREMENT] [Confidence: high]
{需求文档内容}

## Code Context
[Source: CodeGraphSource] [Type: SOURCE_CODE] [Confidence: high]
{代码模块信息}

## Architecture Context
[Source: ProjectMemorySource] [Type: MEMORY] [Confidence: medium]
{架构约束信息}

## Git History Context
[Source: GitHistorySource] [Type: GIT_HISTORY] [Confidence: medium]
{Git 历史信息}

## LOW_CONTEXT_CONFIDENCE WARNING
当前上下文质量未达到最低标准，分析结论仅供参考。
建议：补充更多需求文档或代码索引后重新分析。
```

### 9.4 最终 Token 计数和预算校验

Assemble 阶段最后一步是校验组装后的上下文是否满足 Token 预算：

```python
def validate_budget(assembled: str, token_budget: int, tolerance: float = 0.05) -> BudgetValidationResult:
    """校验组装后的上下文是否满足 Token 预算

    允许 5% 溢出用于元数据标记
    """
    actual_tokens = count_tokens(assembled)
    max_allowed = int(token_budget * (1 + tolerance))

    if actual_tokens <= token_budget:
        return BudgetValidationResult(
            valid=True,
            actual_tokens=actual_tokens,
            budget=token_budget,
            status="within_budget",
        )
    elif actual_tokens <= max_allowed:
        return BudgetValidationResult(
            valid=True,
            actual_tokens=actual_tokens,
            budget=token_budget,
            status="within_tolerance",
        )
    else:
        return BudgetValidationResult(
            valid=False,
            actual_tokens=actual_tokens,
            budget=token_budget,
            status="over_budget",
        )
```

**超预算处理**：如果 Assemble 后仍超预算（超过 105%），回退到 Compress 阶段对低分条目执行更激进的压缩，然后重新 Assemble。最多重试 2 次，仍超预算则截断最低分条目。

---

## 10. Quality Gate 详细设计

### 10.1 检查项

Quality Gate 在 Collect 阶段之后、Score 阶段之前执行，检查收集到的上下文质量是否满足最低标准：

```python
class QualityGateResult(BaseModel):
    """Quality Gate 检查结果"""

    passed: bool = Field(description="是否通过质量检查")
    total_items: int = Field(description="有效 context 条目总数")
    max_semantic_score: float = Field(description="最高语义得分（Collect 阶段预估）")
    code_evidence_count: int = Field(description="代码证据数（SOURCE_CODE 类型条目数）")
    low_context_confidence: bool = Field(default=False, description="是否进入 LOW_CONTEXT_CONFIDENCE 模式")
    failures: list[str] = Field(default_factory=list, description="未通过的检查项列表")
```

**三项检查**：

| # | 检查项 | 阈值 | 说明 |
|---|--------|------|------|
| 1 | 有效 context 条目数 | >= 2 | 至少有 2 条上下文才能进行有意义的推理 |
| 2 | 最高语义得分 | >= 0.65 | 至少有 1 条上下文与当前推理意图高度相关 |
| 3 | 代码证据数 | >= 1 | 代码是分析的基础，必须有代码上下文 |

```python
def check_quality_gate(items: list[ContextItem]) -> QualityGateResult:
    """执行 Quality Gate 检查"""
    failures: list[str] = []

    total_items = len(items)
    if total_items < 2:
        failures.append(f"有效 context 条目数 {total_items} < 2")

    # 语义得分：Collect 阶段尚未计算精确的语义相似度，
    # 使用 ChromaDB 检索时的原始相似度得分作为预估值
    max_semantic = max(
        (item.metadata.get("retrieval_score", 0.0) for item in items),
        default=0.0,
    )
    if max_semantic < 0.65:
        failures.append(f"最高语义得分 {max_semantic:.2f} < 0.65")

    code_count = sum(1 for item in items if item.context_kind == ContextKind.SOURCE_CODE)
    if code_count < 1:
        failures.append(f"代码证据数 {code_count} < 1")

    passed = len(failures) == 0
    return QualityGateResult(
        passed=passed,
        total_items=total_items,
        max_semantic_score=max_semantic,
        code_evidence_count=code_count,
        low_context_confidence=not passed,
        failures=failures,
    )
```

### 10.2 LOW_CONTEXT_CONFIDENCE 模式的行为

当 Quality Gate 检查不通过时，Pipeline 进入 LOW_CONTEXT_CONFIDENCE 模式：

| 行为 | 说明 |
|------|------|
| 降低推理激进度 | Agent 的推理步骤更保守，减少推断性结论 |
| 输出报告标注 | 报告中添加免责声明："证据不足，结论仅供参考" |
| 放宽 Select 阈值 | `min_score` 降低至 0.2，允许更多低分上下文参与 |
| 跳过多样性约束 | 不强制要求 SOURCE_CODE 类型，允许纯文档上下文 |
| 触发补充收集 | 建议用户补充需求文档或执行代码索引 |
| 事件记录 | 发布 `LOW_CONTEXT_CONFIDENCE` 认知级事件 |

```python
class LowContextConfidenceMode:
    """LOW_CONTEXT_CONFIDENCE 模式的行为调整"""

    min_score_override: float = 0.2
    diversity_required_kinds: list[ContextKind] = []
    report_disclaimer: str = (
        "当前上下文质量未达到最低标准，分析结论仅供参考。"
        "建议：补充更多需求文档或代码索引后重新分析。"
    )
```

### 10.3 Quality Gate 在 Pipeline 中的位置

```
Collect ──▶ Quality Gate ──▶ Score ──▶ Select ──▶ Compress ──▶ Assemble
              │
              ├── 通过 → 正常流程
              └── 不通过 → LOW_CONTEXT_CONFIDENCE 模式
                           │
                           ├── 调整 Score/Select 参数
                           └── 继续执行后续阶段（不中断 Pipeline）
```

**关键设计决策**：Quality Gate 不通过时不中断 Pipeline，而是降低标准继续执行。原因：

1. 即使上下文质量不足，仍应尽力给出分析结果（标注免责声明）
2. 完全中断 Pipeline 会导致用户无法获得任何反馈
3. LOW_CONTEXT_CONFIDENCE 模式确保用户知道结果的可信度有限

---

## 11. Context Strategy 模式

### 11.1 ContextStrategy 抽象接口

```python
from abc import ABC, abstractmethod


class ContextStrategy(ABC):
    """上下文策略抽象接口——定义不同推理阶段的上下文偏好"""

    @abstractmethod
    def get_active_sources(self) -> list[type[ContextSource]]:
        """返回该策略激活的 ContextSource 类型列表"""
        ...

    @abstractmethod
    def get_source_budgets(self) -> dict[ContextKind, int]:
        """返回每种 ContextKind 的 max_items 预算"""
        ...

    @abstractmethod
    def get_score_weights(self) -> dict[str, float]:
        """返回 Score 阶段的权重配置 {w1, w2, w3, w4}"""
        ...

    @abstractmethod
    def get_budget_allocation(self) -> dict[ContextKind, float]:
        """返回各 ContextKind 在 Token 预算中的占比上限"""
        ...

    @abstractmethod
    def get_quality_gate_thresholds(self) -> dict[str, float]:
        """返回 Quality Gate 的阈值配置"""
        ...

    @abstractmethod
    def get_select_config(self) -> dict:
        """返回 Select 阶段的配置（min_score, diversity 等）"""
        ...
```

### 11.2 RiskAnalysisStrategy（风险分析策略）

适用于风险分析推理阶段，偏好代码证据和历史风险信号：

```python
class RiskAnalysisStrategy(ContextStrategy):
    """风险分析策略——偏好代码证据、Git 历史、L3 风险记忆"""

    def get_active_sources(self) -> list[type[ContextSource]]:
        return [
            CodeGraphSource,
            GitHistorySource,
            ProjectMemorySource,
            VectorResultSource,
        ]

    def get_source_budgets(self) -> dict[ContextKind, int]:
        return {
            ContextKind.SOURCE_CODE: 20,
            ContextKind.GIT_HISTORY: 15,
            ContextKind.MEMORY: 10,
            ContextKind.REQUIREMENT: 10,
        }

    def get_score_weights(self) -> dict[str, float]:
        return {
            "w1_semantic": 0.35,
            "w2_time_decay": 0.2,
            "w3_user_mark": 0.1,
            "w4_context_kind": 0.35,
        }

    def get_budget_allocation(self) -> dict[ContextKind, float]:
        return {
            ContextKind.SOURCE_CODE: 0.4,
            ContextKind.GIT_HISTORY: 0.25,
            ContextKind.MEMORY: 0.2,
            ContextKind.REQUIREMENT: 0.15,
        }

    def get_quality_gate_thresholds(self) -> dict[str, float]:
        return {
            "min_items": 3,
            "min_semantic_score": 0.65,
            "min_code_evidence": 1,
        }

    def get_select_config(self) -> dict:
        return {
            "min_score": 0.35,
            "max_same_kind_ratio": 0.4,
            "min_kinds": 2,
            "required_kinds": [ContextKind.SOURCE_CODE],
        }
```

| 维度 | 配置 | 说明 |
|------|------|------|
| 激活数据源 | Code + Git + Memory + Requirement | 代码和 Git 历史是风险识别的核心 |
| SOURCE_CODE 预算 | 40% | 代码证据占最大预算 |
| w4_context_kind | 0.35 | 更重视来源权威性（代码 > 记忆） |
| w2_time_decay | 0.2 | Git 历史的时间衰减更重要 |
| min_score | 0.35 | 风险分析要求更可靠的证据 |
| Quality Gate | min_items=3 | 至少 3 条上下文才能做风险判断 |

### 11.3 ArchitectureUnderstandingStrategy（架构理解策略）

适用于架构理解推理阶段，偏好架构文档和代码依赖：

```python
class ArchitectureUnderstandingStrategy(ContextStrategy):
    """架构理解策略——偏好架构文档、代码依赖、L3 约束"""

    def get_active_sources(self) -> list[type[ContextSource]]:
        return [
            CodeGraphSource,
            VectorResultSource,
            ProjectMemorySource,
            GitHistorySource,
        ]

    def get_source_budgets(self) -> dict[ContextKind, int]:
        return {
            ContextKind.SOURCE_CODE: 15,
            ContextKind.REQUIREMENT: 10,
            ContextKind.ARCH_DOC: 15,
            ContextKind.MEMORY: 15,
            ContextKind.GIT_HISTORY: 5,
        }

    def get_score_weights(self) -> dict[str, float]:
        return {
            "w1_semantic": 0.45,
            "w2_time_decay": 0.1,
            "w3_user_mark": 0.15,
            "w4_context_kind": 0.3,
        }

    def get_budget_allocation(self) -> dict[ContextKind, float]:
        return {
            ContextKind.SOURCE_CODE: 0.3,
            ContextKind.REQUIREMENT: 0.15,
            ContextKind.ARCH_DOC: 0.25,
            ContextKind.MEMORY: 0.25,
            ContextKind.GIT_HISTORY: 0.05,
        }

    def get_quality_gate_thresholds(self) -> dict[str, float]:
        return {
            "min_items": 2,
            "min_semantic_score": 0.6,
            "min_code_evidence": 1,
        }

    def get_select_config(self) -> dict:
        return {
            "min_score": 0.25,
            "max_same_kind_ratio": 0.35,
            "min_kinds": 3,
            "required_kinds": [ContextKind.SOURCE_CODE, ContextKind.MEMORY],
        }
```

| 维度 | 配置 | 说明 |
|------|------|------|
| 激活数据源 | Code + Requirement + Memory + Git | 架构文档和 L3 约束是核心 |
| ARCH_DOC 预算 | 25% | 架构文档占较大预算 |
| MEMORY 预算 | 25% | L3 架构约束和决策记录很重要 |
| w1_semantic | 0.45 | 语义相关性最重要（架构理解需要精准匹配） |
| min_kinds | 3 | 架构理解需要多种来源交叉验证 |
| min_score | 0.25 | 允许较低分但有参考价值的上下文 |

### 11.4 EvidenceAggregationStrategy（证据聚合策略）

适用于证据聚合推理阶段，偏好需求原文和代码匹配：

```python
class EvidenceAggregationStrategy(ContextStrategy):
    """证据聚合策略——偏好需求原文、代码匹配、验证结果"""

    def get_active_sources(self) -> list[type[ContextSource]]:
        return [
            VectorResultSource,
            CodeGraphSource,
            ProjectMemorySource,
        ]

    def get_source_budgets(self) -> dict[ContextKind, int]:
        return {
            ContextKind.REQUIREMENT: 20,
            ContextKind.SOURCE_CODE: 15,
            ContextKind.MEMORY: 5,
        }

    def get_score_weights(self) -> dict[str, float]:
        return {
            "w1_semantic": 0.5,
            "w2_time_decay": 0.05,
            "w3_user_mark": 0.2,
            "w4_context_kind": 0.25,
        }

    def get_budget_allocation(self) -> dict[ContextKind, float]:
        return {
            ContextKind.REQUIREMENT: 0.4,
            ContextKind.SOURCE_CODE: 0.4,
            ContextKind.MEMORY: 0.2,
        }

    def get_quality_gate_thresholds(self) -> dict[str, float]:
        return {
            "min_items": 3,
            "min_semantic_score": 0.7,
            "min_code_evidence": 1,
        }

    def get_select_config(self) -> dict:
        return {
            "min_score": 0.3,
            "max_same_kind_ratio": 0.45,
            "min_kinds": 2,
            "required_kinds": [ContextKind.SOURCE_CODE, ContextKind.REQUIREMENT],
        }
```

| 维度 | 配置 | 说明 |
|------|------|------|
| 激活数据源 | Requirement + Code + Memory | 需求原文和代码匹配是证据的核心 |
| REQUIREMENT 预算 | 40% | 需求原文占最大预算 |
| w1_semantic | 0.5 | 语义相关性最关键（证据必须与需求精准匹配） |
| w3_user_mark | 0.2 | 用户标记的上下文在证据聚合中更重要 |
| required_kinds | SOURCE_CODE + REQUIREMENT | 证据聚合必须同时有需求和代码 |
| min_semantic_score | 0.7 | 证据聚合对语义相关性要求最高 |

---

## 12. Token Budget 管理机制

### 12.1 Token 计数方法

```python
class TokenCounter:
    """Token 计数器——统一 Token 计算方法"""

    def __init__(self, model: str = "gpt-4"):
        self.model = model

    def count(self, text: str) -> int:
        """计算文本的 Token 数量

        优先使用 tiktoken（OpenAI 模型），
        降级使用字符数估算（非 OpenAI 模型）
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except (KeyError, ImportError):
            # 降级：按 1 token ≈ 4 字符估算
            return len(text) // 4

    def count_items(self, items: list[ContextItem]) -> int:
        """计算一组 ContextItem 的总 Token 数"""
        return sum(item.token_count for item in items)
```

**Token 计数策略**：

| 模型 | 计数方式 | 说明 |
|------|---------|------|
| OpenAI 系列 | tiktoken | 精确计数 |
| 其他模型 | 字符数 / 4 | 估算，偏保守 |

### 12.2 预算分配策略

```
context_budget（如 128000 tokens）
│
├── 系统提示（15%）= 19200 tokens
│   └── 分析框架、维度定义、输出格式
│
├── 历史上下文（25%）= 32000 tokens
│   └── 前序推理步骤的 Thought/Observation 摘要
│
├── 当前推理（45%）= 57600 tokens  ← Context Pipeline 管控
│   └── Collect → Score → Select → Compress → Assemble 的输出
│
└── 工具输出预留（15%）= 19200 tokens
    └── search_code / get_deps / read_file 等工具的返回
```

**Context Pipeline 的有效预算**：

```python
def compute_effective_budget(
    context_budget: int,
    current_reasoning_ratio: float = 0.45,
) -> int:
    """计算 Context Pipeline 的有效 Token 预算"""
    return int(context_budget * current_reasoning_ratio)
```

### 12.3 预算超限处理

| 阶段 | 超限检测 | 处理方式 |
|------|---------|---------|
| Collect 后 | 总收集条目 Token 数远超预算 | 正常，由后续阶段处理 |
| Select 后 | 选中条目仍超预算 | 触发 Compress 阶段 |
| Compress 后 | 压缩后仍超预算 | 对最低分条目截断，最多重试 2 次 |
| Assemble 后 | 组装后仍超预算（> 105%） | 回退 Compress，更激进压缩 |
| Assemble 重试后 | 仍超预算 | 截断最低分条目直到满足预算 |

**硬约束**：Pipeline 输出的 `token_count` 必须 <= `context_budget × 1.05`。超过此硬约束时，强制截断最低分条目。

---

## 13. 接口定义

### 13.1 ContextPipeline 主接口

```python
from reqradar.kernel.context_types import ContextItem, ContextKind


class ContextPipeline:
    """Context Pipeline 主接口——五阶段流水线的编排器"""

    def __init__(
        self,
        source_registry: dict[ContextKind, ContextSource],
        strategy: ContextStrategy,
        token_counter: TokenCounter,
        quality_gate: QualityGate,
    ):
        self.source_registry = source_registry
        self.strategy = strategy
        self.token_counter = token_counter
        self.quality_gate = quality_gate

    async def execute(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_budget: int,
    ) -> PipelineResult:
        """执行完整的五阶段流水线

        参数:
            session_id: 当前 Session ID
            project_id: 项目 ID
            query: 当前推理步骤的查询意图
            context_budget: Token 预算上限

        返回:
            PipelineResult 包含组装后的上下文和元信息
        """
        # 阶段 1：Collect
        collected = await self._collect(session_id, project_id, query)

        # Quality Gate 检查
        gate_result = self.quality_gate.check(collected)

        # 阶段 2：Score
        scored = await self._score(collected, query)

        # 阶段 3：Select
        effective_budget = compute_effective_budget(context_budget)
        selected = self._select(scored, effective_budget, gate_result)

        # 阶段 4：Compress（如需要）
        compressed = await self._compress(selected, effective_budget)

        # 阶段 5：Assemble
        assembled = self._assemble(compressed, gate_result)

        return PipelineResult(
            context=assembled.context,
            token_count=assembled.token_count,
            budget=context_budget,
            items_count=len(compressed),
            quality_gate_result=gate_result,
            strategy_name=self.strategy.__class__.__name__,
        )

    async def _collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
    ) -> list[ContextItem]:
        """Collect 阶段：并行调用激活的 ContextSource"""
        ...

    async def _score(
        self,
        items: list[ContextItem],
        query: str,
    ) -> list[ScoredContextItem]:
        """Score 阶段：计算综合评分"""
        ...

    def _select(
        self,
        items: list[ScoredContextItem],
        token_budget: int,
        gate_result: QualityGateResult,
    ) -> list[ScoredContextItem]:
        """Select 阶段：Token 预算约束下的贪心选择"""
        ...

    async def _compress(
        self,
        items: list[ScoredContextItem],
        token_budget: int,
    ) -> list[CompressedContextItem]:
        """Compress 阶段：压缩超预算条目"""
        ...

    def _assemble(
        self,
        items: list[CompressedContextItem],
        gate_result: QualityGateResult,
    ) -> AssembleResult:
        """Assemble 阶段：格式标准化和预算校验"""
        ...
```

```python
class PipelineResult(BaseModel):
    """Pipeline 执行结果"""

    context: str = Field(description="组装后的最终上下文文本")
    token_count: int = Field(ge=0, description="实际 Token 数")
    budget: int = Field(ge=0, description="Token 预算")
    items_count: int = Field(ge=0, description="包含的上下文条目数")
    quality_gate_result: QualityGateResult = Field(description="Quality Gate 检查结果")
    strategy_name: str = Field(description="使用的策略名称")
```

### 13.2 ContextSource 抽象接口

见第 5.1 节。

### 13.3 ContextStrategy 抽象接口

见第 11.1 节。

### 13.4 QualityGate 接口

```python
class QualityGate:
    """Quality Gate 检查器"""

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = thresholds or {
            "min_items": 2,
            "min_semantic_score": 0.65,
            "min_code_evidence": 1,
        }

    def check(self, items: list[ContextItem]) -> QualityGateResult:
        """执行 Quality Gate 检查"""
        ...

    def get_low_confidence_config(self) -> LowContextConfidenceMode:
        """返回 LOW_CONTEXT_CONFIDENCE 模式的配置"""
        ...
```

---

## 14. 错误处理

### 14.1 数据源不可用

| 场景 | 处理策略 | 影响 |
|------|---------|------|
| 单个 ContextSource.collect() 抛出异常 | 捕获异常，记录 warning 日志，返回空列表 | 其他 Source 继续收集 |
| 所有 ContextSource 不可用 | Collect 返回空列表，Quality Gate 不通过 | 进入 LOW_CONTEXT_CONFIDENCE 模式 |
| ChromaDB 连接超时 | VectorResultSource 返回空列表 | 缺少语义检索结果，Score 阶段无 embedding |
| PG 数据库不可用 | CodeGraphSource / GitHistorySource 返回空列表 | 缺少代码和 Git 历史 |
| L3 知识服务不可用（P5 后） | L3ContextSource 返回空列表 | 缺少 L3 知识注入，不影响 Pipeline 运行 |

### 14.2 Token 计数不准

| 场景 | 处理策略 |
|------|---------|
| tiktoken 不可用 | 降级使用字符数估算（1 token ≈ 4 字符） |
| 估算偏差导致超预算 | Assemble 阶段的预算校验会检测到，触发回退压缩 |
| 不同模型 Token 计数差异 | 使用目标模型的 Token 计数器；跨模型时按最保守估算 |

### 14.3 压缩失败

| 场景 | 处理策略 |
|------|---------|
| LLM 摘要调用失败 | 跳过摘要生成，降级为关键词提取或截断 |
| LLM 摘要超时 | 跳过摘要生成，降级为截断 |
| 结构化转换解析失败 | 保留原始内容，标记为未压缩 |
| 所有压缩策略失败 | 直接截断到预算上限 |

### 14.4 异常体系

Context Pipeline 相关异常继承自 `core/exceptions.py` 的 `ReqRadarException`：

```python
class ContextPipelineError(ReqRadarException):
    """Context Pipeline 基础异常"""

class ContextSourceUnavailableError(ContextPipelineError):
    """数据源不可用"""

class TokenBudgetExceededError(ContextPipelineError):
    """Token 预算超限（Assemble 后仍超 105%）"""

class CompressionError(ContextPipelineError):
    """压缩失败"""

class QualityGateError(ContextPipelineError):
    """Quality Gate 检查异常（非不通过，而是检查过程本身出错）"""
```

---

## 15. 配置参数

Pipeline 相关配置项纳入 Scope × Domain 配置矩阵，位于 RUNTIME Domain：

### 15.1 Pipeline 全局配置

| 配置项 | 默认值 | 范围 | 说明 |
|--------|--------|------|------|
| `pipeline.context_budget_default` | 128000 | 4096-2000000 | 默认 Token 预算 |
| `pipeline.current_reasoning_ratio` | 0.45 | 0.2-0.8 | 当前推理分区占比 |
| `pipeline.system_prompt_ratio` | 0.15 | 0.05-0.3 | 系统提示分区占比 |
| `pipeline.history_ratio` | 0.25 | 0.1-0.5 | 历史上下文分区占比 |
| `pipeline.tool_output_ratio` | 0.15 | 0.05-0.3 | 工具输出预留分区占比 |
| `pipeline.budget_tolerance` | 0.05 | 0.0-0.1 | 预算溢出容忍度 |
| `pipeline.compress_max_retries` | 2 | 1-5 | 压缩重试次数 |
| `pipeline.collect_timeout` | 10 | 1-60 | 单个 Source 收集超时（秒） |
| `pipeline.assembly_timeout` | 5 | 1-30 | Assemble 阶段超时（秒） |

### 15.2 Score 阶段配置

见第 6.7 节。

### 15.3 Select 阶段配置

| 配置项 | 默认值 | 范围 | 说明 |
|--------|--------|------|------|
| `pipeline.select.min_score` | 0.3 | 0.0-0.5 | 最低综合得分阈值 |
| `pipeline.select.max_same_kind_ratio` | 0.4 | 0.2-0.8 | 同一 ContextKind 最大占比 |
| `pipeline.select.min_kinds` | 2 | 1-6 | 最少 ContextKind 种类数 |
| `pipeline.select.required_kinds` | ["SOURCE_CODE"] | - | 必须包含的 ContextKind |

### 15.4 Compress 阶段配置

| 配置项 | 默认值 | 范围 | 说明 |
|--------|--------|------|------|
| `pipeline.compress.summary_max_ratio` | 0.3 | 0.1-0.5 | 摘要最大占原始 Token 比例 |
| `pipeline.compress.summary_enabled` | true | - | 是否启用 LLM 摘要压缩 |
| `pipeline.compress.truncate_enabled` | true | - | 是否启用截断兜底 |

### 15.5 Quality Gate 配置

| 配置项 | 默认值 | 范围 | 说明 |
|--------|--------|------|------|
| `pipeline.quality_gate.min_items` | 2 | 1-10 | 最少有效条目数 |
| `pipeline.quality_gate.min_semantic_score` | 0.65 | 0.0-1.0 | 最低语义得分 |
| `pipeline.quality_gate.min_code_evidence` | 1 | 0-5 | 最少代码证据数 |
| `pipeline.quality_gate.low_confidence_min_score` | 0.2 | 0.0-0.5 | LOW_CONTEXT_CONFIDENCE 模式的 min_score |

---

## 16. 与其他模块的关系

| 模块 | 文档 | 交互方式 | 说明 |
|------|------|---------|------|
| CognitiveSession | R-01 | Session 持有 `context_budget` 和 `context_usage`，Pipeline 遵守预算约束 | Session 是 Pipeline 的配置来源和状态接收者 |
| Evidence Model | M-01 | Pipeline 的 Collect 阶段从 L3 注入 memory_ref 类型上下文；Score 阶段使用 ContextKind 权重 | Evidence 的 ContextKind 与 Pipeline 的 ContextKind 枚举对齐 |
| Project Cognitive State | M-03 | Pipeline 的 Collect 阶段从 L3 拉取 active + confidence >= 0.6 的知识 | L3 知识是 MEMORY 类型上下文的来源 |
| ToolRuntime | R-04 | Pipeline 的当前推理分区预留了工具输出的 Token 空间 | 工具调用结果不经过 Pipeline，直接注入推理上下文 |
| Event Stream | R-03 | Pipeline 执行过程产生认知级事件 | CONTEXT_COLLECTED / CONTEXT_SCORED / LOW_CONTEXT_CONFIDENCE |
| Checkpoint | R-05 | Checkpoint 的热状态包含 ContextState（当前 Pipeline 的 usage 和 strategy） | Checkpoint 恢复时需重建 Pipeline 状态 |
| index-service | I-01 | Pipeline 通过 ContextSource 适配器调用 index-service 的检索 API | ChromaDB 向量检索、PG 结构化查询 |
| ingestion-service | I-01 | Pipeline 消费 ingestion-service 产生的 L1 索引数据 | L1 是 SOURCE_CODE / REQUIREMENT / GIT_HISTORY 的数据基础 |

**依赖方向**：

```
R-02 (Context Pipeline)
  ├── 依赖 R-01 (Session) 的 context_budget 和 context_strategy
  ├── 依赖 M-01 (Evidence) 的 ContextKind 枚举
  ├── 依赖 M-03 (L3 Knowledge) 的知识注入接口
  ├── 依赖 R-04 (ToolRuntime) 的工具输出预留
  └── 被 R-01 (Session)、R-03 (Event Stream)、R-05 (Checkpoint) 引用
```

---

## 17. 测试策略

### 17.1 P1.10 对比测试详细设计

P1.10 是决定 V2 是否继续推进的关键对比测试，验证 Context Pipeline 是否优于 f-string 拼接。

#### 17.1.1 测试方法

| 维度 | 评估方法 | 通过标准 |
|------|---------|---------|
| 风险识别准确率 | 人工评审（3 份需求 × 2 人交叉评审），标注"风险点"并比对 V1/V2 的召回率和精确率 | V2 召回率 >= V1，精确率 >= V1 |
| 证据溯源完整度 | 检查分析报告中每个结论是否可追溯到 L0/L1 证据 | V2 有源可溯的结论占比 >= V1 |
| 分析覆盖度 | 人工标注每份需求的"应覆盖模块"，比对分析报告中的模块命中率 | V2 命中率 >= V1 |
| 整体质量评估 | LLM-as-judge（GPT-4）对分析报告的完整性、准确性、可操作性打分（1-10） | V2 均分 >= V1 均分 |

| 指标 | 通过标准 | 说明 |
|------|---------|------|
| avg token cost / 次分析 | <= V1 的 1.5 倍 | 超出则说明 Token Budget 控制失效 |
| context assembly 延迟 | <= 2s | Collect → Assemble 总耗时 |
| 总分析延迟 | <= V1 的 1.3 倍 | 用户感知的等待时间 |

#### 17.1.2 fail-fast 规则

任一触发直接判负，不进入均分比较：

| 触发条件 | 说明 |
|---------|------|
| 出现 1 次"关键风险完全未识别" | 人工标注的高风险点在 V2 报告中无任何提及 |
| context assembly 延迟 > 5s | 用户不可接受的等待 |
| avg token cost > V1 的 2 倍 | 成本失控 |

#### 17.1.3 通过标准

- 四个质量维度：人工评审中 V2 优于或等于 V1 的样本 >= 2/3
- 三个成本维度：全部满足
- **质量和成本同时达标，M1 才判定为通过**

### 17.2 单元测试

| 测试类 | 关键测试场景 |
|--------|------------|
| TestContextKind | 枚举值完整性、基础权重映射、权重叠加规则 |
| TestContextItem | 字段默认值、token_count 校验、content_hash 去重 |
| TestScoredContextItem | 综合得分计算、各维度归一化、边界值 |
| TestTokenCounter | OpenAI 模型精确计数、降级估算、空文本 |
| TestQualityGate | 三项检查通过/不通过、LOW_CONTEXT_CONFIDENCE 模式触发 |
| TestTimeDecay | 不同半衰期、边界值（0 天、负数）、指数衰减验证 |
| TestCosineSimilarity | 相同向量、正交向量、相反向量、零向量 |

### 17.3 集成测试

| 测试类 | 关键测试场景 |
|--------|------------|
| TestCollectStage | 多 Source 并行收集、单 Source 失败容错、去重逻辑 |
| TestScoreStage | 完整评分流程、权重配置切换、embedding 缺失降级 |
| TestSelectStage | 贪心选择正确性、预算约束满足、多样性保证、最低阈值过滤 |
| TestCompressStage | 结构化转换、关键词提取、摘要生成、截断兜底、压缩优先级 |
| TestAssembleStage | 格式标准化、元数据标记、预算校验、超预算回退 |
| TestPipelineEndToEnd | 完整五阶段执行、策略切换、LOW_CONTEXT_CONFIDENCE 模式 |

### 17.4 关键测试场景

1. **Token 预算硬约束**：任意输入下，组装后的上下文不超过预算的 105%
2. **Quality Gate 触发**：模拟 Collect 返回空列表/低分列表，验证 LOW_CONTEXT_CONFIDENCE 模式
3. **策略切换**：同一项目，分别使用三种策略执行 Pipeline，验证上下文组合差异
4. **L3 confidence 叠加**：MEMORY 类型上下文带不同 L3 confidence，验证权重叠加正确
5. **压缩回退**：模拟 LLM 摘要失败，验证降级到截断的行为
6. **数据源不可用**：模拟 ChromaDB 超时，验证 Pipeline 继续运行
7. **大规模上下文**：模拟 200+ 条 ContextItem，验证 Select 和 Compress 的性能
8. **空项目**：新项目无 L3 知识、无 Git 历史，验证 Pipeline 的降级行为

---

## 18. 明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| 动态预算调整 | 不做 | Token 预算在 Session 创建时确定，运行期间不可修改 |
| 跨 Session 上下文共享 | 不做 | 每个 Session 独立执行 Pipeline，跨 Session 共享通过 L3 知识注入实现 |
| 上下文缓存 | Phase 1 不做 | 同一 Session 内不同推理步骤的上下文需求不同，缓存命中率低 |
| LLM 辅助评分 | Phase 1 不做 | Score 阶段使用规则引擎，LLM 辅助评分在 Phase 2 探索 |
| 上下文版本化 | 不做 | Pipeline 的输出是即时组装的，不需要版本管理 |
| 自定义 ContextKind | Phase 1 不做 | 6 种 ContextKind 覆盖当前需求，扩展点预留但不开放自定义 |
| 上下文的细粒度权限控制 | Phase 1 不做 | 上下文权限跟随 Session 权限，不单独控制 |
| 上下文可视化 API | Phase 1 不做 | 前端可视化依赖 M-04 Cognitive Graph Schema |
| 上下文 A/B 测试框架 | Phase 1 不做 | P1.10 对比测试是手动执行的，不引入自动化 A/B 框架 |
| 多轮 Pipeline 迭代 | Phase 1 不做 | Pipeline 单次执行，不引入"收集-评估-再收集"的迭代循环 |
