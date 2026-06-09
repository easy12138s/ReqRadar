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

## 一、文档说明

本计划面向**编码 Agent**。每项任务含：目标 / 任务清单 / 验收标准 / 必读参考 / 涉及文件 / 注意事项。

**前置必读**（按顺序读完再动手）：

1. [AGENTS.md §0.5 环境准备](../../../AGENTS.md)
2. [AGENTS.md §3 Phase 开发工作流](../../../AGENTS.md)
3. [C-01 编码规范](C-01_CODING_CONVENTIONS.md)（Pydantic / FastAPI / SQLAlchemy 模板）
4. [C-02 模块依赖地图 §9.1 决策树](C-02_MODULE_DEPENDENCY_MAP.md)（新增文件放哪）
5. [C-05 测试规范 §3 §6 §13](C-05_TEST_SPECIFICATION.md)（测试目录 / Fixture / 9 项边界）
6. [C-06 数据库迁移计划](C-06_DATABASE_MIGRATION_PLAN.md)（Alembic 迁移命名）
7. [C-04 API 契约注册表](C-04_API_CONTRACT_REGISTRY.md)（端点 schema）
8. [C-03 配置注册表](C-03_CONFIGURATION_REGISTRY.md)（配置项 schema）
9. [CHECKLIST.md](../CHECKLIST.md)（P0-P9 验收基线）
10. [MVP-02 验收清单](MVP-02_MVP_VERIFICATION_CHECKLIST.md)（每项任务的验证步骤）

**核心约束**（违反任一 = 代码不可合入）：

- 绝对导入，禁止 `from ..`
- `str | None` / `list[str]`，禁 `Optional` / `List`
- 异常必须带 `cause` 链（用 `raise X from y`）
- 端点用 `request.app.state.config`，禁模块级 `load_config()`
- 9 项测试边界：成功/401/403/404/422/409/空列表/外部失败/路径遍历
- mock 必做：LLM / 网络 / Git / MinIO / Redis
- 每个测试用独立 SQLite + `tmp_path`

**当前项目状态**（基线）：
- 12 容器微服务架构（`docker-compose.yml`，含 Traefik + PG + Redis + ChromaDB + 7 个业务服务 + Frontend）
- 核心推理链已通（Runner + ReAct + **11 工具** + LiteLLMClient）
- 已知 MVP 痛点：内存 TaskStore / 内存 Session / asyncio.run 嵌套 / 无监控
- 认证方式：BFF 层通过 Header 注入 JWT，**无 `/api/v2/auth/login` 路由**（认证由 auth-service 独立处理）

---

## 一.5、Day 0 准备（启动 MVP 任务前的强制前置）

> **本节是 8 项任务的前置门槛**，不完成不能开始 Day 1。

### 1.5.1 测试目录补建

按 C-05 §3 测试目录结构，**当前 `tests/` 缺少 `integration/` 和 `e2e/` 子目录**，需在 Day 0 补建：

```
tests/
├── conftest.py              # 已有
├── unit/                    # 已有
├── integration/             # 【新建】 集成测试
│   ├── __init__.py
│   ├── conftest.py          # 集成测试 fixture
│   ├── api/                 # API 端点集成测试
│   ├── services/            # Service 层集成测试
│   └── tools/               # 工具真调测试（MVP-8 用）
└── e2e/                     # 【新建】 端到端测试
    ├── __init__.py
    ├── conftest.py          # E2E fixture：mock LLM + 独立 DB
    └── test_mvp1_smoke.py   # Day 1 真跑脚本（MVP-1.5 产出）
```

| # | 子任务 | 产出 | 估时 |
|---|--------|------|------|
| 0.1 | `tests/integration/__init__.py` + `conftest.py`（集成测试 fixture） | 目录结构 | 0.5h |
| 0.2 | `tests/e2e/__init__.py` + `conftest.py`（E2E fixture：mock LLM） | 目录结构 | 0.5h |
| 0.3 | 检查 `pytest.ini` / `pyproject.toml` 的 `asyncio_mode = "auto"` 配置 | 配置确认 | 0.5h |
| 0.4 | `pytest --collect-only` 验证两个新目录可被 pytest 发现 | 收集成功 | 0.5h |

### 1.5.2 通用 Fixture 准备

按 C-05 §6.2 Fixture 表，**当前 `tests/conftest.py` 缺少以下 mock fixture**，需在 Day 0 注册：

| Fixture | 用途 | 存放位置 | Day 0 必做 |
|---------|------|---------|-----------|
| `mock_llm_client` | mock LLM 客户端（含 complete / complete_with_tools） | `tests/conftest.py` | ✅ |
| `mock_redis` | mock Redis Streams/PubSub | `tests/conftest.py` | ✅ |
| `mock_minio` | mock MinIO 客户端 | `tests/conftest.py` | ✅ |
| E2E 版 `mock_llm_client` | E2E 专用 mock LLM | `tests/e2e/conftest.py` | ✅ |

> **关于 boto3 mock**：MVP-7 用 `mocker.patch("boto3.client")` 临时 mock 即可，**不**注册为 fixture。

**校验命令**：`pytest -k "mock_llm or mock_redis or mock_minio" --co` 能看到 fixture 列表。

### 1.5.3 文档基线确认

- [ ] `docs/CHECKLIST.md` 反映 P0-P9 最新验收状态
- [ ] 当前分支 `refactor/v2` 工作区干净
- [ ] `.env` 文件已配置真实 LLM API Key

### 1.5.4 Day 0 验收

