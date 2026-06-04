# ADR-003: Kernel 最小化（仅类型定义）

## Context

V2 需要在 7 个微服务间共享类型定义、枚举、ORM 模型和异常体系。需要决定共享内核的边界——放多少东西进去。

## Decision

`reqradar-kernel` **仅包含类型定义**，代码总量 ≤ 3000 行。具体包含：Pydantic 模型、SQLAlchemy ORM、枚举、Protocol 接口、异常类、配置基类。

不包含：任何业务逻辑、I/O 操作、算法实现。

## Consequence

- **正面**：零运行时依赖（不依赖数据库/网络/文件）、所有服务可安全引用、不会成为性能瓶颈、版本冲突风险最低
- **负面**：需要在各服务中重复实现 Protocol 的具体类（如 ContextSource 适配器）

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 厚 Kernel（含工具函数） | 会增加 Kernel 的第三方依赖（如 httpx/sqlalchemy），导致版本锁定 |
| 零共享（每个服务独立定义） | 类型不一致、ORM 模型重复定义、迁移时字段遗漏风险高 |
