# F-01 前端 V2 详细设计

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | 前端 V2 的功能架构设计——前后端接口对齐、组件树、路由、状态管理、WebSocket 消费层 |
| 前置文档 | 02_SYSTEM_ARCHITECTURE.md（第 8 节前端策略）、04_IMPLEMENTATION_ROADMAP.md（P8 前端改造）、C-04_API_CONTRACT_REGISTRY.md（全部 API 端点 + WS 协议）、CODE_WIKI.md（V1 前端结构参考） |
| 核心目标 | 前端功能架构设计——不涉及 UI/UX 美化，仅定义页面/组件/路由/数据流/API 调用与 WS 消费方案 |
| 文档职责 | What & How — 前端有哪些页面、组件如何拆分、数据怎么流转、API 怎么调用、WS 怎么消费、类型怎么映射 |

**设计约束**：本文档不设计 UI 布局、配色、交互动效——这些属于 P8 后期的美化任务。本文档仅保证**前后端功能完整对齐**。

---

## 2. 总则

### 2.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 8 | 构建工具 |
| Ant Design | 6 | UI 组件库 |
| @tanstack/react-query | 5 | 服务端状态管理 |
| React Router | 7 | 路由 |
| Axios | — | HTTP 客户端 |
| recharts | — | 图表（认知仪表盘） |
| react-markdown | — | 报告内容展示 |
| framer-motion | — | 页面过渡动画 |

### 2.2 设计原则

| 原则 | 说明 |
|------|------|
| 不兼容 V1 | 全新 `/api/v2/` 路径，全新路由 `/app/v2/`，不保留 V1 页面 |
| API 优先 | 每个页面的数据来源对应 C-04 中明确的 API 端点 |
| 按需加载 | 所有页面组件 `React.lazy()` + `Suspense` 懒加载 |
| 类型安全 | 后端 Pydantic → 前端 TypeScript 类型定义一一对应 |
| 实时优先 | 分析过程通过 WebSocket 实时推送，不做轮询 |
| UI 后置 | 本文档只定功能骨架，不画 UI——美化留到 P8 后期 |

### 2.3 部署策略

- 前端独立容器化（Nginx 托管静态产物）
- 通过 Traefik 路由 `/app/*` 
- 独立于后端服务部署，可单独扩缩容

---

## 3. 页面路由表

### 3.1 完整路由

| 路径 | 页面组件 | 权限 | 说明 | 对应后端 API |
|------|---------|------|------|-------------|
| `/app/v2/login` | LoginPage | 无 | 登录 | `POST /api/v2/auth/login` |
| `/app/v2/register` | RegisterPage | 无 | 注册 | `POST /api/v2/auth/register` |
| `/app/v2/` | DashboardPage | 用户 | 项目列表 + 仪表盘概览 | `GET /api/v2/projects`, `GET /api/v2/projects/{pid}/knowledge`（聚合） |
| `/app/v2/projects/:pid` | ProjectDetailPage | 用户 | 项目详情 + L0/L1 索引状态 | `GET /api/v2/projects/{id}`, `GET /api/v2/projects/{pid}/knowledge` |
| `/app/v2/projects/:pid/analyze` | AnalysisCreatePage | 用户 | 提交需求 + 创建 Session | `POST /api/v2/sessions` |
| `/app/v2/sessions/:sid` | SessionDetailPage | 用户 | Session 状态 + 7 维度 + 证据 | `GET /api/v2/sessions/{id}`, `GET /api/v2/sessions/{id}/dimensions`, `GET /api/v2/sessions/{id}/evidence` |
| `/app/v2/sessions/:sid/events` | SessionEventsPage | 用户 | 推理步骤事件流 | `GET /api/v2/sessions/{id}/events`, `GET /api/v2/sessions/{id}/trace` |
| `/app/v2/sessions/:sid/report` | ReportPage | 用户 | 分析报告查看 | `GET /api/v2/sessions/{id}`（通过 output-service） |
| `/app/v2/sessions/:sid/checkpoints` | CheckpointsPage | 用户 | Checkpoint 版本链 + 回放 | `GET /api/v2/sessions/{id}/checkpoints` |
| `/app/v2/projects/:pid/knowledge` | KnowledgeDashboard | 用户 | L3 认知仪表盘 | `GET /api/v2/projects/{pid}/knowledge`（聚合），`POST /api/v2/projects/{pid}/knowledge`（检索） |
| `/app/v2/projects/:pid/knowledge/:kid` | KnowledgeDetail | 用户 | 单条知识详情 | `GET /api/v2/projects/{pid}/knowledge/{kid}` |
| `/app/v2/projects/:pid/knowledge/changelog` | KnowledgeChangelog | 用户 | 知识变更日志 | `GET /api/v2/projects/{pid}/knowledge/changelog` |
| `/app/v2/projects/:pid/graph` | GraphExplorerPage | 用户 | 认知图谱浏览 | `GET /api/v2/projects/{pid}/graph/neighbors`, `GET /api/v2/projects/{pid}/graph/subgraph` |
| `/app/v2/templates` | TemplateManagerPage | 用户 | 报告模板管理 | `GET|POST /api/v2/templates` |
| `/app/v2/settings` | SettingsPage | 用户 | 系统/项目/用户配置 | `/api/v2/configs/*` |
| `/app/v2/admin/users` | UserManagementPage | admin | 用户管理 | `/api/v2/users/*` |

