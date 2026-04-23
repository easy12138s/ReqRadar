# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Fixed 5-step analysis pipeline (Read → Extract → Retrieve → Analyze → Generate)
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