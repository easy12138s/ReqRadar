# ReqRadar V2 — MVP Hardening 实施计划

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | 路由图 04 P0-P9 已完成后的"MVP 冲刺"实施计划，专攻剩余的 8 项 MVP 必做和中优先任务 |
| 前置文档 | 04_IMPLEMENTATION_ROADMAP.md（路线图）、CHECKLIST.md（验收记录）、MVP-02_MVP_VERIFICATION_CHECKLIST.md（配套验收清单） |
| 核心目标 | 把"能跑通的 Demo"提升为"单人可演示、关键状态不丢、用户感知流畅"的 MVP 级别交付 |
| 文档职责 | 定义 8 项任务的输入、任务清单、验收标准、可演示成果、风险与回滚策略 |

---

## 一、背景与定位

### 1.1 路线图实施现状

按 04 路线图，P0-P9 主体代码已完成（CHECKLIST.md 已标注通过），但**核心假设的端到端验证**、**关键状态的持久化**、**性能与可观测性**三类工作**未在路线图中作为独立 Phase 规划**，导致 V2 当前处于"代码到位但没跑过、跑过但重启丢"的 Demo 阶段。

### 1.2 MVP 定义

按 MVP 原则（M0 = Minimum Viable Product）：

> **单人能跑通：上传项目 → 摄取 → 提问 → 拿到报告，不出 P0 级别错误。**

**MVP 边界**：

| 项 | MVP 边界内 | MVP 边界外（v1.x 延后） |
|----|-----------|----------------------|
| 创建项目 | ✅ 3 场景（git clone / 本地目录 / 压缩包） | — |
| 上传/挂载 | ✅ 文档 + 代码 | — |
| 向量化 | ✅ ChromaDB ONNX | — |
| Session + 推理 | ✅ 单 Session，能跑通 | 跨 Session 飞轮 |
| 工具调用 | ✅ 9 工具全部能调 | 工具链编排 |
| 报告 | ✅ 能输出 Markdown | PDF / 多模板 |
| 前端 | ✅ 能看结果 | 美化 / 组件库 |
| **持久化** | ✅ **关键状态重启不丢** | — |
| **监控** | ⚠️ 深健康检查 | Prometheus / 链路追踪 |
| **MinIO** | ⚠️ L0 原始文件 | 冷状态全量搬迁 |
| **gRPC** | ❌ 不必 | P10 性能升级 |
| **P9 MCP** | ⚠️ 基础可用 | 真实 IDE 验证 |

### 1.3 总体评分基线

按 MVP 口径（功能真实可用 + 关键持久化 + MinIO/P10 进度 + 可观测性）：

| 维度 | 当前分 |
|------|--------|
| MVP 核心 9 项 | 80 / 100 |
| MVP 周边质量 | 55 / 100 |
| MinIO 替换 + P10 | 0 / 100 |
| 可观测性 | 20 / 100 |
| **综合** | **55 / 100** |

**目标**：本计划执行后，综合分提升到 **80 / 100**（接近 Beta 级）。

---

## 二、任务总览

| 编号 | 任务 | 优先级 | 估时 | 状态 |
|------|------|--------|------|------|
| **MVP-1** | 端到端真跑一次（docker compose up + cool-agent）发现真 bug | 🔴 P0 | 1 天 | ⬜ 未做 |
| **MVP-2** | TaskStore 落 PG（output service task_id 重启不丢） | 🔴 P0 | 0.5 天 | ⬜ 未做 |
| **MVP-3** | Session 状态机从 PG 恢复 | 🔴 P0 | 1 天 | ⬜ 未做 |
| **MVP-4** | Container 模型去嵌套（pipeline.execute 事件循环冲突） | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **MVP-5** | 前端抽核心组件（Button / Table / Loading） | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **MVP-6** | 结构化日志 + /health 深健康 | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **MVP-7** | MinIO 接入 L0 原始文件 | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **MVP-8** | 9 工具真调验证 + L3Writer PG 注入验证 + Graph 端点真验 | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **合计** | | | **5 天** | |

> **预估收益**：执行后综合分从 55 提升到 80（+25 分）。

---

## 三、任务详细设计

---

