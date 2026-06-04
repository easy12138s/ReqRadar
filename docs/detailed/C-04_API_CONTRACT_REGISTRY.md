# C-04 API Contract Registry -- API 契约注册表

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 全部 API 端点的统一注册表，为 vibe coding 模式下的 AI Agent 提供完整的端点清单和精确的请求/响应 Schema |
| 前置文档 | R-01（Session 生命周期）、R-03（Event Stream Schema）、R-05（Checkpoint Design）、M-01（Evidence Model）、M-03（Project Cognitive State） |
| 核心目标 | 汇总所有 V2 API 端点，定义统一的设计总则、错误格式、分页规范、WebSocket 协议，确保前后端和服务间契约一致 |
| 文档职责 | What -- 哪些端点存在、路径是什么、请求/响应长什么样、认证要求如何、来源哪个设计文档 |

---

## 2. API 设计总则

### 2.1 基本约定

| 约定 | 说明 |
|------|------|
| API 前缀 | 所有 V2 外部 API 使用 `/api/v2/` 前缀；服务间内部 API 使用 `/internal/v2/` 前缀 |
| 认证方式 | JWT Bearer Token，通过 `Authorization: Bearer <token>` 头传递 |
| 内容类型 | 请求/响应统一使用 `application/json`，除非特别说明 |
| 时间格式 | ISO 8601，含时区，UTC，如 `2026-06-01T10:00:00Z` |
| ID 格式 | UUID v4，字符串形式，如 `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` |
| 空值表示 | JSON 中使用 `null`，不使用空字符串或省略字段 |
| 字符编码 | UTF-8 |

### 2.2 分页规范

所有列表类端点统一使用以下分页参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码，从 1 开始 |
| `page_size` | int | 20 | 每页条数，最大 200 |

分页响应格式：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

部分端点（如 Checkpoint 版本链、Event 流）使用 `limit`/`offset` 风格分页，在端点说明中特别标注。

### 2.3 认证要求标注

每个端点标注认证要求：

| 标记 | 含义 |
|------|------|
| `Required` | 必须携带有效 JWT Token |
| `Optional` | 可选认证，未认证时返回公开数据子集 |
| `None` | 无需认证（如 Health 端点） |
| `Internal` | 服务间调用，不经过 JWT 认证，通过网络策略隔离 |

---

## 3. 统一错误响应 Schema

### 3.1 错误响应格式

所有 API 错误响应使用统一的 JSON 结构：

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session xxx 不存在",
    "details": {}
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `error.code` | string | 机器可读的错误码，格式 `{RESOURCE}_{ERROR_TYPE}` |
| `error.message` | string | 人类可读的错误描述，中文 |
| `error.details` | object | 可选的附加详情，如校验错误字段列表 |

### 3.2 错误码命名规则

格式：`{RESOURCE}_{ERROR_TYPE}`

- `RESOURCE`：大写蛇形，如 `SESSION`、`CHECKPOINT`、`EVIDENCE`、`KNOWLEDGE`
- `ERROR_TYPE`：大写蛇形，如 `NOT_FOUND`、`ALREADY_EXISTS`、`INVALID_STATE`、`VALIDATION_FAILED`

### 3.3 标准 HTTP 状态码与错误码映射

| HTTP 状态码 | 含义 | 典型错误码 |
|------------|------|-----------|
| 400 | 请求参数错误 | `REQUEST_VALIDATION_FAILED`、`INVALID_PARAMETER` |
| 401 | 未认证 | `AUTHENTICATION_REQUIRED`、`TOKEN_EXPIRED` |
| 403 | 权限不足 | `PERMISSION_DENIED`、`RESOURCE_FORBIDDEN` |
| 404 | 资源不存在 | `SESSION_NOT_FOUND`、`PROJECT_NOT_FOUND`、`CHECKPOINT_NOT_FOUND`、`EVIDENCE_NOT_FOUND`、`KNOWLEDGE_NOT_FOUND` |
| 409 | 状态冲突 | `SESSION_INVALID_STATE`、`SESSION_ALREADY_RUNNING`、`CHECKPOINT_VERSION_CONFLICT`、`DUPLICATE_KEY` |
| 422 | 校验失败 | `CONFIG_VALIDATION_FAILED`、`EVIDENCE_CHAIN_BROKEN` |
| 500 | 服务器内部错误 | `INTERNAL_ERROR` |
| 503 | 服务不可用 | `STORAGE_UNAVAILABLE`、`LLM_SERVICE_UNAVAILABLE` |

---

## 4. 端点总表

### 4.1 Session 模块

来源文档：R-01

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| POST | `/api/v2/sessions` | 创建 Session | Required | `CreateSessionRequest` | `CognitiveSession` (201) | R-01 8.1 |
| POST | `/api/v2/sessions/{id}/start` | 启动/恢复 Session | Required | `StartSessionRequest` | `SessionStartResponse` (200) | R-01 8.2 |
| GET | `/api/v2/sessions/{id}` | 查询 Session 状态 | Required | - | `CognitiveSession` (200) | R-01 8.3 |
| POST | `/api/v2/sessions/{id}/cancel` | 取消 Session | Required | - | `CancelResponse` (202) | R-01 8.4 |
| POST | `/api/v2/sessions/{id}/checkpoint` | 手动触发 Checkpoint | Required | - | `CheckpointBrief` (200) | R-01 8.5 / R-05 12.3 |
| GET | `/api/v2/sessions/{id}/events` | 查询事件流 | Required | - | `EventBatch` (200) | R-01 8.6 / R-03 11.3 |
| WS | `/api/v2/sessions/{id}/ws` | 实时事件推送 | Required | - | Stream | R-01 8.7 / R-03 9 |

