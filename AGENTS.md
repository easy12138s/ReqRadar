# AGENTS.md — ReqRadar V2 Agent 工作指南

## 0. 首次进入：必读启动流程

收到任何开发任务后，按以下顺序阅读——不要跳，每次新建会话都要走一遍：

```
第1步: docs/00_PROJECT_POSITIONING.md (3min)
        → 理解"这不是普通 CRUD 项目，是认知运行时系统"
        → 重点读"ReqRadar 不是什么"章节

第2步: docs/01_RESTUCTURE_OVERVIEW.md (5min)
        → 理解 V1→V2 的核心转变：功能集合 → Runtime System
        → 重点读"Runtime Flow"图 + 四大核心抽象

第3步: docs/02_SYSTEM_ARCHITECTURE.md (5min)
        → 理解整体技术架构和服务边界
        → 重点读分层架构和依赖方向

第4步: docs/03_COGNITIVE_ASSET_MODEL.md (5min)
        → 理解 L0→L3 四层认知资产模型
        → 重点读数据流铁律

第5步: 阅读本文件（AGENTS.md）全程规则
```

### 0.5 环境准备（首次必做，3 分钟）

```bash
# 1. 激活 conda 环境
conda activate reqradar

# 2. 确认 Python 版本 ≥ 3.12
python --version

# 3. 安装内核包（可编辑模式，含 sqlalchemy + pydantic + aiosqlite）
pip install -e reqradar/kernel

# 4. 安装开发工具
pip install ruff mypy pytest pytest-asyncio pytest-cov coverage
```

**镜像加速**：pip 已配置阿里云/清华/豆瓣镜像，`pip install` 自动走国内源。

完成后用以下命令验证环境：

```bash
pytest tests/unit/kernel/ -v       # P0 测试应全部通过
ruff check reqradar/kernel/          # 无 lint 错误
```

**技术栈速查：**

| 项 | 值 |
|----|-----|
| Python | 3.12.13（conda env: `reqradar`） |
| 包管理器 | pip（已配国内镜像） |
| Kernel 安装 | `pip install -e reqradar/kernel`（可编辑模式） |
| 本地数据库 | SQLite（`reqradar_dev.db`），无需 PostgreSQL |
| Lint/Format | ruff |
| 类型检查 | mypy |
| 测试 | pytest + pytest-asyncio |

**不需要的服务**（开发阶段）：
- PostgreSQL（用 SQLite 替代）
- Redis（后续阶段）
- MinIO（后续阶段）
- Docker（P2+ 阶段可选）

### 0.6 Docker 开发环境（P2+ 阶段可选）

本地已安装 Docker 时，可用于多服务集成测试：

```bash
# 复制环境变量模板
cp .env.example .env

# 启动全部服务（Traefik + PG + Redis + Auth + API + Cognitive-RT + Index + Output）
docker compose up -d

# 查看服务状态
docker compose ps

# 查看某个服务日志
docker compose logs -f api-service

# 重建单个服务（代码修改后）
docker compose build cognitive-rt && docker compose up -d cognitive-rt

# 停止全部服务
docker compose down

# 停止并清除数据卷（重置数据库）
docker compose down -v
```

> **日常开发仍用 conda**，Docker 用于验证多服务集成、Traefik 路由、服务间通信等场景。

---

## 1. 核心宪法（不可协商规则）

以下规则违反任何一条 = 代码不可合入。

### 1.1 编码铁律（来源：C-01 编码规范）

| # | 规则 | 反例 |
|---|------|------|
| 1 | `str | None` 不用 `Optional[str]` | `Optional[str]` |
| 2 | `list[str]` 不用 `List[str]` | `from typing import List` |
| 3 | 绝对导入，禁止相对导入 | `from ..exceptions import` |
| 4 | 异常必须带 `cause` 链 | `raise LLMException("fail")` 无 cause |
| 5 | Docstring/注释用中文，标识符用英文 | 注释写英文、变量写中文 |
| 6 | Pydantic 所有字段必须有 `Field(description="中文描述")` | `name: str` 无 Field |
| 7 | 禁止裸 `except:` 和 `except Exception: pass` | 吞异常 |
| 8 | 禁止 `print()` 替代日志 | `print("debug")` |
| 9 | 禁止模块级 `load_config()` 直接调用 | 端点用 `request.app.state.config` |
| 10 | f-string 格式化日志 | `logger.info(f"value={x}")` |

### 1.2 依赖铁律（不可违反）

