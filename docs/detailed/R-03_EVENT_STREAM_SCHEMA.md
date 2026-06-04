# R-03 Event Stream Schema 详细设计

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | Event Stream 的完整 Schema 定义、传输机制、持久化策略与推送方案，为 P3（Cognitive Runtime Core）的实现提供精确蓝图 |
| 前置文档 | 01_RESTRUCTURE_OVERVIEW.md（6.2 Event Stream）、02_SYSTEM_ARCHITECTURE.md（4.3 Event Stream）、03_COGNITIVE_ASSET_MODEL.md（5.2 L2 Event Stream、5.3 Event 存储策略）、R-01_SESSION_LIFECYCLE.md（6.2 Session 与 Event Stream） |
| 核心目标 | 定义 Event 的三级体系、完整 Schema、Redis Streams 传输机制、PostgreSQL 持久化策略、WebSocket 多节点广播方案，使"日志不是 Runtime，事件才是"成为工程事实 |
| 文档职责 | What & How — Event 是什么、三级体系如何划分、Schema 如何定义、如何传输与持久化、如何推送到前端、如何支撑推理链 Trace |

---

## 2. 概述

### 2.1 Event Stream 在 V2 中的定位

V1 的推理过程可见性依赖散落的日志和 ad-hoc WebSocket 推送，无法结构化地回放、追溯和解释推理过程。V2 引入 Event Stream，将 Runtime 的每一次状态变更建模为不可变的事件记录。

**核心命题：日志不是 Runtime，事件才是。**

| | V1（日志模式） | V2（Event Stream 模式） |
|---|---|---|
| 记录方式 | 散落日志 + ad-hoc WS 推送 | 结构化事件流，三级体系 |
| 可追溯性 | 只能靠日志关键词搜索 | 按 session_id + sequence 精确回放 |
| 可解释性 | 无结构化推理链 | 完整推理链 Trace |
| 实时性 | WS 推送内容不统一 | 统一事件推送，前端可按级别过滤 |
| 持久化 | 日志文件，查询困难 | PostgreSQL 结构化存储，索引查询 |

### 2.2 Event Stream 的核心价值

Event Stream 是 ReqRadar V2 Runtime 的**结构化推理链技术保障**，支撑以下场景：

| 场景 | 说明 |
|------|------|
| 实时 WebSocket 推送 | 前端实时展示推理进度、工具调用、证据发现 |
| Runtime Debug | 开发者通过事件流定位推理过程中的异常行为 |
| 推理链 Trace | 按 session_id + sequence 回放完整推理过程 |
| 可解释性 | 向用户解释"AI 为什么得出这个结论" |
| Timeline | 可视化展示推理步骤的时间线 |
| 未来 Replay | 基于 Event Stream 重放推理过程（Phase 3+） |

---

## 3. 核心概念

### 3.1 Event 的本质

Event 是 Runtime 状态变更的**不可变记录**。它不是日志行，而是具有明确 Schema、可索引、可查询的结构化数据。

**关键属性**：

| 属性 | 说明 |
|------|------|
| 不可变性 | Event 一旦产生，不可修改、不可删除 |
| 有序性 | 同一 Session 内，Event 按 sequence 严格递增 |
| 归属性 | 每个 Event 必须关联一个 session_id |
| 自描述性 | Event 的 payload 包含足够的上下文，无需回查其他数据即可理解事件含义 |
| 轻量性 | 单个 Event 的 payload 应控制在 10KB 以内，大段内容使用引用 |

### 3.2 三级事件体系的层次关系

```
┌────────────────────────────────────────────────────────────┐
│  Session 级事件                                             │
│  Session 生命周期的宏观状态变更                               │
│  粒度：粗，频率：低（整个 Session 5-10 个）                   │
│  消费者：api-service, output-service, index-service          │
├────────────────────────────────────────────────────────────┤
│  Reasoning 级事件                                           │
│  推理循环中每一步的执行状态变更                                │
│  粒度：中，频率：中（每个推理步骤 2-4 个）                     │
│  消费者：api-service（WS推送）, index-service                 │
├────────────────────────────────────────────────────────────┤
│  Cognitive 级事件                                           │
│  认知状态（上下文、证据、维度）的变更                          │
│  粒度：细，频率：高（每个推理步骤可能产生多个）                 │
│  消费者：index-service, api-service（WS推送）                 │
└────────────────────────────────────────────────────────────┘
```

| 层级 | 关注点 | 典型问题 | 事件数量级 |
|------|--------|---------|-----------|
| Session 级 | Session 整体在做什么？ | "分析开始了吗？""分析完成了吗？" | 5-10 / Session |
| Reasoning 级 | Agent 当前在推理什么？ | "正在调用哪个工具？""这一步花了多久？" | 50-200 / Session |
| Cognitive 级 | 认知状态发生了什么变化？ | "发现了什么证据？""维度状态如何变化？" | 100-500 / Session |

### 3.3 Event 的传输路径

```
cognitive-rt（事件产生者）
       │
       ├──► Redis Streams ──► index-service（消费者：持久化到 PostgreSQL）
       │    reqradar:events:{session_id}
       │
       └──► Redis Pub/Sub ──► api-service（消费者：WebSocket 推送到前端）
            ws:session:{session_id}
```

**双通道设计**：

| 通道 | 技术 | 用途 | 持久化 |
|------|------|------|--------|
| Redis Streams | 消费者组模式 | 可靠传输 + 持久化消费 | 传输层不持久化，由消费者持久化到 PG |
| Redis Pub/Sub | 发布/订阅模式 | 实时广播 + WebSocket 推送 | 不持久化，fire-and-forget |

---

## 4. 事件类型完整定义

### 4.1 Session 级事件

Session 级事件描述 CognitiveSession 生命周期的宏观状态变更，与 R-01 中定义的状态转换一一对应。

#### 4.1.1 SESSION_CREATED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_CREATED |
| 描述 | Session 创建成功，配置校验通过，进入 READY 状态 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, output-service, index-service |
| 触发时机 | R-01 状态转换 T1（CREATED → READY） |

**Payload Schema**：

```python
class SessionCreatedPayload(BaseModel):
    session_id: UUID
    project_id: UUID
    user_id: UUID
    config: SessionConfig
    context_budget: int
    context_strategy: str
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `project_id` | UUID | 关联项目 ID |
| `user_id` | UUID | 创建者 ID |
| `config` | SessionConfig | 会话配置快照 |
| `context_budget` | int | Token 预算上限 |
| `context_strategy` | str | Context Pipeline 策略名 |

#### 4.1.2 SESSION_STARTED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_STARTED |
| 描述 | Session 正式启动，推理循环开始执行 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, output-service, index-service |
| 触发时机 | R-01 状态转换 T3（READY → RUNNING） |

**Payload Schema**：

```python
class SessionStartedPayload(BaseModel):
    session_id: UUID
    started_at: datetime
    context_usage: int = 0
    l1_index_available: bool = True
    l3_knowledge_injected: bool = False
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `started_at` | datetime | 启动时间 |
| `context_usage` | int | 初始上下文使用量 |
| `l1_index_available` | bool | L1 索引是否可用 |
| `l3_knowledge_injected` | bool | 是否注入了 L3 知识 |

#### 4.1.3 SESSION_CHECKPOINTED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_CHECKPOINTED |
| 描述 | Checkpoint 写入成功，Session 完成一次状态快照 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, index-service |
| 触发时机 | R-01 状态转换 T6（CHECKPOINTING → RUNNING） |

**Payload Schema**：

```python
class SessionCheckpointedPayload(BaseModel):
    session_id: UUID
    checkpoint_id: UUID
    checkpoint_version: int
    checkpoint_type: str
    state_summary: CheckpointStateSummary
```

```python
class CheckpointStateSummary(BaseModel):
    context_usage: int
    current_step: int
    current_phase: str
    evidence_count: int
    dimensions_completed: list[str]
    dimensions_pending: list[str]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `checkpoint_id` | UUID | Checkpoint 唯一标识 |
| `checkpoint_version` | int | Checkpoint 版本号 |
| `checkpoint_type` | str | Checkpoint 类型（STEP_COMPLETE / CHATBACK_SNAPSHOT / SESSION_COMPLETE / MANUAL） |
| `state_summary` | CheckpointStateSummary | 状态摘要 |

#### 4.1.4 SESSION_COMPLETED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_COMPLETED |
| 描述 | Session 分析完成，所有维度评估结束 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, output-service, index-service |
| 触发时机 | R-01 状态转换 T11（RUNNING → COMPLETED） |

**Payload Schema**：

```python
class SessionCompletedPayload(BaseModel):
    session_id: UUID
    finished_at: datetime
    total_reasoning_steps: int
    total_tool_calls: int
    evidence_count: int
    dimension_summary: dict[str, str]
    context_usage_peak: int
    context_budget: int
    l3_sediment_triggered: bool
    report_generation_triggered: bool
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `finished_at` | datetime | 完成时间 |
| `total_reasoning_steps` | int | 总推理步骤数 |
| `total_tool_calls` | int | 总工具调用数 |
| `evidence_count` | int | 收集的证据总数 |
| `dimension_summary` | dict[str, str] | 各维度评估结果摘要（维度名 → 风险等级） |
| `context_usage_peak` | int | 上下文使用峰值 |
| `context_budget` | int | Token 预算上限 |
| `l3_sediment_triggered` | bool | 是否触发了 L3 沉淀 |
| `report_generation_triggered` | bool | 是否触发了报告生成 |

#### 4.1.5 SESSION_FAILED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_FAILED |
| 描述 | Session 因错误终止（包括 FAILED、TIMEOUT、ABORTED 状态） |
| 产生者 | cognitive-rt |
| 消费者 | api-service, index-service |
| 触发时机 | R-01 状态转换 T2/T12/T13/T14/T16/T17/T19/T20 |

