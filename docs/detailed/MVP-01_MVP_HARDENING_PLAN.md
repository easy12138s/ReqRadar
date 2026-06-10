# ReqRadar V2 — 核心功能补全实施计划

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v2.0 |
| 文档定位 | 基于 36 项问题真实验证结果，重新定义实施计划——从"bug 修复"正名为"核心功能补全" |
| 前置文档 | MVP-01_MVP_HARDENING_PLAN.md（v1.0，已被本计划替代）、MVP-1_BUG_LOG.md |
| 核心目标 | 把"LLM 裸跑出报告的 Demo"补全为"上下文增强 + 知识沉淀 + 数据持久化的认知运行时" |
| 文档职责 | 定义 4 个阶段的任务清单、依赖关系、验收标准 |

---

## 一、现状诊断

### 1.1 E2E 验证结论

MVP-1 端到端测试已通过（9 步全链路 PASS），但验证的是**链路可达性**而非**功能正确性**：

```
设计路径（未接通）：
  Runner → ContextPipeline.execute() → Sources.collect() → Strategy.get_weights()
         → score_items(weights) → select → compress → assemble → 注入 prompt
  推理完成 → L3Writer.append() → 知识沉淀 → 下次推理可检索

实际路径（E2E 跑通的）：
  Runner → build_dynamic_system_prompt(f-string) → LLM 裸跑 → 出报告
```

### 1.2 36 项问题分类

| 类别 | 数量 | 本质 | 阶段 |
|------|------|------|------|
| A 类：已设计未接通 | 7 | 核心功能缺失，代码存在但从未被主流程调用 | Phase 2 |
| B 类：已实现未持久化 | 3 | 功能半成品，内存版能工作但重启丢数据 | Phase 3 |
| C 类：类型/接口不匹配 | 6 | 集成未做，接口契约未对齐 | Phase 1 |
| D 类：实现错误 | 4 | 真正的 bug | Phase 1 |
| E 类：代码质量 | 16 | 死代码、命名不一致、导出缺失 | Phase 4 |

### 1.3 各层完成度

| 层次 | 已完成 | 未完成 |
|------|--------|--------|
| L0 原始上下文 | 文档摄取 ✅、PDF 解析 ✅、向量化 ✅ | — |
| L1 结构化事实 | PG 存储 ✅、ChromaDB 索引 ✅ | — |
| L2 推理过程 | Session 生命周期 ✅、LLM 调用 ✅、报告生成 ✅ | Pipeline 空转、Sources 未注入、策略未调用、Evidence 未收集 |
| L3 持久知识 | L3Writer 类实现 ✅、index-service API ✅ | cognitive_rt 从未调用 L3 写入 |
| 推理增强 | f-string prompt 模板 ✅ | 上下文组装、策略权重、质量门控、token 预算——全部死代码 |
| 数据持久化 | 项目/文档 PG 持久化 ✅ | Session/Event/Checkpoint 全内存，重启丢数据 |

---

## 二、实施阶段总览

```
Phase 1: 接口对齐 + 基础修复 ──→ Phase 2: 认知管线接通 ──→ Phase 3: 持久化闭环 ──→ Phase 4: 代码质量
  (C类 + D类, 10项)              (A类, 7项)               (B类, 3项)           (E类, 16项)
  打地基                          接神经                    存数据               打扫卫生
```

**阶段依赖关系**：
- Phase 1 是 Phase 2 的前置（接口不对齐，管线接不通）
- Phase 2 是 Phase 3 的前置（管线不通，持久化无意义）
- Phase 4 可穿插在 Phase 1-3 间隙做，但优先级最低

---

## Phase 1：接口对齐 + 基础修复

> **目标**：消除所有类型/接口不匹配和实现错误，为 Phase 2 管线接通扫清障碍。

### P1-1: project_id 类型统一为 str（#11）

| 项目 | 内容 |
|------|------|
| 问题 | `analysis_agent.py:38` 声明 `project_id: int`，实际传入 UUID 字符串 |
| 修复 | 将 `AnalysisAgent.__init__` 的 `project_id: int` 改为 `project_id: str` |
| 涉及文件 | `reqradar/cognitive_rt/cognition/analysis_agent.py` |
| 验收 | `grep -n "project_id.*int" reqradar/cognitive_rt/cognition/analysis_agent.py` 无结果 |

