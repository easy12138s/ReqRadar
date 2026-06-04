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

第3步: docs/04_IMPLEMENTATION_ROADMAP.md (2min)
        → 定位当前该做哪个 Phase（看依赖关系图）
        → 找到对应 Phase 的验收标准和回滚策略

第4步: docs/README.md (3min)
        → 按"第四遍：按 Phase 查阅"找到你当前 Phase 需要的所有文档
        → 按列表逐个阅读
```

**此后**，每次被分配新 Phase 任务时，只需重复第 3-4 步。

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

**镜像加速**：你的 pip 已配置阿里云/清华/豆瓣镜像，`pip install` 会自动走国内源，下载速度很快。

完成后用以下命令验证环境：

```bash
pytest tests/unit/kernel/ -v       # P0 测试应全部通过
ruff check reqradar/kernel/          # 无 lint 错误
```

**技术栈速查：**

| 项 | 值 |
|----|-----|
| Python | 3.12.13（conda env: `reqradar`） |
| 包管理器 | pip（你的 pip 已配国内镜像，自动走阿里云/清华/豆瓣源） |
| Kernel 安装 | `pip install -e reqradar/kernel`（可编辑模式，修改即生效） |
| 本地数据库 | SQLite（`reqradar_dev.db`），无需安装 PostgreSQL |
| Lint/Format | ruff |
| 类型检查 | mypy |
| 测试 | pytest + pytest-asyncio |

**不需要的服务**（P0-P1 阶段）：
- PostgreSQL（用 SQLite 替代）
- Redis（P3 才需要）
- MinIO（P3 才需要）
- Docker（P2 才需要）

## 1. 文档体系使用规则

### 1.1 文档分四类，按需取用

| 类别 | 代表文档 | 什么时候读 |
|------|---------|-----------|
| **世界观** | 00/01/02/03/04 | 每次新会话必读（校准方向） |
| **操作手册** | C-01~C-06 + S-01 | 编码时持续查阅（写一行查一行） |
| **施工图纸** | R-01~R-05 + M-01~M-04 + I-01~I-03 | 理解具体实现细节时查阅 |
| **决策追溯** | adr/ 目录（16 条） | 困惑"为什么这样设计"时查阅 |

### 1.2 文档优先级规则

```
设计文档 > 编码规范 > 代码推测 > 记忆猜测

