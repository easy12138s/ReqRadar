# ingestion-service 重构规划

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ingestion-service 的完整实施规划，覆盖架构设计、技术选型、任务分解、验收标准 |
| 前置文档 | I-01 §7（服务间 API 契约）、03 §3-4（L0/L1 认知资产模型）、C-06 Batch 2（数据库表定义）、02 §6.6（服务职责）、ADR-009（Ingestion 独立服务） |
| 核心目标 | 将原始文档/代码/Git 历史转化为 L1 结构化事实，供 Context Pipeline 消费 |

---

## 2. 架构定位

### 2.1 在认知飞轮中的位置

```
用户上传文件 / 代码仓库 / Git 历史
    │
    ▼
  L0: Raw Context（档案馆）
    │  MinIO 原始文件 + PG 元数据指针
    │
    │  ◀── ingestion-service（本次规划）
    ▼
  L1: Structured Facts（图书馆）
    │  PG 结构化元数据 + ChromaDB 向量嵌入
    │
    │  ◀── cognitive-rt Context Pipeline 消费
    ▼
  L2: Analysis Records → L3: Persistent Knowledge
```

### 2.2 服务职责（来源：02 §6.6）

| 属性 | 说明 |
|------|------|
| 职责 | 文档解析、代码分析、向量化、元数据提取 |
| 暴露 | HTTP API（内部）+ 异步任务 |
| 依赖 | PostgreSQL, ChromaDB, 本地文件系统（MinIO 降级） |
| 调用方 | cognitive-rt（触发摄取）、BFF（用户上传） |
| 被调方 | index-service（L1 事实写入，I-01 §7） |

### 2.3 调用拓扑

```
BFF(api-service) ──HTTP──► ingestion-service（用户上传文档）
cognitive-rt     ──HTTP──► ingestion-service（触发代码/Git 摄取）
ingestion-service ──HTTP──► index-service（L1 事实写入）
ingestion-service ──直接──► ChromaDB（向量写入）
ingestion-service ──直接──► 本地文件系统（L0 原始文件存储）
```

---

## 3. 技术选型

### 3.1 文档解析：markitdown

| 项目 | 说明 |
|------|------|
| 包名 | `markitdown`（微软 AutoGen 团队开源） |
| 安装 | `pip install 'markitdown[pdf,docx,pptx,xlsx,html]'` |
| 支持格式 | PDF、DOCX、PPTX、XLSX、HTML、Markdown、纯文本、图片（OCR）、CSV、JSON、XML、EPUB |
| API | `MarkItDown().convert(file_path)` → `result.text_content`（Markdown 文本） |
| 优势 | 一个 API 覆盖所有格式，无需自己写解析器 |

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("requirements.pdf")
markdown_text = result.text_content
```

### 3.2 代码解析：Python AST（内置）

| 项目 | 说明 |
|------|------|
| 模块 | `ast`（Python 标准库） |
| 提取内容 | 类名、函数名、签名、文档字符串、行号范围 |
| 局限 | 仅支持 Python 语法，其他语言暂不支持（MVP 阶段） |

### 3.3 Git 解析：subprocess + git log（内置）

| 项目 | 说明 |
|------|------|
| 模块 | `subprocess`（Python 标准库） |
| 提取内容 | commit_hash、author、message、changed_files、numstat |
| 格式 | `git log --pretty=format:... --numstat` |

### 3.4 向量化：ChromaDB 内置 ONNX 模型

**V1 经验教训**：

| V1 问题 | 根因 | V2 解决方案 |
|---------|------|------------|
| 模型太大 | `sentence-transformers` 依赖链（torch ~2GB） | 默认使用 ChromaDB 内置 `ONNXMiniLM_L6_V2`（~80MB，无 torch） |
| 首次启动慢 | 模型加载 30-60 秒 | 内置 ONNX 秒级启动 |
| 下载失败 | HuggingFace 国内访问不稳定 | 内置 ONNX 零下载，永远可用 |

**三级降级策略**：

```
第一级：用户显式指定模型（EMBEDDING_MODEL=xxx）
  │  需要 sentence-transformers，可能需要下载
  │  失败 ↓
