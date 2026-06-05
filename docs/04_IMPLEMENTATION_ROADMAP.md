# ReqRadar V2 — 实施路线图

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.2 |
| 文档定位 | V2 重构的实施路线图、Phase 拆分与验收标准 |
| 前置文档 | 00_PROJECT_POSITIONING.md（项目宪法）、01_RESTRUCTURE_OVERVIEW.md（Runtime 蓝图）、02_SYSTEM_ARCHITECTURE.md（总体架构设计）、03_COGNITIVE_ASSET_MODEL.md（认知资产模型） |
| 核心目标 | 将架构蓝图转化为可执行、可验证、可回滚的分阶段实施计划 |
| 文档职责 | 定义每个 Phase 的任务清单、依赖关系、验收标准、里程碑、风险与回滚策略 |

---

## 一、总体原则

### 1.1 演进哲学

```
先验证核心假设 → 再构建 Runtime 核心能力 → 再完善基础设施 → 最后优化性能与服务拆分
```

V2 重构的最大风险不是技术实现，而是**产品核心假设是否成立**：Context Pipeline 是否真的比 f-string 拼接更智能？Checkpoint 是否真的能让分析可恢复？L2→L3 的认知飞轮是否真的越转越快？

Phase 的排序遵循一个铁律：**能最早验证核心假设的，优先级最高。**

### 1.2 每个 Phase 的定义标准

| 要素 | 要求 |
|------|------|
| **输入** | 依赖的前置 Phase 产出 |
| **任务清单** | 可分配给单人、2-3 天内可完成的具体任务 |
| **验收标准** | 可执行、可验证的 Definition of Done，不是"代码写完" |
| **可演示成果** | 每个 Phase 结束时有可展示的功能增量 |
| **回滚策略** | 如果失败，如何回到上一个可工作状态 |

### 1.3 分支策略

```
develop（V1 维护）
    │
    └── refactor/v2（V2 重构主分支，始终保持最新可工作状态）
            │
            ├── refactor/v2-p1（Phase 分支，完成后合并回 refactor/v2）
            ├── refactor/v2-p2
            └── ...
```

**铁律**：
- **Phase 分支必须从 `refactor/v2` 拉出**：`git checkout -b refactor/v2-p{N} refactor/v2`
- **Phase 验收通过后必须合并回 `refactor/v2`**：验收人执行合并 + 更新 CHECKLIST.md
- **合并回主分支后才能开始下一个 Phase**
- **严禁 Phase 分支之间直接合并**（必须通过 `refactor/v2` 中转）
- **master 不动**，等所有 Phase 完成后一次性合并

**验收合并流程**（每个 Phase 完成后必须执行）：

```
编码 Agent 负责：
  1. 自检（ruff + pytest）
  2. 通知验收人验收

验收人负责：
  3. 验收通过后，执行合并：git checkout refactor/v2 && git merge refactor/v2-p{N} --no-ff
  4. 更新 docs/CHECKLIST.md
  5. 通知编码 Agent 开始下一个 Phase

编码 Agent 开始下一个 Phase：
  6. 从最新 refactor/v2 拉出新分支：git checkout -b refactor/v2-p{N+1} refactor/v2
```

> **教训**：P0-P9 期间因缺乏此约束，所有 Phase 分支从未合并回 `refactor/v2`，导致主分支停留在 P0 时代，最终需要手动修复。此流程确保类似问题不再发生。

---

## 二、Phase 总览

| Phase | 名称 | 核心目标 | 依赖 | 预计周期 |
|-------|------|---------|------|---------|
| **P0** | Kernel 抽离 | 建立类型与枚举的唯一定义源 | 无 | 1 周 |
| **P1** | 模块化单体 + Context Pipeline | **验证认知运行时智力（核心假设）** | P0 | 4 周 |
| **P3** | Cognitive Runtime Core | Session / Event / Checkpoint / Runtime State | P1 | 4 周 |
| **P2** | Gateway + Auth 独立化 | 引入 Traefik，Auth 独立服务 | P3 | 2 周 |
| **P4** | ToolRuntime | 工具管控中间层 | P3 | 2 周 |
| **P5** | 拆 index-service | ChromaDB 独立，认知存储独立，L3 知识治理完整落地 | P3 | 3 周 |
| **P6** | 拆 output-service | 报告渲染独立 | P5 | 1 周 |
| **P7** | BFF 独立 | api-service 独立为前端聚合层 | P2 | 1 周 |
| **P8** | 前端改造 | 前端独立容器化、V2 全新界面适配 | P7 | 4 周 |
| **P9** | MCP 独立 | integration-service 可选部署 | P5 | 2 周 |
| **P10** | 性能升级 | 热点路径 HTTP → gRPC | P5 | 2 周 |

