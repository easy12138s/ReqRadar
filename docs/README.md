# ReqRadar V2 文档体系

## Agent 阅读顺序（推荐）

### 第一遍：理解项目（必须，2 份）

1. [00_PROJECT_POSITIONING.md](00_PROJECT_POSITIONING.md) — 项目是什么、不是什么、战略边界
2. [01_RESTUCTURE_OVERVIEW.md](01_RESTUCTURE_OVERVIEW.md) — V1→V2 核心转变、Runtime 架构蓝图

### 第二遍：理解架构（必须，3 份）

3. [02_SYSTEM_ARCHITECTURE.md](02_SYSTEM_ARCHITECTURE.md) — 技术栈选型、8 服务拓扑、核心子系统设计
4. [03_COGNITIVE_ASSET_MODEL.md](03_COGNITIVE_ASSET_MODEL.md) — L0→L3 四层认知资产模型（核心理论）
5. [04_IMPLEMENTATION_ROADMAP.md](04_IMPLEMENTATION_ROADMAP.md) — 11 Phase 分阶段实施计划

### 第三遍：编码前必读（必须，2 份）

6. [detailed/C-01_CODING_CONVENTIONS.md](detailed/C-01_CODING_CONVENTIONS.md) — 每一行代码的编写规则
7. [detailed/C-02_MODULE_DEPENDENCY_MAP.md](detailed/C-02_MODULE_DEPENDENCY_MAP.md) — 文件放哪、能 import 什么、禁止 import 什么

### 第零步：搭建开发环境

**编码前必须完成。** 完整步骤见 [AGENTS.md](../AGENTS.md) §0.5"环境准备"。

核心信息速查：

| 项 | 值 |
|----|-----|
| Python | 3.12.13（conda env: `reqradar`） |
| 包管理器 | pip（已配国内镜像，下载速度快） |
| 本地数据库 | SQLite（无需 PostgreSQL） |
| 配置文件 | `pyproject.toml` + `.env`（从 `.env.example` 复制） |
| 安装命令 | `conda activate reqradar && pip install -e reqradar/kernel` |
| 验证命令 | `pytest tests/unit/kernel/ -v` |
| P0-P1 不需要 | PostgreSQL / Redis / MinIO / Docker |

### 补充阅读：架构决策记录（ADR，16 份）

当需要理解"**为什么这样设计**"时查阅。每份 ADR 用四段式（Context/Decision/Consequence/Tradeoff）记录一条关键架构决策的背景、选择原因和权衡过程。

| 编号 | 决策 | 关联 Phase | 一句话 |
|------|------|-----------|--------|
| [001](adr/001-traefik-gateway.md) | Traefik 边缘网关 | P2 | 为什么选 Traefik 而非 Nginx/Caddy/Kong |
| [002](adr/002-auth-independent-service.md) | Auth 独立服务 | P2 | 为什么 JWT Secret 只能由 auth-service 持有 |
| [003](adr/003-kernel-minimal.md) | Kernel 最小化 | P0 | 为什么 Kernel ≤3000 行、不含业务逻辑 |
| [004](adr/004-chatback-in-cognitive-rt.md) | Chatback 留在 Runtime | P3 | 为什么追问功能不独立成服务 |
| [005](adr/005-phase1-http-communication.md) | Phase 1 用 HTTP | P2-P9 | 为什么初期不用 gRPC/Kafka |
| [006](adr/006-phase1-shared-postgresql.md) | Phase 1 共享 PG | 全 Phase | 为什么初期不分库 |
| [007](adr/007-uv-workspace-monorepo.md) | uv Monorepo | P0 | 为什么弃 Poetry 选 uv |
| [008](adr/008-future-ux-design.md) | 前端不兼容 V1 | P8 | 为什么 V2 前端全新设计而非渐进改造 |
| [009](adr/009-ingestion-independent.md) | Ingestion 独立 | P6 | 为什么文件解析必须独立服务 |
| [010](adr/010-api-bff-pattern.md) | BFF 模式 | P7 | 为什么前端经过 api-service 聚合而非直连各服务 |
| [011](adr/011-cognitive-session-first-class.md) | Session 一等公民 | P3 | 为什么 Session 不是数据库记录而是 Runtime 实体 |
| [012](adr/012-context-pipeline-p1.md) | Context Pipeline P1 | P1 | 为什么上下文工程优先于 Runtime 核心 |
| [013](adr/013-event-stream-redis.md) | Event Stream Redis | P3 | 为什么事件用 Redis Streams 而非 Kafka/PG |
| [014](adr/014-tool-runtime.md) | ToolRuntime 中间层 | P4 | 为什么工具管控不在 BaseTool 内实现 |
| [015](adr/015-graph-capability-reserved.md) | Graph 能力预留 | P5+ | 为什么当前用 PG 关联表而非 Neo4j |
| [016](adr/016-checkpoint-persistence.md) | Checkpoint 持久化 | P3 | 为什么 cognitive-rt 创建、index-service 存储 |

