# R-05 Checkpoint Design（Checkpoint 详细设计）

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | Checkpoint System 的详细设计规格，为 P3（Cognitive Runtime Core）中 Checkpoint 相关任务（P3.5-P3.8）的实现提供精确蓝图 |
| 前置文档 | 01_RESTRUCTURE_OVERVIEW.md（6.4 Checkpoint System）、02_SYSTEM_ARCHITECTURE.md（4.5 Checkpoint System）、03_COGNITIVE_ASSET_MODEL.md（5.3 Checkpoint 存储策略、5.4 Checkpoint 状态分区）、04_IMPLEMENTATION_ROADMAP.md（P3 Checkpoint 相关任务、P3 启动前置条件中的事务保证） |
| 核心目标 | 定义 Checkpoint 的数据模型、三区存储策略、创建与恢复流程、版本链管理、事务保证机制及与 index-service 的交互契约 |
| 文档职责 | What & How — Checkpoint 是什么、数据如何分区存储、如何创建和恢复、版本链如何管理、事务如何保证、API 如何暴露 |

---

## 2. 概述

### 2.1 Checkpoint 在 V2 中的定位

ReqRadar V2 的核心能力之一是**分析可恢复**——当推理过程中断（服务重启、网络异常、用户取消后恢复）时，系统能够从最近的完整状态快照继续执行，而非从头开始。Checkpoint 是实现这一能力的核心技术保障。

在 V2 四层认知资产模型中，Checkpoint 属于 **L2（Analysis Records）** 层，是 Session 在某个推理步骤的完整状态快照：

```
L0 Raw Context        →  Checkpoint 不直接引用（通过 Evidence 间接引用）
L1 Structured Facts   →  Checkpoint 的可重建状态来源（工具重新执行可获取）
L2 Analysis Records   →  Checkpoint 的产生与存储层  ★ 本文档
L3 Persistent Knowledge →  Checkpoint 不直接涉及（Session 完成后 L3 沉淀独立触发）
```

**Checkpoint 不是日志，不是增量事件，不是可选的调试工具。** 它是 Runtime State 的版本化快照持久化机制——每个 Checkpoint 代表 Session 在某个推理步骤的完整可恢复状态，是分析可恢复、可回放、可追溯的技术保障。

### 2.2 V1 → V2 的核心升级

| 维度 | V1 | V2 |
|------|----|----|
| 存储方式 | 嵌入 ReportVersion.context_snapshot（JSON blob） | 独立 checkpoints 表 + MinIO 冷存储 |
| 状态分区 | 无分区，全量序列化 | 三区存储：热（PG JSONB）/ 冷（MinIO）/ 可重建（不持久化） |
| 版本链 | 无版本链概念 | 有序版本链，支持回溯追溯 |
| 恢复机制 | 从 JSON blob 反序列化，无校验 | 结构化恢复 + Evidence 链完整性校验 + 失败回退 |
| 事务保证 | 无 | 写入原子性、恢复校验、失败安全、可降级 |
| 触发条件 | 仅分析完成时 | 步骤完成 / 工具调用前后 / 手动 / 周期性 |
| 创建者 | 分析 Agent 直接序列化 | cognitive-rt 创建，index-service 持久化存储 |

---

## 3. 核心概念

### 3.1 Checkpoint 的本质：Session 在某个推理步骤的完整状态快照

Checkpoint 捕获 Session 在某个推理步骤完成后的全部可恢复状态，包含四个子状态：

| 子状态 | 含义 | 存储分区 |
|--------|------|---------|
| **AgentState** | Agent 的推理进度：当前步骤、推理阶段、上下文使用量 | 热状态（PG JSONB） |
| **EvidenceState** | 当前 Session 的证据摘要：总数、各类型分布、各状态分布、平均置信度 | 热状态（PG JSONB） |
| **DimensionState** | 7 维度评估进度：已完成维度、待分析维度、各维度状态 | 热状态（PG JSONB） |
| **ContextState** | 完整上下文快照：上下文来源、评分、选择理由、压缩策略 | 冷状态（MinIO） |

**核心约束**：Checkpoint 必须包含足够的信息，使得从该 Checkpoint 恢复后，Session 能够从 `current_step + 1` 继续执行，且推理结果与未中断时一致。

### 3.2 版本链：每个 Session 的 Checkpoint 形成有序版本链

每个 Session 的 Checkpoint 按 `version` 递增排列，形成有序版本链：

```
Session S1 的版本链：
  v1 (STEP_COMPLETE) ──► v2 (TOOL_PRE) ──► v3 (TOOL_POST) ──► v4 (STEP_COMPLETE) ──► v5 (MANUAL) ──► ...
  │                        │                  │                  │                     │
  previous_version=null    previous=1         previous=2         previous=3            previous=4
```

版本链的关键属性：

| 属性 | 说明 |
|------|------|
| 单调递增 | 同一 Session 内 `version` 严格递增，不允许空洞 |
| 链式引用 | 每个 Checkpoint 记录 `previous_version`，形成双向可遍历链 |
| 不可变 | Checkpoint 一旦写入不可修改（append-only） |
| 可回溯 | 通过版本链可回溯到任意历史 Checkpoint |

### 3.3 三区存储模型

为避免 Checkpoint 变成存储黑洞，将快照数据按访问模式和重建成本分为三类：

```
┌─────────────────────────────────────────────────────────────────┐
│  热状态（Hot State）— PG JSONB                                    │
│  恢复时必须立即读取，需结构化查询                                    │
│  AgentState + EvidenceState + DimensionState                     │
│  单条 ≤ 1MB                                                      │
├─────────────────────────────────────────────────────────────────┤
│  冷状态（Cold State）— MinIO                                      │
│  恢复时可能需要，但体积大且不需结构化查询                             │
│  完整 Context Snapshot（上下文来源、评分、选择理由）                 │
│  无大小限制，按需读取                                              │
├─────────────────────────────────────────────────────────────────┤
│  可重建状态（Reconstructible State）— 不持久化                     │
│  恢复时重新执行工具调用即可获得                                      │
│  工具返回的原始数据、检索 payload                                   │
│  不占持久化存储                                                    │
└─────────────────────────────────────────────────────────────────┘
```

**三区存储的强制约束**：

- 热状态必须能独立支撑 Session 的基本恢复（不含上下文细节）
- 冷状态是热状态的补充，恢复时可按需加载
- 可重建数据**严禁**写入持久化存储，违反此约束视为设计错误

---

## 4. Checkpoint 数据模型

### 4.1 CheckpointType 枚举

```python
from enum import StrEnum


class CheckpointType(StrEnum):
    STEP_COMPLETE = "STEP_COMPLETE"
    TOOL_PRE = "TOOL_PRE"
    TOOL_POST = "TOOL_POST"
    MANUAL = "MANUAL"
    PERIODIC = "PERIODIC"
    CHATBACK_SNAPSHOT = "CHATBACK_SNAPSHOT"
```

| 类型 | 含义 | 触发条件 | 典型频率 |
|------|------|---------|---------|
| `STEP_COMPLETE` | 推理步骤完成后的快照 | 每个推理步骤完成时 | 最高（每步一次） |
| `TOOL_PRE` | 工具调用前的快照 | ToolRuntime 执行工具前 | 中等（依赖工具调用频率） |
| `TOOL_POST` | 工具调用后的快照 | ToolRuntime 执行工具后 | 中等（依赖工具调用频率） |
| `MANUAL` | 用户手动触发的快照 | 用户调用 checkpoint API | 低（用户主动） |
| `PERIODIC` | 周期性自动快照 | 距上次 Checkpoint 超过 `checkpoint_interval` | 低（默认 300s 一次） |
| `CHATBACK_SNAPSHOT` | Chatback 对话前的状态快照 | 进入 WAITING_INPUT 状态前自动创建 | 低（仅 Chatback 场景） |

**类型选择策略**：

| 场景 | 推荐类型 | 说明 |
|------|---------|------|
| 常规推理步骤 | STEP_COMPLETE | 最常见的快照类型，确保每步可恢复 |
| 关键工具调用（写操作、不可逆操作） | TOOL_PRE + TOOL_POST | 工具前后各一次快照，确保可回滚到工具调用前 |
| 用户主动保存 | MANUAL | 用户在 UI 上点击"保存快照" |
| 长时间推理步骤 | PERIODIC | 单步推理超过 interval 时，确保不会丢失太多进度 |

### 4.2 StateSummary 数据模型

```python
from pydantic import BaseModel, Field


class StateSummary(BaseModel):
    context_usage: int = Field(default=0, ge=0, description="当前已用 Token 数")
    context_budget: int = Field(default=128000, gt=0, description="Token 预算上限")
    active_tools: list[str] = Field(default_factory=list, description="当前活跃的工具列表")
    current_phase: str = Field(default="INIT", description="当前推理阶段")
    current_step: int = Field(default=0, ge=0, description="当前推理步骤序号")
    evidence_count: int = Field(default=0, ge=0, description="已收集的证据总数")
    dimensions_completed: list[str] = Field(default_factory=list, description="已完成的维度")
    dimensions_pending: list[str] = Field(default_factory=list, description="待分析的维度")
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `context_usage` | int | 当前已用 Token 数，恢复时用于重建 Context Pipeline 的预算约束 |
| `context_budget` | int | Token 预算上限，恢复时用于验证预算配置一致性 |
| `active_tools` | list[str] | 当前活跃的工具列表，恢复时用于重建 ToolRuntime 状态 |
| `current_phase` | str | 当前推理阶段，恢复时用于定位推理循环位置 |
| `current_step` | int | 当前推理步骤序号，恢复时从 `current_step + 1` 继续 |
| `evidence_count` | int | 已收集的证据总数，恢复时用于校验 Evidence 链完整性 |
| `dimensions_completed` | list[str] | 已完成的维度列表，恢复时用于跳过已完成的维度评估 |
| `dimensions_pending` | list[str] | 待分析的维度列表，恢复时用于确定剩余推理方向 |

### 4.3 CheckpointDiff 数据模型

```python
class CheckpointDiff(BaseModel):
    added: list[str] = Field(
        default_factory=list,
        description="相比上一版本新增的状态字段路径，如 'evidence_count', 'dimensions_completed'",
    )
    removed: list[str] = Field(
        default_factory=list,
        description="相比上一版本移除的状态字段路径",
    )
    modified: list[dict] = Field(
        default_factory=list,
        description="相比上一版本修改的状态字段，每项包含 path/old_value/new_value",
    )
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `added` | list[str] | 新增的状态字段路径列表 |
| `removed` | list[str] | 移除的状态字段路径列表 |
| `modified` | list[dict] | 修改的状态字段列表，每项格式：`{"path": "evidence_count", "old_value": 5, "new_value": 8}` |