**Payload Schema**：

```python
class SessionFailedPayload(BaseModel):
    session_id: UUID
    finished_at: datetime
    terminal_status: str
    error_message: str
    error_type: str
    last_checkpoint_version: int
    recoverable: bool
    total_reasoning_steps: int
    total_tool_calls: int
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `finished_at` | datetime | 终止时间 |
| `terminal_status` | str | 终态类型（FAILED / TIMEOUT / ABORTED） |
| `error_message` | str | 错误描述 |
| `error_type` | str | 错误类型（异常类名） |
| `last_checkpoint_version` | int | 最新 Checkpoint 版本号，0 表示无可用快照 |
| `recoverable` | bool | 是否可从 Checkpoint 恢复 |
| `total_reasoning_steps` | int | 失败前已完成的推理步骤数 |
| `total_tool_calls` | int | 失败前已完成的工具调用数 |

#### 4.1.6 SESSION_CANCELLING

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_CANCELLING |
| 描述 | Session 正在取消 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, index-service |
| 触发时机 | 用户请求取消 Session，Session 进入 CANCELLING 状态 |

**Payload Schema**：

```python
class SessionCancellingPayload(BaseModel):
    """Session 正在取消"""

    session_id: UUID = Field(description="Session ID")
    reason: str = Field(default="", description="取消原因")
    current_step: int = Field(description="取消时的推理步骤号")
    pending_tool_calls: int = Field(default=0, description="正在执行的工具调用数")
    last_checkpoint_version: int | None = Field(default=None, description="最近的 Checkpoint 版本号")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `reason` | str | 取消原因 |
| `current_step` | int | 取消时的推理步骤号 |
| `pending_tool_calls` | int | 正在执行的工具调用数 |
| `last_checkpoint_version` | int \| None | 最近的 Checkpoint 版本号 |
| `timestamp` | datetime | 事件产生时间 |

#### 4.1.7 SESSION_CANCELLED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_CANCELLED |
| 描述 | Session 已取消 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, output-service, index-service |
| 触发时机 | Session 取消流程完成，进入 CANCELLED 终态 |

**Payload Schema**：

```python
class SessionCancelledPayload(BaseModel):
    """Session 已取消"""

    session_id: UUID = Field(description="Session ID")
    finished_at: datetime = Field(description="取消完成时间")
    reason: str = Field(default="", description="取消原因")
    total_reasoning_steps: int = Field(description="已完成的推理步骤数")
    total_tool_calls: int = Field(description="已完成的工具调用数")
    last_checkpoint_version: int | None = Field(default=None, description="恢复时可用的最近 Checkpoint 版本号")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `finished_at` | datetime | 取消完成时间 |
| `reason` | str | 取消原因 |
| `total_reasoning_steps` | int | 已完成的推理步骤数 |
| `total_tool_calls` | int | 已完成的工具调用数 |
| `last_checkpoint_version` | int \| None | 恢复时可用的最近 Checkpoint 版本号 |
| `timestamp` | datetime | 事件产生时间 |

#### 4.1.8 SESSION_TIMEOUT

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_TIMEOUT |
| 描述 | Session 执行超时 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, output-service, index-service |
| 触发时机 | Session 执行时间超过配置的最大执行时间 |

**Payload Schema**：

```python
class SessionTimeoutPayload(BaseModel):
    """Session 执行超时"""

    session_id: UUID = Field(description="Session ID")
    finished_at: datetime = Field(description="超时时间")
    max_execution_time: int = Field(description="配置的最大执行时间（秒）")
    elapsed_time: int = Field(description="实际执行时间（秒）")
    total_reasoning_steps: int = Field(description="已完成的推理步骤数")
    total_tool_calls: int = Field(description="已完成的工具调用数")
    last_checkpoint_version: int | None = Field(default=None, description="恢复时可用的最近 Checkpoint 版本号")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `finished_at` | datetime | 超时时间 |
| `max_execution_time` | int | 配置的最大执行时间（秒） |
| `elapsed_time` | int | 实际执行时间（秒） |
| `total_reasoning_steps` | int | 已完成的推理步骤数 |
| `total_tool_calls` | int | 已完成的工具调用数 |
| `last_checkpoint_version` | int \| None | 恢复时可用的最近 Checkpoint 版本号 |
| `timestamp` | datetime | 事件产生时间 |

#### 4.1.9 SESSION_ABORTED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_ABORTED |
| 描述 | Session 异常中止（不可恢复错误） |
| 产生者 | cognitive-rt |
| 消费者 | api-service, output-service, index-service |
| 触发时机 | Session 遇到不可恢复错误（如 Checkpoint 损坏、状态不一致） |

**Payload Schema**：

```python
class SessionAbortedPayload(BaseModel):
    """Session 异常中止（不可恢复错误）"""

    session_id: UUID = Field(description="Session ID")
    finished_at: datetime = Field(description="中止时间")
    error_type: str = Field(description="错误类型，如 CheckpointCorrupted / StateInconsistency / InternalError")
    error_message: str = Field(description="错误详情")
    total_reasoning_steps: int = Field(description="已完成的推理步骤数")
    last_checkpoint_version: int | None = Field(default=None, description="最近的 Checkpoint 版本号（可能不可用）")
    recoverable: bool = Field(default=False, description="是否可恢复（ABORTED 默认不可恢复）")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `finished_at` | datetime | 中止时间 |
| `error_type` | str | 错误类型（CheckpointCorrupted / StateInconsistency / InternalError） |
| `error_message` | str | 错误详情 |
| `total_reasoning_steps` | int | 已完成的推理步骤数 |
| `last_checkpoint_version` | int \| None | 最近的 Checkpoint 版本号（可能不可用） |
| `recoverable` | bool | 是否可恢复（ABORTED 默认不可恢复） |
| `timestamp` | datetime | 事件产生时间 |

#### 4.1.10 SESSION_WAITING_INPUT

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_WAITING_INPUT |
| 描述 | Session 等待用户输入（Chatback） |
| 产生者 | cognitive-rt |
| 消费者 | api-service, index-service |
| 触发时机 | Agent 在推理过程中需要用户澄清或确认，进入 WAITING_INPUT 状态 |

**Payload Schema**：

```python
class SessionWaitingInputPayload(BaseModel):
    """Session 等待用户输入（Chatback）"""

    session_id: UUID = Field(description="Session ID")
    question: str = Field(description="向用户提出的问题")
    context_summary: str = Field(default="", description="当前分析上下文摘要，帮助用户理解问题背景")
    current_step: int = Field(description="等待输入时的推理步骤号")
    checkpoint_version: int = Field(description="Chatback 快照的 Checkpoint 版本号")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `question` | str | 向用户提出的问题 |
| `context_summary` | str | 当前分析上下文摘要，帮助用户理解问题背景 |
| `current_step` | int | 等待输入时的推理步骤号 |
| `checkpoint_version` | int | Chatback 快照的 Checkpoint 版本号 |
| `timestamp` | datetime | 事件产生时间 |

#### 4.1.11 SESSION_RESUMED

| 属性 | 说明 |
|------|------|
| 事件名 | SESSION_RESUMED |
| 描述 | Session 从等待输入恢复执行 |
| 产生者 | cognitive-rt |
| 消费者 | api-service, index-service |
| 触发时机 | 用户回复 Chatback 问题，Session 从 WAITING_INPUT 恢复到 RUNNING |

**Payload Schema**：

```python
class SessionResumedPayload(BaseModel):
    """Session 从等待输入恢复执行"""

    session_id: UUID = Field(description="Session ID")
    user_response: str = Field(default="", description="用户的回复内容")
    resumed_from_step: int = Field(description="恢复时的推理步骤号")
    checkpoint_version: int = Field(description="恢复使用的 Checkpoint 版本号")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `user_response` | str | 用户的回复内容 |
| `resumed_from_step` | int | 恢复时的推理步骤号 |
| `checkpoint_version` | int | 恢复使用的 Checkpoint 版本号 |
| `timestamp` | datetime | 事件产生时间 |

---

### 4.2 Reasoning 级事件

Reasoning 级事件描述推理循环中每一步的执行状态变更，是推理链 Trace 的核心数据来源。

#### 4.2.1 STEP_STARTED

| 属性 | 说明 |
|------|------|
| 事件名 | STEP_STARTED |
| 描述 | 一个推理步骤开始执行 |
| 产生者 | cognitive-rt（推理循环） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | 推理循环中每个步骤开始时 |

**Payload Schema**：

```python
class StepStartedPayload(BaseModel):
    session_id: UUID
    step: int
    phase: str
    context_usage: int
    context_budget: int
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 步骤序号（从 1 开始） |
| `phase` | str | 推理阶段（INIT / ANALYSIS / EVIDENCE_AGG / DIMENSION_EVAL / REPORT_GEN） |
| `context_usage` | int | 当前上下文使用量 |
| `context_budget` | int | Token 预算上限 |

#### 4.2.2 STEP_COMPLETED

| 属性 | 说明 |
|------|------|
| 事件名 | STEP_COMPLETED |
| 描述 | 一个推理步骤执行完成 |
| 产生者 | cognitive-rt（推理循环） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | 推理循环中每个步骤完成时 |

**Payload Schema**：

