# C-03 配置注册表（Configuration Registry）

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 全局配置项的权威注册表，为 AI Agent 在 vibe coding 模式下提供完整配置清单，避免遗漏或冲突 |
| 前置文档 | R-01 SESSION_LIFECYCLE、R-02 CONTEXT_PIPELINE、R-03 EVENT_STREAM_SCHEMA、R-04 TOOL_RUNTIME、R-05 CHECKPOINT_DESIGN、M-01 EVIDENCE_MODEL、M-03 PROJECT_COGNITIVE_STATE、M-04 COGNITIVE_GRAPH_SCHEMA |
| 核心目标 | 定义配置体系总览、加载与覆盖规则、完整配置项总表、配置文件格式、环境变量映射、新增配置项注册规则 |
| 文档职责 | What — 有哪些配置项、每个配置项的标识符/类型/默认值/范围/所属 Scope 与 Domain；How — 配置如何加载、如何覆盖、如何扩展 |

---

## 2. 配置体系总览

### 2.1 Scope 层级

配置按四层 Scope 组织，高优先级覆盖低优先级：

| Scope | 优先级 | 存储位置 | 典型内容 |
|-------|--------|---------|---------|
| SYSTEM | 最低（1） | `~/.reqradar/config.yaml` 全局段 | 全局默认值、基础设施参数 |
| PROJECT | 2 | `~/.reqradar/config.yaml` 项目段 + PG `project_configs` 表 | 项目级工具白名单、预算覆盖 |
| USER | 3 | PG `user_configs` 表 | 用户模型偏好、推送偏好 |
| SESSION | 最高（4） | 请求体 `config` 字段 | 单次会话的超时、策略覆盖 |

**解析优先级**：SESSION > USER > PROJECT > SYSTEM

### 2.2 Domain 分类

配置按业务领域分为六个 Domain：

| Domain | 说明 | 涉及模块 |
|--------|------|---------|
| LLM | 大语言模型调用相关配置 | LLM Client、推理循环 |
| TOOL | 工具运行时管控配置 | ToolRuntime、ToolRegistry |
| MCP | 模型上下文协议相关配置（预留） | MCP 适配器 |
| INDEX | 索引、知识治理、图查询配置 | L3 Knowledge、Cognitive Graph、Governance |
| RUNTIME | 运行时核心配置（Session、Pipeline、Event、Checkpoint、Evidence） | CognitiveSession、ContextPipeline、EventStream、Checkpoint、Evidence |
| OUTPUT | 报告输出相关配置 | Report Generation、Template |

### 2.3 Scope x Domain 矩阵

| | LLM | TOOL | MCP | INDEX | RUNTIME | OUTPUT |
|---|-----|------|-----|-------|---------|--------|
| **SYSTEM** | llm_timeout, llm_max_retries | default_timeout, default_max_retries, cache_enabled, rate_limit_enabled | (预留) | governance.*, graph.*, l3_write.*, l3.changelog.* | session.*, pipeline.*, event.*, checkpoint.*, evidence.* | (预留) |
| **PROJECT** | llm_model 覆盖 | 工具白名单、项目级超时覆盖 | (预留) | 项目级 governance 覆盖 | context_budget 覆盖、checkpoint_enabled 覆盖 | template_id |
| **USER** | 用户模型偏好 | 用户工具权限（scopes） | (预留) | - | WebSocket 推送偏好 | 输出格式偏好 |
| **SESSION** | llm_model, llm_temperature | 会话级超时覆盖 | (预留) | - | context_budget, context_strategy, max_execution_time 等 | output_format, template_id |

---

## 3. 配置加载与覆盖规则

### 3.1 加载流程

```
1. 启动时加载 SYSTEM scope
   └── 读取 ~/.reqradar/config.yaml 的全局段

2. 请求时按需加载 PROJECT scope
   └── 读取 config.yaml 项目段 + PG project_configs 表

3. 请求时按需加载 USER scope
   └── 读取 PG user_configs 表

4. 请求时解析 SESSION scope
   └── 读取 API 请求体 config 字段

5. 合并解析：按优先级覆盖，生成最终有效配置
   SESSION > USER > PROJECT > SYSTEM
```

### 3.2 覆盖规则

| 规则 | 说明 |
|------|------|
| 标量覆盖 | 高优先级的非 None 值直接覆盖低优先级值 |
| 列表合并 | `tools` 列表采用完全替换策略（高优先级列表整体替换低优先级列表） |
| 字典合并 | 字典类型采用浅合并策略（高优先级 key 覆盖同 key，保留低优先级独有 key） |
| None 不覆盖 | 高优先级值为 None 时不覆盖低优先级值 |
| 约束校验 | 合并后的最终值必须满足类型、范围约束，否则使用低优先级值并记录 warning |

### 3.3 特殊覆盖场景

| 场景 | 行为 |
|------|------|
| checkpoint_enabled 动态降级 | 运行期间 Checkpoint 写入失败时，可动态将 `checkpoint_enabled` 设为 False（仅当 `checkpoint_degradation = "lenient"`） |
| 运行期间 config 不可修改 | 除 `checkpoint_enabled` 降级外，Session 创建后 config 不可修改 |
| 权重约束 | `pipeline.score.w1 + w2 + w3 + w4 = 1.0`，合并后校验 |
| 比例约束 | `pipeline.current_reasoning_ratio + system_prompt_ratio + history_ratio + tool_output_ratio = 1.0`，合并后校验 |

---

## 4. 配置项总表