```
[ ] tests/integration/ 和 tests/e2e/ 目录已创建，__init__.py 齐全
[ ] 4 个 mock fixture 已在 conftest.py 注册
[ ] pytest --collect-only 能发现两个新目录
[ ] 4 个 mock fixture 能在测试中正确获取（`pytest --fixtures tests/` 列出 mock_llm_client / mock_redis / mock_minio / e2e_mock_llm_client）
[ ] ruff check tests/ 无 lint 错误
[ ] 当前工作区 git status 干净
```

**Day 0 估时**：3 小时

---

## 二、任务总览

| 编号 | 任务 | 优先级 | 估时 | 状态 |
|------|------|--------|------|------|
| **MVP-1** | 端到端真跑一次（docker compose up + cool-agent）发现真 bug | 🔴 P0 | 3-4 天 | ⬜ 未做 |
| **MVP-2** | TaskStore 落 PG（含 `_session_tasks` 字典迁移） | 🔴 P0 | 1 天 | ⬜ 未做 |
| **MVP-3** | Session 状态机从 PG 恢复（基于现有 checkpoint 扩展） | 🔴 P0 | 1.5 天 | ⬜ 未做 |
| **MVP-4** | Container 模型去嵌套（删除 `analysis_agent.py` 的 ThreadPoolExecutor workaround） | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **MVP-5** | 前端抽核心组件（基于 antd 6 二次封装 AppButton/AppTable/AppLoading） | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **MVP-6** | 结构化日志 + /health 深健康（扩展现有 `infrastructure/logging.py`） | 🟡 P1 | 0.5 天 | ⬜ 未做 |
| **MVP-7** | MinIO 接入 L0 原始文件 | 🟢 P2 可选 | 0.5 天 | ⬜ 推后 |
| **MVP-8** | 11 工具真调验证 + L3Writer PG 注入验证 + Graph 端点真验 | 🟡 P1 | 1 天 | ⬜ 未做 |
| **合计** | | | **8.5 天** | |

> **预估收益**：执行后综合分从 55 提升到 80（+25 分）。
>
> **MVP-7 说明**：MinIO 推到第二轮，当前本地文件存储能满足 MVP 单人演示需求。

---

## 三、任务详细设计

---

### MVP-1：端到端真跑一次（高优先级，最高 ROI）

**目标**：用真实环境跑通"创建项目 → 上传 → 摄取 → 启动 Session → 拿到报告"全链路，发现并记录真 bug。这是后续 7 项任务的输入。

**依赖**：无（Day 0 完成即可开始）

**涉及文件**：
- `tests/e2e/test_mvp1_smoke.py`（新建，E2E 测试）
- `tests/e2e/conftest.py`（如 Day 0 未建，补建）
- `docs/MVP-1_BUG_LOG.md`（新建，Bug 登记）

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-1.1 | 准备 `.env` | 复制 `.env.example` 为 `.env`，填入真实 `LLM_API_KEY`（`grep -i 'llm_api_key' .env.example` 查键名） | 0.5h |
| MVP-1.2 | 启动容器 | `docker compose up -d`，等 30 秒，`docker compose ps` 全部 `healthy` | 0.5h |
| MVP-1.3 | 应用迁移 | `docker compose exec api-service alembic upgrade head`，确认输出 `Running upgrade -> head, ...` | 0.5h |
| MVP-1.4 | 准备测试项目 | 准备 3 个：① `D:\EasyFiles\private\project\cool-agent` ② 任一开源小项目 ③ 1 个 zip 压缩包；每项目附 1 份 markdown 需求文档 | 1h |
| MVP-1.5 | 写 E2E 脚本 | 在 `tests/e2e/test_mvp1_smoke.py` 实现 `test_mvp1_full_flow()`，9 步调用见下方"必读 API" | 2h |
| MVP-1.6 | 跑 3 轮 × 3 类 | 改参数循环执行；失败步骤记录到 `docs/MVP-1_BUG_LOG.md` | 2h |
| MVP-1.7 | 修 P0 bug | 阻塞主链路的 bug 必须修；非阻塞可记到遗留问题。**估时 2-3 天**（CHECKLIST 有 7 个 Phase 待复核，可能发现 10+ bug） | 2-3 天 |
| MVP-1.8 | 复测 | 重新跑脚本 3 轮全成功，更新 BUG_LOG 状态 | 1h |

**必读 API**（9 步调用）：

> **认证说明**：BFF 无 `/api/v2/auth/login` 路由。E2E 脚本需先调用 auth-service 的 `/internal/v2/auth/issue` 获取 JWT，后续请求携带 `Authorization: Bearer <token>` Header。

```
1. POST http://localhost:8001/internal/v2/auth/issue  → 获取 JWT（auth-service 直连）
2. POST /api/v2/projects              → 创建项目（source_type: git|local|zip）
3. POST /api/v2/projects/{id}/upload  → 上传需求文档
4. POST /api/v2/projects/{id}/ingest  → 触发摄取
5. GET  /api/v2/projects/{id}         → 验证 indexed_at 不为空
6. POST /api/v2/sessions              → 创建 Session
7. POST /api/v2/sessions/{id}/start   → 启动推理
8. GET  /api/v2/sessions/{id}/events  → 轮询直到 status=COMPLETED
9. GET  /api/v2/sessions/{id}/report  → 验证报告有 ≥ 3 风险点 + ≥ 5 证据
```

**验收标准**（对照 MVP-02 §MVP-1）：
- [ ] 脚本可 `pytest tests/e2e/test_mvp1_smoke.py -v` 运行
- [ ] 3 轮 × 3 类 = 9 次全部 PASS
- [ ] 0 次 5xx 错误
- [ ] BUG_LOG.md 记录所有发现 → 修复 → 复测
- [ ] `ruff check tests/e2e/` 无 lint 错误

