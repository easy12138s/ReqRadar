# C-02 模块依赖地图（Module Dependency Map）

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 模块间依赖关系的权威参考——文件放哪、能 import 什么、不能 import 什么 |
| 前置文档 | 01_RESTUCTURE_OVERVIEW.md（Runtime 蓝图）、02_SYSTEM_ARCHITECTURE.md（总体架构）、04_IMPLEMENTATION_ROADMAP.md（P0 Kernel 抽离） |
| 核心目标 | 为 AI Agent（vibe coding 模式）提供精确的模块放置规则和依赖约束，防止循环依赖和层级穿透 |
| 文档职责 | Where & What — 文件放哪个目录、模块能依赖谁、不能依赖谁、新增模块如何判断归属 |

---

## 2. 总则

### 2.1 核心原则：kernel 是最内层，不依赖任何外层

ReqRadar V2 采用**严格分层依赖架构**，依赖方向只能从外层指向内层，禁止反向依赖。核心约束：

> **kernel 不依赖任何 reqradar 内部模块。kernel 只依赖 stdlib 和 third-party。**

这条规则是整个依赖体系的基石。kernel 定义了所有服务共享的类型、枚举、Protocol 和异常，任何对 kernel 的反向依赖都会破坏其"最小共享内核"的定位。

### 2.2 依赖方向铁律

```
允许方向：外层 → 内层（向下依赖）
禁止方向：内层 → 外层（向上穿透）
横行禁止：同层同目录模块之间禁止互相 import
```

---

## 3. 完整目录树

### 3.1 V2 目标目录结构

以下为 P0 完成后的目标目录结构，精确到每个文件，标注职责和对外公开类。

