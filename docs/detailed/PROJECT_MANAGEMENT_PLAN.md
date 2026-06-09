# 项目管理模块规划

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | 项目管理模块的完整实施规划，覆盖项目 CRUD、三种创建场景、代码索引、项目画像、需求文档摄取 |
| 前置文档 | C-06 Batch 1（projects 表定义）、INGESTION_SERVICE_PLAN.md（数据摄取层）、03 §3-4（L0/L1 模型）、C-04（端点注册规范） |
| 核心目标 | 让用户能创建项目、导入代码/文档，为认知运行时提供数据基础 |
| 与 ingestion-service 的关系 | 项目管理层是 ingestion-service 的**上游调用方**，创建项目后触发摄取流程 |

---

## 2. 架构定位

### 2.1 在认知飞轮中的位置

```
用户操作（前端）
  │
  ├─ 创建项目（三种场景）
  │    ├─ git clone
  │    ├─ 本地目录指定
  │    └─ 压缩包上传
  │
  ├─ 上传需求文档
  │
  ▼
项目管理层（本次规划）  ◀── BFF(api-service) 路由
  │
  ├─ 项目 CRUD（PG 持久化）
  ├─ 代码索引构建（调用 ingestion-service）
  ├─ 需求文档摄取（调用 ingestion-service）
  └─ 项目画像构建（调用 LLM + 代码索引数据）
  │
  ▼
数据摄取层（ingestion-service）
  │
  ├─ L0 原始文件存储
  ├─ L1 结构化事实（chunks / code_modules / git_commits）
  └─ ChromaDB 向量嵌入
  │
  ▼
认知分析层（cognitive-rt Context Pipeline）
  │
  └─ 消费 L1 数据 → 推理 → L2/L3
```

### 2.2 服务归属

项目管理功能的端点放在 **BFF(api-service)** 中，具体业务逻辑委托给下游服务：

| 功能 | 端点所在服务 | 业务逻辑所在服务 |
|------|------------|----------------|
| 项目 CRUD | BFF | index-service（PG 持久化） |
| 代码索引构建 | BFF | ingestion-service |
| 需求文档摄取 | BFF | ingestion-service |
| 项目画像构建 | BFF | cognitive-rt（调用 LLM） |

---

## 3. 三种项目创建场景

### 3.1 场景一：git clone

```
用户输入：Git 仓库 URL + 可选凭据
  │
  ├─ 1. BFF 创建项目记录（PG）
  ├─ 2. git clone 到本地目录（asyncio.to_thread）
  ├─ 3. 调用 ingestion-service /ingest/code（AST 解析 + 向量化）
  ├─ 4. 调用 ingestion-service /ingest/git（Git 历史提取）
  ├─ 5. 调用 cognitive-rt 构建项目画像
  └─ 6. 返回项目详情（含代码索引状态）
```

### 3.2 场景二：本地目录指定

```
用户输入：本地目录路径
  │
  ├─ 1. 校验目录存在性 + 可读性
  ├─ 2. BFF 创建项目记录（PG），repo_path = 目录路径
  ├─ 3. 调用 ingestion-service /ingest/code（AST 解析 + 向量化）
  ├─ 4. 如果目录有 .git → 调用 ingestion-service /ingest/git
  ├─ 5. 调用 cognitive-rt 构建项目画像
  └─ 6. 返回项目详情
```

### 3.3 场景三：压缩包上传

```
用户输入：ZIP/TAR.GZ 文件上传
  │
  ├─ 1. 接收上传文件，保存到临时目录
  ├─ 2. 解压到 data/projects/{project_id}/source/
  ├─ 3. BFF 创建项目记录（PG），repo_path = 解压目录
  ├─ 4. 调用 ingestion-service /ingest/code
  ├─ 5. 如果解压后有 .git → 调用 ingestion-service /ingest/git
  ├─ 6. 调用 cognitive-rt 构建项目画像
  └─ 7. 返回项目详情
```

---

## 4. 端点设计

### 4.1 项目 CRUD 端点（新增到 C-04）

