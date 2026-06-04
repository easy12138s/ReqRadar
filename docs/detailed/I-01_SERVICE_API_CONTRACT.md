# I-01 服务间 API 契约

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 服务间内部 API 的完整契约定义，为 P2 服务拆分提供精确的接口规范 |
| 前置文档 | 02_SYSTEM_ARCHITECTURE.md（服务拓扑、调用方向）、03_COGNITIVE_ASSET_MODEL.md（L0-L3 存储策略）、R-05_CHECKPOINT_DESIGN.md（Checkpoint 存储契约）、M-03_PROJECT_COGNITIVE_STATE.md（L3 知识读写契约）、C-04_API_CONTRACT_REGISTRY.md（外部 API 参考风格） |
| 核心目标 | 定义所有服务间 HTTP 调用的完整契约——路径、请求体、响应体、错误码、超时策略、重试策略 |
| 文档职责 | What & How — 服务间如何通信、传递什么数据、错误如何处理 |

---

## 2. 设计总则

### 2.1 基本约定

| 约定 | 说明 |
|------|------|
| API 前缀 | 所有服务间内部 API 使用 `/internal/v2/` 前缀 |
| 认证方式 | 服务间调用使用 `X-Internal-API-Key` Header，不经过 JWT |
| 内容类型 | `application/json` |
| 时间格式 | ISO 8601 UTC，如 `2026-06-01T10:00:00Z` |
| ID 格式 | UUID v4 字符串 |
| 网络隔离 | 内部 API 仅 Docker 内部网络可达，Traefik 不对外暴露 `/internal/` 路由 |
| 超时默认 | HTTP 请求 30s 超时，Checkpoint 写入等写操作 60s 超时 |
| 重试默认 | 幂等 GET 请求重试 3 次，非幂等 POST 默认不重试（由调用方显式处理） |

### 2.2 错误响应格式

与外部 API 一致（详见 C-04 第 3 节）：

```json
{
  "error": {
    "code": "CHECKPOINT_NOT_FOUND",
    "message": "Checkpoint xxx 不存在",
    "details": {}
  }
}
```

### 2.3 服务间调用拓扑

```
cognitive-rt ──HTTP──► index-service      (高频：Checkpoint CRUD / 向量检索 / L3 知识读写)
cognitive-rt ──HTTP──► output-service      (低频：报告生成请求)
cognitive-rt ──HTTP──► integration-service (中频：MCP 工具执行)
api-service  ──HTTP──► auth-service        (高频：JWT 校验 / 用户查询)
api-service  ──HTTP──► cognitive-rt        (中频：Session 创建/查询/取消)
ingestion-svc ──HTTP──► index-service      (中频：L1 事实写入)
integration-svc ──HTTP──► index-service    (中频：项目记忆读取)
integration-svc ──HTTP──► output-service   (低频：MCP 读取报告)
```

---

## 3. cognitive-rt → index-service

**调用频率**：最高频路径，每次推理步骤都会涉及
**超时**：写入 60s，查询 30s
**重试**：GET 幂等重试 3 次，POST 由调用方按 Checkpoint 写入重试策略执行

### 3.1 POST /internal/v2/checkpoints — 创建 Checkpoint

来源：R-05 10.2.1

| 属性 | 值 |
|------|-----|
| 幂等性 | 非幂等（version 递增） |
| 超时 | 60s |
| 重试 | 调用方按 `checkpoint.write_retry_count`（默认 2）重试 |

请求体：

