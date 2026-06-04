# C-06 数据库迁移计划

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v2.0 |
| 文档定位 | ReqRadar V2 数据库迁移的完整执行计划，为 vibe coding 模式下的 AI Agent 提供表创建顺序、迁移脚本命名规则和种子数据方案 |
| 前置文档 | R-01_SESSION_LIFECYCLE.md、R-03_EVENT_STREAM_SCHEMA.md、R-05_CHECKPOINT_DESIGN.md、M-01_EVIDENCE_MODEL.md、M-03_PROJECT_COGNITIVE_STATE.md、M-04_COGNITIVE_GRAPH_SCHEMA.md、M-02_SEVEN_DIMENSION_FRAMEWORK.md、04_IMPLEMENTATION_ROADMAP.md |
| 核心目标 | 定义 V2 全部新表的创建顺序、Alembic 迁移脚本规范、按 Phase 分组的迁移计划、种子数据、回滚策略 |
| 文档职责 | What & How & When -- 创建什么表、怎么创建、何时创建 |

---

## 2. 总则

### 2.1 迁移管理工具

使用 **Alembic** 管理 PostgreSQL 数据库迁移。Alembic 已在项目中集成（`alembic/env.py` 配置了 async engine + `Base.metadata` autogenerate）。

### 2.2 迁移脚本语言

迁移脚本使用 **英文** 标识符和描述，与 Alembic 自动生成的命名保持一致。脚本内的注释使用中文。

### 2.3 数据库引擎

V2 目标数据库为 **PostgreSQL**（生产环境）。开发环境仍支持 SQLite（仅用于单元测试），但 V2 新增表的 JSONB、EXCLUDE 等高级特性仅限 PostgreSQL。

### 2.4 迁移原则

| 原则 | 说明 |
|------|------|
| V2 全新 Schema | V2 使用独立数据库，不与 V1 共存，所有表从零创建，无需考虑向后兼容或数据迁移 |
| 分阶段迁移 | 按 Phase 逐步创建新表，未到 Phase 不创建 |
| 可回滚 | 每个迁移脚本必须提供完整的 downgrade 方法 |
| 幂等性 | 迁移脚本可重复执行不报错（使用 IF NOT EXISTS 等模式） |

---

## 3. V2 表清单总览

### 3.1 V2 表清单

#### 基础表（Batch 1 创建）

| # | 表名 | 说明 |
|---|------|------|
| 1 | users | 用户表 |
| 2 | projects | 项目表 |
| 3 | revoked_tokens | JWT 吊销表 |
| 4 | user_configs | 用户配置表 |
| 5 | system_configs | 系统配置表 |
| 6 | project_configs | 项目配置表 |
| 7 | report_templates | 报告模板表 |

#### L0/L1 索引表（Batch 2 创建）

| # | 表名 | 来源文档 | 所属 Phase | 所属层 | 说明 |
|---|------|---------|-----------|--------|------|
| 8 | raw_context | 03 §3 | P1 | L0 | 原始上下文元数据指针（MinIO 文件引用） |
| 9 | chunks | 03 §4 | P1 | L1 | 文档 Chunk（需求文档按段落/章节切分） |
| 10 | code_modules | 03 §4 | P1 | L1 | 代码模块/类/函数定义与签名 |
| 11 | code_dependencies | 03 §4 | P1 | L1 | 代码依赖关系（import/调用/继承） |
| 12 | git_commits | 03 §4 | P1 | L1 | Git 提交事实 |
| 13 | requirement_code_links | 03 §4 | P1 | L1 | 需求-代码关联 |

#### L2 核心表（Batch 3 创建）

| # | 表名 | 来源文档 | 所属 Phase | 所属层 | 说明 |
|---|------|---------|-----------|--------|------|
| 14 | cognitive_sessions | R-01 | P1 | L2 | 认知会话 |
| 15 | events | R-03 | P1 | L2 | 事件流，结构化推理链记录 |
| 16 | checkpoints | R-05 | P1 | L2 | 会话快照 |
| 17 | evidence_records | M-01 | P1 | L2 | 证据记录，分析结论的可追溯载体 |
| 18 | evidence_relations | M-01 | P1 | L2 | 证据间关系链 |
| 19 | dimension_results | M-02 | P1 | L2 | 七维度评估结果 |

#### L3-A 知识主表（Batch 4 创建）

| # | 表名 | 来源文档 | 所属 Phase | 所属层 | 说明 |
|---|------|---------|-----------|--------|------|
| 20 | glossary | M-03 | P3 | L3-A | 术语表 |
| 21 | module_profiles | M-03 | P3 | L3-A | 模块画像 |
| 22 | constraints | M-03 | P3 | L3-A | 架构约束 |
| 23 | decisions | M-03 | P3 | L3-A | 决策记录 |
| 24 | risks | M-03 | P3 | L3-A | 风险演化 |
| 25 | risk_evolution | M-03 | P3 | L3-A | 风险演化历史 |
| 26 | risk_mitigations | M-03 | P3 | L3-A | 风险缓解措施 |
| 27 | requirement_lineage | M-03 | P3 | L3-A | 需求谱系 |
| 28 | requirement_relations | M-03 | P3 | L3-A | 需求间关系 |
| 29 | incidents | M-03 | P3 | L3-A | 事故记忆 |
| 30 | knowledge_changelog | M-03 | P3 | L3-A | 知识变更日志（append-only） |
| 31 | verification_log | M-03 | P3 | L3-A | 验证日志 |
| 32 | knowledge_relations | M-04 | P3 | L3-A | 知识图谱关系边 |

#### L3-B 预留表（Batch 6 创建）

| # | 表名 | 来源文档 | 所属 Phase | 所属层 | 说明 |
|---|------|---------|-----------|--------|------|
| 33 | cognitive_patterns | M-03 | P5 | L3-B | 认知模式（Phase 5 预留） |

---

## 4. 表创建顺序（按 FK 依赖排序，6 批）

根据外键依赖关系，V2 全部表按以下 6 批顺序创建。每批内的表无相互 FK 依赖，可并行创建。

### 4.1 依赖关系图