#### 4.1.1 POST /api/v2/sessions -- 创建 Session

请求体：

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

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | UUID | 是 | 关联项目 ID |
| `config` | SessionConfig | 否 | 会话配置，未指定字段使用配置矩阵默认值 |

响应体（201 Created）：

```json
{
  "session_id": "uuid",
  "project_id": "uuid",
  "status": "READY",
  "created_at": "2026-06-01T10:00:00Z",
  "config": { "..." : "..." },
  "state": {
    "context_usage": 0,
    "current_step": 0,
    "current_phase": "INIT"
  }
}
```

错误：404（项目不存在）、409（L1 索引不可用）、422（config 校验失败）

#### 4.1.2 POST /api/v2/sessions/{id}/start -- 启动/恢复 Session

请求体：

```json
{
  "resume_from": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `resume_from` | int \| null | 否 | Checkpoint 版本号，null 表示从头开始 |

响应体（200 OK）：

```json
{
  "session_id": "uuid",
  "status": "RUNNING",
  "started_at": "2026-06-01T10:00:05Z",
  "resumed_from_version": null,
  "state": {
    "context_usage": 0,
    "current_step": 0,
    "current_phase": "INIT"
  }
}
```

错误：409（status 非 READY / resume_from 版本不存在 / 恢复校验失败）

#### 4.1.3 GET /api/v2/sessions/{id} -- 查询 Session 状态

响应体（200 OK）：

```json
{
  "session_id": "uuid",
  "project_id": "uuid",
  "status": "RUNNING",
  "created_at": "2026-06-01T10:00:00Z",
  "started_at": "2026-06-01T10:00:05Z",
  "finished_at": null,
  "config": { "..." : "..." },
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

错误：404（Session 不存在）

#### 4.1.4 POST /api/v2/sessions/{id}/cancel -- 取消 Session

响应体（202 Accepted）：

```json
{
  "session_id": "uuid",
  "status": "CANCELLING",
  "message": "Cancellation requested, waiting for current step to complete"
}
```

错误：409（终态 Session / 已在 CANCELLING）

#### 4.1.5 POST /api/v2/sessions/{id}/checkpoint -- 手动触发 Checkpoint

响应体（200 OK）：

```json
{
  "checkpoint_id": "uuid",
  "version": 4,
  "session_id": "uuid",
  "type": "MANUAL",
  "created_at": "2026-06-01T10:05:00Z"
}
```

错误：409（status 非 RUNNING / Checkpoint 已禁用）

#### 4.1.6 GET /api/v2/sessions/{id}/events -- 查询事件流

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str \| null | null | 事件类型过滤 |
| `level` | str \| null | null | 事件级别过滤（session/reasoning/cognitive） |
| `since` | int \| null | null | 起始序列号（不包含） |
| `limit` | int | 100 | 返回条数上限（1-1000） |

响应体（200 OK）：

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
      "payload": { "..." : "..." }
    }
  ],
  "total": 42,
  "has_more": true
}
```

---

### 4.2 Evidence 模块

来源文档：M-01

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| GET | `/api/v2/sessions/{id}/evidence` | 查询 Session 证据列表 | Required | - | `EvidenceListResponse` (200) | M-01 9.2 |
| GET | `/api/v2/sessions/{id}/evidence/{eid}` | 查询单条证据详情 | Required | - | `EvidenceDetailResponse` (200) | M-01 9.2 |
| POST | `/api/v2/sessions/{id}/evidence/{eid}/verify` | 验证证据 | Required | `VerifyEvidenceRequest` | `VerifyEvidenceResponse` (200) | M-01 9.3 |

#### 4.2.1 GET /api/v2/sessions/{id}/evidence -- 查询证据列表

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str \| null | null | 证据类型过滤（code_evidence/requirement_ref/...） |
| `status` | str \| null | null | 证据状态过滤（discovered/verified/challenged/...） |
| `dimension` | str \| null | null | 维度过滤 |
| `min_confidence` | float \| null | null | 最低置信度 |
| `context_kind` | str \| null | null | 上下文类型过滤 |
| `limit` | int | 100 | 返回条数上限 |
| `offset` | int | 0 | 偏移量 |

响应体（200 OK）：

```json
{
  "total": 42,
  "items": [
    {
      "id": "ev-abc123def456",
      "session_id": "uuid",
      "type": "code_evidence",
      "status": "verified",
      "confidence": { "score": 0.85, "level": "high", "basis": "交叉检查 L1 索引通过" },
      "source_ref": {
        "context_kind": "SOURCE_CODE",
        "uri": "l1://modules/payment",
        "display_name": "payment.py:42"
      },
      "content": "支付模块无分布式锁保护",
      "dimension_refs": [
        { "dimension_id": "risk", "role": "supports", "weight": 1.0 }
      ],
      "step_id": 5,
      "tool_call_id": "call-xxx",
      "verified_by": "auto",
      "verified_at": "2026-06-01T10:01:30Z",
      "created_at": "2026-06-01T10:01:25Z",
      "updated_at": "2026-06-01T10:01:30Z"
    }
  ]
}
```

#### 4.2.2 GET /api/v2/sessions/{id}/evidence/{eid} -- 查询证据详情

响应体（200 OK）：

```json
{
  "evidence": {
    "id": "ev-abc123def456",
    "session_id": "uuid",
    "type": "code_evidence",
    "status": "verified",
    "confidence": { "score": 0.85, "level": "high", "basis": "..." },
    "source_ref": { "..." : "..." },
    "content": "...",
    "detail": { "module_name": "payment", "file_path": "src/pay/callback.py", "..." : "..." },
    "dimension_refs": [ "..." ],
    "step_id": 5,
    "tool_call_id": "call-xxx",
    "verified_by": "auto",
    "verified_at": "2026-06-01T10:01:30Z",
    "created_at": "2026-06-01T10:01:25Z",
    "updated_at": "2026-06-01T10:01:30Z"
  },
  "relations": [
    {
      "id": "evr-xxx",
      "source_evidence_id": "ev-abc123def456",
      "target_evidence_id": "ev-yyy",
      "relation_type": "SUPPORTS",
      "confidence": 1.0,
      "rationale": "代码证据支撑风险判断"
    }
  ]
}
```

#### 4.2.3 POST /api/v2/sessions/{id}/evidence/{eid}/verify -- 验证证据

请求体：

```json
{
  "verified_by": "auto"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `verified_by` | string | 是 | 验证者标识：`auto` 或 `human:{user_id}` |

响应体（200 OK）：

```json
{
  "evidence": { "..." : "..." },
  "previous_status": "discovered",
  "confidence_delta": 0.1
}
```

---

### 4.3 Dimension 模块

来源文档：M-01（6.2 维度评估）、M-02（7 维度框架）

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| GET | `/api/v2/sessions/{id}/dimensions` | 查询 Session 维度评估状态 | Required | - | `DimensionStatusResponse` (200) | M-01 6.2 |

#### 4.3.1 GET /api/v2/sessions/{id}/dimensions -- 查询维度评估状态

响应体（200 OK）：

```json
{
  "session_id": "uuid",
  "dimensions": {
    "completeness": { "status": "sufficient", "evidence_count": 5, "risk_level": "low" },
    "consistency": { "status": "sufficient", "evidence_count": 4, "risk_level": "low" },
    "feasibility": { "status": "in_progress", "evidence_count": 2, "risk_level": "medium" },
    "traceability": { "status": "pending", "evidence_count": 0, "risk_level": null },
    "ambiguity": { "status": "pending", "evidence_count": 0, "risk_level": null },
    "risk": { "status": "pending", "evidence_count": 0, "risk_level": null },
    "architecture": { "status": "pending", "evidence_count": 0, "risk_level": null }
  },
  "completed_count": 2,
  "pending_count": 5
}
```

---

### 4.4 Checkpoint 模块

来源文档：R-05

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| GET | `/api/v2/sessions/{id}/checkpoints` | 查询 Checkpoint 版本链 | Required | - | `CheckpointListResponse` (200) | R-05 12.3 |
| GET | `/api/v2/sessions/{id}/checkpoints/{version}` | 查询特定版本 Checkpoint | Required | - | `CheckpointDetailResponse` (200) | R-05 12.3 |
| POST | `/api/v2/sessions/{id}/checkpoints/{version}/restore` | 从 Checkpoint 恢复 | Required | - | `RestoreResponse` (200) | R-05 7.2 |

#### 4.4.1 GET /api/v2/sessions/{id}/checkpoints -- 查询版本链

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 20 | 返回条数上限（1-100） |
| `offset` | int | 0 | 偏移量 |
| `type` | str \| null | null | 按 CheckpointType 过滤 |

响应体（200 OK）：

```json
{
  "session_id": "uuid",
  "total": 42,
  "items": [
    {
      "checkpoint_id": "uuid",
      "version": 42,
      "type": "STEP_COMPLETE",
      "created_at": "2026-06-01T10:00:00Z",
      "state_summary": {
        "current_step": 12,
        "current_phase": "ANALYSIS",
        "context_usage": 45000,
        "evidence_count": 8,
        "dimensions_completed": ["completeness", "consistency"],
        "dimensions_pending": ["feasibility", "traceability", "ambiguity", "risk", "architecture"]
      }
    }
  ],
  "has_more": true
}
```

#### 4.4.2 GET /api/v2/sessions/{id}/checkpoints/{version} -- 查询特定版本

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `include_cold` | bool | false | 是否包含冷状态数据 |

响应体（200 OK）：

```json
{
  "checkpoint_id": "uuid",
  "version": 42,
  "type": "STEP_COMPLETE",
  "created_at": "2026-06-01T10:00:00Z",
  "state_summary": { "..." : "..." },
  "diff": {
    "added": ["evidence_count"],
    "removed": [],
    "modified": [
      { "path": "agent_state.current_step", "old_value": 11, "new_value": 12 }
    ]
  },
  "metadata": {
    "duration_ms": 1200,
    "token_consumed": 500,
    "trigger_reason": "step_12_completed"
  }
}
```

#### 4.4.3 POST /api/v2/sessions/{id}/checkpoints/{version}/restore -- 从 Checkpoint 恢复

响应体（200 OK）：

```json
{
  "session_id": "uuid",
  "status": "RUNNING",
  "restored_from_version": 42,
  "state": {
    "context_usage": 45000,
    "current_step": 13,
    "current_phase": "ANALYSIS"
  }
}
```

错误：404（Checkpoint 版本不存在）、409（Evidence 链校验失败 / 全部 Checkpoint 不可用）

---

### 4.5 L3 Knowledge 模块

来源文档：M-03

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| GET | `/api/v2/projects/{pid}/knowledge` | 按项目聚合查询知识 | Required | - | `KnowledgeAggregateResponse` (200) | M-03 9.1.2 |
| POST | `/api/v2/projects/{pid}/knowledge` | 语义检索知识 | Required | `KnowledgeSearchRequest` | `KnowledgeSearchResponse` (200) | M-03 9.1.3 |
| GET | `/api/v2/projects/{pid}/knowledge/{kid}` | 查询单条知识详情 | Required | - | `KnowledgeDetailResponse` (200) | M-03 9.1.1 |
| PUT | `/api/v2/projects/{pid}/knowledge/{kid}` | 更新知识 | Required | `KnowledgeUpdateRequest` | `KnowledgeDetailResponse` (200) | M-03 9.2 |
| POST | `/api/v2/projects/{pid}/knowledge/{kid}/deprecate` | 废弃知识 | Required | `DeprecateKnowledgeRequest` | `KnowledgeDetailResponse` (200) | M-03 9.2 |
| GET | `/api/v2/projects/{pid}/knowledge/changelog` | 查询知识变更日志 | Required | - | `ChangelogListResponse` (200) | M-03 9.3.3 |

#### 4.5.1 GET /api/v2/projects/{pid}/knowledge -- 按项目聚合查询

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `freshness` | str | active | 新鲜度过滤 |
| `min_confidence` | float | 0.6 | 最低置信度 |
| `knowledge_types` | str \| null | null | 知识类型过滤（逗号分隔） |

响应体（200 OK）：返回各类型的统计摘要和 top 条目。

```json
{
  "project_id": "uuid",
  "summaries": {
    "glossary": { "total": 42, "active": 38, "avg_confidence": 0.75 },
    "module_profile": { "total": 15, "active": 14, "avg_confidence": 0.68 },
    "constraint": { "total": 8, "active": 7, "avg_confidence": 0.82 },
    "risk": { "total": 5, "active": 5, "avg_confidence": 0.6 },
    "decision": { "total": 3, "active": 3, "avg_confidence": 0.9 },
    "requirement_lineage": { "total": 12, "active": 10, "avg_confidence": 0.7 },
    "incident": { "total": 2, "active": 2, "avg_confidence": 0.5 }
  },
  "top_items": { "..." : "..." }
}
```

#### 4.5.2 POST /api/v2/projects/{pid}/knowledge -- 语义检索

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

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 语义检索查询文本 |
| `knowledge_types` | list[str] | 否 | 限制检索的知识类型 |
| `freshness` | string | 否 | 新鲜度过滤，默认 `active` |
| `min_confidence` | float | 否 | 最低置信度，默认 0.6 |
| `top_k` | int | 否 | 返回条数，默认 10，最大 50 |

响应体（200 OK）：按语义相似度排序的知识条目列表。

#### 4.5.3 GET /api/v2/projects/{pid}/knowledge/{kid} -- 查询知识详情

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `knowledge_type` | str | - | 知识类型（必填，用于定位正确的表） |

响应体（200 OK）：

```json
{
  "id": "uuid",
  "knowledge_type": "glossary",
  "data": {
    "canonical_name": "points_engine",
    "definition": "积分计算引擎",
    "aliases": ["PE"],
    "context": "用于处理积分的累积和扣减",
    "related_modules": ["points"]
  },
  "freshness": "active",
  "confidence_score": 0.8,
  "verification_count": 3,
  "source_session_count": 2,
  "human_verified": false,
  "last_verified_at": "2026-05-20T14:30:00Z",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-05-20T14:30:00Z"
}
```

#### 4.5.4 PUT /api/v2/projects/{pid}/knowledge/{kid} -- 更新知识

请求体：

```json
{
  "knowledge_type": "glossary",
  "patch": {
    "definition": "积分计算引擎，支持同步和异步两种模式",
    "aliases": ["PE", "积分引擎"]
  },
  "evidence_ref": "evidence-uuid",
  "session_id": "session-uuid"
}
```

#### 4.5.5 POST /api/v2/projects/{pid}/knowledge/{kid}/deprecate -- 废弃知识

请求体：

```json
{
  "knowledge_type": "constraint",
  "reason": "该约束已不适用于新架构"
}
```

#### 4.5.6 GET /api/v2/projects/{pid}/knowledge/changelog -- 查询变更日志

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `knowledge_type` | str \| null | null | 按知识类型过滤 |
| `knowledge_id` | uuid \| null | null | 按知识 ID 过滤 |
| `change_type` | str \| null | null | 按变更类型过滤（created/updated/deprecated/superseded/verified/merged） |
| `since` | datetime \| null | null | 起始时间 |
| `until` | datetime \| null | null | 截止时间 |
| `limit` | int | 50 | 返回条数上限 |

响应体（200 OK）：

```json
{
  "items": [
    {
      "change_id": "uuid",
      "knowledge_type": "glossary",
      "knowledge_id": "uuid",
      "change_type": "updated",
      "trigger_session_id": "uuid",
      "changed_fields": { "definition": "旧定义" },
      "changed_at": "2026-05-20T14:30:00Z",
      "operator": "session-uuid"
    }
  ],
  "total": 100,
  "has_more": true
}
```

---

### 4.6 Cognitive Graph 模块

来源文档：M-03（8.3 知识关系存储）、M-04（Cognitive Graph Schema 预留）

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| GET | `/api/v2/projects/{pid}/graph/neighbors` | 查询节点邻居 | Required | - | `NeighborResponse` (200) | M-03 8.3 |
| GET | `/api/v2/projects/{pid}/graph/path` | 查询两节点间路径 | Required | - | `PathResponse` (200) | M-04 |
| GET | `/api/v2/projects/{pid}/graph/subgraph` | 查询子图 | Required | - | `SubgraphResponse` (200) | M-04 |

#### 4.6.1 GET /api/v2/projects/{pid}/graph/neighbors -- 查询节点邻居

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `node_type` | str | 是 | 节点类型（glossary/module_profile/constraint/decision/risk/requirement_lineage/incident） |
| `node_id` | uuid | 是 | 节点 ID |
| `relation_type` | str \| null | 否 | 关系类型过滤 |
| `direction` | str | both | 遍历方向（outgoing/incoming/both） |
| `depth` | int | 1 | 遍历深度（1-3） |
| `limit` | int | 50 | 返回条数上限 |

响应体（200 OK）：

```json
{
  "center": { "type": "constraint", "id": "uuid" },
  "neighbors": [
    {
      "type": "risk",
      "id": "uuid",
      "relation_type": "VIOLATES",
      "confidence": 0.8,
      "direction": "outgoing"
    }
  ],
  "total": 3
}
```

#### 4.6.2 GET /api/v2/projects/{pid}/graph/path -- 查询路径

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `from_type` | str | 是 | 起点节点类型 |
| `from_id` | uuid | 是 | 起点节点 ID |
| `to_type` | str | 是 | 终点节点类型 |
| `to_id` | uuid | 是 | 终点节点 ID |
| `max_depth` | int | 5 | 最大搜索深度 |

响应体（200 OK）：

```json
{
  "from": { "type": "risk", "id": "uuid" },
  "to": { "type": "incident", "id": "uuid" },
  "paths": [
    {
      "length": 2,
      "edges": [
        { "source_type": "risk", "source_id": "uuid", "relation": "MITIGATES", "target_type": "constraint", "target_id": "uuid" },
        { "source_type": "constraint", "source_id": "uuid", "relation": "VIOLATES", "target_type": "incident", "target_id": "uuid" }
      ]
    }
  ],
  "found": true
}
```

#### 4.6.3 GET /api/v2/projects/{pid}/graph/subgraph -- 查询子图

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `node_types` | str | 否 | 节点类型过滤（逗号分隔） |
| `relation_types` | str \| null | 否 | 关系类型过滤（逗号分隔） |
| `min_confidence` | float | 0.0 | 最低置信度过滤 |
| `limit` | int | 100 | 最大节点数 |

响应体（200 OK）：

```json
{
  "nodes": [
    { "type": "risk", "id": "uuid", "label": "并发扣减积分" },
    { "type": "constraint", "id": "uuid", "label": "支付模块禁止直接访问数据库" }
  ],
  "edges": [
    { "source_id": "uuid", "target_id": "uuid", "relation_type": "VIOLATES", "confidence": 0.8 }
  ],
  "total_nodes": 15,
  "total_edges": 22
}
```

---

### 4.7 Event Trace 模块

来源文档：R-03

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| GET | `/api/v2/sessions/{id}/trace` | 查询推理链 Trace | Required | - | `ReasoningTraceResponse` (200) | R-03 10.2 |

#### 4.7.1 GET /api/v2/sessions/{id}/trace -- 查询推理链 Trace

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `step_start` | int \| null | null | 起始步骤（包含） |
| `step_end` | int \| null | null | 结束步骤（包含） |
| `include_cognitive` | bool | true | 是否包含 Cognitive 级事件 |
| `include_context` | bool | false | 是否包含 Context Pipeline 事件 |

响应体（200 OK）：

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
      "payload": { "..." : "..." }
    }
  ],
  "steps": [
    {
      "step": 1,
      "started_event": { "..." : "..." },
      "completed_event": { "..." : "..." },
      "tool_calls": [
        {
          "invoked_event": { "..." : "..." },
          "returned_event": { "..." : "..." }
        }
      ],
      "evidence_added": [ { "..." : "..." } ],
      "dimension_changes": [ { "..." : "..." } ],
      "context_events": [ { "..." : "..." } ]
    }
  ]
}
```

---

### 4.8 Health 模块

| 方法 | 路径 | 描述 | 认证 | 请求体 | 响应体 | 来源 |
|------|------|------|------|--------|--------|------|
| GET | `/api/v2/health` | 服务健康检查 | None | - | `HealthResponse` (200) | 通用 |

响应体（200 OK）：

```json
{
  "status": "healthy",
  "version": "0.8.0",
  "uptime_seconds": 3600,
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "minio": "healthy"
  }
}
```

---

## 5. 服务间调用契约

### 5.1 cognitive-rt --> index-service

来源文档：R-05（10.2 HTTP API 契约）

| 方法 | 路径 | 描述 | 请求体 | 响应体 | 来源 |
|------|------|------|--------|--------|------|
| POST | `/internal/v2/checkpoints` | 创建 Checkpoint | `CreateCheckpointRequest` | `CreateCheckpointResponse` (201) | R-05 10.2.1 |
| GET | `/internal/v2/checkpoints/{session_id}` | 查询 Checkpoint | - | `CheckpointData` (200) | R-05 10.2.2 |
| GET | `/internal/v2/checkpoints` | 查询版本链 | - | `CheckpointListResponse` (200) | R-05 10.2.3 |
| GET | `/internal/v2/checkpoints/{session_id}/diff` | 获取版本间 Diff | - | `CheckpointDiffResponse` (200) | R-05 10.2.4 |

#### 5.1.1 POST /internal/v2/checkpoints -- 创建 Checkpoint

请求体：

```json
{
  "session_id": "uuid",
  "version": 42,
  "previous_version": 41,
  "type": "STEP_COMPLETE",
  "state_summary": { "..." : "..." },
  "diff": { "..." : "..." },
  "hot_state": { "..." : "..." },
  "cold_state_json": "{ ... }",
  "metadata": { "..." : "..." }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | UUID | 是 | 所属 Session |
| `version` | int | 是 | 版本号，同一 Session 内递增 |
| `previous_version` | int \| null | 否 | 前一版本号 |
| `type` | CheckpointType | 是 | 快照类型 |
| `state_summary` | StateSummary | 是 | 状态摘要 |
| `diff` | CheckpointDiff | 否 | 与前一版本差异 |
| `hot_state` | dict | 是 | 热状态完整数据（<= 1MB） |
| `cold_state_json` | string \| null | 否 | 冷状态 JSON 字符串 |
| `metadata` | CheckpointMetadata | 否 | 元数据 |

响应体（201 Created）：

```json
{
  "checkpoint_id": "uuid",
  "version": 42,
  "full_state_uri": "minio://checkpoints/{session_id}/v42/context_snapshot.json",
  "created_at": "2026-06-01T10:00:00Z"
}
```

错误：400（参数校验失败）、409（version 已存在）、503（存储服务不可用）

#### 5.1.2 GET /internal/v2/checkpoints/{session_id} -- 查询 Checkpoint

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `v` | int \| null | null | 版本号，null 返回最新 |
| `include_cold` | bool | false | 是否包含冷状态 |
| `at` | datetime \| null | null | 获取特定时间点的最新版本 |

响应体（200 OK）：

```json
{
  "checkpoint_id": "uuid",
  "session_id": "uuid",
  "version": 42,
  "previous_version": 41,
  "created_at": "2026-06-01T10:00:00Z",
  "type": "STEP_COMPLETE",
  "state_summary": { "..." : "..." },
  "diff": { "..." : "..." },
  "hot_state": { "..." : "..." },
  "cold_state": null,
  "metadata": { "..." : "..." }
}
```

#### 5.1.3 GET /internal/v2/checkpoints -- 查询版本链

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | UUID | 是 | Session ID |
| `limit` | int | 否 | 返回条数上限，默认 20，最大 100 |
| `offset` | int | 否 | 偏移量 |
| `type` | CheckpointType \| null | 否 | 按类型过滤 |

响应体（200 OK）：

```json
{
  "session_id": "uuid",
  "total": 42,
  "items": [
    {
      "checkpoint_id": "uuid",
      "version": 42,
      "type": "STEP_COMPLETE",
      "created_at": "2026-06-01T10:00:00Z",
      "state_summary": { "..." : "..." }
    }
  ],
  "has_more": true
}
```

#### 5.1.4 GET /internal/v2/checkpoints/{session_id}/diff -- 获取版本间 Diff

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `from` | int | 是 | 起始版本号 |
| `to` | int | 是 | 结束版本号 |

响应体（200 OK）：

```json
{
  "from_version": 40,
  "to_version": 42,
  "diffs": [
    {
      "version": 41,
      "type": "STEP_COMPLETE",
      "diff": { "added": [], "removed": [], "modified": [] }
    },
    {
      "version": 42,
      "type": "STEP_COMPLETE",
      "diff": { "added": [], "removed": [], "modified": [] }
    }
  ]
}
```

### 5.2 index-service --> L3 知识写入（内部 API）

来源文档：M-03（9.2 L3 知识写入 API）

| 方法 | 路径 | 描述 | 请求体 | 响应体 | 来源 |
|------|------|------|--------|--------|------|
| POST | `/api/v2/internal/knowledge/append` | 追加知识 | `L3AppendRequest` | `L3KnowledgeBase` (200) | M-03 9.2.1 |
| POST | `/api/v2/internal/knowledge/update` | 更新知识 | `L3UpdateRequest` | `L3KnowledgeBase` (200) | M-03 9.2.2 |
| POST | `/api/v2/internal/knowledge/deprecate` | 废弃知识 | `L3DeprecateRequest` | `L3KnowledgeBase` (200) | M-03 9.2.3 |
| POST | `/api/v2/internal/knowledge/merge` | 合并知识 | `L3MergeRequest` | `L3KnowledgeBase` (200) | M-03 9.2.4 |

---

## 6. WebSocket 协议

### 6.1 连接建立

```
ws://host/api/v2/sessions/{id}/ws?token=jwt_token
```

| 参数 | 说明 |
|------|------|
| `{id}` | Session UUID |
| `token` | JWT Token（查询参数方式传递） |

连接建立时，api-service 校验 JWT 有效性及用户对 Session 的访问权限。

### 6.2 服务端 --> 客户端消息

#### 6.2.1 事件推送

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

#### 6.2.2 心跳

```json
{ "type": "ping" }
```

频率：每 30 秒发送一次。客户端需在 60 秒内回复 `pong`，否则服务端断开连接。

#### 6.2.3 Session 终态通知

```json
{
  "type": "session_ended",
  "data": { "status": "COMPLETED" }
}
```

Session 进入终态后 30 秒，服务端关闭 WebSocket 连接。

#### 6.2.4 断点续传完成

```json
{
  "type": "resync_complete",
  "data": { "events_sent": 5 }
}
```

### 6.3 客户端 --> 服务端消息

#### 6.3.1 订阅过滤

```json
{
  "type": "subscribe",
  "filters": {
    "levels": ["session", "reasoning"],
    "types": ["STEP_COMPLETED", "TOOL_INVOKED", "TOOL_RETURNED"]
  }
}
```

| 过滤维度 | 说明 | 默认值 |
|---------|------|--------|
| `levels` | 订阅的事件级别列表 | 全部级别 |
| `types` | 订阅的事件类型列表 | 全部类型 |

#### 6.3.2 断点续传

```json
{
  "type": "resync",
  "last_sequence": 15
}
```

请求补发 sequence > 15 的事件。api-service 从 PostgreSQL 查询缺失事件后逐条推送，完成后发送 `resync_complete`。

#### 6.3.3 心跳回复

```json
{ "type": "pong" }
```

#### 6.3.4 Chatback 用户追问

```json
{
  "type": "chatback",
  "data": {
    "message": "请重点关注支付模块的并发问题"
  }
}
```

### 6.4 连接生命周期

| 阶段 | 说明 |
|------|------|
| 建立连接 | 客户端携带 JWT Token 建立 WebSocket 连接 |
| 正常通信 | 服务端推送事件，客户端可发送过滤/续传/Chatback 消息 |
| 心跳保活 | 服务端每 30s 发送 ping，客户端需在 60s 内回复 pong |
| 断线重连 | 客户端重连后发送 resync 消息，补发缺失事件 |
| 终态关闭 | Session 进入终态后 30s，服务端主动关闭连接 |
| 多节点广播 | 通过 Redis Pub/Sub 跨节点转发事件，任意 cognitive-rt 实例发布的事件所有 api-service 实例都能收到 |

---

## 7. 新增端点的注册规则

### 7.1 注册前检查清单

新增 API 端点前，必须完成以下检查：

| # | 检查项 | 说明 |
|---|--------|------|
| 1 | 确认端点所属模块 | 端点必须归属于明确的模块（Session / Evidence / Checkpoint / Knowledge / Graph / Trace / Health） |
| 2 | 确认 API 前缀 | 外部 API 使用 `/api/v2/`，内部 API 使用 `/internal/v2/` |
| 3 | 确认认证要求 | 标注 Required / Optional / None / Internal |
| 4 | 定义请求/响应 Schema | 使用 Pydantic 模型定义，字段含中文描述 |
| 5 | 定义错误响应 | 使用统一错误格式，定义错误码（`{RESOURCE}_{ERROR_TYPE}`） |
| 6 | 确认分页方式 | 列表端点使用 `page`/`page_size` 或 `limit`/`offset`（需标注） |
| 7 | 更新本文档 | 在对应模块的端点总表中添加一行，并补充请求/响应 Schema 详情 |

### 7.2 命名规范

| 规范 | 说明 | 示例 |
|------|------|------|
| 路径使用复数名词 | 资源集合用复数 | `/sessions`、`/checkpoints` |
| 路径参数使用单数 | 单个资源用单数 | `/sessions/{id}` |
| 嵌套资源不超过两层 | 避免过深嵌套 | `/sessions/{id}/evidence`（允许），`/sessions/{id}/evidence/{eid}/relations/{rid}`（禁止） |
| 动作端点使用动词 | 非 CRUD 操作用动词 | `/sessions/{id}/start`、`/knowledge/{kid}/deprecate` |
| 查询参数使用蛇形命名 | 与 JSON 字段一致 | `page_size`、`min_confidence` |

### 7.3 版本演进规则

| 变更类型 | 兼容性 | 处理方式 |
|---------|--------|---------|
| 新增端点 | 向后兼容 | 直接添加，更新本文档 |
| 新增可选请求字段 | 向后兼容 | 直接添加，默认值保证旧客户端正常 |
| 新增响应字段 | 向后兼容 | 直接添加，旧客户端忽略新字段 |
| 修改字段语义 | 不兼容 | 新增 API 版本前缀（如 `/api/v3/`） |
| 删除字段 | 不兼容 | 新增 API 版本前缀 |
| 修改字段类型 | 不兼容 | 新增 API 版本前缀 |

### 7.4 文档更新流程

```
1. 在设计文档中定义新端点（请求/响应 Schema + 错误码）
2. 在本文档对应模块的端点总表中添加一行
3. 补充请求/响应 Schema 的详细定义
4. 标注来源文档编号
5. 提交 PR 时，审阅者确认本文档已同步更新
```

---

## 附录 A：端点总览速查表

| 模块 | 方法 | 路径 | 认证 | 来源 |
|------|------|------|------|------|
| Session | POST | `/api/v2/sessions` | Required | R-01 |
| Session | POST | `/api/v2/sessions/{id}/start` | Required | R-01 |
| Session | GET | `/api/v2/sessions/{id}` | Required | R-01 |
| Session | POST | `/api/v2/sessions/{id}/cancel` | Required | R-01 |
| Session | POST | `/api/v2/sessions/{id}/checkpoint` | Required | R-01/R-05 |
| Session | GET | `/api/v2/sessions/{id}/events` | Required | R-01/R-03 |
| Session | WS | `/api/v2/sessions/{id}/ws` | Required | R-01/R-03 |
| Evidence | GET | `/api/v2/sessions/{id}/evidence` | Required | M-01 |
| Evidence | GET | `/api/v2/sessions/{id}/evidence/{eid}` | Required | M-01 |
| Evidence | POST | `/api/v2/sessions/{id}/evidence/{eid}/verify` | Required | M-01 |
| Dimension | GET | `/api/v2/sessions/{id}/dimensions` | Required | M-01/M-02 |
| Checkpoint | GET | `/api/v2/sessions/{id}/checkpoints` | Required | R-05 |
| Checkpoint | GET | `/api/v2/sessions/{id}/checkpoints/{version}` | Required | R-05 |
| Checkpoint | POST | `/api/v2/sessions/{id}/checkpoints/{version}/restore` | Required | R-05 |
| L3 Knowledge | GET | `/api/v2/projects/{pid}/knowledge` | Required | M-03 |
| L3 Knowledge | POST | `/api/v2/projects/{pid}/knowledge` | Required | M-03 |
| L3 Knowledge | GET | `/api/v2/projects/{pid}/knowledge/{kid}` | Required | M-03 |
| L3 Knowledge | PUT | `/api/v2/projects/{pid}/knowledge/{kid}` | Required | M-03 |
| L3 Knowledge | POST | `/api/v2/projects/{pid}/knowledge/{kid}/deprecate` | Required | M-03 |
| L3 Knowledge | GET | `/api/v2/projects/{pid}/knowledge/changelog` | Required | M-03 |
| Cognitive Graph | GET | `/api/v2/projects/{pid}/graph/neighbors` | Required | M-03/M-04 |
| Cognitive Graph | GET | `/api/v2/projects/{pid}/graph/path` | Required | M-04 |
| Cognitive Graph | GET | `/api/v2/projects/{pid}/graph/subgraph` | Required | M-04 |
| Event Trace | GET | `/api/v2/sessions/{id}/trace` | Required | R-03 |
| Health | GET | `/api/v2/health` | None | 通用 |
| Internal | POST | `/internal/v2/checkpoints` | Internal | R-05 |
| Internal | GET | `/internal/v2/checkpoints/{session_id}` | Internal | R-05 |
| Internal | GET | `/internal/v2/checkpoints` | Internal | R-05 |
| Internal | GET | `/internal/v2/checkpoints/{session_id}/diff` | Internal | R-05 |
| Internal | POST | `/api/v2/internal/knowledge/append` | Internal | M-03 |
| Internal | POST | `/api/v2/internal/knowledge/update` | Internal | M-03 |
| Internal | POST | `/api/v2/internal/knowledge/deprecate` | Internal | M-03 |
| Internal | POST | `/api/v2/internal/knowledge/merge` | Internal | M-03 |

---

## 附录 B：EventType 速查表

来源文档：R-03

| 事件类型 | 级别 | 产生者 | 触发时机 |
|---------|------|--------|---------|
| SESSION_CREATED | session | cognitive-rt | Session 创建成功 |
| SESSION_STARTED | session | cognitive-rt | Session 启动 |
| SESSION_CHECKPOINTED | session | cognitive-rt | Checkpoint 写入成功 |
| SESSION_CANCELLING | session | cognitive-rt | Session 正在取消 |
| SESSION_CANCELLED | session | cognitive-rt | Session 已取消 |
| SESSION_TIMEOUT | session | cognitive-rt | Session 执行超时 |
| SESSION_ABORTED | session | cognitive-rt | Session 异常中止 |
| SESSION_WAITING_INPUT | session | cognitive-rt | Session 等待用户输入 |
| SESSION_RESUMED | session | cognitive-rt | Session 恢复执行 |
| SESSION_COMPLETED | session | cognitive-rt | Session 分析完成 |
| SESSION_FAILED | session | cognitive-rt | Session 错误终止 |
| STEP_STARTED | reasoning | cognitive-rt | 推理步骤开始 |
| STEP_COMPLETED | reasoning | cognitive-rt | 推理步骤完成 |
| TOOL_INVOKED | reasoning | cognitive-rt | 工具被调用 |
| TOOL_RETURNED | reasoning | cognitive-rt | 工具调用返回 |
| TOOL_RETRY | reasoning | cognitive-rt | 工具执行重试 |
| TOOL_TIMEOUT | reasoning | cognitive-rt | 工具执行超时 |
| TOOL_PERMISSION_DENIED | reasoning | cognitive-rt | 工具权限被拒绝 |
| TOOL_CHECKPOINT_FAILED | reasoning | cognitive-rt | 工具关联 Checkpoint 写入失败 |
| CONTEXT_COLLECTED | cognitive | cognitive-rt | Context Pipeline Collect 完成 |
| CONTEXT_SCORED | cognitive | cognitive-rt | Context Pipeline Score 完成 |
| EVIDENCE_ADDED | cognitive | cognitive-rt | 新证据添加 |
| DIMENSION_CHANGED | cognitive | cognitive-rt | 维度评估状态变更 |

---

## 附录 C：CheckpointType 速查表

来源文档：R-05

| 类型 | 含义 | 触发条件 |
|------|------|---------|
| STEP_COMPLETE | 推理步骤完成后的快照 | 每个推理步骤完成时 |
| TOOL_PRE | 工具调用前的快照 | ToolRuntime 执行工具前 |
| TOOL_POST | 工具调用后的快照 | ToolRuntime 执行工具后 |
| MANUAL | 用户手动触发的快照 | 用户调用 checkpoint API |
| PERIODIC | 周期性自动快照 | 距上次 Checkpoint 超过 interval |
| CHATBACK_SNAPSHOT | Chatback 对话前的状态快照 | 进入 WAITING_INPUT 状态前 |

---

## 附录 D：EvidenceType 速查表

来源文档：M-01

| 类型 | 含义 | ContextKind 映射 |
|------|------|-----------------|
| code_evidence | 代码结构/依赖/实现事实 | SOURCE_CODE |
| requirement_ref | 需求文档原文引用 | REQUIREMENT |
| architecture_doc | 架构文档/设计文档引用 | ARCH_DOC |
| git_history | Git 提交/分支/变更历史 | GIT_HISTORY |
| memory_ref | L3 项目记忆引用 | MEMORY |
| tool_output | 工具执行的原始输出 | 按工具映射 |
| inference | Agent 推理产生的结论 | INFERRED_KNOWLEDGE |
| constraint | 架构约束/设计规则 | 视来源而定 |
| risk_indicator | 风险指标/信号 | 视来源而定 |
| verification_result | 验证结果 | 视来源而定 |

---

## 附录 E：L3 知识类型速查表

来源文档：M-03

| 知识类型 | 去重键 | 写入策略 | PG 表 |
|---------|--------|---------|-------|
| glossary | `canonical_name` | append + 别名合并 | `glossary` |
| module_profile | `module_name` | update 增量 | `module_profiles` |
| constraint | `constraint_hash` | append + deprecated | `constraints` |
| decision | `decision_id` | append | `decisions` |
| risk | `risk_fingerprint` | append + canonical_id 归并 | `risks` + `risk_evolution` + `risk_mitigations` |
| requirement_lineage | `(requirement_id, version)` | append + 图结构 | `requirement_lineage` + `requirement_relations` |
| incident | `incident_id` | append | `incidents` |