```
reqradar/
│
├── __init__.py                          # 包入口，版本号
│
├── kernel/                              # Layer 0 — 最小共享内核（不依赖任何 reqradar 模块）
│   ├── __init__.py
│   ├── types.py                         # 共享类型定义：ContextKind, Scope, Domain 等
│   ├── enums.py                         # 全局枚举：SessionStatus, EventType, EvidenceType, CheckpointType 等
│   ├── exceptions.py                    # 异常层次：ReqRadarException 及全部子类
│   ├── models.py                        # ORM 模型（17 张表），SQLAlchemy 声明
│   ├── database.py                      # SessionFactory, Base, async engine 基类
│   ├── config_base.py                   # Scope x Domain 配置矩阵基类
│   ├── session.py                       # CognitiveSession, SessionConfig, SessionState, SessionStatus
│   ├── context_pipeline.py              # ContextPipeline, ContextSourceProtocol, ContextStrategyProtocol
│   ├── event_stream.py                  # EventPublisherProtocol, EventConsumerProtocol, EventRecord, EventType
│   ├── tool_runtime.py                  # ToolRuntime, ToolCapability, ToolResult, ToolExecutionError
│   ├── checkpoint.py                    # CheckpointManager, CheckpointRecord, CheckpointType
│   ├── evidence.py                      # EvidenceCollectorV2, EvidenceRecord, EvidenceType, EvidenceStatus
│   ├── dimension.py                     # DimensionTrackerV2, DimensionState, DimensionStatus
│   ├── l3_writer.py                     # L3WriterProtocol, GlossaryEntry, ModuleProfile, ...
│   └── cognitive_graph.py              # GraphQueryProtocol, KnowledgeRelation, RelationType
│
├── modules/                             # Layer 1 — 功能模块（可依赖 kernel，不依赖 web/cli）
│   ├── __init__.py
│   ├── llm_client.py                    # LiteLLM 统一客户端工厂：create_llm_client()
│   ├── llm_connectivity.py              # LLM 连通性检测：check_llm_connectivity()
│   ├── code_parser.py                   # 代码解析器：CodeParser
│   ├── git_analyzer.py                  # Git 分析器：GitAnalyzer
│   ├── vector_store.py                  # 向量存储适配器：VectorStore
│   ├── memory.py                        # 记忆系统核心接口
│   ├── memory_manager.py                # 记忆管理器：MemoryManager
│   ├── project_memory.py                # 项目记忆：ProjectMemory
│   ├── user_memory.py                   # 用户记忆：UserMemory
│   ├── synonym_resolver.py              # 同义词解析器：SynonymResolver
│   ├── pending_changes.py               # 待定变更管理：PendingChangeManager
│   └── loaders/                         # 文档加载器子包
│       ├── __init__.py
│       ├── base.py                      # BaseLoader 基类
│       ├── chat_loader.py               # ChatLoader
│       ├── chat_types.py                # ChatMessage, ChatSession 类型
│       ├── markitdown_loader.py         # MarkItDownLoader
│       └── text_loader.py              # TextLoader
│
├── agent/                               # Layer 1 — 分析 Agent（可依赖 kernel + modules，不依赖 web/cli）
│   ├── __init__.py
│   ├── analysis_agent.py                # AnalysisAgent — ReAct 推理主循环
│   ├── runner.py                        # AgentRunner — 分析任务执行器
│   ├── schemas.py                       # Agent 专用 Pydantic 模型
│   ├── llm_utils.py                     # LLM 调用工具函数
│   ├── evidence.py                      # V1 Evidence 收集器（过渡期保留）
│   ├── dimension.py                     # V1 维度追踪器（过渡期保留）
│   ├── memory_evolution.py              # 记忆演化逻辑
│   ├── project_profile.py               # 项目画像逻辑
│   ├── requirement_preprocessor.py      # 需求预处理器
│   ├── tool_call_tracker.py             # 工具调用追踪器
│   ├── prompts/                         # Prompt 模板子包
│   │   ├── __init__.py
│   │   ├── analysis_phase.py            # 分析阶段 Prompt
│   │   ├── chatback_phase.py            # Chatback 阶段 Prompt
│   │   ├── memory_evolution.py          # 记忆演化 Prompt
│   │   ├── project_profile.py           # 项目画像 Prompt
│   │   ├── report_phase.py              # 报告生成 Prompt
│   │   └── requirement_preprocess.py    # 需求预处理 Prompt
│   └── tools/                           # 工具实现子包
│       ├── __init__.py
│       ├── base.py                      # BaseTool 基类
│       ├── registry.py                  # ToolRegistry 工具注册表
│       ├── security.py                  # 安全工具
│       ├── search_code.py               # 代码搜索工具
│       ├── search_git_history.py        # Git 历史搜索工具
│       ├── search_requirements.py       # 需求搜索工具
│       ├── read_file.py                 # 文件读取工具
│       ├── read_module_summary.py       # 模块摘要读取工具
│       ├── list_modules.py              # 模块列表工具
│       ├── get_terminology.py           # 术语获取工具
│       ├── get_project_profile.py       # 项目画像获取工具
│       ├── get_dependencies.py          # 依赖获取工具
│       └── get_contributors.py          # 贡献者获取工具
│
├── web/                                 # Layer 2 — Web 层（可依赖 kernel + modules + agent）
│   ├── __init__.py
│   ├── app.py                           # FastAPI 应用工厂：create_app(), lifespan
│   ├── database.py                      # Web 层 SQLAlchemy 配置（engine, session_factory）
│   ├── models.py                        # Web 层 ORM 模型（V1 过渡期，逐步迁移至 kernel/models.py）
│   ├── dependencies.py                  # FastAPI 依赖注入：DbSession, CurrentUser, get_db, get_current_user
│   ├── enums.py                         # Web 层枚举（V1 过渡期）
│   ├── exceptions.py                    # Web 层异常处理器（映射 domain 异常 → HTTP 状态码）
│   ├── seed.py                          # 数据库种子数据
│   ├── websocket.py                     # WebSocket 连接管理
│   ├── cli.py                           # Web 子命令（serve, createsuperuser）
│   ├── middleware/                      # 中间件子包
│   │   ├── __init__.py
│   │   └── rate_limit.py               # 速率限制中间件
│   ├── api/                             # API 路由子包（各路由模块禁止互相 import）
│   │   ├── __init__.py
│   │   ├── auth.py                      # 认证路由：register, login, me, logout, password
│   │   ├── users.py                     # 用户管理路由
│   │   ├── projects.py                  # 项目路由
│   │   ├── analyses.py                  # 分析路由 + WebSocket
│   │   ├── reports.py                   # 报告路由
│   │   ├── versions.py                  # 版本路由
│   │   ├── chatback.py                  # Chatback 路由
│   │   ├── evidence_api.py              # 证据路由
│   │   ├── memory.py                    # 记忆路由
│   │   ├── profile.py                   # 项目画像路由
│   │   ├── configs.py                   # 配置路由
│   │   ├── templates.py                 # 模板路由
│   │   ├── synonyms.py                  # 同义词路由
│   │   ├── requirements.py              # 需求路由
│   │   ├── releases.py                  # 发布路由
│   │   ├── mcp.py                       # MCP 路由
│   │   └── users.py                     # 用户管理路由
│   └── services/                        # 服务层子包（各服务禁止互相 import）
│       ├── __init__.py
│       ├── analysis_runner.py           # 分析任务运行器
│       ├── chatback_service.py          # Chatback 服务
│       ├── content_reader.py            # 内容读取服务
│       ├── mcp_audit_service.py         # MCP 审计服务
│       ├── mcp_auth_service.py          # MCP 认证服务
│       ├── project_file_service.py      # 项目文件服务
│       ├── project_index_service.py     # 项目索引服务
│       ├── project_store.py             # 项目存储服务
│       ├── report_storage.py            # 报告存储服务
│       ├── requirement_release_service.py # 需求发布服务
│       └── version_service.py           # 版本管理服务
│
├── cli/                                 # Layer 3 — CLI 层（可依赖 kernel + modules + web）
│   ├── __init__.py
│   ├── main.py                          # Click 主入口：reqradar 命令组
│   ├── analyses.py                      # analyze 子命令组
│   ├── config.py                        # config 子命令组
│   ├── projects.py                      # project 子命令组
│   ├── reports.py                       # report 子命令组
│   ├── requirements.py                  # requirement 子命令组
│   ├── mcp_cli.py                       # mcp 子命令组
│   └── utils.py                         # CLI 工具函数
│
├── mcp/                                 # Layer 1 — MCP 集成（可依赖 kernel + modules，不依赖 web/cli）
│   ├── __init__.py
│   ├── auth.py                          # MCP 认证
│   ├── context.py                       # MCP 上下文管理
│   ├── lifecycle.py                     # MCP 生命周期管理
│   ├── schemas.py                       # MCP Schema 定义
│   └── tools.py                         # MCP 工具注册
│
├── infrastructure/                      # Layer 4 — 基础设施（可被所有层依赖）
│   ├── __init__.py
│   ├── config.py                        # Pydantic 配置模型 + load_config()
│   ├── config_manager.py                # 配置管理器（CRUD）
│   ├── logging.py                       # structlog 日志配置
│   ├── paths.py                         # 路径管理：get_paths(), ensure_dirs(), resolve_home()
│   ├── registry.py                      # 配置注册表
│   ├── template_loader.py              # 模板加载器
│   └── migrate_report_files.py         # 报告文件迁移工具
│
└── templates/                           # 报告模板（非 Python 包，Jinja2 + YAML）
    ├── default_report.yaml
    ├── general_requirements.yaml
    ├── performance_analysis.yaml
    ├── report.md.j2
    ├── security_audit.yaml
    ├── tech_debt.yaml
    └── ux_review.yaml
```

