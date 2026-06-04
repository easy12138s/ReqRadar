# ReqRadar V2 重构计划概览

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v2.1 |
| 文档定位 | Runtime 架构蓝图 |
| 前置文档 | 00_PROJECT_POSITIONING.md（项目宪法 / 愿景） |
| 核心目标 | 从「AI 功能集合」演进为「项目认知运行时系统」 |
| 文档职责 | How — Runtime 如何设计、Session 如何运转、State 如何演化 |

---

## 一、架构核心：Runtime First

V1 已经具备 ReAct Agent、Tool Calling、Evidence System、Memory System 等完整能力，但它们仍然以「业务代码」方式存在，没有被建模为 Runtime System。

V2 的核心转变：

| | V1（功能集合） | V2（Runtime System） |
|---|---|---|
| 核心抽象 | HTTP Request + Task 记录 | **Cognitive Session（一等运行时实体）** |
| Prompt 构建 | f-string 拼接 | **Context Pipeline（Token 预算感知）** |
| 工具调用 | 字典查找 + 直接执行 | **ToolRuntime（能力声明 + 统一管控）** |
| 状态可见性 | 散落日志 + ad-hoc WS 推送 | **Event Stream（结构化推理链）** |
| 会话恢复 | 塞在 JSON blob 中 | **Checkpoint（版本化快照）** |

---

## 二、Runtime Flow（运行时数据流）

Runtime 不是模块堆积，而是一个完整的数据流动过程：

```
──────────┐
│   Input   │  需求文档 / 代码仓库 / Git 历史 / 项目记忆
─────┬────┘
      ▼
┌──────────────┐
│  Ingestion   │  多格式解析 → Chunking → 预处理管线
└──────┬───────┘
       ▼
┌──────────────┐
│    Context    │  Context Pipeline: Collect → Score → Select → Compress → Assemble
│   Pipeline    │  （不同推理阶段使用不同 Context Strategy）
──────┬───────┘
       ▼
┌──────────────┐
│  Reasoning   │  ReAct 循环: Thought → Action → Observation → Evidence
│    Loop      │  （每步产生 Event，可 Checkpoint）
└─────────────┘
       ▼
──────────────┐
│  Evidence    │  Evidence 聚合 → Dimension Status 更新 → Cognitive State 演进
│ Aggregation  │
└──────┬───────┘
       ▼
──────────────┐
│   Event      │  事件流: Session/Reasoning/Cognitive 三类事件 → WS 推送 / Debug / Trace
│   Stream     │
└──────┬───────┘
       ▼
┌──────────────┐
│  Checkpoint  │  版本化快照持久化 → 可恢复 / 可回放 / 可追溯
└──────┬───────┘
       ▼
┌──────────────┐
│   Output     │  报告渲染 → 版本管理 → 发布基线 → 认知输出
└──────────────┘
```

---

## 三、Runtime Layering（运行时分层架构）

系统按五层组织，每层职责清晰：

```
─────────────────────────────────────────────┐
│           Output Layer                       │  报告 / 版本 / 发布基线
│  output-service                              │
├─────────────────────────────────────────────
│           Interaction Layer                  │  Chatback / 意图分类 / 快照恢复
│  cognitive-rt/interaction                    │
├─────────────────────────────────────────────┤
│           Cognition Layer                    │  ReAct 推理 / Context Pipeline / ToolRuntime
│  cognitive-rt/cognition + context + tools    │
─────────────────────────────────────────────┤
│           Runtime Layer                      │  Session 管理 / Event Bus / Checkpoint
│  cognitive-rt/runtime + events + checkpoint  │
├─────────────────────────────────────────────┤
│           Infrastructure Layer               │  数据库 / 向量存储 / 文件系统 / Gateway
│  PostgreSQL + ChromaDB + Traefik             │
└─────────────────────────────────────────────┘
```

---

## 四、服务拓扑与职责

### 4.1 服务拓扑

```
Browser / CLI / MCP Client
            │
            ▼
┌──────────────────────────────┐
│      Traefik Gateway         │
│ TLS / Routing / WS / CORS    │
└──────────────┬───────────────
               │
    ┌──────────┼──────────┬──────────┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼          ▼          ▼
  auth      BFF      cognitive-rt  index    output  ingestion integration
                             ★
```

### 4.2 服务清单