**E2E 脚本模板要点**（参考 C-05 §10 异步测试模板）：
- 用 `httpx.AsyncClient` 调 HTTP 接口
- 用 `conftest.py` 的 `e2e_session` / `e2e_project` / `e2e_token` fixture
- LLM 调用**用真 API**（这是 E2E，**不 mock LLM**）
- 每步加 `assert response.status_code in (200, 201)`
- 报告验证：`assert len(data["risks"]) >= 3 and len(data["evidence"]) >= 5`

**风险与应对**：

| 风险 | 概率 | 应对 |
|------|------|------|
| LLM API 不稳定 | 高 | 在脚本里加 3 次重试 + 失败统计 |
| markitdown 首次下载模型失败 | 中 | 复用 `docker-model-cache/`（已加 .gitignore），预热 |
| 容器端口冲突 | 低 | 参照 `docker-compose.yml` 端口分配段 |

**回滚策略**：本任务无破坏性改动，仅新增 `tests/e2e/` 和 `docs/MVP-1_BUG_LOG.md`，git revert 即可。

---

### MVP-2：TaskStore 落 PG（高优先级）

**目标**：`services/output/app.py` 的 `_tasks` 和 `_session_tasks` 两个内存字典（行号先 `grep -n '_tasks\|_session_tasks' services/output/app.py` 确认）改为 PG 表，重启后 task_id 和 session→task 映射仍可查。

**依赖**：MVP-1

**涉及文件**：
- `alembic/versions/V2_MVP-2_create_output_tasks.py`（新建，Alembic 迁移）
- `reqradar/output_svc/store.py`（新建，OutputTaskStore 类）
- `services/output/app.py`（修改，替换 `_tasks` + `_session_tasks` 引用）
- `reqradar/kernel/models.py`（新增 `OutputTask` ORM 模型）
- `tests/unit/output_svc/test_store.py`（新建，单测）
- `docs/CHECKLIST.md`（更新 MVP-2 验收记录）

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-2.1 | 设计 `output_tasks` 表 | 字段：`id (UUID PK)` / `session_id (UUID, 索引)` / `status (str)` / `request (JSONB)` / `result (JSONB nullable)` / `error (text nullable)` / `created_at (timestamptz)` / `updated_at (timestamptz)`；`status` 和 `session_id` 上加 B-tree 索引。**注意**：`session_id` 字段用于替代 `_session_tasks` 字典的 session→task 映射功能 | 1h |
| MVP-2.2 | 写 Alembic 迁移 | `alembic revision -m "V2_MVP-2_create_output_tasks"`；**`upgrade()` 和 `downgrade()` 都必须实现**（参考 C-06 §9.4 Checklist） | 1h |
| MVP-2.3 | 新增 ORM 模型 | 在 `reqradar/kernel/models.py` 加 `OutputTask` 类（参考同文件中 `Event` 模型结构） | 1h |
| MVP-2.4 | 实现 `OutputTaskStore` | 文件 `reqradar/output_svc/store.py`，类方法：`async create(request, session_id) -> str` / `async get(task_id) -> OutputTask \| None` / `async update(task_id, **fields)` / `async list_by_session(session_id) -> list[OutputTask]`；参考 `reqradar/index_svc/knowledge/writer.py` 的异步 SQLAlchemy 写法 | 2h |
| MVP-2.5 | 替换 `services/output/app.py` | 找到所有 `self._tasks[...]` 和 `self._session_tasks[...]`，改为 `await self._store.get(...)` / `await self._store.list_by_session(...)`；**保留属性名 `_store` 不变**，减少端点代码改动 | 1h |
| MVP-2.6 | 注册 store | 在 `app.py` 的 lifespan 里 `app.state.task_store = OutputTaskStore(session_factory)` | 0.5h |
| MVP-2.7 | 写单测 | 9 项边界：成功创建/成功查询/404（不存在 task）/409（重复 ID）/422（非法字段）/空列表查询/session_id 查询/状态机非法转换/DB 故障降级 | 1h |
| MVP-2.8 | 自检 | `ruff check reqradar/output_svc/ services/output/ tests/unit/output_svc/ && pytest tests/unit/output_svc/ -v` | 0.5h |

**关键代码定位指令**（Agent 拿到后直接执行）：

```bash
# 1. 定位 _tasks
grep -n "_tasks" services/output/app.py
# 2. 看现有 ORM 风格
grep -n "class.*Base\b" reqradar/kernel/models.py
# 3. 看现有 async SQLAlchemy 写法
grep -n "async def" reqradar/index_svc/knowledge/writer.py | head -5
# 4. 看 alembic 历史命名
ls alembic/versions/ | tail -3
```

**验收标准**（对照 MVP-02 §MVP-2）：
- [ ] `alembic upgrade head` + `alembic downgrade -1` 双向 OK
- [ ] `pytest tests/unit/output_svc/ --cov=reqradar/output_svc/store --cov-report=term-missing` 覆盖率 ≥ 80%
- [ ] 9 项边界全部通过
- [ ] 真跑验证：创建 task → `docker compose restart output-service` → 旧 task_id 仍可查

**回滚策略**：
- 迁移脚本 `downgrade()` 一键回滚
- 设置环境变量 `FEATURE_OUTPUT_PERSIST=false` 时降级为内存版（保留旧代码路径）

---

### MVP-3：Session 状态机从 PG 恢复（高优先级）

**目标**：`reqradar/cognitive_rt/runtime/session.py` 的 `_sessions` 内存字典支持从 PG 恢复，container 重启后历史 Session 仍可查、可续推。

**依赖**：MVP-1

