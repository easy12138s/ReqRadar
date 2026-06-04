# ADR-009: Ingestion 独立服务

## Context

V1 中文件解析（PDF/DOCX/代码分析）与 Web 服务同进程运行。大文件处理时 CPU 密集任务会阻塞事件循环，影响 API 响应延迟。

## Decision

将 Ingestion 拆分为**独立服务**，通过异步任务队列处理文件解析。cognitive-rt 通过 HTTP 调用 ingestion-service 触发摄取。

## Consequence

- **正面**：CPU 密集任务不阻塞 API 事件循环、可独立扩容处理节点、失败重试与 Web 请求隔离
- **负面**：增加一次网络调用、需要任务队列管理

## Tradeoff

| 方案 | 放弃原因 |
|------|---------|
| 保留在 Web 进程 | CPU 密集型解析会阻塞事件循环，影响 API P99 延迟 |