| 服务 | 定位 | 关键约束 |
|------|------|---------|
| auth-service | 身份与权限信任源 | JWT Secret 仅存于此 |
| api-service (BFF) | 面向前端的数据编排层 | 不持有运行时状态 |
| **cognitive-runtime-service** | **AI Runtime 引擎（核心）** | **持有 Session 全生命周期** |
| index-service | 长期认知与知识索引 | ChromaDB 独占 |
| output-service | 报告与版本输出 | 模板热更新不重启其他服务 |
| ingestion-service | 多源输入与预处理 | 文件处理 CPU 密集，可异步 |
| integration-service | MCP 与外部生态集成 | 可选部署，预留外部数据源扩展点 |
| reqradar-kernel | 最小共享类型内核 | ≤3000 行，仅类型定义 |

---

## 五、CognitiveSession — Runtime Core

**CognitiveSession 不是数据库记录，而是 Runtime 的统一宿主实体。**

它是以下五个子系统的聚合载体：

| 角色 | 说明 |
|------|------|
| **Runtime Scheduler** | 控制 Session 生命周期：11 状态状态机（详见 R-01），核心路径 CREATED → READY → RUNNING → CHECKPOINTING → COMPLETED / FAILED / CANCELLED，含 CANCELLING / TIMEOUT / ABORTED / WAITING_INPUT / RESUMED 扩展状态 |
| **Context State Container** | 持有当前推理步骤的全部上下文：project_memory / user_memory / history / evidence / dimension_state |
| **Event Host** | 所有推理事件以 session_id 为归属，可通过 session 获取完整 Event Trace |
| **Checkpoint Owner** | 每个 Checkpoint 是 Session 在某个步骤的完整状态快照，由 cognitive-rt 创建，由 index-service 持久化存储 |
| **Cognitive State Carrier** | 会话结束时，Cognitive State 沉淀到 index-service 成为组织记忆 |

**Session 生命周期**：

```
CREATED → READY → RUNNING → CHECKPOINTING → COMPLETED
                                          → FAILED
                                          → CANCELLED（经 CANCELLING 中间态）
                                          → TIMEOUT
                                          → ABORTED
                                 → WAITING_INPUT → RESUMED → RUNNING
```
（完整 11 状态状态机及 20 条转换规则详见 R-01_SESSION_LIFECYCLE.md）

---

## 六、四大 Runtime 核心抽象

### 6.1 Context Pipeline

**替代 f-string 拼接，实现 Token 预算感知的上下文工程。**

流水线：

```
Collect → Score → Select → Compress → Assemble
```

核心机制：

- **Token Budget Awareness**：任何步骤不超上限，保留高价值上下文
- **Dynamic Attention Allocation**：根据当前推理阶段（风险分析/架构理解/证据聚合）使用不同 Context Strategy
- **Stage-aware Context Scheduling**：不同步骤注入不同上下文源组合

### 6.2 Event Stream

**日志不是 Runtime，事件才是。**

三类事件：

| 层级 | 事件类型 |
|------|---------|
| Session 级 | SessionCreated / Started / Checkpointed / Completed / Failed |
| 推理级 | ThoughtGenerated / ToolInvoked / ObservationReceived / StepCompleted |
| 认知级 | EvidenceAdded / DimensionChanged / MemoryInjected / RiskDetected |

用途：实时 WebSocket 推送 / Runtime Debug / 推理链 Trace / 可解释性 / Timeline / 未来 Replay。

### 6.3 ToolRuntime

**在工具注册表之上增加管控中间层。**

为每个工具声明能力元数据：超时、重试策略、权限、是否需要 Checkpoint、自动事件记录。不改各工具的实现方式，只增加管控能力。

### 6.4 Checkpoint System

**版本化快照持久化机制。**

每个 Checkpoint 是 Session 在某个步骤的完整状态快照（包含 AgentState + EvidenceState + DimensionState + ContextState）。**cognitive-rt 负责创建，index-service 负责持久化存储和恢复。**

支持：

- 任意时间点恢复
- 分析中断后继续
- Chatback 对话前快照回滚
- 推理链回溯追溯
- runtime 服务重启后跨实例恢复

---

## 七、Project Cognitive State

系统长期积累的核心数据结构。从 Memory JSON 升级为 **AI 对项目的持续认知状态**：

