# 需求：重构 ReqRadar 配置系统，支持三层配置模型与热加载

## 背景

ReqRadar 当前使用单一的 `.reqradar.yaml` 配置文件来管理所有配置，包括 LLM 模型选择、Web 服务端口、分析参数等。随着项目向企业级需求评审平台演进，这种单文件静态配置方案暴露出以下问题：

1. **CORS 中间件硬编码为 `allow_origins=["*"]`**，生产环境存在安全风险，但无法通过配置调整
2. **文件上传无大小限制**，大文件可能打爆服务器内存
3. **JWT Secret 使用默认硬编码值** `"change-me-in-production"`，部署时容易遗漏修改
4. **所有配置必须在 YAML 中修改并重启服务**，无法热加载
5. **不同项目、不同用户需要不同的 LLM 配置**（如不同项目使用不同模型，不同用户有自己的 API Key），单文件无法满足
6. **项目中的 `config_json` 字段是原始字符串**，无 schema、无校验、无 UI 支持
7. **配置加载用 monkey-patch**（`create_app` 里直接替换 `load_config`），代码质量差

## 目标

重构 ReqRadar 配置系统，实现：

1. **三层配置模型**：系统级（全局默认）、项目级（项目专属）、用户级（个人偏好），每层独立管理
2. **配置继承与覆盖**：用户级 > 项目级 > 系统级 > YAML 文件 > 代码默认值
3. **明确划界**：`.reqradar.yaml` 仅保留基础设施/启动配置（host/port/database_url/secret_key/log.level），所有业务/运行时配置迁移到数据库
4. **零重启热加载**：运行时配置变更仅对新任务生效，运行中任务不受影响
5. **敏感值安全管理**：API Key 等敏感配置掩码展示、脱敏日志、数据库可选加密
6. **Web 可配**：管理员可在 Web 上调整系统级配置，项目管理员调整项目级配置，用户调整个人配置

## 详细需求

### 1. 三层配置存储

新增三张数据表：

- `system_configs`：系统级配置，管理员维护，影响全局
- `project_configs`：项目级配置，项目管理员维护，仅影响所属项目
- `user_configs`：用户级配置，用户本人维护，仅影响该用户的操作

每张表至少包含：config_key、config_value、value_type（string/integer/float/boolean/json）、is_sensitive、created_at、updated_at

### 2. 配置解析优先级

运行时按以下优先级解析配置值：

```
用户级配置 (user_configs)     ← 最高优先级
项目级配置 (project_configs)
系统级配置 (system_configs)
.reqradar.yaml 文件            ← 仅用于基础设施配置和业务默认值
Pydantic 代码默认值            ← 最低优先级
```

### 3. 文件专属配置（仅 YAML）

以下配置因服务启动前就必须确定，只能放在 `.reqradar.yaml` 中，不存数据库：

- `web.host`、`web.port` — 启动时绑定地址和端口
- `web.database_url` — 连接数据库后才能存其他配置
- `web.secret_key` — JWT 认证初始化
- `web.static_dir` — 启动时挂载静态文件
- `log.level` — 日志系统启动时初始化
- `llm.api_key` — 系统兜底 API Key（当用户/项目未配置时使用）

### 4. 可数据库覆盖的配置（热加载）

以下配置支持三层继承，运行时从数据库读取：

- `llm.provider`、`llm.model`、`llm.base_url`、`llm.timeout`、`llm.max_retries`
- `analysis.max_similar_reqs`、`analysis.max_code_files`、`analysis.tool_use_enabled`、`analysis.tool_use_max_rounds`、`analysis.tool_use_max_tokens`
- `web.max_upload_size`（MB）、`web.cors_origins`（JSON 数组）、`web.max_concurrent_analyses`、`web.access_token_expire_minutes`
- `memory.enabled`、`memory.storage_path`
- `git.lookback_months`

### 5. 敏感值处理