```python
class StepCompletedPayload(BaseModel):
    session_id: UUID
    step: int
    phase: str
    duration_ms: int
    context_usage: int
    context_budget: int
    tool_calls_in_step: int
    evidence_added_in_step: int
    thought_summary: str
    next_action: str | None = None
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 步骤序号 |
| `phase` | str | 推理阶段 |
| `duration_ms` | int | 步骤耗时（毫秒） |
| `context_usage` | int | 步骤结束后的上下文使用量 |
| `context_budget` | int | Token 预算上限 |
| `tool_calls_in_step` | int | 本步骤内的工具调用次数 |
| `evidence_added_in_step` | int | 本步骤内新增的证据数 |
| `thought_summary` | str | Agent 思考的摘要（截断至 500 字符） |
| `next_action` | str \| None | 下一步动作预告（tool_call / conclude / wait_input） |

#### 4.2.3 TOOL_INVOKED

| 属性 | 说明 |
|------|------|
| 事件名 | TOOL_INVOKED |
| 描述 | 工具被调用 |
| 产生者 | cognitive-rt（ToolRuntime） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | ToolRuntime.execute() 调用开始时 |

**Payload Schema**：

```python
class ToolInvokedPayload(BaseModel):
    session_id: UUID
    step: int
    tool_id: str
    tool_name: str
    call_id: UUID
    params_summary: dict[str, str]
    timeout: float
    retry_count: int = 0
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤序号 |
| `tool_id` | str | 工具注册 ID |
| `tool_name` | str | 工具名称（如 search_code, get_deps） |
| `call_id` | UUID | 本次调用的唯一标识，与 TOOL_RETURNED 配对 |
| `params_summary` | dict[str, str] | 参数摘要（值截断至 200 字符，防止大 payload） |
| `timeout` | float | 超时时间（秒） |
| `retry_count` | int | 当前重试次数（首次调用为 0） |

#### 4.2.4 TOOL_RETURNED

| 属性 | 说明 |
|------|------|
| 事件名 | TOOL_RETURNED |
| 描述 | 工具调用返回结果 |
| 产生者 | cognitive-rt（ToolRuntime） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | ToolRuntime.execute() 调用返回时 |

**Payload Schema**：

```python
class ToolReturnedPayload(BaseModel):
    session_id: UUID
    step: int
    tool_name: str
    call_id: UUID
    success: bool
    duration_ms: int
    result_summary: str | None = None
    error_message: str | None = None
    result_size_bytes: int | None = None
    from_cache: bool = False
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤序号 |
| `tool_name` | str | 工具名称 |
| `call_id` | UUID | 与 TOOL_INVOKED 配对的调用 ID |
| `success` | bool | 调用是否成功 |
| `duration_ms` | int | 调用耗时（毫秒） |
| `result_summary` | str \| None | 结果摘要（截断至 500 字符），大结果不内联 |
| `error_message` | str \| None | 失败时的错误信息 |
| `result_size_bytes` | int \| None | 结果原始大小（字节），用于监控 |
| `from_cache` | bool | 是否来自缓存 |

#### 4.2.5 TOOL_RETRY

| 属性 | 说明 |
|------|------|
| 事件名 | TOOL_RETRY |
| 描述 | 工具执行重试 |
| 产生者 | cognitive-rt（ToolRuntime） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | 工具调用失败后触发重试时 |

**Payload Schema**：

```python
class ToolRetryPayload(BaseModel):
    """工具执行重试"""

    session_id: UUID = Field(description="Session ID")
    step: int = Field(description="当前推理步骤号")
    tool_id: str = Field(description="工具 ID")
    tool_name: str = Field(description="工具名称")
    call_id: str = Field(description="工具调用 ID")
    retry_count: int = Field(description="当前重试次数（从 1 开始）")
    max_retries: int = Field(description="最大重试次数")
    error_type: str = Field(description="触发重试的错误类型")
    error_message: str = Field(default="", description="错误详情")
    next_retry_delay_ms: int = Field(description="下次重试前的等待时间（毫秒）")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤号 |
| `tool_id` | str | 工具 ID |
| `tool_name` | str | 工具名称 |
| `call_id` | str | 工具调用 ID |
| `retry_count` | int | 当前重试次数（从 1 开始） |
| `max_retries` | int | 最大重试次数 |
| `error_type` | str | 触发重试的错误类型 |
| `error_message` | str | 错误详情 |
| `next_retry_delay_ms` | int | 下次重试前的等待时间（毫秒） |
| `timestamp` | datetime | 事件产生时间 |

#### 4.2.6 TOOL_TIMEOUT

| 属性 | 说明 |
|------|------|
| 事件名 | TOOL_TIMEOUT |
| 描述 | 工具执行超时 |
| 产生者 | cognitive-rt（ToolRuntime） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | 工具调用超过配置的超时时间时 |

**Payload Schema**：

```python
class ToolTimeoutPayload(BaseModel):
    """工具执行超时"""

    session_id: UUID = Field(description="Session ID")
    step: int = Field(description="当前推理步骤号")
    tool_id: str = Field(description="工具 ID")
    tool_name: str = Field(description="工具名称")
    call_id: str = Field(description="工具调用 ID")
    timeout_ms: int = Field(description="配置的超时时间（毫秒）")
    retry_count: int = Field(default=0, description="超时前的重试次数")
    will_retry: bool = Field(description="是否会重试")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤号 |
| `tool_id` | str | 工具 ID |
| `tool_name` | str | 工具名称 |
| `call_id` | str | 工具调用 ID |
| `timeout_ms` | int | 配置的超时时间（毫秒） |
| `retry_count` | int | 超时前的重试次数 |
| `will_retry` | bool | 是否会重试 |
| `timestamp` | datetime | 事件产生时间 |

#### 4.2.7 TOOL_PERMISSION_DENIED

| 属性 | 说明 |
|------|------|
| 事件名 | TOOL_PERMISSION_DENIED |
| 描述 | 工具权限被拒绝 |
| 产生者 | cognitive-rt（ToolRuntime） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | 工具调用因权限不足被拒绝时 |

**Payload Schema**：

```python
class ToolPermissionDeniedPayload(BaseModel):
    """工具权限被拒绝"""

    session_id: UUID = Field(description="Session ID")
    step: int = Field(description="当前推理步骤号")
    tool_id: str = Field(description="工具 ID")
    tool_name: str = Field(description="工具名称")
    call_id: str = Field(description="工具调用 ID")
    required_scopes: list[str] = Field(description="工具要求的权限范围")
    granted_scopes: list[str] = Field(default_factory=list, description="Session 实际拥有的权限范围")
    denied_scope: str = Field(description="被拒绝的具体权限")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤号 |
| `tool_id` | str | 工具 ID |
| `tool_name` | str | 工具名称 |
| `call_id` | str | 工具调用 ID |
| `required_scopes` | list[str] | 工具要求的权限范围 |
| `granted_scopes` | list[str] | Session 实际拥有的权限范围 |
| `denied_scope` | str | 被拒绝的具体权限 |
| `timestamp` | datetime | 事件产生时间 |

#### 4.2.8 TOOL_CHECKPOINT_FAILED

| 属性 | 说明 |
|------|------|
| 事件名 | TOOL_CHECKPOINT_FAILED |
| 描述 | 工具关联的 Checkpoint 写入失败 |
| 产生者 | cognitive-rt（ToolRuntime） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | 工具调用关联的 Checkpoint 写入失败时 |

**Payload Schema**：

```python
class ToolCheckpointFailedPayload(BaseModel):
    """工具关联的 Checkpoint 写入失败"""

    session_id: UUID = Field(description="Session ID")
    step: int = Field(description="当前推理步骤号")
    tool_id: str = Field(description="工具 ID")
    tool_name: str = Field(description="工具名称")
    call_id: str = Field(description="工具调用 ID")
    checkpoint_type: str = Field(description="Checkpoint 类型：TOOL_PRE 或 TOOL_POST")
    error_type: str = Field(description="失败原因类型，如 StorageUnavailable / SizeExceeded / TransactionAborted")
    error_message: str = Field(default="", description="失败详情")
    degraded_mode: bool = Field(default=False, description="是否已降级为无 Checkpoint 模式继续执行")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤号 |
| `tool_id` | str | 工具 ID |
| `tool_name` | str | 工具名称 |
| `call_id` | str | 工具调用 ID |
| `checkpoint_type` | str | Checkpoint 类型（TOOL_PRE / TOOL_POST） |
| `error_type` | str | 失败原因类型（StorageUnavailable / SizeExceeded / TransactionAborted） |
| `error_message` | str | 失败详情 |
| `degraded_mode` | bool | 是否已降级为无 Checkpoint 模式继续执行 |
| `timestamp` | datetime | 事件产生时间 |

---

### 4.3 Cognitive 级事件

Cognitive 级事件描述认知状态（上下文、证据、维度）的变更，是推理链 Trace 中最细粒度的事件。

#### 4.3.1 CONTEXT_COLLECTED

| 属性 | 说明 |
|------|------|
| 事件名 | CONTEXT_COLLECTED |
| 描述 | Context Pipeline 的 Collect 阶段完成，上下文源已收集 |
| 产生者 | cognitive-rt（Context Pipeline） |
| 消费者 | index-service |
| 触发时机 | Context Pipeline Collect 阶段完成时 |

**Payload Schema**：

```python
class ContextCollectedPayload(BaseModel):
    session_id: UUID
    step: int
    sources: list[ContextSourceEntry]
    total_items: int
    total_tokens_estimate: int
```

```python
class ContextSourceEntry(BaseModel):
    source_type: str
    item_count: int
    token_estimate: int
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤序号 |
| `sources` | list[ContextSourceEntry] | 各上下文源的收集情况 |
| `total_items` | int | 收集的总条目数 |
| `total_tokens_estimate` | int | 估算的总 Token 数 |