- 架构理解 / 术语体系 / 模块依赖
- 历史决策 / 未解决风险
- 需求谱系 / 证据图谱
- 置信度评分

长期演进方向：从 RAG Retrieval 向 Cognitive Graph 演进。当前不引入图数据库，但接口层预留 Graph 演化能力（ADR-015）。

---

## 八、服务间调用关系

```
前端 → Traefik → 各服务（透明路由）

api-svc → auth-svc（验权）
api-svc → cognitive-rt（task 统计 / 提交任务）

cognitive-rt → index-svc（工具数据查询，最频繁）
cognitive-rt → output-svc（报告渲染）
cognitive-rt → LLM Provider（每次 ReAct 循环）

integration-svc → ingestion-svc（MCP 读需求）
integration-svc → index-svc（MCP 读记忆）
integration-svc → output-svc（MCP 读报告）
integration-svc → cognitive-rt（MCP 读分析列表）

CLI → backend（全部远程执行，与前端共享同一 API）
```

---

## 九、演进路线

| 阶段 | 目标 | 说明 |
|------|------|------|
| **P0** | Kernel 抽离 | 最小共享内核，ORM 单一定义源，Workspace 建立 |
| **P1** | 模块化单体 + Context Pipeline | 不拆部署，先拆边界；**Context Pipeline 同步实现，验证认知运行时智力** |
| **P2** | Gateway + Auth | 引入 Traefik，Auth 独立化 |
| **P3** | **Cognitive Runtime Core** | **最关键**：Session / Event / Checkpoint / Runtime State |
| **P4** | ToolRuntime | Capability Layer / Retry / Timeout / Tool Event |
| **P5** | 拆 index-service | ChromaDB 独立，认知存储独立 |
| **P6** | 拆 output-service | 渲染独立，模板独立 |
| **P7** | BFF 独立 | api-service 独立为前端聚合层 |
| **P8** | MCP 独立 | integration-service 可选部署 |
| **P9** | 性能升级 | 热点路径 HTTP → gRPC |

---

## 十、明确不做的事

| 方向 | 结论 |
|------|------|
| Neo4j / 图数据库 | 暂不引入，接口预留 |
| Kafka / 外部 MQ | 暂不引入 |
| 完整事件驱动架构 | 暂不引入 |
| 通用 Agent 平台 | 不做 |
| 多 Agent 编排 | 不做 |
| 通用 AI OS | 不做 |
| 本地 CLI 执行引擎 | 不做（CLI 统一远程调用） |

---

## 十一、ADR（架构决策记录）

当前 16 条关键决策，未来独立为 `/docs/adr/` 目录，每条 ADR 展开为 Context/Decision/Consequence/Tradeoff 四段式结构：

| ADR | 决策 |
|-----|------|
| ADR-001 | Traefik 作为边缘网关 |
| ADR-002 | Auth 独立服务 |
| ADR-003 | Kernel 最小化（仅类型定义） |
| ADR-004 | Chatback 留在 Cognitive Runtime |
| ADR-005 | Phase 1 使用 HTTP 通信 |
| ADR-006 | Phase 1 共享 PostgreSQL |
| ADR-007 | uv workspace Monorepo |
| **ADR-008** | **面向未来用户体验设计（不兼容 V1，以 V2 认知运行时体验为目标）** |
| ADR-009 | Ingestion 独立 |
| ADR-010 | api-service 采用 BFF 模式 |
| ADR-011 | CognitiveSession 为一等公民 |
| ADR-012 | 引入 Context Pipeline（**P1 优先级**） |
| ADR-013 | 引入 Event Stream（Redis Streams） |
| ADR-014 | 引入 ToolRuntime |
| ADR-015 | Graph 能力预留，暂不实现 |
| **ADR-016** | **Checkpoint 持久化（cognitive-rt 创建，index-service 存储）** |

---

## 十二、总结

ReqRadar V2 不是一次普通微服务重构，而是从「AI 功能集合」升级为「垂直领域 Cognitive Runtime System」。

系统核心目标不是生成内容，而是**让 AI 对项目形成长期、可追溯、可演化的认知**。

核心壁垒来自：项目认知建模、Context Runtime、Evidence System、Cognitive State、Long-term Project Understanding——而不是 Prompt 模板、Tool 数量或通用聊天能力。

---