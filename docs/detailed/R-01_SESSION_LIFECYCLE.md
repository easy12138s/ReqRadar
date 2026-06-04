# R-01 CognitiveSession 生命周期详细设计

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | CognitiveSession 生命周期的详细设计规格，为 P3（Cognitive Runtime Core）的实现提供精确蓝图 |
| 前置文档 | 01_RESTRUCTURE_OVERVIEW.md（第五章 CognitiveSession、第九章演进路线）、02_SYSTEM_ARCHITECTURE.md（4.1 CognitiveSession）、03_COGNITIVE_ASSET_MODEL.md（5.2 L2 CognitiveSession）、04_IMPLEMENTATION_ROADMAP.md（P3 启动前置条件） |
| 核心目标 | 定义 CognitiveSession 的完整状态机、数据模型、生命周期流程、子系统交互、恢复机制与 API 契约 |
| 文档职责 | What & How — Session 是什么、状态如何流转、数据如何持久化、失败如何恢复、API 如何暴露 |

---

## 2. 概述

CognitiveSession 是 ReqRadar V2 Runtime 的**一等运行时实体**。它不是一条数据库记录，而是以下五个子系统的聚合载体：

| 角色 | 说明 | 关键持有物 |
|------|------|-----------|
| **Runtime Scheduler** | 控制 Session 生命周期状态转换 | `status`、`status_history` |
| **Context State Container** | 持有当前推理步骤的全部上下文 | `context_budget`、`context_usage`、`context_strategy` |
| **Event Host** | 所有推理事件以 session_id 为归属 | 事件流引用 |
| **Checkpoint Owner** | 管理 Checkpoint 版本链 | `checkpoint_chain`、`last_checkpoint_version` |
| **Cognitive State Carrier** | 会话结束时沉淀认知到 L3 | `evidence_summary`、`dimension_summary` |

**设计原则**：

- Session 是状态机的唯一宿主，所有状态转换必须经过 Session 的 `transition()` 方法
- Session 不持有推理逻辑，只持有推理状态；推理逻辑由 Agent 执行，Session 被动接收状态变更
- Session 的生命周期由 cognitive-rt 全权管理，其他服务通过 API 或 Event 观察但不直接修改

---

## 3. Session 状态机

### 3.1 状态枚举

```python
class SessionStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    CHECKPOINTING = "CHECKPOINTING"
    WAITING_INPUT = "WAITING_INPUT"
    CANCELLING = "CANCELLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    ABORTED = "ABORTED"
```

| 状态 | 含义 | 是否终态 | 可转换至 |
|------|------|---------|---------|
| CREATED | Session 已创建，等待配置校验和资源准备 | 否 | READY, FAILED |
| READY | 配置校验通过，资源就绪，等待启动 | 否 | RUNNING, CANCELLED |
| RUNNING | 推理循环执行中 | 否 | CHECKPOINTING, WAITING_INPUT, CANCELLING, COMPLETED, FAILED, TIMEOUT, ABORTED |
| CHECKPOINTING | 正在写入 Checkpoint 快照 | 否 | RUNNING, CANCELLING, FAILED, ABORTED |
| WAITING_INPUT | 等待用户输入（Chatback 场景） | 否 | RUNNING, CANCELLING |
| CANCELLING | 收到取消请求，正在执行清理 | 否 | CANCELLED, TIMEOUT, ABORTED |
| COMPLETED | 分析完成，L3 沉淀已触发 | 是 | - |
| FAILED | 可恢复错误导致失败 | 是 | - |
| CANCELLED | 用户主动取消，正常终止 | 是 | - |
| TIMEOUT | 超过最大执行时间 | 是 | - |
| ABORTED | 不可恢复错误导致异常中止 | 是 | - |

### 3.2 状态转换图

```
                          ┌──────────┐
                          │ CREATED  │
                          └────┬─────┘
                               │ 配置校验通过
                               ▼
                          ┌──────────┐
                    ┌─────│  READY   │─────┐
                    │     └────┬─────┘     │
                    │          │ 启动       │ 用户取消
                    │          ▼           │
                    │     ┌──────────┐     │
                    │     │ RUNNING  │─────┤
                    │     └──┬──┬──┬─┘     │
                    │        │  │  │       │
          ┌─────────┘        │  │  │       │
          │ Chatback         │  │  │       │
          │ 暂停             │  │  │       │
          ▼                  │  │  │       │
     ┌──────────────┐        │  │  │       │
     │WAITING_INPUT │───────►│  │  │       │
     └──────┬───────┘ 恢复   │  │  │       │
            │               │  │  │       │
            │ 用户取消       │  │  │       │
            ▼               │  │  │       │
     ┌──────────────┐       │  │  │       │
     │ CANCELLING   │◄──────┘  │  │       │
     └──┬───┬───┬───┘          │  │       │
        │   │   │              │  │       │
        │   │   │              │  │       │
        ▼   ▼   ▼              ▼  ▼       │
   ┌────┐ ┌────┐ ┌────┐  ┌────┐ ┌────┐   │
   │CAN │ │TIM │ │ABO │  │COM │ │FAI │   │
   │CEL │ │EOUT│ │RT  │  │PLE │ │LED │   │
   │LED │ │    │ │    │  │TED │ │    │   │
   └────┘ └────┘ └────┘  └────┘ └────┘   │
                                           │
                                    ┌──────┘
                                    ▼
                              ┌──────────┐
                              │CANCELLED │
                              └──────────┘

  详细转换（RUNNING 周期性快照）:

     RUNNING ──周期触发──► CHECKPOINTING ──完成──► RUNNING
                                    │
                                    │ 取消请求
                                    ▼
                              CANCELLING
```

### 3.3 状态转换规则

每条转换定义：触发条件 → 前置校验 → 副作用 → 后置不变量

| # | 源状态 | 目标状态 | 触发条件 | 前置校验 | 副作用 | 后置不变量 |
|---|--------|---------|---------|---------|--------|-----------|
| T1 | CREATED | READY | 配置校验完成 | `project_id` 有效；`context_budget > 0`；`strategy` 已注册 | 发布 `SESSION_CREATED` 事件；初始化 `context_usage = 0` | `status = READY`；`context_usage = 0` |
| T2 | CREATED | FAILED | 配置校验失败 | 校验错误信息非空 | 发布 `SESSION_FAILED` 事件；记录 `error_message` | `status = FAILED`；`error_message` 非空 |
| T3 | READY | RUNNING | 用户调用 start API | `status = READY`；`project_id` 对应的 L1 索引可用 | 发布 `SESSION_STARTED` 事件；初始化 Context Pipeline；启动推理循环 | `status = RUNNING`；`started_at` 已设置 |
| T4 | READY | CANCELLED | 用户取消 | `status = READY` | 发布 `SESSION_CANCELLED` 事件 | `status = CANCELLED`；`finished_at` 已设置 |
| T5 | RUNNING | CHECKPOINTING | 周期性触发 / 手动触发 | `status = RUNNING`；当前步骤已完成 | 暂停推理循环；开始写入 Checkpoint | `status = CHECKPOINTING` |
| T6 | CHECKPOINTING | RUNNING | Checkpoint 写入成功 | Checkpoint 版本号递增 | 发布 `CHECKPOINT_CREATED` 事件；恢复推理循环 | `status = RUNNING`；`last_checkpoint_version` 递增 |
| T7 | RUNNING | WAITING_INPUT | Agent 请求用户输入 | `status = RUNNING`；Chatback 问题非空 | 发布 `SESSION_WAITING_INPUT` 事件；暂停推理循环 | `status = WAITING_INPUT`；`pending_question` 非空 |
| T8 | WAITING_INPUT | RUNNING | 用户提供输入 | `status = WAITING_INPUT`；用户输入非空 | 发布 `SESSION_RESUMED` 事件；将用户输入注入 Context Pipeline；恢复推理循环 | `status = RUNNING`；`pending_question = None` |
| T9 | WAITING_INPUT | CANCELLING | 用户取消 | `status = WAITING_INPUT` | 发布 `SESSION_CANCELLING` 事件 | `status = CANCELLING` |
| T10 | RUNNING | CANCELLING | 用户取消 | `status = RUNNING` | 发布 `SESSION_CANCELLING` 事件；标记推理循环需停止 | `status = CANCELLING` |
| T11 | RUNNING | COMPLETED | 推理循环正常结束 | 所有维度评估完成；Evidence 链完整 | 发布 `SESSION_COMPLETED` 事件；触发 L3 沉淀；生成报告 | `status = COMPLETED`；`finished_at` 已设置；`dimension_summary` 非空 |
| T12 | RUNNING | FAILED | 可恢复错误 | 错误信息非空 | 发布 `SESSION_FAILED` 事件；记录 `error_message`；保留已有 Checkpoint | `status = FAILED`；`error_message` 非空；`finished_at` 已设置 |
| T13 | RUNNING | TIMEOUT | 超过 `max_execution_time` | `now - started_at > max_execution_time` | 发布 `SESSION_TIMEOUT` 事件；强制停止推理循环 | `status = TIMEOUT`；`finished_at` 已设置 |
| T14 | RUNNING | ABORTED | 不可恢复错误 | 错误信息非空；错误类型为 `FatalError` 或 `LLMException` 且不可重试 | 发布 `SESSION_ABORTED` 事件；记录 `error_message`；不触发 L3 沉淀 | `status = ABORTED`；`error_message` 非空；`finished_at` 已设置 |
| T15 | CHECKPOINTING | CANCELLING | 用户取消 | `status = CHECKPOINTING` | 发布 `SESSION_CANCELLING` 事件；中断 Checkpoint 写入 | `status = CANCELLING` |
| T16 | CHECKPOINTING | FAILED | Checkpoint 写入失败且不可重试 | 写入错误信息非空 | 发布 `SESSION_FAILED` 事件；记录 `error_message` | `status = FAILED`；`error_message` 非空 |
| T17 | CHECKPOINTING | ABORTED | Checkpoint 写入期间存储服务不可用 | 存储服务健康检查失败 | 发布 `SESSION_ABORTED` 事件；记录 `error_message` | `status = ABORTED`；`error_message` 非空 |
| T18 | CANCELLING | CANCELLED | 清理完成 | 推理循环已停止；资源已释放 | 发布 `SESSION_CANCELLED` 事件；释放 Context Pipeline 资源 | `status = CANCELLED`；`finished_at` 已设置 |
| T19 | CANCELLING | TIMEOUT | 取消过程中超过最大执行时间 | `now - started_at > max_execution_time` | 发布 `SESSION_TIMEOUT` 事件；强制终止 | `status = TIMEOUT`；`finished_at` 已设置 |
| T20 | CANCELLING | ABORTED | 取消过程中遇到不可恢复错误 | 错误信息非空 | 发布 `SESSION_ABORTED` 事件；记录 `error_message` | `status = ABORTED`；`error_message` 非空 |