### 4.1 LLM Domain

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `session.llm_timeout` | int | 60 | 10-300 | SYSTEM/SESSION | R-01 | LLM 调用超时（秒） |
| `session.llm_max_retries` | int | 3 | 0-10 | SYSTEM/SESSION | R-01 | LLM 调用最大重试次数 |

### 4.2 TOOL Domain

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `tool.default_timeout` | float | 30.0 | 1.0-600.0 | SYSTEM | R-04 | 全局默认工具超时（秒） |
| `tool.default_max_retries` | int | 3 | 0-10 | SYSTEM | R-04 | 全局默认最大重试次数 |
| `tool.default_cache_ttl` | int | 300 | 0-3600 | SYSTEM | R-04 | 全局默认缓存 TTL（秒），0 表示不缓存 |
| `tool.cache_enabled` | bool | True | - | SYSTEM | R-04 | 是否启用结果缓存 |
| `tool.cache_max_size` | int | 1000 | 100-100000 | SYSTEM | R-04 | 缓存最大条目数 |
| `tool.cache_cleanup_interval` | int | 300 | 60-3600 | SYSTEM | R-04 | 缓存清理间隔（秒） |
| `tool.checkpoint_enabled` | bool | True | - | SYSTEM | R-04 | 是否启用 Checkpoint 集成 |
| `tool.event_publishing_enabled` | bool | True | - | SYSTEM | R-04 | 是否启用事件发布 |
| `tool.rate_limit_enabled` | bool | True | - | SYSTEM | R-04 | 是否启用速率限制 |

### 4.3 MCP Domain

当前阶段无配置项。MCP Domain 为模型上下文协议适配器预留，待后续 Phase 实现。

### 4.4 INDEX Domain

#### 4.4.1 知识治理（Governance）

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `governance.freshness.stale_threshold_days` | int | 90 | 7-365 | SYSTEM/PROJECT | M-03 | 知识陈旧阈值（天），超过标记为 stale |
| `governance.freshness.historical_after_days` | int | 180 | 30-730 | SYSTEM/PROJECT | M-03 | 知识归档阈值（天），超过标记为 historical |
| `governance.freshness.stale_check_interval_hours` | int | 24 | 1-168 | SYSTEM | M-03 | 陈旧检查间隔（小时） |
| `governance.confidence.base_score_single_session` | float | 0.3 | 0.0-1.0 | SYSTEM | M-03 | 单次会话知识的基础置信度 |
| `governance.confidence.base_score_multi_session` | float | 0.6 | 0.0-1.0 | SYSTEM | M-03 | 多次会话知识的基础置信度 |
| `governance.confidence.base_score_many_sessions` | float | 0.8 | 0.0-1.0 | SYSTEM | M-03 | 多次以上会话知识的基础置信度 |
| `governance.confidence.human_verified_baseline` | float | 0.9 | 0.0-1.0 | SYSTEM | M-03 | 人工验证后的置信度基线 |
| `governance.confidence.decay_start_days` | int | 60 | 1-365 | SYSTEM | M-03 | 置信度衰减起始天数 |
| `governance.confidence.decay_rate_per_week` | float | 0.05 | 0.0-1.0 | SYSTEM | M-03 | 每周置信度衰减率 |
| `governance.confidence.decay_minimum` | float | 0.1 | 0.0-1.0 | SYSTEM | M-03 | 置信度衰减下限 |
| `governance.verification.interval_sessions` | int | 10 | 1-100 | SYSTEM | M-03 | 验证间隔（会话数） |
| `governance.verification.effective_confidence_boost` | float | 0.05 | 0.0-1.0 | SYSTEM | M-03 | 验证有效时的置信度提升 |
| `governance.verification.ineffective_threshold` | float | 0.05 | 0.0-1.0 | SYSTEM | M-03 | 验证无效的判定阈值 |
| `governance.verification.harmful_threshold` | float | -0.05 | -1.0-0.0 | SYSTEM | M-03 | 验证有害的判定阈值 |
| `governance.injection.min_confidence` | float | 0.6 | 0.0-1.0 | SYSTEM/PROJECT | M-03 | 注入上下文的最低置信度 |
| `governance.injection.default_freshness_filter` | list[str] | ["active"] | - | SYSTEM/PROJECT | M-03 | 默认注入的新鲜度过滤条件 |

#### 4.4.2 L3 写入

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `l3_write.max_retries` | int | 3 | 0-10 | SYSTEM | M-03 | L3 写入最大重试次数 |
| `l3_write.retry_delay_ms` | int | 100 | 10-10000 | SYSTEM | M-03 | L3 写入重试延迟（毫秒） |
| `l3_write.chromadb_retry_max` | int | 5 | 0-20 | SYSTEM | M-03 | ChromaDB 写入最大重试次数 |
| `l3_write.chromadb_retry_delay_ms` | int | 500 | 10-10000 | SYSTEM | M-03 | ChromaDB 写入重试延迟（毫秒） |
| `l3_write.batch_size` | int | 50 | 10-500 | SYSTEM | M-03 | L3 批量写入大小 |
| `l3_write.dependency_snapshot_max` | int | 5 | 1-20 | SYSTEM | M-03 | 依赖快照最大保留数 |

#### 4.4.3 L3 变更日志

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `l3.changelog.retention_days` | int | 365 | 30-3650 | SYSTEM | M-03 | 变更日志保留天数 |
| `l3.changelog.archive_after_days` | int | 90 | 7-365 | SYSTEM | M-03 | 变更日志归档天数 |
| `l3.changelog.cleanup_batch_size` | int | 1000 | 100-10000 | SYSTEM | M-03 | 变更日志清理批量大小 |

