# I-02 部署与 DevOps 详细设计

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | ReqRadar V2 部署架构、CI/CD 流水线、监控告警方案的完整规格 |
| 前置文档 | 02_SYSTEM_ARCHITECTURE.md（部署拓扑、技术栈）、I-01_SERVICE_API_CONTRACT.md（服务间调用）、S-01_SECURITY_DESIGN.md（部署安全） |
| 核心目标 | 为 P2 Gateway + Auth 和后续服务拆分提供可执行的部署方案 |
| 文档职责 | What & How — 怎么部署、怎么构建、怎么监控、怎么发布 |

---

## 2. Docker Compose 完整拓扑

### 2.1 服务清单

| 服务 | 镜像构建方式 | 副本数 | 端口暴露 | 健康检查 |
|------|------------|--------|---------|---------|
| traefik | `traefik:v3` | 1 | 80, 443 | `/ping` |
| auth-service | Dockerfile | 1 | (内部 8001) | `/health` |
| api-service | Dockerfile | 1 | (内部 8002) | `/health` |
| cognitive-rt | Dockerfile | 1 | (内部 8003) | `/health` |
| index-service | Dockerfile | 1 | (内部 8004) | `/health` |
| output-service | Dockerfile | 1 | (内部 8005) | `/health` |
| ingestion-service | Dockerfile | 1 | (内部 8006) | `/health` |
| integration-service | Dockerfile | 1 | (内部 8007) | `/health` |
| postgres | `postgres:16-alpine` | 1 | (内部 5432) | `pg_isready` |
| redis | `redis:7-alpine` | 1 | (内部 6379) | `redis-cli ping` |
| minio | `minio/minio` | 1 | (内部 9000, 9001) | `/minio/health/live` |

### 2.2 网络拓扑

```
                    ┌──────────────────────────────────┐
                    │         traefik (80/443)          │
                    │    TLS termination / routing      │
                    └────────────┬─────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        api-service         frontend          (future)
        (8002)              (nginx:80)
              │
    ┌─────────┼─────────┬──────────┬──────────┐
    ▼         ▼         ▼          ▼          ▼
 auth-svc  cognitive  index     output   (future)
 (8001)    -rt(8003)  -svc(8004) -svc(8005)
              │         │
              │    ┌────┴────┐
              │    ▼         ▼
              │  postgres  minio
              │  (5432)    (9000)
              │
              └──────► redis (6379)
                         │ Streams + Pub/Sub

        ingestion-svc(8006) ──► index-service
        integration-svc(8007) ──► index-service
```

### 2.3 docker-compose.yml 结构

```yaml
version: "3.9"

x-common-env: &common-env
  INTERNAL_API_KEY: ${INTERNAL_API_KEY}
  POSTGRES_URL: postgresql+asyncpg://reqradar:${DB_PASSWORD}@postgres:5432/reqradar
  REDIS_URL: redis://redis:6379
  MINIO_ENDPOINT: minio:9000

x-healthcheck: &healthcheck
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s

services:
  traefik:
    image: traefik:v3
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--api.insecure=false"
      - "--ping=true"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik/dynamic.yml:/etc/traefik/dynamic.yml:ro
    networks:
      - traefik-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=PathPrefix(`/app`)"
      - "traefik.http.services.frontend.loadbalancer.server.port=80"
    networks:
      - traefik-net

  api-service:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    environment:
      <<: *common-env
      SERVICE_NAME: api-service
      AUTH_SERVICE_URL: http://auth-service:8001
      COGNITIVE_RT_URL: http://cognitive-rt:8003
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=PathPrefix(`/api`) || PathPrefix(`/ws`)"
      - "traefik.http.services.api.loadbalancer.server.port=8002"
    networks:
      - traefik-net
      - internal-net

  auth-service:
    build:
      context: .
      dockerfile: services/auth/Dockerfile
    environment:
      <<: *common-env
      JWT_SECRET: ${JWT_SECRET}
      JWT_EXPIRATION_MINUTES: 120
      REFRESH_EXPIRATION_DAYS: 7
    networks:
      - internal-net

  cognitive-rt:
    build:
      context: .
      dockerfile: services/cognitive-rt/Dockerfile
    environment:
      <<: *common-env
      INDEX_SERVICE_URL: http://index-service:8004
      OUTPUT_SERVICE_URL: http://output-service:8005
    networks:
      - internal-net

  index-service:
    build:
      context: .
      dockerfile: services/index/Dockerfile
    environment:
      <<: *common-env
      CHROMADB_HOST: chromadb
      CHROMADB_PORT: 8000
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
    networks:
      - internal-net

  output-service:
    build:
      context: .
      dockerfile: services/output/Dockerfile
    environment:
      <<: *common-env
      INDEX_SERVICE_URL: http://index-service:8004
    networks:
      - internal-net

  ingestion-service:
    build:
      context: .
      dockerfile: services/ingestion/Dockerfile
    environment:
      <<: *common-env
      INDEX_SERVICE_URL: http://index-service:8004
    networks:
      - internal-net

  integration-service:
    build:
      context: .
      dockerfile: services/integration/Dockerfile
    environment:
      <<: *common-env
      INDEX_SERVICE_URL: http://index-service:8004
      OUTPUT_SERVICE_URL: http://output-service:8005
    networks:
      - internal-net

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: reqradar
      POSTGRES_USER: reqradar
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U reqradar"]
      <<: *healthcheck
    networks:
      - internal-net

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      <<: *healthcheck
    networks:
      - internal-net

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      <<: *healthcheck
    networks:
      - internal-net

networks:
  traefik-net:
    driver: bridge
  internal-net:
    driver: bridge
    internal: true  # 不暴露到宿主机

volumes:
  pg_data:
  redis_data:
  minio_data:
```