**涉及文件**：
- `alembic/versions/V2_MVP-3_create_session_snapshots.py`（新建）
- `reqradar/cognitive_rt/runtime/session_repo.py`（新建，SessionStateRepo 类）
- `reqradar/cognitive_rt/runtime/session_api.py`（修改，`SessionService` 类的 `_sessions` 字典，L67）
- `reqradar/kernel/models.py`（新增 SessionSnapshot ORM）
- `reqradar/cognitive_rt/runtime/server.py`（lifespan 启动时调用 load，L31-50）
- `tests/unit/cognitive_rt/runtime/test_session_repo.py`（新建单测）
- `tests/integration/cognitive_rt/test_session_recovery.py`（新建集成测，验证 kill -9 恢复）
- `docs/CHECKLIST.md`

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-3.1 | 设计 `session_snapshots` 表 | 字段：`session_id (UUID PK)` / `status (str, 索引)` / `state_data (JSONB)` / `checkpoint_version (int)` / `last_event_id (UUID nullable)` / `created_at` / `updated_at` | 1h |
| MVP-3.2 | 写 Alembic 迁移 | `alembic revision -m "V2_MVP-3_create_session_snapshots"`；**upgrade() + downgrade() 都实现**；`status` 字段加 B-tree 索引便于 `WHERE status IN ('CREATED','READY','RUNNING')` 查询 | 1h |
| MVP-3.3 | 新增 ORM 模型 | `class SessionSnapshot(Base)` 在 `reqradar/kernel/models.py` | 0.5h |
| MVP-3.4 | 实现 `SessionStateRepo` | 文件 `reqradar/cognitive_rt/runtime/session_repo.py`；方法：`async save(session)` / `async load(session_id) -> SessionSnapshot \| None` / `async list_active() -> list[SessionSnapshot]` / `async delete(session_id)`；**所有方法包 try/except，DB 故障时返回 None 或抛 StorageUnavailableError，由调用方降级** | 2h |
| MVP-3.5 | 修改 `SessionService` | 在 `session_api.py` 的 `SessionService` 类中：① 状态转换方法内追加 `await self._repo.save(self.to_dict())`，但**用 `asyncio.shield()` 包装，确保失败不阻塞状态变更**；② 加 `async restore(snapshot)` 方法，从 `SessionSnapshot.state_data` 重建 `SessionStateMachine` 对象 | 2h |
| MVP-3.6 | lifespan 接入 load | 在 `server.py` 的 `lifespan` 函数（L31）里：`active = await session_repo.list_active()` → 对每个 session 调用 `SessionService.restore(snapshot)` 重建 → 放入 `SessionService._sessions` 字典 | 1h |
| MVP-3.7 | 单测 | 9 项边界 + 持久化失败降级路径 + JSON 序列化反序列化正确性 | 2h |
| MVP-3.8 | 集成测 | 在 `tests/integration/cognitive_rt/test_session_recovery.py` 写 `test_session_survives_restart()`：① 启动 cognitive-rt ② 创建 Session ③ 推进到 RUNNING ④ `docker compose kill cognitive-rt` ⑤ `docker compose up -d cognitive-rt` ⑥ 验证 `GET /api/v2/sessions/{id}` 仍可查到且状态正确 | 1h |
| MVP-3.9 | 自检 | `ruff check reqradar/cognitive_rt/ tests/ && pytest tests/unit/cognitive_rt/runtime/ tests/integration/cognitive_rt/ -v` | 0.5h |

**降级策略**（重要）：

```python
# 在 transition() 内
try:
    await asyncio.shield(self._repo.save(self.to_dict()))
except StorageUnavailableError as e:
    logger.warning("session_persist_failed", session_id=self.id, error=str(e))
    # 不重新抛出，不阻塞状态变更
```

**验收标准**（对照 MVP-02 §MVP-3）：
- [ ] `alembic upgrade head` + `downgrade -1` 双向 OK
- [ ] cognitive-rt 重启后，CREATED/READY/RUNNING 状态 Session 全部恢复（log: "Loaded N active sessions"）
- [ ] 持久化失败时**状态转换仍成功**（仅记 warn 日志）
- [ ] 单测覆盖率 ≥ 80%
- [ ] 集成测 `test_session_survives_restart` 通过
- [ ] 9 项边界 + 异常路径测试

**回滚策略**：
- 迁移脚本 `downgrade()` 一键回滚
- `FEATURE_SESSION_PERSIST=false` 时**关闭 load 逻辑**（仅保留 save，降级为写日志不读写）

---

### MVP-4：Container 模型去嵌套（中优先级）

**目标**：`reqradar/cognitive_rt/cognition/context_pipeline.py` 的 `pipeline.execute` 在 agent 内被 `asyncio.run` 嵌套调用的事件循环反模式重构。

**依赖**：MVP-1