### 3.2 前端目录结构（参考）

```
frontend/src/
├── api/                 # API 客户端模块（每后端路由一文件）
│   ├── client.ts        # axios 实例，统一拦截器
│   ├── auth.ts
│   ├── projects.ts
│   ├── analyses.ts
│   └── ...
├── components/          # 通用 UI 组件
├── context/             # React Context（Auth, Theme）
├── hooks/               # 自定义 Hooks
├── pages/               # 页面组件（路由级，lazy 加载）
├── types/               # TypeScript 类型定义
├── constants/           # 常量定义
├── App.tsx              # 路由 + Provider 嵌套
└── main.tsx             # 入口
```

---

## 4. 分层依赖规则

### 4.1 五层架构定义

| Layer | 目录 | 可依赖 | 禁止依赖 |
|-------|------|--------|---------|
| **Layer 0** (kernel) | `kernel/` | stdlib, third-party | 任何 `reqradar.*` 模块 |
| **Layer 1** (modules) | `modules/`, `agent/`, `mcp/` | kernel, stdlib, third-party | `web.*`, `cli.*` |
| **Layer 2** (web) | `web/` | kernel, modules, agent, stdlib, third-party | `cli.*` |
| **Layer 3** (cli) | `cli/` | kernel, modules, web, stdlib, third-party | 无额外限制 |
| **Layer 4** (infrastructure) | `infrastructure/` | stdlib, third-party | 无（被所有层依赖） |

### 4.2 依赖方向 ASCII 图

```
                    ┌─────────────────────────────────────────────┐
                    │              Layer 3: cli/                   │
                    │   可依赖: kernel, modules, agent, web        │
                    └──────────────────┬──────────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────────────┐
                    │              Layer 2: web/                   │
                    │   可依赖: kernel, modules, agent             │
                    └──────────────────┬──────────────────────────┘
                                       │
                                       ▼
          ┌────────────────────────────────────────────────────────┐
          │                Layer 1: modules/ agent/ mcp/           │
          │   可依赖: kernel                                        │
          └──────────────────────────┬─────────────────────────────┘
                                     │
                                     ▼
          ┌────────────────────────────────────────────────────────┐
          │                Layer 0: kernel/                        │
          │   可依赖: stdlib, third-party ONLY                     │
          │   禁止依赖: 任何 reqradar.* 模块                        │
          └────────────────────────────────────────────────────────┘

          ┌────────────────────────────────────────────────────────┐
          │          Layer 4: infrastructure/                      │
          │   可被所有层依赖（配置、日志、路径）                      │
          │   自身只依赖: stdlib, third-party                       │
          └────────────────────────────────────────────────────────┘
               ▲         ▲          ▲          ▲
               │         │          │          │
            kernel    modules     web        cli
           (可依赖)  (可依赖)   (可依赖)   (可依赖)
```

### 4.3 infrastructure 的特殊地位

`infrastructure/` 是横切层，提供配置、日志、路径等基础能力。它被所有层依赖，但自身不依赖任何 `reqradar.*` 模块：

```
infrastructure/ ──► stdlib, third-party（仅此）
       ▲
       │ 被依赖
  ┌────┴────┬─────────┬─────────┐
kernel   modules    web       cli
```

**约束**：`infrastructure/` 不引入任何业务语义。如果某个工具函数需要引用 `kernel/` 中的类型，则该函数应放在 `kernel/` 中，而非 `infrastructure/`。

### 4.4 依赖矩阵

下表用 X 标记"允许依赖"，用 -- 标记"禁止依赖"：

| 依赖方 \ 被依赖方 | kernel | modules | agent | mcp | web | cli | infrastructure |
|-------------------|--------|---------|-------|-----|-----|-----|----------------|
| **kernel**        | --     | --      | --    | --  | --  | --  | --             |
| **modules**       | X      | --      | --    | --  | --  | --  | X              |
| **agent**         | X      | X       | --    | --  | --  | --  | X              |
| **mcp**           | X      | X       | --    | --  | --  | --  | X              |
| **web.api**       | X      | X       | X     | --  | --  | --  | X              |
| **web.services**  | X      | X       | X     | X   | --  | --  | X              |
| **web（其他）**    | X      | X       | X     | --  | --  | --  | X              |
| **cli**           | X      | X       | X     | --  | X   | --  | X              |

