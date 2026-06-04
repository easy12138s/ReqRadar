# ADR-014: 引入 ToolRuntime

## Context

V1 中 LLM Agent 直接调用工具的 `execute()` 方法，无超时控制、无重试策略、无权限校验、无自动事件记录。

## Decision

在 Agent 和 ToolRegistry 之间插入 **ToolRuntime** 管控中间层。ToolRuntime 不改变工具实现方式，只增加六项管控能力：超时控制、重试策略、权限校验、Checkpoint 记录、事件记录、结果缓存。

## Consequence

- **正面**：工具调用可靠性提升、超时不会无限等待、重试日志可用于调试、事件自动记录无需工具开发者关心
- **负面**：多一层间接调用，增加约 5ms 开销（可忽略）

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 在每个 BaseTool.execute() 中实现管控 | 管控逻辑分散，一致性差，新增工具需重复实现 |