#### 4.4.4 认知图（Cognitive Graph）

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `graph.max_path_depth` | int | 5 | 1-20 | SYSTEM | M-04 | 图路径查询最大深度 |
| `graph.max_subgraph_nodes` | int | 1000 | 100-10000 | SYSTEM | M-04 | 子图查询最大节点数 |
| `graph.max_impact_nodes` | int | 2000 | 100-20000 | SYSTEM | M-04 | 影响分析最大节点数 |
| `graph.default_min_confidence` | float | 0.6 | 0.0-1.0 | SYSTEM | M-04 | 图查询默认最低置信度 |
| `graph.confidence_decay_threshold_days` | int | 60 | 1-365 | SYSTEM | M-04 | 图节点置信度衰减起始天数 |
| `graph.confidence_decay_rate` | float | 0.05 | 0.0-1.0 | SYSTEM | M-04 | 图节点每周置信度衰减率 |
| `graph.confidence_min` | float | 0.1 | 0.0-1.0 | SYSTEM | M-04 | 图节点置信度衰减下限 |
| `graph.orphan_detection_days` | int | 30 | 1-365 | SYSTEM | M-04 | 孤立节点检测阈值（天） |
| `graph.auto_discover_enabled` | bool | True | - | SYSTEM | M-04 | 是否启用关系自动发现 |
| `graph.cycle_detection_enabled` | bool | True | - | SYSTEM | M-04 | 是否启用环路检测 |
| `graph.conflict_detection_enabled` | bool | True | - | SYSTEM | M-04 | 是否启用冲突检测 |
| `graph.human_declared_confidence` | float | 0.9 | 0.0-1.0 | SYSTEM | M-04 | 人工声明关系的默认置信度 |
| `graph.inferred_confidence_cap` | float | 0.6 | 0.0-1.0 | SYSTEM | M-04 | 推断关系的置信度上限 |
| `graph.switch_threshold_relations` | int | 100000 | 10000-10000000 | SYSTEM | M-04 | 切换图 DB 的关系数阈值（ADR-015） |
| `graph.switch_threshold_path_ms` | int | 1000 | 100-30000 | SYSTEM | M-04 | 切换图 DB 的路径查询延迟阈值（毫秒） |

### 4.5 RUNTIME Domain

#### 4.5.1 Session 配置

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `session.max_execution_time` | int | 1800 | 60-7200 | SYSTEM/PROJECT/SESSION | R-01 | 最大执行时间（秒） |
| `session.context_budget_default` | int | 128000 | 4096-2000000 | SYSTEM/PROJECT | R-01 | 默认 Token 预算 |
| `session.max_reasoning_steps` | int | 50 | 1-200 | SYSTEM/PROJECT/SESSION | R-01 | 最大推理步骤数 |
| `session.max_tool_calls` | int | 100 | 1-500 | SYSTEM/PROJECT/SESSION | R-01 | 最大工具调用数 |
| `session.step_timeout` | int | 120 | 10-600 | SYSTEM/SESSION | R-01 | 单步推理超时（秒） |
| `session.cancellation_timeout` | int | 60 | 10-300 | SYSTEM | R-01 | 取消清理超时（秒） |
| `session.recovery_max_rollback` | int | 3 | 1-10 | SYSTEM | R-01 | 恢复时最大回退版本数 |
| `session.auto_cleanup_days` | int | 90 | 7-365 | SYSTEM | R-01 | 终态 Session 自动清理天数 |
| `session.ws_heartbeat_interval` | int | 30 | 5-120 | SYSTEM | R-01 | WebSocket 心跳间隔（秒） |
| `session.ws_heartbeat_timeout` | int | 60 | 10-300 | SYSTEM | R-01 | WebSocket 心跳超时（秒） |

#### 4.5.2 Context Pipeline 配置

**全局配置**：

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `pipeline.context_budget_default` | int | 128000 | 4096-2000000 | SYSTEM/PROJECT | R-02 | 默认 Token 预算（与 session.context_budget_default 等价） |
| `pipeline.current_reasoning_ratio` | float | 0.45 | 0.2-0.8 | SYSTEM | R-02 | 当前推理分区占比 |
| `pipeline.system_prompt_ratio` | float | 0.15 | 0.05-0.3 | SYSTEM | R-02 | 系统提示分区占比 |
| `pipeline.history_ratio` | float | 0.25 | 0.1-0.5 | SYSTEM | R-02 | 历史上下文分区占比 |
| `pipeline.tool_output_ratio` | float | 0.15 | 0.05-0.3 | SYSTEM | R-02 | 工具输出预留分区占比 |
| `pipeline.budget_tolerance` | float | 0.05 | 0.0-0.1 | SYSTEM | R-02 | 预算溢出容忍度 |
| `pipeline.compress_max_retries` | int | 2 | 1-5 | SYSTEM | R-02 | 压缩重试次数 |
| `pipeline.collect_timeout` | int | 10 | 1-60 | SYSTEM | R-02 | 单个 Source 收集超时（秒） |
| `pipeline.assembly_timeout` | int | 5 | 1-30 | SYSTEM | R-02 | Assemble 阶段超时（秒） |