> **注**：P2 从原计划的 P3 之前调整到 P3 之后，以降低 P1 验证失败时的沉没成本。P1 完成后仅引入最小 Traefik 配置以满足 P3 开发期间的 WebSocket 调试需要，不进行 Auth 独立化。

---

## 三、Phase 详细设计

---

### P0：Kernel 抽离

**目标**：建立 reqradar-kernel，作为所有服务的类型与枚举的唯一定义源。

**依赖**：无

**任务清单**：

| # | 任务 | 产出 | 估时 |
|---|------|------|------|
| P0.1 | 初始化 uv workspace Monorepo 结构 | `pyproject.toml`（根 + kernel） | 0.5 天 |
| P0.2 | 从 V1 搬迁 ORM 模型（19 张表） | `kernel/models.py` | 1 天 |
| P0.3 | 从 V1 搬迁/合并枚举定义 | `kernel/enums.py` | 0.5 天 |
| P0.4 | 合并 V1 异常层次（web + core） | `kernel/exceptions.py` | 0.5 天 |
| P0.5 | 搬迁 SessionFactory 和数据库基类 | `kernel/database.py` | 0.5 天 |
| P0.6 | 定义 Scope×Domain 配置基类 | `kernel/config_base.py` | 1 天 |
| P0.7 | 编写 Kernel 包的使用铁律文档 | `kernel/README.md` | 0.5 天 |
| P0.8 | 为 Kernel 编写单元测试 | `tests/kernel/` | 1 天 |

**验收标准**：
- [ ] `reqradar-kernel` 可通过 `uv sync` 被其他 workspace 成员引用
- [ ] 所有 ORM 模型可被 SQLAlchemy 正确映射
- [ ] 枚举值与原 V1 定义一致
- [ ] 异常层次覆盖 V1 所有已知错误类型
- [ ] Scope×Domain 配置模型可通过 JSON Schema 验证
- [ ] Kernel 包总代码行数 ≤ 3000
- [ ] 所有公开接口有 docstring

**可演示成果**：在 Python REPL 中导入 `reqradar_kernel` 并实例化 ORM 模型、枚举、异常。

**回滚策略**：P0 是纯类型定义，不涉及运行时代码。如果失败，删除 `refactor/v2-p0` 分支即可，无影响。

---

### P1：模块化单体 + Context Pipeline（核心假设验证）

**目标**：在 V1 代码基础上按新架构边界重组模块结构，并实现 Context Pipeline（五阶段上下文工程），**验证"上下文工程优于 f-string 拼接"这一核心假设**。这是决定 V2 是否继续推进的关键 Phase。

**依赖**：P0

**Context Pipeline 数据源的过渡策略**：
- P1 阶段：Collect 通过统一的 `ContextSource` 接口适配 V1 的 project_memory/user_memory 等数据源
- P5 完成后：增加 `L3ContextSource` 适配器，Collect 通过配置切换即可从 L3 拉取知识，无需重构
- 这保证了 P1 的 Context Pipeline 在 P5 之后平滑过渡，不产生技术债

**任务清单**：