**涉及文件**：
- `reqradar/cognitive_rt/cognition/analysis_agent.py`（**主改**，L176-201 的 `asyncio.run` + `ThreadPoolExecutor` workaround）
- `reqradar/cognitive_rt/cognition/context_pipeline.py`（辅改，加 `execute_async` 纯异步接口）
- `tests/unit/cognitive_rt/cognition/test_context_pipeline.py`（修改，新增 async 测试）
- `docs/CHECKLIST.md`

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-4.1 | 定位所有反模式 | `grep -rn "asyncio.run\|ThreadPoolExecutor" reqradar/cognitive_rt/`，把找到的所有行号记录到 `docs/MVP-4_NESTED_LOOP_LOG.md`。**已知位置**：`analysis_agent.py:176-201`（用 `ThreadPoolExecutor` 包装 `asyncio.run`） | 0.5h |
| MVP-4.2 | 设计双接口 | `pipeline.execute_sync()` 保持原签名不变（同步 wrapper，内部用 `asyncio.run` 仅在确认无事件循环时调用）；新加 `pipeline.execute_async()`（纯 async） | 1h |
| MVP-4.3 | 修改 `analysis_agent.py` | **删除 L176-201 的 ThreadPoolExecutor workaround**，改为：`result = await pipeline.execute_async(...)`。因为 `analysis_agent` 的 `_build_context()` 方法本身就在 async 上下文中被调用（由 `runner.py` 的 `run_react_analysis` 调用），所以直接用 `await` 即可 | 1h |
| MVP-4.4 | 单测补全 | 在 `test_context_pipeline.py` 加 `async def test_pipeline_execute_async_in_running_loop()`，验证在已运行 loop 中调用不抛 `RuntimeError: This event loop is already running` | 1h |
| MVP-4.5 | 真跑验证 | 跑 `tests/e2e/test_mvp1_smoke.py` 10 轮；统计成功率（必须 100%）+ 平均延迟 | 1h |
| MVP-4.6 | 自检 | `grep -rn "asyncio.run\|ThreadPoolExecutor" reqradar/cognitive_rt/ 2>&1` 输出必须为空（除 `execute_sync` 内部保留的 1 处外） | 0.5h |

**关键代码定位**：

```bash
# 已知 asyncio.run 嵌套位置
grep -n "asyncio.run\|ThreadPoolExecutor" reqradar/cognitive_rt/cognition/analysis_agent.py
# pipeline.execute 定义
grep -n "def execute" reqradar/cognitive_rt/cognition/context_pipeline.py
# 确认 _build_context 的调用链
grep -n "_build_context" reqradar/cognitive_rt/cognition/analysis_agent.py
```

**双接口实现模板**：

```python
# context_pipeline.py
class ContextPipeline:
    async def execute_async(self, inputs) -> ContextBundle:
        """纯异步版本，供已在事件循环中调用的场景使用。"""
        return await self._execute_core(inputs)

    def execute_sync(self, inputs) -> ContextBundle:
        """同步版本，仅用于无事件循环的脚本场景。"""
        try:
            asyncio.get_running_loop()
            has_loop = True
        except RuntimeError:
            has_loop = False
        if has_loop:
            raise RuntimeError(
                "execute_sync called inside running event loop, "
                "use execute_async instead"
            )
        return asyncio.run(self._execute_core(inputs))
```

**验收标准**（对照 MVP-02 §MVP-4）：
- [ ] `grep -rn "asyncio.run" reqradar/ services/` 输出 = 0
- [ ] `tests/unit/cognitive_rt/cognition/test_context_pipeline.py` 全过
- [ ] `tests/e2e/test_mvp1_smoke.py` 10 轮成功率 = 100%
- [ ] context assembly 平均延迟 ≤ 2s

**回滚策略**：`FEATURE_PIPELINE_SYNC_FALLBACK=true` 时保留旧 `execute()` 路径，新 `execute_async` 不启用。

---

### MVP-5：前端抽核心组件（中优先级）

**目标**：`frontend/src/components/` 增加 `AppButton` / `AppTable` / `AppLoading` 三个二次封装组件，基于现有 antd 6 组件库，重构 8 页面统一使用。

**依赖**：MVP-1

**涉及文件**：
- `frontend/src/components/AppButton.tsx`（新建，基于 antd `Button` 二次封装）
- `frontend/src/components/AppTable.tsx`（新建，基于 antd `Table` 二次封装）
- `frontend/src/components/AppLoading.tsx`（新建，基于 antd `Spin` + `Skeleton` 二次封装）
- `frontend/src/components/index.ts`（新建，统一导出）
- `frontend/src/pages/*.tsx`（8 个页面，修改）

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-5.1 | 设计 AppButton 组件 | 基于 antd `Button` 封装，TS props：`variant: 'primary' \| 'secondary' \| 'ghost'` / `size: 'sm' \| 'md' \| 'lg'` / `loading: boolean` / `disabled: boolean` / `onClick` / `children`；内部映射到 antd 的 `type` + `size` 属性 | 0.5h |
| MVP-5.2 | 设计 AppTable 组件 | 基于 antd `Table` 封装，TS props：`columns` / `dataSource` / `loading` / `emptyText` / `rowKey`；统一空态和 loading 样式 | 0.5h |
| MVP-5.3 | 设计 AppLoading 组件 | 基于 antd `Spin` + `Skeleton` 封装，两种变体：`<AppLoading.Spinner />`（小区域）+ `<AppLoading.Skeleton rows={3} />`（列表骨架屏） | 0.5h |
| MVP-5.4 | 重构 8 页面 | 替换所有直接使用 antd 组件为二次封装组件；用 `grep -rn "from 'antd'" frontend/src/pages` 验证减少程度 | 1h |
| MVP-5.5 | type-check + build | `cd frontend && npm run type-check && npm run build`；build 产物能产出到 `dist/` | 0.5h |

**关键代码定位指令**：

```bash
# 找所有直接使用 antd 的地方
grep -rn "from 'antd'" frontend/src/pages | wc -l
# 看现有 page 结构
ls frontend/src/pages/
# 看现有 antd 用法
grep -rn "import.*Button\|import.*Table\|import.*Spin" frontend/src/pages
```

**AppButton 组件实现模板**（基于 antd 二次封装）：

```tsx
// frontend/src/components/AppButton.tsx
import React from 'react';
import { Button, ButtonProps } from 'antd';

interface AppButtonProps extends Omit<ButtonProps, 'type' | 'size'> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
}

const variantMap = {
  primary: 'primary',
  secondary: 'default',
  ghost: 'text',
} as const;

const sizeMap = {
  sm: 'small',
  md: 'middle',
  lg: 'large',
} as const;

export const AppButton: React.FC<AppButtonProps> = ({
  variant = 'primary',
  size = 'md',
  ...props
}) => {
  return (
    <Button
      type={variantMap[variant]}
      size={sizeMap[size]}
      {...props}
    />
  );
};
```