**Score 阶段配置**：

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `pipeline.score.w1_semantic` | float | 0.4 | 0.0-1.0 | SYSTEM/PROJECT | R-02 | 语义相似度权重 |
| `pipeline.score.w2_time_decay` | float | 0.15 | 0.0-1.0 | SYSTEM/PROJECT | R-02 | 时间衰减权重 |
| `pipeline.score.w3_user_mark` | float | 0.15 | 0.0-1.0 | SYSTEM/PROJECT | R-02 | 用户标记权重 |
| `pipeline.score.w4_context_kind` | float | 0.3 | 0.0-1.0 | SYSTEM/PROJECT | R-02 | ContextKind 权重 |
| `pipeline.score.half_life.source_code` | int | 90 | 1-365 | SYSTEM | R-02 | SOURCE_CODE 半衰期（天） |
| `pipeline.score.half_life.requirement` | int | 180 | 1-730 | SYSTEM | R-02 | REQUIREMENT 半衰期（天） |
| `pipeline.score.half_life.arch_doc` | int | 120 | 1-365 | SYSTEM | R-02 | ARCH_DOC 半衰期（天） |
| `pipeline.score.half_life.git_history` | int | 30 | 1-180 | SYSTEM | R-02 | GIT_HISTORY 半衰期（天） |
| `pipeline.score.half_life.memory` | int | 60 | 1-365 | SYSTEM | R-02 | MEMORY 半衰期（天） |
| `pipeline.score.half_life.inferred` | int | 7 | 1-90 | SYSTEM | R-02 | INFERRED_KNOWLEDGE 半衰期（天） |

> **约束**：`w1_semantic + w2_time_decay + w3_user_mark + w4_context_kind = 1.0`

**Select 阶段配置**：

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `pipeline.select.min_score` | float | 0.3 | 0.0-0.5 | SYSTEM/PROJECT | R-02 | 最低综合得分阈值 |
| `pipeline.select.max_same_kind_ratio` | float | 0.4 | 0.2-0.8 | SYSTEM | R-02 | 同一 ContextKind 最大占比 |
| `pipeline.select.min_kinds` | int | 2 | 1-6 | SYSTEM | R-02 | 最少 ContextKind 种类数 |
| `pipeline.select.required_kinds` | list[str] | ["SOURCE_CODE"] | - | SYSTEM/PROJECT | R-02 | 必须包含的 ContextKind |

**Compress 阶段配置**：

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `pipeline.compress.summary_max_ratio` | float | 0.3 | 0.1-0.5 | SYSTEM | R-02 | 摘要最大占原始 Token 比例 |
| `pipeline.compress.summary_enabled` | bool | True | - | SYSTEM | R-02 | 是否启用 LLM 摘要压缩 |
| `pipeline.compress.truncate_enabled` | bool | True | - | SYSTEM | R-02 | 是否启用截断兜底 |

**Quality Gate 配置**：

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `pipeline.quality_gate.min_items` | int | 2 | 1-10 | SYSTEM | R-02 | 最少有效条目数 |
| `pipeline.quality_gate.min_semantic_score` | float | 0.65 | 0.0-1.0 | SYSTEM | R-02 | 最低语义得分 |
| `pipeline.quality_gate.min_code_evidence` | int | 1 | 0-5 | SYSTEM | R-02 | 最少代码证据数 |
| `pipeline.quality_gate.low_confidence_min_score` | float | 0.2 | 0.0-0.5 | SYSTEM | R-02 | LOW_CONTEXT_CONFIDENCE 模式的 min_score |

#### 4.5.3 Event Stream 配置

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `event.stream_maxlen` | int | 10000 | 1000-100000 | SYSTEM | R-03 | Redis Streams 每个 Stream 的最大消息数 |
| `event.consumer_group` | str | "event-persisters" | - | SYSTEM | R-03 | 消费者组名称 |
| `event.consumer_batch_size` | int | 10 | 1-100 | SYSTEM | R-03 | 单次消费批量大小 |
| `event.consumer_block_ms` | int | 2000 | 100-10000 | SYSTEM | R-03 | 消费者阻塞等待时间（毫秒） |
| `event.persist_batch_size` | int | 50 | 10-500 | SYSTEM | R-03 | 持久化批量写入大小 |
| `event.persist_flush_interval` | float | 1.0 | 0.1-10.0 | SYSTEM | R-03 | 持久化定时刷新间隔（秒） |
| `event.pending_check_interval` | int | 60 | 10-300 | SYSTEM | R-03 | Pending 列表检查间隔（秒） |
| `event.pending_idle_threshold` | int | 300000 | 60000-1800000 | SYSTEM | R-03 | Pending 消息空闲超时（毫秒） |
| `event.payload_max_size_bytes` | int | 10240 | 1024-102400 | SYSTEM | R-03 | 单个事件 payload 最大字节数 |
| `event.fallback_queue_max_size` | int | 10000 | 1000-100000 | SYSTEM | R-03 | 本地降级队列最大容量 |
| `event.pubsub_enabled` | bool | True | - | SYSTEM | R-03 | 是否启用 Redis Pub/Sub 广播 |
| `event.ws_heartbeat_interval` | int | 30 | 5-120 | SYSTEM | R-03 | WebSocket 心跳间隔（秒） |
| `event.ws_heartbeat_timeout` | int | 60 | 10-300 | SYSTEM | R-03 | WebSocket 心跳超时（秒） |
| `event.ws_session_close_delay` | int | 30 | 5-120 | SYSTEM | R-03 | Session 终态后 WS 连接关闭延迟（秒） |
| `event.stream_cleanup_after_hours` | int | 24 | 1-168 | SYSTEM | R-03 | Session 终态后 Redis Stream 清理时间（小时） |