| # | 任务 | 产出 | 估时 |
|---|------|------|------|
| P1.1 | 在单体服务内建立新的目录边界 | `cognitive_rt/`、`index_svc/`、`output_svc/` 等目录 | 1 天 |
| P1.2 | 将 `agent/*` 重组到 `cognitive_rt/cognition/` | 迁移 ReAct Agent、Evidence System | 2 天 |
| P1.3 | 将 `modules/vector_store.py` 移至 `index_svc/` | 向量检索独立边界 | 0.5 天 |
| P1.4 | 将 `modules/memory*.py` 移至 `index_svc/memory/` | Memory 系统独立边界 | 1 天 |
| P1.5 | 将 `core/report.py` 移至 `output_svc/` | 报告渲染独立边界 | 0.5 天 |
| P1.6 | **实现 Context Pipeline 五阶段流水线**（分解为 5 个子任务） | Collect → Score → Select → Compress → Assemble | 7 天 |
| P1.6a | 实现 Collect 阶段：多数据源适配器（project_memory, user_memory, code_graph, vector_results, git_history），通过 ContextSource 接口统一访问；定义 ContextKind 枚举（SOURCE_CODE / REQUIREMENT / ARCH_DOC / GIT_HISTORY / MEMORY / INFERRED_KNOWLEDGE）及各类型基础权重 | 各数据源适配器 + ContextSource 接口 + ContextKind 枚举 | 2 天 |
| P1.6a.5 | 实现 Quality Gate 检查点：有效 context 条目 ≥ 2、最高语义得分 ≥ 0.65、代码证据数 ≥ 1；不满足时进入 LOW_CONTEXT_CONFIDENCE 模式，降低推理激进度，输出报告标注"证据不足，结论仅供参考" | QualityGate 模块 | 0.5 天 |
| P1.6b | 实现 Score 阶段：相关性评分算法（语义相似度 + 时间衰减 + 用户标记 + ContextKind 基础权重叠加） | 评分函数 + 权重配置 | 1.5 天 |
| P1.6c | 实现 Select 阶段：Token 预算约束下的贪心选择 | 预算感知选择器 | 1.5 天 |
| P1.6d | 实现 Compress 阶段：摘要生成与截断策略 | 摘要 prompt 模板 + 截断逻辑 | 1 天 |
| P1.6e | 实现 Assemble 阶段：按优先级排序、添加元数据标记、格式标准化 | 最终上下文组装器 | 1 天 |
| P1.7 | 实现 Token Budget 控制机制 | token_counter + budget_enforcer | 1 天 |
| P1.8 | 实现至少 2 种 Context Strategy | 风险分析策略 / 架构理解策略 | 2 天 |
| P1.9 | 修改 Agent 推理入口，使用 Context Pipeline 替代 f-string | `cognitive_rt/cognition/agent.py` | 2 天 |
| P1.10 | 对比测试：Context Pipeline vs 原始 f-string 的分析质量 | 测试用例 + 质量评分脚本 | 3 天 |

**P1.10 对比测试评估标准**：

质量维度：

| 维度 | 评估方法 | 通过标准 |
|------|---------|---------|
| **风险识别准确率** | 人工评审（3 份需求 × 2 人交叉评审），标注"风险点"并比对 V1/V2 的召回率和精确率 | V2 召回率 ≥ V1，精确率 ≥ V1 |
| **证据溯源完整度** | 检查分析报告中每个结论是否可追溯到 L0/L1 证据 | V2 有源可溯的结论占比 ≥ V1 |
| **分析覆盖度** | 人工标注每份需求的"应覆盖模块"，比对分析报告中的模块命中率 | V2 命中率 ≥ V1 |
| **整体质量评估** | LLM-as-judge（GPT-4）对分析报告的完整性、准确性、可操作性打分（1-10） | V2 均分 ≥ V1 均分 |

成本维度：

| 指标 | 通过标准 | 说明 |
|------|---------|------|
| **avg token cost / 次分析** | ≤ V1 的 1.5 倍 | 超出则说明 Token Budget 控制失效 |
| **context assembly 延迟** | ≤ 2s | Collect → Assemble 总耗时 |
| **总分析延迟** | ≤ V1 的 1.3 倍 | 用户感知的等待时间 |

**通过标准**：
- 四个质量维度：人工评审中 V2 优于或等于 V1 的样本 ≥ 2/3
- 三个成本维度：全部满足
- **质量和成本同时达标，M1 才判定为通过**

**fail-fast 规则**（任一触发直接判负，不进入均分比较）：
- 出现 1 次"关键风险完全未识别"（人工标注的高风险点在 V2 报告中无任何提及）
- context assembly 延迟 > 5s（用户不可接受的等待）
- avg token cost > V1 的 2 倍（成本失控）

**验收标准**：
- [ ] 新旧目录边界清晰，但服务仍以单体方式运行
- [ ] Context Pipeline 五阶段全部实现且可独立测试
- [ ] Token Budget 控制：任意输入下，组装后的上下文不超过预算的 105%
- [ ] Agent 使用 Context Pipeline 完成一次完整的需求分析，生成报告
- [ ] 前端用户体验无变化（API 路径和响应格式未变）
- [ ] Quality Gate 在不满足阈值时正确触发 LOW_CONTEXT_CONFIDENCE 模式，输出报告包含免责声明
- [ ] ContextKind 枚举已定义，Score 阶段按类型应用不同基础权重
- [ ] **P1.10 对比测试通过**（质量和成本同时达标，这是 M1 里程碑的 Go/No-Go 决策依据）
- [ ] ContextSource 接口已预留 L3 数据源适配能力，为 P5 平滑过渡做好准备

**可演示成果**：上传同一份需求文档，分别用 V1 和 V2-P1 分析，展示 V2 的推理步骤更聚焦、上下文引用更精准。