**注**：
- `modules` 内部子模块之间可以互相依赖（如 `memory_manager` → `project_memory`），但应保持最小依赖
- `agent` 可依赖 `modules`，但 `modules` 禁止依赖 `agent`
- `web.api.*` 各路由模块之间禁止互相 import
- `web.services.*` 各服务之间禁止互相 import

---

## 5. 模块注册表

### 5.1 kernel/ — 最小共享内核

| 文件 | 职责 | 对外公开接口 |
|------|------|-------------|
| `kernel/types.py` | 共享类型定义 | `ContextKind`, `Scope`, `Domain`, `ConfigKey`, `ContextItem`, `ScoredContextItem`, `TokenBudget` |
| `kernel/enums.py` | 全局枚举 | `SessionStatus`, `EventType`, `EvidenceType`, `EvidenceStatus`, `CheckpointType`, `DimensionStatus`, `FreshnessStatus`, `RelationType`, `KnowledgeNodeType` |
| `kernel/exceptions.py` | 异常层次 | `ReqRadarException`, `FatalError`, `ConfigException`, `LLMException`, `ParseException`, `VectorStoreException`, `GitException`, `IndexException`, `ReportException`, `LoaderException`, `VisionNotConfiguredError`, `ToolExecutionError`, `CheckpointException`, `SessionException`, `ContextBudgetExceededException` |
| `kernel/models.py` | ORM 模型 | 全部 SQLAlchemy 模型类（17 张表），`Base` |
| `kernel/database.py` | 数据库基类 | `SessionFactory`, `async_engine`, `get_session()` |
| `kernel/config_base.py` | 配置矩阵基类 | `ConfigMatrixBase`, `ScopeDomainConfig`, `ConfigResolutionChain` |
| `kernel/session.py` | 会话核心 | `CognitiveSession`, `SessionConfig`, `SessionState`, `SessionStatus` |
| `kernel/context_pipeline.py` | 上下文管线 | `ContextPipeline`, `ContextSourceProtocol`, `ContextStrategyProtocol`, `QualityGateResult` |
| `kernel/event_stream.py` | 事件流 | `EventPublisherProtocol`, `EventConsumerProtocol`, `EventRecord`, `EventType` |
| `kernel/tool_runtime.py` | 工具运行时 | `ToolRuntime`, `ToolCapability`, `ToolResult`, `ToolExecutionError` |
| `kernel/checkpoint.py` | 检查点 | `CheckpointManager`, `CheckpointRecord`, `CheckpointType` |
| `kernel/evidence.py` | 证据模型 | `EvidenceCollectorV2`, `EvidenceRecord`, `EvidenceType`, `EvidenceStatus`, `EvidenceRelation`, `SourceRef` |
| `kernel/dimension.py` | 维度追踪 | `DimensionTrackerV2`, `DimensionState`, `DimensionStatus`, `DimensionAssessment` |
| `kernel/l3_writer.py` | L3 写入协议 | `L3WriterProtocol`, `GlossaryEntry`, `ModuleProfile`, `ArchitectureConstraint`, `DecisionRecord`, `RiskEvolution`, `RequirementLineage`, `AccidentMemory`, `L3KnowledgeBase`, `ConfidenceMetadata` |
| `kernel/cognitive_graph.py` | 认知图谱 | `GraphQueryProtocol`, `KnowledgeRelation`, `RelationType`, `KnowledgeNode` |

### 5.2 modules/ — 功能模块

| 文件 | 职责 | 对外公开接口 |
|------|------|-------------|
| `modules/llm_client.py` | LiteLLM 统一客户端 | `create_llm_client()`, `LiteLLMClient` |
| `modules/llm_connectivity.py` | LLM 连通性检测 | `check_llm_connectivity()`, `ConnectivityResult` |
| `modules/code_parser.py` | 代码解析 | `CodeParser`, `ParseResult` |
| `modules/git_analyzer.py` | Git 分析 | `GitAnalyzer`, `GitAnalysisResult` |
| `modules/vector_store.py` | 向量存储 | `VectorStore`, `SearchResult` |
| `modules/memory.py` | 记忆系统核心 | `MemorySystem` |
| `modules/memory_manager.py` | 记忆管理 | `MemoryManager` |
| `modules/project_memory.py` | 项目记忆 | `ProjectMemory` |
| `modules/user_memory.py` | 用户记忆 | `UserMemory` |
| `modules/synonym_resolver.py` | 同义词解析 | `SynonymResolver` |
| `modules/pending_changes.py` | 待定变更 | `PendingChangeManager`, `PendingChange` |
| `modules/loaders/base.py` | 加载器基类 | `BaseLoader` |
| `modules/loaders/chat_loader.py` | Chat 加载器 | `ChatLoader` |
| `modules/loaders/chat_types.py` | Chat 类型 | `ChatMessage`, `ChatSession` |
| `modules/loaders/markitdown_loader.py` | MarkItDown 加载器 | `MarkItDownLoader` |
| `modules/loaders/text_loader.py` | 文本加载器 | `TextLoader` |

### 5.3 agent/ — 分析 Agent