第二级：ChromaDB 内置 ONNXMiniLM_L6_V2（默认）
  │  零下载，秒启动，英文为主但中文可用
  │  失败 ↓
第三级：ChromaDB 自动默认（None）
```

**配置**：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `EMBEDDING_MODEL` | `default` | `default` = 内置 ONNX；其他值 = SentenceTransformer 模型名 |

### 3.5 存储：本地文件系统（MinIO 降级）

| 层 | 存储引擎 | 说明 |
|----|---------|------|
| L0 原始文件 | 本地文件系统 | `data/l0/{project_id}/{filename}`，后续迁移到 MinIO |
| L1 元数据 | PostgreSQL | chunks / code_modules / git_commits 等 6 张表 |
| L1 向量 | ChromaDB | requirements 集合 + code 集合 |

---

## 4. 模块架构

```
services/ingestion/
  ├── app.py                      # FastAPI 入口 + 端点
  ├── Dockerfile                  # Docker 镜像
  └── requirements.txt            # 依赖

reqradar/ingestion/
  ├── __init__.py
  ├── parsers/
  │   ├── __init__.py
  │   ├── document_parser.py      # markitdown 封装
  │   ├── code_parser.py          # Python AST 解析
  │   └── git_parser.py           # git log 解析
  ├── chunking/
  │   ├── __init__.py
  │   └── chunker.py              # Markdown → 结构化 chunk
  └── vectorizer.py               # ChromaDB 向量化
```

---

## 5. 端点设计

### 5.1 端点清单（来源：I-01 §7 + MVP 扩展）

| # | 端点 | 方法 | 说明 | MVP |
|---|------|------|------|-----|
| 1 | `/internal/v2/ingest/document` | POST | 上传文档 → 解析 → 切分 → 向量化 | ✅ |
| 2 | `/internal/v2/ingest/code` | POST | 扫描代码目录 → AST 解析 → 向量化 | ✅ |
| 3 | `/internal/v2/ingest/git` | POST | 扫描 Git 仓库 → 提交历史 → 写入 | ✅ |
| 4 | `/internal/v2/l0/raw-context` | POST | 注册 L0 原始上下文元数据 | ✅ |
| 5 | `/internal/v2/l1/chunks` | POST | 批量写入 Chunk（I-01 §7.2） | ✅ |
| 6 | `/internal/v2/l1/code-modules` | POST | 批量写入代码模块（I-01 §7.3） | ✅ |
| 7 | `/internal/v2/l1/git-commits` | POST | 批量写入 Git 提交（I-01 §7.4） | ✅ |
| 8 | `/health` | GET | 健康检查 | ✅ |

**说明**：端点 1-3 是 MVP 新增的"一键摄取"端点，内部串联 L0 注册 + 解析 + L1 写入 + 向量化。端点 4-7 是 I-01 §7 定义的原子端点，供 index-service 调用。

### 5.2 一键文档摄取流程

```
POST /internal/v2/ingest/document
  │
  ├─ 1. 保存原始文件到 L0（本地文件系统）
  │     → data/l0/{project_id}/{timestamp}_{filename}
  │     → 注册 raw_context 元数据到 PG
  │
  ├─ 2. markitdown 解析
  │     → Markdown 文本
  │
  ├─ 3. Markdown 切分
  │     → 按 # 标题切分为 chunk 列表
  │     → 每个 chunk 带 section_path / position / offset
  │
  ├─ 4. 向量化
  │     → ChromaDB requirements 集合写入
  │     → 返回 embedding_id 列表
  │
  ├─ 5. L1 写入 PG
  │     → INSERT chunks 表
  │
  └─ 6. 返回结果
        → { raw_context_id, chunks_count, embedding_ids }
