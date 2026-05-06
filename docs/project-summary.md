# ReqRadar 项目综合分析报告

> 生成日期: 2026-05-06 | 版本: 0.8.0

---

## 目录

1. [项目概览](#1-项目概览)
2. [架构总览](#2-架构总览)
3. [模块说明](#3-模块说明)
   - 3.1 [基础设施层](#31-基础设施层-infrastructure)
   - 3.2 [核心层](#32-核心层-core)
   - 3.3 [智能体层](#33-智能体层-agent)
   - 3.4 [工具层](#34-工具层-tools)
   - 3.5 [提示词层](#35-提示词层-prompts)
   - 3.6 [功能模块层](#36-功能模块层-modules)
   - 3.7 [文档加载器层](#37-文档加载器层-loaders)
   - 3.8 [Web 层](#38-web-层)
   - 3.9 [Web API 层](#39-web-api-层)
   - 3.10 [Web 服务层](#310-web-服务层-services)
   - 3.11 [CLI 层](#311-cli-层)
   - 3.12 [前端层](#312-前端层-frontend)
   - 3.13 [测试套件](#313-测试套件-tests)
4. [已知遗留问题](#4-已知遗留问题)

---

## 1. 项目概览

**ReqRadar** (需求透镜) 是一个垂直领域需求分析 Agent 系统。用户提交需求描述或多份需求文件（文本/PDF/DOCX/图片），系统先通过 LLM 整合为结构化需求文档，再由 ReAct Agent 调用 9 种分析工具，经过 CoT 引导的推理循环，生成决策导向的双层分析报告（决策摘要层 + 技术支撑层），分析后自动更新项目记忆。

| 属性 | 值 |
|------|------|
| 项目名称 | ReqRadar (需求透镜) |
| 版本 | 0.8.0 |
| 语言 | Python 3.12+ / TypeScript |
| 后端框架 | FastAPI / SQLAlchemy 2 (async) / Pydantic v2 |
| 前端框架 | React 19 / Ant Design 6 / Vite 8（深色科技风主题） |
| 向量数据库 | ChromaDB + BAAI/bge-large-zh 嵌入模型 |
| 数据库 | SQLite (默认) / PostgreSQL (可选) |
| LLM 支持 | OpenAI-compatible API / Ollama |

### 核心能力

- **需求预处理**: 多文件上传（PDF/DOCX/图片/Markdown），LLM 整合为结构化需求文档，支持编辑确认后复用
- **ReAct 分析**: 单层循环 + CoT 提示词引导 + 7 维度 LLM 自评估，9 种分析工具可按需调用
- **风险评估**: 多维度分析（理解、影响、风险、变更、决策、证据、验证），每步产出轻量评估
- **决策报告**: 双层报告生成（管理层摘要 + 技术层细节），支持模板化输出 + 对话式追问
- **记忆自进化**: 分析后自动提取候选知识，LLM 比对去重，更新项目记忆（术语/模块/约束/技术栈）
- **项目记忆**: Markdown 格式持久化术语、模块、团队、约束等领域知识

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React SPA)                     │
│  16 Pages · 16 Components · 13 API Clients · AuthContext        │
├─────────────────────────────────────────────────────────────────┤
│                         Web Layer (FastAPI)                     │
│  API Routers (13个) · WebSocket · Auth (JWT) · Dependencies    │
│  Services: AnalysisRunner · ChatbackService · ProjectFileService│
├─────────────────────────────────────────────────────────────────┤
│                        Agent Layer                              │
│  run_react_analysis() — 单层 CoT 循环                           │
│  │ 每步: 动态系统提示词 → CoT 用户提示词 → LLM 调用             │
│  │ (tool_calls 或 STEP_OUTPUT_SCHEMA) → 更新维度/证据           │
│  │ 终止: LLM 自声明 / max_steps / 连续空步 / 连续失败            │
│  │                                                              │
│  ├── Tools (9个): SearchCode / ReadFile / GetDeps / ...        │
│  ├── Evidence + Dimension Tracker                               │
│  ├── Memory Evolution (分析后自动更新项目记忆)                   │
│  └── Requirement Preprocessor (多文件整合)                      │
├─────────────────────────────────────────────────────────────────┤
│                       Modules Layer                             │
│  CodeParser · GitAnalyzer · LLMClient · VectorStore            │
│  ProjectMemory · UserMemory · SynonymResolver · Loaders (6种)  │
├─────────────────────────────────────────────────────────────────┤
│                     Core / Infrastructure                       │
│  Config · ConfigManager · Logging · TemplateLoader · Registry  │
│  ReportRenderer · Exceptions                                   │
├─────────────────────────────────────────────────────────────────┤
│                          CLI (Click + Rich)                     │
│  project · requirement · analyze · report · config · serve     │
└─────────────────────────────────────────────────────────────────┘
```

### 关键架构决策（v0.7+）

| 决策 | 说明 |
|------|------|
| 单层 ReAct 循环 | 去掉 tool_use_loop.py 内层子循环，每步一次 LLM 调用 |
| CoT 提示词 | 4 阶段引导 + "思考→行动→评估" 模板，动态注入维度状态 |
| LLM 自评估 | 每步产出轻量 STEP_OUTPUT_SCHEMA（5 字段），LLM 自己声明维度 sufficient |
| 分析深度 | quick=10 / standard=15 / deep=25 步，绝对上限 + 连续空步检测兜底 |

---

## 3. 模块说明

### 3.1 基础设施层 (Infrastructure)

#### `config.py` — 配置模型

基于 Pydantic 的配置树，根模型 `Config` 组合 13 个子配置: `LLMConfig`, `VisionConfig`, `MemoryConfig`, `MemoryEvolutionConfig`, `LoaderConfig`, `IndexConfig`, `AnalysisConfig`, `AgentConfig`, `GitConfig`, `OutputConfig`, `ReportingConfig`, `WebConfig`, `LogConfig`。`load_config()` 从 `.reqradar.yaml` 加载，`_validate_critical_settings()` 在启动时验证关键配置。

#### `config_manager.py` — 数据库配置管理

五级优先级配置解析: 用户级 > 项目级 > 系统级 > `.reqradar.yaml` > Pydantic 默认值。支持点分键和类型强制转换。写入使用 upsert 语义，敏感值自动脱敏。

#### `logging.py` — 结构化日志

基于 `structlog` 的双模式日志: 开发用 `ConsoleRenderer`，生产用 `JSONRenderer`。

#### `template_loader.py` — 报告模板

YAML + Jinja2 报告模板定义与渲染。`TemplateLoader` 提供 `load_definition()`, `render()`, `build_section_prompts()`。

---

### 3.2 核心层 (Core)

#### `context.py` — 分析上下文

定义 `AnalysisContext` 和 13+ 辅助数据模型（`RequirementUnderstanding`, `RiskItem`, `DecisionSummary`, `EvidenceItem`, `DeepAnalysis` 等），表示一次分析的完整状态。

#### `exceptions.py` — 异常体系

扁平异常层次结构，根为 `ReqRadarException`，10 个领域子类。`__cause__` 属性设置 Python 异常链。

#### `report.py` — 报告渲染器

`ReportRenderer` 通过 Jinja2 模板渲染 Markdown 报告，支持回退内联模板和 `render_from_dict()`。

---

### 3.3 智能体层 (Agent)

#### `runner.py` — 单层 ReAct 循环（v0.7 重写）

`run_react_analysis()` 是核心分析循环。**每步流程**:
1. 动态构建系统提示词（阶段引导 + 维度状态 + 项目记忆 + 历史证据）
2. 构建用户提示词（CoT 模板: 理解状态→选择行动→评估结果）
3. LLM 调用（`_complete_with_tools`），支持 tool_calls 和结构化输出双分支
4. tool_calls 分支 → 执行工具（去重/权限/截断）→ append 到对话历史 → continue
5. 结构化输出分支 → `update_agent_from_step_result()` 标记维度 sufficient → 检查终止
6. 终止后 → `generate_report()` 生成最终报告 → `evolve_memory_after_analysis()` 记忆进化

参数 `requirement_text` 可覆盖 agent 的原始需求文本（用于引用预处理文档）。

#### `analysis_agent.py` — 分析智能体

状态机 `AgentState` (INIT/ANALYZING/GENERATING/COMPLETED/FAILED/CANCELLED)。`should_terminate()` 复合检查: 取消、步数上限、LLM 自声明 final_step、`all_sufficient()`、连续 3 空步/3 失败。

#### `dimension.py` — 维度跟踪

7 维度: understanding, impact, risk, change, decision, evidence, verification。状态: pending → in_progress → sufficient。每步 LLM 报告 sufficient 后 agent 调用 `mark_sufficient()`。

#### `evidence.py` — 证据收集

`EvidenceCollector` 维护有序证据列表，提供按维度/类型过滤和 LLM 上下文注入。

#### `requirement_preprocessor.py` — 需求预处理（v0.8 新增）

`preprocess_requirements()` 接收多文件路径，按扩展名分发 Loader（图片用 Vision LLM），然后 LLM 整合为结构化 Markdown 需求文档（背景/功能需求/非功能需求/约束/术语）。

#### `memory_evolution.py` — 记忆自进化（v0.7 新增）

`evolve_memory_after_analysis()` 分析后触发: 从报告中提取候选知识（术语/模块/约束/技术栈）→ LLM 比对已有 ProjectMemory → 去重合并 → 写入更新。

#### `schemas.py` — JSON Schema 定义

12 个 JSON Schema 用于 LLM 结构化输出，包括: `EXTRACT_SCHEMA`, `ANALYZE_SCHEMA`, `STEP_OUTPUT_SCHEMA`（v0.7 新增，轻量中间评估）, `REPORT_DATA_SCHEMA`, `MEMORY_EVOLUTION_SCHEMA`（v0.7 新增）, `CONSOLIDATION_SCHEMA`（v0.8 新增），以及项目画像/关键词映射/模块相关等。

#### `tool_call_tracker.py` — 工具调用追踪

简化版（v0.7）: 去重 + 每工具调用上限。移除了旧的 token 预算估算逻辑。

#### `llm_utils.py` — LLM 工具函数

`_parse_json_response()`（Markdown 围栏/JSON 提取）、`_call_llm_structured()`（function-calling → text-completion 回退）、`_complete_with_tools()`。

---

### 3.4 工具层 (Tools)

9 种分析工具，通过 `ToolRegistry` 注册，由 `runner.py` 的 `_execute_tool_calls()` 统一调度（去重/权限/截断/4000 字符预算）。

| 工具 | 权限 | 功能 |
|------|------|------|
| `SearchCodeTool` | read:code | 关键词/符号类型搜索代码图谱 |
| `ReadFileTool` | read:code | 沙箱化文件读取（PathSandbox + SensitiveFileFilter） |
| `ReadModuleSummaryTool` | read:memory | 读取缓存模块摘要 |
| `ListModulesTool` | read:memory | 列出所有项目模块 |
| `SearchRequirementsTool` | read:history | 语义搜索历史需求文档 |
| `GetDependenciesTool` | read:code | 模块依赖图查询 |
| `GetContributorsTool` | read:git | Git 贡献者加权分析 |
| `GetProjectProfileTool` | read:memory | 项目画像查看 |
| `GetTerminologyTool` | read:memory | 术语/域名查询 |

---

### 3.5 提示词层 (Prompts)

#### `analysis_phase.py` — 分析阶段提示（v0.7 重写）

`SYSTEM_PROMPT_TEMPLATE` 定义 4 阶段引导（理解→定位→评估→建议），每阶段有进度条和推荐工具。`build_dynamic_system_prompt()` 每步重建，注入项目记忆、用户偏好、历史上下文、当前维度状态、上轮遗留计划。`build_step_user_prompt()` 注入 CoT 模板（理解状态→选择行动→评估结果）。

#### `report_phase.py` — 报告阶段提示

`build_report_generation_prompt()` 组装需求文本 + 维度状态 + 收集证据 + 模板章节。

#### `chatback_phase.py` — 追问阶段提示

四种问题类型行为规则: 解释型/纠正型/深入型/探索型。

#### `requirement_preprocess.py` — 需求整合提示（v0.8 新增）

多文件整合为结构化 Markdown 需求的提示词，含去重/冲突标记/质量规则。

#### `memory_evolution.py` — 记忆进化提示（v0.7 新增）

CoT 比对 + 更新的提示词: 逐条比对新旧知识 → 判断 add/update/skip/merge → 输出操作列表。

---

### 3.6 功能模块层 (Modules)

#### `code_parser.py` — Python 代码解析

基于 `ast` 模块构建结构化代码图（`CodeSymbol`/`CodeFile`/`CodeGraph`）。仅支持 `.py` 文件。

#### `git_analyzer.py` — Git 分析器

加权评分: 40% 提交数 + 30% 变更行数 + 30% 近期度。支持单文件和模块级贡献者分析。

#### `llm_client.py` — LLM 客户端

`OpenAIClient` (httpx + 指数退避重试) 和 `OllamaClient` (无工具调用)。工厂函数 `create_llm_client` 按 provider 创建。

#### `vector_store.py` — 向量存储

`ChromaVectorStore` 基于 ChromaDB + BAAI/bge-large-zh。`Document`/`SearchResult` 数据类。

#### `project_memory.py` — Markdown 项目记忆

持久化到 `<storage>/<project_id>/project.md`。双向 Markdown 转换。`add_module()`/`add_term()`/`batch_add_*()` 等丰富更新方法，`to_text()` 提供文本导出（v0.7 新增）。

#### `user_memory.py` — Markdown 用户记忆

持久化到 `<storage>/<user_id>/user.md`。更正/关注领域/偏好/术语偏好。

#### `memory_manager.py` — 记忆门面

`AnalysisMemoryManager` 组合 ProjectMemory + UserMemory。`memory_enabled=False` 时返回空字符串。

#### `synonym_resolver.py` — 同义词解析

三级策略: 项目映射 → 全局映射 → 硬编码回退。`expand_keywords_with_synonyms` 返回扩展关键词。

#### `pending_changes.py` — 待审批变更

数据库支持的审批工作流。`create`/`accept`/`reject`/`list_pending`。

---

### 3.7 文档加载器层 (Loaders)

6 种加载器，通过 `LoaderRegistry` 按扩展名分发。

| 加载器 | 格式 | 说明 |
|--------|------|------|
| `TextLoader` | .txt/.md/.rst | UTF-8 优先 + GBK 回退 |
| `ImageLoader` | .png/.jpg/.jpeg/.gif/.bmp/.webp | 同步读字节 + Vision LLM 异步描述 |
| `ChatLoader` | .json (飞书) / .csv | 聊天记录结构化提取 |
| `PDFLoader` | .pdf | pdfplumber 逐页提取文本 |
| `DocxLoader` | .docx | python-docx 段落提取 |
| 回退 | 其他 | UTF-8 原样读取 |

**v0.8 更新**: 加载器现在也在需求预处理阶段使用（`requirement_preprocessor.py`），此前仅用于索引构建。

---

### 3.8 Web 层

#### `app.py` — 应用工厂

`create_app()` 构造 FastAPI，`lifespan` 管理启动/关闭。注册 13 个 API 路由器，挂载 SPA 静态文件到 `/app`。

#### `models.py` — ORM 模型

18 个模型（v0.8 新增 `RequirementDocument`）: User, UserConfig, SystemConfig, Project, ProjectConfig, AnalysisTask, Report, UploadedFile, PendingChange, SynonymMapping, ReportTemplate, ReportVersion, ReportChat, LLMCallLog, **RequirementDocument**。

#### `enums.py` — 枚举

`TaskStatus` (PENDING/RUNNING/COMPLETED/FAILED/CANCELLED), `ChangeStatus`, **`PreprocessStatus`**（v0.8 新增: processing/ready/failed）。

#### `dependencies.py` — 依赖注入

JWT 认证 (`OAuth2PasswordBearer`)，`get_current_user()` 解码令牌并查询用户。

#### `websocket.py` — WebSocket 管理

`ConnectionManager` 按任务 ID 管理连接集合，`_safe_send` 自动清理死连接。

---

### 3.9 Web API 层

13 个 API 路由器:

| 路由 | 前缀 | 功能 |
|------|------|------|
| auth | `/api/auth` | 注册/登录/JWT/登出 |
| projects | `/api/projects` | 项目 CRUD + 索引触发 |
| analyses | `/api/analyses` | 分析提交/列表/取消/重试 |
| **requirements** | `/api/requirements` | **需求预处理 CRUD（v0.8 新增）** |
| reports | `/api/reports` | 报告获取/导出 |
| configs | `/api` | 三级配置管理 |
| templates | `/api/templates` | 报告模板 CRUD |
| synonyms | `/api/synonyms` | 同义词 CRUD |
| versions | `/api/analyses/{task_id}/reports` | 版本历史/回滚 |
| chatback | `/api/analyses/{task_id}` | 对话式追问 |
| evidence | `/api/analyses/{task_id}` | 证据链查看 |
| memory | `/api/projects/{project_id}` | 项目记忆只读 |
| profile | `/api/projects/{project_id}` | 画像编辑/待审批变更 |

### 3.10 Web 服务层 (Services)

- **`analysis_runner.py`** — 分析调度器（`asyncio.Semaphore` 并发控制），v0.7 后委托 `run_react_analysis()` 执行
- **`chatback_service.py`** — 交互式追问，基于中文关键词的意图分类
- **`project_file_service.py`** — 文件系统管理（ZIP解压/Git克隆/500MB上限/路径穿越防护）
- **`project_index_service.py`** — 代码索引构建（PythonCodeParser + ChromaVectorStore）
- **`version_service.py`** — 报告版本管理（默认上限 10 个版本）

---

### 3.11 CLI 层

```
reqradar project   — 项目管理 (create/list/show/delete/index)
reqradar requirement — 需求预处理 (preprocess) [v0.8 新增]
reqradar analyze   — 分析任务 (submit/list/status/cancel/file)
reqradar report    — 报告 (get/versions/evidence)
reqradar config    — 配置管理 (init/list/get/set/delete)
reqradar serve     — 启动 Web 服务
```

**`reqradar analyze submit`** 支持三种输入方式: `-t` 文本 / `-r` 预处理文档ID / `-f` 文件。

**`reqradar requirement preprocess`** 支持多文件（`-f`）或目录扫描（`-d`），交互确认或自动保存。

---

### 3.12 前端层 (Frontend)

React 19 + TypeScript + Ant Design 6 + Vite 8。深色科技风主题（`#00d4ff` 青 + `#7c3aed` 紫）。

#### 架构变更（v0.7 Web 重构）

| 旧 → 新 |
|---------|
| AppLayout (Sider嵌套) → AppShell (TopBar + 单层 Main) |
| NavMenu → TopBar 水平导航 |
| SettingsLayout (双层嵌套) → 删除，设置页平铺 |
| App.css (183行死代码) → 删除 |
| Ant Design 默认蓝 → 深色科技风自定义主题 |
| Spin 加载 → Skeleton 骨架屏 |
| 无 ErrorBoundary → 全局 ErrorBoundary |
| WebSocket 无重连 → 指数退避自动重连 |

#### 页面 (16 个)

| 页面 | 路径 | 功能 |
|------|------|------|
| Dashboard | `/` | 知识向首页（统计+项目总览+快捷操作）[v0.7 新增] |
| Projects | `/projects` | 项目列表（搜索+创建+删除） |
| ProjectDetail | `/projects/:id` | 项目详情/文件浏览/知识库 |
| ProjectProfile | `/projects/:id/profile` | 画像编辑+待审批变更 |
| SynonymManager | `/projects/:id/synonyms` | 同义词管理 |
| AnalysisSubmit | `/analyses/submit` | 提交分析（文本/文件/预处理三种方式） |
| AnalysisList | `/analyses` | 分析任务列表 |
| AnalysisProgress | `/analyses/:id` | 实时进度（WebSocket+重连） |
| ReportView | `/reports/:taskId` | 报告查看+TOC+证据+追问 |
| RequirementEdit | `/requirements/:id` | 需求文档编辑确认 [v0.8 新增] |
| Login | `/login` | 登录/注册 |
| LLMConfig | `/settings/llm` | LLM 配置 |
| TemplateManager | `/settings/templates` | 模板管理 |
| UserPreferences | `/settings/preferences` | 用户偏好 |

#### 组件 (16 个)

AppShell, ErrorBoundary, SkeletonCard, SkeletonTable, SkeletonStat, ChatPanel, DimensionProgress, EvidencePanel, StepProgress, DepthSelector, FocusAreaSelector, FileUploader, VersionSelector, TemplateSelector, PendingChangeCard, RiskBadge

#### API 层 (13 个)

analyses, auth, chatback, configs, evidence, profile, projects, reports, requirements, synonyms, templates, versions + 共享 client.ts

---

### 3.13 测试套件 (Tests)

46 个测试文件，覆盖: agent 层（analysis_agent/dimension/evidence/tool_tracker 等）、tools（7 种）、modules（code_parser/git_analyzer/llm_client/vector_store）、Web API（auth/projects/reports/configs 等）、集成测试（round1/2/3）、loader 测试。

82 个 agent 相关测试全部通过（v0.7 验证）。测试使用 `conftest.py` 共享 fixtures（`:memory:` SQLite）。

**覆盖缺口**: 无前端测试基础设施；部分模块（memory_evolution, requirement_preprocessor, runner）仅有集成覆盖无单元覆盖。

---

## 4. 已知遗留问题

以下问题已识别但未完全解决，按优先级排列:

### 安全
- **Token 撤销仅内存存储**: 多实例部署时不同步，重启后失效。需 Redis 或数据库表实现持久化撤销。
- **Docker 部署不完整**: `Dockerfile` 无前端构建步骤，`docker-compose.yml` 默认密钥为 `change-me-in-production`。

### 架构
- **模块级可变全局状态**: `dependencies.py` 的 `async_session_factory` 和 `auth.py` 的 `SECRET_KEY` 仍通过运行时外部修改模块属性设置。
- **双记忆系统并存**: 旧 YAML `MemoryManager` (已标记废弃但未删除) vs 新 Markdown `ProjectMemory`/`UserMemory`。旧系统仍有部分工具引用。
- **代码解析仅支持 Python**: 无法覆盖前端 TypeScript 代码。

### 功能
- **无项目共享/协作模型**: 仅 `owner_id` 检查，无多用户访问机制。
- **search_requirements 相似度假设余弦距离**: 若切换距离度量会产生错误结果。
- **模块名模糊匹配**: 子串匹配可能误命中不相关模块。
- **配置 API 空值删除语义**: `PUT` 发送 `value==""` 触发删除，非直观行为。

### 测试
- **前端无测试**: 无 jest/vitest 配置。
- **pytest-cov 未声明为 dev 依赖**: `pyproject.toml` 的 `addopts` 引用 `--cov` 但包未安装。

---

> **文档结束** — 以上为 ReqRadar v0.8.0 的综合分析，涵盖所有功能模块的当前状态。