**ContextSourceEntry 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_type` | str | 上下文源类型（SOURCE_CODE / REQUIREMENT / GIT_HISTORY / MEMORY / ARCH_DOC / INFERRED_KNOWLEDGE） |
| `item_count` | int | 该源收集的条目数 |
| `token_estimate` | int | 该源估算的 Token 数 |

#### 4.3.2 CONTEXT_SCORED

| 属性 | 说明 |
|------|------|
| 事件名 | CONTEXT_SCORED |
| 描述 | Context Pipeline 的 Score 阶段完成，上下文片段已评分 |
| 产生者 | cognitive-rt（Context Pipeline） |
| 消费者 | index-service |
| 触发时机 | Context Pipeline Score 阶段完成时 |

**Payload Schema**：

```python
class ContextScoredPayload(BaseModel):
    session_id: UUID
    step: int
    scored_items: int
    selected_items: int
    selected_tokens: int
    budget: int
    top_source_types: list[str]
    avg_score: float
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤序号 |
| `scored_items` | int | 参与评分的条目数 |
| `selected_items` | int | 被选中的条目数 |
| `selected_tokens` | int | 选中条目的总 Token 数 |
| `budget` | int | Token 预算 |
| `top_source_types` | list[str] | 得分最高的上下文源类型（最多 3 个） |
| `avg_score` | float | 选中条目的平均得分 |

#### 4.3.3 EVIDENCE_ADDED

| 属性 | 说明 |
|------|------|
| 事件名 | EVIDENCE_ADDED |
| 描述 | 新证据被添加到 Evidence 链 |
| 产生者 | cognitive-rt（Evidence Aggregation） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | Evidence 聚合阶段完成时 |

**Payload Schema**：

```python
class EvidenceAddedPayload(BaseModel):
    session_id: UUID
    step: int
    evidence_id: UUID
    evidence_type: str
    dimension: str
    source_ref: str
    confidence: float
    summary: str
    depends_on: list[UUID] = Field(default_factory=list)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤序号 |
| `evidence_id` | UUID | 证据唯一标识 |
| `evidence_type` | str | 证据类型（constraint / observation / risk / decision / fact） |
| `dimension` | str | 关联维度（completeness / consistency / feasibility / traceability / ambiguity / risk / architecture） |
| `source_ref` | str | 来源引用（格式：l0://{id} 或 l1://{id}） |
| `confidence` | float | 置信度（0.0-1.0） |
| `summary` | str | 证据摘要（截断至 500 字符） |
| `depends_on` | list[UUID] | 依赖的其他证据 ID |

#### 4.3.4 DIMENSION_CHANGED

| 属性 | 说明 |
|------|------|
| 事件名 | DIMENSION_CHANGED |
| 描述 | 维度评估状态发生变更 |
| 产生者 | cognitive-rt（Dimension Evaluator） |
| 消费者 | api-service（WS推送）, index-service |
| 触发时机 | 维度评估状态更新时 |

**Payload Schema**：

```python
class DimensionChangedPayload(BaseModel):
    session_id: UUID
    step: int
    dimension: str
    previous_risk_level: str | None = None
    current_risk_level: str
    evidence_count: int
    previous_evidence_count: int
    evaluation_status: str
    summary: str | None = None
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | Session 全局唯一标识 |
| `step` | int | 当前推理步骤序号 |
| `dimension` | str | 维度名称 |
| `previous_risk_level` | str \| None | 变更前的风险等级（首次评估为 None） |
| `current_risk_level` | str | 当前风险等级（none / low / medium / high / critical） |
| `evidence_count` | int | 当前证据数 |
| `previous_evidence_count` | int | 变更前的证据数 |
| `evaluation_status` | str | 评估状态（not_started / in_progress / completed） |
| `summary` | str \| None | 维度评估小结（截断至 500 字符） |

---

## 5. Event 基础数据模型

### 5.1 EventRecord Pydantic 模型

```python
class EventRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    session_id: UUID
    sequence: int
    event_type: EventType
    event_level: EventLevel
    timestamp: datetime
    producer: str
    payload: dict[str, Any]
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `event_id` | UUID | PK，自动生成 | 事件全局唯一标识 |
| `session_id` | UUID | FK → cognitive_sessions，非空 | 归属 Session |
| `sequence` | int | 非空，同一 session_id 内严格递增 | 事件序号，用于排序和回放 |
| `event_type` | EventType | 非空 | 事件类型枚举 |
| `event_level` | EventLevel | 非空 | 事件级别枚举 |
| `timestamp` | datetime | 非空 | 事件产生时间（UTC） |
| `producer` | str | 非空 | 事件产生者标识（如 "cognitive-rt", "context-pipeline"） |
| `payload` | dict[str, Any] | 非空 | 事件负载，JSONB 存储 |

### 5.2 EventType 枚举

```python
class EventType(str, Enum):
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_CHECKPOINTED = "SESSION_CHECKPOINTED"
    SESSION_CANCELLING = "SESSION_CANCELLING"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"
    SESSION_ABORTED = "SESSION_ABORTED"
    SESSION_WAITING_INPUT = "SESSION_WAITING_INPUT"
    SESSION_RESUMED = "SESSION_RESUMED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_FAILED = "SESSION_FAILED"

    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    TOOL_INVOKED = "TOOL_INVOKED"
    TOOL_RETURNED = "TOOL_RETURNED"
    TOOL_RETRY = "TOOL_RETRY"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_PERMISSION_DENIED = "TOOL_PERMISSION_DENIED"
    TOOL_CHECKPOINT_FAILED = "TOOL_CHECKPOINT_FAILED"

    CONTEXT_COLLECTED = "CONTEXT_COLLECTED"
    CONTEXT_SCORED = "CONTEXT_SCORED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    DIMENSION_CHANGED = "DIMENSION_CHANGED"
```

### 5.3 EventLevel 枚举

```python
class EventLevel(str, Enum):
    SESSION = "session"
    REASONING = "reasoning"
    COGNITIVE = "cognitive"
```

### 5.4 EventType 与 EventLevel 的映射

| EventType | EventLevel |
|-----------|------------|
| SESSION_CREATED | SESSION |
| SESSION_STARTED | SESSION |
| SESSION_CHECKPOINTED | SESSION |
| SESSION_CANCELLING | SESSION |
| SESSION_CANCELLED | SESSION |
| SESSION_TIMEOUT | SESSION |
| SESSION_ABORTED | SESSION |
| SESSION_WAITING_INPUT | SESSION |
| SESSION_RESUMED | SESSION |
| SESSION_COMPLETED | SESSION |
| SESSION_FAILED | SESSION |
| STEP_STARTED | REASONING |
| STEP_COMPLETED | REASONING |
| TOOL_INVOKED | REASONING |
| TOOL_RETURNED | REASONING |
| TOOL_RETRY | REASONING |
| TOOL_TIMEOUT | REASONING |
| TOOL_PERMISSION_DENIED | REASONING |
| TOOL_CHECKPOINT_FAILED | REASONING |
| CONTEXT_COLLECTED | COGNITIVE |
| CONTEXT_SCORED | COGNITIVE |
| EVIDENCE_ADDED | COGNITIVE |
| DIMENSION_CHANGED | COGNITIVE |

### 5.5 辅助模型

```python
class EventFilter(BaseModel):
    session_id: UUID
    event_level: EventLevel | None = None
    event_type: EventType | None = None
    since_sequence: int | None = None
    limit: int = Field(default=100, ge=1, le=1000)

class EventBatch(BaseModel):
    session_id: UUID
    events: list[EventRecord]
    total: int
    has_more: bool
```

---

## 6. Redis Streams 配置

### 6.1 Stream 命名规则

```
reqradar:events:{session_id}
```

| 规则 | 说明 |
|------|------|
| 前缀 | `reqradar:events:` |
| 后缀 | session_id（UUID 字符串，不含连字符） |
| 示例 | `reqradar:events:a1b2c3d4e5f67890a1b2c3d4e5f67890` |

**设计理由**：按 session_id 分 Stream，而非全局单一 Stream。原因：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 按 Session 分 Stream（选定） | 消费者可按 Session 独立消费；清理时直接删除 Stream；无跨 Session 干扰 | Stream 数量随 Session 增长，需定期清理 |
| 全局单一 Stream | Stream 数量少，管理简单 | 消费者需过滤无关 Session；单 Stream 成为瓶颈；清理困难 |

### 6.2 消费者组配置

```python
CONSUMER_GROUP_NAME = "event-persisters"
CONSUMER_NAME_PREFIX = "index-svc"
```

| 参数 | 值 | 说明 |
|------|-----|------|
| 消费者组名 | `event-persisters` | index-service 持久化消费者组 |
| 消费者名 | `index-svc-{instance_id}` | 按 index-service 实例编号区分 |
| 起始位置 | `0` | 从 Stream 最早的消息开始消费 |
| 消费策略 | `XREADGROUP GROUP event-persisters index-svc-{id} COUNT 10 BLOCK 2000` | 批量读取，阻塞等待 2 秒 |

**消费者组的创建**：

```python
async def ensure_consumer_group(redis: Redis, stream_key: str) -> None:
    try:
        await redis.xgroup_create(
            name=stream_key,
            groupname=CONSUMER_GROUP_NAME,
            id="0",
            mkstream=True,
        )
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise
```

### 6.3 MAXLEN 限制策略

```python
STREAM_MAXLEN = 10000
STREAM_MAXLEN_APPROXIMATE = True
```

| 参数 | 值 | 说明 |
|------|-----|------|
| MAXLEN | 10000 | 每个 Stream 最多保留 10000 条消息 |
| 近似裁剪 | True | 使用 `MAXLEN ~ 10000`，避免精确裁剪的性能开销 |
| 裁剪时机 | 每次写入时 | `XADD key MAXLEN ~ 10000 * field value` |

**设计理由**：Redis Streams 是传输层而非持久化层。10000 条的上限确保：
- 正常 Session（500-700 个事件）不会触发裁剪
- 异常 Session（事件暴增）不会导致 Redis 内存溢出
- 持久化消费者在 10000 条消息窗口内有充足时间消费

### 6.4 消息序列化格式

Redis Streams 中的消息采用扁平化的 field-value 格式（Redis Streams 原生限制，不支持嵌套结构）：

```
XADD reqradar:events:{session_id} *
  event_id "a1b2c3d4-..."
  session_id "e5f67890-..."
  sequence "15"
  event_type "STEP_COMPLETED"
  event_level "reasoning"
  timestamp "2026-06-01T10:01:30.123456Z"
  producer "cognitive-rt"
  payload '{"step":5,"phase":"ANALYSIS","duration_ms":1200,...}'
