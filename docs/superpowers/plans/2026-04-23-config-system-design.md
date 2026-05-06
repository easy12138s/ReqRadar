# ReqRadar 配置系统重构设计文档

**日期**: 2026-04-23
**状态**: 已确认
**范围**: 后端配置系统全面重构（文件 + 数据库双层架构）

---

## 1. 设计目标

1. **消除当前配置系统的硬编码和单点问题**
2. **支持三层配置模型**：系统级、项目级、用户级，每层独立管理、热加载
3. **明确划界**：`.reqradar.yaml` 负责基础设施/启动配置，数据库负责业务/运行时配置
4. **支持配置继承与覆盖**：用户级 > 项目级 > 系统级 > YAML 文件 > 代码默认值
5. **敏感值安全管理**：掩码展示、脱敏日志、可选加密存储
6. **零重启热加载**：运行时配置变更仅对新任务生效

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  运行时请求（如启动分析任务）                                  │
├─────────────────────────────────────────────────────────────┤
│  ConfigManager.get("llm.model", context={user_id, project_id})│
├─────────────────────────────────────────────────────────────┤
│  解析优先级（从高到低）                                       │
│  1. 用户级配置 (user_configs)                                │
│  2. 项目级配置 (project_configs)                             │
│  3. 系统级配置 (system_configs)                              │
│  4. .reqradar.yaml 文件                                      │
│  5. Pydantic 代码默认值                                      │
├─────────────────────────────────────────────────────────────┤
│  文件专属配置（仅 .reqradar.yaml）                            │
│  - web.host, web.port, web.database_url                      │
│  - web.secret_key                                            │
│  - log.level                                                 │
│  - llm.api_key（系统兜底）                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 三层配置模型

### 3.1 系统级配置 (`system_configs`)

- **管理者**: 系统管理员（`role=admin`）
- **作用域**: 全局
- **Web 可改**: 是（管理员权限）

### 3.2 项目级配置 (`project_configs`)

- **管理者**: 项目管理员
- **作用域**: 单个项目
- **Web 可改**: 是（项目成员）

### 3.3 用户级配置 (`user_configs`)

- **管理者**: 用户本人
- **作用域**: 该用户所有操作
- **Web 可改**: 是（本人）

---

## 4. 划界原则

### 只能文件配置

| 配置 Key | 原因 |
|:---|:---|
| `web.host` | 启动前绑定地址 |
| `web.port` | 启动前监听端口 |
| `web.database_url` | 连数据库后才能存其他配置 |
| `web.secret_key` | JWT 认证初始化 |
| `web.static_dir` | 启动时挂载静态文件 |
| `log.level` | 日志系统启动时初始化 |
| `llm.api_key` | 系统兜底 Key |

### 可数据库覆盖（热加载）

| 配置 Key | 层级 |
|:---|:---|
| `llm.provider` | U/P/S |
| `llm.model` | U/P/S |
| `llm.base_url` | U/P/S |
| `llm.timeout` | U/P/S |
| `llm.max_retries` | U/P/S |
| `analysis.*` | P/S |
| `web.max_upload_size` | S |
| `web.cors_origins` | S |
| `web.max_concurrent_analyses` | S |
| `web.access_token_expire_minutes` | S |
| `memory.*` | P/S |
| `git.lookback_months` | P/S |

> 上表为示例，架构须支持任意配置 Key 动态扩展。

---

## 5. 配置继承与优先级

```
用户级 > 项目级 > 系统级 > YAML 文件 > 代码默认值
```

**示例**：

```
Key: llm.model

用户 A:         gpt-4o          (用户级)
项目 X:         qwen2.5         (项目级)
系统默认:       gpt-4o-mini     (系统级)
YAML 文件:      deepseek-chat   (文件)
代码默认值:     gpt-4o-mini     (代码)

用户 A 在项目 X 中 → gpt-4o（用户级优先）
用户 B 在项目 X 中 → qwen2.5（项目级）
用户 C 在项目 Y 中 → gpt-4o-mini（系统级）
```

---

## 6. 数据模型

### `SystemConfig`

```python
class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="string", nullable=False)
    # "string" | "integer" | "float" | "boolean" | "json"
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
```

### `ProjectConfig`

```python
class ProjectConfig(Base):
    __tablename__ = "project_configs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="string", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    
    project: Mapped["Project"] = relationship(back_populates="configs")
    
    __table_args__ = (UniqueConstraint("project_id", "config_key", name="uq_project_config_key"),)
```

### `UserConfig`

```python
class UserConfig(Base):
    __tablename__ = "user_configs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="string", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    
    user: Mapped["User"] = relationship(back_populates="configs")
    
    __table_args__ = (UniqueConstraint("user_id", "config_key", name="uq_user_config_key"),)
```