```
Batch 1: 基础表（无 FK 依赖）
  users
  projects
  revoked_tokens ──► users
  user_configs ──► users
  system_configs
  project_configs ──► projects
  report_templates

Batch 2: L0/L1 索引表（依赖 Batch 1）
  raw_context ──► projects
  chunks ──► projects, raw_context
  code_modules ──► projects
  code_dependencies ──► projects, code_modules (自依赖)
  git_commits ──► projects
  requirement_code_links ──► projects, chunks, code_modules

Batch 3: L2 核心表（依赖 Batch 1）
  cognitive_sessions ──► users, projects
  │
  ├── events ──► cognitive_sessions
  ├── checkpoints ──► cognitive_sessions
  ├── evidence_records ──► cognitive_sessions
  ├── dimension_results ──► cognitive_sessions
  │
  └── evidence_relations ──► evidence_records (自依赖)

Batch 4: L3-A 知识主表（依赖 Batch 1）
  glossary ──► projects
  module_profiles ──► projects
  constraints ──► projects
  decisions ──► projects
  risks ──► projects
  requirement_lineage ──► projects
  requirement_relations ──► projects
  incidents ──► projects
  knowledge_changelog ──► (无 FK 到其他 L3 表)
  verification_log ──► projects

Batch 5: L3-A 子表与关系表（依赖 Batch 4）
  risk_evolution ──► risks
  risk_mitigations ──► risks
  knowledge_relations ──► projects, knowledge_relations (自引用)

Batch 6: L3-B 预留表（Phase 5）
  cognitive_patterns ──► projects
```

### 4.2 批次详情

#### Batch 1: 基础表（P1 阶段创建）

| 顺序 | 表名 | FK 依赖 | 说明 |
|------|------|---------|------|
| 1.1 | users | 无 | 用户表，V2 基础表 |
| 1.2 | projects | 无 | 项目表，V2 基础表 |
| 1.3 | revoked_tokens | users(id) | JWT 吊销表 |
| 1.4 | user_configs | users(id) | 用户配置表 |
| 1.5 | system_configs | 无 | 系统配置表 |
| 1.6 | project_configs | projects(id) | 项目配置表 |
| 1.7 | report_templates | 无 | 报告模板表 |

**Batch 1 内部创建顺序**：users -> projects -> revoked_tokens -> user_configs -> system_configs -> project_configs -> report_templates

**Batch 1 DDL（Alembic 迁移脚本 `V2_P1_create_base_tables.py`）：**

```python
def upgrade() -> None:
    # 1.1 users — 用户表
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_users_username", "users", ["username"], unique=True)
    op.create_index("idx_users_email", "users", ["email"], unique=True)

    # 1.2 projects — 项目表
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("repo_path", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_projects_name", "projects", ["name"])

    # 1.3 revoked_tokens — JWT 吊销表
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("jti", sa.String(36), nullable=False, unique=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_revoked_tokens_jti", "revoked_tokens", ["jti"], unique=True)

    # 1.4 user_configs — 用户配置表
    op.create_table(
        "user_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "config_key", name="uq_user_configs_user_key"),
    )
    op.create_index("idx_user_configs_user_id", "user_configs", ["user_id"])

    # 1.5 system_configs — 系统配置表
    op.create_table(
        "system_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("config_key", sa.String(100), nullable=False, unique=True),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_system_configs_key", "system_configs", ["config_key"], unique=True)

    # 1.6 project_configs — 项目配置表
    op.create_table(
        "project_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "config_key", name="uq_project_configs_project_key"),
    )
    op.create_index("idx_project_configs_project_id", "project_configs", ["project_id"])

    # 1.7 report_templates — 报告模板表
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("render_template", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_report_templates_name", "report_templates", ["name"], unique=True)
```

#### Batch 2: L0/L1 索引表（P1 阶段创建）

| 顺序 | 表名 | FK 依赖 | 说明 |
|------|------|---------|------|
| 2.1 | raw_context | projects(id) | L0 原始上下文元数据指针 |
| 2.2 | chunks | projects(id), raw_context(id) | L1 文档 Chunk |
| 2.3 | code_modules | projects(id) | L1 代码模块/类/函数 |
| 2.4 | code_dependencies | projects(id), code_modules(id) x2 | L1 代码依赖关系 |
| 2.5 | git_commits | projects(id) | L1 Git 提交事实 |
| 2.6 | requirement_code_links | projects(id), chunks(id), code_modules(id) | L1 需求-代码关联 |

**Batch 2 内部创建顺序**：raw_context -> chunks -> code_modules -> code_dependencies -> git_commits -> requirement_code_links

**Batch 2 DDL（Alembic 迁移脚本 `V2_P1_l0l1_index_tables.py`）：**

