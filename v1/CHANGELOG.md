# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-05-09

### Added

- 零配置启动：`pip install reqradar` → `reqradar serve` 直接可用，不再因默认 secret key 崩溃
- 启动横幅：显示版本号、Web UI/API 地址、默认管理员账号、LLM API Key 和密钥提示
- Embedding 模型注册表：支持 4 种模型，Docker 通过 `EMBEDDING_MODEL` 构建参数切换
- `python-dotenv` 支持：自动加载 `.env` 和 `~/.reqradar/.env`
- 跨平台部署脚本：`scripts/deploy.sh`（Linux/macOS）+ `scripts/deploy.ps1`（Windows）
- 轻量级 embedding 模型选项：`BAAI/bge-small-zh`（95MB）和 `BAAI/bge-base-zh`（390MB）
- 多语言 embedding 模型：`BAAI/bge-m3`（100+ 语言支持）
- Docker healthcheck `start-period: 60s` 为 embedding 模型加载留出时间

### Changed

- `load_config()` 无配置文件时返回全默认值并记录 debug 日志
- `_validate_critical_settings` 从 `raise ValueError` 改为 `warnings.warn`
- `app.py` lifespan 中默认密钥检查从 `raise RuntimeError` 改为 `logger.warning`
- Windows `ALLOWED_LOCAL_PREFIXES` 动态包含所有驱动器号和 `USERPROFILE`

### Fixed

- 无 `.reqradar.yaml` 时 `reqradar serve` 因 secret key 校验直接崩溃
- CJK 兼容象形文字在标题分割中不被识别的问题

### Removed

- 前端 i18n 框架，所有 `t()` 调用替换为硬编码中文

## [0.7.0] - 2026-05-06

### Added

- **ReAct Agent 重构**：单循环 CoT 引导架构，替代旧双循环模式
- **记忆进化**：分析后自动触发记忆自演化（`MemoryEvolutionConfig`）
- **Web UI 全面重设计**：深色主题、AppShell 布局、Dashboard 仪表盘
- **SSE Chatback 流式对话**：实时 token 显示、`<think>` 标签折叠、意图分类
- **报告视图重设计**：固定头部 + 滚动内容 + 固定底部追问面板
- **需求预处理引擎**：多文件上传（PDF/DOCX/PPTX/XLSX/HTML/图片/EPUB），LLM 合并为结构化需求文档
- **API 端点新增**：
  - `/api/requirements`：需求文档 CRUD + 预处理提交
  - `/api/evidence`：证据链管理
  - `/api/users`：用户管理（列表/角色/删除）
  - `/api/synonyms`：同义词映射 CRUD
- **报告版本管理**：版本创建/列表/回滚/对比，版本数上限控制
- **LLM 连通性缓存**（5min TTL）+ 分析/聊天前自动验证 + 测试连接端点
- **LiteLLM 统一后端**：替代自定义 OpenAI/Ollama 客户端，支持 100+ 模型接口
- **Microsoft MarkItDown**：统一文档加载器（替代 pdfplumber/python-docx 各自为政）
- **Git 提交历史索引**：`SearchGitHistoryTool` 语义搜索提交记录
- **Docker 多阶段构建**：`docker/entrypoint.sh` 自动生成配置 + 安全加固
- **前端构建产物打入 wheel/sdist**

### Changed

- `run_react_analysis` 单循环架构：Agent → Tool → Observation → CoT → 维度追踪 → 终止判定
- 前端从玻璃拟物风格改为扁平深色主题，统一颜色变量
- `docker-compose.yml` 迁移至 `docker/` 子目录，支持 `EMBEDDING_MODEL` 构建参数
- `ChromaVectorStore` 新增 `collection_name` 参数，支持多集合索引
- 分析提交前端重构：Tab 切换（文本/文件/预处理需求）
- 所有 60+ 前后端类型对齐

### Fixed

- 批量修复 8 轮：类型对齐、模板管理、WebSocket 重连、鉴权、项目画像、LLM 配置、死代码清理
- `RiskBadge` 在 `risk_level` 为 `unknown` 字符串时崩溃
- `task.id.slice` 崩溃和提交按钮防重复点击
- `UnboundLocalError` in `get_analysis`
- 首次启动缺少种子管理员用户
- Docker 镜像中 curl 不可用导致 healthcheck 失败