### 2.4 Traefik 动态配置

```yaml
# traefik/dynamic.yml
http:
  middlewares:
    rate-limit-global:
      rateLimit:
        average: 1000
        burst: 200
    rate-limit-login:
      rateLimit:
        average: 5
        period: 1m
        burst: 3
    security-headers:
      headers:
        frameDeny: true
        contentTypeNosniff: true
        browserXssFilter: true
        referrerPolicy: "strict-origin-when-cross-origin"
```

---

## 3. Dockerfile 规范

### 3.1 多阶段构建模板

```dockerfile
# 每个服务的 Dockerfile 遵循此模板

# ===== 构建阶段 =====
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# ===== 运行阶段 =====
FROM python:3.12-slim AS runtime

RUN groupadd -r reqradar && useradd -r -g reqradar reqradar

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv
COPY reqradar/kernel /app/reqradar/kernel
COPY services/{service_name} /app/service

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER reqradar

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:{port}/health || exit 1

EXPOSE {port}

CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "{port}"]
```

### 3.2 各服务端口映射

| 服务 | 端口 |
|------|------|
| auth-service | 8001 |
| api-service | 8002 |
| cognitive-rt | 8003 |
| index-service | 8004 |
| output-service | 8005 |
| ingestion-service | 8006 |
| integration-service | 8007 |

---

## 4. CI/CD 流水线

### 4.1 GitHub Actions 流水线阶段

```
push/PR → ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
          │ 1. Lint  │ → │ 2. Test  │ → │ 3. Build │ → │ 4. Scan  │ → │ 5. Deploy│
          │ ruff     │   │ pytest   │   │ docker   │   │ trivy    │   │ compose  │
          │ mypy     │   │ coverage │   │ build    │   │ pip-audit│   │ up -d    │
          │ eslint   │   │ vitest   │   │          │   │          │   │          │
          └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
              5min           8min          10min           3min           2min
```

### 4.2 完整 ci.yml 骨架

```yaml
name: CI

on:
  push:
    branches: [main, develop, "refactor/**"]
  pull_request:
    branches: [main, develop]

jobs:
  lint-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install ruff mypy
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy .

  lint-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run lint

  test-backend:
    needs: lint-backend
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: test, POSTGRES_USER: test, POSTGRES_PASSWORD: test }
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install uv && uv sync
      - run: pytest -q --cov=reqradar --cov-report=xml
      - uses: codecov/codecov-action@v4
        with: { files: ./coverage.xml }

  test-frontend:
    needs: lint-frontend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run test

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pip-audit && pip-audit
      - uses: aquasecurity/trivy-action@master
        with: { scan-type: fs, scan-ref: . }

  build-and-push:
    needs: [test-backend, test-frontend, security-scan]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: ${{ github.actor }}, password: ${{ secrets.GITHUB_TOKEN }} }
      - run: docker compose -f docker-compose.yml build
      - run: docker compose -f docker-compose.yml push
```

---

## 5. 环境变量清单

### 5.1 必填环境变量

| 变量 | 用途 | 示例 |
|------|------|------|
| `JWT_SECRET` | JWT 签名密钥 | `openssl rand -hex 32` |
| `DB_PASSWORD` | PostgreSQL 密码 | 随机生成 |
| `INTERNAL_API_KEY` | 服务间认证密钥 | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | LLM API Key 加密密钥 | `openssl rand -hex 32` |
| `MINIO_ACCESS_KEY` | MinIO 访问密钥 | `minioadmin`（开发） |
| `MINIO_SECRET_KEY` | MinIO 密钥 | `minioadmin`（开发） |

### 5.2 可选环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 提供商 | `openai` |
| `LLM_MODEL` | 模型名称 | `gpt-4o` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `SENTRY_DSN` | 错误追踪 | — |

---

## 6. 监控与告警