```python
def upgrade() -> None:
    # 2.1 raw_context — L0 原始上下文元数据指针
    op.create_table(
        "raw_context",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),  # document / repo_snapshot / git_history / other
        sa.Column("uri", sa.String(500), nullable=False),  # MinIO 路径
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),  # SHA-256
        sa.Column("source", sa.String(20), nullable=False, server_default="upload"),  # upload / cli / mcp
        sa.Column("superseded_by", sa.UUID(), sa.ForeignKey("raw_context.id"), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_", sa.JSON(), nullable=False, server_default="{}"),
        sa.CheckConstraint("type IN ('document', 'repo_snapshot', 'git_history', 'other')", name="ck_raw_context_type"),
        sa.CheckConstraint("source IN ('upload', 'cli', 'mcp')", name="ck_raw_context_source"),
    )
    op.create_index("idx_raw_context_project", "raw_context", ["project_id", "type"])
    op.create_index("idx_raw_context_hash", "raw_context", ["content_hash"])
    op.create_index("idx_raw_context_superseded", "raw_context", ["superseded_by"])

    # 2.2 chunks — L1 文档 Chunk
    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_context_id", sa.UUID(), sa.ForeignKey("raw_context.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_type", sa.String(20), nullable=False),  # paragraph / section / heading / table / list
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("text_uri", sa.String(500), nullable=True),  # MinIO 大文本引用（>1KB）
        sa.Column("position", sa.Integer(), nullable=False),  # 在原文中的顺序
        sa.Column("offset_start", sa.Integer(), nullable=True),  # 字符偏移
        sa.Column("offset_end", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.String(500), nullable=True),  # 如 "3.2.1 > 3.2 > 3"
        sa.Column("embedding_id", sa.String(100), nullable=True),  # ChromaDB 向量 ID
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("chunk_type IN ('paragraph', 'section', 'heading', 'table', 'list')", name="ck_chunks_type"),
    )
    op.create_index("idx_chunks_project", "chunks", ["project_id", "chunk_type"])
    op.create_index("idx_chunks_raw_context", "chunks", ["raw_context_id"])
    op.create_index("idx_chunks_embedding", "chunks", ["embedding_id"])
    op.create_index("idx_chunks_stale", "chunks", ["project_id", "is_stale"])

    # 2.3 code_modules — L1 代码模块/类/函数
    op.create_table(
        "code_modules",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_type", sa.String(20), nullable=False),  # module / class / function / method
        sa.Column("qualified_name", sa.String(500), nullable=False),  # 如 "reqradar.web.api.auth"
        sa.Column("short_name", sa.String(100), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),  # 函数签名/类定义
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("embedding_id", sa.String(100), nullable=True),  # ChromaDB 向量 ID
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("module_type IN ('module', 'class', 'function', 'method')", name="ck_code_modules_type"),
    )
    op.create_index("idx_code_modules_project", "code_modules", ["project_id", "module_type"])
    op.create_index("idx_code_modules_qualified", "code_modules", ["project_id", "qualified_name"])
    op.create_index("idx_code_modules_file", "code_modules", ["project_id", "file_path"])
    op.create_index("idx_code_modules_embedding", "code_modules", ["embedding_id"])
    op.create_index("idx_code_modules_stale", "code_modules", ["project_id", "is_stale"])

    # 2.4 code_dependencies — L1 代码依赖关系
    op.create_table(
        "code_dependencies",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_module_id", sa.UUID(), sa.ForeignKey("code_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_module_id", sa.UUID(), sa.ForeignKey("code_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dep_type", sa.String(20), nullable=False),  # import / call / inherit / compose
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("dep_type IN ('import', 'call', 'inherit', 'compose')", name="ck_code_deps_type"),
        sa.CheckConstraint("source_module_id != target_module_id", name="ck_code_deps_no_self"),
    )
    op.create_index("idx_code_deps_source", "code_dependencies", ["source_module_id"])
    op.create_index("idx_code_deps_target", "code_dependencies", ["target_module_id"])
    op.create_index("idx_code_deps_project", "code_dependencies", ["project_id", "dep_type"])

    # 2.5 git_commits — L1 Git 提交事实
    op.create_table(
        "git_commits",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_hash", sa.String(40), nullable=False),
        sa.Column("author", sa.String(200), nullable=False),
        sa.Column("author_email", sa.String(200), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("changed_files", sa.JSON(), nullable=False, server_default="[]"),  # [{path, additions, deletions}]
        sa.Column("diff_summary", sa.Text(), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_git_commits_project", "git_commits", ["project_id", "committed_at"])
    op.create_index("idx_git_commits_hash", "git_commits", ["project_id", "commit_hash"], unique=True)
    op.create_index("idx_git_commits_author", "git_commits", ["project_id", "author"])

    # 2.6 requirement_code_links — L1 需求-代码关联
    op.create_table(
        "requirement_code_links",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.UUID(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("code_module_id", sa.UUID(), sa.ForeignKey("code_modules.id", ondelete="CASCADE"), nullable=True),
        sa.Column("link_type", sa.String(20), nullable=False),  # filename_match / annotation / llm_inferred / rule_match
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("evidence", sa.Text(), nullable=True),  # 关联依据描述
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("link_type IN ('filename_match', 'annotation', 'llm_inferred', 'rule_match')", name="ck_req_code_links_type"),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_req_code_links_confidence"),
    )
    op.create_index("idx_req_code_links_project", "requirement_code_links", ["project_id", "link_type"])
    op.create_index("idx_req_code_links_chunk", "requirement_code_links", ["chunk_id"])
    op.create_index("idx_req_code_links_module", "requirement_code_links", ["code_module_id"])
```

#### Batch 3: L2 核心表（P1 阶段创建）

| 顺序 | 表名 | FK 依赖 | 说明 |
|------|------|---------|------|
| 3.1 | cognitive_sessions | projects(id), users(id) | 必须最先创建，其他 L2 表依赖此表 |
| 3.2 | events | cognitive_sessions(session_id) | 事件流，依赖 sessions |
| 3.3 | checkpoints | cognitive_sessions(session_id) | 快照，依赖 sessions |
| 3.4 | evidence_records | cognitive_sessions(id) | 证据记录，依赖 sessions |
| 3.5 | evidence_relations | evidence_records(id) x2 | 证据关系，依赖 evidence_records |
| 3.6 | dimension_results | cognitive_sessions(id) | 维度结果，依赖 sessions |

**Batch 3 内部创建顺序**：cognitive_sessions -> events -> checkpoints -> evidence_records -> evidence_relations -> dimension_results

#### Batch 4: L3-A 知识主表（P3 阶段创建）

| 顺序 | 表名 | FK 依赖 | UNIQUE 约束 |
|------|------|---------|-------------|
| 4.1 | glossary | projects(id) | (project_id, canonical_name) |
| 4.2 | module_profiles | projects(id) | (project_id, module_name) |
| 4.3 | constraints | projects(id) | (project_id, constraint_hash) |
| 4.4 | decisions | projects(id) | (project_id, decision_id) |
| 4.5 | risks | projects(id) | (project_id, canonical_risk_id), (project_id, risk_fingerprint) |
| 4.6 | requirement_lineage | projects(id) | (project_id, requirement_id, version) |
| 4.7 | requirement_relations | projects(id) | (project_id, source_requirement_id, target_requirement_id, relation_type) |
| 4.8 | incidents | projects(id) | (project_id, incident_id) |
| 4.9 | knowledge_changelog | 无 FK 到其他 L3 表 | 无（多态引用 knowledge_type + knowledge_id） |
| 4.10 | verification_log | projects(id) | 无 |

**Batch 4 内部创建顺序**：所有表仅依赖 projects，可按任意顺序创建。建议按上表顺序，便于代码审查。

#### Batch 5: L3-A 子表与关系表（P3 阶段创建，紧接 Batch 4）

| 顺序 | 表名 | FK 依赖 | UNIQUE 约束 |
|------|------|---------|-------------|
| 5.1 | risk_evolution | risks(id) ON DELETE CASCADE | 无 |
| 5.2 | risk_mitigations | risks(id) ON DELETE CASCADE | 无 |
| 5.3 | knowledge_relations | projects(id) ON DELETE CASCADE, knowledge_relations(relation_id) 自引用 | (project_id, source_type, source_id, relation_type, target_type, target_id) |

**Batch 5 内部创建顺序**：risk_evolution -> risk_mitigations -> knowledge_relations

#### Batch 6: L3-B 预留表（P5 阶段创建）

| 顺序 | 表名 | FK 依赖 | UNIQUE 约束 |
|------|------|---------|-------------|
| 6.1 | cognitive_patterns | projects(id) | (project_id, pattern_id) |