### Security

- Docker 容器以非 root `appuser` 运行
- 敏感文件过滤模式（`SensitiveFileFilter` + `PathSandbox`）

## [0.5.0] - 2026-04-24

### Added

- ReAct Agent 执行模式（AnalysisRunnerV2）：迭代工具调用 + 7 维度追踪 + 终止判定
- Chatback 对话式追问：意图分类 + 上下文恢复 + 单轮/多轮对话
- 报告版本管理：版本创建/列表/回滚/对比，版本数上限控制
- 同义词映射 CRUD：业务术语 ↔ 代码术语，按项目/优先级/来源管理
- 报告模板自定义：YAML 定义 + Jinja2 渲染模板，DB 存储
- 三级配置优先级：User > Project > System > YAML > 代码默认值
- LLM 调用审计日志（llm_call_logs 表）
- TaskStatus / ChangeStatus 枚举替代字符串字面量
- WebSocket 并发广播（asyncio.gather）

### Security

- JWT 密钥支持 `${ENV_VAR}` 环境变量引用，默认密钥生产环境触发警告
- CORS 生产模式默认限制为 localhost，debug 模式允许 `*`
- 文件上传扩展名白名单
- WebSocket 订阅前校验任务归属

### Changed

- AnalysisRunnerV2._execute_agent 拆分为 _init_agent / _init_tools / _load_template / _save_report
- 数据库连接池配置（pool_size / max_overflow / pool_pre_ping），SQLite 保持 WAL + pragma
- get_db 依赖从全局可变状态改为 app.state.session_factory（向后兼容）
- auto_create_tables 默认关闭，推荐 Alembic 迁移
- 前端启用 TypeScript strict 模式
- ruff 配置增加 SIM/RUF 规则 + isort known-first-party
- mypy 配置增加 ignore_missing_imports + exclude
- pre-commit 增加 ruff-format hook + sqlalchemy stubs

## [0.4.0] - 2026-04-23

### Added

- Web 模块：基于 FastAPI + SQLite + JWT 的后端 API 和 React + Ant Design 前端
- CLI 命令 `reqradar serve`：启动 Web 服务（默认 0.0.0.0:8000）
- CLI 命令 `reqradar createsuperuser`：创建管理员账号
- REST API：注册/登录、项目 CRUD、分析任务提交/进度/重试、报告导出、知识库只读查询
- WebSocket 实时进度推送
- 项目级 CodeGraph + VectorStore 缓存（ProjectStore）
- 异步分析调度器（AnalysisRunner + Semaphore 并发控制）
- 服务启动时自动恢复 running 状态任务为 failed
- `/health` 和 `/api/metrics` 端点
- Docker 部署配置（Dockerfile + docker-compose.yml）
- 前端 React SPA：登录/注册、项目管理、分析提交与进度、报告查看
- 前端代码分割（React.lazy + Suspense）
- 前端中文界面

### Changed

- `AnalysisContext` 等 17 个 dataclass 迁移为 Pydantic `BaseModel`
- `Scheduler.run()` 新增 `on_step_start` / `on_step_complete` 回调参数
- `report.py` 中 5 处 `__dict__` 替换为 `model_dump()`
- 密码哈希从 passlib 切换为直接使用 bcrypt（兼容 bcrypt 4.1+）
- `Config` 新增 `WebConfig` 子配置

## [0.3.0] - 2026-04-22

### Added