**风险与应对**：

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Context Pipeline 质量不如 f-string（P1.10 测试不通过） | **致命** | V2 核心假设失败 | 保留 f-string fallback；P1 结束后根据对比测试决定是否继续 V2。若失败，仅保留目录重组和 P0 成果，V2 暂停 |
| P1.6 Context Pipeline 实现超时 | 中 | 影响后续 Phase 启动 | P1 周期已预留缓冲；P1.6 已拆分为 5 个子任务便于追踪进度 |

**回滚策略**：P1 的所有改动在 `refactor/v2` 分支内。如果核心假设验证失败，`cognitive_rt/cognition/agent.py` 回退到 f-string 模式，其余重组保留。

---

### P3：Cognitive Runtime Core

**目标**：实现 CognitiveSession 生命周期管理、Event Stream、Checkpoint System，建立 Runtime State 管理能力。**这是 V2 最关键的技术 Phase。**

**依赖**：P1

**前置准备**：P1 完成后，仅引入 Traefik 最小配置（一个下午），用于 WebSocket 路由调试，不进行 Auth 独立化。

**任务清单**：

| # | 任务 | 产出 | 估时 |
|---|------|------|------|
| P3.1 | 实现 CognitiveSession 状态机 | `cognitive_rt/runtime/session.py` | 3 天 |
| P3.2 | 实现 Session 生命周期 API | CRUD + 状态转换 | 1 天 |
| P3.3 | 实现 Event Stream 发布器（Session/Reasoning/Cognitive 三类事件） | `cognitive_rt/runtime/events.py` | 2 天 |
| P3.4 | 实现 Redis Streams 事件发布/消费者组 | `cognitive_rt/runtime/event_bus.py` | 2 天 |
| P3.5 | 实现 Checkpoint 创建逻辑 | `cognitive_rt/runtime/checkpoint.py` | 2 天 |
| P3.6 | 实现 Checkpoint 状态分区（热/冷/可重建） | 分区策略 + MinIO 客户端 | 2 天 |
| P3.7 | 实现 index-service 的 Checkpoint 存储 API | `index_svc/api/checkpoint_api.py` | 2 天 |
| P3.8 | 实现 Checkpoint 恢复逻辑 | 从 index-service 拉取快照 → 重建 Runtime State | 3 天 |
| P3.9 | 实现 WebSocket 事件推送 | api-service 订阅 Redis Pub/Sub → 前端推送 | 2 天 |
| P3.10 | 修改 Agent 推理循环，每步发布事件 + 定期 Checkpoint | 集成到 ReAct 循环 | 2 天 |
| P3.11 | 集成测试：创建 Session → 运行 3 步推理 → 中断 → 从 Checkpoint 恢复 → 继续完成 | E2E 测试 | 3 天 |

**验收标准**：
- [ ] CognitiveSession 完整经历 CREATED → RUNNING → CHECKPOINTING → COMPLETED 状态转换
- [ ] Event Stream 实时推送到前端，延迟 < 2s
- [ ] 推理中断后，从最近的 Checkpoint 恢复，步骤数和证据链一致
- [ ] Checkpoint 热状态存在 PG JSONB，冷状态存在 MinIO，可重建状态不占持久化存储
- [ ] cognitive-rt 重启后，未完成的 Session 可从 Checkpoint 恢复

**可演示成果**：启动一次分析 → 在推理进行到第 3 步时手动停掉 cognitive-rt → 重启 → 从第 2 步的 Checkpoint 恢复 → 分析继续完成，前端感知到中断和恢复。

**风险与应对**：

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Checkpoint 恢复时状态不一致 | 高 | 分析结果错误 | P3.8 实现后必须做 20+ 次中断恢复测试，覆盖不同推理阶段 |
| Event Stream 体积膨胀，Redis 内存压力 | 中 | Redis OOM | 设置 Redis Streams MAXLEN 限制 + 消费确认机制 |

**回滚策略**：P3 改动集中在 `cognitive_rt/runtime/`，如 Checkpoint 恢复逻辑不稳定，可暂时禁用 Checkpoint 功能，Session 仍以线性方式执行。

> **P3 启动前置条件**：
> 1. 更新 01 文档的 CognitiveSession 状态机，将 CANCELLED 单状态扩展为 CANCELLING → CANCELLED / TIMEOUT / ABORTED 分支。
> 2. 定义 Checkpoint 事务保证（架构层面）：
>    - **写入原子性**：Checkpoint 写入 PG JSONB + 关联 Event 必须在同一事务
>    - **恢复时校验**：恢复时校验 Evidence 链完整性，不通过则拒绝恢复（返回上一致点）
>    - **失败安全**：Checkpoint 写入失败时，Session 不应继续推进（宁可中断，不输出错误结论）
>    - **可降级**：Checkpoint 写入失败时，自动切换为"无 Checkpoint 模式"继续执行（降级而不中断）

