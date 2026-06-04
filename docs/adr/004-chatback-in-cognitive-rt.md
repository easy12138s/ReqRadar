# ADR-004: Chatback 留在 Cognitive Runtime

## Context

Chatback（分析完成后用户追问 Agent 的功能）涉及推理上下文恢复和 Checkpoint 回滚，与 Runtime 状态紧密耦合。需要决定它归属于哪个服务。

## Decision

Chatback 功能保留在 **cognitive-rt** 内部，不作为独立服务。

## Consequence

- **正面**：避免推理状态跨服务传输、Chatback 可直接操作 Session Checkpoint、Context Pipeline 复用、实现简单
- **负面**：cognitive-rt 职责较宽（Session + 推理 + Chatback），未来可能考虑拆分

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| Chatback 独立服务 | 需要跨服务传输完整 Runtime State（AgentState + EvidenceState + DimensionState），序列化成本高且恢复时状态一致性难以保证 |