| 文件 | 职责 | 对外公开接口 |
|------|------|-------------|
| `agent/analysis_agent.py` | ReAct 推理主循环 | `AnalysisAgent` |
| `agent/runner.py` | 分析任务执行器 | `AgentRunner` |
| `agent/schemas.py` | Agent 专用模型 | `AgentState`, `StepResult`, `AnalysisConfig` |
| `agent/llm_utils.py` | LLM 调用工具 | `call_llm()`, `parse_json_response()` |
| `agent/evidence.py` | V1 证据收集器 | `EvidenceCollector`（过渡期） |
| `agent/dimension.py` | V1 维度追踪器 | `DimensionTracker`（过渡期） |
| `agent/memory_evolution.py` | 记忆演化 | `MemoryEvolution` |
| `agent/project_profile.py` | 项目画像 | `ProjectProfiler` |
| `agent/requirement_preprocessor.py` | 需求预处理 | `RequirementPreprocessor` |
| `agent/tool_call_tracker.py` | 工具调用追踪 | `ToolCallTracker` |
| `agent/tools/base.py` | 工具基类 | `BaseTool` |
| `agent/tools/registry.py` | 工具注册表 | `ToolRegistry` |

### 5.4 web/ — Web 层

| 文件 | 职责 | 对外公开接口 |
|------|------|-------------|
| `web/app.py` | 应用工厂 | `create_app()`, lifespan |
| `web/database.py` | 数据库配置 | `async_session_factory`, `engine` |
| `web/models.py` | ORM 模型（V1） | `UserModel`, `ProjectModel`, `AnalysisTaskModel` 等（逐步迁移至 kernel） |
| `web/dependencies.py` | 依赖注入 | `DbSession`, `CurrentUser`, `get_db`, `get_current_user` |
| `web/exceptions.py` | 异常处理器 | `register_exception_handlers()` |
| `web/websocket.py` | WebSocket 管理 | `ConnectionManager` |
| `web/seed.py` | 种子数据 | `seed_database()` |
| `web/cli.py` | Web CLI | `serve`, `createsuperuser` 命令 |

### 5.5 cli/ — CLI 层

| 文件 | 职责 | 对外公开接口 |
|------|------|-------------|
| `cli/main.py` | Click 主入口 | `cli` 命令组 |
| `cli/analyses.py` | 分析子命令 | `analyze` 命令组 |
| `cli/config.py` | 配置子命令 | `config` 命令组 |
| `cli/projects.py` | 项目子命令 | `project` 命令组 |
| `cli/reports.py` | 报告子命令 | `report` 命令组 |
| `cli/requirements.py` | 需求子命令 | `requirement` 命令组 |
| `cli/mcp_cli.py` | MCP 子命令 | `mcp` 命令组 |
| `cli/utils.py` | 工具函数 | `format_output()`, `resolve_api_url()` |

### 5.6 mcp/ — MCP 集成

| 文件 | 职责 | 对外公开接口 |
|------|------|-------------|
| `mcp/auth.py` | MCP 认证 | `MCPAuthManager` |
| `mcp/context.py` | MCP 上下文 | `MCPContextManager` |
| `mcp/lifecycle.py` | MCP 生命周期 | `MCPLifecycleManager` |
| `mcp/schemas.py` | MCP Schema | `MCPServerConfig`, `MCPToolDefinition` |
| `mcp/tools.py` | MCP 工具 | `MCPToolRegistry` |

### 5.7 infrastructure/ — 基础设施

| 文件 | 职责 | 对外公开接口 |
|------|------|-------------|
| `infrastructure/config.py` | 配置模型 | `Config`, `HomeConfig`, `LLMConfig`, `load_config()` |
| `infrastructure/config_manager.py` | 配置管理 | `ConfigManager`, `get_config()`, `set_config()`, `delete_config()` |
| `infrastructure/logging.py` | 日志配置 | `setup_logging()`, `get_logger()` |
| `infrastructure/paths.py` | 路径管理 | `get_paths()`, `ensure_dirs()`, `resolve_home()` |
| `infrastructure/registry.py` | 配置注册表 | `ConfigRegistry` |
| `infrastructure/template_loader.py` | 模板加载 | `TemplateLoader`, `load_template()` |
| `infrastructure/migrate_report_files.py` | 迁移工具 | `migrate_report_files()` |

---

## 6. 禁止依赖清单

### 6.1 绝对禁止

| 编号 | 规则 | 原因 |
|------|------|------|
| D-01 | `kernel/` 禁止 import `web.*` | kernel 是最内层，不可穿透到 Web 层 |
| D-02 | `kernel/` 禁止 import `modules.*` | kernel 通过 Protocol 解耦，modules 实现 Protocol，kernel 不引用 modules |
| D-03 | `kernel/` 禁止 import `agent.*` | 同 D-02 |
| D-04 | `kernel/` 禁止 import `cli.*` | kernel 不感知 CLI 层 |
| D-05 | `kernel/` 禁止 import `mcp.*` | kernel 不感知 MCP 集成层 |
| D-06 | `modules/` 禁止 import `web.*` | modules 是业务逻辑层，不应感知 HTTP 传输层 |
| D-07 | `modules/` 禁止 import `agent.*` | modules 是被 agent 依赖的基础层，反向依赖形成循环 |
| D-08 | `agent/` 禁止 import `web.*` | agent 是推理引擎，不应感知 HTTP 传输层 |
| D-09 | `mcp/` 禁止 import `web.*` | MCP 集成层不应感知 Web 层 |
| D-10 | `mcp/` 禁止 import `agent.*` | MCP 不应依赖 Agent 内部实现 |

### 6.2 同层隔离

