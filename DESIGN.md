# ReqRadar 项目设计文档

> 本文档记录项目的核心定位和技术决策，作为长期维护的参考依据。

---

## 一、项目定位

ReqRadar（需求透视）是一个**需求分析 Agent**，服务于需求从提出到开发之间的信息对齐环节。通过聚合散落在需求文档、代码仓库、历史记录中的关键信息，在关键节点为团队提供共用的上下文参考。

核心特征：ReAct Agent 工具增强、固定模板双层报告、确定性优先、结论附证据、隐私优先、记忆驱动。

**不做的事**：不生成代码、不做实时监控、不将原始敏感数据外传。

---

## 二、ReAct Agent 执行模式

AnalysisAgent 迭代循环，10 种工具按需调用，7 维度追踪充分性（understanding/impact/risk/change/decision/evidence/verification），达到步数上限或维度充分后生成报告。

Web 端通过 `analyze submit` 提交任务到后台执行。CLI 提供 `analyze file` 离线分析和项目管理命令。

---

## 三、双层报告

- **决策摘要层**：面向产品/管理层，总体判断 + 结论与证据 + 待定问题
- **技术支撑层**：面向开发者，需求理解 + 影响域 + 风险分析 + 实施建议
- **附录**：三维度质量指标（流程完成度 / 内容完整度 / 证据支撑度）

---

## 四、工具体系

10 种分析工具：search_code、search_requirements、search_git_history、list_modules、get_contributors、read_file、read_module_summary、get_project_profile、get_terminology、get_dependencies

向量库分为 requirements / commits 两个 ChromaDB collection，支持语义搜索需求文档和历史提交。

安全机制：PathSandbox 路径沙箱 + SensitiveFileFilter 敏感文件过滤 + ToolPermissionChecker 权限检查 + ToolCallTracker 去重/轮次/预算管理。

---

## 五、记忆系统

项目记忆（术语、团队、分析历史、模块关联）自动积累，存储在 `.reqradar/memories/`（项目级）和 `.reqradar/user_memories/`（用户级）。分析完成后自动触发记忆自演化（memory_evolution）。后续分析自动注入 LLM prompt。

---

## 六、Web 模块

- **后端**：FastAPI + SQLAlchemy 2 (async) + JWT (HS256, 24h) + WebSocket + SSE 流式
- **前端**：React + TypeScript (strict) + Ant Design + ReactMarkdown + 代码分割
- **文件解析**：基于 Microsoft MarkItDown 统一转换 PDF/DOCX/PPTX/XLSX/HTML/图片/EPUB 为 Markdown，按标题自然分块
- **分析服务**：AnalysisRunner + Semaphore 并发控制 + ReAct 循环 WebSocket 实时进度推送
- **配置**：三级优先级（User > Project > System）+ LLM 连通性缓存（5min TTL）
- **数据库**：SQLite WAL / 通用池化 + auto_create_tables
- **安全**：JWT + bcrypt、RevokedToken 表管理撤销、CORS 生产限制、上传扩展名白名单
- **认证**：种子 admin 用户（admin@reqradar.io / Admin12138%）、密码修改端点、Token 撤销、登出失效
- **需求预处理**：多文件上传 → MarkItDown 转 Markdown → LLM 合并为结构化需求文档
- **报告**：版本管理 + 回滚 + Chatback SSE 流式追问 + 风险等级识别 + 证据链管理
- **需求管理**：预处理需求 CRUD、分析任务关联需求文档
- **证据 API**：证据条目标注、来源追踪
- **用户 API**：用户列表/角色/删除、管理员管理
- **同义词**：业务术语 ↔ 代码术语映射 CRUD（项目级/优先级/来源）
- **LLM 配置**：多 provider 支持（OpenAI / Ollama / 兼容接口）、连通性测试、键值遮盖、缓存 TTL 管理
- **Embedding 模型**：4 种内置模型可选（bge-large-zh / bge-base-zh / bge-small-zh / bge-m3）

---

## 七、CLI

提供离线分析和项目管理命令：project create / analyze file / report get / config set 等。Web 服务通过 `reqradar serve` 启动。完整命令列表见 `reqradar --help`。

---

*最后更新：2026-05-09*