**验收标准**（对照 MVP-02 §MVP-5）：
- [ ] `npm run type-check` 0 错误
- [ ] `npm run build` 成功
- [ ] `grep -rn "<button" frontend/src/pages` 输出 ≤ 2
- [ ] `grep -rn "<table" frontend/src/pages` 输出 ≤ 2
- [ ] 8 页面在浏览器无 console 错误

**回滚策略**：每个组件独立 PR，git revert 单 commit 即可。

---

### MVP-6：结构化日志 + /health 深健康（中优先级）

**目标**：日志改为 JSON 格式携带 `session_id` / `request_id`；`/health` 改为深健康（检查 PG / Chroma / Redis 真实可用性）。

**依赖**：MVP-1

**涉及文件**：
- `reqradar/infrastructure/logging.py`（**扩展现有文件**，当前只有 contextvars 辅助函数，需新增 `JSONFormatter` 类和 `setup_json_logging()` 函数）
- `reqradar/infrastructure/health.py`（新建，深健康检查）
- `services/{api,auth,cognitive-rt,index,output,ingestion,integration}/app.py`（7 个服务，修改）
- `tests/unit/infrastructure/test_logging.py`（新建）
- `tests/unit/infrastructure/test_health.py`（新建）

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-6.1 | 实现 JSON formatter | **扩展** `reqradar/infrastructure/logging.py`（保留现有 `set_log_context` / `clear_log_context` / `get_session_id` 函数）；新增 `JSONFormatter` 类和 `setup_json_logging()` 函数；输出字段：`timestamp` / `level` / `msg` / `session_id` / `request_id` / `module` / `extra` | 1h |
| MVP-6.2 | 替换 7 个服务的 logging 配置 | 找 `logging.basicConfig` 全部替换为 `setup_json_logging()`；**保留原有 logger 名称不变**；**注意**：每个服务的入口文件不同（api→app.py, cognitive-rt→server.py, index→app.py 等） | 1h |
| MVP-6.3 | 实现深健康检查 | 文件 `reqradar/infrastructure/health.py`；函数 `async def check_dependencies() -> dict` 包含 `pg` / `redis` / `chroma` 三个键；PG 用 `SELECT 1`，Redis 用 `PING`，Chroma 用 `heartbeat()` | 1h |
| MVP-6.4 | 替换 7 个服务的 /health 端点 | 把每个服务 `/health` 端点改为 `await check_dependencies()`；任一依赖失败返回 503 + JSON 错误 | 1h |
| MVP-6.5 | 单测 | `test_logging.py` 验证 JSON 输出可被 `json.loads` 解析；`test_health.py` mock PG/Redis/Chroma 验证 3 种场景 | 0.5h |
| MVP-6.6 | 真跑验证 | `curl http://localhost:8000/health` 返回 200 + JSON；`docker compose stop postgres` 后返回 503 | 0.5h |

**关键代码定位指令**：

```bash
grep -rn "logging.basicConfig" services/ reqradar/
grep -rn "/health" services/
```

**JSON formatter 实现模板**：

```python
# reqradar/infrastructure/logging.py
import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON 日志格式器，输出可被 jq 解析。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "module": record.module,
            "session_id": getattr(record, "session_id", None),
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_json_logging(level: str = "INFO") -> None:
    """统一替换 root logger 的 formatter。"""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
```

**验收标准**（对照 MVP-02 §MVP-6）：
- [ ] `docker compose logs api-service | head -1 | jq .` 合法 JSON
- [ ] `/health` 返回 200 时所有依赖可用
- [ ] `docker compose stop postgres` 后 `/health` 返回 503
- [ ] 7 个服务全部接入

**回滚策略**：保留旧 `logging.basicConfig` 路径为 `FEATURE_JSON_LOG=false` 时的 fallback。

---

### MVP-7：MinIO 接入 L0 原始文件（中优先级）

**目标**：`docker-compose.yml` 增加 minio service，ingestion-service 的 L0 写入改用 MinIO（替代本地路径）。

**依赖**：MVP-1

**涉及文件**：
- `docker-compose.yml`（修改，新增 minio + createbucket 服务）
- `services/ingestion/requirements.txt`（加 boto3）
- `reqradar/ingestion/storage/__init__.py`（新建）
- `reqradar/ingestion/storage/s3_client.py`（新建，MinIO/S3 客户端封装）
- `reqradar/ingestion/storage/local_fallback.py`（新建，本地路径 fallback）
- `services/ingestion/app.py`（修改，L0 写入逻辑）
- `.env.example`（加 `L0_STORAGE_BACKEND` / `MINIO_*` 变量）
- `tests/unit/ingestion/test_s3_client.py`（新建）

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-7.1 | docker-compose.yml 加 minio | 新增 `minio` service（`minio/minio:latest`，端口 9000/9001）+ `createbucket` 一次性 init container（创建 `reqradar-l0` bucket） | 1h |
| MVP-7.2 | 加 boto3 依赖 | `services/ingestion/requirements.txt` 追加 `boto3==1.34.0`；`docker compose build ingestion-service` | 0.5h |
| MVP-7.3 | 实现 S3Client 封装 | 文件 `reqradar/ingestion/storage/s3_client.py`；类 `S3Client`，方法 `async def upload(key, bytes) -> str` / `async def download(key) -> bytes` / `async def exists(key) -> bool`；用 `aioboto3` 异步客户端 | 1.5h |
| MVP-7.4 | 实现 LocalFallback | 文件 `reqradar/ingestion/storage/local_fallback.py`；同样三个方法，落本地 `L0_STORAGE_PATH` | 0.5h |
| MVP-7.5 | 工厂方法 | 文件 `reqradar/ingestion/storage/__init__.py` 加 `def get_l0_storage() -> S3Client \| LocalFallback`；按 `L0_STORAGE_BACKEND` 环境变量切换 | 0.5h |
| MVP-7.6 | 替换 L0 写入 | `services/ingestion/app.py` 找到 L0 写入逻辑（`grep -n 'L0\|raw_context'`），改为 `await get_l0_storage().upload(key, content)` | 0.5h |
| MVP-7.7 | 配 .env.example | 加：`L0_STORAGE_BACKEND=minio` / `MINIO_ENDPOINT=minio:9000` / `MINIO_ACCESS_KEY=reqradar` / `MINIO_SECRET_KEY=reqradar-dev-secret` / `MINIO_BUCKET=reqradar-l0` | 0.5h |
| MVP-7.8 | 单测 | `test_s3_client.py`：3 场景：成功上传下载/连接失败降级/不存在 key 抛 404 | 1h |
| MVP-7.9 | 真跑验证 | `docker compose up -d`；`docker compose exec api-service python -c "import boto3; ..."` 上传 + 列对象 + 下载 | 0.5h |

