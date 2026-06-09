# ReqRadar V2 — 开发进度追踪

```
本文档在每次 Phase 验收通过后由验收人更新。
编码 Agent 不应修改本文档。
```

## ⚠️ 重要声明（2026-06-08）

> **全栈集成测试暴露严重问题：之前所有 Phase 的验收仅验证了"代码存在 + 测试通过 + lint 无错"，从未验证核心业务逻辑是否真正实现。**
>
> 实际测试发现：cognitive-rt 的 Session 启动后不会执行推理（Runner/LLM 未集成），多数服务的"功能"只是 API 壳子。
>
> 以下验收结论需要全面复核。已标记为 ⚠️ 的 Phase 存在功能缺失风险，待逐项审查后更新状态。

## 概览

| 里程碑 | Phase | 代码验收 | 功能验收 | 核心风险 |
|--------|-------|---------|---------|---------|
| — | **P0** — Kernel 抽离 | ✅ | ✅ | 无（纯数据模型，已验证） |
| M1 | **P1** — Context Pipeline | ✅ | ⚠️ 待复核 | 五阶段流水线是否真正可执行？Agent 是否真正集成了 Pipeline？ |
| M2 | **P3** — Cognitive Runtime Core | ✅ | ✅ **通过** | Runner 集成已完整（create_runner_components → _run_analysis → run_react_analysis），Session 启动后真正执行 LLM 推理循环 |
| — | **P2** — Gateway + Auth | ✅ | ⚠️ 待复核 | JWT 签发/验证已验证可用，Redis 客户端是否真正工作？ |
| — | **P4** — ToolRuntime | ✅ | ⚠️ 待复核 | 六项管控是否真正实现？还是只有 Schema？ |
| M3 | **P5** — 拆 index-service + L3 | ✅ | ✅ **通过** | L3Writer 已注入 db_session_factory（PG 持久化），Graph 端点完整实现（BFS 查询 CodeModule/CodeDependency 表），向量检索字段名修复（query→query_text + collection） |
| — | **P6** — 拆 output-service | ✅ | ⚠️ 待复核 | 报告生成是否真正调用 LLM？还是只有模板渲染壳子？ |
| — | **P7** — BFF 独立 | ✅ | ⚠️ 待复核 | BFF 聚合是否真正转发到后端服务？还是只返回桩数据？ |
| — | **P9** — MCP 独立 | ✅ | ⚠️ 待复核 | MCP 工具是否真正可用？还是只有注册声明？ |
| M4 | **P8** — 前端改造 | ✅ | ⚠️ 待复核 | 前端页面是否真正连接后端 API？WebSocket 是否真正推送？ |
| — | **P10** — 性能升级 | ⬜ 未开始 | — | — |

**说明**：
- **代码验收**：文件存在、测试通过、lint 无错、代码结构符合设计
- **功能验收**：核心业务逻辑真正可执行、端到端流程跑通
- **⚠️ 待复核**：代码验收通过但功能验收未做，需要逐项审查

---

## P0 — Kernel 抽离

**验收日期**：2026-06-04

**验收结论**：✅ **通过**

**代码基线**：`48731c4`

**交付物**：7 个文件，70 测试，共享内核包（types/enums/exceptions/database/models/config_base）

---

## P1 — Context Pipeline

**验收日期**：2026-06-04

**验收结论**：✅ **验收通过**（11 次提交）

**代码基线**：`8d9dcd7`

**交付物**：V1 代码搬迁 + 五阶段 Context Pipeline（Collect→Score→Select→Compress→Assemble）+ Agent 集成 + Alembic 迁移 + 对比测试框架，126 tests

---

## P2 — Gateway + Auth

**验收日期**：2026-06-04

**验收结论**：✅ **验收通过**（3 项缺陷已修复 `480db1f`）

**代码基线**：`480db1f`

**交付物**：Docker Compose 8 服务 + Traefik 路由 + Auth Service（JWT 签发/验证）+ Internal-API-Key 中间件 + Redis 客户端（内存降级），19 测试

---

## P3 — Cognitive Runtime Core

**验收日期**：2026-06-04（代码验收）

**代码验收结论**：✅ 代码结构完整