---

### P2：Gateway + Auth 独立化

**目标**：引入 Traefik 作为边缘网关，将 Auth 抽离为独立服务，建立服务间通信的基础设施。

**依赖**：P3（P3 期间已引入最小 Traefik 配置，此处完整实现）

**任务清单**：

| # | 任务 | 产出 | 估时 |
|---|------|------|------|
| P2.1 | Docker Compose 完善 Traefik + Redis 配置 | `docker-compose.yml` 最终版 | 1 天 |
| P2.2 | 完善 Traefik 路由规则（含 WebSocket） | 动态配置或静态规则 | 1 天 |
| P2.3 | 创建 auth-service 独立目录 + FastAPI 应用骨架 | `services/auth/` | 1 天 |
| P2.4 | 从单体中搬迁 auth 相关代码（JWT 签发/验证、用户 CRUD） | auth-service 路由 + 服务逻辑 | 2 天 |
| P2.5 | 实现服务间 Internal-API-Key 认证 | 中间件 | 1 天 |
| P2.6 | 配置 Redis Streams 基础连接 | 各服务 Redis 客户端封装 | 1 天 |
| P2.7 | 集成测试：前端请求经过 Traefik 路由到各服务 | E2E 测试用例 | 2 天 |

**验收标准**：
- [ ] Traefik 正确路由 `/api/*` 到对应服务
- [ ] Auth 独立服务可独立部署、独立重启
- [ ] JWT 签发与校验功能与 V1 一致
- [ ] 服务间调用携带 Internal-API-Key，非授权请求被拒绝
- [ ] Redis Streams 可成功发布/订阅消息

**可演示成果**：启动完整 Docker Compose，通过 Traefik 访问前端，登录、创建项目、触发分析，一切正常。

**风险与应对**：

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Traefik 路由配置复杂，WebSocket 路由失败 | 中 | 前端实时推送中断 | P2.2 时重点验证 WS 路由 |

**回滚策略**：如果 Traefik 引入后稳定性问题频发，暂时回退到 FastAPI 直接暴露端口，Auth 可保留独立服务或合并回单体。

---

### P4：ToolRuntime

**目标**：在工具注册表之上增加管控中间层，为每个工具提供超时、重试、权限校验、自动 Checkpoint 和事件记录能力。

**依赖**：P3

**任务清单**：

| # | 任务 | 产出 | 估时 |
|---|------|------|------|
| P4.1 | 定义 ToolRuntime 接口与能力声明 Schema | `cognitive_rt/runtime/tool_runtime.py` | 1 天 |
| P4.2 | 实现超时控制（asyncio.wait_for） | 可配置超时 | 1 天 |
| P4.3 | 实现重试策略（指数退避） | 可配置最大重试次数 | 1 天 |
| P4.4 | 实现工具执行前后自动 Checkpoint | 与 P3 Checkpoint 集成 | 1 天 |
| P4.5 | 实现工具调用事件记录 | TOOL_INVOKED / TOOL_RETURNED | 0.5 天 |
| P4.6 | 实现权限校验（基于 Scope×Domain） | 工具级权限检查 | 1 天 |
| P4.7 | 迁移现有工具（search_code/get_deps/read_file 等）到 ToolRuntime | 适配层 | 2 天 |
| P4.8 | 集成测试：工具超时自动中断、重试后成功 | 测试用例 | 1 天 |

**验收标准**：
- [ ] 所有工具通过 ToolRuntime.execute() 调用
- [ ] 工具超时后自动中断，不超过配置超时 + 2s
- [ ] 工具失败后按配置重试，重试次数可验证
- [ ] 每次工具调用自动发布事件
- [ ] 关键工具调用前后自动创建 Checkpoint

**可演示成果**：触发一个会超时的工具调用，前端实时看到 TOOL_INVOKED → 超时中断 → 自动重试 → TOOL_RETURNED 的完整事件链。

---

### P5：拆 index-service（含 L3 知识治理完整落地）

**目标**：将 index-service 拆分为独立服务，ChromaDB 独立，同时**完整落地 03 文档定义的七种 L3-A 知识类型和知识治理框架**，实现 L2→L3 的认知沉淀和知识资产治理。

**依赖**：P3

**任务清单**：