**降级策略模板**：

```python
# reqradar/ingestion/storage/__init__.py
def get_l0_storage():
    backend = os.getenv("L0_STORAGE_BACKEND", "local")
    if backend == "minio":
        try:
            return S3Client(...)
        except Exception as e:
            logger.warning("minio_unavailable_fallback_local", error=str(e))
            return LocalFallback(...)
    return LocalFallback(...)
```

**验收标准**（对照 MVP-02 §MVP-7）：
- [ ] `docker compose up -d minio` 容器 healthy
- [ ] http://localhost:9001 控制台可登录
- [ ] 上传文档后 MinIO 中可见对象
- [ ] `docker compose stop minio` 后上传仍能成功（降级到本地）
- [ ] 9 项边界单测全过

**回滚策略**：`L0_STORAGE_BACKEND=local` 一键切回本地路径。

---

### MVP-8：11 工具 + L3Writer + Graph 端点真验（中优先级）

**目标**：对全部 11 个工具 + L3Writer + Graph 三端点（neighbors / path / subgraph）逐个真跑验证。

**工具清单**（11 个，位于 `reqradar/cognitive_rt/cognition/tools/`）：
- **核心 5 个**：`search_code` / `read_file` / `search_requirements` / `list_modules` / `get_project_profile`
- **扩展 6 个**：`get_dependencies` / `get_contributors` / `search_git_history` / `read_module_summary` / `get_terminology` / `security`

**依赖**：MVP-2、MVP-3（持久化层稳定后做真验才有意义）

**涉及文件**：
- `tests/integration/tools/test_tools_smoke.py`（新建）
- `tests/integration/index_svc/test_l3_writer.py`（新建）
- `tests/integration/index_svc/test_graph_endpoints.py`（新建）
- 各工具 / 端点的 bug 修复（如有）

**任务清单**：

| # | 子任务 | 具体操作 | 估时 |
|---|--------|---------|------|
| MVP-8.1 | 核心 5 工具真调测试 | 文件 `tests/integration/tools/test_tools_smoke.py`；5 工具 × 3 场景 = 15 用例；用 `httpx.AsyncClient` 调 cognitive-rt 内部 API | 1.5h |
| MVP-8.2 | 扩展 6 工具真调测试 | 同文件；6 工具 × 2 场景 = 12 用例（扩展工具只需验证成功路径 + 404） | 1h |
| MVP-8.3 | L3Writer 验证 | 文件 `tests/integration/index_svc/test_l3_writer.py`；7 种知识类型各 `test_create_X` + `test_query_X` = 14 用例 | 1h |
| MVP-8.4 | Graph 端点验证 | 文件 `tests/integration/index_svc/test_graph_endpoints.py`；3 端点 × 3 查询场景 = 9 用例 | 1h |
| MVP-8.5 | 修复发现的 bug | 把真跑发现的问题记录到 `docs/MVP-8_BUG_LOG.md`，阻塞主链路的必修 | 0.5h |
| MVP-8.6 | 自检 | `pytest tests/integration/ -v && ruff check tests/integration/` | 0.5h |

**关键代码定位指令**：

```bash
# 工具实现位置
grep -rn "search_code\|read_file\|search_requirements" reqradar/cognitive_rt/cognition/tools/
# L3Writer 实现
grep -n "class L3Writer" reqradar/index_svc/knowledge/writer.py
# Graph 端点
grep -n "graph_neighbors\|graph_path\|graph_subgraph" services/index/app.py
```

**工具真调测试模板**：

```python
# tests/integration/tools/test_tools_smoke.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_code_returns_results(client: AsyncClient, project_with_code):
    """成功：search_code 工具返回 ≥ 3 个代码片段。"""
    resp = await client.post(
        "/internal/v2/tools/invoke",
        json={"tool": "search_code", "params": {"query": "用户认证", "project_id": str(project_with_code.id), "top_k": 10}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) >= 3


@pytest.mark.asyncio
async def test_search_code_project_not_found_returns_404(client: AsyncClient):
    """边界：项目不存在返回 404。"""
    resp = await client.post(
        "/internal/v2/tools/invoke",
        json={"tool": "search_code", "params": {"query": "test", "project_id": "00000000-0000-0000-0000-000000000000"}},
    )
    assert resp.status_code == 404
```