### P1-2: StateSummary 类型对齐（#9）

| 项目 | 内容 |
|------|------|
| 问题 | `tool_runtime.py:374-377` 传 `state_summary={...}` dict，但接收方期望 StateSummary 对象 |
| 修复 | 改为构造 `StateSummary(...)` 对象传入；若 StateSummary 无合适构造函数，则让接收方兼容 dict |
| 涉及文件 | `reqradar/cognitive_rt/runtime/tool_runtime.py` |
| 验收 | `mypy reqradar/cognitive_rt/runtime/tool_runtime.py` 无类型错误（或 ruff check 通过） |

### P1-3: DimensionStatus 枚举对齐（#10）

| 项目 | 内容 |
|------|------|
| 问题 | `dimension.py:87-92` `from_snapshot()` 存字符串，但与 `DimensionStatus` 枚举比较 |
| 修复 | `from_snapshot()` 中将字符串转为 `DimensionStatus(status_str)` 枚举值 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/dimension.py` |
| 验收 | checkpoint 恢复后 `dim.status == DimensionStatus.COMPLETED` 判断正确 |

### P1-4: EvidenceRecord.content 长度扩展（#20）

| 项目 | 内容 |
|------|------|
| 问题 | `EvidenceRecord.content` 为 `String(200)`，长证据被截断 |
| 修复 | 改为 `Text`（无长度限制） |
| 涉及文件 | `reqradar/kernel/models.py` |
| 迁移 | 新增 Alembic 迁移 `V2_P1_extend_evidence_content.py`：`ALTER TABLE evidence_records ALTER COLUMN content TYPE TEXT` |
| 验收 | 可存储 10000+ 字符的证据内容 |

### P1-5: L3Knowledge.project_id 改为 UUID FK（#21）

| 项目 | 内容 |
|------|------|
| 问题 | `L3Knowledge.project_id` 是 `String(36)` 而非 UUID 外键，与其他模型不一致 |
| 修复 | 改为 `ForeignKey("projects.id")` 的 UUID 列 |
| 涉及文件 | `reqradar/kernel/models.py` |
| 迁移 | 新增 Alembic 迁移 |
| 验收 | `SELECT conname FROM pg_constraint WHERE conrelid = 'l3_knowledge'::regclass AND contype = 'f'` 返回 FK 约束 |

### P1-6: ToolResultCache 缓存 key 嵌套 dict 处理（#18）

| 项目 | 内容 |
|------|------|
| 问题 | `hash(frozenset(params.items()))` 在 params 含嵌套 dict 时 TypeError |
| 修复 | 用 `json.dumps(params, sort_keys=True)` 生成稳定字符串 key |
| 涉及文件 | `reqradar/cognitive_rt/runtime/tool_runtime.py` |
| 验收 | `cache_key({"a": {"b": 1}})` 不崩溃 |

### P1-7: ToolResultCache 改为 LRU（#19）

| 项目 | 内容 |
|------|------|
| 问题 | 缓存是 FIFO（`next(iter(self._cache))`），文档声称 LRU |
| 修复 | 改用 `collections.OrderedDict` + `move_to_end()` 实现 LRU |
| 涉及文件 | `reqradar/cognitive_rt/runtime/tool_runtime.py` |
| 验收 | 访问已有 key 后，该 key 不再是最先被淘汰的 |

### P1-8: asyncio.run 反模式修复（#7）→ 合入 P2-1

| 项目 | 内容 |
|------|------|
| 问题 | `analysis_agent.py:176-201` 用 `ThreadPoolExecutor` + `asyncio.run` 嵌套事件循环 |
| 评估 | `asyncio.run` 出现在 `_get_context_text_via_pipeline()` 中，因为该方法是同步函数但需调异步 `pipeline.execute()`。P2-1 将 Pipeline 提升到 Runner 层（异步环境）后，`_get_context_text_via_pipeline()` 整个方法可删除，`asyncio.run` 自然消失 |
| 修复 | **与 P2-1 合并执行**。P2-1 完成后，删除 `_get_context_text_via_pipeline()` 方法及 `get_context_text()` 中的分支逻辑 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/analysis_agent.py` |
| 验收 | `grep -rn "asyncio.run\|ThreadPoolExecutor" reqradar/cognitive_rt/cognition/` 输出为空 |

### P1-9: Redis 内存模式支持 TTL（#22）