### 3.4 状态转换幂等性

状态转换必须具备幂等性，确保在重试场景下不会产生异常：

| 场景 | 行为 | 说明 |
|------|------|------|
| 当前状态已是目标状态 | 直接返回成功，不产生副作用 | 如 Session 已是 RUNNING，再次调用 `transition(RUNNING)` 直接成功 |
| 当前状态不在转换的源状态中 | 抛出 `InvalidTransitionError` | 如 Session 是 COMPLETED，调用 `transition(RUNNING)` 抛异常 |
| 转换过程中并发调用 | 乐观锁 + 版本号保证只有一个成功 | 失败方获取最新状态后判断是否需要重试 |

**实现约束**：
- `transition()` 方法内部首先检查 `current_status == target_status`，若相等则直接返回
- 状态转换的副作用（发布事件、更新时间戳等）仅在首次转换时执行
- 重试同一转换不产生重复事件

### 3.5 CANCELLING 分支逻辑

CANCELLING 状态是取消流程的中间态，确保推理循环优雅退出：

```
用户调用 cancel API
       │
       ▼
  ┌──────────────┐
  │  CANCELLING   │  标记 cancel_requested = True
  └──────┬───────┘
         │
         ├── 推理循环检测到 cancel_requested
         │   ├── 当前步骤完成 → 释放资源 → CANCELLED
         │   └── 当前步骤超时 → 强制中断 → CANCELLED
         │
         ├── 清理过程超过 max_execution_time → TIMEOUT
         │
         └── 清理过程遇到不可恢复错误（如存储损坏）→ ABORTED
```

**CANCELLING 的超时阈值**：取 `min(max_execution_time - elapsed_time, cancellation_timeout)`，其中 `cancellation_timeout` 默认 60 秒。若剩余执行时间不足，以剩余时间为准。

**CANCELLING 期间的行为约束**：
- 不启动新的推理步骤
- 不发起新的工具调用
- 正在执行的工具调用等待其完成或超时
- 正在写入的 Checkpoint 等待其完成或中断
- 已写入的 Checkpoint 和 Event 不回滚

---

## 4. Session 数据模型

### 4.1 CognitiveSession Pydantic 模型

```python
class CognitiveSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    project_id: UUID
    user_id: UUID
    status: SessionStatus = SessionStatus.CREATED

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    config: SessionConfig
    state: SessionState

    error_message: str | None = None
    error_type: str | None = None

    last_checkpoint_version: int = 0
    total_reasoning_steps: int = 0
    total_tool_calls: int = 0

    status_history: list[StatusTransition] = Field(default_factory=list)
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `session_id` | UUID | PK，自动生成 | 全局唯一标识 |
| `project_id` | UUID | FK → projects，非空 | 关联项目 |
| `user_id` | UUID | FK → users，非空 | 创建者 |
| `status` | SessionStatus | 非空，默认 CREATED | 当前状态 |
| `created_at` | datetime | 非空，自动设置 | 创建时间 |
| `updated_at` | datetime | 非空，自动更新 | 最后更新时间 |
| `started_at` | datetime \| None | RUNNING 时非空 | 启动时间 |
| `finished_at` | datetime \| None | 终态时非空 | 结束时间 |
| `config` | SessionConfig | 非空 | 会话配置 |
| `state` | SessionState | 非空 | 运行时状态 |
| `error_message` | str \| None | 终态 FAILED/ABORTED 时非空 | 错误描述 |
| `error_type` | str \| None | 终态 FAILED/ABORTED 时非空 | 错误类型（异常类名） |
| `last_checkpoint_version` | int | >= 0 | 最新 Checkpoint 版本号 |
| `total_reasoning_steps` | int | >= 0 | 已完成推理步骤数 |
| `total_tool_calls` | int | >= 0 | 已完成工具调用数 |
| `status_history` | list[StatusTransition] | 追加不可改 | 状态转换历史 |

### 4.2 SessionConfig 数据模型

```python
class SessionConfig(BaseModel):
    context_budget: int = Field(default=128000, gt=0, description="Token 预算上限")
    context_strategy: str = Field(default="risk_analysis", description="Context Pipeline 策略名")
    max_execution_time: int = Field(default=1800, gt=0, description="最大执行时间（秒）")
    checkpoint_interval: int = Field(default=300, gt=0, description="自动 Checkpoint 间隔（秒）")
    checkpoint_enabled: bool = Field(default=True, description="是否启用自动 Checkpoint")
    max_reasoning_steps: int = Field(default=50, gt=0, le=200, description="最大推理步骤数")
    max_tool_calls: int = Field(default=100, gt=0, le=500, description="最大工具调用数")
    tools: list[str] = Field(default_factory=lambda: ["search_code", "get_deps", "read_file", "get_git_history"], description="允许使用的工具列表")
    llm_model: str | None = Field(default=None, description="覆盖默认 LLM 模型")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM 温度")
    output_format: str = Field(default="markdown", description="输出格式")
    template_id: UUID | None = Field(default=None, description="报告模板 ID")
