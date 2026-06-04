# I-03 V1→V2 数据迁移映射方案

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V1 到 V2 的完整数据迁移映射、清洗规则与回滚方案 |
| 前置文档 | 03_COGNITIVE_ASSET_MODEL.md（L0-L3 四层模型）、C-06_DATABASE_MIGRATION_PLAN.md（V2 表结构）、04_IMPLEMENTATION_ROADMAP.md（P5.11 迁移方案）、CODE_WIKI.md（V1 数据模型） |
| 核心目标 | 提供 V1 19 张表到 V2 33 张表的字段级映射、数据清洗算法、可执行迁移脚本框架 |
| 文档职责 | What & How — 迁移什么、怎么迁移、怎么验证、怎么回滚 |

---

## 2. 迁移总则

### 2.1 迁移策略

```
V1 数据库（SQLite/PostgreSQL）
         │
         │ 1. 全量备份
         ▼
    V1 备份文件
         │
         │ 2. 读取 + 转换
         ▼
    V2 数据库（PostgreSQL 全新 Schema）
         │
         │ 3. 验证
         ▼
    迁移报告（通过/失败 + 统计数据）
```

### 2.2 迁移原则

| 原则 | 说明 |
|------|------|
| 只读源库 | 迁移脚本不修改 V1 数据库任何数据 |
| 全新目标库 | V2 使用独立数据库，从零写入 |
| 可断点续迁 | 每张表独立迁移，失败可单独重跑 |
| 完整验证 | 迁移后自动校验数据完整性和关联一致性 |
| 可回滚 | 迁移前全量备份 V1 数据库，回滚通过恢复 V1 + 删除 V2 DB 实现 |

### 2.3 迁移执行时机

在 P5（拆 index-service）完成后、V2 正式上线前执行。迁移脚本在测试环境至少验证 3 次后才在生产执行。

---

## 3. V1 → V2 表级映射总览

### 3.1 直接搬迁（结构基本一致）

| V1 表 | V2 表 | 变更说明 |
|-------|-------|---------|
| `users` | `users` | 字段基本一致，V2 增加 UUID 主键（如 V1 用自增 ID） |
| `revoked_tokens` | `revoked_tokens` | 同结构 |
| `user_configs` | `user_configs` | 同结构 |
| `system_configs` | `system_configs` | 同结构 |
| `project_configs` | `project_configs` | 同结构 |
| `report_templates` | `report_templates` | 同结构 |
| `mcp_access_keys` | （auth-service） | 同结构 |
| `projects` | `projects` | V2 增加 UUID 主键 |

### 3.2 结构转换

| V1 表 | V2 表 | 转换逻辑 |
|-------|-------|---------|
| `uploaded_files` | `raw_context`（L0） | 文件路径映射为 MinIO URI |
| `analysis_tasks` | `cognitive_sessions`（L2） | 状态映射 + 字段拆分 |
| `reports` | `cognitive_sessions.state` + `events` | 报告数据拆分为 Session 状态和事件 |
| `report_versions` | `checkpoints`（L2） | 版本 → Checkpoint 版本链 |
| `report_chats` | `events`（L2） | 对话记录 → SESSION_WAITING_INPUT 事件 |
| `requirement_documents` | `chunks`（L1） | 需求文本 Chunking 后写入 |
| `pending_changes` | `knowledge_changelog`（L3） | 待审核变更 → 知识变更日志 |
| `synonym_mappings` | `glossary.aliases`（L3） | 同义词 → 术语别名 |
| `llm_call_logs` | `events`（reasoning 级） | LLM 调用日志 → TOOL_INVOKED 事件 |
| `mcp_tool_calls` | `events`（reasoning 级） | MCP 调用 → TOOL_INVOKED 事件 |
| `requirement_releases` | `requirement_lineage`（L3） | 发布版本 → 需求谱系 |

### 3.3 聚合沉淀

| V1 数据 | V2 目标 | 转换逻辑 |
|---------|---------|---------|
| `project_memory` JSON | L3 七种知识类型 | 按类型拆分 + 初始 confidence=0.5 |
| `analysis_tasks.progress_snapshot` | `events` + `evidence_records` | JSON 反序列化为结构化记录 |
| `analysis_tasks.context_json` | `checkpoints.hot_state` | 分析上下文 → Checkpoint 热状态 |