**关系补充**：

```python
# Project 添加
configs: Mapped[list["ProjectConfig"]] = relationship(back_populates="project", cascade="all, delete-orphan")

# User 添加
configs: Mapped[list["UserConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")
```

---

## 7. 核心组件：ConfigManager

### 接口

```python
class ConfigManager:
    def __init__(self, db_session: AsyncSession, file_config: Config): ...
    
    async def get(self, key: str, *, user_id: int|None=None, project_id: int|None=None, default: Any=None, as_type: str|None=None) -> Any: ...
    async def get_str(self, key: str, **kwargs) -> str: ...
    async def get_int(self, key: str, **kwargs) -> int: ...
    async def get_float(self, key: str, **kwargs) -> float: ...
    async def get_bool(self, key: str, **kwargs) -> bool: ...
    async def get_json(self, key: str, **kwargs) -> Any: ...
    async def get_masked(self, key: str, **kwargs) -> str: ...
    
    # Admin
    async def set_system(self, key: str, value: Any, value_type: str|None=None, description: str=""): ...
    async def delete_system(self, key: str): ...
    
    # Project
    async def set_project(self, project_id: int, key: str, value: Any, value_type: str|None=None): ...
    async def delete_project(self, project_id: int, key: str): ...
    
    # User
    async def set_user(self, user_id: int, key: str, value: Any, value_type: str|None=None): ...
    async def delete_user(self, user_id: int, key: str): ...
```

### 类型转换

| value_type | 存储 | 读取 |
|:---|:---|:---|
| `string` | 原字符串 | `str(value)` |
| `integer` | 原字符串 | `int(value)` |
| `float` | 原字符串 | `float(value)` |
| `boolean` | `"true"`/`"false"` | 大小写不敏感比较 |
| `json` | JSON 字符串 | `json.loads(value)` |

### 敏感值掩码

- 长度 ≤ 8: `***`
- 长度 > 8: 前3位 + `***` + 后3位
- 示例: `sk-abc123def456` → `sk-***456`

---

## 8. API 设计

### 系统级

```
GET    /api/configs/system                    # 列出（掩码）
GET    /api/configs/system/{key}              # 获取（掩码）
PUT    /api/configs/system/{key}              # 创建/更新
DELETE /api/configs/system/{key}              # 删除
```

### 项目级

```
GET    /api/projects/{project_id}/configs
GET    /api/projects/{project_id}/configs/{key}
PUT    /api/projects/{project_id}/configs/{key}
DELETE /api/projects/{project_id}/configs/{key}
```

### 用户级

```
GET    /api/me/configs
GET    /api/me/configs/{key}
PUT    /api/me/configs/{key}
DELETE /api/me/configs/{key}
```

### 解析查询

```
GET    /api/configs/resolve?key=llm.model&project_id=1
```

---

## 9. 安全设计

| 场景 | 处理 |
|:---|:---|
| GET API | 掩码展示 |
| PUT API | 传值更新，不传保持，传`""`删除 |
| 数据库存储 | 默认明文，后续可选 AES |
| 日志 | 禁止打印，用 `[SENSITIVE]` 占位 |
| WebSocket | 不包含配置值 |

**权限**:
- 系统级: `role == "admin"`
- 项目级: `owner_id == current_user.id`（后续扩展成员角色）
- 用户级: `user_id == current_user.id`

---

## 10. 改造范围

### 新增

| 文件 | 职责 |
|:---|:---|
| `web/models/config.py` | 三个 Config 模型 |
| `infrastructure/config_manager.py` | ConfigManager |
| `web/api/configs.py` | API 端点 |
| `alembic/versions/` | 迁移脚本 |

### 修改

| 文件 | 改动 |
|:---|:---|
| `infrastructure/config.py` | 标记文件专属 Key；衔接 ConfigManager |
| `web/models.py` | 新增模型 + 关系 |
| `web/app.py` | CORS 动态配置；ConfigManager 挂载；注册 router |
| `web/services/analysis_runner.py` | 任务启动时从 ConfigManager 读取；用户 API Key |
| `web/api/analyses.py` | 上传限制；传递 user_id |
| `web/api/auth.py` | token 过期时间动态配置 |
| `web/api/projects.py` | 索引参数动态配置 |
| `pyproject.toml` | 新增快捷脚本 |

### 废弃

- `Project.config_json`：功能由 `ProjectConfig` 替代

---

## 11. 实施计划

**Phase 1**: 数据库模型 + ConfigManager + 单元测试
**Phase 2**: 三层配置 API + API 测试
**Phase 3**: 存量系统改造（app.py / analysis_runner / analyses / auth / projects）
**Phase 4**: 工程化（脚本 / health check / 文档）
