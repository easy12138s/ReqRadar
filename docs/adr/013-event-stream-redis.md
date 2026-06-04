# ADR-013: 引入 Event Stream（Redis Streams）

## Context

V1 的推理过程可见性依赖散落日志和 ad-hoc WebSocket 推送，无法结构化回放、追溯和解释推理过程。V2 需要一种结构化的方式来记录每个推理步骤。

## Decision

使用 **Redis Streams** 作为 Event Stream 的传输层，PostgreSQL 作为持久化层。三级事件体系：Session 级 / Reasoning 级 / Cognitive 级。

跨节点 WebSocket 广播通过 **Redis Pub/Sub** 实现。

## Consequence

- **正面**：结构化推理链可回放追溯、Redis Streams 消费者组支持多节点消费、Pub/Sub 天然支持广播
- **负面**：引入 Redis 依赖、Streams 需要定期清理、PEL 积压需要监控

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| Kafka | 运维复杂度过高，对当前规模过度设计 |
| 纯 PostgreSQL NOTIFY/LISTEN | 无持久化消费、无消费者组、消息重放困难 |