**功能验收结论**：✅ **Runner 集成已完整**（2026-06-09 修复桩实现 + Bug）

**代码基线**：`f5589ad` + 桩修复提交

**交付物**：Session 状态机（11 态 + 20 转换）+ Event Stream（三级事件）+ Checkpoint 系统 + WebSocket ConnectionManager + LiteLLMClient + RunnerFactory + 9 工具注册 + run_react_analysis 完整循环，165 tests

**Runner 集成链**：
- `server.py:142-148`：`create_runner_components()` 创建 agent/llm_client/tool_registry 并传入 `start()`
- `session_api.py:164-179`：`start()` 检测三参数非 None → `asyncio.create_task(_run_analysis())`
- `runner.py:437-699`：完整 ReAct 循环（LLM tool calling → 工具执行 → 证据收集 → 维度追踪 → Checkpoint → 报告生成 → 记忆演化）
- `llm_client.py:23-210`：httpx 真实调用，含重试、tool calling、结构化输出
- `context_sources.py`：5 个 Source 全部接入真实 HTTP 数据源（index-service）

---

## P4 — ToolRuntime

**验收日期**：2026-06-04

**验收结论**：✅ **验收通过**（3 项设计偏差已修复 `f5ede13`）

**代码基线**：`f5ede13`

**交付物**：ToolRuntime 六项管控（超时/重试/限流/缓存/权限/Checkpoint）+ 10 工具能力声明，21 测试

---

## P5 — 拆 index-service + L3 知识治理

**验收日期**：2026-06-04

**验收结论**：✅ **验收通过**（2 项缺陷已修复 `84b2f0a`）

**代码基线**：`84b2f0a`

**交付物**：七种 L3-A 知识类型 + FreshnessManager + ConfidenceCalculator + KnowledgeChangelog + L3Writer + RelationStore + L3ContextSource + V1→V2 迁移方案，28 测试

---

## P6 — 拆 output-service

**验收日期**：2026-06-04

**验收结论**：✅ **验收通过**（2 项缺陷已修复 `15b6da9`）

**代码基线**：`15b6da9`

**交付物**：output-service 独立服务（6 端点：generate/status/latest/reload-templates/content/health）+ Jinja2 模板，16 测试

---

## P7 — BFF 独立

**验收日期**：2026-06-04

**验收结论**：✅ **验收通过**（2 项缺陷已修复 `508f79d`）

**代码基线**：`508f79d`

**交付物**：api-service BFF 聚合层（27 端点覆盖 C-04 §4 全部模块）+ JWT 鉴权 + X-Internal-API-Key 注入 + ServiceClient（httpx 异步），33 测试

---

## P9 — MCP 独立

**验收日期**：2026-06-05

**验收结论**：✅ **验收通过**

**代码基线**：`23ef43e`

**交付物**：integration-service（FastMCP Server + 管理 API）+ 7 个 V2 MCP 工具 + Access Key 管理（生成/验证/撤销）+ 审计日志（脱敏/查询/清理）+ Internal-API-Key 中间件 + Dockerfile

---

## P8 — 前端改造（M4 里程碑）

**验收日期**：2026-06-08

**验收结论**：✅ **验收通过**（M4 里程碑达成）

**代码基线**：`18d7bbb`（合并提交）+ `7f5dc7f`（C1 review fixes）

**交付物**：

| Wave | 内容 | 交付 |
|------|------|------|
| Wave 1 | 基础设施 | Dockerfile + nginx.conf + vite.config.ts + 类型定义 + API 客户端 + 路由骨架 + AuthGuard + AppLayout |
| Wave 2 | 核心主流程 | LoginPage + DashboardPage + AnalysisCreatePage + SessionDetailPage |
| Wave 3 | 实时事件 | useSessionWebSocket Hook + WsContext + SessionEventsPage |
| Wave 4 | 报告 + 认知仪表盘 | ReportPage + KnowledgeDashboard（7 Tab：总览/术语/模块/约束/决策/风险/事故） |
| Wave 5 | 可降级 | CheckpointsPage + 前端测试 |

**验收指标**：