```

| 字段 | Redis 类型 | 说明 |
|------|-----------|------|
| `event_id` | string | UUID 字符串 |
| `session_id` | string | UUID 字符串 |
| `sequence` | string | 整数的字符串表示（Redis Streams field 值为 string） |
| `event_type` | string | EventType 枚举值 |
| `event_level` | string | EventLevel 枚举值 |
| `timestamp` | string | ISO 8601 格式 |
| `producer` | string | 产生者标识 |
| `payload` | string | JSON 序列化的 payload 对象 |

**序列化约束**：

| 约束 | 说明 |
|------|------|
| payload 单条上限 | 10KB（序列化后） |
| 超限处理 | payload 中大段内容使用引用（如 `result_ref: "l1://..."`），不内联 |
| 编码 | UTF-8 |
| 时间格式 | ISO 8601，含微秒，UTC 时区 |

### 6.5 消费确认机制

```python
async def consume_and_persist(redis: Redis, stream_key: str) -> None:
    messages = await redis.xreadgroup(
        groupname=CONSUMER_GROUP_NAME,
        consumername=f"index-svc-{INSTANCE_ID}",
        streams={stream_key: ">"},
        count=10,
        block=2000,
    )

    if not messages:
        return

    for stream_name, entries in messages:
        event_records = [deserialize_event(entry) for entry in entries]
        try:
            await batch_persist_events(event_records)
            ids = [entry[0] for entry in entries]
            await redis.xack(stream_name, CONSUMER_GROUP_NAME, *ids)
        except Exception as e:
            logger.error(f"持久化失败，不确认消费: {e}")
```

**确认规则**：

| 规则 | 说明 |
|------|------|
| 确认时机 | 事件成功持久化到 PostgreSQL 后才确认 |
| 批量确认 | 同一批次的事件批量确认，减少网络往返 |
| 失败不确认 | 持久化失败时，消息留在 Pending 列表，等待重新消费 |
| Pending 检查 | 每 60 秒扫描 Pending 列表，超过 5 分钟未确认的消息重新分配 |
| 重复消费防护 | 持久化时使用 `event_id` 作为幂等键，`INSERT ... ON CONFLICT DO NOTHING` |

### 6.6 Stream 清理任务

Session 进入终态后，其对应的 Redis Stream 不再产生新消息，需要定期清理以释放 Redis 内存。

**清理策略**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `stream_cleanup_after_hours` | 24 | Session 终态后延迟清理时间 |
| `stream_cleanup_batch_size` | 50 | 每次清理任务处理的 Stream 数量 |
| `stream_cleanup_interval_seconds` | 3600 | 清理任务执行间隔 |

**清理流程**：

```
1. index-service 定时任务（每小时执行一次）
2. 查询 PG cognitive_sessions 表中 status 为终态且 updated_at < now() - interval 'stream_cleanup_after_hours' 的 Session
3. 对每个待清理 Session：
   a. 调用 Redis XLEN 确认 Stream 存在
   b. 调用 Redis DEL 删除 Stream
   c. 调用 Redis DEL 删除对应的 Pub/Sub 频道（如有残留）
4. 记录清理日志（清理数量、释放内存估算）
```

**安全约束**：
- 清理前确认 Event 已持久化到 PG（通过 `events` 表的 `session_id` 记录数与 Stream 的 XLEN 对比校验）
- 清理失败不重试（下次定时任务会再次尝试）
- 清理操作仅删除 Redis 数据，不影响 PG 中的持久化 Event

---

## 7. Redis Pub/Sub 配置（WebSocket 广播）

### 7.1 频道命名

```
ws:session:{session_id}
```

| 规则 | 说明 |
|------|------|
| 前缀 | `ws:session:` |
| 后缀 | session_id（UUID 字符串，不含连字符） |
| 示例 | `ws:session:a1b2c3d4e5f67890a1b2c3d4e5f67890` |

### 7.2 发布/订阅流程

```
cognitive-rt 实例 A（事件产生者）
       │
       │  1. 产生 Event
       │  2. 写入 Redis Streams
       │  3. 发布到 Redis Pub/Sub
       │     PUBLISH ws:session:{sid} {serialized_event}
       │
       ├──► api-service 实例 1（订阅者）
       │    │  已订阅 ws:session:{sid}
       │    │  收到消息 → 推送给连接到本实例的 WebSocket 客户端
       │    │
       │    ├──► 前端客户端 A
       │    └──► 前端客户端 B
       │
       └──► api-service 实例 2（订阅者）
            │  已订阅 ws:session:{sid}
            │  收到消息 → 推送给连接到本实例的 WebSocket 客户端
            │
            └──► 前端客户端 C
```

**关键流程**：

| 步骤 | 执行者 | 操作 |
|------|--------|------|
| 1 | cognitive-rt | 产生 Event，写入 Redis Streams |
| 2 | cognitive-rt | 将 Event 序列化后发布到 `ws:session:{sid}` 频道 |
| 3 | api-service | 订阅 `ws:session:{sid}` 频道，接收消息 |
| 4 | api-service | 反序列化 Event，推送给连接到本实例的 WebSocket 客户端 |

### 7.3 多节点广播方案

**订阅管理**：

```python
class WebSocketSessionManager:
    def __init__(self, redis: Redis):
        self._redis = redis
        self._pubsub = redis.pubsub()
        self._sessions: dict[str, set[WebSocket]] = {}
        self._listener_task: asyncio.Task | None = None

    async def subscribe(self, session_id: str, ws: WebSocket) -> None:
        channel = f"ws:session:{session_id}"
        if session_id not in self._sessions:
            self._sessions[session_id] = set()
            await self._pubsub.subscribe(channel)
        self._sessions[session_id].add(ws)

    async def unsubscribe(self, session_id: str, ws: WebSocket) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].discard(ws)
            if not self._sessions[session_id]:
                del self._sessions[session_id]
                channel = f"ws:session:{session_id}"
                await self._pubsub.unsubscribe(channel)
```

**广播逻辑**：

```python
async def _listen_and_broadcast(self) -> None:
    async for message in self._pubsub.listen():
        if message["type"] != "message":
            continue

        channel = message["channel"]
        if isinstance(channel, bytes):
            channel = channel.decode()

        session_id = channel.removeprefix("ws:session:")
        event_data = message["data"]

        if session_id in self._sessions:
            dead_ws: list[WebSocket] = []
            for ws in self._sessions[session_id]:
                try:
                    await ws.send_text(event_data)
                except Exception:
                    dead_ws.append(ws)
            for ws in dead_ws:
                await self.unsubscribe(session_id, ws)
```

**多节点广播的关键特性**：

| 特性 | 说明 |
|------|------|
| 去中心化 | 无需中央协调器，Redis Pub/Sub 自动广播到所有订阅者 |
| 按需订阅 | api-service 仅订阅有前端客户端关注的 Session 频道 |
| 自动清理 | 最后一个 WebSocket 客户端断开后，自动取消订阅 |
| 跨节点 | 任意 cognitive-rt 实例发布的事件，所有 api-service 实例都能收到 |

### 7.4 连接断开处理

| 场景 | 处理方式 |
|------|---------|
| 前端 WebSocket 断开 | 从 SessionManager 中移除该 WebSocket；如果是该 Session 的最后一个客户端，取消订阅频道 |
| api-service 实例宕机 | Redis Pub/Sub 自动检测连接断开，其他实例不受影响；前端应实现自动重连 |
| cognitive-rt 实例宕机 | 事件不再产生，前端通过心跳超时检测到异常 |
| Redis 连接断开 | api-service 自动重连 Redis，重新订阅之前关注的频道；重连期间的事件从 PostgreSQL 补偿 |

**前端重连补偿机制**：

```
1. 前端检测到 WebSocket 断开
2. 前端记录最后收到的 sequence 号
3. 前端重新建立 WebSocket 连接
4. 前端发送 { type: "resync", last_sequence: N }
5. api-service 从 PostgreSQL 查询 sequence > N 的事件
6. api-service 通过 WebSocket 补发缺失的事件
7. 补发完成后，恢复正常实时推送
```

---

## 8. Event 持久化

### 8.1 PostgreSQL `events` 表结构

```sql
CREATE TABLE events (
    event_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES cognitive_sessions(session_id) ON DELETE CASCADE,
    sequence     INTEGER NOT NULL,
    event_type   VARCHAR(30) NOT NULL,
    event_level  VARCHAR(15) NOT NULL,
    timestamp    TIMESTAMPTZ NOT NULL,
    producer     VARCHAR(50) NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_events_session_sequence UNIQUE (session_id, sequence),
    CONSTRAINT ck_events_event_type CHECK (event_type IN (
        'SESSION_CREATED', 'SESSION_STARTED', 'SESSION_CHECKPOINTED',
        'SESSION_COMPLETED', 'SESSION_FAILED', 'SESSION_CANCELLING',
        'SESSION_CANCELLED', 'SESSION_TIMEOUT', 'SESSION_ABORTED',
        'SESSION_WAITING_INPUT', 'SESSION_RESUMED',
        'STEP_STARTED', 'STEP_COMPLETED',
        'TOOL_INVOKED', 'TOOL_RETURNED', 'TOOL_RETRY', 'TOOL_TIMEOUT',
        'TOOL_PERMISSION_DENIED', 'TOOL_CHECKPOINT_FAILED',
        'CONTEXT_COLLECTED', 'CONTEXT_SCORED',
        'EVIDENCE_ADDED', 'DIMENSION_CHANGED'
    )),
    CONSTRAINT ck_events_event_level CHECK (event_level IN ('session', 'reasoning', 'cognitive'))
);
```

**字段说明**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `event_id` | UUID | PK | 事件全局唯一标识 |
| `session_id` | UUID | FK, NOT NULL | 归属 Session |
| `sequence` | INTEGER | NOT NULL, UNIQUE(session_id, sequence) | 同一 Session 内严格递增的序号 |
| `event_type` | VARCHAR(30) | NOT NULL, CHECK | 事件类型枚举 |
| `event_level` | VARCHAR(15) | NOT NULL, CHECK | 事件级别枚举 |
| `timestamp` | TIMESTAMPTZ | NOT NULL | 事件产生时间 |
| `producer` | VARCHAR(50) | NOT NULL | 事件产生者标识 |
| `payload` | JSONB | NOT NULL, DEFAULT '{}' | 事件负载 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 持久化时间（与 timestamp 可能不同） |

### 8.2 索引策略

```sql
-- 按时间顺序回放推理链（最核心的查询模式）
CREATE INDEX idx_events_session_sequence ON events (session_id, sequence);