#### 4.5.4 Checkpoint 配置

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `checkpoint.enabled` | bool | True | - | SYSTEM/PROJECT | R-05 | 是否启用自动 Checkpoint |
| `checkpoint.interval` | int | 300 | 30-3600 | SYSTEM/PROJECT | R-05 | 自动 Checkpoint 间隔（秒） |
| `checkpoint.degradation` | str | "lenient" | "strict"/"lenient" | SYSTEM | R-05 | Checkpoint 失败降级策略 |
| `checkpoint.recovery_mode` | str | "strict" | "strict"/"lenient" | SYSTEM | R-05 | 恢复模式 |
| `checkpoint.recovery_max_rollback` | int | 3 | 1-10 | SYSTEM | R-05 | 恢复时最大回退版本数 |
| `checkpoint.max_active` | int | 20 | 5-100 | SYSTEM | R-05 | 最大活跃 Checkpoint 数 |
| `checkpoint.hot_state_max_bytes` | int | 1048576 | 65536-10485760 | SYSTEM | R-05 | 热状态最大字节数 |
| `checkpoint.archive_days` | int | 30 | 1-365 | SYSTEM | R-05 | Checkpoint 归档天数 |
| `checkpoint.delete_days` | int | 90 | 7-3650 | SYSTEM | R-05 | Checkpoint 删除天数 |
| `checkpoint.keep_last_on_delete` | bool | True | - | SYSTEM | R-05 | 删除时是否保留最新版本 |
| `checkpoint.write_retry_count` | int | 2 | 0-5 | SYSTEM | R-05 | Checkpoint 写入重试次数 |
| `checkpoint.write_retry_delay_ms` | int | 1000 | 100-10000 | SYSTEM | R-05 | Checkpoint 写入重试延迟（毫秒） |
| `checkpoint.cold_state_enabled` | bool | True | - | SYSTEM | R-05 | 是否启用冷状态存储 |
| `checkpoint.orphan_cleanup_hours` | int | 24 | 1-168 | SYSTEM | R-05 | 孤立 Checkpoint 清理时间（小时） |
| `checkpoint.batch_delete_size` | int | 1000 | 100-10000 | SYSTEM | R-05 | 批量删除大小 |

#### 4.5.5 Evidence 配置

| 标识符 | 类型 | 默认值 | 范围 | Scope | 来源文档 | 说明 |
|--------|------|--------|------|-------|---------|------|
| `evidence.max_per_session` | int | 500 | 50-5000 | SYSTEM/PROJECT | M-01 | 单次会话最大证据数 |
| `evidence.max_relations_per_evidence` | int | 20 | 1-100 | SYSTEM | M-01 | 单条证据最大关联数 |
| `evidence.auto_verify_enabled` | bool | True | - | SYSTEM/PROJECT | M-01 | 是否启用自动验证 |
| `evidence.auto_verify_on_creation` | bool | True | - | SYSTEM/PROJECT | M-01 | 创建时是否自动验证 |
| `evidence.min_confidence_for_l3` | float | 0.5 | 0.0-1.0 | SYSTEM/PROJECT | M-01 | 沉淀到 L3 的最低置信度 |
| `evidence.min_confidence_for_conclusion` | float | 0.3 | 0.0-1.0 | SYSTEM/PROJECT | M-01 | 作为结论的最低置信度 |
| `evidence.high_confidence_requires_factual` | bool | True | - | SYSTEM | M-01 | 高置信度是否要求事实支撑 |
| `evidence.chain_validation_on_complete` | bool | True | - | SYSTEM/PROJECT | M-01 | 完成时是否验证证据链 |
| `evidence.chain_max_depth` | int | 10 | 1-50 | SYSTEM | M-01 | 证据链最大深度 |
| `evidence.detail_max_size_bytes` | int | 1048576 | 1024-10485760 | SYSTEM | M-01 | 证据详情最大字节数 |
| `evidence.confidence_boost_auto_verify` | float | 0.1 | 0.0-1.0 | SYSTEM | M-01 | 自动验证的置信度提升 |
| `evidence.confidence_boost_human_verify` | float | 0.15 | 0.0-1.0 | SYSTEM | M-01 | 人工验证的置信度提升 |
| `evidence.confidence_penalty_challenged` | float | 0.2 | 0.0-1.0 | SYSTEM | M-01 | 被质疑的置信度惩罚 |
| `evidence.deprecated_auto_cleanup_days` | int | 90 | 7-3650 | SYSTEM | M-01 | 废弃证据自动清理天数 |

### 4.6 OUTPUT Domain

当前阶段 OUTPUT Domain 的配置项通过 SESSION scope 的请求体字段提供，未纳入全局配置注册表：

| 标识符 | 类型 | 默认值 | Scope | 来源文档 | 说明 |
|--------|------|--------|-------|---------|------|
| `session.output_format` | str | "markdown" | SESSION | R-01 | 输出格式 |
| `session.template_id` | UUID \| None | None | SESSION | R-01 | 报告模板 ID |

---

## 5. 配置文件格式

### 5.1 config.yaml 完整 Schema 示例

