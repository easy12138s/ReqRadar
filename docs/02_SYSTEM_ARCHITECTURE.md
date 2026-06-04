## ReqRadar V2 — 总体技术架构设计

### 1. 设计目标

| 目标 | 说明 |
|------|------|
| 架构完整性 | 每个组件的设计必须是最终形态，不允许临时降级或"先跑起来再说" |
| 可追溯性 | 所有推理过程、状态变更、上下文演变必须可记录、可查询、可回放 |
| 可观测性 | 系统运行状态、性能指标、错误链路必须透明可见 |
| 可扩展性 | 新服务模块、新工具类型、新 LLM 提供商的接入成本最小化 |
| 面向未来体验设计 | 以 V2 认知运行时体验为目标，不兼容 V1 现有界面和 API |

---

### 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Traefik Gateway                                 │
│                    (边缘路由 / TLS终止 / 限流 / 健康检查)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  auth-service │           │  api-service  │           │  frontend     │
│  (认证授权)    │           │   (BFF/API)   │           │  (静态资源)    │
│               │           │               │           │               │
│ • JWT签发      │           │ • 请求路由     │           │ • React 19    │
│ • 权限校验     │           │ • 协议转换     │           │ • Ant Design 6│
│ • 用户管理     │           │ • 聚合响应     │           │ • Vite 8      │
└───────────────┘           └───────┬───────┘           └───────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │cognitive-rt │ │index-service│ │output-service│
            │ (认知运行时)  │ │  (索引存储)  │ │  (输出渲染)  │
            │             │ │             │ │             │
            │• Session管理 │ │• Checkpoint │ │• 报告生成    │
            │• Context管线 │ │  存储查询    │ │• 格式转换    │
            │• Event Stream│ │• 向量索引    │ │• 导出下载    │
            │• ToolRuntime │ │• 全文检索    │ │             │
            └──────┬──────┘ └─────────────┘ └─────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ingestion-svc│ │integration- │ │   Redis     │
│ (数据摄取)   │ │  svc (集成)  │ │  Streams    │
│             │ │             │ │  Pub/Sub    │
│• 文档解析    │ │• MCP客户端   │ │             │
│• 代码分析    │ │• 外部API    │ │• Event Bus  │
│• 向量化      │ │• 工具编排    │ │• WS广播     │
└─────────────┘ └─────────────┘ └─────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         reqradar-kernel (共享内核)                           │
│                                                                              │
│  • 领域模型 (Pydantic)  • 配置矩阵 (Scope × Domain)  • 基础类型定义          │
│  • 序列化协议  • 错误码体系  • 常量与枚举                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 3. 技术栈选型

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 网关 | Traefik | v3 | 边缘路由、TLS、限流、服务发现 |
| 前端 | React + Ant Design + Vite | 19 / 6 / 8 | 用户界面 |
| API 框架 | FastAPI | 0.115+ | HTTP API |
| 异步任务 | Celery / ARQ | - | 后台任务队列 |
| 数据库 | PostgreSQL | 16+ | 关系数据、JSONB、向量扩展 |
| 缓存/消息 | Redis | 7+ | 缓存、Streams、Pub/Sub |
| 对象存储 | MinIO | - | 大文件、二进制数据 |
| 容器编排 | Docker Compose | - | 本地/测试环境 |
| 包管理 | uv | - | Python monorepo |
| 监控 | Prometheus + Grafana | - | 指标采集与可视化 |

---

### 4. 核心子系统设计

#### 4.1 CognitiveSession — 一等运行时实体

CognitiveSession 是 V2 架构的核心抽象，代表一次完整的认知分析会话。

**属性：**
- `session_id`: UUID，全局唯一标识
- `status`: 状态机（11 状态，详见 R-01：CREATED → READY → RUNNING → CHECKPOINTING → COMPLETED / FAILED / CANCELLED / CANCELLING / TIMEOUT / ABORTED / WAITING_INPUT / RESUMED）
- `context_budget`: Token 预算上限
- `context_usage`: 当前已用 Token
- `checkpoint_chain`: Checkpoint 版本链引用
- `created_at / updated_at`: 时间戳