-- 按事件类型过滤查询
CREATE INDEX idx_events_session_type ON events (session_id, event_type);

-- 按事件级别过滤查询
CREATE INDEX idx_events_session_level ON events (session_id, event_level);

-- 按时间范围查询（Timeline 展示）
CREATE INDEX idx_events_session_timestamp ON events (session_id, timestamp);

-- JSONB 索引：按 payload 中的 step 查询（推理步骤关联）
CREATE INDEX idx_events_payload_step ON events
    ((payload->>'step')) WHERE payload ? 'step';

-- JSONB 索引：按 payload 中的 dimension 查询（维度关联）
CREATE INDEX idx_events_payload_dimension ON events
    ((payload->>'dimension')) WHERE payload ? 'dimension';
```

**索引设计说明**：

| 索引 | 用途 | 选择性 |
|------|------|--------|
| `idx_events_session_sequence` | 推理链回放、Trace 查询 | 高（session_id 区分度好） |
| `idx_events_session_type` | 按事件类型过滤 | 中 |
| `idx_events_session_level` | 按事件级别过滤 | 低（仅 3 个值） |
| `idx_events_session_timestamp` | Timeline 展示 | 高 |
| `idx_events_payload_step` | 按推理步骤关联查询 | 中（部分索引） |
| `idx_events_payload_dimension` | 按维度关联查询 | 中（部分索引） |

### 8.3 持久化策略

**方案：异步批量写入**

```python
class EventPersister:
    def __init__(self, db_session_factory: Callable, batch_size: int = 50, flush_interval: float = 1.0):
        self._db_session_factory = db_session_factory
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buffer: list[EventRecord] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

    async def append(self, event: EventRecord) -> None:
        async with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self._batch_size:
                await self._flush()

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            await self._batch_insert(batch)
        except Exception as e:
            logger.error(f"事件批量持久化失败: {e}")
            self._buffer.extend(batch)

    async def _batch_insert(self, events: list[EventRecord]) -> None:
        async with self._db_session_factory() as session:
            stmt = insert(EventModel).values(
                [e.model_dump() for e in events]
            ).on_conflict_do_nothing(
                constraint="uq_events_session_sequence"
            )
            await session.execute(stmt)
            await session.commit()
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 50 | 缓冲区达到此数量时触发写入 |
| `flush_interval` | 1.0s | 定时刷新间隔，确保低频事件也能及时持久化 |
| `on_conflict` | DO NOTHING | 基于 `uq_events_session_sequence` 唯一约束的幂等写入 |

**选择异步批量写入而非实时写入的理由**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 实时写入 | 事件产生即持久化，无丢失窗口 | 每个事件一次 DB 写入，高延迟场景下性能差 |
| **异步批量写入**（选定） | 减少 DB 写入次数，提高吞吐；批量 INSERT 效率高 | 存在短暂丢失窗口（最多 flush_interval 秒） |

**丢失窗口的补偿**：Redis Streams 中的消息在持久化确认前不会删除。如果 EventPersister 在 flush 前崩溃，Redis Streams 中的消息仍可被重新消费。

### 8.4 事件查询接口

```python
async def query_events(
    session_id: UUID,
    event_level: EventLevel | None = None,
    event_type: EventType | None = None,
    since_sequence: int | None = None,
    limit: int = 100,
) -> EventBatch:
    ...
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | 必填，查询的 Session |
| `event_level` | EventLevel \| None | 按级别过滤 |
| `event_type` | EventType \| None | 按类型过滤 |
| `since_sequence` | int \| None | 起始序列号（不包含），用于分页和断点续传 |
| `limit` | int | 返回条数上限（1-1000） |

---

## 9. Event 与 WebSocket 推送

### 9.1 api-service 订阅 Redis Pub/Sub 到前端推送的完整流程

```
1. 前端建立 WebSocket 连接
   ws://host/api/v2/sessions/{id}/ws?token=jwt_token

2. api-service 验证 JWT，校验用户对 Session 的访问权限

3. api-service 将 WebSocket 注册到 SessionManager
   SessionManager.subscribe(session_id, ws)

4. SessionManager 检查是否已有该 Session 的订阅
   ├── 已有 → 直接加入现有订阅集合
   └── 没有 → 订阅 Redis Pub/Sub 频道 ws:session:{session_id}

5. cognitive-rt 产生事件 → 发布到 Redis Pub/Sub

6. api-service 的 Pub/Sub listener 收到消息

7. SessionManager 将事件推送给所有关注该 Session 的 WebSocket 客户端
   推送前根据客户端的过滤偏好过滤事件级别

8. WebSocket 连接断开时
   SessionManager.unsubscribe(session_id, ws)
   如果是最后一个客户端 → 取消订阅 Redis Pub/Sub 频道
```

### 9.2 事件过滤

前端可在 WebSocket 连接时指定订阅的事件级别：

```json
{
  "type": "subscribe",
  "filters": {
    "levels": ["session", "reasoning"],
    "types": ["STEP_COMPLETED", "TOOL_INVOKED", "TOOL_RETURNED"]
  }
}
```

**过滤规则**：

| 过滤维度 | 说明 | 默认值 |
|---------|------|--------|
| `levels` | 订阅的事件级别列表 | 全部级别 |
| `types` | 订阅的事件类型列表 | 全部类型 |

**过滤实现**：

```python
class ClientSubscription:
    def __init__(self, ws: WebSocket, levels: set[EventLevel] | None = None, types: set[EventType] | None = None):
        self.ws = ws
        self.levels = levels
        self.types = types

    def should_receive(self, event: EventRecord) -> bool:
        if self.levels and event.event_level not in self.levels:
            return False
        if self.types and event.event_type not in self.types:
            return False
        return True
```

### 9.3 推送延迟目标

| 指标 | 目标 | 说明 |
|------|------|------|
| 事件产生到 Redis Pub/Sub 发布 | < 10ms | cognitive-rt 内部操作 |
| Redis Pub/Sub 到 api-service 接收 | < 10ms | Redis 内存操作 |
| api-service 到 WebSocket 客户端推送 | < 30ms | 网络传输 + 序列化 |
| **端到端延迟（事件产生到前端接收）** | **< 2s** | 含所有环节，单节点 < 50ms |
| 批量事件推送间隔 | < 100ms | 同一步骤产生的多个事件批量推送 |

---

## 10. Event 与推理链 Trace

### 10.1 通过 session_id + sequence 回放整个推理过程

推理链 Trace 是 Event Stream 最核心的使用场景之一。通过 `session_id + sequence` 可以精确回放 Agent 的完整推理过程。

**Trace 回放流程**：

```
1. 查询 Session 的全部事件（按 sequence 排序）
2. 按 event_level 分层展示：
   ├── Session 级事件 → 时间线骨架
   ├── Reasoning 级事件 → 推理步骤详情
   └── Cognitive 级事件 → 认知状态变更细节
3. 关联 TOOL_INVOKED / TOOL_RETURNED（通过 call_id 配对）
4. 关联 STEP_STARTED / STEP_COMPLETED（通过 step 配对）
5. 关联 EVIDENCE_ADDED / DIMENSION_CHANGED（通过 step 关联到推理步骤）
```

**Trace 数据结构**：

```python
class ReasoningTrace(BaseModel):
    session_id: UUID
    session_events: list[EventRecord]
    steps: list[ReasoningStep]

class ReasoningStep(BaseModel):
    step: int
    started_event: EventRecord
    completed_event: EventRecord | None
    tool_calls: list[ToolCallPair]
    evidence_added: list[EventRecord]
    dimension_changes: list[EventRecord]
    context_events: list[EventRecord]

class ToolCallPair(BaseModel):
    invoked_event: EventRecord
    returned_event: EventRecord | None
