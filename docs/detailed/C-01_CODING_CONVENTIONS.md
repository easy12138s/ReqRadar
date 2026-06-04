# C-01 编码规范（Coding Conventions）

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 项目的编码行为宪法——为 AI 编码 Agent 提供精确的行为约束 |
| 前置文档 | AGENTS.md（V1 编码规范）、01_RESTRUCTURE_OVERVIEW.md（V2 架构蓝图）、02_SYSTEM_ARCHITECTURE.md（技术栈） |
| 核心目标 | 消除一切隐式知识依赖，使 AI Agent 在无人工干预下产出的代码风格一致、质量可控、架构合规 |
| 文档职责 | What & How — 每一行代码应遵循什么规则、违反时有什么后果、正确写法是什么样 |

**适用范围**：本文档约束 `reqradar/` 下所有 Python 代码。前端代码规范见 AGENTS.md 前端章节，本文档不覆盖。

**冲突解决**：本文档与 AGENTS.md 冲突时，以本文档为准。AGENTS.md 中未提及的 V2 新增规则，以本文档为准。

---

## 2. 总则

### 2.1 语言策略

| 内容 | 语言 | 示例 |
|------|------|------|
| 代码注释 / Docstring | 中文 | `# 用户密码哈希` |
| 代码标识符 | 英文 | `hash_password`, `CognitiveSession`, `compute_weight` |
| Git 提交信息 | 英文 | `feat(kernel): add session state machine` |
| PR 标题 / 描述 | 英文 | — |
| 测试函数名 | 英文 | `test_session_transition_running_to_completed` |
| 配置键 | 英文 snake_case | `max_execution_time`, `context_budget` |
| 文档 | 中文 | 本文档 |

### 2.2 Python 版本与语法

- **Python 3.12+**，项目锁定 py312
- 使用 `str | None` 而非 `Optional[str]`（详见第 7 节类型注解规范）
- 使用 `list[str]` 而非 `List[str]`，使用 `dict[str, int]` 而非 `Dict[str, int]`
- 使用 `X | Y` 而非 `Union[X, Y]`
- 绝对导入，禁止相对导入（详见第 5 节 Import 规则）

### 2.3 格式化

| 规则 | 值 | 工具 |
|------|-----|------|
| 行宽 | 100 | Black + Ruff |
| 缩进 | 4 空格 | — |
| Ruff lint 规则 | `E, F, W, I, N, UP, B, SIM, RUF` | ruff check |
| E501 | 忽略（Black 处理行宽） | — |
| known-first-party | `["reqradar"]` | ruff isort |
| 引号风格 | double quotes | Black 默认 |
| 尾随空格 | 禁止 | pre-commit |
| 文件末尾换行 | 必须 | pre-commit |

### 2.4 Lint / Format / Typecheck 三件套

```bash
ruff check . && ruff format --check . && mypy .
```

所有代码提交前必须通过三件套检查，无例外。

---

## 3. 目录结构

V2 项目的精确目录树，标注每个目录和关键文件的职责：