- GET API 返回时掩码展示（如 `sk-***456`）
- PUT API 写入时：传真实值则更新，不传 value 字段则保持原值，传 `""` 则删除
- 数据库默认明文存储，后续可选 AES 加密
- 日志中绝对禁止打印敏感值，用 `[SENSITIVE]` 占位
- WebSocket 消息中不包含任何配置值

### 6. 类型系统

支持五种 value_type：

- `string`：原样存储和读取
- `integer`：存储为字符串，读取时转换为 int
- `float`：存储为字符串，读取时转换为 float
- `boolean`：存储为 `"true"`/`"false"`，读取时大小写不敏感解析
- `json`：存储为 JSON 字符串，读取时 json.loads

### 7. ConfigManager 核心类

新增 `ConfigManager` 类，统一封装配置读取、解析、类型转换、敏感值掩码：

- `get(key, user_id=None, project_id=None, default=None, as_type=None)` — 按优先级解析配置
- `get_str/get_int/get_float/get_bool/get_json(key, ...)` — 类型安全的快捷方法
- `get_masked(key, ...)` — 返回掩码后的值（用于 API 响应）
- `set_system/set_project/set_user(key, value, ...)` — 写入各层级配置
- `delete_system/delete_project/delete_user(key)` — 删除配置

### 8. API 接口

新增以下 REST API：

**系统级（管理员权限）：**
- `GET /api/configs/system` — 列出所有系统配置（敏感值掩码）
- `GET /api/configs/system/{key}` — 获取单个系统配置
- `PUT /api/configs/system/{key}` — 创建/更新系统配置
- `DELETE /api/configs/system/{key}` — 删除系统配置

**项目级（项目成员权限）：**
- `GET /api/projects/{project_id}/configs`
- `GET /api/projects/{project_id}/configs/{key}`
- `PUT /api/projects/{project_id}/configs/{key}`
- `DELETE /api/projects/{project_id}/configs/{key}`

**用户级（本人权限）：**
- `GET /api/me/configs`
- `GET /api/me/configs/{key}`
- `PUT /api/me/configs/{key}`
- `DELETE /api/me/configs/{key}`

**解析查询：**
- `GET /api/configs/resolve?key=llm.model&project_id=1` — 查看当前生效的解析值

### 9. 存量系统改造

- **app.py**：CORS 中间件从 ConfigManager 读取 `cors_origins`；lifespan 中初始化 ConfigManager
- **analysis_runner.py**：分析任务启动时通过 ConfigManager 获取配置；使用当前用户的 `llm.api_key`
- **analyses.py**：文件上传限制从 ConfigManager 读取 `max_upload_size`
- **auth.py**：token 过期时间从 ConfigManager 读取 `access_token_expire_minutes`
- **projects.py**：索引构建参数从 ConfigManager 读取
- **config.py**：标记哪些 Key 是文件专属；提供文件配置与 ConfigManager 的衔接

### 10. 废弃与兼容

- `Project.config_json` 字段废弃，功能由 `ProjectConfig` 表替代
- 过渡期内，YAML 中的非文件专属配置仍然生效，但优先级低于数据库配置

## 约束条件

- 保持向后兼容：现有 `.reqradar.yaml` 格式不变，仅改变内部解析优先级
- 热加载仅对新任务生效，运行中的分析任务不受影响
- 前端页面本次不开发，优先完成后端 API 和核心逻辑
- 数据库迁移使用 Alembic
- 所有新增代码需通过 pytest 测试（现有 317 个测试不能 break）

## 验收标准

- [ ] 能成功读取任意配置 Key，并按正确优先级返回解析值
- [ ] 三层配置 API 均能正常 CRUD，敏感值正确掩码
- [ ] CORS 白名单可从配置动态调整，无需重启
- [ ] 文件上传大小限制可从配置动态调整
- [ ] 分析任务使用发起者用户的 API Key（如果用户配置了）
- [ ] 现有 317 个测试全部通过
- [ ] 新增 ConfigManager 单元测试覆盖优先级解析逻辑