```

| 字段 | 类型 | 默认值 | 约束 | 说明 |
|------|------|--------|------|------|
| `context_budget` | int | 128000 | > 0 | Token 预算上限 |
| `context_strategy` | str | "risk_analysis" | 非空，已注册策略 | Context Pipeline 策略名 |
| `max_execution_time` | int | 1800 | > 0 | 最大执行时间（秒），超时进入 TIMEOUT |
| `checkpoint_interval` | int | 300 | > 0 | 自动 Checkpoint 间隔（秒） |
| `checkpoint_enabled` | bool | True | - | 是否启用自动 Checkpoint |
| `max_reasoning_steps` | int | 50 | 1-200 | 最大推理步骤数 |
| `max_tool_calls` | int | 100 | 1-500 | 最大工具调用数 |
| `tools` | list[str] | 默认 4 个工具 | 非空 | 允许使用的工具列表 |
| `llm_model` | str \| None | None | - | 覆盖默认 LLM 模型，None 使用项目/系统默认 |
| `llm_temperature` | float | 0.1 | 0.0-2.0 | LLM 温度参数 |
| `output_format` | str | "markdown" | 非空 | 输出格式 |
| `template_id` | UUID \| None | None | - | 报告模板 ID，None 使用默认模板 |

### 4.3 SessionState 数据模型

```python
class SessionState(BaseModel):
    context_usage: int = Field(default=0, ge=0, description="当前已用 Token 数")
    current_step: int = Field(default=0, ge=0, description="当前推理步骤序号")
    current_phase: str = Field(default="INIT", description="当前推理阶段")
    pending_question: str | None = Field(default=None, description="等待用户回答的问题")
    cancel_requested: bool = Field(default=False, description="是否收到取消请求")
    evidence_count: int = Field(default=0, ge=0, description="已收集的证据数")
    dimensions_completed: list[str] = Field(default_factory=list, description="已完成的维度")
    dimensions_pending: list[str] = Field(default_factory=list, description="待分析的维度")
    active_tools: list[str] = Field(default_factory=list, description="当前活跃的工具")
```

| 字段 | 类型 | 默认值 | 约束 | 说明 |
|------|------|--------|------|------|
| `context_usage` | int | 0 | >= 0 | 当前已用 Token 数 |
| `current_step` | int | 0 | >= 0 | 当前推理步骤序号 |
| `current_phase` | str | "INIT" | 非空 | 当前推理阶段（INIT / ANALYSIS / EVIDENCE_AGG / DIMENSION_EVAL / REPORT_GEN） |
| `pending_question` | str \| None | None | - | WAITING_INPUT 时非空 |
| `cancel_requested` | bool | False | - | 取消请求标记 |
| `evidence_count` | int | 0 | >= 0 | 已收集的证据数 |
| `dimensions_completed` | list[str] | [] | - | 已完成的维度列表 |
| `dimensions_pending` | list[str] | [] | - | 待分析的维度列表 |
| `active_tools` | list[str] | [] | - | 当前活跃的工具列表 |

### 4.4 辅助模型

```python
class StatusTransition(BaseModel):
    from_status: SessionStatus
    to_status: SessionStatus
    timestamp: datetime
    trigger: str
    reason: str | None = None

class SessionSummary(BaseModel):
    session_id: UUID
    project_id: UUID
    status: SessionStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_reasoning_steps: int
    total_tool_calls: int
    evidence_count: int
    last_checkpoint_version: int
    context_usage: int
    context_budget: int
```

---

## 5. Session 生命周期流程

### 5.1 创建：POST /api/v2/sessions → CREATED → READY

```
客户端                    cognitive-rt                    index-service
  │                          │                               │
  │  POST /api/v2/sessions   │                               │
  │  {project_id, config}    │                               │
  │ ────────────────────────►│                               │
  │                          │                               │
  │                          │  1. 校验 project_id 有效性     │
  │                          │  2. 校验 config 合法性         │
  │                          │  3. 校验 L1 索引可用性         │
  │                          │  4. 创建 CognitiveSession      │
  │                          │     status = CREATED           │
  │                          │  5. 执行 T1: CREATED → READY   │
  │                          │  6. 发布 SESSION_CREATED 事件  │
  │                          │  7. 持久化 Session 到 PG       │
  │                          │                               │
  │  201 {session_id, ...}   │                               │
  │ ◄────────────────────────│                               │
```

**校验规则**：

| 校验项 | 条件 | 失败处理 |
|--------|------|---------|
| project_id 存在 | 查询 projects 表 | 返回 404 |
| L1 索引可用 | 查询 chunks 表是否有该项目的记录 | 返回 409，提示先执行索引 |
| context_budget 合法 | > 0 且 <= 模型最大上下文 | 返回 422 |
| tools 列合法 | 每个工具名已注册 | 返回 422 |
| context_strategy 合法 | 策略名已注册 | 返回 422 |

**创建时的默认值填充**：
- `config` 中未指定的字段使用 Scope × Domain 配置矩阵解析后的默认值
- 解析优先级：请求体 > SESSION scope > USER scope > PROJECT scope > SYSTEM scope

### 5.2 启动：READY → RUNNING

```
客户端                    cognitive-rt                    index-service
  │                          │                               │
  │  POST .../sessions/{id}/start                            │
  │ ────────────────────────►│                               │
  │                          │                               │
  │                          │  1. 校验 status = READY        │
  │                          │  2. 执行 T3: READY → RUNNING   │
  │                          │  3. 设置 started_at            │
  │                          │  4. 初始化 Context Pipeline    │
  │                          │     Collect: 从 L1 拉取上下文   │
  │                          │  5. 启动推理循环（async task）  │
  │                          │  6. 发布 SESSION_STARTED 事件  │
  │                          │                               │
  │  200 {status: "RUNNING"} │                               │
  │ ◄────────────────────────│                               │
```

**Context Pipeline 初始化**：
- Collect 阶段从 L1 拉取项目上下文（代码模块、需求 chunk、Git 历史）
- 如果项目有 L3 知识（P5 之后），Collect 阶段同时注入 L3 active + confidence >= 0.6 的知识
- Score → Select → Compress → Assemble 按 `context_strategy` 执行
- 组装后的上下文 Token 数必须 <= `context_budget`

**推理循环启动**：
- 使用 `asyncio.create_task()` 启动，不阻塞 API 响应
- 推理循环内部维护 `cancel_requested` 标志，每步开始前检查

### 5.3 执行：RUNNING 期间的推理循环

```
┌─────────────────────────────────────────────────────────┐
│                    推理循环（RUNNING）                     │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│  │ 检查取消  │───►│ 检查超时  │───►│ 检查步骤  │           │
│  │ 请求     │    │          │    │ 上限     │           │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘           │
│       │               │               │                  │
│  cancel_requested  elapsed > max   step > max_steps      │
│  = True           _exec_time                          │
│       │               │               │                  │
│       ▼               ▼               ▼                  │
│  CANCELLING       TIMEOUT         COMPLETED              │
│                                                          │
│  ┌──────────────────────────────────────────┐            │
│  │          单步推理流程                      │            │
│  │                                           │            │
│  │  1. Context Pipeline 组装当前步骤上下文    │            │
│  │  2. LLM 推理（Thought）                   │            │
│  │  3. 发布 ThoughtGenerated 事件            │            │
│  │  4. 判断是否需要工具调用                   │            │
│  │     ├── 需要 → ToolRuntime.execute()      │            │
│  │     │   发布 TOOL_INVOKED / TOOL_RETURNED │            │
│  │     └── 不需要 → 直接进入 Observation     │            │
│  │  5. 接收 Observation                      │            │
│  │  6. Evidence 聚合（如适用）                │            │
│  │     发布 EvidenceAdded 事件               │            │
│  │  7. Dimension 状态更新（如适用）           │            │
│  │     发布 DimensionChanged 事件            │            │
│  │  8. 更新 SessionState                     │            │
│  │     current_step += 1                     │            │
│  │     context_usage = pipeline.current_usage│            │
│  │  9. 检查是否需要 Checkpoint               │            │
│  │     周期性触发 → 进入 CHECKPOINTING       │            │
│  │  10. 检查是否需要用户输入                  │            │
│  │     Chatback 场景 → 进入 WAITING_INPUT    │            │
│  │  11. 检查是否所有维度完成                  │            │
│  │     全部完成 → 进入 COMPLETED             │            │
│  └──────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

### 5.4 Checkpointing：RUNNING → CHECKPOINTING → RUNNING

```
cognitive-rt                              index-service
     │                                         │
     │  触发条件（满足任一）：                    │
     │  - 距上次 Checkpoint 超过 interval       │
     │  - 关键推理步骤完成（Evidence 聚合后）    │
     │  - 用户手动触发                          │
     │                                         │
     │  1. 执行 T5: RUNNING → CHECKPOINTING     │
     │  2. 收集当前状态快照：                    │
     │     - AgentState（current_step, phase）  │
     │     - EvidenceState（evidence_count）    │
     │     - DimensionState（completed/pending）│
     │     - ContextState（usage, strategy）    │
     │  3. 热状态写入 PG JSONB                  │
     │  4. 冷状态写入 MinIO                     │
     │     ──── POST /checkpoints ──────────────►│
     │                                         │  5. 事务写入：
     │                                         │     a. INSERT checkpoints
     │                                         │     b. INSERT checkpoint_events
     │                                         │     （同一 PG 事务）
     │  ◄──── 200 {version, checkpoint_id} ─────│
     │                                         │
     │  6. 执行 T6: CHECKPOINTING → RUNNING     │
     │  7. 发布 CHECKPOINT_CREATED 事件         │
     │  8. last_checkpoint_version += 1         │
     │  9. 恢复推理循环                         │
```