| # | 任务 | 产出 | 估时 |
|---|------|------|------|
| P5.1 | 创建 index-service 独立 FastAPI 应用 | `services/index/` | 1 天 |
| P5.2 | 搬迁 ChromaDB 连接和向量检索逻辑 | 独立向量存储服务 | 2 天 |
| P5.3 | 搬迁 Checkpoint 存储和查询逻辑 | 独立 Checkpoint 管理 | 2 天 |
| P5.4 | **实现七种 L3-A 知识类型的沉淀与演化** | 知识沉淀引擎（七模块） | 5 天 |
| P5.4a | 术语表沉淀（新术语追加、confidence 累加、用户可确认） | 术语管理模块 | 1 天 |
| P5.4b | 模块画像沉淀（职责描述更新、风险历史追加、依赖快照） | 模块画像模块 | 1 天 |
| P5.4c | 架构约束沉淀（从 Evidence 提取 constraint 类型、用户显式声明） | 约束管理模块 | 1 天 |
| P5.4d | 决策记录沉淀（从需求分析和 Chatback 中提取、时间线组织） | 决策记录模块 | 0.5 天 |
| P5.4e | 风险演化沉淀（canonical_risk_id 归并、演化轨迹记录、跨 Session 追踪） | 风险演化模块 | 0.5 天 |
| P5.4f | 需求谱系沉淀（派生/冲突/依赖关系推断、版本演化链） | 需求谱系模块 | 0.5 天 |
| P5.4g | 事故记忆沉淀（用户录入 + Git revert/hotfix 自动识别） | 事故记忆模块 | 0.5 天 |
| P5.5 | **实现知识新鲜度管理**（stale 检测、90 天阈值、freshness 状态迁移） | 新鲜度管理模块 | 1.5 天 |
| P5.6 | **实现知识置信度计算**（verification_count 累加、衰减曲线、human_verified 提升） | 置信度计算模块 | 1.5 天 |
| P5.7 | **实现 knowledge_changelog 记录**（append-only、字段变更追踪） | 变更日志模块 | 1 天 |
| P5.8 | **实现 knowledge_relations 表和 Relation Contract 接口**（source_type/id、relation_type、target_type/id、confidence、evidence_ref） | 统一关系存储 + 接口 | 1 天 |
| P5.9 | **实现 L3ContextSource 适配器**（供 Context Pipeline 的 Collect 阶段从 L3 拉取 active+high-confidence 知识） | L3ContextSource | 1 天 |
| P5.10 | 搬迁项目画像生成逻辑 | 聚合模块 | 1 天 |
| P5.11 | 设计 V1 数据迁移到 V2 四层模型的映射方案 | 迁移方案文档 + 脚本框架 | 2 天 |
| P5.12 | 集成测试：L3 知识沉淀 → 治理生效 → Context Pipeline 从 L3 注入 → 认知飞轮可验证 | E2E 测试 | 2 天 |

**验收标准**：
- [ ] index-service 可独立部署、独立重启
- [ ] cognitive-rt 通过 HTTP 调用 index-service 的检索和 Checkpoint API，功能不变
- [ ] ChromaDB 仅 index-service 持有连接
- [ ] 七种 L3-A 知识类型均可通过 API 创建、查询、更新（append-only）
- [ ] L3 知识记录包含 freshness、confidence、changelog 等治理元数据
- [ ] stale 知识（超过 90 天未验证）自动标记，不被 Context Pipeline 注入
- [ ] knowledge_relations 表支持统一关系查询，接口符合 Relation Contract 定义
- [ ] L3ContextSource 适配器可被 Context Pipeline 的 Collect 阶段调用，返回经过新鲜度和置信度过滤的知识
- [ ] **认知飞轮可验证运转**（复合指标，三项同时达标）：
  - `effective_injection_rate` = 被后续 Session 引用的知识数 / 总知识数 ≥ 60%
  - `confidence_weighted_score` = Σ(confidence × citation_count) / N ≥ 0.5
  - `diversity_index` = 知识类型分布不能畸高（任何单一类型占比 ≤ 40%）
- [ ] **飞轮自我验证通过**：每 10 次 Session 沉淀运行一次对比实验，L3 注入质量 ≥ 占位 L3 质量
- [ ] V1 数据迁移方案已完成设计，包含回滚操作手册且已在测试环境验证

**可演示成果**：对同一项目连续分析 3 次，查看 L3 知识库的增长情况、新鲜度状态、置信度分布、关系图谱和变更日志。Context Pipeline 从 L3 自动注入历史知识，分析报告引用历史约束和风险。