| 项目 | 内容 |
|------|------|
| 问题 | `redis_client.py` 内存降级模式忽略 `ex` 参数，缓存永不过期 |
| 修复 | 内存模式 `set()` 记录 `(value, expire_at)` 元组，`get()` 检查过期 |
| 涉及文件 | `reqradar/infrastructure/redis_client.py` |
| 验收 | `client.set("k", "v", ex=1); time.sleep(1.1); assert client.get("k") is None` |

### P1-10: 服务间调用增加重试（#23）

| 项目 | 内容 |
|------|------|
| 问题 | `context_sources.py` 中 httpx 调用无 retry，级联失败 |
| 修复 | 引入 `httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=3))` 或简单 for-retry 循环 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/context_sources.py` |
| 验收 | 模拟 2 次连接失败后第 3 次成功，请求仍能完成 |

### Phase 1 验收标准

- [ ] E2E 冒烟测试仍通过（回归验证）
- [ ] `ruff check reqradar/` 无新增错误
- [ ] Phase 1 新增/修改的代码有对应单元测试
- [ ] Alembic 迁移可执行

---

## Phase 2：认知管线接通

> **目标**：把 Context Pipeline 从"空转"变为"真正驱动推理"，让推理结果受上下文增强而非纯靠 LLM 裸跑。

### P2-1: Context Pipeline 输出接入 Runner（#1）⭐ 最关键

| 项目 | 内容 |
|------|------|
| 问题 | `runner.py:500-517` 用 f-string 构建 prompt，从未调用 `pipeline.execute()` |
| 修复 | 在 `runner._execute_step()` 中调用 `pipeline.execute()`，将 `PipelineResult.context` 注入 system_prompt |
| 涉及文件 | `reqradar/cognitive_rt/cognition/runner.py` |
| 设计 | 1. Runner 构造时接收 `ContextPipeline` 实例<br>2. `_execute_step()` 中 `result = await self.pipeline.execute(session_id, project_id, query, context_budget=128000)`<br>3. 将 `result.context` 追加到 system_prompt 的 `## 上下文增强` 段落<br>4. 保留 `build_dynamic_system_prompt()` 作为 fallback（pipeline 不可用时） |
| 验收 | 推理过程中日志输出 `Pipeline 完成: strategy=..., collected=N, scored=N, selected=N, tokens=N/M` |

### P2-2: ContextSource 注入 service_url（#2）

| 项目 | 内容 |
|------|------|
| 问题 | `CodeGraphSource()` 无参创建，`.configure()` 从未被调，所有 Source 返回空列表 |
| 修复 | 在 Pipeline 创建处（`analysis_agent.py:165-174` 的 `_get_context_text_via_pipeline()`，或 P2-1 后的 Runner 层 Pipeline 工厂），对每个 Source 调用 `.configure(service_url=..., internal_api_key=...)`<br>service_url 从环境变量 `REQRADAR_INDEX_SERVICE_URL`（默认 `http://index-service:8003`）获取 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/analysis_agent.py`（若 Pipeline 留在 agent 层）<br>或 `reqradar/cognitive_rt/cognition/runner.py`（若 P2-1 将 Pipeline 提升到 runner 层） |
| 验收 | Source.collect() 返回非空列表（至少向量检索源有数据） |

### P2-3: 策略权重 key 对齐（#5）

| 项目 | 内容 |
|------|------|
| 问题 | 策略返回 `w1_semantic`，pipeline 读 `w1`，key 不匹配 |
| 修复 | 统一 key 命名。两种方案：<br>A. 策略改为返回 `w1/w2/w3/w4`（简单）<br>B. pipeline 改为读 `w1_semantic/w2_time_decay/w3_user_mark/w4_context_kind`（语义清晰）<br>**推荐方案 A**，因为 pipeline 内部用 w1-w4 更简洁 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/context_strategies.py` |
| 验收 | `strategy.get_score_weights()["w1"]` 返回非 None 值 |

### P2-4: Pipeline.execute() 使用策略（#6）

