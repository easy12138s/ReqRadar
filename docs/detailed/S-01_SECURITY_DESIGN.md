# S-01 安全设计专篇

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 安全设计的完整规格，为 P2 Auth 独立化和服务拆分提供安全基线 |
| 前置文档 | 02_SYSTEM_ARCHITECTURE.md（架构设计、服务拓扑）、I-01_SERVICE_API_CONTRACT.md（服务间 API 契约）、C-04_API_CONTRACT_REGISTRY.md（外部 API 契约） |
| 核心目标 | 定义威胁模型、认证流程、授权矩阵、数据保护策略、审计日志规范，确保系统安全可审计 |
| 文档职责 | What & How — 有哪些安全风险、如何防御、如何审计 |

---

## 2. 威胁模型（STRIDE）

### 2.1 资产清单

| 资产 | 敏感级别 | 存储位置 | 威胁优先级 |
|------|---------|---------|-----------|
| 用户密码哈希 | 高 | PostgreSQL `users.hashed_password` | **P0** |
| JWT Secret Key | 高 | auth-service 环境变量 | **P0** |
| Internal-API-Key | 高 | 各服务环境变量 / Docker secrets | **P0** |
| LLM API Key | 高 | PostgreSQL `system_configs`（加密存储） | **P0** |
| MCP Access Key（哈希） | 高 | PostgreSQL `mcp_access_keys` | **P1** |
| 用户上传的需求文档 | 中 | MinIO L0 | P1 |
| 项目源代码快照 | 中 | MinIO L0 | P1 |
| L3 项目认知知识 | 中 | PostgreSQL L3 表 | P1 |
| Session 推理记录 | 低 | PostgreSQL L2 表 | P2 |
| Event Stream 事件数据 | 低 | Redis Streams | P2 |
| 健康检查端点 | 无 | Traefik 公开 | — |

### 2.2 STRIDE 分析

| 威胁类别 | 威胁描述 | 影响资产 | 风险等级 | 缓解措施 |
|---------|---------|---------|---------|---------|
| **S**poofing（身份伪造） | 攻击者伪造 JWT 访问 API | 全部 API | 高 | JWT 签名验证 + 短期过期 + 吊销列表 |
| **S**poofing | 外部请求绕过 Traefik 直连内部服务 | 内部 API | 高 | Docker 网络隔离 + Internal-API-Key |
| **T**ampering（数据篡改） | 中间人篡改 HTTP 请求/响应 | 传输中数据 | 中 | TLS 1.3（Traefik 终止） |
| **T**ampering | 恶意用户篡改 Evidence 记录 | L2 数据 | 低 | L2 记录 append-only |
| **R**epudiation（抵赖） | 用户否认执行了分析操作 | 审计链路 | 中 | 操作审计日志 |
| **I**nfo Disclosure（信息泄露） | 堆栈信息泄露到 API 错误响应 | 内部实现 | 中 | 统一错误处理器脱敏 |
| **I**nfo Disclosure | 日志中泄露 API Key / Token | 敏感凭证 | 高 | 日志自动脱敏 + 预提交检查 |
| **I**nfo Disclosure | 路径遍历读取服务器文件 | 文件系统 | 高 | 路径规范化 + 白名单校验 |
| **D**oS（拒绝服务） | 恶意高频 API 调用耗尽资源 | 服务可用性 | 中 | 多层速率限制 |
| **D**oS | WebSocket 连接数耗尽 | WS 服务 | 中 | 单用户连接数限制 |
| **E**levation（权限提升） | 普通用户调用管理员接口 | 管理 API | 高 | Scope×Domain 权限矩阵 + 中间件校验 |
| **E**levation | 用户 A 访问用户 B 的项目 | 项目数据 | 高 | 资源归属校验 |

---

## 3. 认证流程设计

### 3.1 JWT 认证流程

```
┌────────┐     ┌────────────┐     ┌──────────┐     ┌──────────────┐
│ 前端   │     │ Traefik    │     │ api-svc  │     │ auth-service │
│        │     │ Gateway    │     │ (BFF)    │     │              │
└───┬────┘     └─────┬──────┘     └────┬─────┘     └──────┬───────┘
    │                │                │                   │
    │ POST /login    │                │                   │
    │───────────────►│───────────────►│                   │
    │                │                │ POST /internal/   │
    │                │                │   v2/auth/verify  │
    │                │                │──────────────────►│
    │                │                │                   │ 校验密码
    │                │                │                   │ 签发 JWT
    │                │                │◄──────────────────│
    │                │                │ access_token      │
    │◄───────────────│◄───────────────│ + refresh_token   │
    │                │                │                   │
    │ 后续请求       │                │                   │
    │ Authorization: │                │                   │
    │ Bearer <token> │                │                   │
    │───────────────►│───────────────►│                   │
    │                │                │ POST /internal/   │
    │                │                │   v2/auth/verify  │
    │                │                │──────────────────►│
    │                │                │                   │ 校验签名+过期+吊销
    │                │                │◄──────────────────│
    │                │                │ {valid: true,     │
    │                │                │  user: {...}}     │
    │◄───────────────│◄───────────────│ 业务响应          │
```

