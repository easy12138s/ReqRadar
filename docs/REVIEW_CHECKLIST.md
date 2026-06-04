# ReqRadar V2 — Code Review 检查清单

```
本文档汇总项目全部文档中的检查规则，供验收人每次 review 代码时逐项核对。
编码 Agent 不应修改本文档。
```

---

## 通则（每轮 Review 必走）

### A. 运行检查

```bash
# === 三件套（必须全部通过） ===
conda activate reqradar
pip install -e reqradar/kernel
ruff check reqradar/ tests/
ruff format --check reqradar/ tests/
mypy reqradar/kernel/

# === 测试 ===
pytest tests/ -q

# === 依赖合规 ===
python scripts/check_dependencies.py
```

---

### B. 编码铁律（来源：AGENTS.md §2.1 / C-01）

| # | 规则 | 检查方法 |
|---|------|---------|
| 1 | `str \| None` 不用 `Optional[str]` | grep `Optional\[` |
| 2 | `list[str]` 不用 `List[str]` | grep `List\[` `Dict\[` `Tuple\[` |
| 3 | `X \| Y` 不用 `Union[X, Y]` | grep `Union\[` |
| 4 | 绝对导入，禁止相对导入 | grep `from \.` |
| 5 | 异常必须带 `cause` 链 | Verify `raise XxxError(..., cause=e)` pattern |
| 6 | 禁止 `Any` 类型（Protocol 签名除外） | grep `: Any` `-> Any` |
| 7 | Pydantic 字段必须 `Field(description="中文描述")` | grep `Field()` 核对是否有 description |
| 8 | 禁止裸 `except:` | grep `^except:` |
| 9 | 禁止 `print()` 替代日志 | grep `print(` |
| 10 | 禁止模块级 `load_config()` 直接调用 | grep `load_config` at module level |
| 11 | f-string 格式化日志 | 检查 logger.\* 调用是否用 f-string |
| 12 | Docstring 中文，标识符英文 | 抽查 |

---

### C. 依赖铁律（来源：AGENTS.md §2.2 / C-02 §6）

| 规则 | 检查方法 |
|------|---------|
| `kernel/` 禁止 import `web/*` `modules/*` `agent/*` `cli/*` `mcp/*` | grep `from reqradar\.(web\|modules\|agent\|cli\|mcp)` in kernel/ |
| `cognitive_rt/` 禁止 import `web/*` | grep `from reqradar\.web` in cognitive_rt/ |
| `index_svc/` 禁止 import `cognitive_rt/*` `web/*` | grep 跨目录 import |
| `output_svc/` 禁止 import `cognitive_rt/*` `web/*` | grep 跨目录 import |
| `web/api/` 各路由禁止互相 import | grep `from reqradar\.web\.api` in web/api/ |
| `web/services/` 各服务禁止互相 import | grep `from reqradar\.web\.services` in web/services/ |

**替代方案**：直接运行 `python scripts/check_dependencies.py`

---

### D. 安全审查（来源：S-01 §11）

| # | 规则 | 检查方法 |
|---|------|---------|
| 1 | 未硬编码密钥、密码、Token | grep 敏感字符串 |
| 2 | 用户输入经 Pydantic Field 约束 | 检查新 Pydantic 模型 |
| 3 | 文件路径操作经过路径遍历防护 | grep `open(` `Path(` `os.path` |
| 4 | 异常消息未暴露内部路径、堆栈 | grep `exc_info` `traceback` |
| 5 | 日志不包含 JWT / API Key / 密码 | grep 日志中拼接敏感字段 |
| 6 | SQL 查询全部 ORM 参数化 | grep `execute(` 检查 raw SQL |
| 7 | 资源操作校验用户归属 | 检查 Session/Project 归属|
| 8 | 管理端点校验 admin 角色 | grep `@requires` `is_admin` |
| 9 | 新增端点标注认证要求 | 检查端点 decorator |

---

### E. 测试覆盖（来源：C-05 §13.3 / C-05 §2.4）

**9 项边界覆盖必须全部有对应测试：**

```
[ ] 成功路径：至少 1 个正向测试
[ ] 未认证(401)：所有端点的无 token 访问
[ ] 权限不足(403)：跨用户访问、普通用户访问管理接口
[ ] 不存在(404)：GET/PUT/DELETE 不存在的 ID
[ ] 无效参数(422)：缺失必填字段、类型错误、越界值
[ ] 重复数据(409)：唯一约束冲突
[ ] 空列表(200)：无数据时返回空列表
[ ] 外部服务失败：mock LLM/存储失败
[ ] 路径遍历：文件读取类端点的 `../` 攻击
```