### 6.1 Prometheus 指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `reqradar_sessions_active` | Gauge | 活跃 Session 数 |
| `reqradar_sessions_total` | Counter | Session 生命周期总量 |
| `reqradar_session_duration_seconds` | Histogram | Session 执行时长分布 |
| `reqradar_llm_calls_total` | Counter | LLM 调用次数 |
| `reqradar_llm_call_duration_seconds` | Histogram | LLM 调用延迟 |
| `reqradar_tool_calls_total` | Counter | 工具调用次数 |
| `reqradar_checkpoint_write_duration_seconds` | Histogram | Checkpoint 写入延迟 |
| `reqradar_api_requests_total` | Counter | API 请求总量 |
| `reqradar_api_request_duration_seconds` | Histogram | API 响应延迟 |

### 6.2 告警规则

| 告警 | 条件 | 严重度 |
|------|------|--------|
| Session 失败率过高 | `rate(reqradar_sessions_total{status="FAILED"}[5m]) / rate(reqradar_sessions_total[5m]) > 0.1` | Critical |
| LLM 调用延迟过高 | `histogram_quantile(0.95, reqradar_llm_call_duration_seconds) > 30` | Warning |
| API 错误率过高 | `rate(reqradar_api_requests_total{status=~"5.."}[5m]) > 10` | Warning |
| Checkpoint 写入持续失败 | `rate(reqradar_checkpoint_write_duration_seconds{status="error"}[10m]) > 0` | Critical |
| 磁盘使用率过高 | `disk_used_percent{mountpoint="/data"} > 85` | Warning |

### 6.3 Grafana Dashboard 模板

核心面板：

1. **Session 概览**：活跃数、完成率、失败率、平均时长趋势
2. **LLM 调用**：QPS、P95 延迟、Token 消耗、错误率
3. **API 网关**：按端点分组的 QPS、P99 延迟、4xx/5xx 占比
4. **存储健康**：PG 连接数、Redis 内存、MinIO 使用量

---

## 7. 日志方案

### 7.1 日志输出

- 所有服务输出 **JSON 格式** 的 structlog 日志到 stdout
- Docker 通过 `json-file` driver 采集
- 生产环境可接入 Loki + Grafana 或 ELK

### 7.2 日志级别

| 环境 | 默认级别 |
|------|---------|
| 开发 | DEBUG |
| 测试 | INFO |
| 生产 | INFO |

### 7.3 日志格式

```json
{
  "timestamp": "2026-06-01T10:00:00.000Z",
  "level": "info",
  "logger": "reqradar.kernel.session",
  "event": "session_transitioned",
  "session_id": "uuid",
  "project_id": "uuid",
  "from_status": "READY",
  "to_status": "RUNNING",
  "service": "cognitive-rt"
}
```

---

## 8. 本地开发环境

### 8.1 快速启动

```bash
# 1. 生成密钥
echo "JWT_SECRET=$(openssl rand -hex 32)" > .env
echo "INTERNAL_API_KEY=$(openssl rand -hex 32)" >> .env
echo "ENCRYPTION_KEY=$(openssl rand -hex 32)" >> .env
echo "DB_PASSWORD=devpassword" >> .env
echo "MINIO_ACCESS_KEY=minioadmin" >> .env
echo "MINIO_SECRET_KEY=minioadmin" >> .env

# 2. 启动全部服务
docker compose up -d

# 3. 运行数据库迁移
docker compose exec api-service alembic upgrade head

# 4. 创建管理员
docker compose exec api-service reqradar createsuperuser
```

### 8.2 单服务开发模式

```bash
# 单独启动基础设施
docker compose up -d postgres redis minio

# 本地运行目标服务
cd services/cognitive-rt
POSTGRES_URL=postgresql+aiosqlite:///dev.db REDIS_URL=redis://localhost:6379 \
  uvicorn main:app --reload --port 8003
```

---

## 9. 数据库迁移执行流程

```bash
# 新建迁移（开发时）
docker compose exec api-service alembic revision --autogenerate -m "V2_P1_create_xxx"

# 应用迁移（部署时）
docker compose exec api-service alembic upgrade head

# 回滚一个版本（紧急回滚）
docker compose exec api-service alembic downgrade -1

# 查看当前版本
docker compose exec api-service alembic current
```

---

## 10. 发布流程

```
1. 功能分支开发 → PR → 代码评审
2. 合并到 develop → CI 全量测试
3. 版本号更新（pyproject.toml + package.json）
4. 合并到 main → CI 构建镜像 + 推送到 ghcr.io
5. 生产环境 docker compose pull + up -d（蓝绿部署）
6. 运行 alembic upgrade head
7. 健康检查通过 → 切换流量
```

---

## 附录 A：依赖版本锁定

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | 运行时 |
| FastAPI | 0.115+ | API 框架 |
| PostgreSQL | 16 | 主数据库 |
| Redis | 7 | 缓存/消息 |
| MinIO | latest | 对象存储 |
| Traefik | v3 | 网关 |
| Docker Compose | v2 | 编排 |
| uv | latest | Python 包管理 |