```

### 10.2 Trace 查询 API

**GET /api/v2/sessions/{id}/trace**

**查询参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `step_start` | int \| null | null | 起始步骤（包含） |
| `step_end` | int \| null | null | 结束步骤（包含） |
| `include_cognitive` | bool | true | 是否包含 Cognitive 级事件 |
| `include_context` | bool | false | 是否包含 Context Pipeline 事件 |

**响应**（200 OK）：

```json
{
  "session_id": "uuid",
  "session_events": [
    {
      "event_id": "uuid",
      "sequence": 1,
      "event_type": "SESSION_CREATED",
      "event_level": "session",
      "timestamp": "2026-06-01T10:00:00Z",
      "producer": "cognitive-rt",
      "payload": { ... }
    }
  ],
  "steps": [
    {
      "step": 1,
      "started_event": { ... },
      "completed_event": { ... },
      "tool_calls": [
        {
          "invoked_event": { ... },
          "returned_event": { ... }
        }
      ],
      "evidence_added": [ { ... } ],
      "dimension_changes": [ { ... } ],
      "context_events": [ { ... } ]
    }
  ]
}
```

### 10.3 Trace 在 Debug 和可解释性中的使用

| 场景 | 使用方式 | 关键事件 |
|------|---------|---------|
| 推理路径 Debug | 回放 Agent 的每一步思考，定位推理偏差 | STEP_STARTED, STEP_COMPLETED, thought_summary |
| 工具调用审计 | 检查工具调用参数和返回是否合理 | TOOL_INVOKED, TOOL_RETURNED |
| 证据链验证 | 验证每条证据的来源和推理过程 | EVIDENCE_ADDED, source_ref, depends_on |
| 维度评估解释 | 解释为什么某个维度被评定为特定风险等级 | DIMENSION_CHANGED, evidence_count |
| 上下文质量分析 | 分析 Context Pipeline 的选择是否合理 | CONTEXT_COLLECTED, CONTEXT_SCORED |
| 性能瓶颈定位 | 通过 duration_ms 定位耗时最长的步骤 | STEP_COMPLETED, TOOL_RETURNED |

---

## 11. 接口定义

### 11.1 EventPublisher 接口

```python
class EventPublisher(Protocol):
    async def publish(self, event: EventRecord) -> None:
        """发布事件到 Redis Streams 和 Redis Pub/Sub"""
        ...

    async def publish_batch(self, events: list[EventRecord]) -> None:
        """批量发布事件"""
        ...
```

**实现约束**：

| 约束 | 说明 |
|------|------|
| 双写 | 每个事件同时写入 Redis Streams 和 Redis Pub/Sub |
| 顺序保证 | 同一 Session 内的事件按 sequence 顺序写入 |
| 失败处理 | Redis Streams 写入失败时重试 3 次；Pub/Sub 写入失败仅记录日志（fire-and-forget） |
| sequence 生成 | 由 cognitive-rt 在内存中维护，每个 Session 一个原子计数器 |

### 11.2 EventConsumer 接口

```python
class EventConsumer(Protocol):
    async def consume(self, session_id: UUID, batch_size: int = 10) -> list[EventRecord]:
        """从 Redis Streams 消费事件"""
        ...

    async def ack(self, session_id: UUID, event_ids: list[str]) -> None:
        """确认事件已消费"""
        ...

    async def pending_check(self, session_id: UUID, min_idle_ms: int = 300000) -> list[PendingEvent]:
        """检查 Pending 列表中超时未确认的事件"""
        ...
```

```python
class PendingEvent(BaseModel):
    event_id: str
    session_id: UUID
    consumer_name: str
    idle_time_ms: int
    delivery_count: int
```

### 11.3 Event 查询 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/sessions/{id}/events` | GET | 查询 Session 事件流 |
| `/api/v2/sessions/{id}/trace` | GET | 查询推理链 Trace |
| `/api/v2/sessions/{id}/events/stats` | GET | 事件统计信息 |

**GET /api/v2/sessions/{id}/events**

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `level` | str \| null | null | 事件级别过滤（session / reasoning / cognitive） |
| `type` | str \| null | null | 事件类型过滤 |
| `since` | int \| null | null | 起始序列号（不包含） |
| `limit` | int | 100 | 返回条数上限（1-1000） |

**响应**（200 OK）：

```json
{
  "session_id": "uuid",
  "events": [
    {
      "event_id": "uuid",
      "sequence": 1,
      "event_type": "SESSION_STARTED",
      "event_level": "session",
      "timestamp": "2026-06-01T10:00:05Z",
      "producer": "cognitive-rt",
      "payload": { ... }
    }
  ],
  "total": 42,
  "has_more": true
}
```

**GET /api/v2/sessions/{id}/events/stats**

**响应**（200 OK）：

```json
{
  "session_id": "uuid",
  "total_events": 342,
  "by_level": {
    "session": 5,
    "reasoning": 128,
    "cognitive": 209
  },
  "by_type": {
    "SESSION_CREATED": 1,
    "SESSION_STARTED": 1,
    "STEP_STARTED": 50,
    "STEP_COMPLETED": 50,
    "TOOL_INVOKED": 28,
    "TOOL_RETURNED": 28,
    "EVIDENCE_ADDED": 85,
    "DIMENSION_CHANGED": 42,
    "CONTEXT_COLLECTED": 50,
    "CONTEXT_SCORED": 50,
    "SESSION_COMPLETED": 1
  },
  "time_range": {
    "first_event": "2026-06-01T10:00:00Z",
    "last_event": "2026-06-01T10:15:30Z"
  }
}
```

### 11.4 WebSocket 事件推送协议

**连接**：

```
ws://host/api/v2/sessions/{id}/ws?token=jwt_token
```

**服务端推送格式**：

```json
{
  "type": "event",
  "data": {
    "event_id": "uuid",
    "sequence": 15,
    "event_type": "STEP_COMPLETED",
    "event_level": "reasoning",
    "timestamp": "2026-06-01T10:01:30Z",
    "producer": "cognitive-rt",
    "payload": {
      "step": 5,
      "phase": "ANALYSIS",
      "duration_ms": 1200,
      "context_usage": 45000,
      "context_budget": 128000,
      "tool_calls_in_step": 1,
      "evidence_added_in_step": 2,
      "thought_summary": "需要检查支付模块的并发安全性...",
      "next_action": "tool_call"
    }
  }
}
```

**客户端消息**：

| 消息类型 | 格式 | 说明 |
|---------|------|------|
| 订阅过滤 | `{"type": "subscribe", "filters": {"levels": [...], "types": [...]}}` | 设置事件过滤偏好 |
| 断点续传 | `{"type": "resync", "last_sequence": N}` | 请求补发 sequence > N 的事件 |
| 心跳回复 | `{"type": "pong"}` | 回复服务端心跳 |
| Chatback | `{"type": "chatback", "data": {"message": "..."}}` | 用户追问 |

**服务端控制消息**：

| 消息类型 | 格式 | 说明 |
|---------|------|------|
| 心跳 | `{"type": "ping"}` | 每 30s 发送，60s 无回复断开 |
| Session 终态通知 | `{"type": "session_ended", "data": {"status": "COMPLETED"}}` | Session 进入终态后 30s 关闭连接 |
| 补发完成 | `{"type": "resync_complete", "data": {"events_sent": 5}}` | 断点续传补发完成 |

---

## 12. 错误处理

### 12.1 Redis 不可用

| 场景 | 影响 | 处理方式 |
|------|------|---------|
| Redis Streams 写入失败 | 事件无法传输到消费者 | 重试 3 次（指数退避：1s, 2s, 4s）；仍失败则写入本地降级队列 |
| Redis Pub/Sub 发布失败 | 前端无法实时收到事件 | 仅记录日志，不影响推理循环；前端通过轮询 API 补偿 |
| Redis 完全不可用 | Streams + Pub/Sub 均不可用 | cognitive-rt 降级为本地事件缓冲模式，事件暂存内存队列；Redis 恢复后批量补发 |
| Redis 重连后 | 需要恢复消费 | 消费者组自动从上次确认的位置继续；Pub/Sub 重新订阅 |

**本地降级队列**：

```python
class FallbackEventQueue:
    def __init__(self, max_size: int = 10000):
        self._queue: deque[EventRecord] = deque(maxlen=max_size)
        self._redis_available: bool = True

    async def publish(self, event: EventRecord, publisher: EventPublisher) -> None:
        if self._redis_available:
            try:
                await publisher.publish(event)
                return
            except RedisError:
                self._redis_available = False
                logger.warning("Redis 不可用，事件进入本地降级队列")
        self._queue.append(event)

    async def drain(self, publisher: EventPublisher) -> int:
        count = 0
        while self._queue:
            event = self._queue.popleft()
            try:
                await publisher.publish(event)
                count += 1
            except RedisError:
                self._queue.appendleft(event)
                break
        if count > 0:
            self._redis_available = True
        return count
```

### 12.2 持久化失败

| 场景 | 影响 | 处理方式 |
|------|------|---------|
| 单批次写入失败 | 事件未持久化到 PG | 不确认 Redis Streams 消费，等待重新消费 |
| 连续写入失败 | 事件积压在 Redis Streams | 触发告警；Redis Streams 的 MAXLEN 确保不会无限积压 |
| PostgreSQL 完全不可用 | 无法持久化 | index-service 进入降级模式，事件保留在 Redis Streams 中；PG 恢复后从 Pending 列表重新消费 |
| 重复事件 | 幂等键冲突 | `ON CONFLICT DO NOTHING`，静默忽略 |

**持久化失败的告警阈值**：

| 指标 | 阈值 | 告警级别 |
|------|------|---------|
| 连续写入失败次数 | >= 5 | WARNING |
| Pending 列表积压消息数 | >= 1000 | WARNING |
| Pending 列表最老消息空闲时间 | >= 10 分钟 | CRITICAL |
| 本地降级队列大小 | >= 5000 | WARNING |

