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
| M4 | **P8** — 前端改造 | ⬜ 未开始 | — | — |
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