### 3.2 路由嵌套结构（React Router）

```tsx
<BrowserRouter basename="/app/v2">
  <Routes>
    {/* 公开 */}
    <Route path="login" element={<LoginPage />} />
    <Route path="register" element={<RegisterPage />} />
    
    {/* 需登录 */}
    <Route element={<AuthGuard />}>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="projects/:pid" element={<ProjectDetailPage />} />
        <Route path="projects/:pid/analyze" element={<AnalysisCreatePage />} />
        <Route path="projects/:pid/knowledge" element={<KnowledgeDashboard />} />
        <Route path="projects/:pid/knowledge/:kid" element={<KnowledgeDetail />} />
        <Route path="projects/:pid/knowledge/changelog" element={<KnowledgeChangelog />} />
        <Route path="projects/:pid/graph" element={<GraphExplorerPage />} />
        <Route path="sessions/:sid" element={<SessionDetailPage />} />
        <Route path="sessions/:sid/events" element={<SessionEventsPage />} />
        <Route path="sessions/:sid/report" element={<ReportPage />} />
        <Route path="sessions/:sid/checkpoints" element={<CheckpointsPage />} />
        <Route path="templates" element={<TemplateManagerPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="admin/users" element={<AdminGuard><UserManagementPage /></AdminGuard>} />
      </Route>
    </Route>
  </Routes>
</BrowserRouter>
```

---

## 4. 组件树

### 4.1 布局组件

```
AppLayout
├── AppShell（Ant Design Layout）
│   ├── Sidebar（导航菜单）
│   │   ├── Logo
│   │   ├── NavMenu（项目/分析/知识/模板/设置）
│   │   └── UserAvatar + Logout
│   ├── Header（面包屑 + 页面标题）
│   └── Content
│       └── <Outlet />（路由渲染区）
└── ChatbackDrawer（全局侧边抽屉，Session 上下文中显示）
```

### 4.2 各页面内部组件