| 项目 | 内容 |
|------|------|
| 问题 | `execute()` 硬编码，4 个策略方法全是死代码 |
| 修复 | 1. `execute()` 中调用 `self.strategy.get_source_budgets()` 替代硬编码预算<br>2. `score_items()` 传入 `weights=self.strategy.get_score_weights()`<br>3. `select_context()` 传入 `min_score=self.strategy.get_select_min_score()`<br>4. `quality_gate.check()` 传入 `thresholds=self.strategy.get_quality_gate_thresholds()` |
| 涉及文件 | `reqradar/cognitive_rt/cognition/context_pipeline.py` |
| 验收 | 切换策略后，pipeline 的 collected/scored/selected 数量有变化 |

### P2-5: 实现 ARCH_DOC 上下文源（#17）

| 项目 | 内容 |
|------|------|
| 问题 | Pipeline 定义了 `ContextKind.ARCH_DOC` 权重，但无 Source 实现 |
| 修复 | 新增 `ArchitectureDocSource` 类，从 index-service 的向量检索中获取架构文档 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/context_sources.py` |
| 验收 | `ArchitectureDocSource.collect()` 返回 `ContextKind.ARCH_DOC` 类型的上下文项 |

### P2-6: L3 知识沉淀接入 cognitive_rt（#3）⭐ 核心闭环

| 项目 | 内容 |
|------|------|
| 问题 | cognitive_rt 推理完成后从未调用 L3 写入，知识永远不沉淀 |
| 修复 | 1. Runner 完成推理后，调用 index-service 的 `/internal/v2/knowledge/append` API<br>2. 从推理结果中提取可沉淀知识（术语、风险、决策记录等）<br>3. 通过 `KnowledgeEvolution` 或新建 `KnowledgePrecipitator` 类统一沉淀逻辑 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/runner.py`（推理完成后调用沉淀）<br>可能新建 `reqradar/cognitive_rt/cognition/knowledge_precipitator.py` |
| 验收 | Session COMPLETED 后，`GET /internal/v2/knowledge/query?project_id=X` 返回非空 L3 知识 |

### P2-7: 项目画像自动触发（#33）

| 项目 | 内容 |
|------|------|
| 问题 | `step_build_project_profile()` 存在但 runner 不调 |
| 修复 | 在 Runner 的推理步骤中，首次遇到项目画像为空时自动触发 `step_build_project_profile()` |
| 涉及文件 | `reqradar/cognitive_rt/cognition/runner.py` |
| 验收 | 首次推理时日志输出 "Building project profile"，后续推理使用已构建的画像 |

### Phase 2 验收标准

- [ ] E2E 冒烟测试通过，且推理日志中可见 Pipeline 执行记录
- [ ] 推理结果中包含上下文增强内容（非纯 LLM 裸跑）
- [ ] Session COMPLETED 后 L3 知识表有新增记录
- [ ] 切换策略后推理行为有可观测差异
- [ ] 项目画像在首次推理时自动构建

---

## Phase 3：持久化闭环

> **目标**：所有运行时状态可持久化，服务重启不丢数据。

### P3-1: Session PG 持久化（#4a）

| 项目 | 内容 |
|------|------|
| 问题 | `SessionService._sessions: dict` 内存存储，重启丢数据 |
| 修复 | 1. 新增 `SessionSnapshot` ORM 模型（已有 `session_snapshots` 表）<br>2. `SessionService` 状态转换时异步写 PG（`asyncio.shield` 防阻塞）<br>3. 服务启动时从 PG load 活跃 Session<br>4. 保留内存缓存作为热路径，PG 作为持久化后端 |
| 涉及文件 | `reqradar/cognitive_rt/runtime/session_api.py`<br>可能新建 `reqradar/cognitive_rt/runtime/session_repo.py` |
| 验收 | 创建 Session → 重启 cognitive-rt → GET Session 仍返回正确状态 |

### P3-2: Event PG 持久化 await（#12）

| 项目 | 内容 |
|------|------|
| 问题 | `EventPublisher` 的 PG 持久化是 fire-and-forget，`_pending_tasks` 未 await |
| 修复 | 1. 在 `EventPublisher` 中增加 `async flush()` 方法，await 所有 pending tasks<br>2. 在 Session 完成时调用 `flush()`<br>3. 在服务 shutdown 时调用 `flush()` |
| 涉及文件 | `reqradar/cognitive_rt/runtime/events.py` |
| 验收 | Session 完成后立即重启服务，事件数据仍可查 |

### P3-3: Checkpoint 冷存储 fallback 修复（#8）