**职责：**
- Runtime Scheduler：调度推理步骤执行顺序
- Context Container：持有当前有效上下文
- Event Host：产生和接收事件
- Checkpoint Owner：管理状态快照版本链
- State Carrier：携带完整会话状态

#### 4.2 Context Pipeline — Token 预算感知的上下文工程

五阶段流水线，每阶段可配置策略：

```
Collect → Score → Select → Compress → Assemble
```

| 阶段 | 功能 | 策略示例 |
|------|------|----------|
| Collect | 收集所有潜在上下文来源 | 历史消息、工具返回、系统提示、相关文档 |
| Score | 评估每个片段的相关性 | 基于 Embedding 相似度、时间衰减、用户显式标记 |
| Select | 根据预算选择最优子集 | 贪心选择、动态规划、约束满足 |
| Compress | 压缩选中片段 | 摘要生成、关键词提取、结构化转换 |
| Assemble | 组装最终上下文 | 按优先级排序、添加元数据标记、格式标准化 |

**约束：** 输出上下文必须严格满足 `token_count ≤ context_budget`。

#### 4.3 Event Stream — 结构化推理链事件

三级事件体系，全部通过 Redis Streams 传输：

| 级别 | 事件类型 | 产生者 | 消费者 |
|------|---------|--------|--------|
| Session | SESSION_CREATED, SESSION_COMPLETED, SESSION_FAILED | cognitive-rt | api-service, output-service |
| Reasoning | STEP_STARTED, STEP_COMPLETED, TOOL_INVOKED, TOOL_RETURNED | cognitive-rt | api-service（WS推送）, index-service |
| Cognitive | CONTEXT_COLLECTED, CONTEXT_SCORED, CHECKPOINT_CREATED | Context Pipeline | index-service |

**WebSocket 多节点广播方案：**

采用 Redis Pub/Sub 实现跨节点 WebSocket 广播。每个 cognitive-rt 实例同时作为 Redis Pub/Sub 的订阅者和发布者：

- **订阅**：监听 `ws:session:{session_id}` 频道，接收其他节点产生的事件
- **发布**：将本节点产生的事件发布到对应 session 频道
- **转发**：收到 Pub/Sub 消息后，转发给连接到本节点且关注该 session 的 WebSocket 客户端

此方案在 Phase 3 多节点部署时直接生效，无需额外过渡方案。

#### 4.4 ToolRuntime — 能力声明中间层

ToolRuntime 是工具执行的运行时封装，提供以下能力：

| 能力 | 说明 |
|------|------|
| 超时控制 | 可配置超时时间，超时自动中断 |
| 重试策略 | 指数退避重试，可配置最大重试次数 |
| 权限校验 | 基于 Scope × Domain 矩阵的权限检查 |
| Checkpoint 记录 | 工具执行前后自动创建 Checkpoint |
| 事件记录 | 产生 TOOL_INVOKED / TOOL_RETURNED 事件 |
| 结果缓存 | 基于参数哈希的短期缓存 |

**接口定义：**
```python
class ToolRuntime:
    async def execute(
        self,
        tool_id: str,
        params: dict,
        session: CognitiveSession,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> ToolResult:
        ...
```

#### 4.5 Checkpoint System — 版本化快照

**存储方案：三区存储（详见 R-05_CHECKPOINT_DESIGN.md）**

| 区 | 存储 | 内容 | 生命周期 |
|----|------|------|---------|
| Hot | PostgreSQL JSONB | hot_state 关键字段（context_usage/active_tools/current_phase/evidence_count/dimension_summary/last_tool） | 随 Session 存活 |
| Cold | MinIO/S3 | full_state 完整快照 JSON | 持久化，按策略清理 |
| Rebuildable | 不存储 | 可从 Hot + Cold + Event Stream 重建 | N/A |

**CheckpointType**：STEP_COMPLETE / CHATBACK_SNAPSHOT / SESSION_COMPLETE / MANUAL

**版本链**：每个 Checkpoint 指向 previous_version，形成不可变版本链。