```
DashboardPage
├── ProjectList（项目卡片列表 + 创建按钮）
│   └── ProjectCard × N（名称/状态/最近分析时间）
└── QuickStats（全局统计：活跃 Session 数/L3 知识数等）

ProjectDetailPage
├── ProjectInfo（名称/描述/仓库路径）
├── L0Files（上传文件列表，MinIO 引用）
├── L1IndexStatus（ChromaDB 索引状态：chunks/代码/commit 数量）
├── AnalysisList（该项目的历史 Session 列表）
│   └── SessionRow × N（状态/创建时间/进度摘要）
└── MemoryPreview（L3 知识摘要卡片）

AnalysisCreatePage
├── RequirementUpload（文件上传 / 文本输入）
├── SessionConfigPanel
│   ├── StrategySelect（context_strategy 选择）
│   ├── BudgetSlider（context_budget 调节）
│   ├── ToolCheckboxGroup（工具白名单勾选）
│   └── TemplateSelect（报告模板选择）
└── StartButton（调用 POST /api/v2/sessions + POST /api/v2/sessions/{id}/start）

SessionDetailPage（分析中实时更新）
├── SessionHeader（状态标签 + 进度条 + 取消按钮）
├── ReasoningTimeline（推理步骤时间线，WS 驱动）
│   └── StepCard × N
│       ├── ThoughtSummary（思考摘要）
│       └── ToolCallBadge × N（工具调用标记）
├── DimensionPanel（7 维度雷达图 + 状态表）
├── EvidenceList（已收集证据列表）
│   └── EvidenceCard × N（类型/置信度/来源引用）
├── ChatbackPanel（用户追问对话区，WS 交互）
└── ReportButton（完成后触发报告生成）

SessionEventsPage
├── EventFilter（按类型/级别过滤）
├── EventTimeline（事件流时间线，WS 实时推送）
│   └── EventItem × N
│       ├── SessionEventCard（开始/完成/失败）
│       ├── StepEventCard（STEP_STARTED/STEP_COMPLETED）
│       ├── ToolEventCard（TOOL_INVOKED/TOOL_RETURNED）
│       └── CognitiveEventCard（EVIDENCE_ADDED/DIMENSION_CHANGED）
└── EventDetailDrawer（点击事件展开 payload 详情）

ReportPage
├── ReportNav（Markdown 目录导航）
└── ReportContent（react-markdown 渲染）

CheckpointsPage
├── VersionChain（版本时间线）
│   └── CheckpointNode × N（版本号/类型/时间/状态摘要）
├── VersionDiff（两版本对比视图）
└── RestoreButton（从选定 Checkpoint 恢复）

KnowledgeDashboard（L3 认知仪表盘）
├── DashboardTabs
│   ├── Tab: 总览
│   │   ├── KnowledgeSummaryCards（7 种知识类型统计卡片）
│   │   ├── RiskHeatmap（风险热力图，按模块着色）
│   │   └── FreshnessDistribution（新鲜度分布饼图）
│   ├── Tab: 术语表（搜索 + 列表 + 新增）
│   ├── Tab: 模块画像（模块卡片网格）
│   ├── Tab: 架构约束（约束列表，含严重度标记）
│   ├── Tab: 决策记录（时间线排列）
│   ├── Tab: 风险演化（风险列表 + 演化轨迹）
│   ├── Tab: 需求谱系（需求版本关系图）
│   └── Tab: 事故记忆（事故时间线）
└── KnowledgeSearchBar（语义检索入口 → POST /api/v2/projects/{pid}/knowledge）

KnowledgeDetail
├── KnowledgeMeta（类型 / freshhness / confidence / 验证次数）
└── KnowledgeContent（各类型特有字段展示）

KnowledgeChangelog
├── ChangelogFilter（按类型/变更类型/时间过滤）
└── ChangelogTable（变更记录列表）

GraphExplorerPage
├── GraphCanvas（节点+关系可视化，可选 recharts 或简单 SVG）
├── NodeDetailPanel（点击节点展示详情）
└── GraphControls（遍历深度/关系类型过滤/置信度阈值）

SettingsPage
├── SystemConfigForm（系统配置编辑）
├── ProjectConfigForm（项目配置编辑）
└── UserConfigForm（用户偏好设置）

TemplateManagerPage
├── TemplateList（模板卡片）
├── TemplateEditor（YAML + Jinja2 编辑）
└── DefaultBadge（默认模板标记）

UserManagementPage（admin only）
└── UserTable（用户列表 + 角色编辑 + 禁用/启用）
```

---

## 5. API 客户端模块拆分

每个后端路由模块一个前端文件，入口统一使用 `apiClient`（Axios 实例，token 注入 + 错误拦截）：

