# ADR-010: api-service 采用 BFF 模式

## Context

V2 有多种前端消费端（Web UI、CLI、未来可能的 MCP Client）。如果各消费端直接调用后端微服务，会导致接口耦合、权限逻辑分散。

## Decision

api-service 采用 **BFF（Backend for Frontend）** 模式，作为前端的唯一聚合层。前端只与 api-service 通信，api-service 负责路由转发、响应聚合、协议转换。

## Consequence

- **正面**：前端只需知道一个服务地址、认证逻辑集中在 BFF、可按前端需求定制响应格式（无需修改后端服务）
- **负面**：增加一跳网络延迟（<5ms 内网延迟）

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 前端直连各服务 | 前端需要知道 7 个服务地址、认证逻辑重复、响应格式差异需要前端适配 |