```json
{
  "session_id": "uuid",
  "version": 42,
  "previous_version": 41,
  "type": "STEP_COMPLETE",
  "state_summary": {
    "current_step": 12,
    "current_phase": "ANALYSIS",
    "context_usage": 45000,
    "evidence_count": 8,
    "dimensions_completed": ["completeness"],
    "dimensions_pending": ["feasibility", "risk"]
  },
  "diff": {
    "added": ["evidence_count"],
    "removed": [],
    "modified": [{"path": "agent_state.current_step", "old": 11, "new": 12}]
  },
  "hot_state": {
    "agent_state": {"current_step": 12, "current_phase": "ANALYSIS"},
    "evidence_state": {"total": 8, "by_type": {"code_evidence": 5}, "avg_confidence": 0.72},
    "dimension_state": {"completeness": "sufficient", "risk": "in_progress"}
  },
  "cold_state_json": "{...context snapshot...}",
  "metadata": {"duration_ms": 1200, "token_consumed": 500, "trigger": "step_12_completed"}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | UUID | 是 | |
| `version` | int | 是 | 同一 Session 内严格递增 |
| `previous_version` | int\|null | 否 | |
| `type` | CheckpointType | 是 | STEP_COMPLETE/TOOL_PRE/TOOL_POST/MANUAL/PERIODIC |
| `state_summary` | dict | 是 | 状态摘要（用于列表查询） |
| `diff` | dict | 否 | 与前一版本的差异 |
| `hot_state` | dict | 是 | 热状态数据，≤ 1MB |
| `cold_state_json` | string\|null | 否 | 冷状态完整 JSON |
| `metadata` | dict | 否 | 元数据 |

响应体 201：

```json
{
  "checkpoint_id": "uuid",
  "version": 42,
  "full_state_uri": "minio://checkpoints/{session_id}/v42/context_snapshot.json",
  "created_at": "2026-06-01T10:00:00Z"
}
```

错误：400/409(version 冲突)/503(MinIO 不可用)

### 3.2 GET /internal/v2/checkpoints/{session_id} — 查询 Checkpoint

| 属性 | 值 |
|------|-----|
| 幂等性 | 幂等 |
| 超时 | 30s |
| 重试 | 3 次 |

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `v` | int\|null | null | 版本号，null=最新 |
| `include_cold` | bool | false | 是否返回冷状态数据 |
| `at` | datetime\|null | null | 获取特定时间点的最新版本 |

响应体 200（include_cold=false）：

```json
{
  "checkpoint_id": "uuid",
  "session_id": "uuid",
  "version": 42,
  "previous_version": 41,
  "created_at": "2026-06-01T10:00:00Z",
  "type": "STEP_COMPLETE",
  "state_summary": {"current_step": 12, "current_phase": "ANALYSIS", "...": "..."},
  "diff": {"...": "..."},
  "hot_state": {"agent_state": {...}, "evidence_state": {...}, "dimension_state": {...}},
  "cold_state": null,
  "metadata": {"...": "..."}
}
```

响应体 200（include_cold=true）：追加 `"cold_state": {<完整上下文快照>}`。

错误：404（Session 无 Checkpoint）

### 3.3 GET /internal/v2/checkpoints — 查询版本链列表

| 属性 | 值 |
|------|-----|
| 幂等性 | 幂等 |
| 超时 | 30s |
| 重试 | 3 次 |

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | UUID | 是 | |
| `limit` | int | 否 | 默认 20，最大 100 |
| `offset` | int | 否 | 默认 0 |
| `type` | CheckpointType\|null | 否 | 按类型过滤 |

响应体 200：

```json
{
  "session_id": "uuid",
  "total": 42,
  "items": [{"checkpoint_id": "uuid", "version": 42, "type": "STEP_COMPLETE", "state_summary": {...}}],
  "has_more": true
}
```

### 3.4 GET /internal/v2/checkpoints/{session_id}/diff — 比较两个版本

| 参数 | 类型 | 必填 |
|------|------|------|
| `from` | int | 是 |
| `to` | int | 是 |

响应体 200：

```json
{
  "from_version": 40, "to_version": 42,
  "diffs": [{"version": 41, "type": "STEP_COMPLETE", "diff": {...}}, ...]
}