### MVP-1：端到端真跑一次（高优先级，最高 ROI）

**目标**：用真实环境跑通"创建项目 → 上传 → 摄取 → 启动 Session → 拿到报告"全链路，发现并记录真 bug。这是后续 7 项任务的输入。

**依赖**：无

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-1.1 | 准备 `.env`（含真实 LLM API Key） | `.env` | 0.5h |
| MVP-1.2 | `docker compose up -d` 启动 11 容器 | 运行日志 + 服务状态 | 0.5h |
| MVP-1.3 | `alembic upgrade head` 应用全部迁移 | 数据库 schema 就绪 | 0.5h |
| MVP-1.4 | 准备测试项目：cool-agent 仓库 + 1 份需求文档 | 测试数据 | 1h |
| MVP-1.5 | 端到端 curl/Python 脚本（自动跑 9 步） | `scripts/e2e_smoke.py` | 2h |
| MVP-1.6 | 跑 3 轮 × 3 类项目，收集全部真 bug | `docs/MVP-1_BUG_LOG.md` | 2h |
| MVP-1.7 | 修复发现的 P0 bug（预计 3-8 个） | 多个 fix commit | 1 天 |
| MVP-1.8 | 复测全链路，全部 9 步 ✅ | 复测报告 | 1h |

**验收标准**：
- [ ] 9 步全链路脚本可在 5 分钟内跑通
- [ ] 3 轮 × 3 类项目共 9 次全部成功，无 5xx 错误
- [ ] 所有发现的 P0 bug 100% 修复
- [ ] 复测报告记录每次跑通时间、LLM Token 消耗、报告质量评分

**可演示成果**：一份"实跑 9 次无错"的截图 + bug 修复记录。

**风险与应对**：

| 风险 | 概率 | 应对 |
|------|------|------|
| LLM API 不稳定 | 高 | 增加重试 + 失败统计 |
| markitdown 首次下载模型失败 | 中 | 预热 Docker 镜像，缓存模型到本地 |
| 容器端口冲突 | 低 | 复用 04 路线图已修复的端口配置 |

**回滚策略**：本任务无破坏性改动，仅新增脚本和文档，无回滚需求。

---

### MVP-2：TaskStore 落 PG（高优先级）

**目标**：`services/output/app.py` 的 `_tasks` 内存字典改为 PG 表，重启后 task_id 仍可查。

**依赖**：MVP-1

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-2.1 | 设计 `output_tasks` 表 schema | Alembic 迁移脚本 | 1h |
| MVP-2.2 | 实现 `OutputTaskStore` 类（PG 后端） | `reqradar/output_svc/store.py` | 2h |
| MVP-2.3 | 替换 `services/output/app.py` 中的 `_tasks` | diff 提交 | 1h |
| MVP-2.4 | 单元测试：task 创建 / 查询 / 状态流转 | `tests/unit/output_svc/test_store.py` | 1h |

**验收标准**：
- [ ] Alembic 迁移可正向 + 回滚
- [ ] TaskStore 单测覆盖率 ≥ 80%
- [ ] 重启 output-service 后，旧的 task_id 仍可查
- [ ] 9 项边界：成功/404（task 不存在）/状态非法/外部 DB 失败/等

**可演示成果**：创建 task → 重启容器 → 旧 task_id 仍可 GET。

**回滚策略**：迁移脚本可 downgrade 回到内存版本。

---

### MVP-3：Session 状态机从 PG 恢复（高优先级）

**目标**：`reqradar/cognitive_rt/runtime/session.py` 的 `_sessions` 内存字典支持从 PG 恢复，container 重启后历史 Session 仍可查、可续推。

**依赖**：MVP-1

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-3.1 | 设计 `session_snapshots` 表 schema（JSONB 存完整状态） | Alembic 迁移 | 1h |
| MVP-3.2 | 实现 `SessionStateRepo`（save / load / list_active） | `reqradar/cognitive_rt/runtime/session_repo.py` | 3h |
| MVP-3.3 | 修改 `SessionStateMachine` 启动时从 PG load 活跃 Session | diff 提交 | 2h |
| MVP-3.4 | 修改状态转换时同步持久化到 PG | diff 提交 | 2h |
| MVP-3.5 | 单元测试 + 集成测试 | `tests/unit/cognitive_rt/runtime/test_session_repo.py` | 2h |

