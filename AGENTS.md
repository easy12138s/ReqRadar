# AGENTS.md — ReqRadar V2

## 环境

```bash
conda activate reqradar
pip install -e reqradar/kernel
pip install ruff mypy pytest pytest-asyncio
```

| 项 | 值 |
|----|-----|
| Python | 3.12+ |
| 数据库 | SQLite（本地）/ PostgreSQL（Docker） |
| Lint | ruff |
| 类型检查 | mypy |
| 测试 | pytest + pytest-asyncio |

---

## 架构

ReqRadar 是一个**项目认知运行时系统**，不是 CRUD 应用。核心抽象：

| 抽象 | 职责 |
|------|------|
| CognitiveSession | 一等运行时实体，11 态状态机 |
| Context Pipeline | 五阶段上下文工程（Collect→Score→Select→Compress→Assemble） |
| Event Stream | 结构化推理链事件推送 |
| Checkpoint | 版本化快照，支持中断恢复 |
| ToolRuntime | 工具统一管控（超时/重试/权限/限流） |

### 数据流四层模型

```
L0 Raw Context    → 不可变原文，不参与检索
L1 Structured     → 可索引事实，不含推理结论
L2 Analysis       → 追加不可改，每次分析完整记录
L3 Knowledge      → 追加演化，受治理框架约束
```

所有结论必须可追溯到 L0/L1 证据。

### 目录结构

```
reqradar/
├── kernel/              # 共享类型/枚举/异常/ORM — 不依赖任何内层
├── infrastructure/      # 配置/日志/路径 — 依赖 kernel
├── modules/             # LLM/解析器/向量存储 — 依赖 kernel + infrastructure
├── cognitive_rt/        # 认知运行时核心 — 依赖 kernel + modules + infra
│   ├── cognition/       #   Agent 推理层
│   └── runtime/         #   Session/Event/Checkpoint/Tool
├── index_svc/           # L3 知识 + Checkpoint 存储
├── output_svc/          # 报告渲染 + 任务管理
├── web/                 # FastAPI + api/v2/ 路由
└── cli/                 # 命令行工具
```

---

## 约束

### 编码

| 规则 | 说明 |
|------|------|
| `str \| None` | 不用 `Optional[str]` |
| `list[str]` | 不用 `List[str]` |
| 绝对导入 | 禁止 `from ..xxx import` |
| 异常带 cause 链 | `raise XxxError("msg") from e` |
| 中文注释，英文标识符 | Docstring 用中文 |
| Pydantic 字段描述 | 必须有 `Field(description="中文")` |
| 禁止裸 except | 不吞异常 |
| 禁止 print 日志 | 用 logger |
| f-string 禁止 | logger 中用 `%s` 占位符 |

### 依赖

```
kernel/        → 仅 stdlib + third-party
modules/       → kernel + infrastructure
cognitive_rt/  → kernel + modules + infrastructure
web/           → kernel + modules + cognitive_rt
cli/           → 所有内层
```

同层隔离：`web/api/*` 之间、`web/services/*` 之间禁止互相 import。

### 测试

- 独立 SQLite + `tmp_path`，不依赖执行顺序
- mock 所有外部依赖（LLM/网络/Git/MinIO/Redis）
- 覆盖：成功 / 401 / 403 / 404 / 422 / 409 / 空列表 / 外部服务失败 / 路径遍历

---

## 工作流

```
环境确认 → 确定文件归属 → 写代码 → 写测试 → 自检 → 提交
```

**自检命令**：
```bash
ruff check reqradar/ tests/
ruff format --check reqradar/ tests/
mypy reqradar/kernel/
pytest -q
```

---

## Git

**分支**：`refactor/v2` 为主分支，Phase 分支 `refactor/v2-p{N}` 从它拉出，验收后 `--no-ff` 合并回。

**提交格式**：`<type>(<scope>): <description>`（英文）
- type: `feat` / `fix` / `refactor` / `docs` / `chore` / `test`

---

## 参考文档

| 文档 | 内容 |
|------|------|
| `docs/00_PROJECT_POSITIONING.md` | 项目宪法 |
| `docs/01_RESTUCTURE_OVERVIEW.md` | Runtime 蓝图 |
| `docs/02_SYSTEM_ARCHITECTURE.md` | 服务拓扑 |
| `docs/03_COGNITIVE_ASSET_MODEL.md` | 认知资产模型 |