```
kernel/  → 只依赖 stdlib + third-party（禁止依赖 web/modules/agent/mcp/cli）
modules/ → 只依赖 kernel + infrastructure（禁止依赖 web/agent）
cognitive_rt/ → 只依赖 kernel + modules + infrastructure → 禁止依赖 web
web/     → 只依赖 kernel + modules + cognitive_rt → 禁止依赖 cli
cli/     → 可依赖所有内层
```

**同层隔离**：`web/api/*` 各路由之间禁止互相 import，`web/services/*` 各服务之间禁止互相 import。

### 1.3 数据流铁律（来源：03 认知资产模型）

```
L0 Raw Context (MinIO) → 不可变，不参与语义检索
L1 Structured Facts (PG+ChromaDB) → 可索引，不包含推理结论
L2 Analysis Records (PG JSONB) → 追加不可改，每次分析完整记录
L3 Persistent Knowledge (PG+ChromaDB) → 追加演化，受治理框架约束
```

所有结论必须可追溯到 L0/L1 证据，否则不可输出为分析结果。

### 1.4 测试铁律

- 每个测试函数使用独立 SQLite + `tmp_path`，不依赖执行顺序
- 必须 mock LLM / 网络 / Git / MinIO / Redis
- 不使用真实 home 目录或开发数据库
- 覆盖 9 项边界：成功/401/403/404/422/409/空列表/外部服务失败/路径遍历

---

## 2. 目录结构与职责

```
reqradar/
├── __init__.py
├── kernel/                     # Layer 0 — 最小共享内核（不依赖任何 reqradar 模块）
│   ├── __init__.py
│   ├── types.py               # 共享类型：ContextKind, Scope, Domain 等
│   ├── enums.py               # 全局枚举：SessionStatus, EventType 等
│   ├── exceptions.py          # 异常层次（ReqRadarException + 子类）
│   ├── database.py            # SQLAlchemy Base + 异步引擎工厂
│   ├── models.py              # 32 张 ORM 模型
│   ├── config_base.py         # Scope×Domain 配置基类 + 三级解析链
│   └── ...
│
├── infrastructure/            # 基础设施（依赖 kernel）
│   ├── config.py              # Pydantic 配置模型
│   ├── logging.py             # 日志配置
│   ├── paths.py               # 路径工具
│   └── ...
│
├── modules/                   # 外部模块适配（依赖 kernel + infrastructure）
│   ├── llm_client.py          # LiteLLM 统一客户端
│   ├── code_parser.py         # 代码解析
│   ├── vector_store.py        # 向量存储（ChromaDB）
│   └── ...
│
├── cognitive_rt/              # 认知运行时核心（依赖 kernel + modules + infrastructure）
│   ├── cognition/             # Agent 推理层
│   ├── runtime/               # Session/Event/Checkpoint/Tool 运行时
│   └── ...
│
├── index_svc/                 # 索引服务（L3 知识 + Checkpoint）
├── output_svc/                # 输出服务（报告渲染 + 任务管理）
├── web/                       # FastAPI Web 层
│   ├── api/v2/                # V2 API 路由
│   └── ...
│
└── cli/                       # 命令行工具
```

---

## 3. 编码工作流

每当被分配一个具体开发任务时：

```
Step 0: 确认环境
  → conda activate reqradar
  → python --version（确认 ≥ 3.12）
  → pip install -e reqradar/kernel（确保内核包最新）

Step 1: 确定文件归属
  → 如果新增文件：按依赖铁律判断放哪个目录（kernel/infrastructure/modules/cognitive_rt/web/cli）
  → 如果修改文件：确认当前路径不违反依赖铁律

Step 2: 编写代码
  → 严格遵守 §1 核心宪法（编码+依赖+数据流+测试）
  → Pydantic 模型必须每个字段有 Field(description="中文描述")
  → Docstring 用中文，标识符用英文

Step 3: 数据库变更（若新增表）
  → 按 Alembic 规范生成迁移脚本
  → 确保 upgrade() 和 downgrade() 都实现
  → 检查命名规范符合约定

Step 4: 编写测试
  → 按 C-05 命名规则：test_{功能}_{场景}_{预期}.py
  → 按测试铁律 mock 外部依赖
  → 覆盖成功/失败/边界场景

Step 5: 自检（全部通过才能提交）
  → ruff check reqradar/ tests/
  → ruff format --check reqradar/ tests/
  → mypy reqradar/kernel/
  → 确认无 lint 错误、格式错误、类型错误

Step 6: 提交
  → git add .
  → git commit -m "<type>(<scope>): <short description>"（英文格式）
  → git push
```

---

## 4. 常用命令速查