**测试隔离规则（C-05 §2.4）：**
- [ ] 每个测试用独立 SQLite + `tmp_path`，不依赖执行顺序
- [ ] LLM / 网络 / Git / MinIO / Redis 全部 mock
- [ ] 不使用真实 home 目录或开发数据库

---

### F. 文档一致性（来源：docs/README.md）

```
[ ] 如果新增 API 端点 → 已在 C-04（API 契约注册表）注册
[ ] 如果新增配置项 → 已在 C-03（配置注册表）注册
[ ] 如果新增数据库表 → 已在 C-06（数据库迁移计划）注册
[ ] 如果新增异常类型 → 已在 C-01 异常层次图中注册
[ ] 新增文档 → 已在 docs/README.md 状态表 + 对应 Phase 查阅区注册
```

---

### G. 数据流铁律（来源：03_COGNITIVE_ASSET_MODEL.md）

```
L0 Raw Context (MinIO) → 不可变，不参与语义检索
L1 Structured Facts (PG+ChromaDB) → 可索引，不包含推理结论
L2 Analysis Records (PG JSONB) → 追加不可改
L3 Persistent Knowledge (PG+ChromaDB) → 追加演化，受治理框架约束
```

- [ ] 所有结论必须可追溯到 L0/L1 证据
- [ ] L2 记录只能追加，不可修改已有内容
- [ ] L3 知识修改必须走 `append` / `deprecate` / `merge` 语义，不可原地改

---

## Phase 专项检查

### P0 — Kernel 抽离

```
[ ] kernel/ 总行数 ≤ 3000
[ ] 所有公开接口有中文 docstring
[ ] 所有异常支持 cause 链
[ ] UUID 主键用 default=uuid4，非 gen_random_uuid()（SQLite兼容）
[ ] Kernel 只依赖 stdlib + third-party（sqlalchemy + pydantic + aiosqlite）
```

### P1 — 模块化单体 + Context Pipeline

```
[ ] Context Pipeline 五阶段完整：Collect → Score → Select → Compress → Assemble
[ ] Token Budget ≤ 预算 105%（超限抛 ContextBudgetExceededException）
[ ] Quality Gate 正确触发 LOW_CONTEXT_CONFIDENCE 模式
[ ] ContextSource 接口预留 L3 适配器扩展点
[ ] Agent 入口注入 ContextPipeline，保留 f-string fallback 开关
[ ] 目录边界清晰：cognitive_rt/ index_svc/ output_svc/
[ ] 所有 V1 import 路径已改为 V2 路径
```

### P3 — Cognitive Runtime Core

```
[ ] CognitiveSession 11 态状态机完整
[ ] Event Stream 三级事件体系（Session/Reasoning/Cognitive）
[ ] Checkpoint 三区存储（热 PG / 冷 MinIO / 可重建）
[ ] WebSocket 实时事件推送
[ ] 中断后从 Checkpoint 恢复步骤数和证据链一致
```

### P2 — Gateway + Auth

```
[ ] Traefik 正确路由 /api/* 到对应服务
[ ] JWT 签发/校验功能与 V1 一致
[ ] 服务间 Internal-API-Key 认证中间件
[ ] Auth 可独立部署、独立重启
```

### P4 — ToolRuntime

```
[ ] ToolRuntime.execute() 统一入口
[ ] 超时控制（asyncio.wait_for）
[ ] 指数退避重试
[ ] 工具执行前后自动 Checkpoint
[ ] TOOL_INVOKED / TOOL_RETURNED 事件记录
[ ] 权限校验（Scope×Domain）
```

### P5 — 拆 index-service + L3

```
[ ] index-service 可独立部署
[ ] ChromaDB 仅 index-service 持有连接
[ ] 七种 L3-A 知识类型全实现
[ ] 知识新鲜度管理（stale 90天检测）
[ ] 知识置信度计算（verification_count + 衰减 + human_verified）
[ ] L3ContextSource 适配器（Context Pipeline Collect 阶段注入）
[ ] 认知飞轮验证：
   - effective_injection_rate ≥ 60%
   - confidence_weighted_score ≥ 0.5
   - diversity_index 任何类型 ≤ 40%
```

### P6-P10（待补充）

```
当前仅 04 路线图有概述，详细验收标准需要在 Phase 启动前补充设计文档。
```

---

## Git 规范检查

```
[ ] 分支命名: refactor/v2-p{N}（从 refactor/v2 拉出）
[ ] 提交格式: <type>(<scope>): <short description>
    - type: feat / fix / refactor / docs / chore / style / test / ci / perf
    - scope: kernel / cognitive_rt / context-pipeline / index-svc / output-svc / web / auth / ...
[ ] 提交语言: 英文
[ ] PR 目标: refactor/v2
```