**Checkpoint 事务保证**（来自 04 文档 P3 前置条件）：

| 保证 | 说明 | 实现方式 |
|------|------|---------|
| **写入原子性** | Checkpoint 写入 PG JSONB + 关联 Event 必须在同一事务 | PG 事务：`BEGIN → INSERT checkpoint → INSERT event → COMMIT` |
| **恢复时校验** | 恢复时校验 Evidence 链完整性，不通过则拒绝恢复 | 恢复流程中执行 `validate_evidence_chain()`，失败则回退到上一个一致点 |
| **失败安全** | Checkpoint 写入失败时，Session 不应继续推进 | 写入失败 → 根据配置决定：ABORTED（严格模式）或降级（宽松模式） |
| **可降级** | Checkpoint 写入失败时，自动切换为"无 Checkpoint 模式"继续执行 | `checkpoint_enabled` 动态设为 False，发布 `CHECKPOINT_DEGRADED` 事件，Session 继续执行 |

**降级策略详细规则**：

```python
async def handle_checkpoint_failure(session: CognitiveSession, error: Exception) -> None:
    if session.config.checkpoint_enabled:
        retry_count = 0
        max_retries = 2
        while retry_count < max_retries:
            retry_count += 1
            success = await retry_checkpoint_write(session)
            if success:
                return
        # 重试耗尽，降级
        session.config.checkpoint_enabled = False
        session.transition(SessionStatus.RUNNING, trigger="checkpoint_degraded")
        publish_event(CHECKPOINT_DEGRADED, session_id=session.session_id, reason=str(error))
    else:
        # 已在降级模式，Checkpoint 仍然失败 → 不影响运行
        pass
```

### 5.5 Chatback 暂停：RUNNING → WAITING_INPUT → RUNNING

```
cognitive-rt                              前端（WebSocket）
     │                                         │
     │  Agent 判断需要用户输入                   │
     │  1. 执行 T7: RUNNING → WAITING_INPUT     │
     │  2. 设置 pending_question                │
     │  3. 创建 Chatback Checkpoint             │
     │     （确保对话前状态可回滚）               │
     │  4. 发布 SESSION_WAITING_INPUT 事件       │
     │  5. 推送 Chatback 问题 ──────────────────►│
     │                                         │
     │                                         │  用户输入回答
     │  ◄────────────────────────── 用户输入 ───│
     │                                         │
     │  6. 执行 T8: WAITING_INPUT → RUNNING     │
     │  7. 将用户输入注入 Context Pipeline       │
     │  8. 清空 pending_question                │
     │  9. 发布 SESSION_RESUMED 事件            │
     │  10. 恢复推理循环                        │
```

**Chatback Checkpoint 的特殊性**：
- WAITING_INPUT 进入时必须创建一次 Checkpoint，确保用户回答后如果需要回滚，可以回到对话前的状态
- 该 Checkpoint 的 `type` 标记为 `CHATBACK_SNAPSHOT`
- 用户回答后的推理如果发现方向错误，可通过回滚到此 Checkpoint 重新开始

### 5.6 取消：RUNNING/CHECKPOINTING → CANCELLING → CANCELLED

```
客户端                    cognitive-rt
  │                          │
  │  POST .../sessions/{id}/cancel
  │ ────────────────────────►│
  │                          │
  │                          │  1. 校验 status ∈ {RUNNING, CHECKPOINTING, WAITING_INPUT}
  │                          │  2. 执行 T10/T15/T9 → CANCELLING
  │                          │  3. 设置 cancel_requested = True
  │                          │  4. 发布 SESSION_CANCELLING 事件
  │                          │
  │  202 {status: "CANCELLING"}
  │ ◄────────────────────────│
  │                          │
  │                     ┌────┤ 推理循环检测到 cancel_requested
  │                     │    │
  │                     │    │  5. 等待当前步骤完成或超时
  │                     │    │  6. 释放 Context Pipeline 资源
  │                     │    │  7. 执行 T18: CANCELLING → CANCELLED
  │                     │    │  8. 设置 finished_at
  │                     │    │  9. 发布 SESSION_CANCELLED 事件
  │                     │    │
  │  GET .../sessions/{id}   │
  │ ────────────────────────►│
  │  200 {status: "CANCELLED"}
  │ ◄────────────────────────│
```

**取消期间的保护措施**：
- 已写入的 Checkpoint 和 Event 不回滚，保留审计链
- 正在执行的工具调用等待其完成（最多等待 `cancellation_timeout` 秒）
- 不触发 L3 沉淀（未完成的分析不应污染长期知识）

### 5.7 超时：RUNNING → TIMEOUT

```
cognitive-rt 内部定时器
     │
     │  每个推理步骤开始前检查：
     │  if now - started_at > max_execution_time:
     │
     │  1. 执行 T13: RUNNING → TIMEOUT
     │  2. 强制停止推理循环
     │  3. 设置 finished_at
     │  4. 发布 SESSION_TIMEOUT 事件
     │  5. 尝试写入最终 Checkpoint（非阻塞，失败不影响状态）
     │  6. 不触发 L3 沉淀
```

**超时检查的时机**：
- 每个推理步骤开始前
- 每次从 WAITING_INPUT 恢复时
- CANCELLING 状态的清理过程中

**超时后的数据保留**：
- 已有的 Checkpoint 和 Event 保留
- 已收集的 Evidence 保留，但标记为 `incomplete`
- 用户可基于已有 Checkpoint 创建新 Session 继续分析

### 5.8 异常中止：RUNNING → ABORTED

```
cognitive-rt 推理循环
     │
     │  不可恢复错误发生：
     │  - LLM 服务持续不可用（重试耗尽）
     │  - 存储服务不可用（Checkpoint 写入失败 + 降级也失败）
     │  - 数据损坏（Evidence 链校验失败）
     │  - OOM / 系统级错误
     │
     │  1. 捕获异常，判断是否可恢复
     │  2. 不可恢复 → 执行 T14: RUNNING → ABORTED
     │  3. 记录 error_message 和 error_type
     │  4. 设置 finished_at
     │  5. 发布 SESSION_ABORTED 事件
     │  6. 不触发 L3 沉淀
     │  7. 保留已有 Checkpoint 和 Event
```

**可恢复 vs 不可恢复的判断**：

| 错误类型 | 可恢复 | 处理方式 |
|---------|--------|---------|
| LLM 单次调用超时 | 是 | 重试（ToolRuntime 管控） |
| LLM 连续 3 次调用失败 | 否 | → ABORTED |
| 工具调用超时 | 是 | 重试或跳过 |
| 工具调用参数错误 | 是 | Agent 自行修正 |
| Checkpoint 写入失败 | 是 | 降级为无 Checkpoint 模式 |
| Checkpoint 降级后存储完全不可用 | 否 | → ABORTED |
| Evidence 链校验失败 | 否 | → ABORTED |
| 内存溢出 / 系统级错误 | 否 | → ABORTED |

### 5.9 完成：RUNNING → COMPLETED

```
cognitive-rt                              index-service         output-service
     │                                         │                     │
     │  所有维度评估完成                         │                     │
     │  1. 执行 T11: RUNNING → COMPLETED        │                     │
     │  2. 设置 finished_at                     │                     │
     │  3. 写入最终 Checkpoint                   │                     │
     │     ──── POST /checkpoints ──────────────►│                     │
     │  4. 发布 SESSION_COMPLETED 事件           │                     │
     │  5. 触发 L3 沉淀（异步）                  │                     │
     │     ──── POST /l3/sediment ──────────────►│                     │
     │  6. 触发报告生成（异步）                   │                     │
     │     ──── POST /reports/generate ──────────────────────────────►│
     │                                         │                     │
     │  7. 更新 dimension_summary               │                     │
     │  8. 更新 evidence_summary                │                     │
```

**完成时的后置条件**：
- `dimension_summary` 包含所有 7 个维度的评估结果
- `evidence_summary` 包含证据总数、各类型分布
- 最终 Checkpoint 的 `type` 标记为 `SESSION_COMPLETE`
- L3 沉淀和报告生成异步执行，不阻塞 Session 状态转换

---