| 项目 | 内容 |
|------|------|
| 问题 | `checkpoint_storage.py:182-193` 热区未找到时仍在热区循环，不读冷存储 |
| 修复 | 热区未找到时，跳转到冷存储（PG）查询逻辑 |
| 涉及文件 | `reqradar/cognitive_rt/runtime/checkpoint_storage.py` |
| 验收 | 热区无数据时，从 PG 恢复历史 checkpoint 成功 |

### P3-4: 内存存储驱逐上限（#13）

| 项目 | 内容 |
|------|------|
| 问题 | `_events`/`_checkpoints`/`_sessions` 无 maxsize，无限增长 OOM |
| 修复 | 1. Session 完成后从内存缓存移除（已持久化到 PG）<br>2. Event 保留最近 N 条（默认 1000）<br>3. Checkpoint 热区保留最近 N 个版本（默认 10） |
| 涉及文件 | `reqradar/cognitive_rt/runtime/session_api.py`、`events.py`、`checkpoint_storage.py` |
| 验收 | 运行 100 个 Session 后，内存中活跃 Session 数 ≤ 10（已完成的已移除） |

### P3-5: Output TaskStore PG 持久化（原 MVP-2）

| 项目 | 内容 |
|------|------|
| 问题 | `services/output/app.py` 的 `_tasks` 内存字典 |
| 修复 | 新增 `OutputTaskStore`（PG 后端），替代内存 `_tasks` + `_session_tasks` |
| 涉及文件 | 新建 `reqradar/output_svc/store.py`<br>修改 `services/output/app.py`<br>新增 Alembic 迁移 |
| 验收 | 创建报告任务 → 重启 output-service → 旧 task_id 仍可查 |

### Phase 3 验收标准

- [ ] 全部服务重启后，历史数据（Session/Event/Checkpoint/Task）仍可查
- [ ] 内存使用不随 Session 数量线性增长
- [ ] E2E 冒烟测试通过（回归验证）

---

## Phase 4：代码质量

> **目标**：清理死代码、修复命名、补全导出，降低维护负担。

### P4-1: 删除死代码（#26, #27, #25）

| 项目 | 内容 |
|------|------|
| 问题 | `_build_messages_chain()` 从未调用、`HISTORICAL_THRESHOLD_DAYS` 未使用、`archive_days/delete_days` 死配置 |
| 修复 | 删除这些未使用的代码和配置 |
| 涉及文件 | `runner.py`、相关配置文件 |

### P4-2: 补全工具导出（#34）