| 编号 | 规则 | 原因 |
|------|------|------|
| D-11 | `web/api/*` 各路由模块禁止互相 import | 路由模块应独立，共享逻辑提取到 `web/services/` 或 `kernel/` |
| D-12 | `web/services/*` 各服务禁止互相 import | 服务间通过 kernel 接口（Protocol/Event）交互，不直接调用 |
| D-13 | `agent/tools/*` 各工具禁止互相 import | 工具应独立，组合逻辑由 Agent 或 ToolRuntime 管理 |
| D-14 | `agent/prompts/*` 各 Prompt 模块禁止互相 import | Prompt 模板应独立，组合由 Agent 管理 |

### 6.3 kernel 的 Protocol 解耦机制

kernel 通过 Protocol（Python `typing.Protocol`）定义接口，modules/agent 实现 Protocol，实现依赖反转：

```python
# kernel/context_pipeline.py — 定义 Protocol
from typing import Protocol

class ContextSourceProtocol(Protocol):
    async def collect(self, query: str, budget: int) -> list[ContextItem]: ...

class ContextStrategyProtocol(Protocol):
    async def select(self, items: list[ScoredContextItem], budget: int) -> list[ScoredContextItem]: ...


# modules/memory.py — 实现 Protocol
from reqradar.kernel.context_pipeline import ContextSourceProtocol, ContextItem

class MemoryContextSource:
    """项目记忆上下文源，实现 ContextSourceProtocol"""
    async def collect(self, query: str, budget: int) -> list[ContextItem]:
        ...
```

**关键约束**：kernel 只定义 Protocol 签名，不 import 任何实现类。modules 提供 Protocol 的具体实现。这确保了 kernel 对 modules 的零依赖。

---

## 7. 循环依赖检测规则

### 7.1 循环依赖的产生原因

| 场景 | 示例 | 后果 |
|------|------|------|
| 双向 import | `A` import `B`，`B` import `A` | ImportError 或属性为 None |
| 间接循环 | `A` → `B` → `C` → `A` | 运行时错误，难以定位 |
| 模块级副作用 | `A` 在模块级执行 `B.func()`，而 `B` 尚未初始化 | AttributeError |

### 7.2 预防措施

1. **严格遵循分层规则**：只允许外层依赖内层，从根本上杜绝循环
2. **使用 Protocol 解耦**：内层定义 Protocol，外层实现，避免反向引用
3. **延迟导入**：仅在函数内部 import，不在模块顶层 import（仅作为最后手段）
4. **事件驱动交互**：服务间通过 Event Stream 通信，不直接调用

### 7.3 检测工具

| 工具 | 用途 | 配置 |
|------|------|------|
| `ruff check .` | Ruff 的 import sorting 规则（I 系列）可检测部分依赖问题 | `pyproject.toml` 中 `known-first-party = ["reqradar"]` |
| `mypy .` | 类型检查时可发现 Protocol 实现不匹配 | `pyproject.toml` 中 `ignore_missing_imports = true` |
| `pydeps` | 生成模块依赖图，可视化检测循环 | 手动运行：`pydeps reqradar --max-bacon=2` |
| 自定义 CI 检查 | 在 CI 中运行依赖规则校验脚本 | 见下方脚本示例 |

### 7.4 CI 依赖规则校验脚本（示例）

```python
#!/usr/bin/env python3
"""校验 reqradar 模块依赖规则，在 CI 中运行"""
import ast
import sys
from pathlib import Path

# 定义禁止的依赖方向：key 禁止 import value 中的任何模块
FORBIDDEN = {
    "kernel": ["web", "modules", "agent", "mcp", "cli"],
    "modules": ["web", "agent", "cli"],
    "agent": ["web", "cli"],
    "mcp": ["web", "agent", "cli"],
}

def get_imports(file_path: Path) -> list[str]:
    """提取文件中所有 reqradar 内部 import"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("reqradar."):
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("reqradar."):
                imports.append(node.module)
    return imports

def check_violations(src_root: Path) -> list[str]:
    """检查所有文件的依赖违规"""
    violations = []
    for py_file in src_root.rglob("*.py"):
        rel = py_file.relative_to(src_root)
        parts = rel.parts
        if len(parts) < 2 or parts[0] != "reqradar":
            continue
        layer = parts[1]  # kernel, modules, agent, ...
        if layer not in FORBIDDEN:
            continue
        forbidden_targets = FORBIDDEN[layer]
        for imp in get_imports(py_file):
            imp_parts = imp.split(".")
            if len(imp_parts) >= 2 and imp_parts[1] in forbidden_targets:
                violations.append(
                    f"{rel}: {layer} 禁止 import {imp} (违反 D-0x 规则)"
                )
    return violations

if __name__ == "__main__":
    src = Path("src")
    violations = check_violations(src)
    if violations:
        for v in violations:
            print(f"DEPENDENCY VIOLATION: {v}", file=sys.stderr)
        sys.exit(1)
    print("All dependency rules satisfied.")
```

---

## 8. 服务间调用方向

### 8.1 V2 微服务间调用关系

当 V2 完成服务拆分后（P5+），各服务间的调用方向如下：