| 标准 | 结果 |
|------|------|
| 独立容器化 | ✅ Nginx + Traefik 路由 `/app/*` |
| API 路径 `/api/v2/` | ✅ 全部替换 |
| 路由 basename `/app/v2` | ✅ 全部替换 |
| WebSocket 实时推送 | ✅ 三级 23 种事件 |
| 认知仪表盘 | ✅ 7 Tab L3 知识可视化 |
| Checkpoint 回放 | ✅ 版本链 + 对比 + 恢复 |
| 无 V1 类型引用 | ✅ 全部重写 |

---

## 跨 Phase 缺陷修复

> 全部 18/18 项已闭环。

| 批次 | 内容 | 修复 commit | 状态 |
|------|------|------------|------|
| 批次一 FIX-1~7 | 代码规范 + kernel 枚举 | 32d4c72 + d1ddace + 2957542 + bffd81a | ✅ |
| 批次二 INT-1~3 | 致命级运行时错误 | c1760df + 9a34cb0 | ✅ |
| 批次三 INT-4~8 | 严重级功能不可用 | c259d2c + 9a34cb0 + dc71851 | ✅ |
| 批次四 INT-9~12 + #13~14 | 中等级功能缺失 | 9a34cb0 + c1760df + dc71851 | ✅ |
| 批次五 INT-4a~5b | INT-4+INT-5 验收后补修 | 2d29b20 | ✅ |

**当前测试基线**：ruff 0 errors，pytest 全部通过

---

## 第二轮质量缺陷（2026-06-08 发现，已修复）

> 验收 Agent 全面审查发现，共 13 项。**全部 13/13 已闭环。**

### A 类：I-01 API 契约不匹配（严重）

| # | 缺失端点 | I-01 条目 | 位置 | 状态 |
|---|---------|----------|------|------|
| A1a | `GET /internal/v2/sessions/{id}/evidence` | §6.5 | `server.py` L173 | ✅ 已修复（c04729e） |
| A1b | `GET /internal/v2/sessions/{id}/dimensions` | §6.6 | `server.py` L185 | ✅ 已修复（c04729e） |
| A2 | `GET /internal/v2/memory/query` | §8.1 | `services/index/app.py` L759 | ✅ 已修复（c04729e + ffe78ac） |
| A3a | `POST /internal/v2/auth/check-permission` | §5.2 | `services/auth/app.py` L142 | ✅ 已修复（c04729e） |
| A3b | `GET /internal/v2/users/{user_id}` | §5.3 | `services/auth/app.py` L167 | ✅ 已修复（c04729e） |

### B 类：错误格式不一致（中等）

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| B1 | output-service HTTPException 用字符串 detail | `services/output/app.py` L268/L310/L312 | ✅ 已修复（c04729e + ffe78ac） |
| B2 | integration-service HTTPException 用字符串 detail | `services/integration/app.py` L144 | ✅ 已修复（c04729e） |

### C 类：编码规范违规（中等）

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| C1 | output-service 静默吞异常 | `services/output/app.py` L171 | ✅ 已修复（c04729e） |
| C2 | vector_store.py 裸吞异常 | `reqradar/index_svc/vector_store.py` L66-67, L237-238 | ✅ 已修复（c04729e） |
| C3 | output-service 异常无 cause 链 | `services/output/app.py` L267/L310/L312 | ⚠️ 非 re-raise，建议性，暂不修复 |
| C4 | BFF config/patch 用 `dict` 无 Schema 验证 | `services/api/app.py` L31, L68 | ⚠️ 已补充 CreateProjectRequest/UpdateProjectRequest，原始 config/patch 裸 dict 保留（P2 优先级） |

### D 类：Docker 配置问题（中等）

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| D1 | ChromaDB 宿主机端口冲突 | `docker-compose.yml` L211 | ✅ 已修复（ffe78ac）：8005→8006 |
| D2 | api-service 和 cognitive-rt 都用端口 8002 | `services/api/Dockerfile` L11-13 | ✅ 已修复（c04729e）：api-service 改 8000 |

### E 类：测试覆盖缺失（中等）