**事务保证**：利用 PostgreSQL ACID 保证 Checkpoint 与业务状态一致性；TOAST 压缩由应用层验证。

**Checkpoint 数据结构示例：**
```json
{
  "checkpoint_id": "uuid",
  "session_id": "uuid",
  "version": 42,
  "previous_version": 41,
  "created_at": "2026-05-26T10:00:00Z",
  "created_by": "cognitive-rt",
  "type": "STEP_COMPLETE",
  "hot_state": {
    "context_usage": 1500,
    "active_tools": ["code_search", "doc_reader"],
    "current_phase": "ANALYSIS",
    "evidence_count": 12,
    "dimension_summary": {"risk": 0.7, "impact": 0.5},
    "last_tool": "code_search"
  },
  "cold_uri": "s3://checkpoints/uuid/v42/full.json",
  "metadata": {
    "duration_ms": 1200,
    "token_consumed": 800
  }
}
```

**版本链查询：**
```sql
-- 获取会话完整版本链
SELECT * FROM checkpoints 
WHERE session_id = ? 
ORDER BY version;

-- 获取特定时间点的状态
SELECT * FROM checkpoints 
WHERE session_id = ? AND created_at <= ? 
ORDER BY version DESC LIMIT 1;
```

#### 4.6 配置矩阵 — Scope × Domain

替代 V1 中按功能模块的配置类，采用二维矩阵：

| | LLM | TOOL | MCP | INDEX | RUNTIME | OUTPUT |
|--|-----|------|-----|-------|---------|--------|
| **SYSTEM** | 系统级默认模型 | 全局工具开关 | 系统 MCP 配置 | 默认索引参数 | 全局运行时限制 | 默认输出格式 |
| **PROJECT** | 项目首选模型 | 项目工具集 | 项目 MCP 覆盖 | 项目索引策略 | 项目预算配置 | 项目模板 |
| **USER** | 用户模型偏好 | 用户工具权限 | 用户 MCP 密钥 | 用户检索偏好 | 用户会话限制 | 用户格式偏好 |
| **SESSION** | 会话模型覆盖 | 会话工具调用 | 会话 MCP 状态 | 会话检索范围 | 会话实时预算 | 会话输出选项 |

**解析优先级：** SESSION > USER > PROJECT > SYSTEM

---

### 5. 部署拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Compose                           │
│                                                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ Traefik │  │  React  │  │ FastAPI │  │ FastAPI │           │
│  │ Gateway │  │  Build  │  │  Auth   │  │  API    │           │
│  │  :80    │  │  (静态)  │  │  Svc    │  │  Svc    │           │
│  │  :443   │  │         │  │         │  │         │           │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
│       │            │            │            │                  │
│       └────────────┴────────────┴────────────┘                  │
│                         │                                        │
│       ┌─────────────────┼─────────────────┐                     │
│       ▼                 ▼                 ▼                     │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐                 │
│  │ cognitive│      │  index  │      │ output  │                 │
│  │   -rt   │      │  -svc   │      │  -svc   │                 │
│  └────┬────┘      └────┬────┘      └────┬────┘                 │
│       │                │                │                       │
│       └────────────────┼────────────────┘                       │
│                        │                                         │
│       ┌────────────────┼────────────────┐                       │
│       ▼                ▼                ▼                       │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐                 │
│  │ingestion│      │integra- │      │  Redis  │                 │
│  │  -svc   │      │ tion-svc│      │Streams+ │                 │
│  │         │      │         │      │ Pub/Sub │                 │
│  └─────────┘      └─────────┘      └────┬────┘                 │
│                                         │                       │
│       ┌────────────────┬────────────────┘                       │
│       ▼                ▼                                        │
│  ┌─────────┐      ┌─────────┐                                   │
│  │PostgreSQL│      │ MinIO   │                                   │
│  │  + pgvector│    │ (S3 API)│                                   │
│  └─────────┘      └─────────┘                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**服务间通信：**
- 同步：HTTP/REST（内部服务间）
- 异步：Redis Streams（事件驱动）
- 广播：Redis Pub/Sub（WebSocket 跨节点）

---

### 6. 服务模块详细说明

