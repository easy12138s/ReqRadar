# ReqRadar Code Wiki

> 需求透镜 — AI 编程时代的项目需求中间层
>
> 版本：0.8.0 | 许可证：MIT | Python 3.12+

---

## 目录

- [1. 项目概览](#1-项目概览)
- [2. 系统架构](#2-系统架构)
- [3. 目录结构](#3-目录结构)
- [4. 后端模块详解](#4-后端模块详解)
  - [4.1 Agent 模块](#41-agent-模块)
  - [4.2 Web 模块](#42-web-模块)
  - [4.3 Core 模块](#43-core-模块)
  - [4.4 Infrastructure 模块](#44-infrastructure-模块)
  - [4.5 Modules 模块](#45-modules-模块)
  - [4.6 MCP 模块](#46-mcp-模块)
  - [4.7 CLI 模块](#47-cli-模块)
- [5. 前端架构](#5-前端架构)
- [6. 数据模型](#6-数据模型)
- [7. API 端点参考](#7-api-端点参考)
- [8. 关键类与函数速查](#8-关键类与函数速查)
- [9. 依赖关系图](#9-依赖关系图)
- [10. 配置系统](#10-配置系统)
- [11. 测试体系](#11-测试体系)
- [12. 构建与部署](#12-构建与部署)
- [13. 代码规范](#13-代码规范)

---

## 1. 项目概览

### 1.1 定位

ReqRadar 是一个**需求分析 Agent 平台**（需求透视），旨在 AI 编程时代充当**项目需求中间层**。它通过 AI Agent 自动提取术语、检索代码、识别风险，生成标准化需求文档，并通过内置 MCP Server 为 AI 编码工具（Trae / Cursor / Windsurf / Claude Desktop）提供一致、准确的项目上下文。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| 结构化需求分析 | AI Agent 自动提取术语、检索代码、识别风险，生成标准化需求文档 |
| 自定义报告模板 | 灵活配置报告结构和内容，适配不同团队的评审流程 |
| 项目记忆系统 | 积累领域知识库（术语表、模块关系、历史经验），越用越懂你的项目 |
| 多格式文档支持 | PDF / DOCX / PPTX / XLSX / HTML / Markdown 等格式自动解析 |
| 隐私优先架构 | 本地部署，支持 OpenAI / Ollama / 自定义 LLM 接口 |
| MCP Server 内置 | 随 Web 服务自动启动，AI 编码工具一键接入 |
| 访问密钥管理 | 为每个开发者生成独立授权 Key，支持吊销和审计追踪 |
| 需求发布机制 | 将分析报告发布为稳定版本，MCP 只能查询已确认的需求 |

### 1.3 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLAlchemy 2.0 异步 + SQLite (aiosqlite) / PostgreSQL |
| 数据库迁移 | Alembic |
| LLM 集成 | LiteLLM（统一多模型调用） |
| 向量存储 | ChromaDB + sentence-transformers |
| 认证 | JWT (python-jose) + bcrypt |
| 前端框架 | React 19 + TypeScript |
| 构建工具 | Vite 8 |
| UI 组件库 | Ant Design 6 |
| 状态管理 | @tanstack/react-query 5 + React Context |
| 路由 | React Router 7 |
| HTTP 客户端 | Axios |
| 包管理 | Poetry (后端) + npm (前端) |
| MCP 协议 | fastmcp |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                          前端 (React + TypeScript)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Dashboard │ │ Projects │ │ Analysis │ │ Reports  │ │ Settings │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       └─────────────┴────────────┴────────────┴────────────┘         │
│                          apiClient (Axios)                           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTP / WebSocket
┌──────────────────────────────┴───────────────────────────────────────┐
│                        FastAPI 后端 (Python 3.12+)                    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    API 路由层 (16 个路由器)                     │    │
│  │  auth | projects | analyses | reports | chatback | configs   │    │
│  │  templates | users | requirements | synonyms | releases     │    │
│  │  versions | memory | profile | evidence | mcp               │    │
│  └───────────────────────────┬──────────────────────────────────┘    │
│                              │                                       │
│  ┌───────────────────────────┴──────────────────────────────────┐    │
│  │                    服务层 (10 个服务)                          │    │
│  │  AnalysisRunner | ChatbackService | ReportStorage            │    │
│  │  ProjectStore | ProjectFileService | ProjectIndexService     │    │
│  │  ContentReader | MCPAuditService | MCPAuthService            │    │
│  │  RequirementReleaseService | VersionService                  │    │
│  └───────────────────────────┬──────────────────────────────────┘    │
│                              │                                       │
│  ┌──────────┐  ┌─────────────┴──────────┐  ┌──────────────────┐    │
│  │ Agent 模块│  │   数据访问层 (ORM)      │  │  Modules 模块    │    │
│  │ Analysis │  │   SQLAlchemy Models     │  │  LLM Client     │    │
│  │ Agent    │  │   18 张表               │  │  Code Parser    │    │
│  │ Tools    │  │                         │  │  Git Analyzer   │    │
│  │ Prompts  │  │                         │  │  Vector Store   │    │
│  └──────────┘  └────────────────────────┘  │  Memory         │    │
│                                             └──────────────────┘    │
│  ┌──────────┐  ┌────────────────────────┐  ┌──────────────────┐    │
│  │ MCP 模块 │  │ Infrastructure 模块     │  │  Core 模块       │    │
│  │ Server   │  │ Config | Paths | Log   │  │  Exceptions     │    │
│  │ Auth     │  │ Template Loader        │  │  Context        │    │
│  │ Tools    │  │                        │  │  Report         │    │
│  └──────────┘  └────────────────────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
用户提交需求 → API 路由 → AnalysisRunner → AnalysisAgent
                                              ├── LLM 分析 (LiteLLM)
                                              ├── 代码搜索 (CodeParser + VectorStore)
                                              ├── Git 历史 (GitAnalyzer)
                                              └── 项目记忆 (ProjectMemory)
                                              ↓
                                         生成报告 (Markdown/HTML)
                                              ↓
                                         保存到文件系统 + 数据库
                                              ↓
WebSocket 推送进度 → 前端实时展示
```

---

## 3. 目录结构

```
ReqRadar/
├── .github/                        # GitHub CI/CD 配置
│   └── workflows/
│       └── ci.yml                  # CI 流水线（6 个 Job）
├── alembic/                        # 数据库迁移脚本（10 个版本）
│   ├── env.py                      # 迁移环境配置
│   └── versions/                   # 迁移版本文件
├── frontend/                       # React/TypeScript 前端
│   ├── src/
│   │   ├── api/                    # API 客户端模块（每个后端路由一个文件）
│   │   ├── components/             # 通用 UI 组件
│   │   ├── context/                # React Context (Auth, Theme)
│   │   ├── hooks/                  # 自定义 Hooks
│   │   ├── pages/                  # 页面组件（路由级，懒加载）
│   │   ├── types/                  # TypeScript 类型定义
│   │   ├── constants/              # 常量定义
│   │   ├── App.tsx                 # 路由 + Provider 嵌套
│   │   └── main.tsx                # 入口
│   ├── package.json                # 前端依赖
│   ├── vite.config.ts              # Vite 配置
│   └── tsconfig.json               # TypeScript 配置
├── scripts/                        # 构建与部署脚本
│   ├── build-package.sh            # 打包脚本
│   ├── deploy.sh                   # Linux/macOS 部署
│   └── deploy.ps1                  # Windows 部署
├── reqradar/                   # Python 后端源码
│   ├── agent/                      # 核心分析 Agent
│   │   ├── prompts/                # 提示词模板
│   │   ├── tools/                  # Agent 工具集
│   │   ├── analysis_agent.py       # 分析 Agent 主体
│   │   ├── runner.py               # Agent 运行器
│   │   └── schemas.py              # 数据模式
│   ├── cli/                        # Click CLI 命令
│   │   ├── main.py                 # CLI 入口
│   │   ├── analyses.py             # 分析命令
│   │   ├── projects.py             # 项目命令
│   │   └── ...
│   ├── core/                       # 领域模型与异常体系
│   │   ├── exceptions.py           # 异常层次结构
│   │   ├── context.py              # 运行时上下文
│   │   └── report.py               # 报告渲染器
│   ├── infrastructure/             # 基础设施层
│   │   ├── config.py               # Pydantic 配置模型
│   │   ├── paths.py                # 路径管理
│   │   ├── logging.py              # 日志配置
│   │   └── template_loader.py      # 模板加载器
│   ├── mcp/                        # MCP 协议实现
│   │   ├── auth.py                 # MCP 认证
│   │   ├── tools.py                # MCP 工具定义
│   │   └── lifecycle.py            # MCP 生命周期
│   ├── modules/                    # 功能模块
│   │   ├── loaders/                # 文档加载器
│   │   ├── llm_client.py           # LiteLLM 客户端
│   │   ├── code_parser.py          # 代码解析器
│   │   ├── git_analyzer.py         # Git 分析器
│   │   ├── memory.py               # 记忆系统
│   │   └── vector_store.py         # 向量存储
│   ├── templates/                  # 报告模板 (YAML + Jinja2)
│   └── web/                        # FastAPI Web 应用
│       ├── api/                    # API 路由层（16 个路由器）
│       ├── services/               # 业务逻辑层（10 个服务）
│       ├── middleware/              # 中间件（限流）
│       ├── app.py                  # 应用工厂
│       ├── database.py             # 数据库引擎
│       ├── models.py               # ORM 模型（18 张表）
│       ├── dependencies.py         # 依赖注入
│       └── websocket.py            # WebSocket 管理
├── tests/                          # 测试套件
│   ├── conftest.py                 # 共享 Fixtures
│   ├── factories.py                # 测试数据工厂
│   ├── helpers/                    # 测试辅助工具
│   ├── unit/                       # 单元测试（21 个文件）
│   ├── integration/                # 集成测试
│   │   ├── api/                    # API 集成测试（11 个文件）
│   │   └── cli/                    # CLI 集成测试（4 个文件）
│   └── e2e/                        # 端到端测试（9 个文件）
├── pyproject.toml                  # Python 项目配置
├── alembic.ini                     # Alembic 配置
├── .env.example                    # 环境变量模板
└── .pre-commit-config.yaml         # Pre-commit 钩子
```

---

## 4. 后端模块详解

### 4.1 Agent 模块

**路径**: `reqradar/agent/`

Agent 模块是 ReqRadar 的核心智能层，负责执行需求分析的完整 AI 流程。

#### 4.1.1 核心组件

| 文件 | 职责 | 关键类/函数 |
|------|------|------------|
| `analysis_agent.py` | 分析 Agent 主体 | `AnalysisAgent` — ReAct 模式的分析 Agent，协调工具调用与 LLM 推理 |
| `runner.py` | Agent 运行器 | `run_react_analysis()` — 执行完整的 ReAct 分析循环 |
| `dimension.py` | 分析维度 | 定义需求分析的多个评估维度 |
| `evidence.py` | 证据收集 | 收集和组织分析过程中的证据链 |
| `llm_utils.py` | LLM 工具函数 | LLM 调用辅助函数 |
| `memory_evolution.py` | 记忆进化 | 基于分析结果更新项目记忆 |
| `project_profile.py` | 项目画像 | 生成项目的技术栈、模块结构等画像信息 |
| `requirement_preprocessor.py` | 需求预处理 | 多文件合并、格式转换、结构化处理 |
| `schemas.py` | 数据模式 | Agent 内部使用的 Pydantic 数据模型 |
| `tool_call_tracker.py` | 工具调用追踪 | 记录和分析 Agent 的工具调用历史 |

#### 4.1.2 提示词模板 (`prompts/`)

| 文件 | 用途 |
|------|------|
| `analysis_phase.py` | 需求分析阶段的系统提示词 |
| `report_phase.py` | 报告生成阶段的提示词 |
| `chatback_phase.py` | 对话回退阶段的提示词 |
| `memory_evolution.py` | 记忆进化的提示词 |
| `project_profile.py` | 项目画像生成的提示词 |
| `requirement_preprocess.py` | 需求预处理的提示词 |

#### 4.1.3 Agent 工具集 (`tools/`)

Agent 通过工具与外部世界交互，工具采用注册制模式。

| 工具 | 文件 | 功能 |
|------|------|------|
| `search_code` | `search_code.py` | 在项目代码库中搜索相关代码片段 |
| `read_file` | `read_file.py` | 读取指定文件内容 |
| `list_modules` | `list_modules.py` | 列出项目的模块结构 |
| `get_terminology` | `get_terminology.py` | 获取项目术语表 |
| `get_dependencies` | `get_dependencies.py` | 分析项目依赖关系 |
| `get_contributors` | `get_contributors.py` | 获取项目贡献者信息 |
| `get_project_profile` | `get_project_profile.py` | 获取项目画像 |
| `read_module_summary` | `read_module_summary.py` | 读取模块摘要 |
| `search_git_history` | `search_git_history.py` | 搜索 Git 提交历史 |
| `search_requirements` | `search_requirements.py` | 搜索需求文档 |

**工具注册机制** (`tools/registry.py`):
- `ToolRegistry` — 工具注册表，管理所有可用工具
- `BaseTool` (`tools/base.py`) — 工具基类，定义统一接口

**安全机制** (`tools/security.py`):
- 路径遍历防护
- 文件访问权限控制
- 敏感信息过滤

---

### 4.2 Web 模块

**路径**: `reqradar/web/`

Web 模块是 ReqRadar 的 HTTP 服务层，基于 FastAPI 构建，采用经典的三层架构。

#### 4.2.1 应用工厂 (`app.py`)

`create_app(config_path)` — 应用工厂函数，负责：
- 创建 FastAPI 实例
- 注册中间件（CORS + RateLimit）
- 注册异常处理器
- 挂载 16 个 API 路由器
- 配置静态文件服务

`lifespan` — 异步生命周期管理器：

**启动阶段**:
1. 加载配置 → 获取路径 → 创建目录
2. 初始化日志系统
3. 创建数据库引擎和会话工厂
4. 自动建表（首次启动或配置开启时）
5. 任务恢复：将所有 `RUNNING` 状态任务标记为 `FAILED`
6. 种子数据：初始化管理员用户和报告模板
7. 初始化 AnalysisRunner 并发信号量
8. 启动 MCP 服务（如配置启用）

**关闭阶段**: 停止 MCP 服务、释放数据库引擎

#### 4.2.2 数据库层 (`database.py`, `models.py`)

**数据库引擎**:
- `Base(DeclarativeBase)` — SQLAlchemy 声明式基类
- `create_engine()` — 异步引擎工厂，SQLite 启用 WAL 模式 + 外键约束
- `create_session_factory()` — 返回 `async_sessionmaker`

**ORM 模型** (18 张表):

| 模型 | 表名 | 用途 |
|------|------|------|
| `User` | `users` | 用户账户 |
| `RevokedToken` | `revoked_tokens` | 已撤销的 JWT Token |
| `UserConfig` | `user_configs` | 用户级配置 |
| `SystemConfig` | `system_configs` | 系统级配置 |
| `Project` | `projects` | 项目 |
| `ProjectConfig` | `project_configs` | 项目级配置 |
| `RequirementDocument` | `requirement_documents` | 需求文档 |
| `AnalysisTask` | `analysis_tasks` | 分析任务 |
| `Report` | `reports` | 分析报告 |
| `UploadedFile` | `uploaded_files` | 上传文件记录 |
| `PendingChange` | `pending_changes` | 待审核变更 |
| `SynonymMapping` | `synonym_mappings` | 术语同义词映射 |
| `ReportTemplate` | `report_templates` | 报告模板 |
| `ReportVersion` | `report_versions` | 报告版本 |
| `ReportChat` | `report_chats` | 对话记录 |
| `LLMCallLog` | `llm_call_logs` | LLM 调用日志 |
| `MCPAccessKey` | `mcp_access_keys` | MCP 访问密钥 |
| `RequirementRelease` | `requirement_releases` | 需求发布版本 |
| `MCPToolCall` | `mcp_tool_calls` | MCP 工具调用审计 |

#### 4.2.3 依赖注入 (`dependencies.py`)

| 依赖 | 类型 | 说明 |
|------|------|------|
| `get_db` | Generator | 获取数据库会话 |
| `DbSession` | `Annotated[AsyncSession, Depends(get_db)]` | 数据库会话类型别名 |
| `get_current_user` | Dependency | JWT 解码 → 检查撤销列表 → 查询用户 |
| `CurrentUser` | `Annotated[User, Depends(get_current_user)]` | 当前用户类型别名 |
| `get_report_storage` | Dependency | 获取报告存储服务 |
| `get_paths` | Dependency | 获取路径字典 |

#### 4.2.4 API 路由层 (`api/`)

共 16 个路由模块，详见 [API 端点参考](#7-api-端点参考)。

#### 4.2.5 服务层 (`services/`)

| 服务 | 文件 | 职责 |
|------|------|------|
| `AnalysisRunner` | `analysis_runner.py` | 执行完整的分析流程，信号量控制并发 |
| `ChatbackService` | `chatback_service.py` | 报告对话回退服务，意图分类 + LLM 生成 |
| `ReportStorage` | `report_storage.py` | 基于文件系统的报告存储，原子写入 |
| `ProjectStore` | `project_store.py` | LRU 缓存（10 个项目），管理 CodeGraph/VectorStore |
| `ProjectFileService` | `project_file_service.py` | 项目文件系统操作，含安全防护 |
| `ProjectIndexService` | `project_index_service.py` | 异步构建项目索引（代码图 + 向量 + Git + 画像） |
| `ContentReader` | `content_reader.py` | 统一内容读取接口（供 MCP 等外部调用） |
| `MCPAuditService` | `mcp_audit_service.py` | MCP 工具调用审计，自动脱敏 |
| `MCPAuthService` | `mcp_auth_service.py` | MCP 访问密钥管理，bcrypt 哈希存储 |
| `RequirementReleaseService` | `requirement_release_service.py` | 需求发布版本生命周期管理 |
| `VersionService` | `version_service.py` | 报告版本管理，LRU 淘汰 + 回滚 |

#### 4.2.6 中间件 (`middleware/`)

**限流中间件** (`rate_limit.py`):
- 按客户端 IP 限制请求频率（默认 60 次/分钟）
- 跳过 `/health`、`/app` 和 WebSocket 请求
- 内存字典存储请求时间戳
- 超限返回 HTTP 429

#### 4.2.7 WebSocket (`websocket.py`)

`ConnectionManager` — 管理按 `task_id` 分组的 WebSocket 连接集合
- `subscribe(task_id, ws)` — 订阅任务进度
- `unsubscribe(task_id, ws)` — 取消订阅
- `broadcast(task_id, event)` — 并发发送，自动清理断开的连接

#### 4.2.8 异常处理 (`exceptions.py`)

`EXCEPTION_STATUS_MAP` 将领域异常映射到 HTTP 状态码：

| 异常 | HTTP 状态码 |
|------|------------|
| `ParseException` / `LoaderException` | 400 |
| `LLMException` | 502 |
| `VisionNotConfiguredError` | 501 |
| 其他 `ReqRadarException` 子类 | 500 |

#### 4.2.9 种子数据 (`seed.py`)

`seed_all(db)` 在应用启动时执行：
1. 创建默认管理员 `admin@reqradar.io`（密码 `Admin12138%`）
2. 加载默认报告模板
3. 加载 5 个命名模板（general_requirements, security_audit, performance_analysis, ux_review, tech_debt）

---

### 4.3 Core 模块

**路径**: `reqradar/core/`

Core 模块定义了项目的领域模型和异常体系。

#### 4.3.1 异常层次结构 (`exceptions.py`)

```
ReqRadarException (基类)
├── FatalError              # 致命错误
├── ConfigException         # 配置错误
├── LLMException            # LLM 调用异常
├── VectorStoreException    # 向量存储异常
├── GitException            # Git 操作异常
├── IndexException          # 索引异常
├── ReportException         # 报告异常
├── LoaderException         # 文档加载异常
├── ParseException          # 解析异常
└── VisionNotConfiguredError # 视觉模型未配置
```

**链式异常追踪**: 所有异常支持 `cause` 参数，用于保留原始异常信息。

#### 4.3.2 运行时上下文 (`context.py`)

管理分析过程中的运行时状态。

#### 4.3.3 报告渲染器 (`report.py`)

`ReportRenderer` — 使用 Jinja2 模板引擎渲染 Markdown/HTML 报告。

---

### 4.4 Infrastructure 模块

**路径**: `reqradar/infrastructure/`

Infrastructure 模块提供项目的基础设施工具。

#### 4.4.1 配置系统 (`config.py`)

基于 Pydantic v2 的多层配置系统：

```python
class Config(BaseModel):
    home: HomeConfig        # 主目录配置
    llm: LLMConfig          # LLM 配置
    web: WebConfig          # Web 服务配置
    mcp: MCPConfig          # MCP 服务配置
    analysis: AnalysisConfig # 分析配置
    auth: AuthConfig        # 认证配置
```

配置加载优先级: 环境变量 > YAML 文件 > 默认值

#### 4.4.2 路径管理 (`paths.py`)

- `get_paths()` — 获取所有系统路径
- `ensure_dirs()` — 确保目录存在
- `resolve_home()` — 解析主目录路径

#### 4.4.3 日志系统 (`logging.py`)

基于 structlog 的结构化日志系统。

#### 4.4.4 模板加载器 (`template_loader.py`)

从 YAML 文件加载报告模板定义。

#### 4.4.5 配置管理器 (`config_manager.py`)

三级配置管理：系统级 → 项目级 → 用户级，支持配置解析和覆盖。

---

### 4.5 Modules 模块

**路径**: `reqradar/modules/`

Modules 模块提供核心功能模块。

#### 4.5.1 LLM 客户端 (`llm_client.py`)

`LiteLLMClient` — 基于 LiteLLM 的统一 LLM 调用客户端
- `create_llm_client()` — 工厂函数，根据配置创建客户端
- 支持 OpenAI / Ollama / 自定义 API
- 统一的 `complete()` / `complete_structured()` / `stream_complete()` 接口

#### 4.5.2 代码解析器 (`code_parser.py`)

`CodeParser` — Python 代码静态分析
- 提取类、函数、导入关系
- 构建代码图（CodeGraph）
- 输出 `code_graph.json`

#### 4.5.3 Git 分析器 (`git_analyzer.py`)

`GitAnalyzer` — Git 仓库分析
- 提取提交历史
- 分析贡献者信息
- 构建提交向量索引

#### 4.5.4 向量存储 (`vector_store.py`)

`ChromaVectorStore` — 基于 ChromaDB 的向量存储
- 支持 requirements 和 commits 两个集合
- 使用 sentence-transformers 生成嵌入

#### 4.5.5 记忆系统

| 文件 | 类 | 职责 |
|------|-----|------|
| `memory.py` | `ProjectMemory` | 项目级记忆管理（术语表、模块关系、历史经验） |
| `memory_manager.py` | `MemoryManager` | 记忆管理器，协调多个记忆源 |
| `project_memory.py` | - | 项目记忆的具体实现 |
| `user_memory.py` | - | 用户级记忆管理 |
| `pending_changes.py` | `PendingChangeManager` | 待审核变更管理 |
| `synonym_resolver.py` | `SynonymResolver` | 同义词解析器 |

#### 4.5.6 文档加载器 (`loaders/`)

| 加载器 | 文件 | 支持格式 |
|--------|------|----------|
| `TextLoader` | `text_loader.py` | TXT, MD, 代码文件 |
| `ChatLoader` | `chat_loader.py` | 聊天记录格式 |
| `MarkitdownLoader` | `markitdown_loader.py` | PDF, DOCX, PPTX, XLSX (需安装 markitdown) |

**基类** (`base.py`): `BaseLoader` — 定义统一的 `load()` 接口

#### 4.5.7 LLM 连通性 (`llm_connectivity.py`)

LLM 服务可达性检测和状态管理。

---

### 4.6 MCP 模块

**路径**: `reqradar/mcp/`

MCP (Model Context Protocol) 模块实现与 AI 编码工具的标准化接口。

#### 4.6.1 组件

| 文件 | 职责 |
|------|------|
| `auth.py` | MCP 认证机制，验证 Access Key |
| `context.py` | MCP 运行时上下文 |
| `lifecycle.py` | MCP 服务生命周期管理 |
| `schemas.py` | MCP 数据模式定义 |
| `tools.py` | MCP 工具定义（search_published_requirements, get_requirement_context, get_project_memory） |

#### 4.6.2 MCP 工具

| 工具 | 用途 | 关键参数 |
|------|------|---------|
| `search_published_requirements` | 搜索已发布的需求版本 | `project_id`, `query`, `limit` |
| `get_requirement_context` | 获取需求完整上下文 | `release_code`, `version` |
| `get_project_memory` | 查询项目知识库 | `project_id`, `topics` |

#### 4.6.3 安全模型

- **访问控制**: 每个开发者使用独立的 Access Key
- **数据隔离**: MCP 只能读取已发布的需求版本
- **审计追踪**: 所有工具调用记录在案，参数自动脱敏

---

### 4.7 CLI 模块

**路径**: `reqradar/cli/`

CLI 模块提供命令行接口。

#### 4.7.1 命令结构

```
reqradar
├── --version                   # 显示版本
├── serve                       # 启动 Web 服务
├── createsuperuser             # 创建管理员
├── index                       # 索引命令
├── project
│   ├── create                  # 创建项目
│   ├── list                    # 列出项目
│   ├── show                    # 显示项目详情
│   ├── delete                  # 删除项目
│   └── index                   # 构建索引
├── analyze
│   ├── submit                  # 提交分析
│   ├── list                    # 列出分析任务
│   ├── status                  # 查看状态
│   ├── cancel                  # 取消任务
│   └── file                    # 文件分析
├── report
│   ├── get                     # 获取报告
│   ├── versions                # 版本列表
│   └── evidence                # 证据链
├── config
│   ├── init                    # 初始化配置
│   ├── list                    # 列出配置
│   ├── get                     # 获取配置
│   ├── set                     # 设置配置
│   └── delete                  # 删除配置
├── requirement
│   └── preprocess              # 需求预处理
└── mcp
    └── serve                   # MCP 服务
```

---

## 5. 前端架构

### 5.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 8 | 构建工具 |
| Ant Design | 6 | UI 组件库 |
| @tanstack/react-query | 5 | 服务端状态管理 |
| React Router | 7 | 路由 |
| Axios | - | HTTP 客户端 |
| framer-motion | - | 动画 |
| recharts | - | 图表 |
| react-markdown | - | Markdown 渲染 |
| html2pdf.js | - | PDF 导出 |

### 5.2 目录结构

```
frontend/src/
├── api/                    # API 客户端模块
│   ├── client.ts           # Axios 实例，统一拦截器
│   ├── auth.ts             # 认证 API
│   ├── projects.ts         # 项目 API
│   ├── analyses.ts         # 分析 API
│   ├── reports.ts          # 报告 API
│   ├── configs.ts          # 配置 API
│   ├── requirements.ts     # 需求 API
│   ├── templates.ts        # 模板 API
│   ├── synonyms.ts         # 同义词 API
│   ├── releases.ts         # 发布 API
│   ├── versions.ts         # 版本 API
│   ├── memory.ts           # 记忆 API
│   └── profile.ts          # 画像 API
├── components/             # 通用 UI 组件
│   ├── AppShell.tsx        # 应用外壳布局
│   ├── ChatPanel.tsx       # 对话面板
│   ├── FileUploader.tsx    # 文件上传组件
│   ├── ErrorBoundary.tsx   # 错误边界
│   ├── RiskBadge.tsx       # 风险等级徽章
│   └── ...                 # 骨架屏组件等
├── context/                # React Context
│   ├── AuthContext.tsx      # 认证上下文
│   └── ThemeContext.tsx     # 主题上下文
├── hooks/                  # 自定义 Hooks
│   └── useWebSocket.ts     # WebSocket Hook
├── pages/                  # 页面组件（懒加载）
│   ├── Dashboard.tsx       # 仪表板
│   ├── Login.tsx           # 登录页
│   ├── Projects.tsx        # 项目列表
│   ├── ProjectDetail.tsx   # 项目详情
│   ├── AnalysisSubmit.tsx  # 提交分析
│   ├── AnalysisList.tsx    # 分析列表
│   ├── AnalysisProgress.tsx# 分析进度
│   ├── ReportView.tsx      # 报告查看
│   ├── SettingsPage.tsx    # 设置页
│   ├── LLMConfig.tsx       # LLM 配置
│   ├── MCPSettings.tsx     # MCP 设置
│   ├── TemplateManager.tsx # 模板管理
│   ├── SynonymManager.tsx  # 同义词管理
│   ├── RequirementEdit.tsx # 需求编辑
│   ├── ProjectProfile.tsx  # 项目画像
│   ├── UserManagement.tsx  # 用户管理
│   └── ...
├── types/                  # TypeScript 类型定义
├── constants/              # 常量定义
│   └── focusAreas.ts       # 分析焦点领域
├── App.tsx                 # 路由 + Provider 嵌套
└── main.tsx                # 入口
```

### 5.3 状态管理

| 类型 | 方案 | 说明 |
|------|------|------|
| 服务端状态 | @tanstack/react-query | 全局 queryClient，staleTime=5min |
| 客户端全局状态 | React Context | AuthContext（认证）, ThemeContext（主题） |
| 组件本地状态 | useState/useReducer | 仅限纯 UI 状态 |

### 5.4 API 调用模式

统一使用 `apiClient`（基于 Axios 的实例）：
- **请求拦截器**: 自动从 localStorage 读取 `access_token` 并注入 `Bearer` 头
- **响应拦截器**: 自动处理 401（跳转登录）/ 403（权限提示）/ 422（参数错误）/ 5xx（服务器错误）

### 5.5 路由配置

使用 React Router 7，basename 为 `/app`，所有页面组件通过 `React.lazy()` + `Suspense` 懒加载。

### 5.6 构建输出

前端构建产物输出到 `reqradar/web/static`，由 FastAPI 的 StaticFiles 中间件服务。

---

## 6. 数据模型

### 6.1 ER 图（核心实体关系）

```
User (1) ──── (N) Project
  │                 │
  │                 ├── (N) ProjectConfig
  │                 ├── (N) RequirementDocument
  │                 ├── (N) AnalysisTask
  │                 │        ├── (N) Report
  │                 │        ├── (N) ReportVersion
  │                 │        ├── (N) ReportChat
  │                 │        └── (N) UploadedFile
  │                 ├── (N) PendingChange
  │                 ├── (N) SynonymMapping
  │                 └── (N) RequirementRelease
  │
  ├── (N) UserConfig
  ├── (N) MCPAccessKey
  └── (N) RevokedToken

ReportTemplate (独立)
SystemConfig (独立)
LLMCallLog (独立)
MCPToolCall (独立)
```

### 6.2 关键模型字段

#### AnalysisTask

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `project_id` | Integer | 关联项目 |
| `user_id` | Integer | 创建者 |
| `status` | Enum | pending/running/completed/failed/cancelled |
| `requirement_text` | Text | 需求文本 |
| `depth` | Integer | 分析深度 |
| `template_id` | Integer | 使用的模板 |
| `current_version` | Integer | 当前版本号 |
| `progress_snapshot` | JSON | 进度快照 |
| `context_json` | JSON | 分析上下文 |

#### RequirementRelease

| 字段 | 类型 | 说明 |
|------|------|------|
| `release_code` | String | 发布码（如 REQ-LOGIN-001） |
| `version` | String | 版本号（如 v1.0） |
| `status` | Enum | draft/published/archived |
| `title` | String | 标题 |
| `summary` | Text | 摘要 |
| `report_data` | JSON | 报告数据快照 |

---

## 7. API 端点参考

### 7.1 认证 (`/api/auth`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/register` | 用户注册 |
| POST | `/login` | 用户登录 |
| GET | `/me` | 获取当前用户 |
| POST | `/logout` | 注销 |
| PUT | `/me/password` | 修改密码 |

### 7.2 用户管理 (`/api/users`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 列出所有用户（管理员） |
| PUT | `/{user_id}` | 修改用户 |
| DELETE | `/{user_id}` | 删除用户 |

### 7.3 项目 (`/api/projects`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 列出项目 |
| GET | `/dashboard-summaries` | 仪表板摘要 |
| POST | `/from-local` | 从本地路径创建 |
| POST | `/from-zip` | 从 ZIP 创建 |
| POST | `/from-git` | 从 Git 创建 |
| GET | `/{id}` | 获取项目详情 |
| PUT | `/{id}` | 更新项目 |
| DELETE | `/{id}` | 删除项目 |
| GET | `/{id}/files` | 获取文件树 |
| POST | `/{id}/index` | 构建索引 |

### 7.4 分析 (`/api/analyses`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/` | 提交分析 |
| POST | `/upload` | 上传文件分析 |
| GET | `/` | 列出分析任务 |
| GET | `/{task_id}` | 获取任务详情 |
| POST | `/{task_id}/retry` | 重试任务 |
| POST | `/{task_id}/cancel` | 取消任务 |
| WS | `/{task_id}/ws` | WebSocket 进度 |

### 7.5 报告 (`/api/reports`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/{task_id}` | 获取报告 |
| GET | `/{task_id}/markdown` | Markdown 报告 |
| GET | `/{task_id}/html` | HTML 报告 |

### 7.6 版本 (`/api/analyses/{task_id}/reports/versions`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/versions` | 版本列表 |
| GET | `/versions/{ver}` | 版本详情 |
| POST | `/rollback` | 回滚版本 |

### 7.7 对话 (`/api/analyses/{task_id}/chat`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/chat` | 普通对话 |
| POST | `/chat/stream` | 流式对话 (SSE) |
| GET | `/chat` | 对话历史 |
| POST | `/chat/save` | 保存对话结果 |

### 7.8 需求 (`/api/requirements`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/preprocess` | 预处理需求 |
| GET | `/{doc_id}` | 获取需求文档 |
| PUT | `/{doc_id}` | 更新需求文档 |
| DELETE | `/{doc_id}` | 删除需求文档 |
| GET | `/` | 列出需求文档 |

### 7.9 发布 (`/api/releases`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/` | 创建发布版本 |
| GET | `/` | 列出发布版本 |
| GET | `/{id}` | 获取发布详情 |
| PUT | `/{id}` | 更新发布版本 |
| DELETE | `/{id}` | 删除发布版本 |
| POST | `/{id}/publish` | 发布 |
| POST | `/{id}/archive` | 归档 |

### 7.10 配置 (`/api/configs`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/system` | 系统配置列表 |
| GET/PUT/DELETE | `/system/{key}` | 系统配置 CRUD |
| GET | `/projects/{pid}/configs` | 项目配置列表 |
| GET/PUT/DELETE | `/projects/{pid}/configs/{key}` | 项目配置 CRUD |
| GET | `/me/configs` | 用户配置列表 |
| GET/PUT/DELETE | `/me/configs/{key}` | 用户配置 CRUD |
| GET | `/resolve` | 配置解析查询 |
| POST | `/me/test-llm` | LLM 连接测试 |

### 7.11 模板 (`/api/templates`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 模板列表 |
| POST | `/` | 创建模板 |
| GET | `/{id}` | 获取模板 |
| PUT | `/{id}` | 更新模板 |
| DELETE | `/{id}` | 删除模板 |
| POST | `/{id}/set-default` | 设为默认 |

### 7.12 同义词 (`/api/synonyms`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 同义词列表 |
| POST | `/` | 创建同义词 |
| PUT | `/{sid}` | 更新同义词 |
| DELETE | `/{sid}` | 删除同义词 |

### 7.13 记忆 (`/api/projects/{pid}`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/terminology` | 术语表 |
| GET | `/modules` | 模块列表 |
| GET | `/team` | 团队成员 |
| GET | `/history` | 分析历史 |

### 7.14 画像 (`/api/projects/{pid}`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/profile` | 获取画像 |
| PUT | `/profile` | 更新画像 |
| GET | `/profile/pending` | 待审核变更 |
| POST | `/profile/pending/{cid}` | 接受变更 |
| POST | `/pending-changes/{cid}/reject` | 拒绝变更 |

### 7.15 证据 (`/api/analyses/{task_id}/evidence`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 证据列表 |
| GET | `/{eid}` | 证据详情 |

### 7.16 MCP (`/api/mcp`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/config` | MCP 配置 |
| PUT | `/config` | 更新配置 |
| GET | `/keys` | 密钥列表 |
| POST | `/keys` | 创建密钥 |
| POST | `/{id}/revoke` | 吊销密钥 |
| POST | `/{id}/re-export` | 重新导出 |
| GET | `/tool-calls` | 审计日志 |
| POST | `/audit/cleanup` | 清理日志 |

### 7.17 其他

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/metrics` | 系统指标 |

---

## 8. 关键类与函数速查

### 8.1 Agent 层

| 类/函数 | 文件 | 职责 |
|---------|------|------|
| `AnalysisAgent` | `agent/analysis_agent.py` | ReAct 模式的分析 Agent |
| `run_react_analysis()` | `agent/runner.py` | 执行完整的 ReAct 分析循环 |
| `ToolRegistry` | `agent/tools/registry.py` | 工具注册表 |
| `BaseTool` | `agent/tools/base.py` | 工具基类 |
| `ReportRenderer` | `core/report.py` | 报告渲染器 |

### 8.2 Web 层

| 类/函数 | 文件 | 职责 |
|---------|------|------|
| `create_app()` | `web/app.py` | FastAPI 应用工厂 |
| `AnalysisRunner` | `web/services/analysis_runner.py` | 分析任务执行器 |
| `ChatbackService` | `web/services/chatback_service.py` | 对话回退服务 |
| `ReportStorage` | `web/services/report_storage.py` | 报告文件存储 |
| `ProjectStore` | `web/services/project_store.py` | 项目缓存管理 |
| `ProjectFileService` | `web/services/project_file_service.py` | 项目文件操作 |
| `ProjectIndexService` | `web/services/project_index_service.py` | 项目索引构建 |
| `VersionService` | `web/services/version_service.py` | 版本管理服务 |
| `ConnectionManager` | `web/websocket.py` | WebSocket 连接管理 |

### 8.3 Modules 层

| 类/函数 | 文件 | 职责 |
|---------|------|------|
| `create_llm_client()` | `modules/llm_client.py` | LLM 客户端工厂 |
| `LiteLLMClient` | `modules/llm_client.py` | LiteLLM 统一客户端 |
| `CodeParser` | `modules/code_parser.py` | Python 代码解析器 |
| `GitAnalyzer` | `modules/git_analyzer.py` | Git 仓库分析器 |
| `ChromaVectorStore` | `modules/vector_store.py` | ChromaDB 向量存储 |
| `ProjectMemory` | `modules/memory.py` | 项目记忆管理 |

### 8.4 Infrastructure 层

| 类/函数 | 文件 | 职责 |
|---------|------|------|
| `load_config()` | `infrastructure/config.py` | 加载配置 |
| `Config` | `infrastructure/config.py` | 配置模型 |
| `get_paths()` | `infrastructure/paths.py` | 获取系统路径 |
| `ConfigManager` | `infrastructure/config_manager.py` | 三级配置管理器 |

---

## 9. 依赖关系图

### 9.1 模块间依赖

```
┌─────────────────────────────────────────────────────────────┐
│                        Web 层                                │
│  api/ ──→ services/ ──→ modules/ ──→ infrastructure/        │
│    │         │              │              │                 │
│    │         ▼              ▼              ▼                 │
│    │      models.py     agent/         core/                │
│    │         │              │              ▲                 │
│    └─────────┴──────────────┴──────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 关键依赖链

1. **分析流程**: `api/analyses` → `AnalysisRunner` → `AnalysisAgent` → `tools/*` → `modules/*`
2. **报告生成**: `AnalysisRunner` → `ReportRenderer` → `ReportStorage` → `VersionService`
3. **MCP 调用**: `mcp/tools` → `ContentReader` → `models/*` + `ReportStorage` + `ProjectMemory`
4. **配置解析**: `api/configs` → `ConfigManager` → `infrastructure/config.py`

---

## 10. 配置系统

### 10.1 配置层级

```
系统级配置 (SystemConfig 表)
    ↓ 覆盖
项目级配置 (ProjectConfig 表)
    ↓ 覆盖
用户级配置 (UserConfig 表)
    ↓ 回退
YAML 配置文件 (~/.reqradar/config.yaml)
    ↓ 回退
环境变量 (REQRADAR_*)
    ↓ 回退
默认值
```

### 10.2 配置模型

```python
class Config(BaseModel):
    home: HomeConfig          # 主目录路径
    llm: LLMConfig            # LLM 提供商、模型、API Key
    web: WebConfig            # 主机、端口、调试模式
    mcp: MCPConfig            # MCP 服务配置
    analysis: AnalysisConfig  # 分析深度、并发数
    auth: AuthConfig          # JWT 密钥、过期时间
```

### 10.3 环境变量

| 变量 | 说明 |
|------|------|
| `REQRADAR_SECRET_KEY` | JWT 签名密钥（必填） |
| `OPENAI_API_KEY` | OpenAI API Key |
| `LLM_PROVIDER` | LLM 提供商 |
| `LLM_MODEL` | 模型名称 |
| `OPENAI_BASE_URL` | API 基础 URL |

---

## 11. 测试体系

### 11.1 测试分层

```
tests/
├── unit/                    # 单元测试（21 个文件）
│   ├── test_auth.py         # 认证工具测试
│   ├── test_config.py       # 配置测试
│   ├── test_exceptions.py   # 异常体系测试
│   └── ...
├── integration/             # 集成测试
│   ├── api/                 # API 集成测试（11 个文件）
│   │   ├── test_auth_api.py
│   │   ├── test_projects_api.py
│   │   └── ...
│   └── cli/                 # CLI 集成测试（4 个文件）
└── e2e/                     # 端到端测试（9 个文件）
    ├── test_auth_flow.py
    ├── test_analysis_pipeline.py
    └── ...
```

### 11.2 Fixture 设计

| Fixture | 作用 | 隔离级别 |
|---------|------|----------|
| `test_config` | 创建指向 `tmp_path` 的配置 | 函数级 |
| `db_engine` | 创建异步 SQLite 引擎 | 函数级 |
| `db_session` | 可用的数据库会话 | 函数级 |
| `app` | 完整的 FastAPI 实例 | 函数级 |
| `client` | 异步 HTTP 客户端 | 函数级 |
| `test_user` | 通过 API 创建的测试用户 | 函数级 |
| `test_project` | 通过 API 创建的测试项目 | 函数级 |

### 11.3 测试数据隔离

- **数据库**: 每个测试函数使用独立 SQLite（`tmp_path`）
- **文件系统**: 所有写入使用 `tmp_path`
- **外部服务**: LLM 调用必须 mock
- **认证**: 通过 `hash_password` + `create_access_token` 直接生成

### 11.4 运行测试

```bash
pytest                                        # 所有测试
pytest tests/unit/                            # 单元测试
pytest tests/integration/api/                 # API 集成测试
pytest tests/e2e/                             # 端到端测试
pytest -k "test_register"                     # 关键词过滤
pytest --cov=reqradar --cov-report=html       # 覆盖率报告
```

---

## 12. 构建与部署

### 12.1 开发环境

```bash
# 安装依赖
poetry install
cd frontend && npm ci && cd ..

# 启动开发服务器
reqradar serve --reload

# 前端开发
cd frontend && npm run dev
```

### 12.2 构建

```bash
# 完整构建
scripts/build-package.sh

# 仅前端
cd frontend && npm run build

# 仅后端
poetry build
```

### 12.3 部署

#### Docker 部署

```bash
# 开发环境
docker-compose up -d

# 生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

#### 脚本部署

```bash
# Linux/macOS
./scripts/deploy.sh

# Windows
.\scripts\deploy.ps1
```

#### 手动部署

```bash
poetry install
cd frontend && npm ci && npm run build && cd ..
alembic upgrade head
reqradar serve --host 0.0.0.0 --port 8000
```

### 12.4 数据库迁移

```bash
# 生成迁移
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

---

## 13. 代码规范

### 13.1 语言策略

| 内容 | 语言 |
|------|------|
| 代码注释 / Docstring | 中文 |
| 代码标识符 | 英文 |
| Git 提交信息 | 英文 |
| 测试函数名 | 英文 |

### 13.2 代码风格

- **行长度**: 100 字符
- **格式化工具**: Black + Ruff
- **Lint 规则**: E, F, W, I, N, UP, B, SIM, RUF
- **类型检查**: mypy (Python 3.12)
- **导入顺序**: 标准库 → 第三方 → 本地模块

### 13.3 命名规范

| 元素 | 风格 | 示例 |
|------|------|------|
| 模块/文件 | `snake_case` | `llm_client.py` |
| 类 | `PascalCase` | `AnalysisAgent` |
| 函数/方法 | `snake_case` | `create_llm_client` |
| 私有属性 | `_leading_underscore` | `_cancelled` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_STEPS` |

### 13.4 Git 提交规范

```
<type>(<scope>): <short description>

type: feat / fix / refactor / docs / chore / style / test / ci / perf
scope: 可选，影响模块名
```

### 13.5 Pre-commit Hooks

- `trailing-whitespace` — 去除行尾空格
- `end-of-file-fixer` — 确保文件以换行结尾
- `black` — 代码格式化
- `ruff` — Lint + 自动修复
- `mypy` — 类型检查

---

## 附录 A: 默认账号

| 字段 | 值 |
|------|-----|
| 邮箱 | `admin@reqradar.io` |
| 密码 | `Admin12138%` |

## 附录 B: 服务地址

| 服务 | 地址 |
|------|------|
| Web UI | http://localhost:8000/app/ |
| API 文档 | http://localhost:8000/docs |
| MCP Server | http://localhost:8765/mcp |

## 附录 C: 存储路径

所有数据存储在 `~/.reqradar/` 下：

| 路径 | 用途 |
|------|------|
| `~/.reqradar/config.yaml` | 用户配置 |
| `~/.reqradar/reports/` | 生成的报告 |
| `~/.reqradar/memory/` | 项目记忆数据 |
| `~/.reqradar/indexes/` | ChromaDB 向量索引 |