```
reqradar/
├── kernel/                  # 核心运行时（不依赖 web 层）
│   ├── __init__.py
│   ├── session.py           # CognitiveSession 生命周期管理
│   ├── context_pipeline.py  # 五阶段上下文管线编排器
│   ├── event_stream.py      # 结构化推理链事件
│   ├── tool_runtime.py      # 工具执行运行时封装
│   ├── checkpoint.py        # 版本化快照管理
│   ├── evidence.py          # Evidence 聚合与证据链
│   ├── dimension.py         # 七维度评估框架
│   ├── l3_writer.py         # L3 知识沉淀写入器
│   ├── cognitive_graph.py   # 认知图谱（接口预留，暂不实现）
│   ├── types.py             # 共享类型定义（ContextKind, SessionStatus 等枚举）
│   ├── exceptions.py        # 异常层次（V2 扩展）
│   └── protocols.py         # Protocol 接口定义（解耦 kernel 与 modules）
│
├── web/                     # FastAPI 层
│   ├── __init__.py
│   ├── app.py               # create_app(), lifespan, 路由注册
│   ├── database.py          # SQLAlchemy async engine, Base, session factories
│   ├── dependencies.py      # DbSession, CurrentUser, get_db, get_current_user
│   ├── models.py            # SQLAlchemy ORM 模型
│   ├── enums.py             # Web 层专用枚举
│   ├── exceptions.py        # FastAPI 异常处理器（映射 domain → HTTP）
│   ├── websocket.py         # WebSocket 连接管理
│   ├── seed.py              # 初始数据种子
│   ├── cli.py               # Click CLI 命令（serve, createsuperuser）
│   ├── middleware/           # 中间件
│   │   ├── __init__.py
│   │   └── rate_limit.py    # 限流中间件
│   ├── api/                 # API 路由
│   │   ├── __init__.py
│   │   ├── v2/              # V2 API 路由（/api/v2/...）
│   │   │   ├── __init__.py
│   │   │   ├── sessions.py  # Session CRUD + 生命周期操作
│   │   │   ├── events.py    # Event Stream 查询
│   │   │   └── ...
│   │   ├── auth.py          # V1 认证路由
│   │   ├── projects.py
│   │   ├── analyses.py
│   │   └── ...              # 其他 V1 路由
│   └── services/            # 业务逻辑
│       ├── __init__.py
│       ├── analysis_runner.py
│       ├── chatback_service.py
│       └── ...
│
├── infrastructure/          # 配置、日志、路径
│   ├── __init__.py
│   ├── config.py            # Pydantic v2 配置模型 + load_config()
│   ├── config_manager.py    # Scope x Domain 配置矩阵
│   ├── logging.py           # structlog 配置
│   ├── paths.py             # get_paths(), ensure_dirs(), resolve_home()
│   ├── registry.py          # 服务注册表
│   ├── template_loader.py   # 报告模板加载
│   └── migrate_report_files.py
│
├── modules/                 # 外部模块适配（llm_client, code_parser 等）
│   ├── __init__.py
│   ├── llm_client.py        # LiteLLM 统一客户端
│   ├── llm_connectivity.py  # LLM 连通性检测
│   ├── code_parser.py       # 代码解析
│   ├── git_analyzer.py      # Git 历史分析
│   ├── memory.py            # 记忆系统
│   ├── memory_manager.py    # 记忆管理器
│   ├── project_memory.py    # 项目记忆
│   ├── user_memory.py       # 用户记忆
│   ├── vector_store.py      # 向量存储（ChromaDB）
│   ├── synonym_resolver.py  # 同义词解析
│   ├── pending_changes.py   # 待处理变更
│   └── loaders/             # 文档加载器
│       ├── __init__.py
│       ├── base.py
│       ├── chat_loader.py
│       ├── chat_types.py
│       ├── markitdown_loader.py
│       └── text_loader.py
│
├── mcp/                     # MCP 协议支持
│   ├── __init__.py
│   ├── auth.py
│   ├── context.py
│   ├── lifecycle.py
│   ├── schemas.py
│   └── tools.py
│
├── cli/                     # Click 命令
│   ├── __init__.py
│   ├── main.py              # 入口命令组
│   ├── analyses.py
│   ├── config.py
│   ├── projects.py
│   ├── reports.py
│   ├── requirements.py
│   ├── mcp_cli.py
│   └── utils.py
│
├── agent/                   # V1 Agent（P1 阶段保留，P3 后逐步迁移至 kernel）
│   ├── __init__.py
│   ├── analysis_agent.py
│   ├── dimension.py
│   ├── evidence.py
│   ├── llm_utils.py
│   ├── memory_evolution.py
│   ├── project_profile.py
│   ├── requirement_preprocessor.py
│   ├── runner.py
│   ├── schemas.py
│   ├── tool_call_tracker.py
│   ├── prompts/             # Prompt 模板
│   └── tools/               # 工具实现
│
├── core/                    # V1 核心模型（P0 后逐步迁移至 kernel）
│   ├── __init__.py
│   ├── context.py
│   ├── exceptions.py        # V1 异常层次（P0 后由 kernel/exceptions.py 替代）
│   └── report.py
│
├── templates/               # 报告模板（YAML + Jinja2）
│   ├── default_report.yaml
│   ├── general_requirements.yaml
│   ├── performance_analysis.yaml
│   ├── report.md.j2
│   ├── security_audit.yaml
│   ├── tech_debt.yaml
│   └── ux_review.yaml
│
└── __init__.py
```

**关键约束**：

- `kernel/` 不依赖 `web/`、`cli/`、`agent/`（详见第 5 节依赖方向）
- `modules/` 通过 Protocol 接口与 `kernel/` 解耦（详见第 5 节）
- `web/api/v2/` 是 V2 新增路由目录，V1 路由保留在 `web/api/` 根目录

---

## 4. 文件命名规则

| 类别 | 命名规则 | 示例 | 说明 |
|------|---------|------|------|
| 模块文件 | `snake_case.py` | `session.py`, `context_pipeline.py` | — |
| Protocol 接口文件 | `{name}_protocol.py` | `l3_writer_protocol.py` | 定义 Protocol 接口，供 modules 实现注入 |
| 测试文件 | `test_{module}_{scenario}.py` | `test_session_transition.py`, `test_context_pipeline_score.py` | 场景名描述测试重点 |
| 配置文件 | `snake_case.yaml` | `default_report.yaml` | — |
| 模板文件 | `snake_case.j2` | `report.md.j2` | Jinja2 模板 |
| 包目录 | `snake_case/` | `kernel/`, `web/api/v2/` | — |
| `__init__.py` | 必须 | 每个包目录下 | 可为空，或导出公共 API |

**禁止**：

