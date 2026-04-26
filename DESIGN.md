# ReqRadar 项目设计文档

> 本文档记录项目的核心定位和技术决策，作为长期维护的参考依据。

---

## 一、项目定位

ReqRadar（需求透视）是一个**需求分析 Agent**，服务于需求从提出到开发之间的信息对齐环节。通过聚合散落在需求文档、代码仓库、历史记录中的关键信息，在关键节点为团队提供共用的上下文参考。

核心特征：固定流程与 ReAct Agent 双引擎、固定模板双层报告、确定性优先、结论附证据、隐私优先、记忆驱动、工具增强。

**不做的事**：不生成代码、不做实时监控、不将原始敏感数据外传。

---

## 二、双引擎执行模式

**Legacy 模式**（CLI `reqradar analyze`）：Scheduler 驱动 6 步固定流程（read → extract → map_keywords → retrieve → analyze → generate），每步可选工具调用循环，有降级策略。

**ReAct Agent 模式**（Web 后端默认）：AnalysisAgent 迭代循环，9 种工具按需调用，7 维度追踪充分性（understanding/impact/risk/change/decision/evidence/verification），达到步数上限或维度充分后生成报告。

---

## 三、双层报告

- **决策摘要层**：面向产品/管理层，总体判断 + 结论与证据 + 待定问题
- **技术支撑层**：面向开发者，需求理解 + 影响域 + 风险分析 + 实施建议
- **附录**：三维度质量指标（流程完成度 / 内容完整度 / 证据支撑度）

---

## 四、工具体系

9 种分析工具：search_code、search_requirements、list_modules、get_contributors、read_file、read_module_summary、get_project_profile、get_terminology、get_dependencies

安全机制：PathSandbox 路径沙箱 + SensitiveFileFilter 敏感文件过滤 + ToolPermissionChecker 权限检查 + ToolCallTracker 去重/轮次/预算管理。

---

## 五、记忆系统

项目记忆（术语、团队、分析历史、模块关联）自动积累，存储在 `.reqradar/memory/`。Web 模式支持项目级 + 用户级双层记忆。后续分析自动注入 LLM prompt。

---

## 六、Web 模块

- **后端**：FastAPI + SQLAlchemy 2 (async) + JWT + WebSocket
- **前端**：React + TypeScript (strict) + Ant Design + 代码分割
- **分析服务**：AnalysisRunner(V1/V2) + Semaphore 并发控制 + WebSocket 实时进度推送
- **配置**：三级优先级（User > Project > System > YAML 文件 > 代码默认值）
- **数据库**：SQLite WAL / 通用池化 + Alembic 迁移
- **安全**：JWT 密钥环境变量、CORS 生产限制、上传扩展名白名单、WebSocket 任务归属校验
- **报告版本**：版本管理 + 回滚 + Chatback 对话式追问

---

*最后更新：2026-04-24*
