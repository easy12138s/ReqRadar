# ADR-002: Auth 独立服务

## Context

V1 中认证逻辑嵌入在单体 FastAPI 应用的 middleware 中。V2 需要支持多服务架构，每个服务都可能需要验证用户身份。如果每个服务各自实现 JWT 验证，会导致密钥分散、吊销不一致的问题。

## Decision

将 Auth 抽离为**独立服务**，作为 JWT 签发与校验的**唯一信任源**。

- auth-service 持有 JWT Secret，签发和校验 Token
- 其他服务不接触 JWT Secret，通过调用 `POST /internal/v2/auth/verify` 校验
- 通过 Internal-API-Key 保护内部调用

## Consequence

- **正面**：JWT Secret 单一存储、吊销列表一致、用户管理集中化、可独立扩缩容
- **负面**：增加一次网络调用（每次 API 请求额外 5ms）、auth-service 成为关键单点

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 共享 JWT Secret | 密钥分散在 7 个服务中，轮换困难，吊销不一致 |
| OAuth2/OIDC Provider | 对内部项目过度设计，当前无多租户/SSO 需求 |
| API Gateway 层校验 | Traefik 不支持复杂 JWT 校验（吊销列表、用户查询） |
