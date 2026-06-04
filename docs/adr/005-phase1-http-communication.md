# ADR-005: Phase 1 使用 HTTP 通信

## Context

V2 微服务间需要通信协议。gRPC 性能更优但初期复杂度高。需要决定默认通信协议。

## Decision

**Phase 1-8** 使用 HTTP/REST + JSON，**Phase 10** 将热点路径（cognitive-rt → index-service）升级为 gRPC。

## Consequence

- **正面**：开发/调试简单（curl/Postman 可直接测试）、与 FastAPI 生态无缝集成、团队学习成本低
- **负面**：序列化开销较 gRPC 大、无内置流式传输、热点路径延迟可能成为瓶颈

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 全 gRPC | 开发调试不便（需 grpcurl）、FastAPI gRPC 支持不成熟、初期过度设计 |
| 消息队列（RabbitMQ/Kafka） | 运维复杂度高，P0-P5 阶段无需异步解耦 |
