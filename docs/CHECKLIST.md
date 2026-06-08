# ReqRadar V2 — 开发进度追踪

```
本文档在每次 Phase 验收通过后由验收人更新。
编码 Agent 不应修改本文档。
```

## 概览

| 里程碑 | Phase | 状态 | 验收日期 | 核心成果 |
|--------|-------|------|---------|---------|
| — | **P0** — Kernel 抽离 | ✅ **验收通过** | 2026-06-04 | 共享内核：类型/枚举/异常/ORM/配置基类 |
| M1 | **P1** — Context Pipeline | ✅ **验收通过** | 2026-06-04 | V1 代码搬迁 + Context Pipeline + Agent 集成 + 对比测试框架，11 次提交 |
| M2 | **P3** — Cognitive Runtime Core | ✅ **验收通过** | 2026-06-04 | Session 状态机 + Event Stream + Checkpoint 系统 + WebSocket，4 次提交，165 tests |
| — | **P2** — Gateway + Auth | ✅ **验收通过** | 2026-06-04 | Docker Compose + Traefik 路由 + Auth Service + JWT + Internal-API-Key + Redis 客户端，3 项缺陷已修复（480db1f） |
| — | **P4** — ToolRuntime | ✅ **验收通过** | 2026-06-04 | 六项管控能力 + 10 工具能力声明 + 21 测试，3 项设计偏差已修复 |
| M3 | **P5** — 拆 index-service + L3 | ✅ **验收通过** | 2026-06-04 | 七种 L3-A 知识类型 + 治理框架 + L3ContextSource + 迁移方案，28 测试，2 项缺陷已修复（84b2f0a） |
| — | **P6** — 拆 output-service | ✅ **验收通过** | 2026-06-04 | output-service 独立服务 + 报告生成/状态/最新 API + 模板热更新 + Jinja2，2 项缺陷已修复（15b6da9） |
| — | **P7** — BFF 独立 | ✅ **验收通过** | 2026-06-04 | api-service BFF 聚合层 + 27 个端点 + JWT 校验 + Internal-API-Key 注入，2 项缺陷已修复（508f79d） |
| — | **P9** — MCP 独立 | ✅ **验收通过** | 2026-06-05 | integration-service + FastMCP Server + 7 个 MCP 工具 + Access Key 管理 + 审计日志，2 次提交 |
| M4 | **P8** — 前端改造 | ✅ **验收通过** | 2026-06-08 | 全新 V2 前端：独立容器化 + /app/v2/ 路由 + /api/v2/ API + WebSocket 实时事件 + 认知仪表盘（7 Tab）+ Checkpoint 回放，M4 里程碑达成 |
| — | **P10** — 性能升级 | ⬜ 未开始 | — | — |

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

**验收日期**：2026-06-04

**验收结论**：✅ **验收通过**（M2 里程碑达成）

**代码基线**：`f5589ad`

**交付物**：Session 状态机（11 态 + 20 转换）+ Event Stream（三级事件）+ Checkpoint 系统（三区存储 + Evidence 链校验）+ WebSocket ConnectionManager，165 tests

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

## 文档索引

| 文档 | 路径 |
|------|------|
| 项目宪法 | `docs/00_PROJECT_POSITIONING.md` |
| Runtime 蓝图 | `docs/01_RESTUCTURE_OVERVIEW.md` |
| 总体架构 | `docs/02_SYSTEM_ARCHITECTURE.md` |
| 认知资产模型 | `docs/03_COGNITIVE_ASSET_MODEL.md` |
| 实施路线图 | `docs/04_IMPLEMENTATION_ROADMAP.md` |
| Agent 工作指南 | `AGENTS.md` |
| 文档导航 | `docs/README.md` |
| ADR 目录 | `docs/adr/`（16 条） |