**验收标准**（对照 MVP-02 §MVP-8）：
- [ ] 核心 5 工具 × 3 场景 = 15 用例全过
- [ ] 扩展 6 工具 × 2 场景 = 12 用例全过
- [ ] L3 7 种知识类型可写可查（14 用例全过）
- [ ] Graph 3 端点 × 3 场景 = 9 用例全过
- [ ] 真问题 100% 修复并有回归测
- [ ] BUG_LOG.md 记录所有发现

**回滚策略**：每个工具 / 端点的修复独立 commit，独立可回滚。

---

## 四、依赖关系图

```
MVP-1（端到端真跑）─────────┐
                            ├──→ MVP-2（TaskStore PG）  ──→ MVP-8（9 工具 + L3 + Graph）
                            ├──→ MVP-3（Session PG）    ──┘
                            ├──→ MVP-4（Container 去嵌套）
                            ├──→ MVP-5（前端抽组件）
                            ├──→ MVP-6（日志 + health）
                            └──→ MVP-7（MinIO）[可选]
```

**关键路径**：MVP-1 → MVP-2 / MVP-3 → MVP-8（共 5 天）
**并行任务**：MVP-4 / MVP-5 / MVP-6 全部依赖 MVP-1，可串行或 2 人并行（共 2 天）
**可选任务**：MVP-7（MinIO）推到第二轮，当前轮聚焦核心功能

---

## 五、执行计划（8 天冲刺）

```
Day 0 上午  §一.5 Day 0 准备：补 tests/integration + e2e 目录 + 4 个 mock fixture
Day 0 下午  §一.5.4 验收 Day 0 全过

Day 1  上午  MVP-1.1 ~ 1.5  准备环境 + 写 tests/e2e/test_mvp1_smoke.py
Day 1  下午  MVP-1.6        跑 3 轮 × 3 类，记录所有 bug

Day 2-3      MVP-1.7        修 P0 bug（CHECKLIST 有 7 个 Phase 待复核，预计 10+ bug）
Day 4  上午  MVP-1.8        复测全链路 ✅

Day 4  下午  MVP-2         TaskStore 落 PG（含 _session_tasks 迁移）
Day 5  上午  MVP-6         结构化日志 + 深健康
Day 5  下午  MVP-3 前半    Session snapshot 表 + repo

Day 6  上午  MVP-3 后半    集成 + 状态机接入 + 真跑验证
Day 6  下午  MVP-4         Container 去嵌套（删除 ThreadPoolExecutor workaround）

Day 7  上午  MVP-5         前端抽 3 组件（基于 antd 二次封装）
Day 7  下午  MVP-8 前半    11 工具真调测试

Day 8  上午  MVP-8 后半    L3Writer + Graph 端点真验 + 修复 bug
Day 8  下午  写 MVP 完成报告 + 更新 CHECKLIST + 合并到 refactor/v2
```

**总周期**：Day 0 半天 + Day 1-8 共 8.5 天。

> **MVP-7（MinIO）推到第二轮**：当前本地文件存储（`L0_STORAGE_PATH`）能满足 MVP 单人演示需求，MinIO 是 P3 的基础设施要求，不需要在 MVP 阶段引入。

---

## 六、里程碑与验收

| 里程碑 | 完成节点 | 验收依据 |
|--------|---------|---------|
| **M-MVP-1** | Day 4 上午 | 端到端脚本能跑通，全部 9 步成功，3 轮 × 3 项目 = 9 次无 P0 错，所有 P0 bug 已修复 |
| **M-MVP-2** | Day 6 下午 | TaskStore + Session 状态机持久化通过测试，重启后旧状态可查；Container 去嵌套完成 |
| **M-MVP-3** | Day 8 下午 | 全部 7 项任务完成（MVP-7 推后），综合分从 55 提升到 80+ |
| **M-MVP-4** | Day 8 + 1 天 | 全部 7 项任务有回归测试 + 文档记录 + CHECKLIST 更新 |

> **每个 M-MVP 通过后**：合并到 `refactor/v2` + 更新 `docs/CHECKLIST.md` + 在 PR 链接中附上验证截图。

---

## 七、风险总览

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| MVP-1 真跑发现大量 P0 bug（>10） | 高 | Day 2-3 无法收尾 | 已调整估时为 3-4 天；优先修阻塞主链路的 bug，次要 bug 记录到遗留问题 |
| LLM API 限流或余额不足 | 中 | MVP-1 跑不通 | 准备 2 个 API Key 切换；限流时记录重试次数；增加"Mini-LM"模式（最小 prompt 跑 1 轮验证链路） |
| 估时超支（实际 > 8.5 天） | 中 | 冲刺延期 | 已基于评估报告调整估时；MVP-7 已推后；如仍超支，MVP-5 前端组件化可进一步推后 |
| 持久化方案性能瓶颈 | 低 | MVP-2/3 延迟超标 | 用 JSONB + 索引；按 session_id 分区 |
| 前端组件化引入新 bug | 中 | MVP-5 页面渲染异常 | 基于 antd 二次封装（非从零手写），降低风险；每个组件独立 PR |

---

## 八、回滚策略

每个任务独立 commit，**不引入破坏性 schema 变更**：
- MVP-2 / MVP-3：新增 PG 表 + 字段，原行为可通过 `FEATURE_OUTPUT_PERSIST=false` / `FEATURE_SESSION_PERSIST=false` 关闭
- MVP-4：保留旧 `pipeline.execute` 同步路径作为 fallback
- MVP-5：纯前端重构，git revert 即可
- MVP-6：日志中间件可关闭
- MVP-8：纯测试 + bug 修复，无功能开关

**总回滚开关**：`MVP_HARDENING_ENABLED=false` 一次性关闭 MVP-2/3/4/6 的新增功能（环境变量级总闸）。

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