### 第四遍：按 Phase 查阅

#### P0 — Kernel 抽离

| 文档 | 用途 |
|------|------|
| [AGENTS.md](../AGENTS.md) | Agent 工作指南（§0.5 环境准备 + §3 工作流 + §4 命令） |
| [C-02_MODULE_DEPENDENCY_MAP.md](detailed/C-02_MODULE_DEPENDENCY_MAP.md) | kernel/ 目录精确文件清单 + 公开接口 |
| [C-06_DATABASE_MIGRATION_PLAN.md](detailed/C-06_DATABASE_MIGRATION_PLAN.md) | Batch 1 基础表 DDL |
| [CODE_WIKI.md](CODE_WIKI.md) | V1 代码全景参考（需要搬迁哪些代码） |
| ADR [003](adr/003-kernel-minimal.md) [007](adr/007-uv-workspace-monorepo.md) | 为什么 Kernel 最小化 + 为什么用 uv |

#### P1 — 模块化单体 + Context Pipeline

| 文档 | 用途 |
|------|------|
| [R-02_CONTEXT_PIPELINE.md](detailed/R-02_CONTEXT_PIPELINE.md) | 五阶段流水线设计 + Token Budget + Quality Gate |
| [C-01_CODING_CONVENTIONS.md](detailed/C-01_CODING_CONVENTIONS.md) | 编码模板（Pydantic/FastAPI/SQLAlchemy） |
| [C-05_TEST_SPECIFICATION.md](detailed/C-05_TEST_SPECIFICATION.md) | 测试命名/边界覆盖/mock 规则 |
| [M-01_EVIDENCE_MODEL.md](detailed/M-01_EVIDENCE_MODEL.md) | 10 种证据类型 + 生命周期 + 证据链 |
| [M-02_SEVEN_DIMENSION_FRAMEWORK.md](detailed/M-02_SEVEN_DIMENSION_FRAMEWORK.md) | 七维度语义 + 评估流程 |
| [C-06_DATABASE_MIGRATION_PLAN.md](detailed/C-06_DATABASE_MIGRATION_PLAN.md) | Batch 2 L0/L1 表 + Batch 3 L2 表 DDL |
| ADR [012](adr/012-context-pipeline-p1.md) | 为什么 Context Pipeline 比 Runtime Core 更优先 |

#### P3 — Cognitive Runtime Core

| 文档 | 用途 |
|------|------|
| [R-01_SESSION_LIFECYCLE.md](detailed/R-01_SESSION_LIFECYCLE.md) | 11 状态状态机 + 转换规则 |
| [R-03_EVENT_STREAM_SCHEMA.md](detailed/R-03_EVENT_STREAM_SCHEMA.md) | 三级事件体系 + Redis Streams + WS 广播 |
| [R-05_CHECKPOINT_DESIGN.md](detailed/R-05_CHECKPOINT_DESIGN.md) | 三区存储 + 版本链 + 恢复流程 |
| [C-04_API_CONTRACT_REGISTRY.md](detailed/C-04_API_CONTRACT_REGISTRY.md) | Session/Event/Checkpoint 端点 Schema |
| ADR [004](adr/004-chatback-in-cognitive-rt.md) [011](adr/011-cognitive-session-first-class.md) [013](adr/013-event-stream-redis.md) [016](adr/016-checkpoint-persistence.md) | Chatback/Session/Event/Checkpoint 四项架构决策 |