- 禁止文件名含大写字母（`Session.py`）
- 禁止文件名含连字符（`context-pipeline.py`）
- 禁止文件名含空格

---

## 5. Import 规则

### 5.1 排序规则

Import 按 Ruff isort 自动排序，顺序为：

1. **标准库**：`import os`, `from pathlib import Path`
2. **第三方库**：`from fastapi import APIRouter`, `from pydantic import BaseModel`
3. **项目内部**：`from reqradar.kernel.exceptions import ReqRadarException`

各组之间空一行。示例：

```python
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.kernel.exceptions import LLMException, SessionError
from reqradar.kernel.types import SessionStatus
from reqradar.web.dependencies import DbSession, CurrentUser
```

### 5.2 绝对导入

所有 import 必须使用绝对路径，禁止相对导入：

```python
# 正确
from reqradar.kernel.exceptions import ReqRadarException
from reqradar.web.dependencies import DbSession

# 禁止
from ..exceptions import ReqRadarException
from .dependencies import DbSession
```

### 5.3 依赖方向

依赖方向严格单向，禁止循环依赖：

```
kernel  ←  web  ←  cli
  ↑          ↑
  └──────────┘
modules
```

| 源 | 可依赖 | 不可依赖 |
|----|--------|---------|
| `kernel/` | 标准库、第三方库、`reqradar.kernel.*` | `web/`, `cli/`, `agent/`, `modules/` |
| `web/` | 标准库、第三方库、`reqradar.kernel.*`, `reqradar.modules.*`, `reqradar.infrastructure.*` | `cli/` |
| `modules/` | 标准库、第三方库、`reqradar.kernel.protocols.*`（Protocol 接口）, `reqradar.infrastructure.*` | `kernel/` 的具体实现类（如 `CognitiveSession`）, `web/`, `cli/` |
| `cli/` | 标准库、第三方库、`reqradar.kernel.*`, `reqradar.web.*`, `reqradar.infrastructure.*` | — |
| `infrastructure/` | 标准库、第三方库 | `kernel/`, `web/`, `modules/` |

### 5.4 Protocol 解耦规则

`modules/` 不得直接 import `kernel/` 的具体实现类，必须通过 Protocol 接口解耦：

```python
# kernel/protocols.py — 定义 Protocol 接口
from typing import Protocol, runtime_checkable

@runtime_checkable
class L3WriterProtocol(Protocol):
    """L3 知识沉淀写入器接口"""

    async def sediment(self, session_id: str, knowledge: dict) -> None:
        ...

@runtime_checkable
class ContextSourceProtocol(Protocol):
    """上下文源接口"""

    async def collect(
        self, session_id: str, project_id: str, query: str, max_items: int = 50,
    ) -> list[dict]:
        ...
```

```python
# modules/llm_client.py — 通过 Protocol 接收依赖
from reqradar.kernel.protocols import L3WriterProtocol

class LiteLLMClient:
    def __init__(self, l3_writer: L3WriterProtocol | None = None):
        self._l3_writer = l3_writer
```

```python
# kernel/session.py — 组装时注入具体实现
from reqradar.modules.llm_client import LiteLLMClient
from reqradar.modules.memory import MemoryManager

class CognitiveSession:
    def __init__(self):
        self._llm_client = LiteLLMClient(l3_writer=self._l3_writer)
```

**规则总结**：

- `kernel/` 定义 Protocol 接口（`kernel/protocols.py`）
- `modules/` 依赖 Protocol 接口，不依赖具体实现类
- `web/` 或 `kernel/` 在组装时注入具体实现
- 禁止 `from reqradar.kernel.session import CognitiveSession` 在 `modules/` 中出现

---

## 6. 命名约定

### 6.1 完整命名表