> **P5 启动前置条件**：
> 1. 更新 03 文档的 freshness 模型，增加 `conflicted` 状态。新知识与已有 L3 知识矛盾时，旧知识标记为 `conflicted`，新知识以 confidence=0.3 暂存，等待人工确认。
> 2. 设计 L3Writer 统一写入接口（`append` / `update` / `deprecate` / `merge`），7 种知识类型共用此接口。详见 03 文档 7.4 节 L3 写入语义矩阵。
> 3. 设计飞轮自我验证机制的 verification_log 表和对比实验框架。详见 03 文档 7.3 节。

---

### P6：拆 output-service

**依赖**：P5

**任务**：创建 output-service，搬迁报告渲染和版本管理。

**验收标准**：output-service 可独立部署，模板热更新不重启其他服务。

---

### P7：BFF 独立

**依赖**：P2

**任务**：创建 api-service，搬迁 Dashboard/项目详情/配置管理 API。

**验收标准**：api-service 可独立部署，前端所有功能正常。

---

### P8：前端改造

**目标**：实现前端独立容器化、V2 全新界面适配，包括全新的认知仪表盘、Event Stream 可视化、Checkpoint 时间线回放等。**这是"不兼容 V1"承诺的兑现。**

**依赖**：P7（BFF 独立后前端有稳定的聚合 API）

**任务清单**：

| # | 任务 | 产出 | 估时 | 优先级 |
|---|------|------|------|--------|
| P8.1 | 前端独立容器化（Nginx/Caddy 托管静态产物） | Dockerfile + 部署配置 | 2 天 | 必须 |
| P8.2 | 前端路由适配全新 `/api/v2/` API | 前端客户端重构 | 3 天 | 必须 |
| P8.3 | 实现 WebSocket Event Stream 结构化推送的前端消费 | 实时事件展示组件 | 3 天 | 必须 |
| P8.4 | 实现项目认知仪表盘（L3 可视化） | 风险热力图、约束清单、术语云、决策时间线 | 5 天 | 必须 |
| P8.5 | 实现 Checkpoint 时间线回放界面 | 会话回放器 | 3 天 | **可降级** |
| P8.6 | 实现全新分析交互界面（Session 创建、进度展示、Chatback 对话） | 分析界面重构 | 4 天 | 必须 |

**降级策略**：P8.5（Checkpoint 时间线回放）标记为可降级任务。若 P8.4 或其他任务超时，P8.5 可推迟到 V2.1 实现，不影响 P8 的验收通过。

**验收标准**：
- [ ] 前端独立容器化，通过 `/app/*` 路由访问，与后端服务解耦
- [ ] 前端所有 API 调用使用 `/api/v2/` 路径，旧 V1 路由完全移除
- [ ] WebSocket 实时推送推理步骤和事件，延迟 < 2s
- [ ] 认知仪表盘展示 L3 知识库的实时状态（风险热力图、约束清单、术语云、决策时间线）
- [ ] 用户可通过全新界面创建项目、上传需求、启动分析、实时观察推理过程

**可演示成果**：访问 V2 前端，创建项目、上传需求文档、启动分析，在全新界面上实时观察 Agent 的推理步骤，分析完成后查看认知仪表盘的更新。

---

### P9：MCP 独立

**依赖**：P5

**任务**：创建 integration-service，搬迁 MCP Server 运行时、API Key 管理、审计日志。

**验收标准**：integration-service 可独立部署，Cursor/Windsurf 可通过 MCP 读取需求、记忆、报告。

---

### P10：性能升级

**依赖**：P5

**任务**：cognitive-rt → index-service 热点路径升级为 gRPC，连接池优化，Checkpoint JSONB 查询优化。

**验收标准**：cognitive-rt → index-service 调用延迟降低 50%+，单次分析 Token 消耗不超过 V1 的 1.2 倍。

---

## 四、依赖关系图（调整后）

```
P0 ──→ P1 ──→ P3 ──→ P2 ──→ P7 ──→ P8
         │       │
         │       ├──→ P4
         │       │
         │       └──→ P5 ──→ P6
         │               │
         │               ├──→ P9
         │               │
         │               └──→ P10
         │
         └──→ (M-01~M-04, R-01~R-05 详细设计文档按需并行推进)
```

- **P0** 是一切的基础
- **P1** 验证核心假设，**M1 里程碑决定是否继续**
- **P3** 是 Runtime 核心，P2/P4/P5 依赖它
- **P2** 移到了 P3 之后，减少 P1 失败时的浪费
- **P5** 是认知资产治理的核心，P6/P9/P10 依赖它
- **P8** 是用户体验的最终交付，依赖 P7