#### P4 — ToolRuntime

| 文档 | 用途 |
|------|------|
| [R-04_TOOL_RUNTIME.md](detailed/R-04_TOOL_RUNTIME.md) | 六项管控能力 + 工具迁移方案 |
| [C-03_CONFIGURATION_REGISTRY.md](detailed/C-03_CONFIGURATION_REGISTRY.md) | Tool Domain 配置项（9 项） |
| ADR [014](adr/014-tool-runtime.md) | 为什么工具管控不在 BaseTool 内实现 |

#### P5 — 拆 index-service + L3 知识治理

| 文档 | 用途 |
|------|------|
| [M-03_PROJECT_COGNITIVE_STATE.md](detailed/M-03_PROJECT_COGNITIVE_STATE.md) | 7 种 L3-A 知识类型 Schema + 治理框架 |
| [M-04_COGNITIVE_GRAPH_SCHEMA.md](detailed/M-04_COGNITIVE_GRAPH_SCHEMA.md) | Relation Contract + 图谱查询接口 |
| [C-06_DATABASE_MIGRATION_PLAN.md](detailed/C-06_DATABASE_MIGRATION_PLAN.md) | Batch 4/5 L3-A 知识表 + 关系表 DDL |
| [detailed/I-03_DATA_MIGRATION_PLAN.md](detailed/I-03_DATA_MIGRATION_PLAN.md) | V1→V2 字段级映射 + 迁移脚本框架 |
| ADR [015](adr/015-graph-capability-reserved.md) | 为什么当前用 PG 关联表而非 Neo4j |

#### P2 — Gateway + Auth

| 文档 | 用途 |
|------|------|
| [I-01_SERVICE_API_CONTRACT.md](detailed/I-01_SERVICE_API_CONTRACT.md) | 8 组服务间 API 完整契约 |
| [I-02_DEPLOYMENT_DEVOPS.md](detailed/I-02_DEPLOYMENT_DEVOPS.md) | Docker Compose / CI/CD / 监控 |
| [S-01_SECURITY_DESIGN.md](detailed/S-01_SECURITY_DESIGN.md) | 威胁模型 / 认证流程 / 审计日志 |
| ADR [001](adr/001-traefik-gateway.md) [002](adr/002-auth-independent-service.md) [005](adr/005-phase1-http-communication.md) | Gateway/Auth/HTTP 三项基础设施决策 |

#### P6-P10 — 后续 Phase

| Phase | 文档 | 状态 |
|-------|------|------|
| P6 拆 output-service | 04 路线图 P6 节 | 概述已有，详细待补充 |
| P6 拆 ingestion-service | 04 路线图 P6 节 + [INGESTION_SERVICE_PLAN](detailed/INGESTION_SERVICE_PLAN.md) | ✅ 详细规划已完成；ADR [009](adr/009-ingestion-independent.md) 说明为什么独立 |
| 项目管理模块 | [PROJECT_MANAGEMENT_PLAN](detailed/PROJECT_MANAGEMENT_PLAN.md) | ✅ 详细规划已完成（三种创建场景 + 代码索引 + 项目画像 + 需求摄取） |
| P7 BFF 独立 | 04 路线图 P7 节 | 概述已有；ADR [010](adr/010-api-bff-pattern.md) 说明 BFF 模式 |
| P8 前端改造 | 04 路线图 P8 节 + [F-01](detailed/F-01_FRONTEND_DESIGN.md) | ✅ 功能架构设计已完成，UI 美化延后 |
| P9 MCP 独立 | 04 路线图 P9 节 | 概述已有，详细待补充 |
| P10 性能升级 | 04 路线图 P10 节 | 概述已有，详细待补充 |

---

## 文档状态总览