```

---

## 3.5 POST /internal/v2/search/vector — 向量检索

| 属性 | 值 |
|------|-----|
| 幂等性 | 幂等 |
| 超时 | 30s |

请求体：

```json
{
  "project_id": "uuid",
  "collection": "requirements",
  "query_text": "支付模块并发安全",
  "top_k": 10,
  "filters": {"chunk_type": "paragraph"},
  "min_score": 0.5
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | UUID | 是 | |
| `collection` | string | 是 | requirements / code |
| `query_text` | string | 是 | |
| `top_k` | int | 否 | 默认 10 |
| `filters` | dict | 否 | ChromaDB where 条件 |
| `min_score` | float | 否 | 最低相似度阈值 |

响应体 200：

```json
{
  "results": [
    {
      "id": "chunk-uuid",
      "content": "支付回调处理函数...",
      "metadata": {"file_path": "src/pay/callback.py", "chunk_type": "paragraph"},
      "score": 0.87
    }
  ],
  "query_time_ms": 45
}
```

---

### 3.6 POST /internal/v2/knowledge/append — 追加 L3 知识

| 属性 | 值 |
|------|-----|
| 幂等性 | 依赖 knowledge_type 的去重键 |
| 超时 | 60s |
| 重试 | 按 `l3_write.max_retries`（默认 3） |

请求体：

```json
{
  "project_id": "uuid",
  "knowledge_type": "glossary",
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

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | UUID | 是 | |
| `knowledge_type` | string | 是 | glossary / module_profile / constraint / decision / risk / requirement_lineage / incident |
| `payload` | dict | 是 | 知识内容，各类型结构见 M-03 |
| `evidence_ref` | string | 是 | 支撑该知识的 L2 Evidence ID |
| `session_id` | UUID | 是 | 触发沉淀的 Session |

响应体 201：

```json
{
  "id": "uuid",
  "knowledge_type": "glossary",
  "freshness": "active",
  "confidence_score": 0.3,
  "created_at": "2026-06-01T10:00:00Z"
}
```

### 3.7 POST /internal/v2/knowledge/update — 更新 L3 知识

同 append 接口，但使用 `update` 端点。payload 为 patch 字典。

### 3.8 POST /internal/v2/knowledge/deprecate — 废弃 L3 知识

请求体：

```json
{
  "project_id": "uuid",
  "knowledge_type": "constraint",
  "knowledge_id": "uuid",
  "reason": "架构升级后此约束不再适用"
}
```

### 3.9 POST /internal/v2/knowledge/merge — 合并 L3 知识

请求体：

```json
{
  "project_id": "uuid",
  "knowledge_type": "glossary",
  "knowledge_ids": ["uuid1", "uuid2"],
  "strategy": "keep_newer",
  "payload_overrides": {"canonical_name": "points_engine"}
}
```

### 3.10 GET /internal/v2/knowledge/query — 查询 L3 知识（供 Context Pipeline 注入）

| 属性 | 值 |
|------|-----|
| 幂等性 | 幂等 |
| 超时 | 10s |

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | UUID | 是 | |
| `knowledge_types` | string | 否 | 逗号分隔，如 "glossary,constraint,risk" |
| `freshness` | string | 否 | 默认 "active" |
| `min_confidence` | float | 否 | 默认 0.6 |
| `limit` | int | 否 | 默认 50 |

响应体 200：

```json
{
  "items": [
    {
      "id": "uuid",
      "knowledge_type": "glossary",
      "data": {"canonical_name": "points_engine", "definition": "积分计算引擎"},
      "freshness": "active",
      "confidence_score": 0.8,
      "verification_count": 3
    }
  ],
  "total": 5
}
```

---

## 4. cognitive-rt → output-service

### 4.1 POST /internal/v2/reports/generate — 请求生成报告

| 属性 | 值 |
|------|-----|
| 幂等性 | 非幂等 |
| 超时 | 120s |

请求体：

```json
{
  "session_id": "uuid",
  "template_id": "uuid",
  "output_format": "markdown"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | UUID | 是 | |
| `template_id` | UUID\|null | 否 | null 使用默认模板 |
| `output_format` | string | 否 | markdown / html / json，默认 markdown |

响应体 202（异步）：

```json
{
  "task_id": "uuid",
  "status": "queued",
  "estimated_duration_ms": 5000
}
```

### 4.2 GET /internal/v2/reports/{task_id}/status — 查询报告生成状态

响应体 200：

```json
{
  "task_id": "uuid",
  "status": "completed",
  "output_uri": "minio://reports/{session_id}/report.md",
  "format": "markdown",
  "size_bytes": 12345,
  "completed_at": "2026-06-01T10:05:00Z"
}
```

---

## 5. api-service → auth-service

### 5.1 POST /internal/v2/auth/verify — 校验 JWT

| 属性 | 值 |
|------|-----|
| 幂等性 | 幂等 |
| 超时 | 5s |
| 重试 | 3 次（关键路径） |

请求体：

```json
{
  "token": "eyJhbGciOi..."
}
```

响应体 200（有效）：

```json
{
  "valid": true,
  "user": {
    "user_id": "uuid",
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "is_active": true
  },
  "jti": "uuid",
  "expires_at": "2026-06-01T14:00:00Z"
}
```

响应体 200（无效）：

```json
{
  "valid": false,
  "reason": "TOKEN_EXPIRED"
}
```

### 5.2 POST /internal/v2/auth/check-permission — 权限检查

| 属性 | 值 |
|------|-----|
| 幂等性 | 幂等 |
| 超时 | 5s |

请求体：

```json
{
  "user_id": "uuid",
  "resource_type": "project",
  "resource_id": "uuid",
  "action": "read"
}
```

响应体 200：

```json
{
  "allowed": true,
  "reason": null
}
```

### 5.3 GET /internal/v2/users/{user_id} — 查询用户

响应体 200：

```json
{
  "user_id": "uuid",
  "username": "admin",
  "email": "admin@example.com",
  "role": "admin",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

## 6. api-service → cognitive-rt

### 6.1 POST /internal/v2/sessions — 创建 Session

| 属性 | 值 |
|------|-----|
| 幂等性 | 非幂等 |
| 超时 | 10s |

请求体：同外部 API `POST /api/v2/sessions`（C-04 第 4.1.1 节）。

响应体 201：同 C-04 第 4.1.1 节。

### 6.2 GET /internal/v2/sessions/{id} — 查询 Session

响应体 200：同 C-04 第 4.1.3 节。

### 6.3 POST /internal/v2/sessions/{id}/cancel — 取消 Session

响应体 202：同 C-04 第 4.1.4 节。

### 6.4 GET /internal/v2/sessions/{id}/events — 查询事件流

响应体 200：同 C-04 第 4.1.6 节。

### 6.5 GET /internal/v2/sessions/{id}/evidence — 查询证据

响应体 200：同 C-04 第 4.2.1 节。

### 6.6 GET /internal/v2/sessions/{id}/dimensions — 查询维度状态

响应体 200：同 C-04 第 4.3.1 节。

---

## 7. ingestion-service → index-service

### 7.1 POST /internal/v2/l0/raw-context — 注册 L0 原始上下文

| 属性 | 值 |
|------|-----|
| 幂等性 | 按 content_hash 去重 |
| 超时 | 30s |

请求体：

```json
{
  "project_id": "uuid",
  "type": "document",
  "uri": "minio://projects/{project_id}/l0/document/20260601/requirements.pdf",
  "original_filename": "requirements.pdf",
  "size_bytes": 204800,
  "content_hash": "sha256hex",
  "source": "upload"
}
```

响应体 201：

```json
{
  "id": "uuid",
  "uri": "minio://...",
  "ingested_at": "2026-06-01T10:00:00Z"
}
```

### 7.2 POST /internal/v2/l1/chunks — 批量写入 Chunk

| 属性 | 值 |
|------|-----|
| 幂等性 | 按 embedding_id 去重 |
| 超时 | 60s |

请求体：

```json
{
  "project_id": "uuid",
  "raw_context_id": "uuid",
  "chunks": [
    {
      "chunk_type": "paragraph",
      "content": "积分计算引擎负责...",
      "text_uri": "minio://...",
      "position": 1,
      "offset_start": 0,
      "offset_end": 150,
      "section_path": "2.1 > 2",
      "embedding_id": "chroma-id-1"
    }
  ]
}
```

响应体 201：

```json
{
  "inserted": 15,
  "skipped_duplicates": 0,
  "chunk_ids": ["uuid1", "uuid2", "..."]
}
```

### 7.3 POST /internal/v2/l1/code-modules — 批量写入代码模块

请求体：

```json
{
  "project_id": "uuid",
  "modules": [
    {
      "module_type": "class",
      "qualified_name": "reqradar.web.api.auth",
      "short_name": "auth",
      "file_path": "reqradar/web/api/auth.py",
      "line_start": 1,
      "line_end": 150,
      "signature": "class AuthRouter:",
      "docstring": "认证路由",
      "embedding_id": "chroma-id-mod-1"
    }
  ]
}
```

### 7.4 POST /internal/v2/l1/git-commits — 批量写入 Git 提交

请求体（同 chunks 批处理模式）：

```json
{
  "project_id": "uuid",
  "commits": [
    {
      "commit_hash": "abc123",
      "author": "John Doe",
      "author_email": "john@example.com",
      "committed_at": "2026-05-15T10:00:00Z",
      "message": "fix: resolve payment callback idempotency",
      "changed_files": [{"path": "src/pay/callback.py", "additions": 10, "deletions": 3}],
      "diff_summary": "增加了幂等键校验"
    }
  ]
}
```

---

## 8. integration-service → index-service

### 8.1 GET /internal/v2/memory/query — 查询项目记忆（供 MCP 使用）

| 属性 | 值 |
|------|-----|
| 幂等性 | 幂等 |
| 超时 | 10s |

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | UUID | 是 | |
| `topics` | string | 否 | 逗号分隔的记忆主题 |
| `knowledge_types` | string | 否 | 同 L3 查询 |

响应体 200：

```json
{
  "project_id": "uuid",
  "glossary": [{"term": "points_engine", "definition": "..."}],
  "constraints": [{"description": "支付模块不允许直接访问数据库"}],
  "risks": [{"title": "并发扣减积分", "severity": "high"}],
  "query_time_ms": 45
}
```

---

## 9. integration-service → output-service

### 9.1 GET /internal/v2/reports/{session_id}/latest — 获取最新报告（供 MCP 使用）

响应体 200：

```json
{
  "session_id": "uuid",
  "output_uri": "minio://reports/{session_id}/report.md",
  "format": "markdown",
  "size_bytes": 12345,
  "generated_at": "2026-06-01T10:05:00Z"
}
```

---

## 10. 重试与降级策略

### 10.1 调用失败处理矩阵

| 调用方 | 被调用方 | 失败处理 |
|--------|---------|---------|
| cognitive-rt → index-service（Checkpoint 写入） | 按 `checkpoint.degradation` 策略：strict=中断 Session / lenient=继续无 Checkpoint 模式 |
| cognitive-rt → index-service（向量检索） | 降级：跳过该检索源，继续分析 |
| cognitive-rt → index-service（L3 查询） | 降级：跳过 L3 注入，仅使用 L1 上下文 |
| cognitive-rt → output-service | 降级：报告生成排队失败，Session 标记 completed_no_report |
| api-service → auth-service | 不可降级：校验失败直接返回 401 |
| api-service → cognitive-rt | 返回 503，前端提示服务暂不可用 |
| ingestion-service → index-service | 排队重试，最大 10 次，间隔递增 |

### 10.2 熔断策略

| 服务 | 熔断条件 | 半开探测 |
|------|---------|---------|
| index-service | 60s 内失败率 > 50% 且请求数 > 10 | 30s 后发 1 个探测请求 |
| auth-service | 30s 内失败率 > 30% 且请求数 > 20 | 15s 后发 1 个探测请求 |
| output-service | 120s 内失败率 > 60% 且请求数 > 5 | 60s 后发 1 个探测请求 |

---

## 11. 新增服务间端点注册规则

1. 内部端点的请求/响应 Schema 定义在 `reqradar-kernel` 中（与外部端点共用 Pydantic 模型）
2. 新增端点时更新本文档对应章节
3. 端点优先使用已有的 C-04 外部 API 响应格式，仅内部专用逻辑新增格式
4. 所有内部端点必须标注调用频率（high / medium / low）和降级策略

---

## 附录 A：Internal-API-Key 管理

| 属性 | 说明 |
|------|------|
| 生成方式 | 启动时由部署脚本生成 256-bit 随机字符串 |
| 传递方式 | `X-Internal-API-Key: {key}` Header |
| 存储方式 | Docker secrets 或环境变量 `INTERNAL_API_KEY` |
| 轮换 | 支持双 key 模式，新旧 key 共存 5 分钟用于平滑切换 |
| 验证 | 各服务启动时加载，中间件层统一校验 |

## 附录 B：调用频率速查

| 调用方向 | 频率 | QPS 估算 |
|---------|------|---------|
| cognitive-rt → index-service（Checkpoint 写入） | 每个推理步骤 1 次 | 0.1/session |
| cognitive-rt → index-service（向量检索） | 每个推理步骤 1-3 次 | 0.3/session |
| cognitive-rt → index-service（L3 查询） | 每个 Session 1 次（Collect 阶段） | 0.05/session |
| cognitive-rt → output-service | 每个 Session 1 次 | 0.05/session |
| api-service → auth-service（JWT 校验） | 每次外部 API 请求 1 次 | 10-100/s |
| api-service → cognitive-rt | 每次 Session CRUD 1 次 | 1-5/s |