| # | 端点 | 方法 | 说明 | 认证 |
|---|------|------|------|------|
| 1 | `/api/v2/projects` | POST | 创建项目（三种场景统一入口） | Required |
| 2 | `/api/v2/projects` | GET | 查询项目列表 | Required |
| 3 | `/api/v2/projects/{id}` | GET | 查询项目详情 | Required |
| 4 | `/api/v2/projects/{id}` | PUT | 更新项目信息 | Required |
| 5 | `/api/v2/projects/{id}` | DELETE | 删除项目（软删除） | Required |
| 6 | `/api/v2/projects/{id}/index` | POST | 触发代码索引构建 | Required |
| 7 | `/api/v2/projects/{id}/ingest` | POST | 上传需求文档并摄取 | Required |
| 8 | `/api/v2/projects/{id}/profile` | GET | 查询项目画像 | Required |
| 9 | `/api/v2/projects/{id}/profile/rebuild` | POST | 重新构建项目画像 | Required |

### 4.2 创建项目请求体

```json
{
  "name": "Cool Agent",
  "description": "个人全场景信息管理自动化闭环",
  "source_type": "git",
  "source_config": {
    "git_url": "https://github.com/user/repo.git",
    "git_branch": "main"
  }
}
```

**source_type 取值**：

| source_type | source_config 字段 | 说明 |
|-------------|-------------------|------|
| `git` | `git_url`, `git_branch`(可选) | git clone |
| `local` | `local_path` | 本地目录指定 |
| `upload` | （文件在 multipart/form-data 中） | 压缩包上传 |
| `empty` | （无） | 空项目，后续手动添加 |

### 4.3 创建项目响应体

```json
{
  "id": "uuid",
  "name": "Cool Agent",
  "description": "...",
  "status": "indexing",
  "source_type": "git",
  "repo_path": "data/projects/{id}/source",
  "created_at": "2026-06-08T10:00:00Z",
  "index_progress": {
    "code_modules": 0,
    "git_commits": 0,
    "status": "pending"
  }
}
```

---

## 5. 数据库表

### 5.1 已有表（C-06 Batch 1）

**projects** 表已定义：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 主键 |
| name | VARCHAR(100) | 项目名称 |
| description | TEXT | 项目描述 |
| repo_path | VARCHAR(500) | 本地仓库路径 |
| is_active | BOOLEAN | 是否激活 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

### 5.2 需要补充的字段

| 字段 | 类型 | 说明 |
|------|------|------|
| source_type | VARCHAR(20) | git / local / upload / empty |
| source_config | JSON | 原始来源配置（git_url、branch 等） |
| status | VARCHAR(20) | creating / indexing / ready / error |
| profile_data | JSON | 项目画像数据（技术栈、架构风格等） |
| indexed_at | TIMESTAMPTZ | 代码索引完成时间 |
| last_sync_at | TIMESTAMPTZ | 最后同步时间（git pull） |

### 5.3 迁移策略

不新建表，在已有 `projects` 表上 ALTER TABLE 补充字段：

```python
# alembic 迁移脚本
op.add_column("projects", sa.Column("source_type", sa.String(20), nullable=True))
op.add_column("projects", sa.Column("source_config", sa.JSON(), nullable=True))
op.add_column("projects", sa.Column("status", sa.String(20), nullable=False, server_default="creating"))
op.add_column("projects", sa.Column("profile_data", sa.JSON(), nullable=True))
op.add_column("projects", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
op.add_column("projects", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
```

---

## 6. 代码索引构建流程

```
POST /api/v2/projects/{id}/index
  │
  ├─ 1. 校验项目存在 + repo_path 有效
  │
  ├─ 2. 调用 ingestion-service /ingest/code
  │     → 扫描 repo_path 下所有 .py 文件
  │     → AST 解析提取类/函数/签名
  │     → 向量化写入 ChromaDB code 集合
  │     → L1 写入 PG code_modules 表
  │
  ├─ 3. 如果 repo_path 有 .git
  │     → 调用 ingestion-service /ingest/git
  │     → git log 提取提交历史
  │     → L1 写入 PG git_commits 表
  │
  ├─ 4. 更新项目 status = "ready"
  │     更新项目 indexed_at = now()
  │
  └─ 5. 返回索引结果
        → { code_modules: N, git_commits: M, status: "ready" }
```

---

## 7. 项目画像构建

### 7.1 触发时机