**验收标准**：
- [ ] cognitive-rt 重启后，所有 CREATED/READY/RUNNING 状态的 Session 可恢复
- [ ] Session 状态转换有审计日志（事件流不变）
- [ ] 持久化失败时**不阻塞**状态转换（降级为内存）
- [ ] 9 项边界 + 异常路径测试

**可演示成果**：启动 Session → 推理到第 3 步 → kill -9 cognitive-rt → 重启 → Session 自动从第 3 步附近恢复。

**回滚策略**：若发现恢复后状态不一致，可禁用启动时 load 逻辑（仅写入不读取），回到原行为。

---

### MVP-4：Container 模型去嵌套（中优先级）

**目标**：`reqradar/cognitive_rt/cognition/context_pipeline.py` 的 `pipeline.execute` 在 agent 内被 `asyncio.run` 嵌套调用的事件循环反模式重构。

**依赖**：MVP-1

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-4.1 | 定位所有 `asyncio.run` / `run_in_executor` 调用点 | 代码位置清单 | 1h |
| MVP-4.2 | 设计"同步上下文 + 异步上下文"双接口 | `pipeline.execute_sync` + `pipeline.execute_async` | 1h |
| MVP-4.3 | 替换调用点为双接口 | diff 提交 | 1h |
| MVP-4.4 | 真跑 MVP-1 脚本 10 轮验证无死锁 | 验证报告 | 1h |

**验收标准**：
- [ ] `asyncio.run` 调用点 100% 消除
- [ ] 10 轮真跑无死锁
- [ ] 性能不退化（context assembly 延迟 ≤ 2s）

**回滚策略**：保留原 `asyncio.run` 路径作为 fallback（`pipeline.execute` 旧签名）。

---

### MVP-5：前端抽核心组件（中优先级）

**目标**：`frontend/src/components/` 增加 `Button` / `Table` / `Loading` 三个基础组件，重构 8 页面统一使用。

**依赖**：MVP-1

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-5.1 | 设计 Button 组件（variant: primary / secondary / ghost） | `Button.tsx` | 1h |
| MVP-5.2 | 设计 Table 组件（columns / dataSource / loading） | `Table.tsx` | 1h |
| MVP-5.3 | 设计 Loading 组件（spinner / skeleton） | `Loading.tsx` | 0.5h |
| MVP-5.4 | 重构 8 页面统一使用 | 多个 diff 提交 | 2h |

**验收标准**：
- [ ] 3 组件有 props 文档（TS type）
- [ ] 8 页面全部接入，无残留手写 `<button>` / `<table>`
- [ ] Loading 状态覆盖 90% 异步数据展示

**回滚策略**：组件化是纯前端重构，每个 commit 可独立回滚。

---

### MVP-6：结构化日志 + /health 深健康（中优先级）

**目标**：日志改为 JSON 格式携带 `session_id` / `request_id`；`/health` 改为深健康（检查 PG / Chroma / Redis 真实可用性）。

**依赖**：MVP-1

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-6.1 | 设计 JSON 日志格式 | `reqradar/infrastructure/logging.py` | 1h |
| MVP-6.2 | 替换 7 个服务的 `logging.basicConfig` | 多个 diff 提交 | 1h |
| MVP-6.3 | 实现深健康检查工具函数 | `reqradar/infrastructure/health.py` | 1h |
| MVP-6.4 | 替换 7 个服务的 `/health` 端点 | 多个 diff 提交 | 1h |

**验收标准**：
- [ ] 日志输出可被 `jq` 直接解析
- [ ] `/health` 返回 200 时所有依赖必须真实可用
- [ ] 任一依赖失败 → 503 + 详细错误

**回滚策略**：日志格式和 health 端点是独立中间件，单独 commit 可回滚。

---

### MVP-7：MinIO 接入 L0 原始文件（中优先级）

**目标**：`docker-compose.yml` 增加 minio service，ingestion-service 的 L0 写入改用 MinIO（替代本地路径）。