```

---

## 6. 数据库表（来源：C-06 Batch 2）

### 6.1 L0 表

**raw_context**：原始上下文元数据指针

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 主键 |
| project_id | UUID FK | 关联项目 |
| type | VARCHAR(30) | document / repo_snapshot / git_history / other |
| uri | VARCHAR(500) | 本地文件路径或 MinIO URI |
| original_filename | VARCHAR(255) | 原始文件名 |
| size_bytes | BIGINT | 文件大小 |
| content_hash | VARCHAR(64) | SHA-256 hex（去重用） |
| source | VARCHAR(20) | upload / cli / mcp |
| superseded_by | UUID FK | 自引用（新版本指向） |
| ingested_at | TIMESTAMPTZ | 摄取时间 |
| metadata_ | JSON | 扩展元数据 |

### 6.2 L1 表

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| chunks | 文档 Chunk | chunk_type, content, section_path, embedding_id, position |
| code_modules | 代码模块 | module_type, qualified_name, file_path, signature, docstring, embedding_id |
| code_dependencies | 代码依赖 | source_module_id, target_module_id, dep_type |
| git_commits | Git 提交 | commit_hash, author, message, changed_files(JSON) |
| requirement_code_links | 需求-代码关联 | chunk_id, code_module_id, link_type, confidence |

---

## 7. 已有可复用资产

| 资产 | 文件 | 复用方式 |
|------|------|---------|
| ChromaDB 向量存储 | `index_svc/vector_store.py` | 直接复用 `ChromaVectorStore`，三级降级策略已内置 |
| 数据库引擎工厂 | `kernel/database.py` | `create_engine()` + `create_session_factory()` |
| ORM 模型 | `kernel/models.py` | 确认/补充 6 张 L0/L1 表的 ORM 定义 |
| Internal-API-Key | `infrastructure/internal_auth.py` | 直接复用中间件 |
| 错误格式 | I-01 §2.2 | `{"error": {"code": "...", "message": "..."}}` |

---

## 8. 任务分解

### 第一波：基础设施（可并行）

| 任务 | 文件 | 说明 | 工作量 |
|------|------|------|--------|
| ING-1 | `kernel/models.py` | 确认/补充 6 张 L0/L1 ORM 模型 | 小 |
| ING-2 | `alembic/versions/` | 确认/创建 L0/L1 表迁移脚本 | 小 |
| ING-3 | `services/ingestion/` | 创建服务骨架：Dockerfile + app.py + requirements.txt | 小 |
| ING-4 | `reqradar/ingestion/` | 创建模块目录结构 + `__init__.py` | 小 |

### 第二波：解析器（可并行）

| 任务 | 文件 | 说明 | 工作量 |
|------|------|------|--------|
| ING-5 | `parsers/document_parser.py` | markitdown 封装：文件路径/字节流 → Markdown | 中 |
| ING-6 | `parsers/code_parser.py` | Python AST 解析：类/函数/签名/文档字符串 | 中 |
| ING-7 | `parsers/git_parser.py` | git log 解析：提交/作者/变更文件/numstat | 中 |
| ING-8 | `chunking/chunker.py` | Markdown 切分：按标题/段落切分，保留 section_path | 中 |

### 第三波：向量化 + 服务端点（依赖第二波）

| 任务 | 文件 | 说明 | 工作量 |
|------|------|------|--------|
| ING-9 | `vectorizer.py` | 向量化模块：复用 ChromaVectorStore，环境变量控制模型 | 中 |
| ING-10 | `services/ingestion/app.py` | 端点组装：L0 注册 + 解析 + 切分 + 向量化 + L1 写入 | 大 |

### 第四波：集成 + Context Source 接通（依赖第三波）

| 任务 | 文件 | 说明 | 工作量 |
|------|------|------|--------|
| ING-11 | `services/index/app.py` | index-service 补 L1 写入端点（被调用方） | 中 |
| ING-12 | `context_sources.py` | 5 个 ContextSource 从 index-service 查询真实 L1 数据 | 大 |
| ING-13 | `docker-compose.yml` | 添加 ingestion-service 服务定义 | 小 |

### 第五波：测试 + 验证

| 任务 | 文件 | 说明 | 工作量 |
|------|------|------|--------|
| ING-14 | `tests/unit/ingestion/` | 解析器单元测试 | 中 |
| ING-15 | `tests/unit/services/test_ingestion_service.py` | HTTP 端点测试 | 中 |
| ING-16 | 端到端验证 | 上传文档 → 摄取 → Pipeline 消费 → 推理使用真实数据 | 大 |

---

## 9. 执行顺序与依赖关系

```
第一波（并行）：
  ING-1 (ORM) + ING-2 (迁移) + ING-3 (服务骨架) + ING-4 (目录结构)
        │
