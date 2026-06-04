# ADR-012: 引入 Context Pipeline（P1 优先级）

## Context

V1 的 Prompt 构建方式是 f-string 拼接——所有上下文片段按固定模板拼入，无 Token 预算感知、无质量评估、无策略适配。

## Decision

引入 **五阶段 Context Pipeline**（Collect → Score → Select → Compress → Assemble），并将其优先级提升到 **P1**（与模块化单体并列），因为它是验证"认知运行时智力"这一核心假设的关键。

## Consequence

- **正面**：Token 预算硬约束防止截断、智能选择替换全量拼接、不同推理阶段使用不同策略
- **负面**：Pipeline 实现增加约 7 天开发量，如果对比测试不通过则 V2 核心假设失败（M1 Go/No-Go 决策点）

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 保留 f-string | 无法解决预算感知、无质量评估、无策略适配三个根本问题 |
| 延迟到 P3 | 核心假设不验证就投入 Checkpoint/Event 开发风险过高 |