**依赖**：MVP-1

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-7.1 | docker-compose.yml 加 minio service + 自动 bucket 创建 | docker-compose.yml diff | 1h |
| MVP-7.2 | 引入 boto3 依赖 + MinIO Client 封装 | `reqradar/ingestion/storage/s3_client.py` | 1h |
| MVP-7.3 | 修改 `services/ingestion/app.py` L0 写入逻辑 | diff 提交 | 1h |
| MVP-7.4 | 真跑验证：上传文档 → L0 出现在 MinIO | 验证截图 | 0.5h |

**验收标准**：
- [ ] MinIO 容器启动后可访问 http://localhost:9001 控制台
- [ ] 上传文档后，MinIO 中可见对应对象
- [ ] L0 metadata 仍存 PG（关联不变）
- [ ] MinIO 不可用时降级为本地路径（不阻塞业务）

**回滚策略**：保留本地路径为 fallback，通过 `L0_STORAGE_BACKEND` 环境变量切换。

---

### MVP-8：9 工具 + L3Writer + Graph 端点真验（中优先级）

**目标**：对 MVP 核心 5 个工具（search_code / read_file / search_requirements / list_modules / get_project_profile）+ L3Writer + Graph 三端点（neighbors / path / subgraph）逐个真跑验证。

**依赖**：MVP-2, MVP-3

**任务清单**：

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| MVP-8.1 | 设计工具真调测试脚本 | `scripts/tools_smoke.py` | 1h |
| MVP-8.2 | 跑 5 工具 × 3 场景，记录真问题 | 验证报告 | 1h |
| MVP-8.3 | 修复发现的工具 bug | 多个 diff 提交 | 1h |
| MVP-8.4 | L3Writer PG 写入真验（创建 7 种知识各 1 条） | 验证截图 | 0.5h |
| MVP-8.5 | Graph 三端点真验（neighbors / path / subgraph 各跑 3 个查询） | 验证截图 | 0.5h |

**验收标准**：
- [ ] 5 工具 × 3 场景 = 15 次全成功
- [ ] L3 7 种知识类型可写可查
- [ ] Graph 三端点返回真实数据（不是空列表）
- [ ] 所有真问题修复并有回归测试

**回滚策略**：每个工具 / 端点的修复独立 commit，可独立回滚。

---

## 四、依赖关系图

```
MVP-1（端到端真跑）─────────┐
                            ├──→ MVP-2（TaskStore PG）  ──→ MVP-8（9 工具 + L3 + Graph）
                            ├──→ MVP-3（Session PG）    ──┘
                            ├──→ MVP-4（Container 去嵌套）
                            ├──→ MVP-5（前端抽组件）
                            ├──→ MVP-6（日志 + health）
                            └──→ MVP-7（MinIO）
```

**关键路径**：MVP-1 → MVP-2 / MVP-3 → MVP-8（共 3 天）
**并行任务**：MVP-4 / MVP-5 / MVP-6 / MVP-7 全部依赖 MVP-1，可串行或 2 人并行（共 2 天）

---

## 五、执行计划（5 天冲刺）

```
Day 1  上午  MVP-1.1 ~ 1.5  准备环境 + 写脚本
Day 1  下午  MVP-1.6 ~ 1.7  跑 3 轮 + 修 P0 bug
Day 1  晚上  MVP-1.8       复测全链路 ✅

Day 2  上午  MVP-2         TaskStore 落 PG（0.5 天）
Day 2  下午  MVP-6         结构化日志 + 深健康（0.5 天）

Day 3  上午  MVP-3 前半    Session snapshot 表 + repo
Day 3  下午  MVP-3 后半    集成 + 状态机接入

Day 4  上午  MVP-4         Container 去嵌套
Day 4  下午  MVP-5         前端抽 3 组件

Day 5  上午  MVP-7         MinIO 接入
Day 5  下午  MVP-8         9 工具 + L3 + Graph 真验
Day 5  晚上  写 MVP 完成报告 + 更新 CHECKLIST
```

---

## 六、里程碑与验收