| 元素 | 风格 | 示例 | 反例 |
|------|------|------|------|
| 模块/文件 | `snake_case` | `session.py`, `context_pipeline.py` | `Session.py`, `contextPipeline.py` |
| 类 | `PascalCase` | `CognitiveSession`, `EvidenceRecord` | `cognitiveSession`, `Cognitive_Session` |
| 函数/方法 | `snake_case` | `create_session`, `compute_weight` | `CreateSession`, `computeWeight` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_EXECUTION_TIME`, `DEFAULT_CONTEXT_BUDGET` | `MaxExecutionTime`, `max_execution_time` |
| Pydantic 模型 | `PascalCase`，无 Model 后缀 | `EvidenceRecord`, `SessionConfig` | `EvidenceRecordModel`, `SessionConfigModel` |
| SQLAlchemy 模型 | `PascalCase`，无 Model 后缀 | `CognitiveSession`, `CheckpointRecord` | `CognitiveSessionModel` |
| Protocol 接口 | `PascalCase` + Protocol 后缀 | `L3WriterProtocol`, `ContextSourceProtocol` | `L3Writer`, `ContextSourceInterface` |
| 枚举类 | `PascalCase` | `SessionStatus`, `ContextKind`, `EvidenceType` | `session_status`, `SESSION_STATUS` |
| 枚举值 | `UPPER_SNAKE_CASE` | `SessionStatus.RUNNING`, `EvidenceType.CODE_EVIDENCE` | `SessionStatus.running`, `EvidenceType.CodeEvidence` |
| 私有属性 | `_leading_underscore` | `_cancelled`, `_current_task_id` | `cancelled_`, `_Cancelled` |
| 配置键 | `snake_case` | `max_execution_time`, `context_budget` | `maxExecutionTime`, `MAX_EXECUTION_TIME` |
| 测试函数 | `test_{unit}_{scenario}` | `test_session_transition_running_to_completed` | `test_running_to_completed` |
| 测试类 | `Test{Unit}` | `TestContextPipeline`, `TestSessionTransition` | `test_context_pipeline`, `ContextPipelineTest` |
| FastAPI 路由变量 | `snake_case` | `session_id`, `project_id` | `sessionId`, `id` |
| Pydantic Field 别名 | `snake_case` | `Field(alias="context_budget")` | `Field(alias="contextBudget")` |

### 6.2 命名语义规则

| 规则 | 说明 | 示例 |
|------|------|------|
| 布尔变量/函数用 is/has/can/should 前缀 | 明确返回值为布尔 | `is_available`, `has_evidence`, `can_resume` |
| 异常类用 Error/Exception 后缀 | 区分异常与普通类 | `SessionError`, `LLMException` |
| 工厂函数用 create_ 前缀 | 明确创建新实例 | `create_session`, `create_llm_client` |
| 验证函数用 validate_/check_ 前缀 | 明确返回校验结果 | `validate_evidence_chain`, `check_quality_gate` |
| 异步函数无特殊前缀 | 不用 `async_` 前缀 | `async def collect()` 而非 `async def async_collect()` |
| Protocol 方法用 `async def` | 保持异步一致性 | `async def sediment(self, ...)` |

---

## 7. 类型注解规范

### 7.1 基本规则

| 规则 | 正确 | 禁止 |
|------|------|------|
| 可选类型用 `T \| None` | `str \| None` | `Optional[str]` |
| 容器类型用小写泛型 | `list[str]`, `dict[str, int]` | `List[str]`, `Dict[str, int]` |
| 联合类型用 `\|` | `int \| float` | `Union[int, float]` |
| SQLAlchemy 列用 `Mapped[type]` | `Mapped[str]`, `Mapped[str \| None]` | `Column(String)` 无注解 |
| FastAPI 依赖用 `Annotated` | `DbSession = Annotated[AsyncSession, Depends(get_db)]` | 手动调用 `Depends()` |
| Protocol 方法用 `async def` + 返回类型 | `async def collect(self) -> list[ContextItem]:` | `async def collect(self):` |

### 7.2 禁止 `Any` 类型

`Any` 类型仅在以下场景可接受（必须注释说明原因）：

```python
# 与外部库交互，无法推断类型
def handle_webhook(payload: dict[str, Any]) -> None:
    # 外部 webhook 格式不可控，无法精确标注
    ...
```

其他所有场景禁止使用 `Any`。如果类型不确定，使用更具体的类型或 `object`。

### 7.3 类型注解示例

```python
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Mapped

from reqradar.kernel.types import SessionStatus


# Pydantic 模型
class SessionConfig(BaseModel):
    context_budget: int = Field(default=128000, gt=0, description="Token 预算上限")
    context_strategy: str = Field(default="risk_analysis", description="Context Pipeline 策略名")
    llm_model: str | None = Field(default=None, description="覆盖默认 LLM 模型")
    tools: list[str] = Field(default_factory=lambda: ["search_code", "get_deps"])


# SQLAlchemy 模型
class CognitiveSessionModel(Base):
    __tablename__ = "cognitive_sessions"

    session_id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"))
    status: Mapped[str] = mapped_column(default="CREATED")
    error_message: Mapped[str | None] = mapped_column(default=None)
    config: Mapped[dict] = mapped_column(JSONB)