```
frontend/src/api/
├── client.ts              # axios 实例（token 注入 + 统一错误处理）
├── auth.ts                # POST /api/v2/auth/*
├── projects.ts            # GET|POST|PUT|DELETE /api/v2/projects/*
├── sessions.ts            # POST|GET /api/v2/sessions/*  (创建/查询/取消/启动)
├── evidence.ts            # GET /api/v2/sessions/{id}/evidence/*  + verify
├── dimensions.ts          # GET /api/v2/sessions/{id}/dimensions
├── checkpoints.ts         # GET /api/v2/sessions/{id}/checkpoints/*  + restore
├── events.ts              # GET /api/v2/sessions/{id}/events
├── trace.ts               # GET /api/v2/sessions/{id}/trace
├── knowledge.ts           # GET|POST|PUT /api/v2/projects/{pid}/knowledge/*  + deprecate + changelog
├── graph.ts               # GET /api/v2/projects/{pid}/graph/*
├── templates.ts           # GET|POST|PUT|DELETE /api/v2/templates/*
├── configs.ts             # GET|PUT|DELETE /api/v2/configs/*  (system/project/user)
├── users.ts               # GET|PUT|DELETE /api/v2/users/*  (admin)
└── health.ts              # GET /api/v2/health
```

### 5.1 apiClient 配置（V2 版）

```typescript
// frontend/src/api/client.ts
import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api/v2",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// 请求拦截器：注入 JWT
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/app/v2/login";
    }
    // 403/404/409/422/5xx 统一 toast 提示（由页面层按需覆盖）
    return Promise.reject(error);
  }
);

export default apiClient;
```

### 5.2 API 模块示例（sessions.ts）

```typescript
// frontend/src/api/sessions.ts
import apiClient from "./client";

export interface CreateSessionRequest {
  project_id: string;
  config?: {
    context_budget?: number;
    context_strategy?: string;
    max_execution_time?: number;
    tools?: string[];
    llm_model?: string | null;
    template_id?: string | null;
  };
}

export interface SessionResponse {
  session_id: string;
  project_id: string;
  status: string;
  created_at: string;
  state: {
    context_usage: number;
    current_step: number;
    current_phase: string;
  };
}

export const createSession = (data: CreateSessionRequest) =>
  apiClient.post<SessionResponse>("/sessions", data);

export const startSession = (sessionId: string, resumeFrom?: number) =>
  apiClient.post(`/sessions/${sessionId}/start`, { resume_from: resumeFrom ?? null });

export const getSession = (sessionId: string) =>
  apiClient.get(`/sessions/${sessionId}`);

export const cancelSession = (sessionId: string) =>
  apiClient.post(`/sessions/${sessionId}/cancel`);

export const getSessionEvents = (sessionId: string, params?: { type?: string; level?: string; since?: number; limit?: number }) =>
  apiClient.get(`/sessions/${sessionId}/events`, { params });

export const getSessionTrace = (sessionId: string, params?: { step_start?: number; step_end?: number }) =>
  apiClient.get(`/sessions/${sessionId}/trace`, { params });
```

---

## 6. 状态管理方案

### 6.1 服务端状态（react-query）

| 数据 | queryKey 模式 | staleTime | 说明 |
|------|-------------|-----------|------|
| 项目列表 | `["projects"]` | 5min | 仪表盘 |
| 项目详情 | `["projects", pid]` | 2min | 项目详情页 |
| Session 状态 | `["sessions", sid]` | 10s | 分析进行中需频繁刷新 |
| Session 列表 | `["sessions", "list", { projectId }]` | 1min | 项目下的 Session 列表 |
| 证据列表 | `["evidence", sid]` | 30s | 分析进行中持续更新 |
| 维度状态 | `["dimensions", sid]` | 30s | |
| Checkpoint 列表 | `["checkpoints", sid]` | 1min | |
| L3 知识聚合 | `["knowledge", pid, "aggregate"]` | 5min | 仪表盘 |
| L3 知识检索 | `["knowledge", pid, "search", query]` | 2min | |
| 知识详情 | `["knowledge", pid, kid]` | 2min | |
| 知识变更日志 | `["knowledge", pid, "changelog"]` | 2min | |
| 图谱邻居 | `["graph", pid, nodeType, nodeId]` | 2min | |
| 模板列表 | `["templates"]` | 10min | |
| 配置 | `["configs", scope]` | 10min | scope = system/project/me |