---

## 5. 迁移脚本命名规则

### 5.1 命名格式

```
V2_{phase}_{description}.py
```

| 段 | 说明 | 示例 |
|----|------|------|
| `V2` | 固定前缀，标识 V2 迁移 | V2 |
| `{phase}` | 所属 Phase | P1, P3, P5 |
| `{description}` | 小写下划线描述 | create_base_tables, add_l3_knowledge_tables |

### 5.2 完整命名示例

| 脚本名 | Phase | 说明 |
|--------|-------|------|
| `V2_P1_create_base_tables.py` | P1 | 创建基础表（users, projects, 辅助配置表） |
| `V2_P1_l0l1_index_tables.py` | P1 | 创建 L0/L1 索引表 |
| `V2_P1_create_cognitive_sessions.py` | P1 | 创建 cognitive_sessions 表 |
| `V2_P1_create_events.py` | P1 | 创建 events 表 |
| `V2_P1_create_checkpoints.py` | P1 | 创建 checkpoints 表 |
| `V2_P1_create_evidence_tables.py` | P1 | 创建 evidence_records + evidence_relations 表 |
| `V2_P1_create_dimension_results.py` | P1 | 创建 dimension_results 表 |
| `V2_P1_seed_system_configs.py` | P1 | 插入 V2 系统配置种子数据 |
| `V2_P1_seed_default_templates.py` | P1 | 插入默认分析模板种子数据 |
| `V2_P3_create_l3_knowledge_main_tables.py` | P3 | 创建 Batch 4 全部 10 张 L3-A 知识主表 |
| `V2_P3_create_l3_knowledge_sub_tables.py` | P3 | 创建 Batch 5 全部 3 张 L3-A 子表与关系表 |
| `V2_P3_seed_l3_default_configs.py` | P3 | 插入 L3 相关系统配置种子数据 |
| `V2_P5_create_cognitive_patterns.py` | P5 | 创建 cognitive_patterns 表 |

### 5.3 Alembic revision 链

每个脚本的 `revision` 和 `down_revision` 构成有序链：

```
V2_P1_create_base_tables
  │
  ▼
V2_P1_l0l1_index_tables
  │
  ▼
V2_P1_create_cognitive_sessions
  │
  ▼
V2_P1_create_events
  │
  ▼
V2_P1_create_checkpoints
  │
  ▼
V2_P1_create_evidence_tables
  │
  ▼
V2_P1_create_dimension_results
  │
  ▼
V2_P1_seed_system_configs
  │
  ▼
V2_P1_seed_default_templates
  │
  ▼
V2_P3_create_l3_knowledge_main_tables
  │
  ▼
V2_P3_create_l3_knowledge_sub_tables
  │
  ▼
V2_P3_seed_l3_default_configs
  │
  ▼
V2_P5_create_cognitive_patterns
```

---

## 6. 按 Phase 分组的迁移计划

### 6.1 P1: Cognitive Runtime Core（L2 核心表）

**目标**：创建基础表、L0/L1 索引表和 L2 核心表，支撑 CognitiveSession 生命周期、事件流、Checkpoint、Evidence 和七维度评估。

**前置条件**：空数据库，无历史迁移。

#### P1 迁移步骤

| 步骤 | 迁移脚本 | 操作 | 依赖 |
|------|---------|------|------|
| P1-1 | V2_P1_create_base_tables | 创建 users, projects, revoked_tokens, user_configs, system_configs, project_configs, report_templates 表 | 无 |
| P1-2 | V2_P1_l0l1_index_tables | 创建 raw_context, chunks, code_modules, code_dependencies, git_commits, requirement_code_links 表 | P1-1 |
| P1-3 | V2_P1_create_cognitive_sessions | 创建 cognitive_sessions 表 + 7 个索引 | P1-1 |
| P1-4 | V2_P1_create_events | 创建 events 表 + 6 个索引 + 3 个约束 | P1-3 |
| P1-5 | V2_P1_create_checkpoints | 创建 checkpoints 表 + 7 个索引 + 5 个约束 | P1-3 |
| P1-6 | V2_P1_create_evidence_tables | 创建 evidence_records + evidence_relations 表 + 全部索引和约束 | P1-3 |
| P1-7 | V2_P1_create_dimension_results | 创建 dimension_results 表 + 索引和约束 | P1-3 |
| P1-8 | V2_P1_seed_system_configs | 插入 V2 系统配置种子数据 | P1-1 |
| P1-9 | V2_P1_seed_default_templates | 插入默认分析模板种子数据 | P1-1 |

#### P1-3: cognitive_sessions 表 DDL

```python
def upgrade() -> None:
    op.create_table(
        "cognitive_sessions",
        sa.Column("session_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="CREATED"),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("last_checkpoint_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_reasoning_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 索引
    op.create_index("idx_sessions_project_id", "cognitive_sessions", ["project_id", sa.text("created_at DESC")])
    op.create_index("idx_sessions_user_id", "cognitive_sessions", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_sessions_status", "cognitive_sessions", ["status"],
                     postgresql_where=sa.text("status IN ('RUNNING','CHECKPOINTING','WAITING_INPUT','CANCELLING')"))
    op.create_index("idx_sessions_recoverable", "cognitive_sessions", ["status", "last_checkpoint_version"],
                     postgresql_where=sa.text("status IN ('FAILED','TIMEOUT') AND last_checkpoint_version > 0"))
    op.create_index("idx_sessions_updated_at", "cognitive_sessions", ["updated_at"])
    op.create_index("idx_sessions_config_strategy", "cognitive_sessions",
                     [sa.text("(config->>'context_strategy')")])
    op.create_index("idx_sessions_state_phase", "cognitive_sessions",
                     [sa.text("(state->>'current_phase')")])
```

#### P1-4: events 表 DDL