```yaml
# ~/.reqradar/config.yaml
# ReqRadar V2 配置文件

# ===== SYSTEM scope 全局配置 =====

# --- LLM Domain ---
llm:
  timeout: 60
  max_retries: 3

# --- TOOL Domain ---
tool:
  default_timeout: 30.0
  default_max_retries: 3
  default_cache_ttl: 300
  cache_enabled: true
  cache_max_size: 1000
  cache_cleanup_interval: 300
  checkpoint_enabled: true
  event_publishing_enabled: true
  rate_limit_enabled: true

# --- INDEX Domain ---
governance:
  freshness:
    stale_threshold_days: 90
    historical_after_days: 180
    stale_check_interval_hours: 24
  confidence:
    base_score_single_session: 0.3
    base_score_multi_session: 0.6
    base_score_many_sessions: 0.8
    human_verified_baseline: 0.9
    decay_start_days: 60
    decay_rate_per_week: 0.05
    decay_minimum: 0.1
  verification:
    interval_sessions: 10
    effective_confidence_boost: 0.05
    ineffective_threshold: 0.05
    harmful_threshold: -0.05
  injection:
    min_confidence: 0.6
    default_freshness_filter:
      - active

l3_write:
  max_retries: 3
  retry_delay_ms: 100
  chromadb_retry_max: 5
  chromadb_retry_delay_ms: 500
  batch_size: 50
  dependency_snapshot_max: 5

l3:
  changelog:
    retention_days: 365
    archive_after_days: 90
    cleanup_batch_size: 1000

graph:
  max_path_depth: 5
  max_subgraph_nodes: 1000
  max_impact_nodes: 2000
  default_min_confidence: 0.6
  confidence_decay_threshold_days: 60
  confidence_decay_rate: 0.05
  confidence_min: 0.1
  orphan_detection_days: 30
  auto_discover_enabled: true
  cycle_detection_enabled: true
  conflict_detection_enabled: true
  human_declared_confidence: 0.9
  inferred_confidence_cap: 0.6
  switch_threshold_relations: 100000
  switch_threshold_path_ms: 1000

# --- RUNTIME Domain ---
session:
  max_execution_time: 1800
  context_budget_default: 128000
  max_reasoning_steps: 50
  max_tool_calls: 100
  step_timeout: 120
  cancellation_timeout: 60
  recovery_max_rollback: 3
  auto_cleanup_days: 90
  ws_heartbeat_interval: 30
  ws_heartbeat_timeout: 60

pipeline:
  context_budget_default: 128000
  current_reasoning_ratio: 0.45
  system_prompt_ratio: 0.15
  history_ratio: 0.25
  tool_output_ratio: 0.15
  budget_tolerance: 0.05
  compress_max_retries: 2
  collect_timeout: 10
  assembly_timeout: 5
  score:
    w1_semantic: 0.4
    w2_time_decay: 0.15
    w3_user_mark: 0.15
    w4_context_kind: 0.3
    half_life:
      source_code: 90
      requirement: 180
      arch_doc: 120
      git_history: 30
      memory: 60
      inferred: 7
  select:
    min_score: 0.3
    max_same_kind_ratio: 0.4
    min_kinds: 2
    required_kinds:
      - SOURCE_CODE
  compress:
    summary_max_ratio: 0.3
    summary_enabled: true
    truncate_enabled: true
  quality_gate:
    min_items: 2
    min_semantic_score: 0.65
    min_code_evidence: 1
    low_confidence_min_score: 0.2

event:
  stream_maxlen: 10000
  consumer_group: "event-persisters"
  consumer_batch_size: 10
  consumer_block_ms: 2000
  persist_batch_size: 50
  persist_flush_interval: 1.0
  pending_check_interval: 60
  pending_idle_threshold: 300000
  payload_max_size_bytes: 10240
  fallback_queue_max_size: 10000
  pubsub_enabled: true
  ws_heartbeat_interval: 30
  ws_heartbeat_timeout: 60
  ws_session_close_delay: 30
  stream_cleanup_after_hours: 24

checkpoint:
  enabled: true
  interval: 300
  degradation: "lenient"
  recovery_mode: "strict"
  recovery_max_rollback: 3
  max_active: 20
  hot_state_max_bytes: 1048576
  archive_days: 30
  delete_days: 90
  keep_last_on_delete: true
  write_retry_count: 2
  write_retry_delay_ms: 1000
  cold_state_enabled: true
  orphan_cleanup_hours: 24
  batch_delete_size: 1000

evidence:
  max_per_session: 500
  max_relations_per_evidence: 20
  auto_verify_enabled: true
  auto_verify_on_creation: true
  min_confidence_for_l3: 0.5
  min_confidence_for_conclusion: 0.3
  high_confidence_requires_factual: true
  chain_validation_on_complete: true
  chain_max_depth: 10
  detail_max_size_bytes: 1048576
  confidence_boost_auto_verify: 0.1
  confidence_boost_human_verify: 0.15
  confidence_penalty_challenged: 0.2
  deprecated_auto_cleanup_days: 90

# ===== PROJECT scope 配置 =====
# 按 project_id 分组，覆盖 SYSTEM scope 的对应项
projects:
  "project-uuid-1":
    llm:
      timeout: 120
    session:
      context_budget_default: 200000
      max_reasoning_steps: 80
    checkpoint:
      enabled: true
      interval: 600
    governance:
      injection:
        min_confidence: 0.7
    pipeline:
      select:
        min_score: 0.35
```

### 5.2 配置文件校验规则

| 规则 | 说明 |
|------|------|
| 类型校验 | 所有配置项必须符合声明的类型（int / float / bool / str / list） |
| 范围校验 | 数值类型必须在声明的范围内 |
| 枚举校验 | 字符串枚举类型必须为合法值（如 checkpoint.degradation 只允许 "strict" / "lenient"） |
| 和约束校验 | Score 权重之和必须为 1.0；Pipeline 分区比例之和必须为 1.0 |
| 未知字段忽略 | config.yaml 中出现未注册的配置项时记录 warning 但不报错 |

---

## 6. 环境变量映射

### 6.1 映射规则

环境变量以 `REQRADAR_` 为前缀，使用 `__`（双下划线）分隔层级：

```
REQRADAR_{SECTION}__{KEY}__{SUBKEY}
```