| 时机 | 说明 |
|------|------|
| 项目创建后自动触发 | 代码索引完成后自动构建 |
| 用户手动触发 | `POST /api/v2/projects/{id}/profile/rebuild` |
| 代码索引更新后 | git pull 后重新索引时触发 |

### 7.2 构建流程

```
POST /api/v2/projects/{id}/profile/rebuild
  │
  ├─ 1. 从 PG 读取 code_modules（文件统计、目录结构、核心文件）
  ├─ 2. 读取关键配置文件（pyproject.toml / requirements.txt / package.json）
  ├─ 3. 调用 LLM 生成项目画像
  │     → 技术栈识别
  │     → 架构风格判断
  │     → 模块职责摘要
  │     → 核心依赖列表
  ├─ 4. 保存画像到 projects.profile_data（JSON）
  └─ 5. 返回项目画像
```

### 7.3 已有可复用资产

| 资产 | 文件 | 说明 |
|------|------|------|
| 项目画像算法 | `cognitive_rt/cognition/project_profile.py` | `step_build_project_profile()` 已实现完整逻辑 |
| 画像 Prompt | `cognitive_rt/cognition/prompts/project_profile.py` | `PROJECT_PROFILE_PROMPT` |
| 画像 Schema | `cognitive_rt/cognition/schemas.py` | `PROJECT_PROFILE_SCHEMA` |

---

## 8. 需求文档摄取

### 8.1 流程

```
POST /api/v2/projects/{id}/ingest（multipart/form-data）
  │
  ├─ 1. 接收上传文件
  ├─ 2. 调用 ingestion-service /ingest/document
  │     → markitdown 解析为 Markdown
  │     → 按标题/段落切分为 chunk
  │     → 向量化写入 ChromaDB requirements 集合
  │     → L1 写入 PG chunks 表
  │     → L0 保存原始文件到 data/l0/{project_id}/
  ├─ 3. 返回摄取结果
  └─ 4. 可选：触发项目画像重新构建（如果需求文档影响画像）
```

### 8.2 支持格式

| 格式 | markitdown 支持 | 说明 |
|------|----------------|------|
| Markdown (.md) | ✅ | 原生支持 |
| PDF (.pdf) | ✅ | `pip install 'markitdown[pdf]'` |
| Word (.docx) | ✅ | `pip install 'markitdown[docx]'` |
| 纯文本 (.txt) | ✅ | 原生支持 |
| HTML (.html) | ✅ | `pip install 'markitdown[html]'` |

---

## 9. 任务分解

### 第一波：项目 CRUD（可并行）

| 任务 | 文件 | 说明 |
|------|------|------|
| PRJ-1 | `kernel/models.py` | projects ORM 补充字段（source_type / source_config / status / profile_data / indexed_at / last_sync_at） |
| PRJ-2 | `alembic/versions/` | ALTER TABLE 迁移脚本 |
| PRJ-3 | `services/api/app.py` | BFF 补项目 CRUD 端点（POST/GET/PUT/DELETE /projects） |

### 第二波：项目创建场景（依赖第一波）

| 任务 | 文件 | 说明 |
|------|------|------|
| PRJ-4 | `services/api/app.py` | git clone 场景：git clone → 调用 ingestion-service |
| PRJ-5 | `services/api/app.py` | 本地目录场景：校验目录 → 调用 ingestion-service |
| PRJ-6 | `services/api/app.py` | 压缩包上传场景：接收文件 → 解压 → 调用 ingestion-service |

### 第三波：索引 + 画像 + 需求（依赖第二波）

| 任务 | 文件 | 说明 |
|------|------|------|
| PRJ-7 | `services/api/app.py` | 代码索引端点：`POST /projects/{id}/index` → 调用 ingestion-service |
| PRJ-8 | `services/api/app.py` | 需求文档摄取端点：`POST /projects/{id}/ingest` → 调用 ingestion-service |
| PRJ-9 | `services/api/app.py` | 项目画像端点：`GET/POST /projects/{id}/profile` → 调用 cognitive-rt |

### 第四波：集成 + 测试

| 任务 | 文件 | 说明 |
|------|------|------|
| PRJ-10 | `tests/unit/services/test_project_api.py` | 项目 CRUD + 创建场景测试 |
| PRJ-11 | 端到端验证 | 创建项目 → 代码索引 → 需求摄取 → 画像构建 → Session 分析 |

