# ReqRadar V2 — MVP Hardening 验收清单

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | 配套 MVP-01 实施计划的逐项验证清单 |
| 前置文档 | [MVP-01_MVP_HARDENING_PLAN.md](MVP-01_MVP_HARDENING_PLAN.md) |
| 核心目标 | 提供 8 项任务的"可执行、可勾选、可签字"验收流程 |
| 文档职责 | 每个任务有：前置条件、验证步骤、判定标准、回归测试要求、签字栏 |

---

## 使用说明

1. **每个任务独立验收**：完成一项后立即执行对应章节，不必等全部完成
2. **判定标准分三档**：
   - ✅ **PASS**：所有验收点通过，可签字
   - ⚠️ **PASS WITH NOTES**：通过但有遗留问题，必须记录在 [遗留问题登记](#遗留问题登记)
   - ❌ **FAIL**：未通过，必须修复后重新验收
3. **签字栏**：编码 Agent + 验收人双方签字，编码 Agent 不能自己验收自己
4. **配套动作**：每项任务 PASS 后，同步更新 `docs/CHECKLIST.md` 对应章节

---

## 全局前置条件

执行任何 MVP 任务前，必须满足：

```
[ ] conda activate reqradar
[ ] python --version       # ≥ 3.12.13
[ ] pip install -e reqradar/kernel
[ ] cp .env.example .env   # 已填入真实 LLM API Key
[ ] git status             # 工作区干净，refactor/v2 分支
[ ] git log --oneline -5   # 确认从最近一次 merge 后开始
```

---

## MVP-1：端到端真跑一次

### 1.1 前置条件

```
[ ] 11 个 docker 容器可正常启动
[ ] 至少 1 个真实项目可用于测试（推荐：cool-agent 仓库 + 1 份 PDF/Word 需求文档）
[ ] LLM API Key 有效且余额充足（建议 ≥ 10 万 token）
```

### 1.2 验证步骤

```
[ ] 步骤 1：docker compose up -d，等待 30 秒
        判定：docker compose ps 全部 healthy

[ ] 步骤 2：docker compose exec api-service alembic upgrade head
        判定：无错误，输出 "Running upgrade -> head"

[ ] 步骤 3：执行 scripts/e2e_smoke.py（脚本需先创建）
        判定：9 步全部 2xx 返回

[ ] 步骤 4：人工核查输出报告
        判定：报告含 ≥ 3 个风险点、≥ 5 条证据、≥ 2 个维度评估

[ ] 步骤 5：重复步骤 3-4 共 3 轮
        判定：3 轮全部成功，无 5xx 错误

[ ] 步骤 6：使用 3 类项目各跑一次（git clone / 本地目录 / 压缩包）
        判定：3 类全部成功

[ ] 步骤 7：填写 docs/MVP-1_BUG_LOG.md
        判定：所有 P0 bug 已修复并记录
```

### 1.3 判定标准

| 维度 | 标准 |
|------|------|
| **成功率** | 9 步 × 3 轮 × 3 类 = 27 次，0 次 5xx 错误 |
| **报告质量** | 风险点 ≥ 3，证据 ≥ 5，维度 ≥ 2 |
| **LLM Token 消耗** | 单次分析 ≤ 50k tokens（粗略） |
| **延迟** | 单次端到端 ≤ 3 分钟 |
| **Bug 闭环** | 发现的 P0 bug 100% 修复 |

### 1.4 回归测试

```
[ ] 现有 tests/unit/ 全部通过（pytest -q）
[ ] ruff check reqradar/ services/ tests/ 无 lint 错误
[ ] mypy reqradar/kernel/ 无类型错误
```

### 1.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## MVP-2：TaskStore 落 PG

### 2.1 前置条件

```
[ ] MVP-1 通过
[ ] Alembic 迁移脚本 MVP-2_create_output_tasks.py 已编写
[ ] reqradar/output_svc/store.py 已实现
[ ] services/output/app.py 已替换 _tasks
```

### 2.2 验证步骤

```
[ ] 步骤 1：alembic upgrade head
        判定：output_tasks 表已创建

[ ] 步骤 2：alembic downgrade -1
        判定：表被删除，无残留

[ ] 步骤 3：alembic upgrade head（重新升级）
        判定：表重新创建

[ ] 步骤 4：pytest tests/unit/output_svc/test_store.py -v
        判定：所有用例通过

[ ] 步骤 5：创建 task（POST /tasks）→ 记录 task_id
        判定：返回 201 + task_id

[ ] 步骤 6：docker compose restart output-service
        判定：容器重启成功

[ ] 步骤 7：GET /tasks/{task_id}（使用步骤 5 的 task_id）
        判定：200 + 正确状态

[ ] 步骤 8：9 项边界测试
        - 成功路径：创建 → 查询 → 更新 → 完成
        - 404：查询不存在的 task_id
        - 409：重复创建同 ID
        - 422：非法参数
        - 500 降级：PG 不可用时返回错误但服务不挂
```

### 2.3 判定标准

| 维度 | 标准 |
|------|------|
| **迁移** | upgrade + downgrade 双向可用 |
| **单测覆盖率** | OutputTaskStore 覆盖率 ≥ 80% |
| **持久化** | 重启后 task_id 仍可查（步骤 7 验证） |
| **降级** | PG 故障时服务不挂，返回 503 + 明确错误 |
| **9 项边界** | 全部覆盖 |

### 2.4 回归测试

```
[ ] pytest tests/unit/output_svc/ -v
[ ] pytest tests/integration/output_service/ -v（如有）
[ ] 现有 5xx 端到端流程不退化
```

### 2.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## MVP-3：Session 状态机从 PG 恢复

### 3.1 前置条件

```
[ ] MVP-1 通过
[ ] Alembic 迁移 MVP-3_create_session_snapshots.py 已编写
[ ] reqradar/cognitive_rt/runtime/session_repo.py 已实现
[ ] SessionStateMachine 启动时 load 逻辑已接入
```

### 3.2 验证步骤

```
[ ] 步骤 1：alembic upgrade head
        判定：session_snapshots 表已创建

[ ] 步骤 2：pytest tests/unit/cognitive_rt/runtime/test_session_repo.py -v
        判定：save/load/list_active 全部通过

[ ] 步骤 3：启动 Session（POST /sessions）→ 推进到 RUNNING
        判定：DB 中有对应 snapshot

[ ] 步骤 4：docker compose restart cognitive-rt
        判定：容器重启成功，日志显示 "Loaded N active sessions"

[ ] 步骤 5：GET /sessions/{id}
        判定：状态正确恢复，可继续推进

[ ] 步骤 6：状态机转换测试
        - CREATED → READY
        - READY → RUNNING
        - RUNNING → CHECKPOINTING → COMPLETED
        - 非法转换：READY → COMPLETED（拒绝）
        - 持久化失败：模拟 DB 故障（断网）→ 状态转换仍进行（降级）

[ ] 步骤 7：中断恢复测试
        - 创建 Session → 运行 5 步
        - kill -9 cognitive-rt
        - 重启
        - 验证：Session 状态从第 5 步附近恢复

[ ] 步骤 8：审计日志验证
        判定：每次状态转换对应 1 个 EVENT，存入 events 表
```

### 3.3 判定标准

| 维度 | 标准 |
|------|------|
| **迁移** | upgrade + downgrade 双向可用 |
| **持久化** | CREATED/READY/RUNNING 状态的 Session 重启可恢复 |
| **审计** | 所有状态转换产生 event 日志 |
| **降级** | 持久化失败不阻塞状态转换 |
| **状态机正确性** | 非法转换全部拒绝 |
| **中断恢复** | kill -9 重启后 Session 状态可继续 |

### 3.4 回归测试

```
[ ] pytest tests/unit/cognitive_rt/runtime/ -v
[ ] 现有 ReAct 推理流程不退化
[ ] 9 工具调用路径不变
```

### 3.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## MVP-4：Container 模型去嵌套

### 4.1 前置条件

```
[ ] MVP-1 通过
[ ] 所有 asyncio.run / run_in_executor 调用点已识别
[ ] pipeline.execute_sync / execute_async 双接口已实现
```

### 4.2 验证步骤

```
[ ] 步骤 1：grep -r "asyncio.run" reqradar/ services/ 2>&1 | wc -l
        判定：输出为 0

[ ] 步骤 2：grep -r "run_in_executor" reqradar/ services/ 2>&1
        判定：仅在明确异步上下文中使用，无嵌套

[ ] 步骤 3：pytest tests/unit/cognitive_rt/cognition/test_context_pipeline.py -v
        判定：所有用例通过

[ ] 步骤 4：跑端到端脚本 10 轮（tests/e2e/test_mvp1_smoke.py）
        判定：10 轮全部成功，无死锁

[ ] 步骤 5：context assembly 延迟统计
        判定：平均延迟 ≤ 2s

[ ] 步骤 6：Fallback 路径验证
        判定：FEATURE_PIPELINE_SYNC_FALLBACK=true 时仍可用旧路径
```

### 4.3 判定标准

| 维度 | 标准 |
|------|------|
| **asyncio.run 消除** | 100% 消除 |
| **死锁率** | 10 轮真跑 0 次死锁 |
| **性能** | context assembly 延迟 ≤ 2s |
| **Fallback** | 旧路径仍可工作（feature flag 控制） |

### 4.4 回归测试

```
[ ] pytest tests/unit/cognitive_rt/cognition/ -v
[ ] 端到端流程不退化
[ ] 9 工具调用延迟不变
```

### 4.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## MVP-5：前端抽核心组件

### 5.1 前置条件

```
[ ] MVP-1 通过
[ ] Button / Table / Loading 三个组件已创建
[ ] 8 页面已重构使用新组件
```

### 5.2 验证步骤

```
[ ] 步骤 1：cd frontend && npm run type-check
        判定：0 类型错误

[ ] 步骤 2：npm run lint
        判定：0 lint 错误

[ ] 步骤 3：grep -r "<button" frontend/src/pages 2>&1 | wc -l
        判定：输出 ≤ 2（仅在极特殊场景使用）

[ ] 步骤 4：grep -r "<table" frontend/src/pages 2>&1 | wc -l
        判定：输出 ≤ 2

[ ] 步骤 5：8 页面逐一访问
        - /dashboard
        - /projects
        - /projects/{id}
        - /sessions/{id}
        - /reports/{id}
        - /knowledge
        - /checkpoints/{id}
        - /settings
        判定：所有页面渲染正常，无 console 错误

[ ] 步骤 6：Loading 状态验证
        判定：异步数据加载时显示 skeleton / spinner，覆盖 90% 列表

[ ] 步骤 7：响应式验证
        判定：移动端（< 768px）布局正常
```

### 5.3 判定标准

| 维度 | 标准 |
|------|------|
| **类型检查** | 0 错误 |
| **Lint** | 0 错误 |
| **组件复用** | 3 组件覆盖 ≥ 90% 场景 |
| **页面渲染** | 8 页面无 console 错误 |
| **Loading 覆盖** | ≥ 90% 异步数据展示 |

### 5.4 回归测试

```
[ ] npm run build
[ ] 现有页面交互逻辑不变
[ ] WebSocket 实时推送仍工作
```

### 5.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## MVP-6：结构化日志 + /health 深健康

### 6.1 前置条件

```
[ ] MVP-1 通过
[ ] JSON 日志格式已定义
[ ] 深健康检查工具已实现
```

### 6.2 验证步骤

```
[ ] 步骤 1：docker compose logs -f api-service | head -50
        判定：日志为 JSON 格式，可被 jq 解析

[ ] 步骤 2：echo '{"level": "info", "msg": "test"}' | jq .
        判定：合法 JSON

[ ] 步骤 3：检查 7 个服务的日志
        - api-service
        - auth-service
        - cognitive-rt
        - index-service
        - output-service
        - ingestion-service
        - integration-service
        判定：7 个全部输出 JSON

[ ] 步骤 4：curl http://localhost:8000/health
        判定：200 + {"status": "ok", "deps": {"pg": "ok", "redis": "ok", "chroma": "ok"}}

[ ] 步骤 5：docker compose stop postgres
        判定：/health 返回 503 + 明确错误

[ ] 步骤 6：docker compose start postgres
        判定：/health 恢复 200

[ ] 步骤 7：深健康覆盖验证
        - PG：执行 SELECT 1
        - Redis：执行 PING
        - Chroma：执行 heartbeat
        判定：3 个依赖全部深度验证

[ ] 步骤 8：日志字段验证
        判定：每条日志含 session_id / request_id / timestamp / level / msg
```

### 6.3 判定标准

| 维度 | 标准 |
|------|------|
| **JSON 格式** | 7 个服务 100% 输出 JSON |
| **可被 jq 解析** | 100% 合法 |
| **深健康** | /health 检查 PG + Redis + Chroma 真实可用性 |
| **降级** | 任一依赖失败 → 503 + 详细错误 |
| **关联字段** | session_id / request_id 携带率 ≥ 90% |

### 6.4 回归测试

```
[ ] 7 个服务的现有日志仍可读
[ ] 错误处理路径不变
[ ] 性能损耗 ≤ 5%
```

### 6.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## MVP-7：MinIO 接入 L0 原始文件

### 7.1 前置条件

```
[ ] MVP-1 通过
[ ] docker-compose.yml 已添加 minio service
[ ] boto3 依赖已添加
[ ] MinIO Client 封装已实现
```

### 7.2 验证步骤

```
[ ] 步骤 1：docker compose up -d minio
        判定：minio 容器 healthy

[ ] 步骤 2：访问 http://localhost:9001
        判定：MinIO 控制台可登录

[ ] 步骤 3：自动 bucket 创建验证
        判定：reqradar-l0 bucket 已创建

[ ] 步骤 4：pytest tests/unit/ingestion/test_s3_client.py -v
        判定：s3_client 单测通过

[ ] 步骤 5：上传文档（POST /projects/{id}/upload）
        判定：返回 201 + object_key

[ ] 步骤 6：MinIO 控制台核查
        判定：bucket 中可见对应对象

[ ] 步骤 7：L0 metadata 验证
        判定：PG raw_context 表有对应记录，对象 key 正确

[ ] 步骤 8：降级路径验证
        - 设置 L0_STORAGE_BACKEND=local
        - 上传文档
        - 判定：仍可用，文件存本地路径

[ ] 步骤 9：MinIO 故障测试
        - docker compose stop minio
        - 上传文档
        - 判定：返回明确错误（不挂服务）
```

### 7.3 判定标准

| 维度 | 标准 |
|------|------|
| **MinIO 启动** | 容器 healthy，控制台可访问 |
| **Bucket 创建** | reqradar-l0 自动创建 |
| **对象存储** | 上传后 MinIO 中可见 |
| **metadata** | PG raw_context 记录正确 |
| **降级** | L0_STORAGE_BACKEND=local 时仍可用 |
| **故障处理** | MinIO 不可用时返回明确错误 |

### 7.4 回归测试

```
[ ] 现有 ingestion 流程不退化
[ ] 9 工具中的 read_file 仍能读取文件
[ ] 文档检索仍能工作
```

### 7.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## MVP-8：9 工具 + L3Writer + Graph 端点真验

### 8.1 前置条件

```
[ ] MVP-2 / MVP-3 通过
[ ] 5 个核心工具（search_code / read_file / search_requirements / list_modules / get_project_profile）已实现
[ ] L3Writer 已注入 PG
[ ] Graph 三端点（neighbors / path / subgraph）已实现
```

### 8.2 验证步骤

#### 工具真调

```
[ ] 步骤 1：search_code
        - 输入：query="用户认证"，project_id=xxx
        - 判定：返回 ≥ 3 个代码片段

[ ] 步骤 2：read_file
        - 输入：path="/src/auth/login.py"
        - 判定：返回文件内容

[ ] 步骤 3：search_requirements
        - 输入：query="登录流程"，project_id=xxx
        - 判定：返回 ≥ 1 个需求文档片段

[ ] 步骤 4：list_modules
        - 输入：project_id=xxx
        - 判定：返回 ≥ 1 个模块

[ ] 步骤 5：get_project_profile
        - 输入：project_id=xxx
        - 判定：返回项目画像

[ ] 步骤 6：每个工具跑 3 场景（项目存在 / 不存在 / 部分数据）
        判定：3 场景全部预期返回
```

#### L3Writer PG 注入

```
[ ] 步骤 7：pytest tests/unit/index_svc/test_l3_writer.py -v
        判定：7 种 L3 知识类型单测全部通过

[ ] 步骤 8：创建 7 种知识各 1 条
        - 术语
        - 模块画像
        - 架构约束
        - 决策记录
        - 风险演化
        - 需求谱系
        - 事故记忆
        判定：PG 中可见全部 7 条

[ ] 步骤 9：freshness / confidence 字段验证
        判定：每条记录有正确元数据
```

#### Graph 端点

```
[ ] 步骤 10：graph_neighbors
        - 输入：node_id=xxx, depth=2
        - 判定：返回邻居列表（非空）

[ ] 步骤 11：graph_path
        - 输入：source=xxx, target=yyy
        - 判定：返回路径列表

[ ] 步骤 12：graph_subgraph
        - 输入：center=xxx, radius=2
        - 判定：返回节点 + 边（非空）
```

### 8.3 判定标准

| 维度 | 标准 |
|------|------|
| **5 工具** | 5 工具 × 3 场景 = 15 次全成功 |
| **L3 7 类型** | 全部可写可查 |
| **Graph 三端点** | 全部返回真实数据 |
| **L3 元数据** | freshness / confidence 字段正确 |
| **真问题修复** | 发现的 bug 100% 修复 |

### 8.4 回归测试

```
[ ] pytest tests/unit/index_svc/ -v
[ ] pytest tests/unit/cognitive_rt/cognition/tools/ -v
[ ] 现有 ReAct 流程不退化
```

### 8.5 签字栏

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 编码 Agent | | | |
| 验收人 | | | |

---

## 全局验收（所有 8 项 PASS 后）

### 全局验证步骤

```
[ ] 步骤 1：完整执行 MVP-1 端到端脚本
        判定：9 步全部成功

[ ] 步骤 2：重启所有服务
        docker compose restart
        判定：所有容器 healthy

[ ] 步骤 3：复测 MVP-2 / MVP-3 的持久化场景
        判定：重启后旧 task_id 和 session 仍可查

[ ] 步骤 4：复测 5 工具 + L3 + Graph
        判定：全部真验通过

[ ] 步骤 5：检查 7 个服务的日志
        判定：JSON 格式 + 关联字段完整

[ ] 步骤 6：检查 8 个前端页面
        判定：渲染正常 + Loading 状态覆盖

[ ] 步骤 7：MinIO 控制台核查
        判定：bucket 正常 + 对象可见

[ ] 步骤 8：综合评分
        判定：综合分从 55 提升到 80+（参照 MVP-01 §一.1.3）
```

### 全局签字栏

| 角色 | 姓名 | 日期 | 签字 | 备注 |
|------|------|------|------|------|
| 编码 Agent | | | | |
| 验收人 | | | | |
| 项目 Owner | | | | |

---

## 遗留问题登记

> 所有非阻塞性、需后续处理的问题记录在此。

| # | 任务 | 问题描述 | 严重度 | 处理计划 | 截止日期 |
|---|------|---------|--------|---------|---------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 配套动作

每个任务 PASS 后，必须同步执行：

1. **更新 `docs/CHECKLIST.md`**
   - 添加 MVP-{N} 验收记录行
   - 标注 ✅ / ⚠️ / ❌

2. **合并到 `refactor/v2`**
   ```bash
   git checkout refactor/v2
   git merge <feature-branch> --no-ff -m "merge: MVP-{N} complete"
   ```

3. **如新增表/端点/配置项**
   - [C-06_DATABASE_MIGRATION_PLAN.md](C-06_DATABASE_MIGRATION_PLAN.md) 注册
   - [C-04_API_CONTRACT_REGISTRY.md](C-04_API_CONTRACT_REGISTRY.md) 注册
   - [C-03_CONFIGURATION_REGISTRY.md](C-03_CONFIGURATION_REGISTRY.md) 注册

4. **若涉及 P0 修复**
   - 在 CHECKLIST.md"第三轮 Bug 修复"章节追加记录

---

## 总结

本验收清单为 8 项 MVP 任务提供**可执行、可勾选、可签字**的验收流程。每个任务有：

- **明确的前置条件**：避免在错误的基础上验证
- **具体验证步骤**：可被任何工程师独立执行
- **量化判定标准**：避免主观判断
- **回归测试要求**：确保不退化
- **双方签字栏**：确保责任落实

完成全部 8 项后，V2 进入 **MVP 可交付状态**，综合分从 55 提升到 80+。