**Diff 计算规则**：

- Diff 在 Checkpoint 创建时计算，对比当前状态与 `previous_version` 对应 Checkpoint 的 `state_summary`
- Diff 仅针对 `state_summary` 计算，不涉及热状态的完整 JSONB（完整 diff 开销过大）
- Diff 用于前端展示版本间的变化摘要，不用于恢复逻辑

**hot_state 关键字段变化追踪**：

虽然 Diff 不对完整 hot_state 做 diff（开销过大），但对以下关键字段的变化进行追踪，记录在 `CheckpointDiff.modified` 中：

| 追踪字段 | 路径 | 追踪原因 |
|---------|------|---------|
| Agent 当前步骤 | `agent_state.current_step` | 快速了解推理进度 |
| Agent 当前阶段 | `agent_state.current_phase` | 快速了解推理阶段 |
| 上下文使用量 | `agent_state.context_usage` | 监控预算消耗 |
| 证据总数 | `evidence_state.total_count` | 监控证据积累 |
| 维度完成数 | `dimension_state.completed_count` | 监控维度覆盖 |
| 维度待处理数 | `dimension_state.pending_count` | 监控维度覆盖 |

追踪实现：Checkpoint 创建时，对比当前与前一版本的上述 6 个字段值，变化记录到 `CheckpointDiff.modified` 列表中。这 6 个字段均在 `state_summary` 中有对应项，因此不会增加额外的 diff 计算开销。

### 4.4 CheckpointMetadata 数据模型

