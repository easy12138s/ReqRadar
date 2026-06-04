# ADR-011: CognitiveSession 为一等公民

## Context

V1 中以 `AnalysisTask`（数据库记录）为核心抽象，分析过程中状态散落在 `progress_snapshot` JSON 和 ad-hoc WebSocket 推送中。恢复分析只能从头开始。

## Decision

将 **CognitiveSession** 提升为 Runtime 的**一等公民实体**——它不是数据库记录，而是 Session/Context/Event/Checkpoint/Cognitive State 五个子系统的聚合载体。

## Consequence

- **正面**：分析可中断恢复、推理过程可回放追溯、状态管理清晰统一
- **负面**：抽象层次较 V1 高，实现复杂度增加

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 保留 AnalysisTask + JSON blob | 无法实现分析恢复、状态分散难以一致管理、不支持 Checkpoint |