### 6.2 客户端全局状态（React Context）

| Context | 内容 | 说明 |
|---------|------|------|
| AuthContext | `{ user, token, login, logout }` | 认证状态 |
| ThemeContext | `{ theme, toggleTheme }` | 亮/暗主题 |
| WsContext | `{ activeConnections: Map<sid, WsState> }` | 活跃 WS 连接状态，供各页面共享 |

### 6.3 组件本地状态

仅限纯 UI 状态（表单值、弹窗开闭、选项卡切换等）。禁止在页面组件中用 `useState` 管理来自服务端的数据。

---

## 7. WebSocket 消费层设计

### 7.1 连接管理

```typescript
// frontend/src/hooks/useSessionWebSocket.ts

interface UseSessionWsOptions {
  sessionId: string;
  enabled: boolean; // Session 状态为 RUNNING/CHECKPOINTING 时才连接
  filters?: { levels?: string[]; types?: string[] };
  onEvent?: (event: WsEvent) => void;
}

function useSessionWebSocket({ sessionId, enabled, filters, onEvent }: UseSessionWsOptions) {
  // 1. 建立连接: ws://host/api/v2/sessions/{sid}/ws?token=jwt
  // 2. 发送订阅过滤: { type: "subscribe", filters: {...} }
  // 3. 接收服务端推送: event / ping / session_ended
  // 4. 心跳: 收到 ping 回复 pong
  // 5. 断线重连: 记录 last_sequence，重连后发送 resync
  // 6. 终态关闭: 收到 session_ended 后 30s 自动断开
  // 7. Chatback: 发送 { type: "chatback", data: { message: "..." } }
}
```

### 7.2 事件消费分发

```
WebSocket → WsContext（全局连接池）
  ├── SessionEventsPage → EventTimeline（全量事件）
  ├── SessionDetailPage → ReasoningTimeline（仅 reasoning 级）
  ├── SessionDetailPage → DimensionPanel（DIMENSION_CHANGED 事件）
  ├── SessionDetailPage → EvidenceList（EVIDENCE_ADDED 事件）
  └── ChatbackPanel → 对话消息（chatback 回复）
```

每个消费组件通过 `useSessionWebSocket` hook 订阅自己关心的事件级别和类型，WS 连接由 hook 内部管理，组件无需关心连接生命周期。

### 7.3 前端 → 服务端 WS 消息类型

| 消息类型 | 触发场景 | payload |
|---------|---------|---------|
| `subscribe` | 连接建立后立即发送 | `{ type: "subscribe", filters: { levels, types } }` |
| `resync` | 断线重连后发送 | `{ type: "resync", last_sequence: number }` |
| `pong` | 收到 ping 后回复 | `{ type: "pong" }` |
| `chatback` | 用户在 ChatbackPanel 输入消息 | `{ type: "chatback", data: { message: string } }` |

---

## 8. TypeScript 类型定义映射

### 8.1 类型文件拆分

```
frontend/src/types/
├── session.ts      # CreateSessionRequest, SessionResponse, SessionStatus, SessionConfig, SessionState
├── evidence.ts     # EvidenceRecord, EvidenceType, EvidenceStatus, EvidenceConfidence, EvidenceRelation
├── dimension.ts    # DimensionResult, DimensionStatus, RiskLevel
├── checkpoint.ts   # CheckpointRecord, CheckpointType, CheckpointVersion, RestoreResponse
├── event.ts        # WsEvent, EventType, EventLevel, EventPayload, EventBatch
├── knowledge.ts    # KnowledgeEntry, KnowledgeType, FreshnessStatus, ConfidenceMetadata, KnowledgeChangelog
├── graph.ts        # KnowledgeNode, KnowledgeRelation, RelationType, NeighborResponse, SubgraphResponse
├── trace.ts        # ReasoningTrace, TraceStep
├── project.ts      # Project, ProjectConfig
├── auth.ts         # LoginRequest, RegisterRequest, User, AuthResponse
├── config.ts       # SystemConfig, ProjectConfig, UserConfig
├── template.ts     # ReportTemplate
├── ws.ts           # WsMessage types (subscribe/resync/pong/chatback + server→client event/ping/session_ended)
└── common.ts       # PaginatedResponse<T>, ErrorResponse, HealthResponse
```