# FastAPI 依赖
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
```

---

## 8. 错误处理规范

### 8.1 异常层次图

V2 异常层次继承自 `ReqRadarException`，按模块和场景细分：

```
ReqRadarException                    # 基础异常类
├── FatalError                       # 致命错误 — 终止流程
├── ConfigException                  # 配置错误
├── SessionError                     # Session 相关错误（V2 新增）
│   ├── IllegalTransitionError       # 非法状态转换
│   ├── SessionTimeoutError          # Session 超时
│   └── RecoveryError                # Checkpoint 恢复失败
├── ContextPipelineError             # Context Pipeline 错误（V2 新增）
│   ├── ContextSourceUnavailableError # 数据源不可用
│   ├── TokenBudgetExceededError     # Token 预算超限
│   ├── CompressionError             # 压缩失败
│   └── QualityGateError             # Quality Gate 检查异常
├── CheckpointError                  # Checkpoint 错误（V2 新增）
│   └── CheckpointWriteError         # Checkpoint 写入失败
├── LLMException                     # LLM 调用错误
├── VectorStoreException             # 向量存储错误
├── GitException                     # Git 操作错误
├── IndexException                   # 索引错误
├── ReportException                  # 报告生成错误
├── LoaderException                  # 加载器错误
├── ParseException                   # 解析错误
└── VisionNotConfiguredError         # 视觉模型未配置错误
```

### 8.2 异常选择决策树

```
发生错误
├── 是否可恢复？
│   ├── 否 → FatalError
│   └── 是 → 错误发生在哪个模块？
│       ├── 配置加载/解析 → ConfigException
│       ├── Session 生命周期 → SessionError
│       │   ├── 状态转换非法 → IllegalTransitionError
│       │   ├── 执行超时 → SessionTimeoutError
│       │   └── Checkpoint 恢复失败 → RecoveryError
│       ├── Context Pipeline → ContextPipelineError
│       │   ├── 数据源不可用 → ContextSourceUnavailableError
│       │   ├── Token 预算超限 → TokenBudgetExceededError
│       │   ├── 压缩失败 → CompressionError
│       │   └── Quality Gate 异常 → QualityGateError
│       ├── Checkpoint 写入 → CheckpointWriteError
│       ├── LLM 调用 → LLMException
│       ├── 向量存储 → VectorStoreException
│       ├── Git 操作 → GitException
│       ├── 索引操作 → IndexException
│       ├── 报告生成 → ReportException
│       ├── 文件加载 → LoaderException
│       ├── 内容解析 → ParseException
│       └── 视觉模型未配置 → VisionNotConfiguredError
```

### 8.3 message 格式

异常 message 必须遵循格式：`"{模块}: {具体描述} — {原因}"`

```python
# 正确
raise LLMException("LLM: LiteLLM 调用失败 — 连接超时", cause=e)
raise SessionTimeoutError("Session: 执行超时 — 已运行 1900s，上限 1800s")
raise IllegalTransitionError(
    "Session: 非法状态转换 — COMPLETED -> RUNNING 不允许"
)

# 禁止 — 无模块前缀
raise LLMException("LiteLLM 调用失败", cause=e)

# 禁止 — 无原因说明
raise SessionTimeoutError("执行超时")
```

### 8.4 cause 链接

所有捕获的底层异常必须通过 `cause` 参数链接，禁止吞异常：

```python
# 正确
try:
    result = await llm_client.generate(prompt)
except Exception as e:
    raise LLMException("LLM: 生成失败 — 模型返回异常", cause=e)

# 禁止 — 吞异常
try:
    result = await llm_client.generate(prompt)
except Exception:
    raise LLMException("LLM: 生成失败")

# 禁止 — 裸 except
try:
    result = await llm_client.generate(prompt)
except:
    pass
```

### 8.5 FastAPI 异常处理器映射表

`web/exceptions.py` 中的异常处理器将领域异常映射为 HTTP 状态码：

| 领域异常 | HTTP 状态码 | 说明 |
|---------|------------|------|
| `FatalError` | 500 | 不可恢复的内部错误 |
| `ConfigException` | 500 | 配置错误（服务端问题） |
| `IllegalTransitionError` | 409 | 状态转换冲突 |
| `SessionTimeoutError` | 408 | 请求超时 |
| `RecoveryError` | 409 | 恢复冲突 |
| `ContextSourceUnavailableError` | 503 | 数据源暂不可用 |
| `TokenBudgetExceededError` | 422 | 预算超限（参数错误） |
| `CompressionError` | 500 | 压缩内部错误 |
| `QualityGateError` | 500 | 质量检查内部错误 |
| `CheckpointWriteError` | 503 | 存储暂不可用 |
| `LLMException` | 502 | 上游 LLM 服务错误 |
| `VectorStoreException` | 503 | 向量存储暂不可用 |
| `GitException` | 500 | Git 操作错误 |
| `IndexException` | 500 | 索引错误 |
| `ReportException` | 500 | 报告生成错误 |
| `LoaderException` | 422 | 文件加载错误（参数问题） |
| `ParseException` | 422 | 解析错误（参数问题） |
| `VisionNotConfiguredError` | 501 | 视觉模型未配置 |

### 8.6 禁止事项

| 禁止 | 原因 |
|------|------|
| 裸 `except:` | 无法定位错误类型，吞掉所有异常 |
| `except Exception: pass` | 吞异常，错误不可见 |
| `except Exception: raise Exception("...")` | 丢失原始 cause 链 |
| 在 `kernel/` 中抛出 HTTP 异常 | kernel 不依赖 web 层，不应感知 HTTP 语义 |
| 在异常 message 中暴露内部实现细节 | 可能泄露敏感信息 |

---

## 9. 日志规范

### 9.1 Logger 命名

每个模块使用独立 logger，命名规则：`reqradar.{package}.{module}`

```python
import logging