## 6. Session 与子系统的交互

### 6.1 Session 与 Context Pipeline

```
┌──────────────────────────────────────────────────────┐
│  CognitiveSession                                     │
│                                                       │
│  config.context_budget ──────► Context Pipeline       │
│  config.context_strategy ────►   │                    │
│  state.context_usage ◄───────────┤                    │
│  state.current_phase ────────►   │                    │
│                                  │                    │
│                                  ▼                    │
│                          Collect → Score → Select     │
│                          → Compress → Assemble        │
│                                                       │
│  Session 不持有 Pipeline 实例，                         │
│  而是通过 session_id 关联。                             │
│  Pipeline 的生命周期与 Session 的 RUNNING 状态对齐。    │
└──────────────────────────────────────────────────────┘
```

| 交互点 | 方向 | 说明 |
|--------|------|------|
| `context_budget` | Session → Pipeline | Token 预算上限，Pipeline 必须遵守 |
| `context_strategy` | Session → Pipeline | 策略名，决定 Score/Select/Compress 的算法选择 |
| `current_phase` | Session → Pipeline | 推理阶段，不同阶段使用不同的上下文源组合 |
| `context_usage` | Pipeline → Session | 当前已用 Token 数，每步推理后更新 |
| `quality_gate_result` | Pipeline → Session | Quality Gate 检查结果，不满足时进入 LOW_CONTEXT_CONFIDENCE 模式 |

**Context Budget 约束**：
- `context_usage` 必须 <= `context_budget` 的 105%（允许 5% 溢出用于元数据标记）
- 超过 105% 时，Pipeline 强制执行 Compress，直到满足预算
- `context_budget` 的值来自 Scope × Domain 配置矩阵的 SESSION scope

### 6.2 Session 与 Event Stream

```
┌──────────────────────────────────────────────────────┐
│  CognitiveSession                                     │
│                                                       │
│  Session 级事件（Session 自身产生）：                   │
│    SESSION_CREATED / STARTED / COMPLETED / FAILED     │
│    CANCELLED / TIMEOUT / ABORTED                      │
│    CHECKPOINTED / WAITING_INPUT / RESUMED             │
│                                                       │
│  推理级事件（Agent 推理循环产生，以 session_id 归属）： │
│    ThoughtGenerated / ToolInvoked / ToolReturned      │
│    StepCompleted                                      │
│                                                       │
│  认知级事件（Evidence/Dimension 变更产生）：            │
│    EvidenceAdded / DimensionChanged                   │
│    MemoryInjected / RiskDetected                      │
│                                                       │
│  所有事件携带 session_id，                              │
│  可通过 GET /sessions/{id}/events 查询完整事件链。     │
└──────────────────────────────────────────────────────┘
```

| 事件类别 | 产生时机 | 传输方式 |
|---------|---------|---------|
| Session 级 | 状态转换时 | Redis Streams + WebSocket |
| 推理级 | 每个推理步骤 | Redis Streams + WebSocket |
| 认知级 | Evidence/Dimension 变更 | Redis Streams + WebSocket |

**Session 事件与状态转换的对应关系**：

| 状态转换 | 产生的 Session 级事件 |
|---------|---------------------|
| CREATED → READY | SESSION_CREATED |
| READY → RUNNING | SESSION_STARTED |
| RUNNING → CHECKPOINTING | （无，CHECKPOINTING 是内部状态） |
| CHECKPOINTING → RUNNING | CHECKPOINT_CREATED |
| RUNNING → WAITING_INPUT | SESSION_WAITING_INPUT |
| WAITING_INPUT → RUNNING | SESSION_RESUMED |
| → CANCELLING | SESSION_CANCELLING |
| CANCELLING → CANCELLED | SESSION_CANCELLED |
| → COMPLETED | SESSION_COMPLETED |
| → FAILED | SESSION_FAILED |
| → TIMEOUT | SESSION_TIMEOUT |
| → ABORTED | SESSION_ABORTED |

### 6.3 Session 与 Checkpoint

```
┌──────────────────────────────────────────────────────┐
│  CognitiveSession                                     │
│                                                       │
│  last_checkpoint_version: 42                          │
│                                                       │
│  checkpoint_chain:                                    │
│    v1 ──► v2 ──► ... ──► v42                         │
│    │       │              │                           │
│    STEP    STEP    CHATBACK_SNAPSHOT                  │
│    _COMPLETE       / SESSION_COMPLETE                 │
│                                                       │
│  Session 拥有 checkpoint_chain，                       │
│  cognitive-rt 负责创建，                               │
│  index-service 负责持久化存储和恢复。                   │
└──────────────────────────────────────────────────────┘
```

| 交互点 | 方向 | 说明 |
|--------|------|------|
| `last_checkpoint_version` | Session ← Checkpoint | 最新版本号，用于恢复时定位 |
| `checkpoint_interval` | Session → Checkpoint | 自动触发间隔 |
| `checkpoint_enabled` | Session → Checkpoint | 是否启用，可动态降级 |
| Checkpoint 创建请求 | Session → index-service | 写入热状态 + 冷状态 |
| Checkpoint 恢复请求 | Session → index-service | 读取热状态 → 重建 SessionState |

**Checkpoint 类型**：

| 类型 | 触发条件 | 说明 |
|------|---------|------|
| `STEP_COMPLETE` | 周期性自动触发 | 常规推理步骤快照 |
| `CHATBACK_SNAPSHOT` | 进入 WAITING_INPUT 前 | 确保对话前状态可回滚 |
| `SESSION_COMPLETE` | 进入 COMPLETED 前 | 最终完整快照 |
| `MANUAL` | 用户手动触发 | 用户主动请求的快照 |

### 6.4 Session 与 ToolRuntime

```
┌──────────────────────────────────────────────────────┐
│  CognitiveSession                                     │
│                                                       │
│  config.tools ────────► ToolRuntime 权限校验           │
│  state.active_tools ◄── ToolRuntime 执行状态          │
│  state.total_tool_calls ──► 工具调用计数              │
│  config.max_tool_calls ──► 工具调用上限检查            │
│                                                       │
│  Session 控制工具执行权限：                             │
│  - 只有 config.tools 中的工具可被调用                  │
│  - 工具调用计数不超过 max_tool_calls                   │
│  - CANCELLING 状态下不启动新的工具调用                 │
└──────────────────────────────────────────────────────┘
```

| 交互点 | 方向 | 说明 |
|--------|------|------|
| `config.tools` | Session → ToolRuntime | 允许使用的工具白名单 |
| `config.max_tool_calls` | Session → ToolRuntime | 工具调用上限 |
| `state.active_tools` | ToolRuntime → Session | 当前正在执行的工具列表 |
| `state.total_tool_calls` | ToolRuntime → Session | 已完成的工具调用计数 |
| `cancel_requested` | Session → ToolRuntime | 取消标志，ToolRuntime 检查后不再启动新调用 |

---

## 7. Session 恢复机制

### 7.1 从 Checkpoint 恢复的完整流程

```
客户端                    cognitive-rt                    index-service
  │                          │                               │
  │  POST .../sessions/{id}/start                            │
  │  {resume_from: version}  │                               │
  │ ────────────────────────►│                               │
  │                          │                               │
  │                          │  1. 查询 Session，确认可恢复   │
  │                          │     status ∈ {FAILED, TIMEOUT}│
  │                          │     且有可用 Checkpoint        │
  │                          │                               │
  │                          │  GET /checkpoints/{sid}?v=N   │
  │                          │ ─────────────────────────────►│
  │                          │                               │
  │                          │  ◄── 200 {checkpoint_data} ───│
  │                          │                               │
  │                          │  2. 校验 Checkpoint 完整性     │
  │                          │  3. 校验 Evidence 链完整性     │
  │                          │  4. 重建 SessionState          │
  │                          │  5. 重建 Context Pipeline      │
  │                          │  6. 执行 T3: READY → RUNNING   │
  │                          │  7. 从 checkpoint.step+1 继续  │
  │                          │  8. 发布 SESSION_RESUMED 事件  │
  │                          │                               │
  │  200 {status: "RUNNING"} │                               │
  │ ◄────────────────────────│                               │
```

**恢复的详细步骤**：

