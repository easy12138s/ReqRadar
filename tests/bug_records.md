# 测试实施期间发现的项目缺陷记录

本文件仅记录测试建设过程中确认的项目业务缺陷。测试代码、fixture、Mock、测试数据或环境问题不记录在这里，应在测试建设阶段直接修正。

## 记录模板

```markdown
### BUG-YYYYMMDD-序号：标题

- 测试文件：
- 测试用例：
- 复现步骤：
- 期望结果：
- 实际结果：
- 影响范围：
- 是否阻塞后续测试：是/否
- 临时处理：无/xfail(reason="...")
```

## 已发现项目缺陷

### BUG-20260512-001：配置化 JWT 密钥与 Token 签发密钥不一致

- 测试文件：`tests/api/test_auth_api.py`、`tests/api/test_users_api.py`、`tests/api/test_reports_versions_api.py`、`tests/api/test_requirements_api.py`
- 测试用例：需要携带认证 Token 的 API 集成测试
- 复现步骤：使用非默认 `web.secret_key` 创建 FastAPI 应用，通过 `create_access_token()` 或登录接口获取 Token，再访问依赖 `CurrentUser` 的接口
- 期望结果：Token 使用当前应用配置密钥签发，并能被认证依赖校验通过
- 实际结果：`create_access_token()` 使用 `reqradar.web.api.auth.SECRET_KEY` 默认值签发，`get_current_user()` 使用 `request.app.state.secret_key` 校验，密钥不一致时返回 401
- 影响范围：所有启用自定义 JWT 密钥的部署环境，登录后访问受保护接口可能失败
- 是否阻塞后续测试：是
- 临时处理：测试夹具暂时将测试配置密钥设置为当前签发逻辑使用的默认值，继续推进测试套件

### BUG-20260512-002：ZIP 导入路径穿越错误未被 API 层转换为 4xx 响应

- 测试文件：`tests/api/test_projects_api.py`
- 测试用例：`test_create_project_from_zip_rejects_path_traversal`
- 复现步骤：调用 `POST /api/projects/from-zip` 上传包含 `../evil.py` 的 zip 文件
- 期望结果：API 返回 400/422 等客户端错误，并给出安全校验失败提示
- 实际结果：`ProjectFileService.extract_zip()` 抛出 `ValueError` 后未被 API 层捕获，异常直接冒泡导致请求失败
- 影响范围：ZIP 项目导入的安全边界错误响应；服务层安全校验有效，但 Web API 错误处理不友好
- 是否阻塞后续测试：是
- 临时处理：对应测试使用 `pytest.mark.xfail(reason="BUG-20260512-002: ZIP path traversal ValueError is not converted to HTTP 4xx")`

### BUG-20260512-003：RateLimitMiddleware 无法正确获取客户端 IP

- 测试文件：`tests/unit/test_rate_limit.py`
- 测试用例：`test_tracks_per_client_ip`
- 复现步骤：构造带有 `request.client = Address("1.1.1.1", 12345)` 的 Request 对象传入 RateLimitMiddleware.dispatch()
- 期望结果：中间件应从 `request.client.host` 获取到 "1.1.1.1" 并按 IP 分别限流
- 实际结果：日志显示 `client_ip` 被识别为 "unknown"，说明 `request.client.host` 获取失败，导致所有请求被归为同一 "unknown" 组
- 影响范围：生产环境部署时，基于 IP 的速率限制可能失效或行为异常
- 是否阻塞后续测试：否
- 临时处理：跳过该测试用例，使用 xfail 标记