---

## 五、里程碑与可演示成果

| 里程碑 | Phase | 可演示成果 | 关键决策点 |
|--------|-------|-----------|-----------|
| **M1** | P1 完成 | Context Pipeline 分析质量对比测试报告 | **决定是否继续推进 V2**（P1.10 通过则继续，否则暂停） |
| **M2** | P3 完成 | 分析中断后从 Checkpoint 恢复，继续完成 | 确认 Runtime 核心能力达标 |
| **M3** | P5 完成 | index-service 独立部署，认知飞轮完整运转，L3 七种知识类型全部沉淀，治理框架生效 | 确认 L2→L3 沉淀机制可行，知识资产不腐化 |
| **M4** | P8 完成 | V2 全新前端上线，认知仪表盘可用 | 确认用户体验达到"不兼容 V1"的目标 |
| **M5** | P9 完成 | MCP 集成分发认知到 IDE | 确认外部生态集成能力 |
| **M6** | P10 完成 | 全服务独立部署，性能达标 | V2 可合并到 master，替换 V1 |

---

## 六、风险总览

| 风险 | 严重程度 | 发生 Phase | 应对 |
|------|---------|-----------|------|
| Context Pipeline 质量不如 f-string（P1.10 不通过） | **致命** | P1 | 保留 f-string fallback；P1 结束后根据对比测试决定去留。此为 M1 决策点 |
| Checkpoint 恢复状态不一致 | **高** | P3 | 大量恢复测试 + 状态校验机制 |
| L3 知识膨胀，Context Pipeline 无法有效利用 | **高** | P5+ | 03 文档定义的知识治理框架（新鲜度/置信度）在 P5 完整落地 |
| L3 知识类型实现遗漏，认知飞轮运转不完整 | **中** | P5 | P5.4 已拆分为七种知识类型的独立子任务 |
| 服务拆分后网络延迟增加 | **中** | P5-P8 | P10 升级 gRPC；内部网络通信延迟本身极低 |
| 团队并行开发时接口契约冲突 | **中** | 全 Phase | P0 Kernel 先确定共享类型；每个 Phase 启动前确认接口契约 |
| V1→V2 数据迁移失败导致用户数据丢失 | **中** | P5+ | P5.11 设计迁移方案含回滚验证，执行前全量备份 |
| 前端改造周期过长，影响 V2 整体交付 | **中** | P8 | P3 完成后启动前端原型设计；P8.5 标记为可降级 |

---

## 七、补充：数据迁移策略概览

V1 到 V2 的数据迁移将在 P5 阶段完成详细设计，当前明确以下原则：

| V1 数据 | V2 目标 | 迁移方式 |
|---------|---------|---------|
| 用户表 | auth-service 用户表 | 直接搬迁，字段基本一致 |
| 项目表 | api-service 项目表 | 直接搬迁，新增 `project_id` 关联 L3 知识库 |
| `analysis_tasks` | L2 `cognitive_sessions` + `events` | 映射为 Session 记录，原分析结果作为初始 Evidence |
| `project_memory` | L3 初始知识库 | 拆分为七种 L3-A 知识类型，初始 confidence=0.5 |
| 上传文件 | L0 MinIO | 直接迁移文件，PG 中建立 `raw_context` 元数据 |

迁移将在 P5 之后、V2 正式上线前执行，必须支持回滚到 V1。迁移方案需包含回滚操作手册，并在测试环境验证通过。

---

## 八、总结

V2 的实施路线图遵循 **"先验证核心假设，再构建 Runtime 核心能力，再完善基础设施，最后优化性能与服务拆分"** 的演进哲学。

- **P0** 建立类型基础设施
- **P1** 验证"上下文工程优于 f-string"这一产品核心假设——**M1 是决定 V2 生死的关键决策点**
- **P3** 构建 Runtime 核心能力（Session/Event/Checkpoint）
- **P2-P7** 逐步完善基础设施和服务拆分
- **P5** 完整落地 L3 七种知识类型和知识治理框架，确保认知飞轮长期健康
- **P8** 交付 V2 全新前端体验
- **P9-P10** 完善生态集成和性能优化

每个 Phase 都有明确的验收标准和回滚策略，确保 V2 的每一步都走得稳健。从 P1 的 M1 决策点，到 P5 的认知飞轮量化验证，到 P8 的用户体验交付，这份路线图确保了 V2 的核心价值——**让组织不再失忆，让 AI 对项目的知识可以持续积累、追溯、演化和治理**——能够一步步从蓝图变为现实。