| 配置项 | 环境变量 |
|--------|---------|
| `session.max_execution_time` | `REQRADAR_SESSION__MAX_EXECUTION_TIME` |
| `pipeline.score.w1_semantic` | `REQRADAR_PIPELINE__SCORE__W1_SEMANTIC` |
| `checkpoint.enabled` | `REQRADAR_CHECKPOINT__ENABLED` |
| `evidence.max_per_session` | `REQRADAR_EVIDENCE__MAX_PER_SESSION` |
| `graph.max_path_depth` | `REQRADAR_GRAPH__MAX_PATH_DEPTH` |

### 6.2 类型转换

| 配置项类型 | 环境变量转换规则 | 示例 |
|-----------|----------------|------|
| int | `int(value)` | `REQRADAR_SESSION__MAX_EXECUTION_TIME=3600` |
| float | `float(value)` | `REQRADAR_PIPELINE__SCORE__W1_SEMANTIC=0.5` |
| bool | `value.lower() in ("true", "1", "yes")` | `REQRADAR_CHECKPOINT__ENABLED=false` |
| str | 直接使用 | `REQRADAR_CHECKPOINT__DEGRADATION=strict` |
| list[str] | 逗号分隔 | `REQRADAR_PIPELINE__SELECT__REQUIRED_KINDS=SOURCE_CODE,REQUIREMENT` |

### 6.3 优先级

环境变量优先级高于 config.yaml 中的 SYSTEM scope 配置，但低于 PROJECT / USER / SESSION scope：

```
SESSION > USER > PROJECT > 环境变量 > SYSTEM (config.yaml)
```

### 6.4 完整映射表

| 环境变量 | 对应配置项 | 类型 |
|---------|-----------|------|
| `REQRADAR_SESSION__MAX_EXECUTION_TIME` | session.max_execution_time | int |
| `REQRADAR_SESSION__CONTEXT_BUDGET_DEFAULT` | session.context_budget_default | int |
| `REQRADAR_SESSION__MAX_REASONING_STEPS` | session.max_reasoning_steps | int |
| `REQRADAR_SESSION__MAX_TOOL_CALLS` | session.max_tool_calls | int |
| `REQRADAR_SESSION__STEP_TIMEOUT` | session.step_timeout | int |
| `REQRADAR_SESSION__CANCELLATION_TIMEOUT` | session.cancellation_timeout | int |
| `REQRADAR_SESSION__LLM_TIMEOUT` | session.llm_timeout | int |
| `REQRADAR_SESSION__LLM_MAX_RETRIES` | session.llm_max_retries | int |
| `REQRADAR_SESSION__WS_HEARTBEAT_INTERVAL` | session.ws_heartbeat_interval | int |
| `REQRADAR_SESSION__WS_HEARTBEAT_TIMEOUT` | session.ws_heartbeat_timeout | int |
| `REQRADAR_PIPELINE__CURRENT_REASONING_RATIO` | pipeline.current_reasoning_ratio | float |
| `REQRADAR_PIPELINE__BUDGET_TOLERANCE` | pipeline.budget_tolerance | float |
| `REQRADAR_PIPELINE__SCORE__W1_SEMANTIC` | pipeline.score.w1_semantic | float |
| `REQRADAR_PIPELINE__SCORE__W2_TIME_DECAY` | pipeline.score.w2_time_decay | float |
| `REQRADAR_PIPELINE__SCORE__W3_USER_MARK` | pipeline.score.w3_user_mark | float |
| `REQRADAR_PIPELINE__SCORE__W4_CONTEXT_KIND` | pipeline.score.w4_context_kind | float |
| `REQRADAR_PIPELINE__SELECT__MIN_SCORE` | pipeline.select.min_score | float |
| `REQRADAR_PIPELINE__QUALITY_GATE__MIN_SEMANTIC_SCORE` | pipeline.quality_gate.min_semantic_score | float |
| `REQRADAR_CHECKPOINT__ENABLED` | checkpoint.enabled | bool |
| `REQRADAR_CHECKPOINT__INTERVAL` | checkpoint.interval | int |
| `REQRADAR_CHECKPOINT__DEGRADATION` | checkpoint.degradation | str |
| `REQRADAR_CHECKPOINT__RECOVERY_MODE` | checkpoint.recovery_mode | str |
| `REQRADAR_CHECKPOINT__COLD_STATE_ENABLED` | checkpoint.cold_state_enabled | bool |
| `REQRADAR_EVENT__STREAM_MAXLEN` | event.stream_maxlen | int |
| `REQRADAR_EVENT__PUBSUB_ENABLED` | event.pubsub_enabled | bool |
| `REQRADAR_EVENT__STREAM_CLEANUP_AFTER_HOURS` | event.stream_cleanup_after_hours | int |
| `REQRADAR_TOOL__DEFAULT_TIMEOUT` | tool.default_timeout | float |
| `REQRADAR_TOOL__CACHE_ENABLED` | tool.cache_enabled | bool |
| `REQRADAR_TOOL__RATE_LIMIT_ENABLED` | tool.rate_limit_enabled | bool |
| `REQRADAR_EVIDENCE__MAX_PER_SESSION` | evidence.max_per_session | int |
| `REQRADAR_EVIDENCE__AUTO_VERIFY_ENABLED` | evidence.auto_verify_enabled | bool |
| `REQRADAR_GOVERNANCE__INJECTION__MIN_CONFIDENCE` | governance.injection.min_confidence | float |
| `REQRADAR_GRAPH__MAX_PATH_DEPTH` | graph.max_path_depth | int |
| `REQRADAR_GRAPH__AUTO_DISCOVER_ENABLED` | graph.auto_discover_enabled | bool |