| 里程碑 | 完成节点 | 验收依据 |
|--------|---------|---------|
| **M-MVP-1** | Day 1 结束 | 端到端脚本能跑通，全部 9 步成功，3 轮 × 3 项目 = 9 次无 P0 错 |
| **M-MVP-2** | Day 3 结束 | TaskStore + Session 状态机持久化通过测试，重启后旧状态可查 |
| **M-MVP-3** | Day 5 结束 | 全部 8 项任务完成，综合分从 55 提升到 80+ |
| **M-MVP-4** | Day 5 + 1 天 | 全部 8 项任务有回归测试 + 文档记录 |

> **每个 M-MVP 通过后**：合并到 `refactor/v2` + 更新 `docs/CHECKLIST.md` + 在 PR 链接中附上验证截图。

---

## 七、风险总览

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| MVP-1 真跑发现大量 P0 bug（>10） | 中 | Day 1 无法收尾 | 优先修阻塞主链路的 bug，次要 bug 推 Day 6 修复 |
| LLM API 限流或余额不足 | 中 | MVP-1 跑不通 | 准备 2 个 API Key 切换；限流时记录重试次数 |
| MinIO 网络下载慢 | 低 | MVP-7 超时 | 国内镜像加速 / 提前拉镜像 |
| 持久化方案性能瓶颈 | 低 | MVP-2/3 延迟超标 | 用 JSONB + 索引；按 session_id 分区 |
| 前端组件化引入新 bug | 中 | MVP-5 页面渲染异常 | 每个组件独立 PR，灰度发布 |

---

## 八、回滚策略

每个任务独立 commit，**不引入破坏性 schema 变更**：
- MVP-2 / MVP-3：新增 PG 表 + 字段，原行为可通过 `FEATURE_OUTPUT_PERSIST=false` / `FEATURE_SESSION_PERSIST=false` 关闭
- MVP-4：保留旧 `pipeline.execute` 同步路径作为 fallback
- MVP-5：纯前端重构，git revert 即可
- MVP-6：日志中间件可关闭
- MVP-7：`L0_STORAGE_BACKEND=local` 切回本地
- MVP-8：纯测试 + bug 修复，无功能开关

**总回滚开关**：`MVP_HARDENING_ENABLED=false` 一次性关闭 MVP-2/3/4/6/7 的新增功能（环境变量级总闸）。

---

## 九、文档配套

| 文档 | 关系 |
|------|------|
| [MVP-02_MVP_VERIFICATION_CHECKLIST.md](MVP-02_MVP_VERIFICATION_CHECKLIST.md) | 配套验收清单：8 项任务的逐项验证步骤 + 判定标准 + 签字栏 |
| [04_IMPLEMENTATION_ROADMAP.md](../04_IMPLEMENTATION_ROADMAP.md) | 母路线图，本计划是其 v1.0 后续的"补完冲刺" |
| [CHECKLIST.md](../CHECKLIST.md) | 验收记录，每个 M-MVP 通过后更新 |
| [C-04_API_CONTRACT_REGISTRY.md](C-04_API_CONTRACT_REGISTRY.md) | 如新增 API 端点需同步注册 |
| [C-06_DATABASE_MIGRATION_PLAN.md](C-06_DATABASE_MIGRATION_PLAN.md) | 新增表需同步注册 |
| [C-03_CONFIGURATION_REGISTRY.md](C-03_CONFIGURATION_REGISTRY.md) | 新增配置项需同步注册 |

---

## 十、总结

本计划定义 8 项 MVP 必做任务，总计 5 天完成，预期把 V2 从"代码到位 Demo 阶段（55 分）"提升到"MVP 可交付阶段（80 分）"。核心原则：

1. **MVP 优先**：砍掉所有非 MVP 必要工作（gRPC、性能、组件库美化、多租户等）
2. **真跑验证**：MVP-1 是所有后续任务的输入，真问题比读代码猜的准 10 倍
3. **关键持久化**：TaskStore + Session 状态机是 MVP 阶段最常被忽视的"重启即丢"问题
4. **可观测性补丁**：深健康检查 + 结构化日志是排障必备，0.5 天工作量价值 5 分
5. **每个任务独立可回滚**：通过 feature flag 关闭，总闸一键回退

完成本计划后，V2 进入"接近 Beta 级"状态，可作为内部 demo 工具长期使用，下一轮可开始 P10 性能升级或认知飞轮 E2E 验证。