| 步骤 | 操作 | 失败处理 |
|------|------|---------|
| 1. 定位 Checkpoint | 根据 `resume_from` 参数或 `last_checkpoint_version` | 无可用 Checkpoint → 返回 409 |
| 2. 读取热状态 | 从 PG JSONB 读取 AgentState/EvidenceState/DimensionState | 读取失败 → 尝试上一个版本 |
| 3. 读取冷状态 | 从 MinIO 读取完整 Context Snapshot（按需） | 读取失败 → 降级为无冷状态恢复 |
| 4. 校验 Evidence 链 | 验证每条 Evidence 的 source 引用有效、confidence > 0 | 校验失败 → 回退到上一个一致点 |
| 5. 重建 SessionState | 从 Checkpoint 数据恢复 `context_usage`、`current_step` 等 | - |
| 6. 重建 Context Pipeline | 使用 Checkpoint 中的 ContextState 重新初始化 Pipeline | 初始化失败 → 从 L1 重新 Collect |
| 7. 恢复推理循环 | 从 `current_step + 1` 继续执行 | - |

### 7.2 恢复时的状态校验

**Evidence 链完整性校验**：

```python
async def validate_evidence_chain(
    session_id: UUID,
    checkpoint_version: int,
) -> ValidationResult:
    evidences = await fetch_evidences(session_id, up_to_step=checkpoint_version)

    for ev in evidences:
        # 校验 1：source 引用有效
        if not await validate_source_reference(ev.source_ref):
            return ValidationResult(valid=False, reason=f"Evidence {ev.id} source_ref invalid")

        # 校验 2：confidence 在合理范围
        if ev.confidence <= 0 or ev.confidence > 1.0:
            return ValidationResult(valid=False, reason=f"Evidence {ev.id} confidence out of range")

        # 校验 3：依赖的 Evidence 存在
        for dep_id in ev.depends_on:
            if not await evidence_exists(dep_id):
                return ValidationResult(valid=False, reason=f"Evidence {ev.id} depends on missing {dep_id}")

    return ValidationResult(valid=True)
```

**校验失败的处理**：

| 校验失败类型 | 处理方式 |
|-------------|---------|
| source_ref 无效 | 尝试回退到上一个 Checkpoint 版本 |
| confidence 异常 | 标记该 Evidence 为 `suspicious`，继续恢复但降低其权重 |
| 依赖 Evidence 缺失 | 回退到上一个一致点（该 Evidence 存在的最近版本） |
| 全部校验失败 | 返回错误，建议用户从更早的 Checkpoint 恢复或重新创建 Session |

### 7.3 恢复失败的处理

| 恢复失败场景 | 处理策略 |
|-------------|---------|
| 指定版本的 Checkpoint 不存在 | 自动尝试 `last_checkpoint_version - 1`，最多回退 3 个版本 |
| 所有 Checkpoint 版本都不可用 | 返回 409，建议重新创建 Session |
| 热状态读取失败 | 尝试从冷状态重建（MinIO 中的完整快照） |
| 冷状态也读取失败 | 返回 500，记录详细错误日志 |
| Evidence 链校验失败 | 回退到上一个一致点 |
| Context Pipeline 重建失败 | 从 L1 重新 Collect，可能丢失部分上下文 |
| LLM 服务不可用 | 恢复成功但 Session 立即进入 FAILED（可再次恢复） |

**恢复的幂等性保证**：
- 同一 Checkpoint 版本多次恢复的结果必须一致
- 恢复操作产生新的 Session 级事件（`SESSION_RESUMED`），但不产生新的 Checkpoint
- 恢复后的 `current_step` 从 Checkpoint 记录的步骤继续，不会重复执行已完成的步骤

---

## 8. Session API 设计

### 8.1 POST /api/v2/sessions（创建）

**请求**：

```json
{
  "project_id": "uuid",
  "config": {
    "context_budget": 128000,
    "context_strategy": "risk_analysis",
    "max_execution_time": 1800,
    "checkpoint_interval": 300,
    "tools": ["search_code", "get_deps", "read_file"],
    "llm_model": null,
    "template_id": null
  }
}
```

**响应**（201 Created）：

```json
{
  "session_id": "uuid",
  "project_id": "uuid",
  "status": "READY",
  "created_at": "2026-06-01T10:00:00Z",
  "config": { ... },
  "state": {
    "context_usage": 0,
    "current_step": 0,
    "current_phase": "INIT"
  }
}
```

**错误响应**：

| 状态码 | 条件 |
|--------|------|
| 404 | project_id 不存在 |
| 409 | 项目 L1 索引不可用 |
| 422 | config 校验失败 |

### 8.2 POST /api/v2/sessions/{id}/start（启动）

**请求**：

```json
{
  "resume_from": null
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `resume_from` | int \| null | Checkpoint 版本号，null 表示从头开始 |

**响应**（200 OK）：

```json
{
  "session_id": "uuid",
  "status": "RUNNING",
  "started_at": "2026-06-01T10:00:05Z",
  "state": {
    "context_usage": 0,
    "current_step": 0,
    "current_phase": "INIT"
  }
}
```

**错误响应**：

| 状态码 | 条件 |
|--------|------|
| 409 | status 不是 READY（已在运行或已完成） |
| 409 | resume_from 版本不存在 |
| 409 | 恢复校验失败 |

### 8.3 GET /api/v2/sessions/{id}（查询状态）

**响应**（200 OK）：

```json
{
  "session_id": "uuid",
  "project_id": "uuid",
  "status": "RUNNING",
  "created_at": "2026-06-01T10:00:00Z",
  "started_at": "2026-06-01T10:00:05Z",
  "finished_at": null,
  "config": { ... },
  "state": {
    "context_usage": 45000,
    "current_step": 12,
    "current_phase": "ANALYSIS",
    "evidence_count": 8,
    "dimensions_completed": ["completeness", "consistency"],
    "dimensions_pending": ["feasibility", "traceability", "ambiguity", "risk", "architecture"]
  },
  "last_checkpoint_version": 3,
  "total_reasoning_steps": 12,
  "total_tool_calls": 15,
  "error_message": null
}
```

### 8.4 POST /api/v2/sessions/{id}/cancel（取消）

**请求**：无请求体

**响应**（202 Accepted）：

```json
{
  "session_id": "uuid",
  "status": "CANCELLING",
  "message": "Cancellation requested, waiting for current step to complete"
}
```

**错误响应**：

| 状态码 | 条件 |
|--------|------|
| 409 | status 是终态（COMPLETED/FAILED/CANCELLED/TIMEOUT/ABORTED） |
| 409 | status 已经是 CANCELLING |

### 8.5 POST /api/v2/sessions/{id}/checkpoint（手动触发 Checkpoint）

**请求**：无请求体

**响应**（200 OK）：

```json
{
  "checkpoint_id": "uuid",
  "version": 4,
  "session_id": "uuid",
  "type": "MANUAL",
  "created_at": "2026-06-01T10:05:00Z"
}
```

**错误响应**：

| 状态码 | 条件 |
|--------|------|
| 409 | status 不是 RUNNING |
| 409 | Checkpoint 已禁用（降级模式） |

### 8.6 GET /api/v2/sessions/{id}/events（查询事件流）

**查询参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str \| null | null | 事件类型过滤（session/reasoning/cognitive） |
| `since` | int \| null | null | 起始序列号 |
| `limit` | int | 100 | 返回条数上限（1-1000） |

**响应**（200 OK）：

```json
{
  "session_id": "uuid",
  "events": [
    {
      "event_id": "uuid",
      "sequence": 1,
      "type": "SESSION_STARTED",
      "level": "session",
      "timestamp": "2026-06-01T10:00:05Z",
      "payload": { ... }
    }
  ],
  "total": 42,
  "has_more": true
}
```

### 8.7 WebSocket /api/v2/sessions/{id}/ws（实时事件推送）

**连接协议**：

```
客户端连接：ws://host/api/v2/sessions/{id}/ws?token=jwt_token

服务端推送格式：
{
  "type": "event",
  "data": {
    "event_id": "uuid",
    "sequence": 15,
    "type": "ThoughtGenerated",
    "level": "reasoning",
    "timestamp": "2026-06-01T10:01:30Z",
    "payload": {
      "step": 5,
      "thought": "需要检查支付模块的并发安全性...",
      "next_action": "tool_call"
    }
  }
}

客户端可发送消息：
{
  "type": "chatback",
  "data": {
    "message": "请重点关注支付模块的并发问题"
  }
}

心跳：
  服务端每 30s 发送 {"type": "ping"}
  客户端需回复 {"type": "pong"}
  超过 60s 无回复则断开连接