#### 6.1 auth-service

| 属性 | 说明 |
|------|------|
| 职责 | JWT 签发与校验、用户认证、权限管理 |
| 暴露 | HTTP API（内部） |
| 依赖 | PostgreSQL（用户表） |
| 不做什么 | 不处理业务逻辑、不直接暴露给前端 |

#### 6.2 api-service（BFF）

| 属性 | 说明 |
|------|------|
| 职责 | 前端统一入口、请求路由、协议转换、响应聚合 |
| 暴露 | HTTP API + WebSocket（前端） |
| 依赖 | auth-service, cognitive-rt, Redis Pub/Sub |
| WebSocket | 维护前端 WS 连接，通过 Redis Pub/Sub 接收跨节点事件并推送给客户端 |

#### 6.3 cognitive-rt-service

| 属性 | 说明 |
|------|------|
| 职责 | CognitiveSession 生命周期管理、Context Pipeline 执行、ToolRuntime 调度、Event 产生 |
| 暴露 | HTTP API（内部）+ Redis Streams |
| 依赖 | Redis Streams, index-service, integration-service |
| 关键 | 无状态设计，可水平扩展 |

#### 6.4 index-service

| 属性 | 说明 |
|------|------|
| 职责 | Checkpoint 存储与查询、向量索引、全文检索 |
| 暴露 | HTTP API（内部） |
| 依赖 | PostgreSQL + pgvector, MinIO |
| Checkpoint | 主存储 PostgreSQL JSONB，超限二进制数据存 MinIO |

#### 6.5 output-service

| 属性 | 说明 |
|------|------|
| 职责 | 报告生成、格式转换、导出下载 |
| 暴露 | HTTP API（内部） |
| 依赖 | index-service（查询 Checkpoint 链） |
| 模板 | 支持 Markdown / HTML / PDF / JSON |

#### 6.6 ingestion-service

| 属性 | 说明 |
|------|------|
| 职责 | 文档解析、代码分析、向量化、元数据提取 |
| 暴露 | HTTP API（内部）+ 异步任务队列 |
| 依赖 | PostgreSQL, MinIO |

#### 6.7 integration-service

| 属性 | 说明 |
|------|------|
| 职责 | MCP 客户端、外部 API 调用、工具编排 |
| 暴露 | HTTP API（内部） |
| 依赖 | Redis Streams（接收 ToolRuntime 调用） |

---

### 7. 数据流转

#### 7.1 分析请求完整流程

```
1. 前端 → api-service: POST /api/v2/analysis
                    │
2. api-service → auth-service: 校验 JWT
                    │
3. api-service → cognitive-rt: 创建 CognitiveSession
                    │
4. cognitive-rt → Redis Streams: 发布 SESSION_CREATED
                    │
5. cognitive-rt: 执行 Context Pipeline
   ├── 调用 integration-service: 工具执行
   ├── 调用 index-service: 存储 Checkpoint
   └── 发布事件到 Redis Streams
                    │
6. api-service ← Redis Pub/Sub: 接收事件
                    │
7. 前端 ← api-service (WebSocket): 实时推送
                    │
8. cognitive-rt: 完成分析
   ├── 调用 output-service: 生成报告
   └── 发布 SESSION_COMPLETED
```

#### 7.2 事件流向

```
cognitive-rt ──► Redis Streams ──► index-service (持久化)
     │                              │
     │                              ▼
     │                         PostgreSQL
     │
     └──► Redis Pub/Sub ──► api-service (WS广播)
                              │
                              ▼
                           前端客户端
```

---

### 8. 前端设计策略

**原则：面向未来用户体验，不兼容 V1**

| 层面 | 策略 |
|------|------|
| API 路径 | 全新 `/api/v2/...` 路径，不复用 V1 路由 |
| WebSocket | 全新 WS 协议，支持 Event Stream 结构化推送 |
| 响应格式 | 全新响应结构，适配 CognitiveSession / Event / Checkpoint 数据模型 |
| 部署 | 前端独立容器化（Nginx/Caddy），与后端服务解耦 |
| 构建 | `outDir` 输出到独立目录，通过 Traefik 路由 `/app/*` |