- Tool-use loop: LLM can invoke 9 analysis tools across multiple rounds (code search, module query, contributor analysis, etc.)
- `ToolRegistry`: tool registration, schema aggregation, and execution dispatch
- `ToolCallTracker`: dedup, round counting, and token budget management for tool calls
- `BaseTool` + `ToolResult` data model for tool abstraction
- 9 analysis tools: search_code, search_requirements, list_modules, get_contributors, read_file, read_module_summary, get_project_profile, get_terminology, get_dependencies
- `complete_with_tools()` method on OpenAIClient for tool_use protocol
- Dual-layer report design: Decision Summary layer + Technical Support layer
- `DecisionSummary` / `DecisionSummaryItem` dataclasses for decision-level output
- `EvidenceItem` dataclass for evidence chain tracking
- `ImpactDomain` dataclass for inferred impact domain tracking
- `executive_summary`, `technical_summary`, `decision_highlights` fields in `GeneratedContent`
- `decision_summary`, `evidence_items`, `impact_domains` fields in `DeepAnalysis` and `ANALYZE_SCHEMA`
- Three-dimension quality indicators: process completion / content completeness / evidence support
- Impact scope upgraded from module count to "code hits + inferred impact domains"
- API key validation in `OpenAIClient._build_headers()` with fail-fast empty key detection

### Changed

- `ANALYZE_PROMPT` requires decision summary, evidence items, and impact domains output
- `GENERATE_PROMPT` explicitly instructs to organize (not re-analyze) into dual-layer content
- `step_generate()` maps new GeneratedContent fields (executive_summary, technical_summary, decision_highlights)
- `step_analyze()` propagates decision_summary to AnalysisContext
- `content_confidence` tightened to require substantive generated content or decision summary
- Report template fully rewritten as dual-layer Jinja2 template
- CLI quality overview replaced with three-dimension rows
- ChromaDB empty metadata normalized to `None` for compatibility

## [0.2.0] - 2026-04-15

### Added

- Document loader framework: `DocumentLoader` ABC, `LoadedDocument`, `LoaderRegistry`
- TextLoader: migrated from CLI, supports .md/.txt/.rst with GBK fallback
- PDFLoader: pdfplumber-based, optional dependency (`pip install pdfplumber`)
- DocxLoader: python-docx-based, optional dependency (`pip install python-docx`)
- ImageLoader: LLM vision integration for UI screenshots (.png/.jpg/.jpeg/.gif/.bmp/.webp)
- ChatLoader: Feishu JSON + generic CSV chat record parsing
- `VisionConfig`: independent vision LLM configuration block (provider/model/api_key/base_url)
- `MemoryConfig`: project memory configuration (enabled/storage_path)
- `LoaderConfig`: loader configuration (chunk_size/chunk_overlap/format toggles)
- `MemoryManager`: per-project memory system (terminology/team/analysis_history)
  - Auto-accumulates terminology extracted from analysis
  - Auto-records team members from Git contributors
  - Persists analysis history (capped at 50 records)
  - Terminology injection into step_extract prompt
  - Post-generate hook updates memory after each analysis
- `complete_vision()` method on OpenAIClient for image understanding
- `create_vision_client()` factory function
- `VisionNotConfiguredError`: clear error when vision is needed but not configured
- `LoaderException` exception class
- CLI `index` command refactored to use LoaderRegistry (supports all file types)

### Changed

- `AnalysisContext` now includes `memory_data` field for project memory injection
- `step_extract` injects known project terminology into LLM prompt
- `analyze` command loads memory before pipeline and updates it after
- `.reqradar.yaml.example` updated with vision, memory, and loader config sections

### Removed

- `infrastructure/errors.py`: dead code, superseded by `core/exceptions.py`

## [0.1.0] - 2026-04-14

### Added

- Initial MVP release of ReqRadar
- CLI commands: `reqradar index` and `reqradar analyze`
- Python code parser based on AST
- Vector search with Chroma + BGE-large-zh embedding model
- Git contributor analysis with weighted scoring algorithm
- LLM client supporting OpenAI and Ollama backends
- ReAct Agent 分析管线，支持迭代工具调用与维度追踪
- Jinja2-based Markdown report generation with fixed template
- Configuration system with YAML + Pydantic + environment variable support
- Structured logging with structlog
- Rich CLI progress display
- Graceful degradation when sub-modules fail
- Analysis context with confidence and completeness tracking

### Changed

- Nothing yet (first release)

### Deprecated

- Nothing yet

### Removed

- Nothing yet

### Fixed

- Nothing yet

### Security

- Nothing yet