| 编号 | 文件名 | 定位 | 状态 | 版本 |
|------|--------|------|------|------|
| 00 | 00_PROJECT_POSITIONING.md | 项目宪法 | ✅ 已完成 | v1.0 |
| 01 | 01_RESTUCTURE_OVERVIEW.md | Runtime 蓝图 | ✅ 已完成 | v2.1 |
| 02 | 02_SYSTEM_ARCHITECTURE.md | 总体架构 | ✅ 已完成 | v1.2 |
| 03 | 03_COGNITIVE_ASSET_MODEL.md | 认知资产模型 | ✅ 已完成 | v1.1 |
| 04 | 04_IMPLEMENTATION_ROADMAP.md | 实施路线图 | ✅ 已完成 | v1.2 |
| — | CODE_WIKI.md | V1 代码参考 | ✅ 已完成 | — |
| — | AGENTS.md | Agent 工作指南（环境 + 工作流 + 命令） | ✅ 已完成 | v2.0 |
| — | CHECKLIST.md | 开发进度追踪（验收记录） | ✅ 已完成 | v1.0 |
| — | REVIEW_CHECKLIST.md | Code Review 检查清单 | ✅ 已完成 | v1.0 |
| C-01 | C-01_CODING_CONVENTIONS.md | 编码规范 | ✅ 已完成 | v1.0 |
| C-02 | C-02_MODULE_DEPENDENCY_MAP.md | 模块依赖地图 | ✅ 已完成 | v1.0 |
| C-03 | C-03_CONFIGURATION_REGISTRY.md | 配置注册表 | ✅ 已完成 | v1.0 |
| C-04 | C-04_API_CONTRACT_REGISTRY.md | API 契约注册表 | ✅ 已完成 | v1.0 |
| C-05 | C-05_TEST_SPECIFICATION.md | 测试规范 | ✅ 已完成 | v1.0 |
| C-06 | C-06_DATABASE_MIGRATION_PLAN.md | 数据库迁移计划 | ✅ 已完成 | v2.0 |
| M-01 | M-01_EVIDENCE_MODEL.md | Evidence 模型 | ✅ 已完成 | v1.0 |
| M-02 | M-02_SEVEN_DIMENSION_FRAMEWORK.md | 七维度框架 | ✅ 已完成 | v1.0 |
| M-03 | M-03_PROJECT_COGNITIVE_STATE.md | L3 认知状态 | ✅ 已完成 | v1.0 |
| M-04 | M-04_COGNITIVE_GRAPH_SCHEMA.md | 认知图谱 | ✅ 已完成 | v1.0 |
| R-01 | R-01_SESSION_LIFECYCLE.md | Session 生命周期 | ✅ 已完成 | v1.0 |
| R-02 | R-02_CONTEXT_PIPELINE.md | Context Pipeline | ✅ 已完成 | v1.0 |
| R-03 | R-03_EVENT_STREAM_SCHEMA.md | Event Stream | ✅ 已完成 | v1.0 |
| R-04 | R-04_TOOL_RUNTIME.md | ToolRuntime | ✅ 已完成 | v1.0 |
| R-05 | R-05_CHECKPOINT_DESIGN.md | Checkpoint | ✅ 已完成 | v1.0 |
| I-01 | I-01_SERVICE_API_CONTRACT.md | 服务间 API 契约 | ✅ 已完成 | v1.0 |
| I-02 | I-02_DEPLOYMENT_DEVOPS.md | 部署与 DevOps | ✅ 已完成 | v1.0 |
| I-03 | I-03_DATA_MIGRATION_PLAN.md | 数据迁移方案 | ✅ 已完成 | v1.0 |
| S-01 | S-01_SECURITY_DESIGN.md | 安全设计专篇 | ✅ 已完成 | v1.0 |
| F-01 | F-01_FRONTEND_DESIGN.md | 前端功能架构设计 | ✅ 已完成 | v1.0 |
| — | INGESTION_SERVICE_PLAN.md | ingestion-service 实施规划 | ✅ 已完成 | v1.0 |
| — | PROJECT_MANAGEMENT_PLAN.md | 项目管理模块规划 | ✅ 已完成 | v1.0 |
| — | adr/ | 架构决策记录（16 条） | ✅ 已完成 | v1.0 |