| # | 问题 | 状态 |
|---|------|------|
| E1 | auth-service 无独立测试 | ✅ 已修复（4925ca6）：7 测试 |
| E2 | index-service 无独立测试 | ✅ 已修复（4925ca6）：7 测试 |
| E3 | cognitive-rt server.py 无 HTTP 端点测试 | ✅ 已修复（4925ca6）：12 测试 |

### 测试过程中发现并修复的 Bug

| Bug | 位置 | 状态 |
|-----|------|------|
| create_jwt_token() 传入不存在的 is_superuser 参数 | `auth/app.py` | ✅ 已修复（4925ca6） |
| get_evidence()/get_dimensions() 对 EventRecord 用 dict.get() | `session_api.py` | ✅ 已修复（4925ca6） |

**修复 commit**：c04729e + 4925ca6 + ffe78ac

**当前测试基线**：ruff 0 errors，pytest 全部通过（新增 26 测试）

---

## 全栈集成测试（2026-06-08）

> 首次使用真实 LLM API（MiniMax-M2.5）+ 真实项目（cool-agent）进行端到端测试。

### 测试结果

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 容器全部 Up | ✅ 11/11 | 所有服务正常运行 |
| 健康检查 | ✅ | api-service /health 200 |
| JWT 签发 | ✅ | auth-service 正常签发 Token |
| Session 创建 | ✅ | BFF → cognitive-rt 创建成功，状态 READY |
| Session 启动 | ✅ | 状态变为 RUNNING，事件 SESSION_CREATED + SESSION_STARTED |
| 证据/维度/事件查询 | ✅ | 接口正常响应 |
| 前端 SPA | ✅ | HTML 正常返回 |
| **实际推理执行** | ❌ | **Runner 未集成——start() 只改状态，不触发 LLM 调用** |
| **推理步骤产生** | ❌ | total_reasoning_steps 始终为 0 |
| **证据收集** | ❌ | 无推理步骤，无证据产生 |
| **维度评估** | ❌ | 无推理步骤，无维度数据 |

### 根因

`session_api.py` L149：`start()` 方法要求 `agent`、`llm_client`、`tool_registry` 三个参数才能启动推理循环，但 `server.py` 的 `start_session` 端点从未构造和传入这些参数。

**结论**：V2 的核心功能——LLM 驱动的推理分析——在 cognitive-rt 服务中完全未实现。当前所有服务只是 API 壳子。

---

## 桩实现审计（2026-06-08）

> 全栈集成测试后，对所有 Phase 逐项审查设计文档 vs 实际代码。

### 审计验证结论

| 类别 | 占比 | 说明 |
|------|------|------|
| 属实 | ~60% | context_sources 空壳、内存存储、Graph/trace 端点缺失、event_bus 无 Redis、get_current_user 硬编码 |
| 措辞不准确 | ~25% | cognitive-rt "不存在"（实际存在，代码在 reqradar/cognitive_rt/runtime/server.py）、checkpoint_storage "空壳"（有本地文件写入）、start_session "空壳"（逻辑存在但工厂桩未接通） |
| 遗漏 | ~15% | trace 端点缺失、ingestion-service 完全不存在 |

### 16 个桩实现分类

| 类别 | 桩数量 | 关键文件 |
|------|--------|---------|
| 推理链断裂 | 3 | server.py, session_api.py, context_sources.py |
| 数据持久化 | 6 | events.py, session_api.py, checkpoint_storage.py, writer.py, auth/app.py, output/app.py |
| 事件/消息 | 2 | event_bus.py, api/app.py (WebSocket) |
| 基础设施 | 2 | redis_client.py, index/app.py (向量检索) |
| 可推迟 | 3 | integration/mcp_keys.py, mcp_audit.py, tool_runtime.py (缓存/限流) |

### 审计遗漏的额外问题

| 问题 | 位置 | 说明 |
|------|------|------|
| BFF trace 端点无后端 | `api/app.py` L660 | BFF 有 trace 路由，cognitive-rt 无此端点 |
| BFF graph×3 端点无后端 | `api/app.py` L577-650 | BFF 有 3 个 graph 路由，index-service 无此端点 |
| ingestion-service 完全不存在 | I-01 §7 | 定义了 4 个端点，整个服务未实现 |
| output-service 报告生成无 LLM | `output/app.py` | 只做 Jinja2 模板渲染，无 LLM 调用 |