---

## 10. 执行顺序与依赖关系

```
第一波（并行）：
  PRJ-1 (ORM) + PRJ-2 (迁移) + PRJ-3 (CRUD 端点)
        │
第二波（并行，依赖第一波）：
  PRJ-4 (git clone) + PRJ-5 (本地目录) + PRJ-6 (压缩包)
        │
第三波（并行，依赖第二波）：
  PRJ-7 (代码索引) + PRJ-8 (需求摄取) + PRJ-9 (项目画像)
        │
第四波：
  PRJ-10 (测试) → PRJ-11 (端到端验证)
```

**与 ingestion-service 的依赖**：
- PRJ-4/5/6 依赖 ingestion-service 的 `/ingest/code` 和 `/ingest/git` 端点
- PRJ-7 依赖 ingestion-service 的 `/ingest/code` 端点
- PRJ-8 依赖 ingestion-service 的 `/ingest/document` 端点
- PRJ-9 依赖 PRJ-7 完成后的 code_modules 数据

**建议执行顺序**：先完成 ingestion-service（ING-1~10），再开始项目管理（PRJ-1~11）。

---

## 11. 验收标准

### 11.1 功能验收

- [ ] 三种场景创建项目：git clone / 本地目录 / 压缩包上传，全链路成功
- [ ] 创建项目后自动触发代码索引构建
- [ ] 代码索引完成后自动构建项目画像
- [ ] 上传需求文档 → markitdown 解析 → 切分 → 向量化 → PG 写入
- [ ] 项目画像包含：技术栈、架构风格、模块职责、核心依赖
- [ ] 项目状态流转：creating → indexing → ready（或 error）
- [ ] Context Pipeline 能消费项目的真实 L1 数据

### 11.2 编码规范验收

- [ ] ruff check 0 errors
- [ ] pytest 全部通过
- [ ] 异常带 cause 链
- [ ] 端点错误格式符合 I-01 §2.2

---

## 12. 与 ingestion-service 的接口约定

项目管理层调用 ingestion-service 的端点：

| 项目管理层调用 | ingestion-service 端点 | 说明 |
|--------------|----------------------|------|
| git clone 后调用 | `POST /internal/v2/ingest/code` | body: `{project_id, repo_path}` |
| git clone 后调用 | `POST /internal/v2/ingest/git` | body: `{project_id, repo_path}` |
| 需求文档上传后调用 | `POST /internal/v2/ingest/document` | multipart: `{project_id, file}` |
| 本地目录指定后调用 | `POST /internal/v2/ingest/code` | body: `{project_id, repo_path}` |
| 压缩包解压后调用 | `POST /internal/v2/ingest/code` | body: `{project_id, repo_path}` |

---

## 13. 关键风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| git clone 耗时长 | 用户体验差 | 异步执行 + 状态轮询（creating → indexing → ready） |
| 大仓库代码索引慢 | 阻塞请求 | 限制扫描文件数（默认 1000），超出跳过 + 告警 |
| 压缩包解压炸弹 | 磁盘溢出 | 限制解压后大小 500MB，文件数 10000 |
| git clone 需要凭据 | 认证失败 | 支持 HTTPS token / SSH key（从环境变量读取） |
| LLM 画像构建失败 | 画像为空 | 降级为规则提取（文件统计 + 目录结构），不依赖 LLM |
| ingestion-service 未启动 | 索引失败 | 返回 503 + 提示启动 ingestion-service |

---

## 14. 完整用户旅程

```
1. 用户打开前端 → DashboardPage
2. 点击"创建项目" → AnalysisCreatePage
3. 选择创建方式：
   a. 输入 Git URL → 点击"创建"
   b. 输入本地路径 → 点击"创建"
   c. 上传 ZIP 文件 → 点击"创建"
4. 前端轮询项目状态（creating → indexing → ready）
5. 项目就绪后，用户点击"上传需求文档"
6. 选择 PDF/DOCX/MD 文件 → 上传
7. 前端轮询摄取状态
8. 摄取完成后，用户点击"启动分析"
9. Session 创建 → 启动 → 推理（消费真实 L1 数据）
10. 推理完成后查看报告 + 认知仪表盘
```