```bash
# === 环境 ===
conda activate reqradar                # 激活 conda 环境（每次新终端必做）
pip install -e reqradar/kernel          # 安装/更新内核包

# === 代码质量 ===
ruff check reqradar/ tests/            # lint
ruff format --check reqradar/ tests/   # format check
mypy reqradar/kernel/                  # 类型检查
ruff check reqradar/ tests/ && ruff format --check reqradar/ tests/ && mypy reqradar/kernel/  # 三件套

# === 测试 ===
pytest -q                               # 全量
pytest tests/unit/kernel/ -v           # P0 单元测试
pytest tests/unit/ -v                  # 全部单元测试
pytest -k "test_config" -v             # 关键字过滤
pytest --cov=reqradar --cov-report=term-missing  # 覆盖率

# === 数据库 ===
alembic revision --autogenerate -m "V2_P1_create_xxx"  # 生成迁移
alembic upgrade head                   # 应用迁移
alembic downgrade -1                   # 回滚一步

# === 部署（Docker） ===
docker compose up -d                   # 启动全部服务
docker compose ps                      # 查看状态
docker compose logs -f api-service     # 查看日志
docker compose build cognitive-rt      # 重建单个服务
docker compose down                    # 停止全部服务
docker compose down -v                 # 停止并清除数据卷
docker compose exec api-service alembic upgrade head  # 迁移

# === 依赖合规检查 ===
python scripts/check_dependencies.py   # 验证依赖铁律
```

---

## 5. Git 提交规范

### 5.1 分支策略

```
develop（V1 维护）
    └── refactor/v2（V2 主分支，始终保持最新可工作状态）
            ├── refactor/v2-p1（Phase 分支）
            ├── refactor/v2-p2
            └── ...
```

**铁律**：
- **Phase 分支必须从 `refactor/v2` 拉出**：`git checkout -b refactor/v2-p{N} refactor/v2`
- **Phase 验收通过后必须合并回 `refactor/v2`**：验收人执行合并 + 更新进度文档
- **合并回主分支后才能开始下一个 Phase**
- **验收人确认通过后，才能开始下一个 Phase**
- **严禁 Phase 分支之间直接合并**（必须通过 `refactor/v2` 中转）
- **master 不动**，等所有 Phase 完成后一次性合并

### 5.2 提交格式

- **格式**: `<type>(<scope>): <short description>`
  - type: `feat` / `fix` / `refactor` / `docs` / `chore` / `style` / `test` / `ci` / `perf`
  - scope: 影响模块名，如 `feat(kernel): add session state machine`
- **语言**: 英文
- **每完成一个子任务提交一次**，不要积攒到最后一次性提交

### 5.3 Phase 完成后的标准操作流程

**编码 Agent 负责**：
```bash
# 1. 自检
ruff check reqradar/ tests/ services/ && pytest tests/ -q

# 2. 通知验收人验收
```

**验收人负责**：
```bash
# 3. 验收通过后，执行合并
git checkout refactor/v2
git merge refactor/v2-p{N} --no-ff -m "merge: P{N} complete"

# 4. 更新进度文档

# 5. 通知编码 Agent 开始下一个 Phase
```

**编码 Agent 开始下一个 Phase**：
```bash
# 6. 从最新 refactor/v2 拉出新分支
git checkout -b refactor/v2-p{N+1} refactor/v2
```

---

## 6. 关键文件速查

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | 根项目配置（uv workspace + ruff + mypy + pytest） |
| `.env.example` | 环境变量模板（复制为 `.env` 使用） |
| `AGENTS.md`（本文件） | Agent 工作指南（环境 + 规则 + 流程 + 命令） |
| `docs/00_PROJECT_POSITIONING.md` | 项目宪法（项目是什么/不是什么） |
| `docs/01_RESTUCTURE_OVERVIEW.md` | Runtime 架构蓝图 |
| `docs/02_SYSTEM_ARCHITECTURE.md` | 服务拓扑和分层设计 |
| `docs/03_COGNITIVE_ASSET_MODEL.md` | L0-L3 认知资产模型和数据流 |
| `scripts/check_dependencies.py` | 依赖合规检查脚本 |

---

## 7. 重要提醒

- **V2 不兼容 V1**——API 路径全新（`/api/v2/`），数据库全新 Schema
- 遇到"为什么这样设计"——但所有设计文档已完成使命，核心规则都在本文件中
- 不确定文件放哪——对照 §1.2 依赖铁律判断层级
- 不确定命名格式——对照 §1.1 编码铁律，见项目现有代码风格
- 不确定测试怎么写——对照 §1.4 测试铁律
- 不确定依赖是否合规——运行 `python scripts/check_dependencies.py`