第二波（并行，依赖第一波）：
  ING-5 (文档解析) + ING-6 (代码解析) + ING-7 (Git 解析) + ING-8 (切分)
        │
第三波（依赖第二波）：
  ING-9 (向量化) → ING-10 (端点组装)
        │
第四波（并行，依赖第三波）：
  ING-11 (index 端点) + ING-12 (ContextSource) + ING-13 (Docker)
        │
第五波：
  ING-14 (测试) + ING-15 (端点测试) → ING-16 (端到端验证)
```

---

## 10. 验收标准

### 10.1 功能验收

- [ ] 上传 Markdown 文档 → 解析 → 切分 → 向量化 → PG 写入，全链路成功
- [ ] 上传 PDF 文档 → markitdown 解析 → 全链路成功
- [ ] 扫描 Python 代码目录 → AST 解析 → 类/函数提取 → 向量化 → PG 写入
- [ ] 扫描 Git 仓库 → 提交历史提取 → PG 写入
- [ ] Context Pipeline 的 CodeGraphSource / VectorResultSource / GitHistorySource 返回真实 L1 数据
- [ ] 向量化默认使用 ONNX 模型，零下载秒启动
- [ ] 显式配置 `EMBEDDING_MODEL=BAAI/bge-small-zh` 时使用中文模型

### 10.2 编码规范验收

- [ ] ruff check 0 errors
- [ ] pytest 全部通过
- [ ] 异常带 cause 链
- [ ] 日志用 `logging.getLogger`，无 f-string
- [ ] Pydantic 字段有 `Field(description="中文描述")`
- [ ] 端点错误格式符合 I-01 §2.2

### 10.3 性能验收

- [ ] 100KB Markdown 文档摄取 < 10 秒（含向量化）
- [ ] 1MB 代码目录扫描 < 30 秒
- [ ] 1000 条 Git 提交解析 < 15 秒
- [ ] ONNX 模型首次加载 < 5 秒

---

## 11. MVP 范围裁剪

| 完整版 | MVP 版 | 裁剪理由 |
|--------|--------|---------|
| MinIO 存储 | 本地文件系统 | 不引入新依赖 |
| PDF/DOCX/PPTX/XLSX/HTML | markitdown 全格式 | markitdown 一个包搞定 |
| Celery 异步任务队列 | 同步处理（asyncio.to_thread） | 简化架构 |
| Python + JS + Go AST | 仅 Python AST | MVP 聚焦 |
| 代码依赖图分析 | 暂不实现 | 复杂度高 |
| 需求-代码关联（LLM 推断） | 暂不实现 | 依赖 LLM 调用 |
| 全量重建索引 | 仅增量新增 | MVP 不需要 |
| 多语言 AST | 仅 Python | MVP 聚焦 |

---

## 12. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./reqradar_dev.db` | PostgreSQL 连接串 |
| `CHROMADB_PATH` | `.reqradar/vectorstore` | ChromaDB 持久化目录 |
| `EMBEDDING_MODEL` | `default` | `default` = 内置 ONNX；其他 = SentenceTransformer 模型名 |
| `L0_STORAGE_PATH` | `data/l0` | L0 原始文件存储目录 |
| `INTERNAL_API_KEY` | （从 .env 读取） | 服务间认证 Key |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## 13. 关键风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| markitdown 依赖冲突 | 安装失败 | 按需安装格式支持（`pip install 'markitdown[pdf]'`），不全量安装 |
| ChromaDB 版本兼容 | 索引格式不兼容 | `vector_store.py` 已有 `_check_index_compatibility` 检查 |
| 大文件 OOM | 内存溢出 | 限制单文件 50MB，超出拒绝 + 日志告警 |
| Git 仓库不存在 | subprocess 报错 | 检查 `.git` 目录存在性，不存在时跳过 + info 日志 |
| ONNX 模型加载失败 | 向量化不可用 | 三级降级策略（见 §3.4） |
| L1 数据量过大 | PG 写入慢 | 批量 INSERT（`executemany`），单次最多 1000 条 |
