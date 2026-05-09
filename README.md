<p align="left">
<h1 align="left">ReqRadar</h1>
<p align="left"><strong>需求透镜</strong></p>
<p align="left">业务即产品</p>
</p>

ReqRadar——需求分析 Agent，在写代码前把需求想清楚。提取术语、检索历史、匹配代码、定位风险，生成决策导向的双层分析报告。

## 架构

Python / FastAPI + React / TypeScript / Ant Design + OpenAI-compatible LLM + ChromaDB + MarkItDown

## 快速开始

### 方式一：一键部署脚本（推荐）

**Linux / macOS:**
```bash
git clone https://github.com/easy12138s/reqradar.git
cd reqradar
./scripts/deploy.sh
```

**Windows PowerShell:**
```powershell
git clone https://github.com/easy12138s/reqradar.git
cd reqradar
.\scripts\deploy.ps1
```

脚本支持参数：
- `--skip-frontend` / `-SkipFrontend` 跳过前端构建
- `--skip-migrate` / `-SkipMigrate` 跳过数据库迁移
- `--dev` / `-Dev` 开发模式（热重载）
- `--port 9000` / `-Port 9000` 自定义端口

### 方式二：Docker

```bash
# 设置必需的环境变量
export OPENAI_API_KEY=your-api-key
export REQRADAR_SECRET_KEY=$(openssl rand -hex 16)

# 可选：使用轻量级 embedding 模型以减少镜像体积和下载时间
# export EMBEDDING_MODEL=BAAI/bge-small-zh

cd docker && docker-compose up -d
# 访问 http://localhost:8000/app/
```

### 方式三：手动安装

```bash
git clone https://github.com/easy12138s/reqradar.git
cd reqradar && poetry install

# 配置（二选一）
cp .reqradar.yaml.example .reqradar.yaml   # YAML 配置
# 或创建 .env 文件：
echo "OPENAI_API_KEY=your-key" > .env
echo "REQRADAR_SECRET_KEY=$(openssl rand -hex 16)" >> .env

# 前端构建
cd frontend && npm ci && npm run build && cd ..

# 数据库迁移
poetry run alembic upgrade head

# 启动
poetry run reqradar serve
# 访问 http://localhost:8000/app/
```

## 配置

ReqRadar 支持 5 级配置优先级：用户级 > 项目级 > 系统级 > YAML 文件 > 代码默认值

配置方式：
- `.reqradar.yaml` — 主配置文件（支持 `${ENV_VAR}` 环境变量引用）
- `.env` — 环境变量文件（自动加载，适合存放密钥）
- 环境变量 — 直接设置 `OPENAI_API_KEY`、`REQRADAR_SECRET_KEY` 等
- Web 界面 — 系统级/项目级/用户级配置管理

### Embedding 模型选择

| 模型 | 维度 | 大小 | 说明 |
|------|------|------|------|
| `BAAI/bge-large-zh` (默认) | 1024 | ~1200 MB | 最佳精度，首次下载较慢 |
| `BAAI/bge-base-zh` | 768 | ~390 MB | 精度与性能平衡 |
| `BAAI/bge-small-zh` | 512 | ~95 MB | 快速推理，低资源占用 |
| `BAAI/bge-m3` | 1024 | ~1100 MB | 多语言支持（100+ 语言） |

在 `.reqradar.yaml` 中修改 `index.embedding_model` 即可切换，Docker 通过 `EMBEDDING_MODEL` 构建参数支持。

## Web 界面

启动后访问 `http://localhost:8000/app/`，提供完整的需求分析工作台：

- **LLM 配置**：多 provider 支持（OpenAI / Ollama / 兼容接口）、连通性测试、键值遮盖
- **项目管理**：ZIP 上传 / Git 克隆创建项目，代码图浏览、文件树、向量索引、画像查看与编辑
- **需求预处理**：多文件上传（PDF / DOCX / PPTX / XLSX / HTML / 图片 / EPUB 等，基于 Microsoft MarkItDown 统一转换），LLM 合并为结构化需求文档，支持在线编辑后提交分析
- **分析任务**：文本输入 / 文件上传 / 引用预处理文档三种提交方式，可选分析深度和报告模板，WebSocket 实时进度推送
- **报告查看**：固定头部 + 可滚动 Markdown 报告 + 固定底部追问面板，SSE 流式对话，风险等级识别，版本管理与回滚
- **项目画像**：LLM 自动构建项目画像（概述 / 技术栈 / 模块 / 术语），支持编辑保存和待确认变更管理
- **用户管理**：Admin 用户管理 / 密码修改 / Token 撤销 / 登录登出

## 命令行

```bash
reqradar serve                   # 启动 Web 服务
reqradar project create ...      # 项目管理
reqradar analyze submit ...      # 提交分析
reqradar requirement preprocess  # 需求预处理
reqradar report get ...          # 获取报告
reqradar config set ...          # 配置管理
```

## 许可证

MIT