---

## 4. 字段级映射详情

### 4.1 `analysis_tasks` → `cognitive_sessions`

| V1 字段 | V2 字段 | 转换规则 |
|---------|---------|---------|
| `id`（int） | `session_id`（UUID） | `str(uuid5(NAMESPACE_OID, f"v1_task_{id}"))` |
| `project_id`（int） | `project_id`（UUID） | 查映射表 `v1_project_id → v2_project_id` |
| `user_id`（int） | `user_id`（UUID） | 查映射表 |
| `status` | `status` | direct_map: pending→CREATED, running→RUNNING, completed→COMPLETED, failed→FAILED, cancelled→CANCELLED |
| `requirement_text` | `state.context.requirement_text` | 写入 state JSONB |
| `depth` | `config.analysis_depth` | 写入 config JSONB |
| `template_id` | `config.template_id` | 查映射表 |
| `current_version` | `last_checkpoint_version` | 直接搬迁 |
| `progress_snapshot`（JSON） | 拆分为 `events` 多条记录 | 见 4.2 |
| `context_json`（JSON） | `checkpoints.hot_state` | 见 4.3 |
| `created_at` | `created_at` | 直接搬迁 |
| `updated_at` | `updated_at` | 直接搬迁 |

### 4.2 `progress_snapshot` → `events`

V1 的 `progress_snapshot` JSON 结构反序列化后，按步骤生成 V2 事件：

```python
# 伪代码
for step in progress_snapshot.get("steps", []):
    # 步骤开始事件
    events.append({
        "session_id": session_id,
        "event_type": "STEP_STARTED",
        "event_level": "reasoning",
        "payload": {"step": step["index"], "phase": step.get("phase", "ANALYSIS")}
    })
    # 工具调用事件
    for tool_call in step.get("tool_calls", []):
        events.append({
            "session_id": session_id,
            "event_type": "TOOL_INVOKED",
            "event_level": "reasoning",
            "payload": {"tool_name": tool_call["name"], "params": tool_call.get("params", {})}
        })
        events.append({
            "session_id": session_id,
            "event_type": "TOOL_RETURNED",
            "event_level": "reasoning",
            "payload": {"tool_name": tool_call["name"], "result_summary": tool_call.get("result", "")[:200]}
        })
    # 步骤完成事件
    events.append({
        "session_id": session_id,
        "event_type": "STEP_COMPLETED",
        "event_level": "reasoning",
        "payload": step
    })
```

### 4.3 `context_json` → `checkpoints`

对于状态为 COMPLETED / FAILED 的分析任务，将其 `context_json` 作为 Checkpoint 的最终快照：

```python
checkpoint = {
    "session_id": session_id,
    "version": 1,
    "previous_version": None,
    "type": "SESSION_COMPLETE",
    "state_summary": {
        "current_step": context_json.get("total_steps", 0),
        "current_phase": "COMPLETED",
        "context_usage": context_json.get("token_usage", 0),
        "evidence_count": len(context_json.get("evidence", [])),
        "dimensions_completed": [],
        "dimensions_pending": ["completeness", "consistency", "feasibility", "traceability", "ambiguity", "risk", "architecture"]
    },
    "hot_state": {
        "agent_state": {
            "current_step": context_json.get("total_steps", 0),
            "current_phase": "COMPLETED"
        },
        "evidence_state": {
            "total": len(context_json.get("evidence", [])),
            "by_type": {},
            "avg_confidence": 0.5
        },
        "dimension_state": {}
    },
    "cold_state_json": json.dumps(context_json),
    "metadata": {"migrated_from": "v1_analysis_task"}
}
```

### 4.4 `uploaded_files` → `raw_context`（L0）