### 8.2 后端 Pydantic → 前端 TypeScript 映射规则

| Pydantic | TypeScript |
|----------|-----------|
| `str` | `string` |
| `int` | `number` |
| `float` | `number` |
| `bool` | `boolean` |
| `UUID` | `string`（格式 `uuid`） |
| `datetime` | `string`（ISO 8601） |
| `list[T]` | `T[]` |
| `dict[str, T]` | `Record<string, T>` |
| `T \| None` | `T \| null` |
| `Enum` | `type X = "a" \| "b" \| "c"` |
| `BaseModel` | `interface X { ... }` |

### 8.3 关键类型示例

```typescript
// frontend/src/types/session.ts
export type SessionStatus =
  | "CREATED" | "READY" | "RUNNING" | "CHECKPOINTING"
  | "WAITING_INPUT" | "CANCELLING"
  | "COMPLETED" | "FAILED" | "CANCELLED" | "TIMEOUT" | "ABORTED";

export interface SessionConfig {
  context_budget: number;
  context_strategy: string;
  max_execution_time: number;
  tools: string[];
  llm_model: string | null;
  template_id: string | null;
}

export interface SessionState {
  context_usage: number;
  current_step: number;
  current_phase: string;
  evidence_count: number;
  dimensions_completed: string[];
  dimensions_pending: string[];
}

export interface SessionResponse {
  session_id: string;
  project_id: string;
  status: SessionStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  config: SessionConfig;
  state: SessionState;
  last_checkpoint_version: number;
  total_reasoning_steps: number;
  total_tool_calls: number;
  error_message: string | null;
}

// frontend/src/types/event.ts
export type EventType =
  | "SESSION_CREATED" | "SESSION_STARTED" | "SESSION_CHECKPOINTED"
  | "SESSION_COMPLETED" | "SESSION_FAILED" | "SESSION_CANCELLING"
  | "SESSION_CANCELLED" | "SESSION_TIMEOUT" | "SESSION_ABORTED"
  | "SESSION_WAITING_INPUT" | "SESSION_RESUMED"
  | "STEP_STARTED" | "STEP_COMPLETED"
  | "TOOL_INVOKED" | "TOOL_RETURNED" | "TOOL_RETRY"
  | "TOOL_TIMEOUT" | "TOOL_PERMISSION_DENIED" | "TOOL_CHECKPOINT_FAILED"
  | "CONTEXT_COLLECTED" | "CONTEXT_SCORED"
  | "EVIDENCE_ADDED" | "DIMENSION_CHANGED";

export type EventLevel = "session" | "reasoning" | "cognitive";

export interface WsEvent {
  event_id: string;
  sequence: number;
  event_type: EventType;
  event_level: EventLevel;
  timestamp: string;
  producer: string;
  payload: Record<string, unknown>;
}

// frontend/src/types/common.ts
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

// frontend/src/types/knowledge.ts
export type KnowledgeType =
  | "glossary" | "module_profile" | "constraint"
  | "decision" | "risk" | "requirement_lineage" | "incident";

export type FreshnessStatus =
  | "active" | "historical" | "superseded" | "deprecated" | "stale" | "conflicted";

export interface KnowledgeEntry {
  id: string;
  knowledge_type: KnowledgeType;
  data: Record<string, unknown>;
  freshness: FreshnessStatus;
  confidence_score: number;
  verification_count: number;
  source_session_count: number;
  human_verified: boolean;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

// frontend/src/types/graph.ts
export type RelationType =
  | "DEPENDS_ON" | "IMPACTS" | "CONFLICTS_WITH" | "EVOLVES_FROM"
  | "MITIGATES" | "VIOLATES" | "DERIVED_FROM" | "CORROBORATES" | "SUPERSEDES";

export interface KnowledgeRelation {
  source_type: KnowledgeType;
  source_id: string;
  relation_type: RelationType;
  target_type: KnowledgeType;
  target_id: string;
  confidence: number;
  evidence_ref: string;
}
```