```python
def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("event_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("event_level", sa.String(15), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("producer", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "sequence", name="uq_events_session_sequence"),
        sa.CheckConstraint("event_type IN ('SESSION_CREATED','SESSION_STARTED','SESSION_CHECKPOINTED','SESSION_COMPLETED','SESSION_FAILED','SESSION_CANCELLING','SESSION_CANCELLED','SESSION_TIMEOUT','SESSION_ABORTED','SESSION_WAITING_INPUT','SESSION_RESUMED','STEP_STARTED','STEP_COMPLETED','TOOL_INVOKED','TOOL_RETURNED','TOOL_RETRY','TOOL_TIMEOUT','TOOL_PERMISSION_DENIED','TOOL_CHECKPOINT_FAILED','CONTEXT_COLLECTED','CONTEXT_SCORED','EVIDENCE_ADDED','DIMENSION_CHANGED')", name="ck_events_event_type"),
        sa.CheckConstraint("event_level IN ('session','reasoning','cognitive')", name="ck_events_event_level"),
    )
    op.create_index("idx_events_session_sequence", "events", ["session_id", "sequence"])
    op.create_index("idx_events_session_type", "events", ["session_id", "event_type"])
    op.create_index("idx_events_session_level", "events", ["session_id", "event_level"])
    op.create_index("idx_events_session_timestamp", "events", ["session_id", "timestamp"])
    op.create_index("idx_events_payload_step", "events", [sa.text("(payload->>'step')")],
                     postgresql_where=sa.text("payload ? 'step'"))
    op.create_index("idx_events_payload_dimension", "events", [sa.text("(payload->>'dimension')")],
                     postgresql_where=sa.text("payload ? 'dimension'"))
```

#### P1-5: checkpoints 表 DDL

```python
def upgrade() -> None:
    op.create_table(
        "checkpoints",
        sa.Column("checkpoint_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="cognitive-rt"),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("state_summary", sa.JSON(), nullable=False),
        sa.Column("diff", sa.JSON(), nullable=False, server_default='{"added":[],"removed":[],"modified":[]}'),
        sa.Column("hot_state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("full_state_uri", sa.String(512), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("session_id", "version", name="uq_checkpoint_session_version"),
        sa.CheckConstraint("type IN ('STEP_COMPLETE','TOOL_PRE','TOOL_POST','MANUAL','PERIODIC')", name="ck_checkpoint_type"),
        sa.CheckConstraint("version >= 1", name="ck_version_positive"),
        sa.CheckConstraint("pg_column_size(hot_state) <= 1048576", name="ck_hot_state_size"),
        sa.CheckConstraint("previous_version IS NULL OR previous_version < version", name="ck_previous_version"),
    )
    op.create_index("idx_checkpoints_session_version", "checkpoints", ["session_id", sa.text("version DESC")])
    op.create_index("idx_checkpoints_session_type", "checkpoints", ["session_id", "type"])
    op.create_index("idx_checkpoints_session_created", "checkpoints", ["session_id", sa.text("created_at DESC")])
    op.create_index("idx_checkpoints_state_phase", "checkpoints", [sa.text("(state_summary->>'current_phase')")])
    op.create_index("idx_checkpoints_state_step", "checkpoints", [sa.text("((state_summary->>'current_step')::int)")])
    op.create_index("idx_checkpoints_meta_tool", "checkpoints", [sa.text("(metadata->>'tool_name')")])
    op.create_index("idx_checkpoints_created_at", "checkpoints", ["created_at"])
```

#### P1-6: evidence_records + evidence_relations 表 DDL

```python
def upgrade() -> None:
    # evidence_records
    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="discovered"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence_level", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("confidence_basis", sa.Text(), server_default=""),
        sa.Column("source_context_kind", sa.String(32), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("source_display_name", sa.String(256), server_default=""),
        sa.Column("content", sa.String(200), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("dimension_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column("verified_by", sa.String(64), server_default=""),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name="ck_evidence_confidence_score"),
        sa.CheckConstraint("type IN ('code_evidence','requirement_ref','architecture_doc','git_history','memory_ref','tool_output','inference','constraint','risk_indicator','verification_result')", name="ck_evidence_type"),
        sa.CheckConstraint("status IN ('discovered','verified','challenged','superseded','deprecated')", name="ck_evidence_status"),
        sa.CheckConstraint("confidence_level IN ('low','medium','high','very_high')", name="ck_evidence_confidence_level"),
        sa.CheckConstraint("source_context_kind IN ('SOURCE_CODE','REQUIREMENT','ARCH_DOC','GIT_HISTORY','MEMORY','INFERRED_KNOWLEDGE')", name="ck_evidence_context_kind"),
    )
    op.create_index("idx_evidence_session", "evidence_records", ["session_id"])
    op.create_index("idx_evidence_session_type", "evidence_records", ["session_id", "type"])
    op.create_index("idx_evidence_session_status", "evidence_records", ["session_id", "status"])
    op.create_index("idx_evidence_dimension", "evidence_records", ["dimension_refs"], postgresql_using="gin")
    op.create_index("idx_evidence_confidence", "evidence_records", ["session_id", "confidence_score"])
    op.create_index("idx_evidence_source_uri", "evidence_records", ["source_uri"])
    op.create_index("idx_evidence_created", "evidence_records", ["created_at"])
    op.create_index("idx_evidence_detail", "evidence_records", ["detail"], postgresql_using="gin")

    # evidence_relations
    op.create_table(
        "evidence_relations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_evidence_id", sa.String(32), sa.ForeignKey("evidence_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_evidence_id", sa.String(32), sa.ForeignKey("evidence_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("rationale", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_evidence_relation_confidence"),
        sa.CheckConstraint("relation_type IN ('SUPPORTS','CONTRADICTS','DERIVED_FROM','SUPERSEDES','CORROBORATES')", name="ck_evidence_relation_type"),
        sa.CheckConstraint("source_evidence_id != target_evidence_id", name="no_self_relation"),
    )
    op.create_index("idx_evidence_relation_session", "evidence_relations", ["session_id"])
    op.create_index("idx_evidence_relation_source", "evidence_relations", ["source_evidence_id"])
    op.create_index("idx_evidence_relation_target", "evidence_relations", ["target_evidence_id"])
    op.create_index("idx_evidence_relation_type", "evidence_relations", ["session_id", "relation_type"])
    op.create_index("idx_evidence_relation_unique", "evidence_relations",
                     ["source_evidence_id", "target_evidence_id", "relation_type"], unique=True)
```

#### P1-7: dimension_results 表 DDL

```python
def upgrade() -> None:
    op.create_table(
        "dimension_results",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="none"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), server_default=""),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "dimension_id", name="uq_dimension_session_id"),
        sa.CheckConstraint("status IN ('not_started','in_progress','completed')", name="ck_dimension_status"),
        sa.CheckConstraint("risk_level IN ('none','low','medium','high','critical')", name="ck_dimension_risk_level"),
    )
    op.create_index("idx_dimension_session_id", "dimension_results", ["session_id"])
    op.create_index("idx_dimension_status", "dimension_results", ["status"])
    op.create_index("idx_dimension_risk_level", "dimension_results", ["risk_level"])
    op.create_index("idx_dimension_dimension_id", "dimension_results", ["dimension_id"])
```