```python
class CheckpointMetadata(BaseModel):
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="本次推理步骤耗时（毫秒），从上一步完成到本 Checkpoint 创建",
    )
    token_consumed: int = Field(
        default=0,
        ge=0,
        description="本次推理步骤消耗的 Token 数",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="关联的工具调用 ID（仅 TOOL_PRE/TOOL_POST 类型）",
    )
    tool_name: str | None = Field(
        default=None,
        description="关联的工具名称（仅 TOOL_PRE/TOOL_POST 类型）",
    )
    trigger_reason: str = Field(
        default="",
        description="触发本次 Checkpoint 的原因描述",
    )
    hot_state_size_bytes: int = Field(
        default=0,
        ge=0,
        description="热状态 JSONB 的字节大小",
    )
    cold_state_size_bytes: int = Field(
        default=0,
        ge=0,
        description="冷状态文件的字节大小",
    )
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `duration_ms` | int | 本次推理步骤耗时，用于性能分析和前端展示 |
| `token_consumed` | int | 本次推理步骤消耗的 Token 数，用于成本追踪 |
| `tool_call_id` | str \| None | 关联的工具调用 ID，TOOL_PRE/TOOL_POST 类型时非空 |
| `tool_name` | str \| None | 关联的工具名称，TOOL_PRE/TOOL_POST 类型时非空 |
| `trigger_reason` | str | 触发原因，如 "step_5_completed"、"periodic_300s"、"user_manual" |
| `hot_state_size_bytes` | int | 热状态大小，用于监控存储容量 |
| `cold_state_size_bytes` | int | 冷状态大小，用于监控 MinIO 存储容量 |

### 4.5 CheckpointRecord 完整数据模型

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CheckpointRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checkpoint_id: UUID = Field(
        default_factory=uuid.uuid4,
        description="Checkpoint 全局唯一标识",
    )
    session_id: UUID = Field(
        description="所属 CognitiveSession ID",
    )
    version: int = Field(
        ge=1,
        description="版本号，同一 Session 内严格递增",
    )
    previous_version: int | None = Field(
        default=None,
        description="前一版本号，首个 Checkpoint 为 None",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="创建时间",
    )
    created_by: str = Field(
        default="cognitive-rt",
        description="创建者标识，固定为 cognitive-rt",
    )
    type: CheckpointType = Field(
        description="Checkpoint 类型",
    )
    state_summary: StateSummary = Field(
        description="状态摘要，用于快速查询和前端展示",
    )
    diff: CheckpointDiff = Field(
        default_factory=CheckpointDiff,
        description="与前一版本的差异",
    )
    hot_state: dict = Field(
        default_factory=dict,
        description="热状态完整数据（AgentState + EvidenceState + DimensionState），存入 PG JSONB",
    )
    full_state_uri: str | None = Field(
        default=None,
        description="冷状态文件 URI，格式：minio://checkpoints/{session_id}/v{version}/context_snapshot.json",
    )
    metadata: CheckpointMetadata = Field(
        default_factory=CheckpointMetadata,
        description="Checkpoint 元数据",
    )
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `checkpoint_id` | UUID | PK，自动生成 | 全局唯一标识 |
| `session_id` | UUID | FK → cognitive_sessions，非空 | 所属 Session |
| `version` | int | >= 1，同一 session_id 内唯一且递增 | 版本号 |
| `previous_version` | int \| None | 首个为 None，其余为前一个 version | 前一版本号 |
| `created_at` | datetime | 非空，自动设置 | 创建时间 |
| `created_by` | str | 非空，默认 "cognitive-rt" | 创建者 |
| `type` | CheckpointType | 非空 | 快照类型 |
| `state_summary` | StateSummary | 非空 | 状态摘要 |
| `diff` | CheckpointDiff | 非空，默认空 | 与前一版本差异 |
| `hot_state` | dict | 非空，JSONB 存储上限 1MB | 热状态完整数据 |
| `full_state_uri` | str \| None | 冷状态存在时非空 | 冷状态文件 URI |
| `metadata` | CheckpointMetadata | 非空 | 元数据 |

---

## 5. 三区存储详细设计

### 5.1 热状态（PG JSONB）

热状态存储在 `checkpoints` 表的 `hot_state` JSONB 列中，包含恢复时必须立即读取的三个子状态。

#### 5.1.1 AgentState JSONB 结构

```json
{
  "current_step": 12,
  "current_phase": "ANALYSIS",
  "context_usage": 45000,
  "context_budget": 128000,
  "context_strategy": "risk_analysis",
  "active_tools": ["search_code", "get_deps"],
  "cancel_requested": false,
  "pending_question": null,
  "last_thought": "需要检查支付模块的并发安全性...",
  "next_action": "tool_call",
  "next_tool": "search_code",
  "next_tool_params": {"query": "payment concurrency", "top_k": 5}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `current_step` | int | 当前推理步骤序号 |
| `current_phase` | str | 当前推理阶段（INIT / ANALYSIS / EVIDENCE_AGG / DIMENSION_EVAL / REPORT_GEN） |
| `context_usage` | int | 当前已用 Token 数 |
| `context_budget` | int | Token 预算上限 |
| `context_strategy` | str | Context Pipeline 策略名 |
| `active_tools` | list[str] | 当前活跃的工具列表 |
| `cancel_requested` | bool | 是否收到取消请求 |
| `pending_question` | str \| null | 等待用户回答的问题（WAITING_INPUT 时非空） |
| `last_thought` | str | 最近一次推理思考内容，恢复时用于 Agent 上下文衔接 |
| `next_action` | str | 下一步动作类型（tool_call / reasoning / complete） |
| `next_tool` | str \| null | 下一步要调用的工具名 |
| `next_tool_params` | dict \| null | 下一步工具调用参数 |

**查询需求**：

| 查询场景 | SQL 模式 | 说明 |
|---------|---------|------|
| 按 session_id + version 精确查询 | `WHERE session_id = ? AND version = ?` | 恢复时定位特定版本 |
| 按 session_id 查询最新版本 | `WHERE session_id = ? ORDER BY version DESC LIMIT 1` | 恢复时获取最新快照 |
| 按 current_phase 过滤 | `WHERE hot_state->>'current_phase' = ?` | 统计分析 |
| 按 current_step 范围查询 | `WHERE (hot_state->>'current_step')::int BETWEEN ? AND ?` | 回溯特定步骤范围 |

#### 5.1.2 EvidenceState JSONB 结构

```json
{
  "total_count": 8,
  "by_type": {
    "code_evidence": 3,
    "requirement_ref": 2,
    "git_history": 1,
    "inference": 2
  },
  "by_status": {
    "discovered": 2,
    "verified": 5,
    "challenged": 1
  },
  "average_confidence": 0.68,
  "high_confidence_count": 4,
  "last_evidence_id": "ev-abc123def456",
  "evidence_ids": ["ev-aaa", "ev-bbb", "ev-ccc", "ev-ddd", "ev-eee", "ev-fff", "ev-ggg", "ev-hhh"]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_count` | int | 证据总数 |
| `by_type` | dict[str, int] | 按类型分布 |
| `by_status` | dict[str, int] | 按状态分布 |
| `average_confidence` | float | 平均置信度 |
| `high_confidence_count` | int | 高置信度证据数（confidence >= 0.6） |
| `last_evidence_id` | str | 最近一条 Evidence 的 ID |
| `evidence_ids` | list[str] | 当前所有 Evidence ID 列表，恢复时用于校验链完整性 |

**查询需求**：

| 查询场景 | SQL 模式 | 说明 |
|---------|---------|------|
| 恢复时校验 Evidence 链 | `WHERE session_id = ?`，读取 `evidence_ids` | 与 evidence_records 表交叉校验 |
| 统计证据分布 | `SELECT hot_state->'evidence_state'->'by_type' FROM checkpoints` | 分析报告 |

#### 5.1.3 DimensionState JSONB 结构

```json
{
  "dimensions": {
    "completeness": {"status": "sufficient", "evidence_count": 5, "last_updated_step": 8},
    "consistency": {"status": "sufficient", "evidence_count": 4, "last_updated_step": 10},
    "feasibility": {"status": "in_progress", "evidence_count": 2, "last_updated_step": 12},
    "traceability": {"status": "pending", "evidence_count": 0, "last_updated_step": null},
    "ambiguity": {"status": "pending", "evidence_count": 0, "last_updated_step": null},
    "risk": {"status": "pending", "evidence_count": 0, "last_updated_step": null},
    "architecture": {"status": "pending", "evidence_count": 0, "last_updated_step": null}
  },
  "completed_count": 2,
  "pending_count": 5
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `dimensions` | dict[str, DimensionInfo] | 每个维度的状态详情 |
| `completed_count` | int | 已完成维度数 |
| `pending_count` | int | 待分析维度数 |

**DimensionInfo 结构**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | str | 维度状态（pending / in_progress / sufficient / insufficient） |
| `evidence_count` | int | 关联证据数 |
| `last_updated_step` | int \| null | 最近更新的推理步骤 |

**查询需求**：

| 查询场景 | SQL 模式 | 说明 |
|---------|---------|------|
| 恢复时确定剩余推理方向 | 读取 `dimensions` 中 pending/in_progress 的维度 | 跳过已完成维度 |
| 统计维度完成度 | `SELECT hot_state->'dimension_state'->'completed_count' FROM checkpoints` | 前端进度展示 |

#### 5.1.4 热状态大小控制

**单条热状态上限：1MB**。当 `hot_state` JSONB 超过 1MB 时：

1. 优先压缩 `evidence_state.evidence_ids` 列表（只保留最近 50 条 ID，早期 ID 可从 evidence_records 表查询）
2. 压缩 `agent_state.last_thought`（截断至 500 字符）
3. 若仍超限，将 `agent_state` 中的非关键字段（`last_thought`、`next_tool_params`）移至冷状态

> **TOAST 压缩注意事项**：PostgreSQL 的 TOAST 机制会自动压缩超 2KB 的字段值，`pg_column_size()` 返回的是压缩后大小，可能小于原始 JSON 大小。因此 PG CHECK 约束 `pg_column_size(hot_state) <= 1048576` 仅作为兜底保护。应用层在写入前必须执行二次校验：
>
> ```python
> hot_state_json = json.dumps(hot_state, ensure_ascii=False)
> if len(hot_state_json) > 1048576:
>     raise CheckpointTooLargeError(
>         f"hot_state 序列化后 {len(hot_state_json)} 字节，超过 1MB 限制"
>     )
> ```
>
> 若应用层校验通过但 PG CHECK 失败（理论上不应发生），说明 TOAST 压缩后仍超限，需将更多数据迁移到冷状态（MinIO）。

### 5.2 冷状态（MinIO）

冷状态存储完整 Context Snapshot，包含恢复时可能需要但体积大且不需结构化查询的数据。

#### 5.2.1 冷状态 JSON 结构

```json
{
  "checkpoint_id": "uuid",
  "session_id": "uuid",
  "version": 42,
  "context_snapshot": {
    "assembled_context": "完整的组装后上下文文本...",
    "sources": [
      {
        "context_kind": "SOURCE_CODE",
        "uri": "l1://modules/payment",
        "score": 0.92,
        "selected_reason": "高相关性，支付模块直接涉及需求",
        "token_count": 2500,
        "compressed": false
      },
      {
        "context_kind": "REQUIREMENT",
        "uri": "l1://chunks/doc-abc?offset=0&length=500",
        "score": 0.88,
        "selected_reason": "需求原文，最高优先级",
        "token_count": 800,
        "compressed": false
      }
    ],
    "pipeline_config": {
      "strategy": "risk_analysis",
      "budget": 128000,
      "quality_gate_result": {
        "passed": true,
        "effective_context_count": 5,
        "max_semantic_score": 0.92,
        "code_evidence_count": 2
      }
    },
    "compression_log": [
      {
        "source_uri": "l1://chunks/doc-def",
        "original_tokens": 3000,
        "compressed_tokens": 800,
        "method": "summary"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `assembled_context` | str | 完整的组装后上下文文本，恢复时可直接注入 LLM |
| `sources` | list[ContextSource] | 上下文来源列表，含评分和选择理由 |
| `pipeline_config` | dict | Pipeline 配置快照，含策略和 Quality Gate 结果 |
| `compression_log` | list[CompressionEntry] | 压缩日志，记录哪些来源被压缩及压缩方式 |

#### 5.2.2 存储路径格式

```
minio://checkpoints/{session_id}/v{version}/context_snapshot.json
```

| 路径段 | 说明 | 示例 |
|--------|------|------|
| `checkpoints` | MinIO bucket 名称 | 固定值 |
| `{session_id}` | Session UUID | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `v{version}` | 版本号 | `v42` |
| `context_snapshot.json` | 文件名 | 固定值 |

#### 5.2.3 读写流程

**写入流程**：

```
cognitive-rt                              index-service                    MinIO
     │                                         │                            │
     │  1. 序列化冷状态为 JSON                   │                            │
     │  2. 计算 JSON 字节大小                    │                            │
     │                                         │                            │
     │  POST /internal/v2/checkpoints           │                            │
     │  {hot_state, cold_state_json, ...}       │                            │
     │ ────────────────────────────────────────►│                            │
     │                                         │                            │
     │                                         │  3. 写入冷状态到 MinIO      │
     │                                         │ ──────────────────────────►│
     │                                         │                            │
     │                                         │  ◄── 200 {uri} ───────────│
     │                                         │                            │
     │                                         │  4. 写入热状态到 PG JSONB   │
     │                                         │     + full_state_uri 引用  │
     │                                         │                            │
     │  ◄── 201 {checkpoint_id, version} ──────│                            │
```

**读取流程**：

```
cognitive-rt                              index-service                    MinIO
     │                                         │                            │
     │  GET /internal/v2/checkpoints/{sid}?v=N  │                            │
     │ ────────────────────────────────────────►│                            │
     │                                         │                            │
     │                                         │  1. 从 PG 读取热状态        │
     │                                         │  2. 判断是否需要冷状态       │
     │                                         │     (include_cold=true)     │
     │                                         │                            │
     │                                         │  GET context_snapshot.json  │
     │                                         │ ──────────────────────────►│
     │                                         │                            │
     │                                         │  ◄── JSON body ────────────│
     │                                         │                            │
     │  ◄── 200 {hot_state, cold_state, ...} ──│                            │
```

### 5.3 可重建状态（不持久化）

可重建状态是指工具返回的原始数据，恢复时重新执行工具调用即可获得。

#### 5.3.1 可重建状态的范围

| 数据类型 | 说明 | 重建方式 |
|---------|------|---------|
| 工具返回的原始结果 | `search_code` 返回的代码片段列表 | 重新执行 `search_code` 工具 |
| 检索 payload | ChromaDB 向量检索的原始匹配结果 | 重新执行向量检索 |
| LLM 响应原始文本 | LLM 返回的完整文本（含 reasoning） | 不可重建，但已由 Event Stream 记录 |
| 文件内容 | `read_file` 工具读取的文件内容 | 重新执行 `read_file` 工具 |

**注意**：LLM 响应原始文本虽然不可通过重新调用精确重建（LLM 输出具有随机性），但已由 Event Stream 的 `ThoughtGenerated` 事件完整记录。Checkpoint 恢复时，Agent 从 `last_thought` 衔接，不需要精确复现 LLM 的原始响应。

#### 5.3.2 重建触发条件

| 条件 | 说明 |
|------|------|
| Checkpoint 恢复后 Agent 需要执行工具调用 | 恢复后第一个推理步骤可能需要工具数据 |
| Context Pipeline 重建需要检索结果 | 冷状态不可用时，从 L1 重新 Collect |
| Evidence 链校验需要工具输出 | 校验 `tool_output` 类型 Evidence 的来源 |

#### 5.3.3 重建流程

```
恢复 Checkpoint
       │
       ▼
  重建热状态（从 PG JSONB）
       │
       ▼
  重建冷状态（从 MinIO，按需）
       │
       ├── 冷状态可用 → 直接使用 assembled_context
       │
       └── 冷状态不可用 → 触发可重建状态重建
              │
              ▼
         Context Pipeline 重新 Collect
              │
              ├── 从 L1 重新检索代码/需求/Git 历史
              ├── 从 L3 注入项目知识（如可用）
              └── Score → Select → Compress → Assemble
                     │
                     ▼
                重建后的上下文注入 Agent
```

**重建的成本控制**：

| 措施 | 说明 |
|------|------|
| 重建仅在冷状态不可用时触发 | 优先使用冷状态，避免不必要的工具调用 |
| 重建使用与原 Pipeline 相同的策略 | `context_strategy` 从热状态恢复 |
| 重建后的上下文需通过 Quality Gate | 确保重建质量不低于原始上下文 |
| 重建耗时计入恢复延迟 | 前端展示恢复进度时需考虑重建时间 |

### 5.4 三区数据的关联关系

```
┌─────────────────────────────────────────────────────────────────┐
│  CheckpointRecord                                                │
│                                                                  │
│  checkpoint_id: UUID                                             │
│  session_id: UUID ────────────► cognitive_sessions.session_id    │
│  version: int                                                    │
│  previous_version: int ──────► checkpoints.version (同一 session) │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  hot_state (PG JSONB)                                    │    │
│  │  ├── agent_state ────────► Session.state 的快照          │    │
│  │  ├── evidence_state ────► evidence_records 的摘要        │    │
│  │  └── dimension_state ──► dimension_results 的摘要        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  full_state_uri ─────────────► MinIO 冷状态文件引用             │
│                                                                  │
│  （可重建状态：不存储，恢复时重新执行工具调用）                     │
└─────────────────────────────────────────────────────────────────┘
```

**关联约束**：

| 约束 | 说明 |
|------|------|
| `session_id` 必须引用有效的 CognitiveSession | FK 约束保证 |
| `version` 在同一 `session_id` 内唯一 | UNIQUE 约束保证 |
| `previous_version` 必须引用同一 Session 的已存在版本 | 应用层校验 |
| `full_state_uri` 非空时，MinIO 中对应文件必须存在 | 写入原子性保证 |
| `evidence_state.evidence_ids` 中的 ID 必须在 evidence_records 表中存在 | 恢复时校验 |

---

## 6. Checkpoint 创建流程

### 6.1 触发条件

| 触发类型 | 条件 | CheckpointType | 优先级 |
|---------|------|---------------|--------|
| 步骤完成 | 每个推理步骤完成后 | STEP_COMPLETE | 高（默认开启） |
| 工具调用前 | ToolRuntime 执行工具前（仅标记为 `needs_checkpoint` 的工具） | TOOL_PRE | 中（按工具配置） |
| 工具调用后 | ToolRuntime 执行工具后（仅标记为 `needs_checkpoint` 的工具） | TOOL_POST | 中（按工具配置） |
| 手动触发 | 用户调用 checkpoint API | MANUAL | 高（立即执行） |
| 周期性触发 | 距上次 Checkpoint 超过 `checkpoint_interval` | PERIODIC | 低（可配置间隔） |

**触发决策流程**：

```
推理步骤完成
       │
       ├── 步骤完成触发 ──────────────────────► 创建 STEP_COMPLETE Checkpoint
       │
       ├── 距上次 Checkpoint 超过 interval ───► 创建 PERIODIC Checkpoint
       │    （与 STEP_COMPLETE 合并，取 STEP_COMPLETE）
       │
       ├── 用户手动触发 ──────────────────────► 创建 MANUAL Checkpoint
       │
       └── 工具调用触发
              ├── 工具标记 needs_checkpoint=true
              │    ├── 调用前 ──► 创建 TOOL_PRE Checkpoint
              │    └── 调用后 ──► 创建 TOOL_POST Checkpoint
              └── 工具标记 needs_checkpoint=false
                   └── 不触发
```

**合并策略**：当多个触发条件同时满足时，按优先级合并：

1. STEP_COMPLETE 和 PERIODIC 同时触发 → 仅创建 STEP_COMPLETE（避免冗余）
2. TOOL_PRE 和其他类型同时触发 → 分别创建（工具调用前后的快照不可省略）
3. MANUAL 与其他类型同时触发 → 分别创建（用户主动请求必须响应）

### 6.2 创建流程

```
cognitive-rt                              index-service                    MinIO
     │                                         │                            │
     │  1. 判断触发条件                          │                            │
     │  2. Session 转为 CHECKPOINTING           │                            │
     │                                         │                            │
     │  3. 收集当前状态                          │                            │
     │     ├── AgentState: 从 Session.state     │                            │
     │     ├── EvidenceState: 从 EvidenceCollector                            │
     │     ├── DimensionState: 从 DimensionTracker                            │
     │     └── ContextState: 从 Context Pipeline                              │
     │                                         │                            │
     │  4. 计算 diff（与上一版本 state_summary） │                            │
     │                                         │                            │
     │  5. 组装 hot_state JSONB                 │                            │
     │     检查大小 ≤ 1MB                        │                            │
     │     超限则压缩/迁移非关键字段              │                            │
     │                                         │                            │
     │  6. 序列化冷状态 JSON                     │                            │
     │                                         │                            │
     │  POST /internal/v2/checkpoints           │                            │
     │  {                                       │                            │
     │    session_id, version, type,            │                            │
     │    state_summary, diff,                  │                            │
     │    hot_state, cold_state_json,           │                            │
     │    metadata                              │                            │
     │  }                                       │                            │
     │ ────────────────────────────────────────►│                            │
     │                                         │                            │
     │                                         │  7. 写入冷状态到 MinIO      │
     │                                         │ ──────────────────────────►│
     │                                         │                            │
     │                                         │  ◄── {uri} ───────────────│
     │                                         │                            │
     │                                         │  8. PG 事务：               │
     │                                         │     a. INSERT checkpoints  │
     │                                         │     b. INSERT events       │
     │                                         │     （CHECKPOINT_CREATED）  │
     │                                         │     c. UPDATE sessions     │
     │                                         │     （last_checkpoint_ver） │
     │                                         │     COMMIT                  │
     │                                         │                            │
     │  ◄── 201 {checkpoint_id, version} ──────│                            │
     │                                         │                            │
     │  9. Session 转回 RUNNING                 │                            │
     │  10. 发布 CHECKPOINT_CREATED 事件        │                            │
     │  11. last_checkpoint_version += 1        │                            │
     │  12. 恢复推理循环                        │                            │
```

### 6.3 写入原子性保证

**核心要求**：Checkpoint 写入 PG JSONB + 关联 Event 必须在同一事务。

**事务内容**：

```sql
BEGIN;

-- 1. 插入 Checkpoint 记录
INSERT INTO checkpoints (checkpoint_id, session_id, version, previous_version,
    created_at, created_by, type, state_summary, diff, hot_state,
    full_state_uri, metadata)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- 2. 插入关联 Event
INSERT INTO events (event_id, session_id, sequence, type, level, timestamp, payload)
VALUES (?, ?, ?, 'CHECKPOINT_CREATED', 'session', NOW(),
    jsonb_build_object('checkpoint_id', ?, 'version', ?, 'type', ?));

-- 3. 更新 Session 的 last_checkpoint_version
UPDATE cognitive_sessions
SET last_checkpoint_version = ?, updated_at = NOW()
WHERE session_id = ?;

COMMIT;
```

**原子性保证**：

| 保证 | 说明 |
|------|------|
| 事务内全部成功或全部回滚 | PG ACID 保证 |
| Checkpoint 与 Event 一致 | 同一事务写入，不会出现有 Checkpoint 无 Event |
| Session 版本号与 Checkpoint 一致 | 同一事务更新，不会出现版本号不匹配 |
| MinIO 写入在 PG 事务前 | 若 MinIO 写入失败，PG 事务不执行；若 PG 事务失败，MinIO 文件成为孤儿文件（可定期清理） |

**MinIO 写入与 PG 事务的时序**：

```
1. 写入 MinIO（冷状态）
   ├── 成功 → 继续 PG 事务
   └── 失败 → 返回错误，不执行 PG 事务

2. 执行 PG 事务（热状态 + Event + Session 更新）
   ├── 成功 → Checkpoint 创建完成
   └── 失败 → MinIO 文件成为孤儿，定期清理任务回收
```

**孤儿文件清理**：index-service 定期扫描 MinIO 中存在但 PG 中无对应 `full_state_uri` 引用的文件，超过 24 小时的孤儿文件自动删除。

---

## 7. Checkpoint 恢复流程

### 7.1 恢复触发条件

| 触发场景 | 说明 | 恢复入口 |
|---------|------|---------|
| Session 中断后恢复 | Session 状态为 FAILED/TIMEOUT，用户请求恢复 | `POST /sessions/{id}/start {resume_from: version}` |
| 服务重启后恢复 | cognitive-rt 重启后扫描 RUNNING 状态的 Session | 自动触发，使用 `last_checkpoint_version` |
| Chatback 回滚 | 用户在 Chatback 中请求回滚到对话前状态 | 使用 `CHATBACK_SNAPSHOT` 类型的 Checkpoint |

### 7.2 恢复流程

```
cognitive-rt                              index-service
     │                                         │
     │  1. 定位 Checkpoint                      │
     │     ├── 指定版本 → 使用 resume_from       │
     │     └── 未指定 → 使用 last_checkpoint_version
     │                                         │
     │  GET /internal/v2/checkpoints/{sid}?v=N  │
     │  &include_cold=true                      │
     │ ────────────────────────────────────────►│
     │                                         │
     │                                         │  2. 从 PG 读取热状态
     │                                         │  3. 从 MinIO 读取冷状态
     │                                         │
     │  ◄── 200 {checkpoint_data} ─────────────│
     │                                         │
     │  4. 校验 Checkpoint 完整性                │
     │     ├── 热状态 JSONB 结构完整             │
     │     ├── version 与请求一致               │
     │     └── full_state_uri 引用有效          │
     │                                         │
     │  5. 校验 Evidence 链完整性                │
     │     （详见 7.3）                          │
     │                                         │
     │  6. 重建热状态                           │
     │     ├── 恢复 AgentState → Session.state  │
     │     ├── 恢复 EvidenceState → 校验 evidence_ids
     │     └── 恢复 DimensionState → 跳过已完成维度
     │                                         │
     │  7. 重建冷状态（按需）                    │
     │     ├── 冷状态可用 → 直接使用             │
     │     └── 冷状态不可用 → 触发可重建状态重建  │
     │         （详见 5.3.3）                    │
     │                                         │
     │  8. 重建可重建状态                        │
     │     └── 不主动重建，推理循环按需执行工具   │
     │                                         │
     │  9. 恢复 Session                         │
     │     ├── 设置 status = RUNNING            │
     │     ├── 设置 current_step = checkpoint.step + 1
     │     └── 恢复 Context Pipeline            │
     │                                         │
     │  10. 发布 SESSION_RESUMED 事件            │
     │  11. 恢复推理循环                        │
```

### 7.3 恢复时校验：Evidence 链完整性校验

恢复时必须校验 Evidence 链完整性，校验不通过则拒绝恢复。

```python
async def validate_evidence_chain(
    session_id: UUID,
    checkpoint_version: int,
    evidence_ids: list[str],
) -> ValidationResult:
    errors: list[str] = []

    for eid in evidence_ids:
        evidence = await fetch_evidence(eid)
        if evidence is None:
            errors.append(f"Evidence {eid} not found")
            continue

        if evidence.status == "deprecated":
            errors.append(f"Evidence {eid} is deprecated")

        if evidence.confidence.score <= 0:
            errors.append(f"Evidence {eid} has invalid confidence: {evidence.confidence.score}")

        for dep_id in evidence.detail.get("premise_evidence_ids", []):
            if not await evidence_exists(dep_id):
                errors.append(f"Evidence {eid} depends on missing {dep_id}")

    if errors:
        return ValidationResult(valid=False, errors=errors)
    return ValidationResult(valid=True)
```

**校验规则**：

| 规则 | 说明 | 失败处理 |
|------|------|---------|
| Evidence 存在性 | `evidence_ids` 中的每条 Evidence 必须在 evidence_records 表中存在 | 记录缺失 ID，尝试回退到上一版本 |
| Evidence 非废弃 | 每条 Evidence 的 status 不能是 deprecated | 排除废弃 Evidence，重新计算 evidence_count |
| 置信度有效 | 每条 Evidence 的 confidence.score > 0 | 标记为可疑，降低权重但不阻断恢复 |
| 前提证据存在 | inference 类型 Evidence 的 `premise_evidence_ids` 全部存在 | 回退到上一一致点 |

### 7.4 恢复失败处理

当恢复失败时，系统尝试回退到上一个一致点：

```
恢复 Checkpoint v42 失败
       │
       ├── Evidence 链校验失败
       │    └── 尝试恢复 v41
       │         ├── 成功 → 从 v41 继续
       │         └── 失败 → 尝试 v40
       │              ├── 成功 → 从 v40 继续
       │              └── 失败 → 尝试 v39
       │                   └── 仍失败 → 返回错误，建议重新创建 Session
       │
       ├── 热状态数据损坏
       │    └── 尝试从冷状态重建热状态
       │         ├── 成功 → 继续恢复
       │         └── 失败 → 回退到上一版本
       │
       ├── 冷状态不可用
       │    └── 降级为无冷状态恢复
       │         ├── 触发可重建状态重建
       │         └── 成功 → 继续恢复（可能丢失部分上下文细节）
       │
       └── 全部恢复路径失败
            └── 返回 409，建议用户重新创建 Session
```

**回退限制**：最多回退 `recovery_max_rollback` 个版本（默认 3），超过则放弃恢复。

---

## 8. 版本链管理

### 8.1 版本链的查询接口

| 查询场景 | API | SQL |
|---------|-----|-----|
| 获取会话完整版本链 | `GET /internal/v2/checkpoints?session_id={sid}` | `SELECT * FROM checkpoints WHERE session_id = ? ORDER BY version` |
| 获取特定版本 | `GET /internal/v2/checkpoints/{sid}?v={version}` | `SELECT * FROM checkpoints WHERE session_id = ? AND version = ?` |
| 获取最新版本 | `GET /internal/v2/checkpoints/{sid}?latest=true` | `SELECT * FROM checkpoints WHERE session_id = ? ORDER BY version DESC LIMIT 1` |
| 获取特定时间点的状态 | `GET /internal/v2/checkpoints/{sid}?at={timestamp}` | `SELECT * FROM checkpoints WHERE session_id = ? AND created_at <= ? ORDER BY version DESC LIMIT 1` |
| 获取版本间的 diff | `GET /internal/v2/checkpoints/{sid}/diff?from=v1&to=v2` | 查询两个版本后对比 `state_summary` |

### 8.2 版本链的回溯追溯

版本链通过 `previous_version` 字段支持双向遍历：

**前向遍历**（从旧到新）：

```sql
SELECT * FROM checkpoints
WHERE session_id = ?
ORDER BY version ASC;
```

**后向遍历**（从新到旧，沿 previous_version 回溯）：

```python
async def trace_back(session_id: UUID, from_version: int, max_steps: int = 10) -> list[CheckpointRecord]:
    chain = []
    current_version = from_version
    while current_version is not None and len(chain) < max_steps:
        checkpoint = await fetch_checkpoint(session_id, current_version)
        if checkpoint is None:
            break
        chain.append(checkpoint)
        current_version = checkpoint.previous_version
    return chain
```

**回溯追溯的使用场景**：

| 场景 | 说明 |
|------|------|
| 恢复时回退 | 从最新版本沿 previous_version 回退，寻找可恢复的一致点 |
| 推理链审计 | 从任意 Checkpoint 回溯，查看推理过程的完整演变 |
| Chatback 回滚 | 回溯到 CHATBACK_SNAPSHOT 类型的 Checkpoint |
| 前端时间线展示 | 展示 Session 的完整版本链，用户可点击任意版本查看状态 |

### 8.3 版本链的清理策略

#### 8.3.1 过期 Checkpoint 的归档

| 规则 | 说明 |
|------|------|
| 归档条件 | Session 进入终态（COMPLETED/FAILED/CANCELLED/TIMEOUT/ABORTED）超过 `checkpoint_archive_days` 天（默认 30） |
| 归档操作 | 保留最新 N 个 Checkpoint（默认 3），其余的热状态从 PG JSONB 移至 MinIO |
| 归档后 PG 中的记录 | `hot_state` 设为 `{"archived": true, "archive_uri": "minio://..."}`，`full_state_uri` 指向归档文件 |
| 归档文件格式 | `minio://checkpoints-archive/{session_id}/v{version}/hot_state.json` |

#### 8.3.2 过期 Checkpoint 的删除

| 规则 | 说明 |
|------|------|
| 删除条件 | Session 进入终态超过 `checkpoint_delete_days` 天（默认 90） |
| 删除操作 | 删除 PG 中的 checkpoints 记录 + MinIO 中的冷状态和归档文件 |
| 保留策略 | 终态 Session 的最后一个 Checkpoint（SESSION_COMPLETE 类型）永久保留，用于审计 |
| 批量删除 | 每日凌晨低峰期执行，单次批量不超过 1000 个 Session |

#### 8.3.3 活跃 Session 的 Checkpoint 保留

| 规则 | 说明 |
|------|------|
| 保留数量 | 活跃 Session 保留最近 `checkpoint_max_active` 个 Checkpoint（默认 20） |
| 清理触发 | 每次创建新 Checkpoint 时检查 |
| 清理操作 | 超出数量的最旧 Checkpoint 的冷状态从 MinIO 删除，热状态保留在 PG（用于 diff 计算） |
| 不可清理 | MANUAL 和 CHATBACK_SNAPSHOT 类型的 Checkpoint 不受数量限制 |

---

## 9. 事务保证

来自 04_IMPLEMENTATION_ROADMAP.md P3 启动前置条件中的四项事务保证。

### 9.1 写入原子性

**保证**：Checkpoint 写入 PG JSONB + 关联 Event 必须在同一事务。

**实现方式**：

```python
async def write_checkpoint_atomic(
    session_id: UUID,
    checkpoint: CheckpointRecord,
    event_payload: dict,
) -> CheckpointRecord:
    async with db_transaction() as tx:
        await tx.execute(
            "INSERT INTO checkpoints (...) VALUES (...)",
            checkpoint.to_db_params(),
        )
        await tx.execute(
            "INSERT INTO events (event_id, session_id, sequence, type, level, timestamp, payload) "
            "VALUES (?, ?, ?, 'CHECKPOINT_CREATED', 'session', NOW(), ?)",
            (uuid4(), session_id, next_sequence(), json.dumps(event_payload)),
        )
        await tx.execute(
            "UPDATE cognitive_sessions SET last_checkpoint_version = ?, updated_at = NOW() "
            "WHERE session_id = ?",
            (checkpoint.version, session_id),
        )
    return checkpoint
```

**违反原子性的场景及处理**：

| 场景 | 风险 | 处理 |
|------|------|------|
| PG 事务部分失败 | Checkpoint 存在但 Event 不存在 | 不可能，PG ACID 保证事务原子性 |
| MinIO 写入成功但 PG 事务失败 | MinIO 中有孤儿文件 | 定期清理任务回收 |
| PG 事务成功但响应丢失 | cognitive-rt 认为写入失败 | 重试时检测到 version 已存在，返回已有记录 |

### 9.2 恢复时校验

**保证**：恢复时校验 Evidence 链完整性，不通过则拒绝恢复。

**校验流程**：

```
恢复请求
       │
       ▼
  读取 Checkpoint 热状态
       │
       ▼
  提取 evidence_state.evidence_ids
       │
       ▼
  逐条校验 Evidence 存在性、状态、置信度
       │
       ├── 全部通过 → 允许恢复
       │
       └── 存在失败 → 拒绝恢复
              │
              ├── 尝试回退到 previous_version
              │    ├── 上一版本校验通过 → 允许恢复（从更早版本）
              │    └── 上一版本也失败 → 继续回退（最多 3 次）
              │
              └── 全部回退失败 → 返回错误
```

**校验的严格程度**：

| 校验项 | 严格模式 | 宽松模式 |
|--------|---------|---------|
| Evidence 不存在 | 拒绝恢复 | 排除缺失 Evidence，继续恢复 |
| Evidence 已废弃 | 拒绝恢复 | 排除废弃 Evidence，继续恢复 |
| Evidence 置信度异常 | 拒绝恢复 | 标记为可疑，降低权重，继续恢复 |
| 前提 Evidence 缺失 | 拒绝恢复 | 拒绝恢复（不可降级） |

**模式选择**：通过 `checkpoint_recovery_mode` 配置项控制，默认为严格模式。

### 9.3 失败安全

**保证**：Checkpoint 写入失败时，Session 不应继续推进（严格模式）或降级为无 Checkpoint 模式（宽松模式）。

**处理流程**：

```
Checkpoint 写入失败
       │
       ├── 重试 1（立即重试）
       │    ├── 成功 → 继续
       │    └── 失败 → 重试 2（延迟 1s）
       │         ├── 成功 → 继续
       │         └── 失败 → 判断降级策略
       │
       └── 降级策略判断
              │
              ├── 严格模式（checkpoint_degradation = "strict"）
              │    └── Session → ABORTED
              │        发布 SESSION_ABORTED 事件
              │        记录 error_message
              │
              └── 宽松模式（checkpoint_degradation = "lenient"）
                   └── checkpoint_enabled = False
                       发布 CHECKPOINT_DEGRADED 事件
                       Session 继续运行（无 Checkpoint 保障）
```

**降级后的行为**：

| 行为 | 说明 |
|------|------|
| 不再自动创建 Checkpoint | `checkpoint_enabled = False`，推理循环跳过 Checkpoint 逻辑 |
| 手动 Checkpoint 请求返回 409 | 用户无法手动触发 |
| Session 不可恢复 | 中断后只能重新创建 Session |
| 事件流正常 | Event Stream 不受 Checkpoint 降级影响 |
| 降级状态可观察 | `CHECKPOINT_DEGRADED` 事件推送到前端，用户可见 |

### 9.4 可降级

**保证**：自动切换为"无 Checkpoint 模式"继续执行。

**降级触发条件**：

| 条件 | 说明 |
|------|------|
| Checkpoint 写入重试耗尽 | 连续 2 次重试均失败 |
| PG 不可用 | 数据库连接失败或写入超时 |
| MinIO 不可用 | 冷状态写入失败（热状态仍可写入 PG，但冷状态缺失影响恢复质量） |

**降级恢复条件**：

| 条件 | 说明 |
|------|------|
| 存储服务恢复 | 下一个推理步骤前检测到存储服务可用 |
| 手动恢复 | 管理员通过 API 重新启用 Checkpoint |
| Session 重新创建 | 新 Session 默认启用 Checkpoint |

**降级期间的监控**：

| 指标 | 说明 |
|------|------|
| `checkpoint_degraded_sessions` | 当前处于降级模式的 Session 数量 |
| `checkpoint_write_failure_count` | Checkpoint 写入失败次数 |
| `checkpoint_recovery_success_rate` | Checkpoint 恢复成功率 |

---

## 10. 与 index-service 的交互

### 10.1 交互概览

```
cognitive-rt                              index-service
     │                                         │
     │  创建 Checkpoint                         │
     │  POST /internal/v2/checkpoints ─────────►│
     │                                         │
     │  查询 Checkpoint                         │
     │  GET /internal/v2/checkpoints/{sid} ────►│
     │                                         │
     │  查询版本链                               │
     │  GET /internal/v2/checkpoints?session_id=│
     │                                         │
     │  删除过期 Checkpoint                      │
     │  （由 index-service 自主执行，无需调用）    │
     │                                         │
     │  恢复 Checkpoint                          │
     │  GET /internal/v2/checkpoints/{sid}?v=N  │
     │  &include_cold=true ────────────────────►│
```

### 10.2 HTTP API 契约

#### 10.2.1 创建 Checkpoint

```
POST /internal/v2/checkpoints

Request:
{
  "session_id": "uuid",
  "version": 42,
  "previous_version": 41,
  "type": "STEP_COMPLETE",
  "state_summary": { ... },
  "diff": { ... },
  "hot_state": { ... },
  "cold_state_json": "{ ... }",
  "metadata": { ... }
}

Response (201 Created):
{
  "checkpoint_id": "uuid",
  "version": 42,
  "full_state_uri": "minio://checkpoints/{session_id}/v42/context_snapshot.json",
  "created_at": "2026-06-01T10:00:00Z"
}

Error Response:
- 400: 参数校验失败（version 不连续、type 无效等）
- 409: version 已存在（重复写入）
- 503: 存储服务不可用（PG 或 MinIO）
```

#### 10.2.2 查询 Checkpoint

```
GET /internal/v2/checkpoints/{session_id}?v=42&include_cold=false

Query Parameters:
- v: int | null — 版本号，null 时返回最新版本
- include_cold: bool — 是否包含冷状态数据，默认 false
- at: timestamp | null — 获取特定时间点的最新版本

Response (200 OK):
{
  "checkpoint_id": "uuid",
  "session_id": "uuid",
  "version": 42,
  "previous_version": 41,
  "created_at": "2026-06-01T10:00:00Z",
  "type": "STEP_COMPLETE",
  "state_summary": { ... },
  "diff": { ... },
  "hot_state": { ... },
  "cold_state": null,  // include_cold=false 时不返回
  "metadata": { ... }
}

Error Response:
- 404: Checkpoint 不存在
```

#### 10.2.3 查询版本链

```
GET /internal/v2/checkpoints?session_id={sid}&limit=20&offset=0

Query Parameters:
- session_id: UUID (required) — Session ID
- limit: int — 返回条数上限，默认 20，最大 100
- offset: int — 偏移量，默认 0
- type: CheckpointType | null — 按类型过滤

Response (200 OK):
{
  "session_id": "uuid",
  "total": 42,
  "items": [
    {
      "checkpoint_id": "uuid",
      "version": 42,
      "type": "STEP_COMPLETE",
      "created_at": "2026-06-01T10:00:00Z",
      "state_summary": { ... }
    }
  ],
  "has_more": true
}
```

#### 10.2.4 获取版本间 Diff

```
GET /internal/v2/checkpoints/{session_id}/diff?from=40&to=42

Response (200 OK):
{
  "from_version": 40,
  "to_version": 42,
  "diffs": [
    {
      "version": 41,
      "type": "STEP_COMPLETE",
      "diff": { "added": [...], "removed": [...], "modified": [...] }
    },
    {
      "version": 42,
      "type": "STEP_COMPLETE",
      "diff": { "added": [...], "removed": [...], "modified": [...] }
    }
  ]
}
```

---

## 11. 存储设计

### 11.1 PostgreSQL `checkpoints` 表结构

```sql
CREATE TABLE checkpoints (
    checkpoint_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id         UUID NOT NULL REFERENCES cognitive_sessions(session_id) ON DELETE CASCADE,
    version            INTEGER NOT NULL,
    previous_version   INTEGER,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by         VARCHAR(64) NOT NULL DEFAULT 'cognitive-rt',
    type               VARCHAR(20) NOT NULL,
    state_summary      JSONB NOT NULL,
    diff               JSONB NOT NULL DEFAULT '{"added":[],"removed":[],"modified":[]}',
    hot_state          JSONB NOT NULL DEFAULT '{}',
    full_state_uri     VARCHAR(512),
    metadata           JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT uq_checkpoint_session_version UNIQUE (session_id, version),
    CONSTRAINT ck_checkpoint_type CHECK (type IN (
        'STEP_COMPLETE', 'TOOL_PRE', 'TOOL_POST', 'MANUAL', 'PERIODIC'
    )),
    CONSTRAINT ck_version_positive CHECK (version >= 1),
    CONSTRAINT ck_hot_state_size CHECK (pg_column_size(hot_state) <= 1048576),
    CONSTRAINT ck_previous_version CHECK (
        previous_version IS NULL OR previous_version < version
    )
);

-- 按版本查询（恢复时最频繁的查询）
CREATE INDEX idx_checkpoints_session_version ON checkpoints (session_id, version DESC);

-- 按类型过滤
CREATE INDEX idx_checkpoints_session_type ON checkpoints (session_id, type);

-- 按时间查询（时间线展示、过期清理）
CREATE INDEX idx_checkpoints_session_created ON checkpoints (session_id, created_at DESC);

-- JSONB 索引：按 state_summary 中的 current_phase 查询
CREATE INDEX idx_checkpoints_state_phase ON checkpoints
    ((state_summary->>'current_phase'));

-- JSONB 索引：按 state_summary 中的 current_step 查询
CREATE INDEX idx_checkpoints_state_step ON checkpoints
    (((state_summary->>'current_step')::int));

-- JSONB 索引：按 metadata 中的 tool_name 查询
CREATE INDEX idx_checkpoints_meta_tool ON checkpoints
    ((metadata->>'tool_name'));

-- 过期清理：按创建时间批量扫描
CREATE INDEX idx_checkpoints_created_at ON checkpoints (created_at);
```

**字段说明**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `checkpoint_id` | UUID | PK | 全局唯一标识 |
| `session_id` | UUID | FK, NOT NULL | 所属 Session |
| `version` | INTEGER | NOT NULL, >= 1, UNIQUE per session | 版本号 |
| `previous_version` | INTEGER | NULLABLE, < version | 前一版本号 |
| `created_at` | TIMESTAMPTZ | NOT NULL | 创建时间 |
| `created_by` | VARCHAR(64) | NOT NULL, DEFAULT 'cognitive-rt' | 创建者 |
| `type` | VARCHAR(20) | NOT NULL, CHECK | 快照类型 |
| `state_summary` | JSONB | NOT NULL | 状态摘要 |
| `diff` | JSONB | NOT NULL, DEFAULT | 与前一版本差异 |
| `hot_state` | JSONB | NOT NULL, <= 1MB | 热状态完整数据 |
| `full_state_uri` | VARCHAR(512) | NULLABLE | 冷状态文件 URI |
| `metadata` | JSONB | NOT NULL | 元数据 |

**索引设计说明**：

| 索引 | 用途 | 选择性 |
|------|------|--------|
| `idx_checkpoints_session_version` | 恢复时按版本查询，最频繁 | 高（session_id + version 唯一） |
| `idx_checkpoints_session_type` | 按类型过滤版本链 | 中 |
| `idx_checkpoints_session_created` | 时间线展示、过期清理 | 高 |
| `idx_checkpoints_state_phase` | 按推理阶段统计 | 低 |
| `idx_checkpoints_state_step` | 按步骤号回溯 | 中 |
| `idx_checkpoints_meta_tool` | 按工具名查询工具相关快照 | 中 |
| `idx_checkpoints_created_at` | 批量过期清理 | 中 |

### 11.2 MinIO 存储路径和命名规则

| 路径模式 | 说明 | 生命周期 |
|---------|------|---------|
| `checkpoints/{session_id}/v{version}/context_snapshot.json` | 冷状态文件 | 跟随 Checkpoint 生命周期 |
| `checkpoints-archive/{session_id}/v{version}/hot_state.json` | 归档热状态 | 跟随 Session 生命周期 |
| `checkpoints-orphan/` | 孤儿文件临时存放 | 24 小时后自动删除 |

**MinIO Bucket 配置**：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| bucket 名称 | `checkpoints` | 冷状态存储 |
| bucket 名称 | `checkpoints-archive` | 归档存储 |
| 版本控制 | 关闭 | Checkpoint 自身已有版本管理 |
| 生命周期 | 无自动过期 | 由 index-service 管理清理 |
| 访问权限 | 私有 | 仅 index-service 可访问 |

### 11.3 存储容量估算

**假设**：单个 Session 平均 30 个推理步骤，每步一个 STEP_COMPLETE Checkpoint。

| 数据 | 单条大小 | 单 Session 数量 | 单 Session 总量 | 1000 Session/月 |
|------|---------|----------------|----------------|----------------|
| 热状态（PG JSONB） | ~5KB | 30 | ~150KB | ~150MB |
| 冷状态（MinIO） | ~50KB | 30 | ~1.5MB | ~1.5GB |
| state_summary（PG JSONB） | ~0.5KB | 30 | ~15KB | ~15MB |
| diff（PG JSONB） | ~0.3KB | 30 | ~9KB | ~9MB |

**PG 存储估算**（单 Session）：~174KB，1000 Session/月 ≈ 174MB/月

**MinIO 存储估算**（单 Session）：~1.5MB，1000 Session/月 ≈ 1.5GB/月

**清理后稳态**（90 天删除策略，保留最后一个 Checkpoint）：

| 存储 | 稳态估算 | 说明 |
|------|---------|------|
| PG | ~50MB/月 | 仅保留活跃 Session + 终态 Session 最后一个 Checkpoint |
| MinIO | ~500MB/月 | 同上 |

---

## 12. 接口定义

### 12.1 CheckpointManager 接口（cognitive-rt 端）

```python
from abc import ABC, abstractmethod
from reqradar.kernel.checkpoint_types import (
    CheckpointRecord,
    CheckpointType,
    StateSummary,
    CheckpointDiff,
    CheckpointMetadata,
)


class CheckpointManager(ABC):
    """Checkpoint 管理器——cognitive-rt 端接口，负责创建和恢复 Checkpoint"""

    @abstractmethod
    async def create(
        self,
        session_id: UUID,
        type: CheckpointType,
        state_summary: StateSummary,
        hot_state: dict,
        cold_state_json: str | None = None,
        metadata: CheckpointMetadata | None = None,
    ) -> CheckpointRecord:
        """创建 Checkpoint，委托 index-service 持久化存储"""
        ...

    @abstractmethod
    async def restore(
        self,
        session_id: UUID,
        version: int | None = None,
        include_cold: bool = True,
    ) -> CheckpointRecord:
        """恢复 Checkpoint，从 index-service 读取并校验"""
        ...

    @abstractmethod
    async def get_latest_version(self, session_id: UUID) -> int | None:
        """获取 Session 最新 Checkpoint 版本号"""
        ...

    @abstractmethod
    async def list_versions(
        self,
        session_id: UUID,
        limit: int = 20,
        offset: int = 0,
        type: CheckpointType | None = None,
    ) -> list[CheckpointRecord]:
        """查询 Session 的 Checkpoint 版本链"""
        ...

    @abstractmethod
    async def get_diff(
        self,
        session_id: UUID,
        from_version: int,
        to_version: int,
    ) -> list[CheckpointDiff]:
        """获取两个版本间的差异"""
        ...

    @abstractmethod
    async def validate_for_recovery(
        self,
        session_id: UUID,
        version: int,
    ) -> ValidationResult:
        """校验指定版本的 Checkpoint 是否可用于恢复"""
        ...
```

### 12.2 CheckpointStorage 接口（index-service 端）

```python
class CheckpointStorage(ABC):
    """Checkpoint 存储接口——index-service 端，负责持久化存储和查询"""

    @abstractmethod
    async def store(
        self,
        checkpoint: CheckpointRecord,
        cold_state_json: str | None = None,
    ) -> CheckpointRecord:
        """存储 Checkpoint：写入 PG + MinIO（如有冷状态），保证原子性"""
        ...

    @abstractmethod
    async def fetch(
        self,
        session_id: UUID,
        version: int | None = None,
        include_cold: bool = False,
    ) -> CheckpointRecord | None:
        """读取 Checkpoint：从 PG 读取热状态，按需从 MinIO 读取冷状态"""
        ...

    @abstractmethod
    async def list_by_session(
        self,
        session_id: UUID,
        limit: int = 20,
        offset: int = 0,
        type: CheckpointType | None = None,
    ) -> tuple[list[CheckpointRecord], int]:
        """查询 Session 的 Checkpoint 列表，返回 (items, total)"""
        ...

    @abstractmethod
    async def fetch_at_time(
        self,
        session_id: UUID,
        timestamp: datetime,
    ) -> CheckpointRecord | None:
        """获取特定时间点的最新 Checkpoint"""
        ...

    @abstractmethod
    async def delete_expired(
        self,
        before: datetime,
        batch_size: int = 100,
    ) -> int:
        """删除过期的 Checkpoint，返回删除数量"""
        ...

    @abstractmethod
    async def archive_old(
        self,
        session_id: UUID,
        keep_recent: int = 3,
    ) -> int:
        """归档旧 Checkpoint 的热状态到 MinIO，返回归档数量"""
        ...

    @abstractmethod
    async def cleanup_orphan_files(self) -> int:
        """清理 MinIO 中的孤儿文件，返回清理数量"""
        ...
```

### 12.3 Checkpoint 查询/恢复 API

cognitive-rt 暴露的外部 API（供 api-service / 前端调用）：

```
POST /api/v2/sessions/{id}/checkpoint
    手动触发 Checkpoint

Response (200 OK):
{
  "checkpoint_id": "uuid",
  "version": 4,
  "type": "MANUAL",
  "created_at": "2026-06-01T10:05:00Z"
}
```

```
GET /api/v2/sessions/{id}/checkpoints
    ?limit=20&offset=0&type=STEP_COMPLETE

Response (200 OK):
{
  "session_id": "uuid",
  "total": 42,
  "items": [
    {
      "checkpoint_id": "uuid",
      "version": 42,
      "type": "STEP_COMPLETE",
      "created_at": "2026-06-01T10:00:00Z",
      "state_summary": { ... }
    }
  ],
  "has_more": true
}
```

```
GET /api/v2/sessions/{id}/checkpoints/{version}
    ?include_cold=false

Response (200 OK):
{
  "checkpoint_id": "uuid",
  "version": 42,
  "type": "STEP_COMPLETE",
  "created_at": "2026-06-01T10:00:00Z",
  "state_summary": { ... },
  "diff": { ... },
  "metadata": { ... }
}
```

```
POST /api/v2/sessions/{id}/start
    {resume_from: 42}

Response (200 OK):
{
  "session_id": "uuid",
  "status": "RUNNING",
  "resumed_from_version": 42,
  "state": { ... }
}
```

---

## 13. 错误处理

### 13.1 写入失败

| 场景 | 错误类型 | 处理策略 |
|------|---------|---------|
| PG 写入失败 | `CheckpointWriteError` | 重试 2 次（指数退避）；仍失败则触发降级策略 |
| MinIO 写入失败 | `CheckpointColdStateError` | 重试 1 次；仍失败则仅写入热状态（`full_state_uri = null`），降级恢复质量 |
| version 冲突 | `CheckpointVersionConflictError` | 返回已有记录（幂等处理） |
| hot_state 超过 1MB | `CheckpointOversizeError` | 压缩热状态；仍超限则将非关键字段移至冷状态 |
| session_id 不存在 | `SessionNotFoundError` | 拒绝写入，返回 404 |
| PG 事务超时 | `CheckpointTransactionTimeoutError` | 重试 1 次；仍超时则触发降级策略 |

### 13.2 恢复失败

| 场景 | 错误类型 | 处理策略 |
|------|---------|---------|
| Checkpoint 版本不存在 | `CheckpointNotFoundError` | 自动尝试 `version - 1`，最多回退 3 次 |
| 热状态数据损坏 | `CheckpointCorruptedError` | 尝试从冷状态重建热状态 |
| 冷状态文件不存在 | `CheckpointColdStateMissingError` | 降级为无冷状态恢复，触发可重建状态重建 |
| Evidence 链校验失败 | `EvidenceChainValidationError` | 回退到上一个一致点 |
| 全部 Checkpoint 不可用 | `CheckpointRecoveryExhaustedError` | 返回 409，建议重新创建 Session |
| Context Pipeline 重建失败 | `ContextRebuildError` | 从 L1 重新 Collect，降级恢复 |

### 13.3 版本链断裂

| 场景 | 检测方式 | 处理策略 |
|------|---------|---------|
| previous_version 指向不存在的版本 | 查询时发现引用断裂 | 标记为链断裂，发布 `CheckpointChainBroken` 事件 |
| version 序列不连续 | 查询版本链时发现空洞 | 不影响恢复（按 version 排序即可），但记录 warning |
| 同一 version 存在多条记录 | UNIQUE 约束冲突 | 不可能，数据库约束保证 |

### 13.4 MinIO 不可用

| 场景 | 影响 | 处理策略 |
|------|------|---------|
| 创建时 MinIO 不可用 | 冷状态无法写入 | 仅写入热状态，`full_state_uri = null`，恢复质量降级 |
| 恢复时 MinIO 不可用 | 冷状态无法读取 | 降级为无冷状态恢复，触发可重建状态重建 |
| MinIO 长期不可用 | 冷状态持续缺失 | Checkpoint 仍可创建和恢复（仅热状态），但恢复后推理质量可能下降 |
| MinIO 数据丢失 | 冷状态文件被误删 | 热状态仍可恢复基本 Session 状态，上下文需重建 |

### 13.5 异常体系

Checkpoint 相关异常继承自 `core/exceptions.py` 的 `ReqRadarException`：

```python
class CheckpointError(ReqRadarException):
    """Checkpoint 系统基础异常"""

class CheckpointWriteError(CheckpointError):
    """Checkpoint 写入失败"""

class CheckpointColdStateError(CheckpointError):
    """Checkpoint 冷状态操作失败"""

class CheckpointVersionConflictError(CheckpointError):
    """Checkpoint 版本冲突"""

class CheckpointOversizeError(CheckpointError):
    """Checkpoint 热状态超过大小限制"""

class CheckpointCorruptedError(CheckpointError):
    """Checkpoint 数据损坏"""

class CheckpointNotFoundError(CheckpointError):
    """Checkpoint 不存在"""

class CheckpointRecoveryError(CheckpointError):
    """Checkpoint 恢复失败"""

class CheckpointChainBrokenError(CheckpointError):
    """Checkpoint 版本链断裂"""
```

---

## 14. 配置参数

Checkpoint 相关配置项纳入 Scope × Domain 配置矩阵，位于 RUNTIME Domain 下：

| 配置项 | Scope | 默认值 | 范围 | 说明 |
|--------|-------|--------|------|------|
| `checkpoint.enabled` | SYSTEM / PROJECT | true | - | 是否启用自动 Checkpoint |
| `checkpoint.interval` | SYSTEM / PROJECT | 300 | 30-3600 | 自动 Checkpoint 间隔（秒） |
| `checkpoint.degradation` | SYSTEM | "lenient" | "strict" / "lenient" | 写入失败降级策略 |
| `checkpoint.recovery_mode` | SYSTEM | "strict" | "strict" / "lenient" | 恢复校验严格程度 |
| `checkpoint.recovery_max_rollback` | SYSTEM | 3 | 1-10 | 恢复时最大回退版本数 |
| `checkpoint.max_active` | SYSTEM | 20 | 5-100 | 活跃 Session 保留的最大 Checkpoint 数 |
| `checkpoint.hot_state_max_bytes` | SYSTEM | 1048576 | 524288-2097152 | 热状态 JSONB 最大字节数 |
| `checkpoint.archive_days` | SYSTEM | 30 | 7-365 | 终态 Session Checkpoint 归档天数 |
| `checkpoint.delete_days` | SYSTEM | 90 | 30-365 | 终态 Session Checkpoint 删除天数 |
| `checkpoint.keep_last_on_delete` | SYSTEM | true | - | 删除时是否保留最后一个 Checkpoint |
| `checkpoint.write_retry_count` | SYSTEM | 2 | 0-5 | 写入失败重试次数 |
| `checkpoint.write_retry_delay_ms` | SYSTEM | 1000 | 100-10000 | 重试间隔（毫秒） |
| `checkpoint.cold_state_enabled` | SYSTEM | true | - | 是否启用冷状态存储 |
| `checkpoint.orphan_cleanup_hours` | SYSTEM | 24 | 1-168 | 孤儿文件清理间隔（小时） |
| `checkpoint.batch_delete_size` | SYSTEM | 1000 | 100-5000 | 批量删除单次上限 |

**配置矩阵映射**：

| | RUNTIME Domain |
|--|---------------|
| **SYSTEM** | `checkpoint.enabled`, `checkpoint.interval`, `checkpoint.degradation` 等全局默认值 |
| **PROJECT** | 项目级 Checkpoint 间隔、启用开关 |
| **USER** | 不适用（用户不直接配置 Checkpoint） |
| **SESSION** | 请求体中 `config.checkpoint_enabled` 和 `config.checkpoint_interval` 覆盖 |

---

## 15. 与其他模块的关系

| 模块 | 文档 | 交互方式 | 说明 |
|------|------|---------|------|
| **Session 生命周期** | R-01 | Session 拥有 `checkpoint_chain`，cognitive-rt 创建，index-service 存储 | Checkpoint 是 Session 状态快照的持久化载体；Session 状态机包含 CHECKPOINTING 状态 |
| **Event Stream** | R-03 | Checkpoint 创建/恢复产生 Session 级事件 | CHECKPOINT_CREATED / CHECKPOINT_DEGRADED / SESSION_RESUMED 事件；Checkpoint 写入与 Event 在同一 PG 事务 |
| **ToolRuntime** | R-04 | 工具调用前后触发 TOOL_PRE/TOOL_POST Checkpoint | 标记 `needs_checkpoint=true` 的工具自动触发 Checkpoint |
| **Evidence Model** | M-01 | Checkpoint 热状态包含 EvidenceState | 恢复时校验 Evidence 链完整性；Evidence 的 `evidence_ids` 存储在热状态中 |
| **7-Dimension Framework** | M-02 | Checkpoint 热状态包含 DimensionState | 恢复时跳过已完成维度；维度完成度是恢复进度的关键指标 |
| **Context Pipeline** | R-02 | Checkpoint 冷状态存储完整 Context Snapshot | 恢复时从冷状态重建 Context Pipeline；冷状态不可用时从 L1 重新 Collect |
| **index-service** | I-01 | cognitive-rt 通过 HTTP API 调用 index-service 存储/查询 Checkpoint | 服务间同步调用；Checkpoint 的 PG 和 MinIO 存储由 index-service 管理 |

**依赖方向**：

```
R-05 (Checkpoint Design)
  ├── 依赖 R-01 (Session Lifecycle) 的状态机和 Session 数据模型
  ├── 依赖 R-03 (Event Stream) 的事件 Schema 和发布机制
  ├── 依赖 R-04 (ToolRuntime) 的工具能力声明（needs_checkpoint）
  ├── 依赖 M-01 (Evidence Model) 的数据模型和链完整性校验
  ├── 依赖 M-02 (7-Dimension Framework) 的维度枚举和状态定义
  ├── 依赖 R-02 (Context Pipeline) 的上下文组装结果
  └── 被 I-01 (服务间 API 契约) 引用 Checkpoint 存储/查询 API
```

---

## 16. 测试策略

### 16.1 单元测试

| 测试类 | 关键测试场景 | 数量估计 |
|--------|------------|---------|
| TestCheckpointType | 枚举值完整性、字符串转换 | 5+ |
| TestStateSummary | 字段默认值、校验规则、序列化 | 10+ |
| TestCheckpointDiff | added/removed/modified 的计算逻辑 | 10+ |
| TestCheckpointMetadata | 字段校验、TOOL_PRE/TOOL_POST 专属字段 | 8+ |
| TestCheckpointRecord | 完整模型校验、version/previous_version 约束、JSONB 序列化 | 15+ |
| TestCheckpointManager | 创建/恢复/查询的 mock 测试 | 15+ |
| TestCheckpointStorage | 存储/读取/删除的 mock 测试 | 15+ |
| TestDiffCalculation | diff 计算的各种场景（新增字段、修改字段、移除字段） | 10+ |
| TestHotStateSizeControl | 超限时压缩/迁移逻辑 | 8+ |

### 16.2 集成测试

| 测试类 | 关键测试场景 |
|--------|------------|
| TestCheckpointCreate | 创建 STEP_COMPLETE / TOOL_PRE / TOOL_POST / MANUAL / PERIODIC 类型 Checkpoint |
| TestCheckpointAtomicWrite | 验证 PG 事务原子性：Checkpoint + Event + Session 更新同时成功或同时回滚 |
| TestCheckpointColdStateWrite | 验证 MinIO 冷状态写入和 URI 引用正确性 |
| TestCheckpointVersionChain | 验证版本号递增、previous_version 引用正确、链式遍历 |
| TestCheckpointDiffCalculation | 验证连续版本间的 diff 计算正确性 |
| TestCheckpointArchive | 验证归档逻辑：热状态移至 MinIO、PG 中保留引用 |
| TestCheckpointDelete | 验证删除逻辑：PG + MinIO 数据同步删除 |

### 16.3 中断恢复测试（20+ 次）

| # | 测试场景 | 操作 | 预期结果 |
|---|---------|------|---------|
| 1 | 正常恢复 | 中断后从最新 Checkpoint 恢复 | 步骤数和证据链一致 |
| 2 | 指定版本恢复 | 从非最新版本恢复 | 从指定步骤继续 |
| 3 | 服务重启恢复 | cognitive-rt 重启后自动恢复 RUNNING Session | Session 从最近 Checkpoint 继续 |
| 4 | 步骤 1 中断 | 第 1 步完成后中断 | 从 v1 恢复，步骤 2 开始 |
| 5 | 步骤 5 中断 | 第 5 步完成后中断 | 从 v5 恢复，步骤 6 开始 |
| 6 | 步骤 10 中断 | 第 10 步完成后中断 | 从 v10 恢复，步骤 11 开始 |
| 7 | 步骤 20 中断 | 第 20 步完成后中断 | 从 v20 恢复，步骤 21 开始 |
| 8 | Evidence 链损坏恢复 | 模拟 Evidence 缺失 | 回退到上一个一致点 |
| 9 | 全部 Checkpoint 不可用 | 清空所有 Checkpoint | 返回 409 |
| 10 | 热状态损坏恢复 | 模拟 JSONB 数据损坏 | 尝试从冷状态重建 |
| 11 | 冷状态不可用恢复 | MinIO 文件删除 | 降级为无冷状态恢复，触发可重建状态重建 |
| 12 | 恢复后继续完成 | 恢复后让分析继续到完成 | 最终 status = COMPLETED |
| 13 | 恢复后再次中断 | 恢复后第 3 步再次中断 | 从新的 Checkpoint 恢复 |
| 14 | 多次恢复 | 同一 Session 连续恢复 3 次 | 每次恢复后推理结果一致 |
| 15 | Chatback 回滚 | Chatback 对话后回滚到对话前 | 状态恢复到 CHATBACK_SNAPSHOT |
| 16 | TOOL_PRE 恢复 | 工具调用前中断 | 恢复后重新执行工具调用 |
| 17 | TOOL_POST 恢复 | 工具调用后中断 | 恢复后跳过已完成的工具调用 |
| 18 | 宽松模式恢复 | Evidence 缺失但宽松模式 | 排除缺失 Evidence，继续恢复 |
| 19 | 严格模式恢复 | Evidence 缺失且严格模式 | 拒绝恢复，回退到上一版本 |
| 20 | 周期性 Checkpoint 恢复 | 长步骤中间 PERIODIC Checkpoint | 从周期性快照恢复，减少进度丢失 |
| 21 | 手动 Checkpoint 恢复 | 用户手动创建的 Checkpoint | 从手动快照恢复 |
| 22 | 降级模式下的恢复 | Checkpoint 降级后中断 | 无法恢复，返回 409 |
| 23 | 恢复时 Context Pipeline 重建 | 冷状态不可用 | 从 L1 重新 Collect，Quality Gate 通过 |
| 24 | 恢复后维度评估一致性 | 恢复后继续维度评估 | 已完成维度不重复评估 |

### 16.4 并发与竞态测试

| 测试场景 | 操作 | 预期结果 |
|---------|------|---------|
| 并发创建 Checkpoint | 两个推理步骤同时触发 Checkpoint | version 递增无冲突，PG UNIQUE 约束保证 |
| 创建与恢复并发 | 创建 Checkpoint 的同时请求恢复 | 恢复使用创建前的最新版本 |
| 创建与取消并发 | 创建 Checkpoint 的同时请求取消 Session | Checkpoint 创建完成后进入 CANCELLING |

### 16.5 性能测试

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| Checkpoint 写入延迟 | < 100ms（热状态） | 写入 100 个 Checkpoint 取 P99 |
| Checkpoint 写入延迟（含冷状态） | < 500ms | 写入 100 个含冷状态的 Checkpoint 取 P99 |
| Checkpoint 查询延迟 | < 50ms | 查询 1000 次取 P99 |
| Checkpoint 恢复延迟 | < 2s（含校验） | 恢复 50 次（含 Evidence 链校验）取 P99 |
| 版本链查询延迟 | < 200ms（50 个版本） | 查询 100 次取 P99 |
| 热状态大小控制 | 单条 ≤ 1MB | 各种推理场景下的热状态大小监控 |

---

## 17. 明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| Checkpoint 的增量存储 | 不做 | 增量存储增加恢复复杂度，全量快照更简单可靠；热状态 1MB 限制已控制存储成本 |
| Checkpoint 的实时流式同步 | 不做 | Checkpoint 是快照而非事件流，不需要实时同步 |
| Checkpoint 的跨 Session 共享 | 不做 | Checkpoint 绑定单一 Session，不引入跨 Session 状态共享 |
| Checkpoint 的自动合并 | 不做 | 多个 Checkpoint 不合并，保留完整版本链用于审计 |
| Checkpoint 的压缩算法 | Phase 1 不做 | JSONB 本身有 TOAST 压缩；自定义压缩增加复杂度，收益有限 |
| Checkpoint 的加密存储 | Phase 1 不做 | Checkpoint 不含敏感数据（敏感数据在 Evidence 中，由 M-01 管控） |
| Checkpoint 的分布式一致性 | Phase 1 不做 | 单 PG 实例保证一致性；多实例部署时 PG 主从复制即可 |
| Checkpoint 的语义化查询 | Phase 1 不做 | 不支持"找到 Agent 思考过 X 的 Checkpoint"这类语义查询 |
| Checkpoint 的自动回滚 | 不做 | 回滚由用户或 Chatback 显式触发，不自动回滚到历史版本 |
| 可重建状态的缓存 | 不做 | 可重建状态不持久化也不缓存，每次恢复时按需重新执行工具 |
| Checkpoint 的跨项目引用 | 不做 | Checkpoint 绑定 Session 和 Project，不引入跨项目引用 |