---

### 9. CLI 定位

**原则：全部远程执行，不维护本地业务逻辑**

| 命令 | 行为 |
|------|------|
| `reqradar analyze <path>` | 调用 api-service 创建远程分析任务 |
| `reqradar status <task-id>` | 查询远程任务状态 |
| `reqradar report <task-id>` | 下载远程生成的报告 |
| `reqradar config` | 管理本地配置文件（API 端点、认证信息） |

CLI 本身是无状态的 thin client，所有业务逻辑在服务端执行。

---

### 10. 接口契约

#### 10.1 服务间通信

- **同步：** HTTP/REST + JSON，OpenAPI 文档自动生成
- **异步：** Redis Streams，JSON 序列化
- **事件 Schema：** 定义在 `reqradar-kernel` 中，所有服务共享

#### 10.2 版本策略

- API 版本号：URL 路径 `/api/v2/...`
- 事件 Schema 版本：字段级兼容，新增字段不破坏旧消费者
- Kernel 包版本：SemVer，服务模块依赖固定 minor 版本

---

### 11. 安全设计

| 层面 | 措施 |
|------|------|
| 传输 | TLS 1.3（Traefik 终止） |
| 认证 | JWT + Refresh Token，auth-service 统一签发 |
| 授权 | Scope × Domain 矩阵，中间件统一校验 |
| 敏感数据 | API Key、MCP 密钥存储于 PostgreSQL，加密字段 |
| 审计 | 所有认证事件、权限变更记录到 Redis Streams → index-service |

---

### 12. 性能基线

| 指标 | 目标 | 说明 |
|------|------|------|
| API 响应 P99 | < 200ms | 健康检查、配置读取等轻量接口 |
| 分析任务启动 | < 2s | 从请求到第一个推理步骤开始 |
| Checkpoint 写入 | < 100ms | 单条 JSONB 记录 |
| WebSocket 延迟 | < 50ms | 事件产生到前端接收（单节点） |
| 上下文组装 | < 500ms | 完整 Pipeline 执行（典型负载） |

---

### 13. 文档配套关系

| 文档 | 内容 | 状态 |
|------|------|------|
| 00_PROJECT_POSITIONING.md | 项目宪法、愿景、战略边界 | ✅ 已完成 |
| 01_RESTUCTURE_OVERVIEW.md | Runtime 架构蓝图、核心概念定义 | ✅ 已完成 |
| **02_SYSTEM_ARCHITECTURE.md** | **总体技术架构设计（本文档）** | **✅ v1.2 当前** |
| 03_COGNITIVE_ASSET_MODEL.md | 四层认知资产模型（L0-L3） | ✅ 已完成 |
| 04_IMPLEMENTATION_ROADMAP.md | 实施路线图、Phase 划分、验收标准 | ✅ 已完成 |
| CODE_WIKI.md | V1 代码全景图 | ✅ 已完成 |
| detailed/M-01~M-04 | 数据模型详细设计（Evidence/7维/L3/图谱） | ✅ 已完成 |
| detailed/R-01~R-05 | 运行时规格（Session/Context/Event/Tool/Checkpoint） | ✅ 已完成 |
| detailed/C-01~C-06 | 编码约束（规范/依赖/配置/API/测试/迁移） | ✅ 已完成 |
| detailed/I-01 服务间 API 契约 | cognitive-rt↔index-service 等内部接口契约 | ✅ 已完成 |
 | detailed/I-02 部署与 DevOps | Docker Compose、CI/CD、监控方案 | ✅ 已完成 |
 | detailed/I-03 数据迁移方案 | V1→V2 完整字段级映射与迁移脚本 | ✅ 已完成 |
 | detailed/S-01 安全设计专篇 | 威胁模型、认证流程、审计日志设计 | ✅ 已完成 |
  | detailed/F-01 前端功能架构 | 页面路由/组件树/状态管理/API映射/WS消费 | ✅ 已完成 |
  | docs/adr/ | 架构决策记录（16 条 ADR 展开） | ✅ 已完成 |

---