### 6.2 P3: L3 Knowledge Layer（L3-A 知识表）

**目标**：创建 L3-A 事实层知识表，支撑项目认知状态的持久化和跨 Session 知识积累。

**前置条件**：P1 已完成，基础表和 cognitive_sessions 表已创建。

#### P3 迁移步骤

| 步骤 | 迁移脚本 | 操作 | 依赖 |
|------|---------|------|------|
| P3-1 | V2_P3_create_l3_knowledge_main_tables | 创建 Batch 4 全部 10 张 L3-A 知识主表 | P1-1 |
| P3-2 | V2_P3_create_l3_knowledge_sub_tables | 创建 Batch 5 全部 3 张 L3-A 子表与关系表 | P3-1 |
| P3-3 | V2_P3_seed_l3_default_configs | 插入 L3 相关系统配置种子数据 | P1-1 |

#### P3-1: L3-A 知识主表 DDL 概要

10 张表共享以下治理元数据列（除 knowledge_changelog 外）：

```python
# 所有 L3-A 知识主表共享的治理元数据列
L3_GOVERNANCE_COLUMNS = [
    sa.Column("freshness", sa.String(20), nullable=False, server_default="active"),
    sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"),
    sa.Column("verification_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("source_session_count", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("human_verified", sa.Boolean(), nullable=False, server_default="false"),
    sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("superseded_by", sa.String(64), nullable=True),
    sa.Column("source_session_ids", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
]
```

各表特有列：

| 表名 | 特有列 | UNIQUE 约束 |
|------|--------|-------------|
| glossary | canonical_name, aliases(JSONB), definition, category, project_id | (project_id, canonical_name) |
| module_profiles | module_name, description, responsibilities(JSONB), dependencies(JSONB), complexity_metrics(JSONB), last_analyzed_at, analysis_count, project_id | (project_id, module_name) |
| constraints | constraint_id, constraint_type, scope, description, severity, constraint_hash, rationale, project_id | (project_id, constraint_hash) |
| decisions | decision_id, title, context, rationale, alternatives(JSONB), status, decision_type, project_id | (project_id, decision_id) |
| risks | canonical_risk_id, title, description, risk_category, severity, affected_modules(JSONB), indicators(JSONB), risk_fingerprint, status, project_id | (project_id, canonical_risk_id), (project_id, risk_fingerprint) |
| requirement_lineage | requirement_id, version, title, content, source_document, section, priority, status, project_id | (project_id, requirement_id, version) |
| requirement_relations | source_requirement_id, target_requirement_id, relation_type, strength, rationale, project_id | (project_id, source_requirement_id, target_requirement_id, relation_type) |
| incidents | incident_id, title, description, severity, affected_modules(JSONB), root_cause, resolution, occurred_at, resolved_at, project_id | (project_id, incident_id) |
| knowledge_changelog | knowledge_type, knowledge_id, change_type, previous_state(JSONB), change_description, changed_by, change_source, project_id | 无（append-only） |
| verification_log | verification_type, target_type, target_id, result, verifier, notes, verified_at, project_id | 无 |

#### P3-2: L3-A 子表与关系表 DDL 概要

| 表名 | 列 | FK | UNIQUE |
|------|-----|-----|--------|
| risk_evolution | risk_id(FK), from_severity, to_severity, trigger, description, changed_at | risks(id) ON DELETE CASCADE | 无 |
| risk_mitigations | risk_id(FK), mitigation_type, description, status, effectiveness_score, implemented_at | risks(id) ON DELETE CASCADE | 无 |
| knowledge_relations | relation_id, project_id(FK), source_type, source_id, relation_type, target_type, target_id, confidence, rationale, superseded_by(FK 自引用), created_at | projects(id) ON DELETE CASCADE, knowledge_relations(relation_id) | (project_id, source_type, source_id, relation_type, target_type, target_id) |

knowledge_relations 表的 CHECK 约束和 EXCLUDE 约束：

```python
sa.CheckConstraint(
    "source_type IN ('glossary','module_profile','constraint','decision','risk','requirement','incident','pattern')",
    name="ck_kr_source_type",
),
sa.CheckConstraint(
    "target_type IN ('glossary','module_profile','constraint','decision','risk','requirement','incident','pattern')",
    name="ck_kr_target_type",
),
sa.CheckConstraint(
    "relation_type IN ('DEPENDS_ON','IMPACTS','CONFLICTS_WITH','EVOLVES_FROM','MITIGATES','VIOLATES','DERIVED_FROM','CORROBORATES','SUPERSEDES')",
    name="ck_kr_relation_type",
),
sa.CheckConstraint(
    "NOT (source_type = target_type AND source_id = target_id)",
    name="ck_kr_no_self_reference",
),
# 对称关系（CONFLICTS_WITH, CORROBORATES）的 EXCLUDE 约束
# 使用 PostgreSQL EXCLUDE 约束防止反向重复
```

knowledge_relations 表的索引：

```python
op.create_index("idx_kr_project", "knowledge_relations", ["project_id"])
op.create_index("idx_kr_source", "knowledge_relations", ["source_type", "source_id"])
op.create_index("idx_kr_target", "knowledge_relations", ["target_type", "target_id"])
op.create_index("idx_kr_relation_type", "knowledge_relations", ["relation_type"])
# Context Pipeline 注入用部分索引
op.create_index("idx_kr_context_inject", "knowledge_relations",
                 ["project_id", "source_type", "relation_type"],
                 postgresql_where=sa.text("relation_type IN ('DEPENDS_ON','IMPACTS','CONFLICTS_WITH')"))
```

### 6.3 P5: L3-B Pattern Layer（预留）

**目标**：创建 cognitive_patterns 表，为 Phase 5 的模式识别功能预留。

**前置条件**：P3 已完成。

#### P5 迁移步骤

| 步骤 | 迁移脚本 | 操作 | 依赖 |
|------|---------|------|------|
| P5-1 | V2_P5_create_cognitive_patterns | 创建 cognitive_patterns 表 | P1-1 |

#### P5-1: cognitive_patterns 表 DDL 概要