---

## 9. react-query 使用规范

### 9.1 查询 Hook 模板

```typescript
// frontend/src/hooks/useSession.ts
import { useQuery } from "@tanstack/react-query";
import { getSession } from "@/api/sessions";
import type { SessionResponse } from "@/types/session";

export function useSession(sessionId: string) {
  return useQuery<SessionResponse>({
    queryKey: ["sessions", sessionId],
    queryFn: () => getSession(sessionId).then(res => res.data),
    // 运行中 Session 每 10 秒刷新
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "RUNNING" || status === "CHECKPOINTING" ? 10000 : false;
    },
    enabled: !!sessionId,
  });
}
```

### 9.2 变更 Hook 模板

```typescript
// frontend/src/hooks/useCreateSession.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSession } from "@/api/sessions";
import type { CreateSessionRequest, SessionResponse } from "@/types/session";

export function useCreateSession(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateSessionRequest) =>
      createSession(data).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions", "list", { projectId }] });
    },
  });
}
```

### 9.3 queryKey 命名规范

- 列表：`["resource"]` 或 `["resource", "list", filters]`
- 详情：`["resource", id]`
- 子资源：`["resource", id, "subresource"]`
- 嵌套子资源：`["resource", id, "subresource", subId]`（最多嵌套两层）

---

## 10. 分页与加载态

### 10.1 分页组件

使用 Ant Design `Table` 的 `pagination` 属性，参数与 C-04 分页规范对齐：

```typescript
interface PaginationParams {
  page: number;       // 从 1 开始
  page_size: number;  // 默认 20，最大 200
}

// 对于 Checkpoint/Event 等特殊端点
interface OffsetPaginationParams {
  limit: number;
  offset: number;
}
```

### 10.2 加载态组件

| 状态 | 组件 | 说明 |
|------|------|------|
| 数据加载中 | `<Spin />` 或 `<Skeleton />` | 首次加载 |
| 数据刷新中 | 不显示 loading，保持旧数据 + 表格右上角小 spinner | react-query 后台刷新 |
| 空列表 | `<Empty description="暂无数据" />` | 列表无数据 |
| 错误 | `<Result status="error" />` + 重试按钮 | API 调用失败 |

---

## 11. Chatback 对话交互

Chatback（分析完成后用户追问）通过 WebSocket 实现，不走独立 REST API（ADR-004）：

### 11.1 交互流程

```
1. 分析进行中 → 用户点击"追问" → 前端发送 WS chatback 消息
2. cognitive-rt 收到 chatback → 暂停推理 → Session 进入 WAITING_INPUT
3. 前端收到 SESSION_WAITING_INPUT 事件 → ChatbackPanel 显示"等待中"
4. cognitive-rt 处理追问 → 创建 Checkpoint（CHATBACK_SNAPSHOT）→ 恢复推理
5. 前端收到 SESSION_RESUMED 事件 → ChatbackPanel 显示回复
```

### 11.2 ChatbackPanel 组件接口

```typescript
interface ChatbackPanelProps {
  sessionId: string;
  visible: boolean;
  onClose: () => void;
}

// 内部状态
interface ChatMessage {
  role: "user" | "agent";
  content: string;
  timestamp: string;
}
```

---

## 12. 构建配置

### 12.1 Vite 配置要点

```typescript
// frontend/vite.config.ts（V2 关键变更）
export default defineConfig({
  base: "/app/v2/",
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api/v2": "http://localhost:8002",  // → api-service
      "/ws": { target: "ws://localhost:8002", ws: true },
    },
  },
  build: {
    outDir: "../dist/frontend-v2",  // 独立于 V1 构建输出
  },
});
```

### 12.2 生产部署

