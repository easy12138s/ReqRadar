# ADR-007: uv Workspace Monorepo

## Context

V2 需要管理 7 个服务 + 1 个 Kernel 包的 Python 依赖，Poetry 对 monorepo 支持不完善。需要选择包管理器。

## Decision

使用 **uv** 的 workspace 功能管理 Python monorepo。根 `pyproject.toml` 定义 workspace members，各服务子目录有独立 `pyproject.toml`。

## Consequence

- **正面**：比 Poetry 快 10-100 倍（Rust 实现）、原生 workspace 支持、与 pip 完全兼容、锁文件统一
- **负面**：相对 Poetry 较新，社区插件较少、部分 CI 工具尚未原生支持

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| Poetry（保留 V1 方式） | 无原生 workspace，需要 plugin，monorepo 体验差 |
| PDM | 功能与 uv 重叠但性能较差 |
| pip + requirements.txt | 无锁文件、依赖解析不可靠 |