| V1 字段 | V2 字段 | 转换规则 |
|---------|---------|---------|
| `id` | `id` | UUID 映射 |
| `project_id` | `project_id` | UUID 映射 |
| `file_name` | `original_filename` | 直接搬迁 |
| `file_path`（本地路径） | `uri` | `minio://projects/{project_id}/l0/document/{timestamp}/{file_name}` |
| `file_size` | `size_bytes` | 直接搬迁 |
| `file_hash`（如有） | `content_hash` | 直接搬迁 |
| `source` | `source` | `"upload"` |
| `file_type` | `type` | direct_map: pdf/docx/pptx/xlsx→document, zip→repo_snapshot, 其他→other |
| `created_at` | `ingested_at` | 直接搬迁 |

### 4.5 `project_memory` JSON → L3 知识类型

V1 的 `project_memory` 是一个 JSON 字段，包含术语表、模块关系、历史经验等混合数据。

```python
def migrate_project_memory(project_id: str, memory_json: dict) -> dict[str, list]:
    """将 V1 project_memory 拆分为 L3 七种知识类型。"""
    result = {"glossary": [], "module_profiles": [], "constraints": [], "decisions": [], "risks": [], "requirement_lineage": [], "incidents": []}

    # 术语表 → glossary
    for term in memory_json.get("terminology", []):
        result["glossary"].append({
            "canonical_name": term["term"],
            "definition": term.get("definition", ""),
            "aliases": term.get("aliases", []),
            "confidence_score": 0.5,
            "freshness": "active",
            "source_session_count": 1,
            "human_verified": False,
        })

    # 模块关系 → module_profiles
    for module_name, module_data in memory_json.get("modules", {}).items():
        result["module_profiles"].append({
            "module_name": module_name,
            "description": module_data.get("description", ""),
            "dependencies": module_data.get("dependencies", []),
            "confidence_score": 0.5,
            "freshness": "active",
        })

    # 历史经验 → decisions / incidents
    for exp in memory_json.get("experiences", []):
        exp_type = exp.get("type", "decision")
        if exp_type == "incident":
            result["incidents"].append({
                "incident_id": f"v1-{exp.get('id', uuid4())}",
                "title": exp.get("title", ""),
                "description": exp.get("description", ""),
                "severity": exp.get("severity", "medium"),
                "confidence_score": 0.5,
                "freshness": "historical",
            })
        else:
            result["decisions"].append({
                "decision_id": f"v1-{exp.get('id', uuid4())}",
                "title": exp.get("title", ""),
                "context": exp.get("context", ""),
                "rationale": exp.get("rationale", ""),
                "confidence_score": 0.5,
                "freshness": "historical",
            })

    return result
```

---

## 5. ID 映射表设计

V1 使用自增整数 ID，V2 使用 UUID。需要维护映射表：

```sql
-- 迁移期间使用的临时映射表
CREATE TABLE _migration_id_map (
    v1_table VARCHAR(50) NOT NULL,
    v1_id INTEGER NOT NULL,
    v2_id UUID NOT NULL,
    PRIMARY KEY (v1_table, v1_id)
);

CREATE INDEX idx_migration_v2_id ON _migration_id_map(v2_id);
```

| V1 表 | ID 列 | V2 UUID 生成规则 |
|-------|-------|-----------------|
| users | id (int) | `uuid5(NAMESPACE_OID, f"v1_user_{id}")` |
| projects | id (int) | `uuid5(NAMESPACE_OID, f"v1_project_{id}")` |
| analysis_tasks | id (int) | `uuid5(NAMESPACE_OID, f"v1_task_{id}")` |
| report_templates | id (int) | `uuid5(NAMESPACE_OID, f"v1_template_{id}")` |

---

## 6. 迁移执行脚本框架

### 6.1 主入口