反例: "我觉得应该这样写" → 违反规则
正例: "R-02 要求五阶段 Collect→Score→Select→Compress→Assemble" → 照做
```

**当文档与现有代码冲突时，以设计文档为准**（V2 是全新构建，不兼容 V1）。

### 1.3 必须查看的"自检清单"

以下清单分散在多个文档中，Agent 提交代码前必须全部打勾：

```
[ ] C-01 第 14 节 禁止事项清单（23 条）
[ ] C-02 第 6 节 禁止依赖清单（14 条）
[ ] C-05 第 13 节 边界覆盖检查清单（9 项）
[ ] S-01 第 11 节 安全检查清单（9 项）
[ ] docs/README.md "Agent 编码后自检"（8 项）
```

## 2. V2 核心宪法（不可协商规则）

以下规则违反任何一条 = 代码不可合入。详细解释在对应文档中，此处仅列要点。

### 2.1 编码铁律（来源：C-01）

| # | 规则 | 反例 |
|---|------|------|
| 1 | `str \| None` 不用 `Optional[str]` | `Optional[str]` |
| 2 | `list[str]` 不用 `List[str]` | `from typing import List` |
| 3 | 绝对导入，禁止相对导入 | `from ..exceptions import` |
| 4 | 异常必须带 `cause` 链 | `raise LLMException("fail")` 无 cause |
| 5 | Docstring/注释用中文，标识符用英文 | 注释写英文、变量写中文 |
| 6 | Pydantic 所有字段必须有 `Field(description="中文描述")` | `name: str` 无 Field |
| 7 | 禁止裸 `except:` 和 `except Exception: pass` | 吞异常 |
| 8 | 禁止 `print()` 替代日志 | `print("debug")` |
| 9 | 禁止模块级 `load_config()` 直接调用 | 端点用 `request.app.state.config` |
| 10 | f-string 格式化日志 | `logger.info(f"value={x}")` |

### 2.2 依赖铁律（来源：C-02）

```
kernel/  → 只依赖 stdlib + third-party（禁止依赖 web/modules/agent/mcp/cli）
modules/ → 只依赖 kernel + infrastructure（禁止依赖 web/agent）
agent/   → 只依赖 kernel + modules（禁止依赖 web）
web/     → 只依赖 kernel + modules + agent（禁止依赖 cli）
cli/     → 可依赖所有内层
```

**同层隔离**：`web/api/*` 各路由之间禁止互相 import，`web/services/*` 各服务之间禁止互相 import。

### 2.3 数据流铁律（来源：03）

```
L0 Raw Context (MinIO) → 不可变，不参与语义检索
L1 Structured Facts (PG+ChromaDB) → 可索引，不包含推理结论
L2 Analysis Records (PG JSONB) → 追加不可改，每次分析完整记录
L3 Persistent Knowledge (PG+ChromaDB) → 追加演化，受治理框架约束
```

所有结论必须可追溯到 L0/L1 证据，否则不可输出为分析结果。

### 2.4 测试铁律（来源：C-05）

- 每个测试函数使用独立 SQLite + `tmp_path`，不依赖执行顺序
- 必须 mock LLM / 网络 / Git / MinIO / Redis
- 不使用真实 home 目录或开发数据库
- 覆盖 9 项边界：成功/401/403/404/422/409/空列表/外部服务失败/路径遍历

## 3. Phase 开发工作流

每当被分配一个 Phase 内的具体任务时：

```
Step 0: 确认环境
  → conda activate reqradar
  → python --version（确认 ≥ 3.12）
  → pip install -e reqradar/kernel（确保内核包最新）

Step 1: 文档准备
  → 查 docs/README.md 的"按 Phase 查阅"表格
  → 收集该 Phase 的全部设计文档
  → 对照阅读 C-01 对应模板（Pydantic / FastAPI / SQLAlchemy）

Step 2: 确定文件归属
  → 查 C-02 第 9.1 节"新增模块放置决策树"
  → 如果新增文件，走 Q1→Q7 决策树确定放哪个目录
  → 如果修改文件，确认不违反依赖铁律

Step 3: 编写代码
  → 按对应 R/M 系列设计文档的伪代码/Schema 实现
  → 按 C-01 模板写 Pydantic/FastAPI/SQLAlchemy 模型
  → 如果新增 API：在 C-04 找到对应端点格式，复制 Schema 写实现
  → 如果新增配置项：按 C-03 第 7 节注册流程新增

Step 4: 数据库变更
  → 如果新增表：按 C-06 命名规则创建 Alembic 迁移脚本
  → 确保 upgrade() 和 downgrade() 都实现
  → 按 C-06 第 9.4 节 Checklist 自查

Step 5: 注册与同步
  → 新增 API → 更新 C-04 端点表 + 补充请求/响应 Schema
  → 新增配置 → 更新 C-03 配置项表 + config.yaml Schema + 环境变量映射
  → 新增表 → 更新 C-06 表清单
  → 新增文档引用 → 更新 README.md 相关表格

Step 6: 编写测试
  → 按 C-05 命名规则：test_{功能}_{场景}_{预期}.py
  → 按 C-05 模板写单元测试 / API 集成测试
  → 走 C-05 第 13 节 9 项边界覆盖
  → 按 C-05 规则 mock 外部依赖

Step 7: 自检
  → conda activate reqradar && ruff check reqradar/ tests/ && ruff format --check reqradar/ tests/ && mypy reqradar/kernel/
  → C-01 第 14 节 禁止事项清单（23 条）
  → C-02 第 6 节 禁止依赖清单（14 条）
  → S-01 第 11 节 安全检查清单（9 项）
  → docs/README.md "Agent 编码后自检"（8 项）
  → 全部通过 → 提交
```

## 4. 常用命令

```bash
# === 环境 ===
conda activate reqradar                # 激活 conda 环境（每次新终端必做）
pip install -e reqradar/kernel          # 安装/更新内核包

# === 代码质量 ===
ruff check reqradar/ tests/            # lint（P0-P1 阶段限定目录）
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

# === 部署（P2+） ===
docker compose up -d                   # 启动全部服务
docker compose exec api-service alembic upgrade head  # 迁移

# === 依赖合规检查 ===
python scripts/check_dependencies.py   # C-02 依赖铁律验证
```

## 5. 关键文件速查（V2）

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | 根项目配置（uv workspace + ruff + mypy + pytest） |
| `.env.example` | 环境变量模板（复制为 `.env` 使用） |
| `reqradar/kernel/` | 共享类型/枚举/异常/ORM/配置基类（唯一定义源） |
| `reqradar/kernel/types.py` | ContextKind, Scope, Domain, TokenBudget 等类型 |
| `reqradar/kernel/enums.py` | SessionStatus(11态), EventType(23种), EvidenceType(10种) 等枚举 |
| `reqradar/kernel/exceptions.py` | 15 个异常类，全部支持 cause 链 |
| `reqradar/kernel/database.py` | SQLAlchemy Base + 异步引擎工厂 |
| `reqradar/kernel/models.py` | 25 张 ORM 模型（P0 已创建，P1 扩展 L0/L1 表） |
| `reqradar/kernel/config_base.py` | Scope×Domain 配置基类 + 三级解析链 |
| `reqradar/web/api/v2/` | V2 新版 API 路由（`/api/v2/...`，P1 开始创建） |
| `tests/unit/kernel/` | Kernel 单元测试 |
| `scripts/check_dependencies.py` | 依赖合规检查脚本 |
| `docs/README.md` | 文档导航总索引 |
| `docs/adr/` | 16 条架构决策记录 |
| `docs/detailed/C-01_CODING_CONVENTIONS.md` | 编码规范完整版（正例/反例/模板） |
| `docs/detailed/C-02_MODULE_DEPENDENCY_MAP.md` | 目录精确清单 + 依赖矩阵 + 禁止清单 |
| `docs/detailed/C-04_API_CONTRACT_REGISTRY.md` | 全部外部 API 端点 Schema |
| `docs/detailed/C-05_TEST_SPECIFICATION.md` | 测试命名/mock/边界覆盖 |
| `docs/detailed/C-06_DATABASE_MIGRATION_PLAN.md` | 33 张表 DDL + 批次顺序 |
| `docs/detailed/I-01_SERVICE_API_CONTRACT.md` | 服务间内部 API 契约 |

## 6. Git 提交规范

- **分支**: `refactor/v2`（主分支）← `refactor/v2-p{N}`（Phase 分支）
- **提交格式**: `<type>(<scope>): <short description>`
  - type: `feat` / `fix` / `refactor` / `docs` / `chore` / `style` / `test` / `ci` / `perf`
  - scope: 影响模块名，如 `feat(kernel): add session state machine`
- **语言**: 英文
- **PR**: 合并到 `refactor/v2`，所有 Phase 完成后合入 `develop`

## 7. 重要提醒

- **V2 不兼容 V1**——API 路径全新（`/api/v2/`），数据库全新 Schema，前端全新设计（P8）
- **遇到"为什么要这样设计"**→ 查 `docs/adr/` 目录找到对应 ADR
- **不确定文件放哪** → 走 C-02 第 9.1 节决策树
- **不确定命名格式** → 查 C-01 第 6 节完整命名表
- **不确定测试怎么写** → 查 C-05 第 8/9 节模板
- **不确定依赖是否合规** → 运行 `python scripts/check_dependencies.py`