### 3.2 Token 生命周期

| Token 类型 | 有效期 | 刷新策略 | 吊销方式 |
|-----------|--------|---------|---------|
| Access Token | 2 小时 | 不支持刷新，过期后用 Refresh Token 换新 | 写入 `revoked_tokens` 表（按 jti） |
| Refresh Token | 7 天 | 换新时同时颁发新 Refresh Token | 写入 `revoked_tokens` 表 |
| Internal-API-Key | 无过期 | 双 key 滚动更新 | 重启服务加载新 key |

### 3.3 JWT Payload 结构

```json
{
  "sub": "user-uuid",
  "jti": "unique-token-id",
  "iat": 1717200000,
  "exp": 1717207200,
  "role": "user",
  "type": "access"
}
```

| 字段 | 说明 |
|------|------|
| `sub` | 用户 UUID |
| `jti` | 唯一 Token ID（用于吊销） |
| `iat` | 签发时间 |
| `exp` | 过期时间 |
| `role` | user / admin |
| `type` | access / refresh |

---

## 4. 授权设计

### 4.1 Scope×Domain 权限矩阵

| | LLM | TOOL | INDEX | RUNTIME | OUTPUT |
|---|-----|------|-------|---------|--------|
| **SYSTEM** | admin 可配 | admin 可配 | admin 可配 | admin 可配 | admin 可配 |
| **PROJECT** | owner 可覆盖 | owner 可配白名单 | owner 可覆盖 | owner 可配预算 | owner 可选模板 |
| **USER** | 自身模型偏好 | 自身工具权限 | 自身检索偏好 | 自身会话限制 | 自身格式偏好 |
| **SESSION** | 会话级覆盖 | 会话级工具集 | — | 会话级预算/策略 | 会话级输出选项 |

### 4.2 资源归属校验

所有涉及项目/分析/Session 的操作必须校验资源归属：

| 资源 | 校验规则 |
|------|---------|
| Project | `project.owner_id == current_user.id` 或 `current_user.role == "admin"` |
| Session | `session.user_id == current_user.id` 或 `session.project.owner_id == current_user.id` |
| Evidence | 通过 `evidence.session_id → session → project` 链校验 |
| L3 Knowledge | 通过 `knowledge.project_id` 校验 |

### 4.3 中间件实现

auth-service 不直接在校验端点返回权限判断，而是在 JWT payload 中携带 `role` 字段。api-service 根据 `role` 和资源归属自行判断：

```python
# api-service 中间件伪代码
async def check_project_access(user: dict, project_id: str, db: AsyncSession) -> bool:
    if user["role"] == "admin":
        return True
    project = await db.get(Project, project_id)
    return project and project.owner_id == user["user_id"]
```

---

## 5. 服务间认证

### 5.1 Internal-API-Key 方案

```
所有服务间 HTTP 调用必须携带：
X-Internal-API-Key: {shared_secret}
```

| 属性 | 值 |
|------|-----|
| 密钥长度 | 256 bits（64 字符 hex） |
| 生成方式 | `openssl rand -hex 32` |
| 存储 | Docker secrets（生产）/ `.env`（开发） |
| 轮换窗口 | 双 key 模式，新旧 key 共存 5 分钟 |
| 验证位置 | 各服务的中间件层 |
| 缺失时的行为 | 返回 403，不暴露任何内部信息 |

---

## 6. 敏感数据保护

### 6.1 凭证存储

| 数据 | 存储方式 | 加密算法 |
|------|---------|---------|
| 用户密码 | PostgreSQL `users.hashed_password` | bcrypt（cost=12） |
| JWT Secret | 环境变量 `JWT_SECRET` | — |
| LLM API Key | PostgreSQL `system_configs` | AES-256-GCM（应用层加密） |
| MCP Access Key | PostgreSQL `mcp_access_keys` | bcrypt 哈希存储，仅导出时显示明文 |
| Internal-API-Key | 环境变量 / Docker secrets | — |

### 6.2 LLM API Key 加密存储

API Key 在写入 PG 前用应用层密钥加密，应用层密钥来自环境变量 `ENCRYPTION_KEY`：

```
存储值 = AES-256-GCM(plaintext_api_key, encryption_key, nonce)
```

读取时解密。`ENCRYPTION_KEY` 丢失则所有已存储的 API Key 不可恢复。

### 6.3 日志脱敏

日志系统必须在输出前自动脱敏以下模式：