- 构建产物由 Nginx 托管，Dockerfile 基于 `nginx:alpine`
- Nginx 配置 `try_files $uri /app/v2/index.html` 支持 SPA 路由
- 前端容器通过 Traefik 路由 `/app/*` 访问

---

## 13. Agent 开发指引

### 13.1 建议开发顺序

```
P8.1: Dockerfile + Nginx 配置 + 前端容器化（1天，基础设施）
P8.2: TypeScript 类型定义 + API 客户端模块 + 路由骨架（3天，全部接口先搭好）
P8.6: Auth 页面 → DashboardPage → AnalysisCreatePage → SessionDetailPage（4天，核心主流程）
P8.3: WebSocket 消费层 + SessionDetailPage 实时更新 + SessionEventsPage（3天）
P8.4: KnowledgeDashboard（5天，7 个 Tab 逐个实现）
P8.5: CheckpointsPage 回放（3天，可降级）
```

### 13.2 每个页面开发步骤

```
1. 读 C-04 找到对应 API 端点 + 请求/响应 Schema
2. 在 frontend/src/types/ 创建对应类型定义
3. 在 frontend/src/api/ 创建对应 API 调用函数
4. 在 frontend/src/hooks/ 创建 react-query Hook
5. 在 frontend/src/pages/ 创建页面组件（先用 Ant Design 基础组件实现功能）
6. 在 App.tsx 注册路由
7. 跑 npm run lint 确保类型正确
```

### 13.3 优先使用 Ant Design v6 组件

| 场景 | 推荐组件 |
|------|---------|
| 数据表格 | `Table`（内置分页、排序、行选择） |
| 表单 | `Form` + `Input` / `Select` / `Slider` / `Switch` / `Checkbox.Group` |
| 统计卡片 | `Card` + `Statistic` |
| 时间线 | `Timeline`（用于 Event Stream / Checkpoint / DecisionRecords） |
| 标签/徽章 | `Tag`（SessionStatus）/ `Badge`（消息数） |
| 选项卡 | `Tabs`（Knowledge 7 个 Tab） |
| 全局提示 | `message` / `notification` |
| 抽屉 | `Drawer`（Chatback / EventDetail） |
| 图表 | recharts `BarChart` / `PieChart` / `RadarChart` / `Treemap` |
| Markdown | react-markdown + `Typography` |

---

## 附录 A：页面-API 映射速查表

| 页面 | 主要 API | 实时更新 |
|------|---------|---------|
| LoginPage | `POST /api/v2/auth/login` | — |
| DashboardPage | `GET /api/v2/projects`, `GET /api/v2/projects/{pid}/knowledge`（聚合统计） | — |
| ProjectDetailPage | `GET /api/v2/projects/{id}` | — |
| AnalysisCreatePage | `POST /api/v2/sessions` → `POST /api/v2/sessions/{id}/start` | — |
| SessionDetailPage | `GET /api/v2/sessions/{id}`, `GET /api/v2/sessions/{id}/dimensions`, `GET /api/v2/sessions/{id}/evidence` | **WS**: reasoning级事件 |
| SessionEventsPage | `GET /api/v2/sessions/{id}/events` | **WS**: 全量事件 |
| ReportPage | `GET /api/v2/sessions/{id}` → output-service | — |
| CheckpointsPage | `GET /api/v2/sessions/{id}/checkpoints` | — |
| KnowledgeDashboard | `GET /api/v2/projects/{pid}/knowledge`, `POST /api/v2/projects/{pid}/knowledge`（检索） | — |
| KnowledgeDetail | `GET /api/v2/projects/{pid}/knowledge/{kid}` | — |
| KnowledgeChangelog | `GET /api/v2/projects/{pid}/knowledge/changelog` | — |
| GraphExplorerPage | `GET /api/v2/projects/{pid}/graph/neighbors`, `GET /api/v2/projects/{pid}/graph/subgraph` | — |
| SettingsPage | `GET/PUT /api/v2/configs/*` | — |
| TemplateManagerPage | `CRUD /api/v2/templates` | — |
| UserManagementPage | `CRUD /api/v2/users` | — |
