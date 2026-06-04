# ReqRadar V2 — 开发进度追踪

```
本文档在每次 Phase 验收通过后由验收人更新。
编码 Agent 不应修改本文档。
```

## 概览

| 里程碑 | Phase | 状态 | 验收日期 | 核心成果 |
|--------|-------|------|---------|---------|
| — | **P0** — Kernel 抽离 | ✅ **验收通过** | 2026-06-04 | 共享内核：类型/枚举/异常/ORM/配置基类 |
| M1 | **P1** — Context Pipeline | ⚠️ **部分通过** | 2026-06-04 | 五阶段流水线完整实现，126 tests passed |
| — | **P3** — Cognitive Runtime Core | ⬜ 未开始 | — | — |
| — | **P2** — Gateway + Auth | ⬜ 未开始 | — | — |
| — | **P4** — ToolRuntime | ⬜ 未开始 | — | — |
| M3 | **P5** — 拆 index-service + L3 | ⬜ 未开始 | — | — |
| — | **P6** — 拆 output-service | ⬜ 未开始 | — | — |
| — | **P7** — BFF 独立 | ⬜ 未开始 | — | — |
| M4 | **P8** — 前端改造 | ⬜ 未开始 | — | — |
| — | **P9** — MCP 独立 | ⬜ 未开始 | — | — |
| — | **P10** — 性能升级 | ⬜ 未开始 | — | — |

---

## P0 — Kernel 抽离

**验收日期**：2026-06-04

**验收结论**：✅ **通过**

**代码基线**：分支 `refactor/v2-p0` → 合并到 `refactor/v2`

**交付物清单**：

| 文件 | 行数 | 验收 |
|------|------|------|
| `reqradar/kernel/types.py` | 70 | ✅ 6 种共享类型 |
| `reqradar/kernel/enums.py` | 172 | ✅ 14 个枚举（11 V1 + 3 V2 保留 + 10 V2 新增） |
| `reqradar/kernel/exceptions.py` | 82 | ✅ 15 个异常（11 V1 + 4 V2 新增），全部 cause 链 |
| `reqradar/kernel/database.py` | 61 | ✅ 异步引擎 + SQLite/PG 自适应 |
| `reqradar/kernel/models.py` | 771 | ✅ 25 张表（19 V1 搬迁 + 6 V2 新增） |
| `reqradar/kernel/config_base.py` | 189 | ✅ Scope×Domain 三级解析链 |
| `reqradar/kernel/__init__.py` | 113 | ✅ 33 个公开符号完整导出 |
| `tests/unit/kernel/` | 4 个文件 | ✅ 70 tests passed |

**验收指标**：

| 标准 | 结果 |
|------|------|
| Kernel 总行数 ≤ 3000 | ✅ 1,458 行 |
| str \| None  不用 Optional | ✅ 0 处 |
| 绝对导入，禁止相对导入 | ✅ 0 处 |
| 所有公开接口有 docstring | ✅ |
| 枚举值与 V1 一致 | ✅ TaskStatus/ChangeStatus/ReleaseStatus 值一致 |
| ruff check | ✅ 0 errors |
| pytest | ✅ 70 passed in 0.93s |

**修复亮点**：
- UUID 主键改用 `default=uuid4` 代替 `gen_random_uuid()`（兼容 SQLite）
- 根 `pyproject.toml` 移除 uv workspace，改用 `pip install -e` + conda
- 代码风格配置完善（RUF002/RUF003/N818 兼容中文 docstring）

---

## P1 — 模块化单体 + Context Pipeline

**验收日期**：2026-06-04

**验收结论**：⚠️ **部分通过**（核心逻辑完成，V1 搬迁和集成待补）

**代码基线**：分支 `refactor/v2-p1`

### 已完成

| 任务 | 状态 | 交付物 |
|------|------|--------|
| P1.1 目录边界 | ✅ | `cognitive_rt/` `index_svc/` `output_svc/` 全部就绪 |
| P1.6a Collect 阶段 | ✅ | 5 种 ContextSource 适配器 + 去重 |
| P1.6a.5 Quality Gate | ✅ | 3 项阈值 + LOW_CONTEXT_CONFIDENCE 模式 |
| P1.6b Score 阶段 | ✅ | 四因子加权评分 + 时间衰减 + ContextKind 权重 |
| P1.6c Select 阶段 | ✅ | Token 预算贪心选择 + 多样性约束 |
| P1.6d Compress 阶段 | ✅ | 最低分条目标截断 + 二分搜索 |
| P1.6e Assemble 阶段 | ✅ | ContextKind 分组 + 元数据标记 + 免责声明 |
| P1.7 Token Budget | ✅ | TokenCounter（tiktoken/字符估算降级）+ 105% 上限引爆 |
| P1.8 Context Strategy | ✅ | 风险分析策略 + 架构理解策略 |

### 待补（已分配编码 Agent）

| 任务 | 说明 |
|------|------|
| P1.2 | 搬迁 V1 agent/ 到 cognitive_rt/cognition/ |
| P1.3 | 搬迁 vector_store.py 到 index_svc/ |
| P1.4 | 搬迁 memory 系统到 index_svc/memory/ |
| P1.5 | 搬迁 core/report.py 到 output_svc/ |
| P1.9 | Agent 推理入口集成 Context Pipeline + f-string fallback |
| P1.E1 | Batch 2 L0/L1 表迁移脚本 |
| P1.E2 | Batch 3 L2 核心表迁移脚本 |
| P1.10 | 对比测试基础设施 + 测试文档 |

**验收指标**：

| 标准 | 结果 |
|------|------|
| ruff check | ✅ 0 errors |
| ruff format | ✅ 29 files already formatted |
| pytest | ✅ 126 passed（P0: 70 + P1: 56） |
| 依赖合规 | ✅ kernel 仅依赖 stdlib + third-party |
| Pydantic Field(description) | ✅ 全部中文描述 |
| 中文 docstring | ✅ 全部公开函数/类 |

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