---

## 文档编号规则

```
顶层（docs/）：
  0X_PROJECT_POSITIONING.md          # 项目宪法与愿景
  0X_RESTRUCTURE_OVERVIEW.md         # 重构蓝图
  0X_SYSTEM_ARCHITECTURE.md          # 技术架构
  0X_COGNITIVE_ASSET_MODEL.md        # 认知资产模型
  0X_IMPLEMENTATION_ROADMAP.md       # 实施路线图
  CODE_WIKI.md                       # V1 代码全景

详细设计（docs/detailed/）：
  C-XX_CODING_CONVENTIONS.md         # Coding — 编码约束
  C-XX_MODULE_DEPENDENCY_MAP.md      # Coding — 模块依赖
  C-XX_CONFIGURATION_REGISTRY.md     # Coding — 配置注册表
  C-XX_API_CONTRACT_REGISTRY.md      # Coding — API 契约
  C-XX_TEST_SPECIFICATION.md         # Coding — 测试规范
  C-XX_DATABASE_MIGRATION_PLAN.md    # Coding — 数据库迁移

  M-XX_EVIDENCE_MODEL.md             # Model — Evidence 模型
  M-XX_SEVEN_DIMENSION_FRAMEWORK.md  # Model — 七维度框架
  M-XX_PROJECT_COGNITIVE_STATE.md    # Model — L3 认知状态
  M-XX_COGNITIVE_GRAPH_SCHEMA.md     # Model — 认知图谱

  R-XX_SESSION_LIFECYCLE.md          # Runtime — Session 生命周期
  R-XX_CONTEXT_PIPELINE.md           # Runtime — Context Pipeline
  R-XX_EVENT_STREAM_SCHEMA.md        # Runtime — Event Stream
  R-XX_TOOL_RUNTIME.md               # Runtime — ToolRuntime
  R-XX_CHECKPOINT_DESIGN.md          # Runtime — Checkpoint

  I-XX_xxx.md                        # Infrastructure — 基础设施
  S-XX_xxx.md                        # Security — 安全设计
  F-XX_xxx.md                        # Frontend — 前端设计
```

- **前缀 C** = Coding（编码约束：风格/依赖/配置/API/测试/迁移）
- **前缀 M** = Model（数据模型：Evidence/维度/认知状态/图谱）
- **前缀 R** = Runtime（运行时：Session/Context/Event/Tool/Checkpoint）
- **前缀 I** = Infrastructure（基础设施：服务间契约/部署/迁移）
- **前缀 S** = Security（安全设计）
- **前缀 F** = Frontend（前端设计）

---

## 文档维护规则

### 新增文档时

1. 在本文档"文档状态总览"表格中添加一行
2. 在本文档"按 Phase 查阅"对应 Phase 下添加引用
3. 在被引用文档的"前置文档"、"参考文档"等章节中补充新文档编号
4. 更新 `02_SYSTEM_ARCHITECTURE.md` 第 13 节"文档配套关系"表

### 修改文档时

1. 递增文档内的版本号
2. 如果修改影响其他文档（如 API Schema 变更 → C-04 需同步），必须同步更新
3. 重大修改后，检查所有引用该文档的"前置文档"字段是否需要调整

### Agent 编码后自检

以下检查项应在代码提交前完成：

```
[ ] 确认所有引用的设计文档编号存在（对照本文档"文档状态总览"）
[ ] 确认代码风格符合 C-01（编码规范）
[ ] 确认 import 依赖符合 C-02（模块依赖地图）
[ ] 如果新增 API 端点，确认已在 C-04（API 契约注册表）注册
[ ] 如果新增配置项，确认已在 C-03（配置注册表）注册
[ ] 如果新增数据库表，确认已在 C-06（数据库迁移计划）注册
[ ] 如果新增异常类型，确认已在 C-01 异常层次图中注册
[ ] 测试覆盖 C-05 规定的 9 项边界场景
```

### 版本号规则

- 文档版本号独立于项目版本号
- 每次内容修改后递增（v1.0 → v1.1）
- 结构性重写时递增主版本号（v1.x → v2.0）