```
┌──────────────────────────────────────────────────────────────────┐
│                        Traefik Gateway                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
  auth-service        api-service          frontend
  (认证授权)           (BFF/API)           (静态资源)
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    cognitive-rt     index-service    output-service
    (认知运行时)      (索引存储)        (输出渲染)
           │               │
           │ HTTP          │
           ├──────────────►│  cognitive-rt → index-service（Checkpoint 存储/查询，最频繁）
           │               │
           │ Redis Pub/Sub │
           ├──────────────►│  cognitive-rt → api-service（Event 广播 → WS 推送）
           │               │
           │ HTTP          │
           ▼               │
    integration-svc        │
    (MCP/外部集成)         │
           │               │
           │ HTTP          │
           ├──────────────►│  integration-svc → index-service（读取记忆）
           │               │
    ingestion-svc          │
    (数据摄取)             │
           │               │
           │ HTTP          │
           ├──────────────►│  ingestion-svc → index-service（写入结构化事实）
           │               │
           └───────────────┘
```

### 8.2 调用方向汇总表

| 调用方 | 被调用方 | 协议 | 场景 |
|--------|---------|------|------|
| cognitive-rt | index-service | HTTP | Checkpoint 存储/查询、向量检索、L3 知识读写 |
| cognitive-rt | api-service | Redis Pub/Sub | Event Stream 广播，api-service 转发至前端 WS |
| cognitive-rt | integration-service | HTTP | 工具执行（MCP 调用、外部 API） |
| cognitive-rt | output-service | HTTP | 报告生成请求 |
| api-service | auth-service | HTTP | JWT 校验、权限查询 |
| api-service | cognitive-rt | HTTP | 创建/查询 Session、提交分析任务 |
| integration-service | index-service | HTTP | 读取项目记忆、检索知识 |
| integration-service | output-service | HTTP | MCP 读取报告 |
| ingestion-service | index-service | HTTP | 写入 L1 结构化事实、向量索引 |

### 8.3 禁止的服务间调用

| 禁止方向 | 原因 |
|---------|------|
| index-service → cognitive-rt | index-service 是被动存储层，不应反向调用运行时 |
| output-service → cognitive-rt | 输出服务不驱动运行时 |
| auth-service → 任何业务服务 | 认证服务是信任源，不依赖业务服务 |
| 任何服务 → auth-service（除 api-service） | 只有 BFF 需要校验 JWT |

---

## 9. 新增模块的放置规则

### 9.1 决策树

当需要新增一个 Python 模块时，按以下决策树判断归属目录：

```
新增模块 M
│
├── Q1: M 是否定义了被多个服务共享的类型/枚举/Protocol/异常？
│   ├── 是 → kernel/
│   └── 否 → Q2
│
├── Q2: M 是否包含业务逻辑（LLM 调用、数据解析、记忆管理等）？
│   ├── 是 → Q3
│   └── 否 → Q4
│
├── Q3: M 是否与 Agent 推理过程直接相关（工具、Prompt、推理策略）？
│   ├── 是 → agent/
│   │   ├── 工具实现 → agent/tools/
│   │   ├── Prompt 模板 → agent/prompts/
│   │   └── Agent 核心逻辑 → agent/
│   └── 否 → Q3a
│
├── Q3a: M 是否与 MCP/外部集成相关？
│   ├── 是 → mcp/
│   └── 否 → modules/
│
├── Q4: M 是否暴露 HTTP API 端点？
│   ├── 是 → Q5
│   └── 否 → Q6
│
├── Q5: M 的 HTTP 端点属于哪个子域？
│   ├── 路由处理 → web/api/
│   ├── 业务编排 → web/services/
│   ├── 中间件 → web/middleware/
│   └── 其他 Web 基础设施 → web/
│
├── Q6: M 是否是 CLI 命令？
│   ├── 是 → cli/
│   └── 否 → Q7
│
├── Q7: M 是否提供配置/日志/路径等横切基础设施？
│   ├── 是 → infrastructure/
│   └── 否 → 回到 Q1 重新审视，或创建新的 kernel 子模块
```

### 9.2 常见场景速查

| 新增内容 | 放置目录 | Layer | 示例 |
|---------|---------|-------|------|
| 新的共享枚举 | `kernel/enums.py` | 0 | `AnalysisPriority` |
| 新的 Protocol 定义 | `kernel/*.py` | 0 | `ReportRendererProtocol` |
| 新的异常类型 | `kernel/exceptions.py` | 0 | `SessionTimeoutException` |
| 新的 LLM Provider 适配 | `modules/llm_client.py` | 1 | `AnthropicAdapter` |
| 新的文档加载器 | `modules/loaders/` | 1 | `PdfLoader` |
| 新的分析工具 | `agent/tools/` | 1 | `search_dependencies.py` |
| 新的 Prompt 模板 | `agent/prompts/` | 1 | `risk_assessment.py` |
| 新的 API 路由 | `web/api/` | 2 | `health.py` |
| 新的业务服务 | `web/services/` | 2 | `session_service.py` |
| 新的 CLI 子命令 | `cli/` | 3 | `session.py` |
| 新的配置模型 | `infrastructure/config.py` | 4 | `RedisConfig` |
| 新的 ORM 表 | `kernel/models.py` | 0 | `CheckpointModel` |

### 9.3 新增模块的依赖检查清单

新增模块时，必须完成以下检查：

