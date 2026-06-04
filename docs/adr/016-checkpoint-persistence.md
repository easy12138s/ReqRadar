# ADR-016: Checkpoint 持久化（cognitive-rt 创建，index-service 存储）

## Context

V2 的核心能力是分析可恢复。需要将 Session 在某一步骤的完整状态持久化，以便中断后恢复。需要决定 Checkpoint 的创建者和存储者。

## Decision

- **cognitive-rt** 负责**创建** Checkpoint（它是 Runtime 状态的唯一持有者）
- **index-service** 负责**持久化存储和查询** Checkpoint（它是认知数据的唯一存储者）
- 存储采用三区模型：热状态（PG JSONB）、冷状态（MinIO）、可重建状态（不持久化）

## Consequence

- **正面**：职责分离清晰（运行时 vs 存储）、Checkpoint 可独立于 cognitive-rt 实例存活（重启后跨实例恢复）、三区存储防止存储膨胀
- **负面**：cognitive-rt 和 index-service 之间存在强耦合（每次推理步骤都需调用）

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| cognitive-rt 自己存储 | 重启丢失、无法跨实例恢复、与其他认知数据割裂 |
| 全量存 MinIO | 查询缓慢（需反序列化全量 JSON）、不利于结构化查询 |
