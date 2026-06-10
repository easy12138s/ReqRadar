# MVP-1 Bug Log

## E2E 测试日期：2026-06-10

### BUG-001: numpy 顶层导入导致 4 个服务启动崩溃

- **严重度**: P0
- **状态**: ✅ 已修复
- **影响服务**: auth-service, api-service, cognitive-rt, output-service
- **现象**: 4 个容器全部 `Exited(1)`，日志 `ModuleNotFoundError: No module named 'numpy'`
- **根因**: `reqradar/kernel/__init__.py` 导出 `ReqRadarEmbeddingFunction` → `embedding.py` 顶层 `import numpy as np` → 所有 import `reqradar.kernel` 的服务都需要 numpy，但 Dockerfile 未安装
- **修复**: 将 `embedding.py` 中 `import numpy as np` 改为 `TYPE_CHECKING` 条件导入 + 方法内懒加载
- **修复文件**: `reqradar/kernel/embedding.py`
- **教训**: kernel 包是所有服务的公共依赖，新增模块不得引入重量级顶层依赖（numpy/onnxruntime 等）

### BUG-002: checkpoint 重复 key 错误

- **严重度**: P1
- **状态**: ⬜ 未修复
- **影响服务**: cognitive-rt
- **现象**: `UniqueViolationError: duplicate key value violates unique constraint "uq_checkpoint_session_version"`，Key (session_id, version) 已存在
- **根因**: checkpoint version 自增逻辑存在竞态或重试未跳过已存在版本
- **影响**: 不阻塞主链路（Session 仍能 COMPLETED），但日志刷错误且 checkpoint 可能不完整
- **建议**: checkpoint 写入前先检查版本是否已存在，或用 `ON CONFLICT DO UPDATE`

### BUG-003: evidence 列表为空

- **严重度**: P1
- **状态**: ⬜ 未修复
- **影响服务**: cognitive-rt → BFF
- **现象**: Session COMPLETED 后 `GET /api/v2/sessions/{id}/evidence` 返回 `items: []`
- **根因**: 推理过程中收集的证据未写入 `evidence_records` PG 表，或写入路径有 bug
- **影响**: 报告可能缺少证据支撑，维度评估可能为空
- **建议**: 检查 `runner.py` 中证据收集 → PG 写入链路

### BUG-004: EventPublisher publish 缺少参数

- **严重度**: P2
- **状态**: ⬜ 未修复
- **影响服务**: cognitive-rt
- **现象**: 日志 `publish 调用缺少 message 或 event_record`
- **根因**: EventPublisher.publish() 被调用时参数不完整
- **影响**: 部分事件未正确发布到事件流

### BUG-005: 计划中的 9 步 API 路径与实际不符

- **严重度**: P1（文档级）
- **状态**: ✅ 已在 E2E 脚本中修正
- **差异**:
  - 计划: `POST /api/v2/auth/login` → 实际: 无此端点，需通过 `auth-service /internal/v2/auth/issue` 签发
  - 计划: `GET /api/v2/sessions/{id}/report` → 实际: `POST /api/v2/reports/generate` + `GET /api/v2/reports/{task_id}/status`
  - 计划: `POST /api/v2/projects/{id}/ingest` → 实际路径一致，但需传 `file` + `project_id`