```

**WebSocket 生命周期**：
- Session 进入终态后，WebSocket 保持 30 秒后自动关闭
- 客户端断开后可重连，重连后从最后收到的 sequence + 1 续传
- 多节点部署时，通过 Redis Pub/Sub 跨节点转发事件

---

## 9. 存储设计

### 9.1 PostgreSQL `cognitive_sessions` 表结构

```sql
CREATE TABLE cognitive_sessions (
    session_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status           VARCHAR(20) NOT NULL DEFAULT 'CREATED',
    config           JSONB NOT NULL,
    state            JSONB NOT NULL DEFAULT '{}',
    error_message    TEXT,
    error_type       VARCHAR(100),
    last_checkpoint_version INTEGER NOT NULL DEFAULT 0,
    total_reasoning_steps   INTEGER NOT NULL DEFAULT 0,
    total_tool_calls        INTEGER NOT NULL DEFAULT 0,
    status_history   JSONB NOT NULL DEFAULT '[]',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ
);
```

**字段说明**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `session_id` | UUID | PK | 全局唯一标识 |
| `project_id` | UUID | FK, NOT NULL | 关联项目 |
| `user_id` | UUID | FK, NOT NULL | 创建者 |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'CREATED' | 当前状态，枚举值见 3.1 |
| `config` | JSONB | NOT NULL | SessionConfig 序列化 |
| `state` | JSONB | NOT NULL, DEFAULT '{}' | SessionState 序列化 |
| `error_message` | TEXT | NULLABLE | 错误描述 |
| `error_type` | VARCHAR(100) | NULLABLE | 错误类型（异常类名） |
| `last_checkpoint_version` | INTEGER | NOT NULL, DEFAULT 0 | 最新 Checkpoint 版本号 |
| `total_reasoning_steps` | INTEGER | NOT NULL, DEFAULT 0 | 已完成推理步骤数 |
| `total_tool_calls` | INTEGER | NOT NULL, DEFAULT 0 | 已完成工具调用数 |
| `status_history` | JSONB | NOT NULL, DEFAULT '[]' | 状态转换历史 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 最后更新时间 |
| `started_at` | TIMESTAMPTZ | NULLABLE | 启动时间 |
| `finished_at` | TIMESTAMPTZ | NULLABLE | 结束时间 |

### 9.2 索引策略

```sql
-- 按项目查询 Session 列表（最频繁的查询）
CREATE INDEX idx_sessions_project_id ON cognitive_sessions (project_id, created_at DESC);

-- 按用户查询 Session 列表
CREATE INDEX idx_sessions_user_id ON cognitive_sessions (user_id, created_at DESC);

-- 按状态查询活跃 Session（cognitive-rt 重启后恢复用）
CREATE INDEX idx_sessions_status ON cognitive_sessions (status)
    WHERE status IN ('RUNNING', 'CHECKPOINTING', 'WAITING_INPUT', 'CANCELLING');

-- 按状态查询可恢复 Session
CREATE INDEX idx_sessions_recoverable ON cognitive_sessions (status, last_checkpoint_version)
    WHERE status IN ('FAILED', 'TIMEOUT') AND last_checkpoint_version > 0;

-- updated_at 用于清理过期 Session
CREATE INDEX idx_sessions_updated_at ON cognitive_sessions (updated_at);

-- JSONB 索引：按 config 中的 context_strategy 查询
CREATE INDEX idx_sessions_config_strategy ON cognitive_sessions
    ((config->>'context_strategy'));

-- JSONB 索引：按 state 中的 current_phase 查询
CREATE INDEX idx_sessions_state_phase ON cognitive_sessions
    ((state->>'current_phase'));
```

**索引设计说明**：

| 索引 | 用途 | 选择性 |
|------|------|--------|
| `idx_sessions_project_id` | 项目详情页展示分析历史 | 高（project_id 区分度好） |
| `idx_sessions_user_id` | 用户 Dashboard 展示最近分析 | 高 |
| `idx_sessions_status` | cognitive-rt 重启后扫描活跃 Session | 低（部分索引，仅覆盖活跃状态） |
| `idx_sessions_recoverable` | 查找可恢复的 Session | 低（部分索引） |
| `idx_sessions_updated_at` | 定期清理过期 Session | 中 |
| `idx_sessions_config_strategy` | 按策略统计 Session | 低 |
| `idx_sessions_state_phase` | 按推理阶段统计 Session | 低 |

---

## 10. 错误处理

### 10.1 状态转换非法

当请求的状态转换不满足前置校验时，返回 409 Conflict：

```python
class IllegalTransitionError(ReqRadarException):
    def __init__(self, session_id: UUID, from_status: SessionStatus, to_status: SessionStatus):
        super().__init__(
            f"Illegal transition: {from_status.value} -> {to_status.value} "
            f"for session {session_id}"
        )
        self.session_id = session_id
        self.from_status = from_status
        self.to_status = to_status
```

| 场景 | 错误码 | HTTP 状态 | 说明 |
|------|--------|----------|------|
| 非终态转换到非法状态 | ILLEGAL_TRANSITION | 409 | 状态机不允许的转换 |
| 终态 Session 不允许任何转换 | SESSION_TERMINATED | 409 | 已完成/失败/取消的 Session 不可变更 |
| 重复取消 | ALREADY_CANCELLING | 409 | Session 已在 CANCELLING 状态 |

### 10.2 恢复失败

```python
class RecoveryError(ReqRadarException):
    def __init__(self, session_id: UUID, checkpoint_version: int, reason: str, cause: Exception | None = None):
        super().__init__(
            f"Recovery failed for session {session_id} from checkpoint v{checkpoint_version}: {reason}",
            cause=cause,
        )
        self.session_id = session_id
        self.checkpoint_version = checkpoint_version
```

| 场景 | 处理方式 |
|------|---------|
| Checkpoint 版本不存在 | 自动尝试前一个版本，最多回退 3 次 |
| Evidence 链校验失败 | 回退到上一个一致点 |
| 热状态数据损坏 | 尝试从冷状态重建 |
| 冷状态也损坏 | 返回错误，建议重新创建 Session |
| Context Pipeline 重建失败 | 从 L1 重新 Collect，降级恢复 |

### 10.3 超时处理

```python
class SessionTimeoutError(ReqRadarException):
    def __init__(self, session_id: UUID, elapsed: float, limit: int):
        super().__init__(
            f"Session {session_id} timed out after {elapsed:.1f}s (limit: {limit}s)"
        )
        self.session_id = session_id
        self.elapsed = elapsed
        self.limit = limit
```

**超时处理的分层策略**：

| 层级 | 超时类型 | 阈值 | 处理 |
|------|---------|------|------|
| Session | 最大执行时间 | `max_execution_time`（默认 1800s） | → TIMEOUT |
| 推理步骤 | 单步超时 | `step_timeout`（默认 120s） | 重试 1 次，仍超时 → FAILED |
| 工具调用 | 工具超时 | ToolRuntime 配置（默认 30s） | 重试（ToolRuntime 管控） |
| LLM 调用 | LLM 超时 | `llm_timeout`（默认 60s） | 重试 3 次，仍超时 → ABORTED |
| 取消清理 | 取消超时 | `cancellation_timeout`（默认 60s） | 强制终止 → CANCELLED |

### 10.4 Checkpoint 写入失败

```python
class CheckpointWriteError(ReqRadarException):
    def __init__(self, session_id: UUID, version: int, cause: Exception):
        super().__init__(
            f"Checkpoint write failed for session {session_id} v{version}: {cause}",
            cause=cause,
        )
        self.session_id = session_id
        self.version = version
```

**处理流程**：

```
Checkpoint 写入失败
       │
       ├── 重试 1（立即）
       │    ├── 成功 → 继续
       │    └── 失败 → 重试 2（延迟 1s）
       │         ├── 成功 → 继续
       │         └── 失败 → 判断降级策略
       │
       └── 降级策略
            ├── 严格模式（默认）：Session → ABORTED
            └── 宽松模式：checkpoint_enabled = False，Session 继续
                           发布 CHECKPOINT_DEGRADED 事件