| 列 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| pattern_id | VARCHAR(64) | NOT NULL | 模式标识 |
| project_id | UUID | FK projects(id) | 所属项目 |
| pattern_type | VARCHAR(32) | NOT NULL | 模式类型 |
| name | VARCHAR(255) | NOT NULL | 模式名称 |
| description | TEXT | NOT NULL | 模式描述 |
| indicators | JSONB | NOT NULL DEFAULT '[]' | 模式指标 |
| evidence_refs | JSONB | NOT NULL DEFAULT '[]' | 证据引用 |
| confidence_score | FLOAT | NOT NULL DEFAULT 0.5 | 置信度 |
| ... | ... | ... | 含治理元数据列 |
| UNIQUE | | (project_id, pattern_id) | |

---

## 7. 种子数据

### 7.1 V2 系统配置种子数据（P1）

| config_key | config_value | value_type | description |
|------------|-------------|------------|-------------|
| session.max_execution_time | 1800 | integer | Session 最大执行时间（秒） |
| session.checkpoint_interval | 300 | integer | 自动 Checkpoint 间隔（秒） |
| session.checkpoint_enabled | true | boolean | 是否启用自动 Checkpoint |
| session.checkpoint_degradation | lenient | string | Checkpoint 失败降级策略 |
| session.context_budget_default | 128000 | integer | 默认 Token 预算 |
| session.max_reasoning_steps | 50 | integer | 最大推理步骤数 |
| session.max_tool_calls | 100 | integer | 最大工具调用数 |
| session.step_timeout | 120 | integer | 单步推理超时（秒） |
| session.cancellation_timeout | 60 | integer | 取消清理超时（秒） |
| session.llm_timeout | 60 | integer | LLM 调用超时（秒） |
| session.llm_max_retries | 3 | integer | LLM 调用最大重试次数 |
| session.recovery_max_rollback | 3 | integer | 恢复时最大回退版本数 |
| session.auto_cleanup_days | 90 | integer | 终态 Session 自动清理天数 |
| event.stream_maxlen | 10000 | integer | Redis Streams 每个 Stream 最大消息数 |
| event.persist_batch_size | 50 | integer | 持久化批量写入大小 |
| event.persist_flush_interval | 1.0 | float | 持久化定时刷新间隔（秒） |
| event.payload_max_size_bytes | 10240 | integer | 单个事件 payload 最大字节数 |
| checkpoint.hot_state_max_bytes | 1048576 | integer | 热状态 JSONB 最大字节数 |
| checkpoint.archive_days | 30 | integer | 终态 Session Checkpoint 归档天数 |
| checkpoint.delete_days | 90 | integer | 终态 Session Checkpoint 删除天数 |
| checkpoint.max_active | 20 | integer | 活跃 Session 保留的最大 Checkpoint 数 |
| evidence.max_per_session | 500 | integer | 单个 Session 最大 Evidence 数量 |
| evidence.auto_verify_enabled | true | boolean | 是否启用自动验证 |
| evidence.min_confidence_for_l3 | 0.5 | float | 沉淀到 L3 的最低置信度阈值 |

### 7.2 默认分析模板种子数据（P1）

| name | description | definition | render_template | is_default |
|------|-------------|------------|-----------------|------------|
| 标准七维度分析 | 覆盖理解、影响、风险、变更、决策、证据、验证七个维度的标准分析模板 | (YAML 定义，包含七维度配置) | (Jinja2 模板) | true |
| 快速风险评估 | 仅聚焦风险和影响两个维度，适用于快速扫描 | (YAML 定义，仅 risk + impact) | (Jinja2 模板) | false |
| 需求完整性检查 | 聚焦理解和证据维度，适用于需求文档质量评估 | (YAML 定义，仅 understanding + evidence) | (Jinja2 模板) | false |

### 7.3 L3 相关系统配置种子数据（P3）

| config_key | config_value | value_type | description |
|------------|-------------|------------|-------------|
| l3.confidence_decay_weekly | 0.05 | float | 超过 60 天未验证的知识每周衰减值 |
| l3.confidence_floor | 0.1 | float | 知识置信度衰减下限 |
| l3.auto_sediment_on_complete | true | boolean | Session 完成时是否自动触发 L3 沉淀 |
| l3.human_verify_boost | 0.9 | float | 人工验证后的置信度直接提升值 |
| l3.cross_session_threshold_low | 0.3 | float | 单 Session 产生知识的初始置信度 |
| l3.cross_session_threshold_mid | 0.6 | float | 2-3 个 Session 产生知识的置信度 |
| l3.cross_session_threshold_high | 0.8 | float | 4+ 个 Session 产生知识的置信度 |

---

## 8. 回滚策略

### 8.1 总则

每个 Alembic 迁移脚本的 `downgrade()` 方法必须完整实现，确保可以安全回退到迁移前的状态。

### 8.2 回滚规则

| 规则 | 说明 |
|------|------|
| 表删除顺序与创建顺序相反 | 先删除子表（有 FK 依赖的表），再删除父表 |
| 索引随表删除 | DROP TABLE 自动删除关联索引 |
| 种子数据需清除 | downgrade 中 DELETE 种子数据，避免重复插入 |

### 8.3 各迁移脚本的 downgrade 要求

| 迁移脚本 | downgrade 操作 |
|---------|---------------|
| V2_P1_create_base_tables | DROP TABLE project_configs, report_templates, user_configs, system_configs, revoked_tokens, projects, users CASCADE |
| V2_P1_l0l1_index_tables | DROP TABLE requirement_code_links, git_commits, code_dependencies, code_modules, chunks, raw_context |
| V2_P1_create_cognitive_sessions | DROP TABLE cognitive_sessions CASCADE |
| V2_P1_create_events | DROP TABLE events |
| V2_P1_create_checkpoints | DROP TABLE checkpoints |
| V2_P1_create_evidence_tables | DROP TABLE evidence_relations, DROP TABLE evidence_records |
| V2_P1_create_dimension_results | DROP TABLE dimension_results |
| V2_P1_seed_system_configs | DELETE FROM system_configs WHERE config_key LIKE 'session.%' OR config_key LIKE 'event.%' OR config_key LIKE 'checkpoint.%' OR config_key LIKE 'evidence.%' |
| V2_P1_seed_default_templates | DELETE FROM report_templates WHERE name IN ('标准七维度分析', '快速风险评估', '需求完整性检查') |
| V2_P3_create_l3_knowledge_main_tables | DROP TABLE verification_log, knowledge_changelog, incidents, requirement_relations, requirement_lineage, risks, decisions, constraints, module_profiles, glossary |
| V2_P3_create_l3_knowledge_sub_tables | DROP TABLE knowledge_relations, risk_mitigations, risk_evolution |
| V2_P3_seed_l3_default_configs | DELETE FROM system_configs WHERE config_key LIKE 'l3.%' |
| V2_P5_create_cognitive_patterns | DROP TABLE cognitive_patterns |