> 上表仅列出最常用的环境变量映射。所有配置项均可按 `REQRADAR_{SECTION}__{KEY}` 规则映射，将配置项标识符中的 `.` 替换为 `__` 并转为大写即可。

---

## 7. 新增配置项的注册规则

### 7.1 注册检查清单

新增配置项时，必须完成以下全部步骤：

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 确定标识符 | 使用 `{domain}.{subsystem}.{name}` 三级命名，全小写，下划线分隔 |
| 2 | 确定类型 | int / float / bool / str / list[str]，优先使用标量类型 |
| 3 | 确定默认值 | 必须提供合理的默认值，确保系统零配置可启动 |
| 4 | 确定范围 | 数值类型必须声明范围（min-max），bool/str 必须声明合法值 |
| 5 | 确定 Scope | 明确该配置项在哪些 Scope 层级可设置 |
| 6 | 确定 Domain | 归属 LLM / TOOL / MCP / INDEX / RUNTIME / OUTPUT 之一 |
| 7 | 更新本注册表 | 在本文档第 4 章对应 Domain 的表格中新增一行 |
| 8 | 更新 config.yaml Schema | 在第 5 章 Schema 示例中添加对应字段 |
| 9 | 更新环境变量映射 | 在第 6 章映射表中添加对应条目 |
| 10 | 更新 Pydantic 模型 | 在 `infrastructure/config.py` 的对应配置模型中添加字段 |
| 11 | 编写校验逻辑 | 在 Pydantic 模型中添加 `Field(ge=, le=)` 或 `field_validator` |
| 12 | 编写单元测试 | 覆盖默认值、范围边界、类型校验 |

### 7.2 命名规范

| 规则 | 说明 | 示例 |
|------|------|------|
| 三级命名 | `{domain}.{subsystem}.{name}` | `pipeline.score.w1_semantic` |
| 全小写 | 标识符全部小写 | 不允许 `pipeline.Score.W1Semantic` |
| 下划线分隔 | 单词间用下划线连接 | `max_execution_time` |
| 语义明确 | 名称应自解释，避免缩写 | `max_retries` 而非 `mr` |
| 布尔前缀 | bool 类型使用 `enabled` / `is_` 前缀 | `cache_enabled`, `auto_discover_enabled` |
| 时间后缀 | 时间相关配置带单位后缀 | `_timeout`（秒）、`_delay_ms`（毫秒）、`_days`（天）、`_hours`（小时） |
| 大小后缀 | 容量相关配置带单位后缀 | `_max_size_bytes`、`_max_size` |

### 7.3 Scope 分配原则

| 原则 | 说明 |
|------|------|
| SYSTEM 必选 | 所有配置项必须在 SYSTEM scope 有默认值 |
| PROJECT 可选 | 项目级差异化配置才开放 PROJECT scope（如工具白名单、预算覆盖） |
| USER 谨慎 | 仅用户偏好类配置开放 USER scope（如模型偏好、推送偏好） |
| SESSION 受限 | 仅会话创建时可指定的配置开放 SESSION scope（如 context_budget、strategy） |
| 基础设施不开放 | 基础设施参数（如 Redis 连接、缓存大小）仅 SYSTEM scope |

### 7.4 冲突检测

新增配置项时必须检查：

| 检查项 | 说明 |
|--------|------|
| 标识符唯一性 | 新标识符不能与已有配置项重名 |
| Domain 归属一致性 | 同一子系统的配置项应归属同一 Domain |
| Scope 兼容性 | 新配置项的 Scope 层级不能与已有依赖关系的配置项冲突 |
| 默认值一致性 | 同一概念的配置项在不同 Domain 中的默认值必须一致（如 `session.context_budget_default` 与 `pipeline.context_budget_default` 默认值必须相同） |
| 约束一致性 | 新配置项加入后，和约束（如权重之和 = 1.0）仍须满足 |

### 7.5 废弃流程

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 标记 deprecated | 在注册表中标记 `deprecated: true`，添加 `replacement` 字段指向替代配置项 |
| 2 | 保留一个版本 | 废弃配置项至少保留一个大版本的兼容期 |
| 3 | 记录 warning | 读取废弃配置项时记录 warning 日志 |
| 4 | 迁移指南 | 在 CHANGELOG 中提供迁移指南 |
| 5 | 移除 | 兼容期结束后从注册表、Pydantic 模型、config.yaml Schema 中移除 |

---

## 附录 A：配置项统计

| Domain | 配置项数量 |
|--------|-----------|
| LLM | 2 |
| TOOL | 9 |
| MCP | 0（预留） |
| INDEX | 34 |
| RUNTIME | 78 |
| OUTPUT | 2（SESSION scope 请求体字段） |
| **合计** | **125** |

## 附录 B：配置项来源文档索引

| 来源文档 | 配置项数量 | Domain |
|---------|-----------|--------|
| R-01 SESSION_LIFECYCLE | 15 | LLM (2) + RUNTIME (13) |
| R-02 CONTEXT_PIPELINE | 28 | RUNTIME (28) |
| R-03 EVENT_STREAM_SCHEMA | 15 | RUNTIME (15) |
| R-04 TOOL_RUNTIME | 9 | TOOL (9) |
| R-05 CHECKPOINT_DESIGN | 15 | RUNTIME (15) |
| M-01 EVIDENCE_MODEL | 14 | RUNTIME (14) |
| M-03 PROJECT_COGNITIVE_STATE | 22 | INDEX (22) |
| M-04 COGNITIVE_GRAPH_SCHEMA | 15 | INDEX (15) |