```

---

## 11. 配置参数

### 11.1 Session 相关配置

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `session.max_execution_time` | int | 1800 | 60-7200 | 最大执行时间（秒） |
| `session.checkpoint_interval` | int | 300 | 30-3600 | 自动 Checkpoint 间隔（秒） |
| `session.checkpoint_enabled` | bool | True | - | 是否启用自动 Checkpoint |
| `session.checkpoint_degradation` | str | "lenient" | "strict" / "lenient" | Checkpoint 失败降级策略 |
| `session.context_budget_default` | int | 128000 | 4096-2000000 | 默认 Token 预算 |
| `session.max_reasoning_steps` | int | 50 | 1-200 | 最大推理步骤数 |
| `session.max_tool_calls` | int | 100 | 1-500 | 最大工具调用数 |
| `session.step_timeout` | int | 120 | 10-600 | 单步推理超时（秒） |
| `session.cancellation_timeout` | int | 60 | 10-300 | 取消清理超时（秒） |
| `session.llm_timeout` | int | 60 | 10-300 | LLM 调用超时（秒） |
| `session.llm_max_retries` | int | 3 | 0-10 | LLM 调用最大重试次数 |
| `session.ws_heartbeat_interval` | int | 30 | 5-120 | WebSocket 心跳间隔（秒） |
| `session.ws_heartbeat_timeout` | int | 60 | 10-300 | WebSocket 心跳超时（秒） |
| `session.recovery_max_rollback` | int | 3 | 1-10 | 恢复时最大回退版本数 |
| `session.auto_cleanup_days` | int | 90 | 7-365 | 终态 Session 自动清理天数 |

### 11.2 配置矩阵映射

Session 相关配置在 Scope × Domain 矩阵中的位置：

| | RUNTIME Domain |
|--|---------------|
| **SYSTEM** | `session.max_execution_time`, `session.context_budget_default` 等全局默认值 |
| **PROJECT** | 项目级预算配置、工具白名单 |
| **USER** | 用户会话限制、模型偏好 |
| **SESSION** | 请求体中 `config` 字段覆盖，优先级最高 |

**解析优先级**：请求体 config > SESSION scope > USER scope > PROJECT scope > SYSTEM scope

---

## 12. 与其他模块的关系

| 模块 | 文档 | 交互方式 | 说明 |
|------|------|---------|------|
| Context Pipeline | R-02 | Session 持有 `context_budget` 和 `context_usage`，Pipeline 遵守预算约束 | Session 是 Pipeline 的配置来源和状态接收者 |
| Event Stream | R-03 | Session 产生 Session 级事件，推理循环产生 Reasoning/Cognitive 级事件 | 所有事件以 `session_id` 为归属 |
| Checkpoint | R-05 | Session 拥有 `checkpoint_chain`，cognitive-rt 创建，index-service 存储 | Checkpoint 是 Session 状态快照的持久化载体 |
| Evidence Model | M-01 | Session 持有 `evidence_count`，Evidence 链完整性是恢复校验的必要条件 | Evidence 聚合发生在 Session 的推理循环中 |
| 7-Dimension Framework | M-02 | Session 持有 `dimensions_completed/pending`，维度完成是 COMPLETED 的前置条件 | 维度评估驱动 Session 推理循环的终止判断 |
| ToolRuntime | R-04 | Session 控制 `config.tools` 白名单和 `max_tool_calls` 上限 | Session 是工具执行权限的管控者 |
| L3 Knowledge Sediment | M-03 | Session COMPLETED 时触发 L3 沉淀（异步） | Session 是 L2→L3 认知飞轮的起点 |
| index-service | I-01 | Session 通过 HTTP API 调用 index-service 存储/查询 Checkpoint | 服务间同步调用 |
| output-service | I-01 | Session COMPLETED 时触发报告生成（异步） | 服务间异步调用 |

**依赖方向**：

```
R-01 (Session Lifecycle)
  ├── 依赖 R-02 (Context Pipeline) 的接口定义
  ├── 依赖 R-03 (Event Stream) 的事件 Schema
  ├── 依赖 R-05 (Checkpoint) 的存储接口
  ├── 依赖 M-01 (Evidence) 的数据模型
  ├── 依赖 M-02 (7-Dimension) 的维度枚举
  └── 被 R-04 (ToolRuntime)、M-03 (L3 Sediment) 依赖
```

---

## 13. 测试策略

### 13.1 单元测试

| 测试类别 | 覆盖内容 | 数量估计 |
|---------|---------|---------|
| 状态机转换 | 每条转换规则（T1-T20）的合法/非法场景 | 40+ |
| 数据模型 | Pydantic 模型的校验、序列化、默认值 | 20+ |
| 配置解析 | Scope × Domain 矩阵的优先级解析 | 10+ |
| Checkpoint 降级 | 重试、降级、严格模式的各种组合 | 10+ |
| 恢复校验 | Evidence 链完整性校验的各种失败场景 | 10+ |

### 13.2 集成测试

| 测试类别 | 覆盖内容 | 关键断言 |
|---------|---------|---------|
| 创建 → 启动 → 完成 | 完整正常流程 | status 最终为 COMPLETED |
| 创建 → 启动 → 取消 | 取消流程 | status 经历 CANCELLING → CANCELLED |
| 创建 → 启动 → 超时 | 超时流程 | status 为 TIMEOUT |
| 创建 → 启动 → 异常中止 | 不可恢复错误 | status 为 ABORTED |
| Chatback 暂停/恢复 | WAITING_INPUT 往返 | 推理在恢复后继续 |
| Checkpoint 周期性写入 | 自动 Checkpoint | version 递增，PG 中有对应记录 |
| Checkpoint 写入失败降级 | 降级模式 | Session 继续运行，事件标记降级 |
| 手动 Checkpoint | 用户触发 | type = MANUAL |

### 13.3 恢复测试

| 测试场景 | 操作 | 预期结果 |
|---------|------|---------|
| 正常恢复 | 中断后从最新 Checkpoint 恢复 | 步骤数和证据链一致 |
| 指定版本恢复 | 从非最新版本恢复 | 从指定步骤继续 |
| Evidence 链损坏恢复 | 模拟 Evidence 缺失 | 回退到上一个一致点 |
| 全部 Checkpoint 不可用 | 清空所有 Checkpoint | 返回 409 |
| 热状态损坏恢复 | 模拟 JSONB 数据损坏 | 尝试从冷状态重建 |
| 恢复后继续完成 | 恢复后让分析继续到完成 | 最终 status = COMPLETED |

### 13.4 并发与竞态测试

| 测试场景 | 操作 | 预期结果 |
|---------|------|---------|
| 并发取消 | 两个客户端同时调用 cancel | 只有一个成功，另一个返回 409 |
| 取消与完成竞态 | 推理完成的同时调用 cancel | 先到达的生效，后到达的返回 409 |
| 并发启动 | 两个客户端同时调用 start | 只有一个成功，另一个返回 409 |
| Checkpoint 期间取消 | CHECKPOINTING 状态下调用 cancel | 进入 CANCELLING，Checkpoint 中断 |

### 13.5 性能测试

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| Session 创建延迟 | < 200ms | 创建 100 个 Session 取 P99 |
| 状态查询延迟 | < 50ms | 查询 1000 次取 P99 |
| Checkpoint 写入延迟 | < 100ms | 写入 100 个 Checkpoint 取 P99 |
| WebSocket 事件推送延迟 | < 50ms（单节点） | 从事件产生到客户端接收 |
| 恢复延迟 | < 2s | 从请求到推理循环恢复 |

---

## 14. 明确不做的事

| 方向 | 结论 | 原因 |
|------|------|------|
| Session 暂停/恢复（非 Checkpoint 方式） | 不做 | Checkpoint 是唯一的恢复机制，不引入独立的暂停语义 |
| Session 克隆 | 不做 | 可通过创建新 Session + resume_from 实现类似效果 |
| 多 Agent 编排 | 不做 | 单 Session 内单 Agent 推理，不引入 Agent 间协调 |
| Session 级别的时间线回滚 | 不做 | Checkpoint 是快照而非操作日志，不支持任意时间点回滚到非 Checkpoint 点 |
| Session 间依赖 | 不做 | Session 之间独立，不引入 DAG 依赖关系 |
| Session 优先级调度 | 不做 | 当前单实例部署，不需要调度器；多实例部署时由 P4 ToolRuntime 处理 |
| Session 结果自动对比 | 不做 | 同一项目的多次分析对比由前端聚合展示，不在 Session 层实现 |
| Session 实时修改 config | 不做 | config 在创建时确定，运行期间不可修改（除 checkpoint_enabled 降级） |
| Session 数据的软删除 | 不做 | 终态 Session 保留审计链，通过 `auto_cleanup_days` 定期硬删除 |
| 跨项目 Session | 不做 | Session 绑定单一项目，不引入跨项目分析 |