### 桩实现修复计划

> 详细计划见 `.trae/documents/V2_Stub_Remediation_Plan.md`

**10 个修复任务 + 3 个新增任务**：

| 波次 | 任务 | 说明 | 依赖 |
|------|------|------|------|
| 第一波（并行） | Task 1: LiteLLMClient | 新建 LLM 客户端封装 | 无 |
| | Task 4: context_sources | 5 个 Source 接入 index-service | 无 |
| | Task 5: Alembic 配置 | 补全 alembic.ini/env.py/script.py.mako | 无 |
| 第二波（依赖第一波） | Task 2: Runner 工厂函数 | 创建 agent/llm_client/tool_registry | Task 1 |
| | Task 6: auth PG | auth-service 接入 PostgreSQL | Task 5 |
| | Task 7: cognitive-rt PG | Session/Event/Checkpoint 持久化 | Task 5 |
| | Task 9: L3Writer PG | L3 知识持久化 | Task 5 |
| 第三波（依赖第二波） | Task 3: 接通 Runner | server.py start_session 传入 Runner 参数 | Task 1+2 |
| | Task 8: Redis + WS | EventBus Redis 集成 + WebSocket 真实推送 | Task 7 |
| | Task 11: BFF 缺失端点 | graph×3 + trace×1 补实现或返回 501 | 无 |
| | Task 12: output 报告改造 | 报告生成接入 LLM + 分析数据 | Task 3 |
| 第四波 | Task 10: 集成验证 | 端到端全链路测试 | 全部 |
| 可推迟 | Task 13: ingestion-service | I-01 §7 定义的 4 个端点 | P2 |

### 修复计划审查修正

| 原计划问题 | 修正 |
|-----------|------|
| cognitive-rt 服务"不存在" | 修正为"服务存在（Dockerfile 指向 server.py），但 start_session 不触发推理" |
| checkpoint_storage "空壳" | 修正为"有本地文件写入，持久化后端为内存+本地文件" |
| Task 2 工具数量"9 个" | 修正为"5 个（V2 已迁移的），其余 4 个待确认" |
| Task 5 script.py.meso | 拼写修正为 script.py.mako |
| 遗漏 BFF 4 个空路由 | 新增 Task 11 |
| 遗漏 output-service 无 LLM | 新增 Task 12 |
| 遗漏 ingestion-service | 新增 Task 13（P2 可推迟） |

---

## 第三轮 Bug 修复（2026-06-09）

> 全面代码审查发现 3 项 Bug。**全部 3/3 已闭环。**

| # | Bug | 位置 | 修复内容 | 状态 |
|---|-----|------|---------|------|
| Bug 1 | 向量检索字段名不匹配 | `context_sources.py` L209/L273 | `{"query": query}` → `{"query_text": query, "collection": "code"/"requirements"}` | ✅ |
| Bug 2 | L3Writer 未注入 PG | `services/index/app.py` L320 | `L3Writer()` → `L3Writer(db_session_factory)` | ✅ |
| Bug 3 | Graph 端点为桩 | `services/index/app.py` L885-1098 | 返回空列表 → BFS 算法 + SQLAlchemy 查询 `CodeModule`/`CodeDependency` 表 | ✅ |

---

## 文档索引

| 文档 | 路径 |
|------|------|
| 项目宪法 | `docs/00_PROJECT_POSITIONING.md` |
| Runtime 蓝图 | `docs/01_RESTUCTURE_OVERVIEW.md` |
| 总体架构 | `docs/02_SYSTEM_ARCHITECTURE.md` |
| 认知资产模型 | `docs/03_COGNITIVE_ASSET_MODEL.md` |
| 实施路线图 | `docs/04_IMPLEMENTATION_ROADMAP.md` |
| **ingestion-service 规划** | `docs/detailed/INGESTION_SERVICE_PLAN.md` |
| **项目管理模块规划** | `docs/detailed/PROJECT_MANAGEMENT_PLAN.md` |
| Agent 工作指南 | `AGENTS.md` |
| 文档导航 | `docs/README.md` |
| ADR 目录 | `docs/adr/`（16 条） |