- [ ] 确认模块所属 Layer，依赖方向是否符合分层规则
- [ ] 确认不引入任何禁止的 import（参见第 6 节禁止依赖清单）
- [ ] 如果是 `web/api/` 或 `web/services/` 下的模块，确认不 import 同目录其他模块
- [ ] 如果是 `kernel/` 下的模块，确认不 import 任何 `reqradar.*` 模块
- [ ] 在 `kernel/types.py` 或 `kernel/enums.py` 中定义需要的共享类型
- [ ] 运行 `ruff check . && mypy .` 确认无 lint 和类型错误
- [ ] 运行依赖规则校验脚本（第 7.4 节）确认无违规

---

## 10. V1 → V2 迁移期间的过渡规则

### 10.1 双轨并行期

在 P0-P3 迁移期间，V1 和 V2 代码共存。以下过渡规则在此期间有效：

| 规则 | 说明 | 过渡期结束后 |
|------|------|-------------|
| `web/models.py` 保留 | V1 ORM 模型暂留于 `web/models.py`，逐步迁移至 `kernel/models.py` | 删除 `web/models.py` |
| `web/enums.py` 保留 | V1 枚举暂留，逐步迁移至 `kernel/enums.py` | 删除 `web/enums.py` |
| `agent/evidence.py` 保留 | V1 EvidenceCollector 暂留，V2 `kernel/evidence.py` 完成后替换 | 删除 `agent/evidence.py` |
| `agent/dimension.py` 保留 | V1 DimensionTracker 暂留，V2 `kernel/dimension.py` 完成后替换 | 删除 `agent/dimension.py` |
| `core/` 目录保留 | V1 `core/` 目录暂留（context.py, exceptions.py, report.py），逐步迁移至 `kernel/` | 删除 `core/` 目录 |

### 10.2 迁移优先级

```
P0: kernel/types.py + kernel/enums.py + kernel/exceptions.py + kernel/models.py + kernel/database.py
     ← 从 core/ 和 web/ 搬迁类型、枚举、异常、ORM
P1: kernel/context_pipeline.py + kernel/config_base.py
     ← 新增 Context Pipeline Protocol 和配置矩阵
P3: kernel/session.py + kernel/event_stream.py + kernel/checkpoint.py
     ← 新增 Session/Event/Checkpoint 核心抽象
P4: kernel/tool_runtime.py
     ← 新增 ToolRuntime 管控层
P5: kernel/evidence.py + kernel/dimension.py + kernel/l3_writer.py + kernel/cognitive_graph.py
     ← 从 agent/ 搬迁并升级 Evidence/Dimension，新增 L3/Graph
```

### 10.3 迁移期间禁止事项

| 禁止 | 原因 |
|------|------|
| 在 V1 代码中新增对 `kernel/` 的反向依赖 | 迁移是单向的，V1 代码不依赖 V2 kernel |
| 在 `core/` 目录中新增文件 | `core/` 是待废弃目录，新代码放 `kernel/` |
| 在 `web/models.py` 中新增 ORM 表 | 新表定义在 `kernel/models.py` |

---

## 11. 附录

### 11.1 术语表

| 术语 | 定义 |
|------|------|
| kernel | 最小共享内核，Layer 0，仅包含类型、枚举、Protocol、异常、ORM |
| Protocol | Python `typing.Protocol`，定义接口签名，不包含实现 |
| Layer | 依赖层级，0-4，数字越小越内层 |
| 依赖穿透 | 内层模块 import 外层模块，违反分层规则 |
| 同层隔离 | 同一目录下的模块之间禁止互相 import |
| 横切层 | infrastructure/，被所有层依赖的基础设施 |

### 11.2 参考文档

| 文档 | 关联 |
|------|------|
| 01_RESTUCTURE_OVERVIEW.md | Runtime 蓝图，定义了五层运行时分层 |
| 02_SYSTEM_ARCHITECTURE.md | 总体架构，定义了服务拓扑和通信方式 |
| 03_COGNITIVE_ASSET_MODEL.md | 认知资产模型，定义了 L0-L3 数据层次 |
| 04_IMPLEMENTATION_ROADMAP.md | 实施路线图，定义了 P0-P10 迁移阶段 |
| R-01_SESSION_LIFECYCLE.md | Session 生命周期，定义了 kernel/session.py 的核心模型 |
| R-02_CONTEXT_PIPELINE.md | Context Pipeline，定义了 kernel/context_pipeline.py 的核心模型 |
| R-03_EVENT_STREAM_SCHEMA.md | Event Stream，定义了 kernel/event_stream.py 的核心模型 |
| R-04_TOOL_RUNTIME.md | ToolRuntime，定义了 kernel/tool_runtime.py 的核心模型 |
| R-05_CHECKPOINT_DESIGN.md | Checkpoint，定义了 kernel/checkpoint.py 的核心模型 |
| M-01_EVIDENCE_MODEL.md | Evidence 模型，定义了 kernel/evidence.py 的核心模型 |
| M-02_SEVEN_DIMENSION_FRAMEWORK.md | 七维度框架，定义了 kernel/dimension.py 的核心模型 |
| M-03_PROJECT_COGNITIVE_STATE.md | L3 知识，定义了 kernel/l3_writer.py 的核心模型 |
| M-04_COGNITIVE_GRAPH_SCHEMA.md | 认知图谱，定义了 kernel/cognitive_graph.py 的核心模型 |
| AGENTS.md | 编码规范，定义了 import 规则和异常体系 |