| 项目 | 内容 |
|------|------|
| 问题 | `SearchGitHistoryTool` 未从 `tools/__init__.py` 导出 |
| 修复 | 在 `__init__.py` 中添加导出 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/tools/__init__.py` |

### P4-3: 补全异常导出（#35）

| 项目 | 内容 |
|------|------|
| 问题 | `IngestionException` 未从 `kernel/__init__.py` 导出 |
| 修复 | 在 `kernel/__init__.py` 中添加导出 |
| 涉及文件 | `reqradar/kernel/__init__.py` |

### P4-4: Logger 名称修正（#32）

| 项目 | 内容 |
|------|------|
| 问题 | `tools/security.py` 用 `reqradar.agent.security`，不符合模块层级 |
| 修复 | 改为 `reqradar.cognitive_rt.cognition.tools.security` |
| 涉及文件 | `reqradar/cognitive_rt/cognition/tools/security.py` |

### P4-5: Scope.SESSION 加入 _SCOPE_PRIORITY（#36）

| 项目 | 内容 |
|------|------|
| 问题 | `Scope.SESSION` 不在 `_SCOPE_PRIORITY` 中 |
| 修复 | 添加 `Scope.SESSION` 到优先级映射 |
| 涉及文件 | `reqradar/kernel/config_base.py` |

### P4-6: models.py 表数注释修正（#28）

| 项目 | 内容 |
|------|------|
| 问题 | 注释说 25 张表，实际 32 张 |
| 修复 | 更新注释 |
| 涉及文件 | `reqradar/kernel/models.py` |

### P4-7: ContextSource max_items 执行（#29）

| 项目 | 内容 |
|------|------|
| 问题 | 所有 Source 接受 `max_items` 参数但不限制返回数量 |
| 修复 | 在 `collect()` 返回前截断到 `max_items` |
| 涉及文件 | `reqradar/cognitive_rt/cognition/context_sources.py` |
| 备注 | **Phase 2 后验收**：P2-2 注入 service_url 后 Source 才有真实返回数据，此时 max_items 截断才有意义 |

### P4-8: ContextSource context_kind 使用（#30）

| 项目 | 内容 |
|------|------|
| 问题 | `context_kind` 参数未使用 |
| 修复 | 在 `collect()` 中按 `context_kind` 过滤返回结果 |
| 涉及文件 | `reqradar/cognitive_rt/cognition/context_sources.py` |
| 备注 | **Phase 2 后验收**：同 P4-7 |

### P4-9: embedding.py 运行时依赖声明（#31）

| 项目 | 内容 |
|------|------|
| 问题 | `httpx`/`onnxruntime`/`numpy` 未在 `pyproject.toml` 声明 |
| 修复 | 添加 `onnxruntime` 和 `numpy` 到可选依赖组 `[embedding]`，`httpx` 已是核心依赖 |
| 涉及文件 | `pyproject.toml` |

### P4-10: server.py Pydantic 模型化（#15）

| 项目 | 内容 |
|------|------|
| 问题 | `server.py` 端点全用 dict 而非 Pydantic 模型，违 C-01 §6 |
| 修复 | 为每个端点定义 Pydantic Request/Response 模型 |
| 涉及文件 | `reqradar/cognitive_rt/runtime/server.py` |

### P4-11: 私有属性访问修复（#14）

| 项目 | 内容 |
|------|------|
| 问题 | `session_api.py` 访问 `sm._state`，`server.py` 访问 `_publisher._bus` |
| 修复 | 添加公共访问方法（如 `SessionMachine.state` property、`EventPublisher.get_bus()`） |
| 涉及文件 | `reqradar/cognitive_rt/runtime/session_api.py`、`server.py` |

### P4-12: 代码解析扩展（#24）

| 项目 | 内容 |
|------|------|
| 问题 | `code_parser.py` 仅支持 `.py` |
| 修复 | 添加 `.js/.ts/.java/.go` 等常见语言的解析支持 |
| 涉及文件 | `reqradar/ingestion/code_parser.py` |
| 备注 | 优先级最低，可推到后续迭代 |

### P4-13: Evidence/Dimension Pydantic 迁移评估（#16）

| 项目 | 内容 |
|------|------|
| 问题 | 用 dataclass 而非 Pydantic，违 C-01 §8.1 |
| 评估 | dataclass 在纯计算层是合理的（无需序列化/校验），但如果需要跨服务传输则应改为 Pydantic<br>**建议**：保持 dataclass 用于内部计算，在 API 边界用 Pydantic 做序列化 |
| 涉及文件 | 仅评估，可能不改 |

### Phase 4 验收标准

- [ ] `ruff check reqradar/` 无新增错误
- [ ] `grep -rn "reqradar.agent" reqradar/` 输出为空（logger 名称已修正）
- [ ] 所有 `__init__.py` 导出完整
- [ ] 无明显死代码

---

## 三、执行节奏建议

| 阶段 | 任务数 | 建议时长 | 关键里程碑 |
|------|--------|---------|-----------|
| Phase 1 | 9 | 3-4 天 | 所有接口类型对齐，E2E 回归通过 |
| Phase 2 | 8 | 5-6 天 | Pipeline 真正驱动推理，L3 知识可沉淀，asyncio.run 消除 |
| Phase 3 | 5 | 3-4 天 | 服务重启不丢数据 |
| Phase 4 | 13 | 3-4 天 | 代码质量达标 |
| **总计** | **35** | **14-18 天** | |

### 每日节奏

1. 每个任务完成后立即跑 E2E 回归（`scripts/e2e_smoke.py`）
2. Phase 2 每完成一个 P2 任务，用真实 PDF 文档做一次完整推理，对比报告质量
3. Phase 3 每完成一个 P3 任务，做一次重启恢复测试

### 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| P2-1 接入 Pipeline 后推理质量下降 | 报告变差 | 保留 `FEATURE_CONTEXT_PIPELINE=false` 降级开关 |
| P2-6 L3 沉淀逻辑复杂 | 知识提取不准 | 先实现最简单的"全量沉淀"，后续迭代优化 |
| P3-1 Session PG 持久化影响性能 | 推理变慢 | 用 `asyncio.shield` 异步写，不阻塞主路径 |
| Phase 2 工作量超预期 | 延期 | P2-5（ARCH_DOC）和 P2-7（项目画像）可推到 Phase 2.5 |

---

## 四、与旧计划的关系

| 旧计划任务 | 新计划对应 | 变化 |
|-----------|-----------|------|
| MVP-1 端到端真跑 | ✅ 已完成 | E2E 已通过，脚本在 `tests/e2e/test_mvp1_smoke.py` |
| MVP-2 TaskStore PG | P3-5 | 不变 |
| MVP-3 Session PG | P3-1 | 不变，但基于现有 checkpoint_storage 扩展而非新建 repo |
| MVP-4 asyncio.run | P1-8 | 不变 |
| MVP-5 前端组件 | **移除** | 非核心功能，推到独立迭代 |
| MVP-6 日志+健康 | **移除** | 非核心功能，推到独立迭代 |
| MVP-7 MinIO | **移除** | 非核心功能，推到独立迭代 |
| MVP-8 工具+L3+Graph | P2-6（L3 部分） | 工具/Graph 验证推到 Phase 4 后 |
| — | P2-1~P2-4 | **新增**：认知管线接通（旧计划未覆盖） |
| — | P2-5, P2-7 | **新增**：ARCH_DOC 源 + 项目画像（旧计划未覆盖） |
| — | P1-1~P1-7 | **新增**：接口对齐（旧计划未覆盖） |

---

## 五、36 项问题 → 任务映射

| # | 问题 | 任务 | 阶段 |
|---|------|------|------|
| 1 | Pipeline 输出未用 | P2-1 | Phase 2 |
| 2 | Source URL 未注入 | P2-2 | Phase 2 |
| 3 | L3 无写入入口 | P2-6 | Phase 2 |
| 4 | Session/Event/L3 内存存储 | P3-1, P3-2, P3-4 | Phase 3 |
| 5 | 策略权重 key 不匹配 | P2-3 | Phase 2 |
| 6 | 策略未被 execute 调用 | P2-4 | Phase 2 |
| 7 | asyncio.run 反模式 | P1-8 | Phase 1 |
| 8 | 冷存储 fallback 错误 | P3-3 | Phase 3 |
| 9 | dict vs StateSummary | P1-2 | Phase 1 |
| 10 | str vs DimensionStatus | P1-3 | Phase 1 |
| 11 | int vs str project_id | P1-1 | Phase 1 |
| 12 | Event fire-and-forget | P3-2 | Phase 3 |
| 13 | 内存无驱逐上限 | P3-4 | Phase 3 |
| 14 | 私有属性直接访问 | P4-11 | Phase 4 |
| 15 | server.py 用 dict | P4-10 | Phase 4 |
| 16 | dataclass vs Pydantic | P4-13 | Phase 4 |
| 17 | 无 ARCH_DOC 源 | P2-5 | Phase 2 |
| 18 | frozenset 嵌套 dict | P1-6 | Phase 1 |
| 19 | FIFO 非 LRU | P1-7 | Phase 1 |
| 20 | content 200 字符 | P1-4 | Phase 1 |
| 21 | project_id 非 FK | P1-5 | Phase 1 |
| 22 | Redis 忽略 TTL | P1-9 | Phase 1 |
| 23 | 无重试 | P1-10 | Phase 1 |
| 24 | 代码解析仅 Python | P4-12 | Phase 4 |
| 25 | archive_days 死配置 | P4-1 | Phase 4 |
| 26 | _build_messages_chain 死代码 | P4-1 | Phase 4 |
| 27 | HISTORICAL_THRESHOLD_DAYS | P4-1 | Phase 4 |
| 28 | 表数注释不符 | P4-6 | Phase 4 |
| 29 | max_items 未执行 | P4-7 | Phase 4 |
| 30 | context_kind 未使用 | P4-8 | Phase 4 |
| 31 | 依赖未声明 | P4-9 | Phase 4 |
| 32 | Logger 名称不匹配 | P4-4 | Phase 4 |
| 33 | 项目画像未触发 | P2-7 | Phase 2 |
| 34 | SearchGitHistoryTool 未导出 | P4-2 | Phase 4 |
| 35 | IngestionException 未导出 | P4-3 | Phase 4 |
| 36 | Scope.SESSION 缺失 | P4-5 | Phase 4 |