| 敏感模式 | 脱敏后 | 检测方式 |
|---------|--------|---------|
| API Key | `sk-***a1b2`（保留后 4 位） | 正则 `/sk-[a-zA-Z0-9]{32,}/` |
| JWT Token | `eyJh***...`（保留前 10 字符） | Header 字段名 `Authorization` |
| 密码字段 | `***` | 字段名为 `password`、`hashed_password` 等 |
| Email | `a***@example.com` | 正则邮箱模式 |

---

## 7. API 安全

### 7.1 CORS 策略

| 环境 | 允许来源 |
|------|---------|
| 开发 | `http://localhost:5173`（Vite dev server） |
| 生产 | 同源（前端由同一 Traefik 服务），不开放跨域 |

### 7.2 速率限制

| 层级 | 限制 | 适用范围 |
|------|------|---------|
| Traefik | 全局 1000 req/s | 所有入口流量 |
| Traefik | `/api/auth/login` 5 req/min/IP | 防暴力破解 |
| FastAPI 中间件 | 60 req/min/IP | 所有 API 端点 |
| WebSocket | 单用户 10 个并发连接 | WS 端点 |

速率限制响应：HTTP 429 + `Retry-After` Header。

### 7.3 请求体大小限制

| 端点 | 限制 |
|------|------|
| 文件上传 | 100MB（Traefik + FastAPI 双重限制） |
| 普通 JSON 请求 | 1MB |
| WebSocket 消息 | 64KB |

### 7.4 路径遍历防护

所有涉及文件路径的用户输入必须经过路径规范化校验：

```python
from pathlib import Path

def safe_resolve(user_path: str, base_dir: Path) -> Path:
    resolved = (base_dir / user_path).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        raise SecurityException("路径遍历攻击被拦截")
    return resolved
```

---

## 8. WebSocket 安全

| 措施 | 说明 |
|------|------|
| Token 传递 | 初次连接时通过查询参数 `?token=jwt` 传递 |
| 连接校验 | api-service 在 WebSocket 握手阶段校验 JWT 有效性 |
| Session 归属 | 校验 `ws_session_id` 对应的 Session 属于当前用户 |
| 连接数限制 | 单用户最多 10 个并发 WS 连接 |
| 心跳超时 | 60s 无 pong 则断开 |
| 消息大小 | 单条消息最大 64KB |

---

## 9. 审计日志

### 9.1 审计事件类型

| 事件 | 记录内容 | 保留期限 |
|------|---------|---------|
| 用户登录成功/失败 | user_id, ip, user_agent, timestamp | 90 天 |
| Token 刷新 | user_id, ip, timestamp | 90 天 |
| 权限变更 | operator_id, target_user_id, old_role, new_role | 永久 |
| MCP Access Key 创建/吊销 | operator_id, key_id, action | 永久 |
| LLM API Key 变更 | operator_id, action, timestamp | 永久 |
| 异常访问（403/429） | user_id(如有), ip, endpoint, timestamp | 30 天 |

### 9.2 审计日志存储

审计日志写入 PostgreSQL `audit_logs` 表：

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    user_id UUID REFERENCES users(id),
    ip_address INET,
    user_agent TEXT,
    resource_type VARCHAR(50),
    resource_id UUID,
    action VARCHAR(50),
    detail JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user_id ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_event_type ON audit_logs(event_type, created_at DESC);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
```

### 9.3 审计日志写入原则

- 异步写入，不阻塞主业务流程
- 写入失败不影响业务响应（fire-and-forget）
- 记录中包含的服务端内部路径需脱敏

---

## 10. 部署安全

| 措施 | 说明 |
|------|------|
| 最小权限容器 | 所有容器以非 root 用户运行 |
| 只读文件系统 | 除 `/tmp`、`/data` 和日志目录外，文件系统只读 |
| 网络隔离 | 内部服务仅通过 Docker 内部网络通信，不暴露端口到宿主机 |
| 密钥注入 | 生产环境通过 Docker secrets 注入，不写入镜像或配置文件 |
| 健康检查不泄露 | `/health` 仅返回 `{"status":"healthy"}`，不暴露依赖状态 |
| 依赖扫描 | CI 中集成 `pip-audit` / `npm audit`，阻断已知漏洞依赖 |

---

## 11. Agent 安全检查清单

编码 Agent 在提交代码前必须确认以下安全项：

```
[ ] 未硬编码任何密钥、密码、Token
[ ] 所有用户输入经过类型、长度、范围校验（Pydantic Field 约束）
[ ] 文件路径操作经过路径遍历防护（safe_resolve 函数）
[ ] 异常消息未暴露内部路径、堆栈、数据库结构
[ ] 日志输出不包含 JWT Token、API Key、密码等敏感信息
[ ] SQL 查询全部使用 ORM 参数化，无字符串拼接
[ ] 资源操作已校验用户归属（project/session/evidence 归属检查）
[ ] 管理类端点已校验 admin 角色
[ ] 新增端点已标注认证要求（Required/Optional/None/Internal）
```