logger = logging.getLogger("reqradar.kernel.session")
logger = logging.getLogger("reqradar.web.api.v2.sessions")
logger = logging.getLogger("reqradar.modules.llm_client")
```

禁止使用 `__name__` 作为 logger 名称（在包内使用时会产生冗长的 `reqradar.kernel.session` 以外的不一致格式）。

### 9.2 日志级别规则

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| DEBUG | 内部状态、调试信息 | `logger.debug("Session state: %s", session.state)` |
| INFO | 业务事件、流程节点 | `logger.info("Session %s transitioned to RUNNING", session_id)` |
| WARNING | 降级/重试/非预期但可恢复 | `logger.warning("Context source %s unavailable, skipping", source_name)` |
| ERROR | 失败但可恢复 | `logger.error("Checkpoint write failed for session %s", session_id, exc_info=True)` |
| CRITICAL | 不可恢复、系统级错误 | `logger.critical("Database connection lost, shutting down")` |

### 9.3 structlog 格式

生产环境使用 structlog JSON 输出，包含上下文信息：

```python
import structlog

logger = structlog.get_logger("reqradar.kernel.session")

# 结构化日志，包含 session_id / project_id 上下文
logger.info(
    "session_transitioned",
    session_id=str(session_id),
    project_id=str(project_id),
    from_status="READY",
    to_status="RUNNING",
    trigger="user_start",
)
```

**必须包含的上下文字段**：

| 场景 | 必须包含的字段 |
|------|--------------|
| Session 相关 | `session_id`, `project_id` |
| LLM 调用 | `session_id`, `model`, `token_count` |
| 工具调用 | `session_id`, `tool_id`, `duration_ms` |
| Checkpoint | `session_id`, `version`, `type` |
| Context Pipeline | `session_id`, `stage`, `item_count`, `token_count` |

### 9.4 禁止事项

| 禁止 | 原因 | 替代方案 |
|------|------|---------|
| `print()` | 无法控制级别、无法关闭、无法结构化 | `logger.info()` / `logger.debug()` |
| 无 logger 的 `logging.info()` | 无法区分来源 | `logger = logging.getLogger("reqradar.xxx")` |
| f-string 格式化日志 | 延迟格式化失效，性能浪费 | `logger.info("Session %s started", session_id)` |
| 日志中记录敏感信息 | 安全风险 | 脱敏后记录，如 `api_key=***abc` |

---

## 10. 异步规范

### 10.1 规则表

| 规则 | 说明 | 示例 |
|------|------|------|
| FastAPI 端点用 `async def` | FastAPI 原生支持异步 | `async def create_session(request: Request):` |
| 数据库操作用 `async with session.begin()` | 确保事务正确提交/回滚 | `async with session.begin(): session.add(obj)` |
| 后台任务用 `asyncio.create_task()` | fire-and-forget 异步任务 | `asyncio.create_task(run_analysis(session_id))` |
| 禁止 `asyncio.run()` 在 FastAPI 中 | 事件循环已由 FastAPI 管理 | — |
| 禁止 `time.sleep()` 在异步代码中 | 阻塞事件循环 | 用 `await asyncio.sleep()` |
| 禁止同步 IO 在异步端点中 | 阻塞事件循环 | 用 `aiofiles` / `httpx.AsyncClient` |
| 长时间 CPU 密集任务用 `run_in_executor` | 避免阻塞事件循环 | `await asyncio.get_event_loop().run_in_executor(None, cpu_func)` |

### 10.2 后台任务模式

```python
import asyncio

from reqradar.kernel.session import CognitiveSession


async def start_analysis(session_id: str) -> dict:
    """API 端点：启动分析任务"""
    # 创建后台任务，不阻塞 API 响应
    asyncio.create_task(_run_analysis_loop(session_id))
    return {"session_id": session_id, "status": "RUNNING"}


async def _run_analysis_loop(session_id: str) -> None:
    """后台任务：执行推理循环"""
    try:
        session = await load_session(session_id)
        await session.run()
    except Exception as e:
        logger.error("Analysis loop failed: %s", session_id, exc_info=True)
        # 错误处理：更新 Session 状态为 FAILED
```

### 10.3 数据库事务模式

```python
async def create_session_record(
    session: CognitiveSession,
    db: AsyncSession,
) -> None:
    """创建 Session 数据库记录"""
    async with db.begin():
        db.add(CognitiveSessionModel(
            session_id=str(session.session_id),
            project_id=str(session.project_id),
            status=session.status.value,
            config=session.config.model_dump(),
            state=session.state.model_dump(),
        ))