### 12.3 WebSocket 断连

| 场景 | 处理方式 |
|------|---------|
| 客户端网络抖动 | 客户端自动重连 + resync 补发 |
| api-service 实例重启 | 客户端重连到其他实例；Redis Pub/Sub 重新订阅 |
| 心跳超时 | 服务端主动断开，客户端重连 |
| Session 终态后连接未关闭 | 服务端在 Session 终态后 30s 主动关闭连接 |

---

## 13. 配置参数

### 13.1 Event 相关配置

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `event.stream_maxlen` | int | 10000 | 1000-100000 | Redis Streams 每个 Stream 的最大消息数 |
| `event.consumer_group` | str | "event-persisters" | - | 消费者组名称 |
| `event.consumer_batch_size` | int | 10 | 1-100 | 单次消费批量大小 |
| `event.consumer_block_ms` | int | 2000 | 100-10000 | 消费者阻塞等待时间（毫秒） |
| `event.persist_batch_size` | int | 50 | 10-500 | 持久化批量写入大小 |
| `event.persist_flush_interval` | float | 1.0 | 0.1-10.0 | 持久化定时刷新间隔（秒） |
| `event.pending_check_interval` | int | 60 | 10-300 | Pending 列表检查间隔（秒） |
| `event.pending_idle_threshold` | int | 300000 | 60000-1800000 | Pending 消息空闲超时（毫秒，默认 5 分钟） |
| `event.payload_max_size_bytes` | int | 10240 | 1024-102400 | 单个事件 payload 最大字节数 |
| `event.fallback_queue_max_size` | int | 10000 | 1000-100000 | 本地降级队列最大容量 |
| `event.pubsub_enabled` | bool | True | - | 是否启用 Redis Pub/Sub 广播 |
| `event.ws_heartbeat_interval` | int | 30 | 5-120 | WebSocket 心跳间隔（秒） |
| `event.ws_heartbeat_timeout` | int | 60 | 10-300 | WebSocket 心跳超时（秒） |
| `event.ws_session_close_delay` | int | 30 | 5-120 | Session 终态后 WS 连接关闭延迟（秒） |
| `event.stream_cleanup_after_hours` | int | 24 | 1-168 | Session 终态后 Redis Stream 清理时间（小时） |

### 13.2 配置矩阵映射

Event 相关配置在 Scope × Domain 矩阵中的位置：

| | RUNTIME Domain |
|--|---------------|
| **SYSTEM** | `event.stream_maxlen`, `event.persist_batch_size` 等全局默认值 |
| **PROJECT** | 项目级事件过滤偏好 |
| **USER** | 用户级 WebSocket 推送偏好 |
| **SESSION** | 不适用（Event 配置不按 Session 覆盖） |

---

## 14. 与其他模块的关系

| 模块 | 文档 | 交互方式 | 说明 |
|------|------|---------|------|
| CognitiveSession | R-01 | Session 产生 Session 级事件；推理循环产生 Reasoning/Cognitive 级事件 | 所有事件以 `session_id` 为归属；Session 状态转换与 Session 级事件一一对应 |
| Context Pipeline | R-02 | Pipeline 产生 CONTEXT_COLLECTED / CONTEXT_SCORED 事件 | Context Pipeline 的 Collect 和 Score 阶段是 Cognitive 级事件的主要来源 |
| ToolRuntime | R-04 | ToolRuntime 产生 TOOL_INVOKED / TOOL_RETURNED 事件 | 工具调用的生命周期通过事件对（call_id 配对）完整记录 |
| Checkpoint | R-05 | Checkpoint 写入成功产生 SESSION_CHECKPOINTED 事件 | Checkpoint 是 Session 级事件的触发源之一 |
| Evidence Model | M-01 | Evidence 聚合产生 EVIDENCE_ADDED 事件 | 证据的 source_ref 和 depends_on 通过事件 payload 传递 |
| 7-Dimension Framework | M-02 | 维度评估状态变更产生 DIMENSION_CHANGED 事件 | 维度的风险等级变化通过事件实时通知前端 |
| Project Cognitive State | M-03 | L3 沉淀从 Event Trace 中提取可沉淀知识 | Event Stream 是 L2→L3 认知飞轮的数据来源 |
| index-service | I-01 | index-service 消费 Redis Streams 持久化事件到 PG | 服务间异步通信 |
| api-service | I-01 | api-service 订阅 Redis Pub/Sub 推送 WebSocket | 服务间异步通信 |

**依赖方向**：

```
R-03 (Event Stream Schema)
  ├── 依赖 R-01 (Session Lifecycle) 的事件触发时机定义
  ├── 依赖 R-02 (Context Pipeline) 的 CONTEXT_* 事件 payload 定义
  ├── 依赖 R-04 (ToolRuntime) 的 TOOL_* 事件 payload 定义
  ├── 依赖 R-05 (Checkpoint) 的 SESSION_CHECKPOINTED 事件 payload 定义
  ├── 依赖 M-01 (Evidence) 的 EVIDENCE_ADDED 事件 payload 定义
  ├── 依赖 M-02 (7-Dimension) 的 DIMENSION_CHANGED 事件 payload 定义
  └── 被 I-01 (服务间 API 契约)、M-03 (L3 Sediment) 依赖
```

---

## 15. 测试策略

### 15.1 单元测试

| 测试类别 | 覆盖内容 | 数量估计 |
|---------|---------|---------|
| EventRecord 模型 | Pydantic 模型的校验、序列化、默认值 | 15+ |
| EventType / EventLevel 枚举 | 枚举值完整性、映射关系 | 10+ |
| Payload Schema | 各事件类型的 payload 校验（必填、类型、范围） | 30+ |
| 序列化/反序列化 | Event → Redis Stream field-value → Event 的往返 | 10+ |
| 事件过滤 | ClientSubscription 的级别/类型过滤逻辑 | 10+ |
| SessionManager | 订阅/取消订阅/广播逻辑 | 15+ |

### 15.2 集成测试

| 测试类别 | 覆盖内容 | 关键断言 |
|---------|---------|---------|
| 事件发布到 Redis Streams | EventPublisher 发布后 Stream 中有对应消息 | XREAD 返回正确数据 |
| 消费者组消费 | EventConsumer 消费后 PG 中有对应记录 | PG 查询返回正确事件 |
| 消费确认 | 持久化成功后 XACK 被调用 | XPENDING 无未确认消息 |
| 批量持久化 | 多个事件批量写入 PG | 所有事件按 sequence 排序正确 |
| 幂等写入 | 重复消费同一消息 | PG 中只有一条记录 |
| Pub/Sub 广播 | 发布到频道后所有订阅者收到 | api-service 收到消息 |
| WebSocket 推送 | 前端 WebSocket 收到事件 | 事件格式正确，sequence 连续 |

### 15.3 端到端测试

| 测试场景 | 操作 | 预期结果 |
|---------|------|---------|
| 完整事件流 | 创建 Session → 启动 → 推理 → 完成 | PG 中有完整的 13 种事件类型 |
| 推理链 Trace | 查询 Trace API | 步骤、工具调用、证据、维度变更正确关联 |
| WebSocket 实时推送 | 前端订阅 Session 事件 | 端到端延迟 < 2s |
| 事件过滤 | 前端只订阅 reasoning 级 | 只收到 STEP_*/TOOL_* 事件 |
| 断点续传 | WebSocket 断开后重连 | 补发缺失的事件 |
| Redis 不可用降级 | 模拟 Redis 宕机 | 事件进入本地降级队列，推理不中断 |
| 持久化失败恢复 | 模拟 PG 写入失败 | 事件留在 Pending 列表，PG 恢复后重新消费 |

### 15.4 性能测试

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| 事件发布吞吐 | >= 1000 events/s | 单 cognitive-rt 实例持续发布 |
| 事件消费吞吐 | >= 500 events/s | 单 index-service 实例持续消费并持久化 |
| 批量持久化延迟 | < 50ms（50 条批量） | 测量 _batch_insert 耗时 |
| WebSocket 推送延迟 | < 50ms（单节点） | 从事件产生到前端接收 |
| 端到端延迟 | < 2s | 含 Redis + PG + WS 全链路 |
| Trace 查询延迟 | < 500ms（500 条事件） | 查询完整推理链 |
| Redis Stream 内存 | < 10MB / Session | 10000 条消息上限下的内存占用 |

---

## 16. 明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| 完整事件驱动架构 | 不做 | 当前仅用于推理链记录和实时推送，不引入 CQRS / Event Sourcing |
| Kafka / 外部 MQ | 不做 | Redis Streams 满足当前需求；Kafka 引入运维复杂度，ADR-013 明确选择 Redis Streams |
| 事件回放驱动状态重建 | 不做 | 状态重建由 Checkpoint 负责，Event Stream 不承担状态重建职责 |
| 跨 Session 事件聚合 | 不做 | 事件以 Session 为边界，跨 Session 聚合由 L3 沉淀负责 |
| 事件 Schema 版本化 | Phase 1 不做 | 当前 Schema 稳定，新增字段不破坏旧消费者；版本化在多服务独立部署后再引入 |
| 事件压缩 | 不做 | 单个 payload 限制 10KB，总体存储量可控；压缩增加复杂度 |
| 事件订阅的持久化 | 不做 | WebSocket 订阅是临时的，不持久化到数据库；重连后通过 resync 补偿 |
| 事件到消息队列的桥接 | 不做 | 不将 Event Stream 桥接到外部消息队列（如 Kafka、RabbitMQ） |
| 事件的细粒度权限控制 | 不做 | 事件权限跟随 Session 权限，不单独控制事件级别的访问 |
