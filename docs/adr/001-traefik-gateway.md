# ADR-001: Traefik 作为边缘网关

## Context

V2 架构需要统一的入口网关来管理 7+ 微服务的路由、TLS 终止、限流、WebSocket 代理。需要选择一个生产级网关。

## Decision

选择 **Traefik v3** 作为边缘网关。

## Consequence

- **正面**：Docker 原生集成（自动服务发现）、支持动态配置热更新、内置 Let's Encrypt、WebSocket 原生支持、中间件链（限流/头注入/CORS）
- **负面**：学习曲线较 Nginx 高、社区中文资料较少、动态配置 YAML 语法特殊

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| Nginx | 静态配置，服务频繁变更时需要 reload，不适合微服务动态拓扑 |
| Caddy | 功能较 Traefik 少（限流、动态路由），扩展性不足 |
| Kong | 过于重量级，需要独立数据库，对当前 7 服务规模过度设计 |
| Envoy | 运维复杂度高，适合 Service Mesh 而非简单网关 |