```

---

## 11. Pydantic 模型模板

```python
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SessionConfig(BaseModel):
    """Session 配置模型"""

    model_config = ConfigDict(
        from_attributes=True,  # 支持 SQLAlchemy ORM 转换
        str_strip_whitespace=True,  # 自动去除字符串首尾空格
        frozen=False,  # 是否不可变（按需设置）
    )

    # 字段定义：类型 + Field + 中文 description
    context_budget: int = Field(
        default=128000,
        gt=0,
        description="Token 预算上限",
    )
    context_strategy: str = Field(
        default="risk_analysis",
        description="Context Pipeline 策略名",
    )
    max_execution_time: int = Field(
        default=1800,
        gt=0,
        description="最大执行时间（秒）",
    )
    llm_model: str | None = Field(
        default=None,
        description="覆盖默认 LLM 模型",
    )
    tools: list[str] = Field(
        default_factory=lambda: ["search_code", "get_deps", "read_file"],
        description="允许使用的工具列表",
    )

    # 字段级验证器
    @field_validator("context_strategy")
    @classmethod
    def validate_strategy_registered(cls, v: str) -> str:
        """校验策略名已注册"""
        registered = {"risk_analysis", "architecture_understanding", "evidence_aggregation"}
        if v not in registered:
            raise ValueError(f"未注册的策略名: {v}，可选值: {registered}")
        return v

    # 模型级验证器
    @model_validator(mode="after")
    def validate_config_consistency(self) -> "SessionConfig":
        """校验配置项之间的逻辑一致性"""
        if self.context_budget < 4096:
            raise ValueError("context_budget 不能小于 4096")
        return self


class SessionState(BaseModel):
    """Session 运行时状态"""

    model_config = ConfigDict(from_attributes=True)

    context_usage: int = Field(default=0, ge=0, description="当前已用 Token 数")
    current_step: int = Field(default=0, ge=0, description="当前推理步骤序号")
    current_phase: str = Field(default="INIT", description="当前推理阶段")
    pending_question: str | None = Field(default=None, description="等待用户回答的问题")
    cancel_requested: bool = Field(default=False, description="是否收到取消请求")
```

**模板要点**：

1. `model_config = ConfigDict(from_attributes=True)` — 支持 ORM 转换
2. 所有字段必须有 `Field()` + `description` — 中文描述
3. 数值字段必须有范围约束（`gt`, `ge`, `le` 等）
4. 可选字段用 `str | None = Field(default=None, ...)`
5. 验证器用 `@field_validator` / `@model_validator` — Pydantic v2 语法
6. 验证器方法名用英文，docstring 用中文

---

## 12. FastAPI 端点模板

```python
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from reqradar.kernel.exceptions import IllegalTransitionError, SessionTimeoutError
from reqradar.kernel.types import SessionStatus
from reqradar.web.dependencies import DbSession, CurrentUser

