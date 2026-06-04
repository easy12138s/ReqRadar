# ADR-008: 面向未来用户体验设计

## Context

V1 前端界面围绕"任务列表"范式设计。V2 的核心抽象变为 CognitiveSession、Event Stream、Checkpoint、L3 认知仪表盘。V1 的界面无法承载新的交互范式。

## Decision

V2 前端**不兼容 V1**，全新设计界面和 API 路径（`/api/v2/`），以 V2 认知运行时体验为目标。

## Consequence

- **正面**：不受 V1 遗留设计约束、可充分发挥 V2 Event Stream/Checkpoint/L3 的交互潜力、代码干净无迁移包袱
- **负面**：V1 用户需要适应新界面、前端开发工作量较大（P8）、V1 和 V2 无法平滑过渡

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 渐进式改造 V1 前端 | V1 架构（任务列表范式）与 V2（Session/Event/认知）差异过大，强行改造导致两套范式混杂 |