### 8.4 回滚验证

回滚后需验证：

| 验证项 | 方法 |
|--------|------|
| V2 表已删除 | `SELECT tablename FROM pg_tables WHERE tablename IN ('cognitive_sessions', 'events', ...)` 返回空 |
| 种子数据已清除 | `SELECT count(*) FROM system_configs WHERE config_key LIKE 'session.%'` 返回 0 |

---

## 9. 新增表的注册规则

### 9.1 SQLAlchemy ORM 模型注册

新增表的 SQLAlchemy ORM 模型必须在 `reqradar/web/models.py` 中定义，并继承 `Base`。Alembic 的 `env.py` 通过 `from reqradar.web.models import *` 自动发现所有模型。

**注册步骤**：

1. 在 `models.py` 中新增 ORM 模型类
2. 运行 `alembic revision --autogenerate -m "V2_P1_create_xxx"` 生成迁移脚本
3. 检查自动生成的脚本，补充 CHECK 约束、部分索引等 autogenerate 无法处理的 DDL
4. 运行 `alembic upgrade head` 应用迁移

### 9.2 命名规范

| 元素 | 规范 | 示例 |
|------|------|------|
| ORM 类名 | PascalCase | CognitiveSession, EvidenceRecord |
| __tablename__ | snake_case | cognitive_sessions, evidence_records |
| 列名 | snake_case | session_id, confidence_score |
| 索引名 | idx_{table}_{columns} | idx_sessions_project_id |
| 唯一约束名 | uq_{table}_{columns} | uq_events_session_sequence |
| 检查约束名 | ck_{table}_{column} | ck_events_event_type |
| 外键名 | fk_{table}_{column} | fk_sessions_project_id |

### 9.3 V2 模型文件组织

V2 使用全新 Schema，所有模型直接在 `reqradar/web/models.py` 中定义。如模型数量增多导致文件过长，可按功能模块拆分为独立文件（如 `models_cognitive.py`、`models_evidence.py`、`models_knowledge.py`），但仅为文件组织目的，非 V1 兼容需要。

拆分时需确保所有模型文件导入同一个 `Base` 实例：

```python
# reqradar/web/database.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

```python
# reqradar/web/models.py
from reqradar.web.database import Base
from reqradar.web.models_cognitive import *  # noqa: F401,F403
from reqradar.web.models_evidence import *  # noqa: F401,F403
from reqradar.web.models_knowledge import *  # noqa: F401,F403
```

### 9.4 新增表 Checklist

每次新增表时，需确认以下事项：

| # | 检查项 | 说明 |
|---|--------|------|
| 1 | ORM 模型已定义 | 在 models.py 或拆分模块中创建，继承 Base |
| 2 | __tablename__ 已设置 | 使用 snake_case 复数形式 |
| 3 | PK 已定义 | 使用 UUID 或 Integer 自增 |
| 4 | FK 已定义 | 使用 sa.ForeignKey，指定 ondelete |
| 5 | UNIQUE 约束已定义 | 在 __table_args__ 中声明 |
| 6 | CHECK 约束已定义 | 枚举值、范围校验等 |
| 7 | 索引已定义 | 查询热点字段建索引 |
| 8 | created_at/updated_at 已定义 | TIMESTAMPTZ，默认 NOW() |
| 9 | Alembic 迁移脚本已生成 | 包含 upgrade + downgrade |
| 10 | downgrade 已验证 | 执行 downgrade 后数据库状态正确 |
| 11 | 种子数据脚本已编写 | 如需初始数据 |
| 12 | 文档已更新 | 更新本文件的表清单 |

---

## 附录 A: L3 知识治理元数据列定义

所有 L3-A 知识主表（除 knowledge_changelog）共享以下治理元数据列：

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| freshness | VARCHAR(20) | NOT NULL, DEFAULT 'active' | 新鲜度状态：active / historical / superseded / deprecated / stale / conflicted |
| confidence_score | FLOAT | NOT NULL, DEFAULT 0.5 | 置信度评分 0.0-1.0 |
| verification_count | INTEGER | NOT NULL, DEFAULT 0 | 验证次数 |
| source_session_count | INTEGER | NOT NULL, DEFAULT 1 | 来源 Session 数量 |
| human_verified | BOOLEAN | NOT NULL, DEFAULT false | 是否经过人工验证 |
| last_verified_at | TIMESTAMPTZ | NULLABLE | 最近验证时间 |
| superseded_by | VARCHAR(64) | NULLABLE | 替代此条记录的新记录 ID |
| source_session_ids | JSONB | NOT NULL, DEFAULT '[]' | 来源 Session ID 列表 |
| evidence_refs | JSONB | NOT NULL, DEFAULT '[]' | 证据引用列表 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 最后更新时间 |

**FreshnessStatus 枚举值**：

| 值 | 含义 | 触发条件 |
|----|------|---------|
| active | 当前有效 | 新创建或最近验证通过 |
| historical | 历史记录 | 超过 60 天未验证且未衰减到 stale |
| superseded | 已被替代 | 新记录通过 SUPERSEDES 关系替代 |
| deprecated | 已废弃 | 人工标记或严重冲突 |
| stale | 过期 | 超过 60 天未验证，置信度衰减到下限 |
| conflicted | 存在冲突 | 存在未解决的 CONFLICTS_WITH 关系 |

## 附录 B: knowledge_relations 关系类型

| 关系类型 | 含义 | 对称性 | Context Pipeline 注入 |
|---------|------|--------|---------------------|
| DEPENDS_ON | 依赖关系 | 非对称 | 是 |
| IMPACTS | 影响关系 | 非对称 | 是 |
| CONFLICTS_WITH | 冲突关系 | 对称 | 是 |
| EVOLVES_FROM | 演化来源 | 非对称 | 否 |
| MITIGATES | 缓解关系 | 非对称 | 否 |
| VIOLATES | 违反关系 | 非对称 | 否 |
| DERIVED_FROM | 派生关系 | 非对称 | 否 |
| CORROBORATES | 印证关系 | 对称 | 否 |
| SUPERSEDES | 替代关系 | 非对称 | 否 |

**对称关系约束**：CONFLICTS_WITH 和 CORROBORATES 为对称关系，A->B 和 B->A 视为同一条关系。使用 PostgreSQL EXCLUDE 约束防止反向重复。