```python
#!/usr/bin/env python3
"""
V1 → V2 数据迁移脚本

使用方式:
  python migrate_v1_to_v2.py --v1-db postgresql://... --v2-db postgresql://...

迁移步骤:
  1. 校验 V1 数据库结构
  2. 建立 ID 映射表
  3. 按批次迁移表数据
  4. 验证数据完整性
  5. 输出迁移报告
"""
import asyncio
import json
import sys
from datetime import datetime
from uuid import UUID, NAMESPACE_OID, uuid4, uuid5

import click
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


def v2_uuid(v1_table: str, v1_id: int) -> UUID:
    """生成 V1 自增 ID 对应的 V2 UUID。"""
    return uuid5(NAMESPACE_OID, f"v1_{v1_table}_{v1_id}")


async def migrate_batch_1(session_v1: AsyncSession, session_v2: AsyncSession) -> dict:
    """批次 1：直接搬迁表（users, projects, 配置表, 模板表）"""
    stats = {}

    # users
    rows = (await session_v1.execute(text("SELECT * FROM users"))).fetchall()
    for row in rows:
        v2_id = v2_uuid("user", row.id)
        await session_v2.execute(
            text("INSERT INTO users (id, username, email, hashed_password, is_active, is_superuser, created_at, updated_at) VALUES (:id, :username, :email, :hashed_password, :is_active, :is_superuser, :created_at, :updated_at) ON CONFLICT DO NOTHING"),
            {"id": v2_id, "username": row.username, "email": row.email, "hashed_password": row.hashed_password, "is_active": row.is_active, "is_superuser": row.is_superuser, "created_at": row.created_at, "updated_at": row.updated_at},
        )
        await session_v2.execute(
            text("INSERT INTO _migration_id_map (v1_table, v1_id, v2_id) VALUES (:table, :v1_id, :v2_id) ON CONFLICT DO NOTHING"),
            {"table": "users", "v1_id": row.id, "v2_id": v2_id},
        )
    stats["users"] = len(rows)

    # projects（同样逻辑）
    # ...
    return stats


async def migrate_batch_2(session_v1: AsyncSession, session_v2: AsyncSession) -> dict:
    """批次 2：L0/L1 索引表（uploaded_files → raw_context）"""
    # 实现见第 4.4 节字段映射
    return {}


async def migrate_batch_3(session_v1: AsyncSession, session_v2: AsyncSession) -> dict:
    """批次 3：L2 核心表（analysis_tasks → cognitive_sessions + events + checkpoints）"""
    # 实现见第 4.1-4.3 节
    return {}


async def migrate_batch_4(session_v1: AsyncSession, session_v2: AsyncSession) -> dict:
    """批次 4：L3 知识表（project_memory → L3 七种知识类型）"""
    # 实现见第 4.5 节
    return {}


async def verify_migration(session_v1: AsyncSession, session_v2: AsyncSession) -> list[str]:
    """验证迁移完整性。"""
    errors = []

    # 验证用户数
    v1_count = (await session_v1.execute(text("SELECT COUNT(*) FROM users"))).scalar()
    v2_count = (await session_v2.execute(text("SELECT COUNT(*) FROM users"))).scalar()
    if v1_count != v2_count:
        errors.append(f"用户数不一致：V1={v1_count}, V2={v2_count}")

    # 验证项目数
    v1_count = (await session_v1.execute(text("SELECT COUNT(*) FROM projects"))).scalar()
    v2_count = (await session_v2.execute(text("SELECT COUNT(*) FROM projects"))).scalar()
    if v1_count != v2_count:
        errors.append(f"项目数不一致：V1={v1_count}, V2={v2_count}")

    # 验证 Session 数
    v1_count = (await session_v1.execute(text("SELECT COUNT(*) FROM analysis_tasks"))).scalar()
    v2_count = (await session_v2.execute(text("SELECT COUNT(*) FROM cognitive_sessions"))).scalar()
    if v1_count != v2_count:
        errors.append(f"Session 数不一致：V1={v1_count}, V2={v2_count}")

    return errors


@click.command()
@click.option("--v1-db", required=True, help="V1 数据库连接串")
@click.option("--v2-db", required=True, help="V2 数据库连接串")
@click.option("--dry-run", is_flag=True, help="仅校验不写入")
def main(v1_db: str, v2_db: str, dry_run: bool):
    """执行 V1 → V2 数据迁移。"""
    asyncio.run(_run(v1_db, v2_db, dry_run))


async def _run(v1_db: str, v2_db: str, dry_run: bool):
    engine_v1 = create_async_engine(v1_db)
    engine_v2 = create_async_engine(v2_db)

    async with engine_v1.begin() as conn_v1, engine_v2.begin() as conn_v2:
        # 创建映射表
        await conn_v2.execute(text("""
            CREATE TABLE IF NOT EXISTS _migration_id_map (
                v1_table VARCHAR(50) NOT NULL,
                v1_id INTEGER NOT NULL,
                v2_id UUID NOT NULL,
                PRIMARY KEY (v1_table, v1_id)
            )
        """))

        stats = {}
        stats.update(await migrate_batch_1(conn_v1, conn_v2))
        stats.update(await migrate_batch_2(conn_v1, conn_v2))
        stats.update(await migrate_batch_3(conn_v1, conn_v2))
        stats.update(await migrate_batch_4(conn_v1, conn_v2))

        errors = await verify_migration(conn_v1, conn_v2)

        if dry_run:
            await conn_v2.rollback()
            print("DRY RUN — 已回滚所有写入")
        elif errors:
            await conn_v2.rollback()
            print(f"迁移验证失败，已回滚：{errors}")
        else:
            await conn_v2.commit()
            print(f"迁移成功，统计：{json.dumps(stats, default=str)}")


if __name__ == "__main__":
    main()
```