router = APIRouter(prefix="/api/v2/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """创建 Session 请求体"""

    project_id: UUID = Field(description="项目 ID")
    config: SessionConfig | None = Field(default=None, description="Session 配置")


class SessionResponse(BaseModel):
    """Session 响应体"""

    session_id: UUID
    project_id: UUID
    status: SessionStatus
    created_at: str


@router.post("", status_code=201, response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: DbSession,
    user: CurrentUser,
    http_request: Request,
) -> SessionResponse:
    """创建新的 CognitiveSession

    通过 request.app.state 访问全局状态，禁止直接调用 load_config()。
    """
    # 通过 app.state 访问配置（禁止模块级 load_config）
    config = http_request.app.state.config

    # 业务逻辑委托给 service 层
    session = await session_service.create(
        project_id=request.project_id,
        user_id=user["user_id"],
        config=request.config,
        db=db,
    )

    return SessionResponse(
        session_id=session.session_id,
        project_id=session.project_id,
        status=session.status,
        created_at=session.created_at.isoformat(),
    )


@router.post("/{session_id}/start")
async def start_session(
    session_id: UUID,
    db: DbSession,
    user: CurrentUser,
    http_request: Request,
) -> dict:
    """启动 Session 推理循环"""
    try:
        await session_service.start(session_id=session_id, db=db)
    except IllegalTransitionError as e:
        # 异常处理器会转换为 409
        raise
    except SessionTimeoutError as e:
        # 异常处理器会转换为 408
        raise

    return {"session_id": str(session_id), "status": "RUNNING"}
```

**模板要点**：

1. 路由注册在 `APIRouter` 上，V2 路由前缀 `/api/v2/`
2. 通过 `request.app.state.config` 访问配置（禁止 `load_config()` 直接调用）
3. 请求体和响应体使用 Pydantic 模型
4. 业务逻辑委托给 `services/` 层，端点只做参数校验和响应组装
5. 异常直接 raise，由 `web/exceptions.py` 统一处理
6. 依赖注入使用 `Annotated` 类型（`DbSession`, `CurrentUser`）

---

## 13. SQLAlchemy 模型模板

```python
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Base, Mapped, mapped_column, relationship


class CognitiveSessionModel(Base):
    """CognitiveSession ORM 模型"""

    __tablename__ = "cognitive_sessions"

    # 主键：使用 mapped_column + Mapped 类型注解
    session_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 外键
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    # 普通字段
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CREATED",
    )

    # 可空字段：Mapped[str | None]
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    error_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
    )

    # JSONB 字段
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    state: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    status_history: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    # 整数字段
    last_checkpoint_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_reasoning_steps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_tool_calls: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # 时间戳字段
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )

    # 关系定义
    project = relationship("ProjectModel", back_populates="sessions")
    user = relationship("UserModel", back_populates="sessions")
    checkpoints = relationship(
        "CheckpointModel",
        back_populates="session",
        order_by="CheckpointModel.version",
        cascade="all, delete-orphan",
    )
```

**模板要点**：

1. 使用 `Mapped[type]` 类型注解（SQLAlchemy 2.0 风格）
2. 可空字段用 `Mapped[str | None]`，不用 `Optional[str]`
3. 主键默认值用 `default=lambda: str(uuid4())`
4. 时间戳用 `TIMESTAMP(timezone=True)`，默认值用 `datetime.utcnow`
5. JSONB 字段用于存储复杂嵌套结构（config, state, status_history）
6. 关系定义使用 `relationship()`，明确 `back_populates` 和 `cascade`
7. 外键必须指定 `ondelete` 策略

---

## 14. 禁止事项清单

| # | 禁止事项 | 原因 | 替代方案 |
|---|---------|------|---------|
| 1 | 模块级 `load_config()` 直接调用 | 模块级绑定导致 mock 失效，测试无法隔离 | `request.app.state.config` |
| 2 | 页面组件直接 `axios` | 绕过统一拦截器，token 注入和错误处理失效 | `apiClient`（`frontend/src/api/client.ts`） |
| 3 | `Optional[T]` | Python 3.12+ 已有更简洁的语法 | `T \| None` |
| 4 | `List[T]`, `Dict[K, V]` | Python 3.12+ 已支持内置泛型 | `list[T]`, `dict[K, V]` |
| 5 | `Union[X, Y]` | Python 3.12+ 已有更简洁的语法 | `X \| Y` |
| 6 | 相对导入 | 隐式依赖，重构时易遗漏 | 绝对导入 `from reqradar.kernel.xxx import ...` |
| 7 | 裸 `except:` | 吞掉所有异常（含 KeyboardInterrupt），无法定位问题 | `except SpecificException:` |
| 8 | `except Exception: pass` | 吞异常，错误不可见 | 记录日志后 raise 或转换为领域异常 |
| 9 | `print()` | 无法控制级别、无法关闭、无法结构化 | `logger.info()` / `logger.debug()` |
| 10 | 硬编码密钥/密码 | 安全风险，泄露不可控 | 环境变量 + 配置文件 |
| 11 | 拼接 SQL | SQL 注入风险 | ORM（SQLAlchemy）或参数化查询 |
| 12 | 在 `kernel/` 中 import `web/` | 违反依赖方向，kernel 不依赖 web 层 | 通过 Protocol 接口解耦 |
| 13 | 在 `modules/` 中 import `kernel/` 具体实现类 | 违反依赖方向，modules 通过 Protocol 解耦 | `from reqradar.kernel.protocols import XxxProtocol` |
| 14 | `asyncio.run()` 在 FastAPI 中 | 事件循环已由 FastAPI 管理，嵌套循环会崩溃 | `asyncio.create_task()` |
| 15 | `time.sleep()` 在异步代码中 | 阻塞事件循环，所有协程停滞 | `await asyncio.sleep()` |
| 16 | `Any` 类型（除非不可避免） | 丧失类型安全，mypy 无法检查 | 更具体的类型或 `object` |
| 17 | 在 `kernel/` 中抛出 HTTP 异常 | kernel 不依赖 web 层，不应感知 HTTP 语义 | 抛出领域异常，由 `web/exceptions.py` 映射 |
| 18 | 在异常 message 中暴露内部实现 | 安全风险，可能泄露堆栈/路径/密钥 | 脱敏后记录 |
| 19 | f-string 格式化日志 | 延迟格式化失效，性能浪费 | `logger.info("Session %s started", session_id)` |
| 20 | 使用 `__name__` 作为 logger 名称 | 包内使用时产生不一致格式 | `logging.getLogger("reqradar.kernel.session")` |
| 21 | Pydantic 模型加 `Model` 后缀 | 与 SQLAlchemy 模型混淆，命名冗余 | `EvidenceRecord` 而非 `EvidenceRecordModel` |
| 22 | 在循环内发 SQL | N+1 问题，性能灾难 | 批量操作 / `selectinload` / `joinedload` |
| 23 | 代码中使用 emoji | 跨平台显示不一致 | 纯文本 |