---

## 7. 迁移批次执行顺序

| 批次 | 表 | 依赖 | 预计时间 |
|------|-----|------|---------|
| Batch 1 | users, projects, revoked_tokens, user_configs, system_configs, project_configs, report_templates | 无 | 1min |
| Batch 2 | raw_context, chunks, code_modules, code_dependencies, git_commits | Batch 1 | 5min |
| Batch 3 | cognitive_sessions, events, checkpoints, evidence_records | Batch 1 | 10min |
| Batch 4 | glossary, module_profiles, constraints, decisions, risks, incidents, requirement_lineage | Batch 1 | 5min |
| Batch 5 | evidence_relations, knowledge_relations, knowledge_changelog | Batch 3, 4 | 3min |

---

## 8. 回滚方案

### 8.1 回滚步骤

```
1. 停止所有 V2 服务
2. 删除 V2 数据库中的所有表（DROP SCHEMA public CASCADE; CREATE SCHEMA public;）
3. 重新运行 alembic upgrade head（重建空 V2 Schema）
4. 从备份恢复 V1 数据库（覆盖 V2 写入期间 V1 的变化）
5. 重新启动 V1 服务
```

### 8.2 回滚手册

```bash
# 1. 停止 V2
docker compose down

# 2. 清理 V2 数据库
docker compose run --rm postgres psql -U reqradar -d reqradar -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 3. 重建 V2 空 Schema
docker compose run --rm api-service alembic upgrade head

# 4. 恢复 V1 数据库（假设备份文件为 v1_backup.sql）
# 如果 V1 和 V2 共用 PG 实例：先恢复到独立数据库
# 如果 V1 使用 SQLite：直接还原文件

# 5. 重启 V1
docker compose -f docker-compose.v1.yml up -d
```

---

## 9. 迁移验证 SQL

```sql
-- 1. 表级行数校验
SELECT 'V2 cognitive_sessions' AS label, COUNT(*) FROM cognitive_sessions
UNION ALL
SELECT 'V1 migrated tasks', COUNT(*) FROM _migration_id_map WHERE v1_table = 'analysis_tasks';

-- 2. 外键完整性校验
SELECT 'orphan events', COUNT(*) FROM events e
LEFT JOIN cognitive_sessions s ON e.session_id = s.session_id
WHERE s.session_id IS NULL;

SELECT 'orphan checkpoints', COUNT(*) FROM checkpoints c
LEFT JOIN cognitive_sessions s ON c.session_id = s.session_id
WHERE s.session_id IS NULL;

-- 3. L3 知识新鲜度校验
SELECT freshness, COUNT(*) FROM glossary GROUP BY freshness;
SELECT freshness, COUNT(*) FROM constraints GROUP BY freshness;

-- 4. ID 映射完整性
SELECT v1_table, COUNT(*) FROM _migration_id_map GROUP BY v1_table ORDER BY v1_table;
```

---

## 10. 迁移后清理

迁移验证通过后：

```sql
-- 删除临时映射表（保留 7 天用于问题排查）
-- 7 天后执行：
DROP TABLE IF EXISTS _migration_id_map;
```
