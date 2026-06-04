# ReqRadar V1 归档

此目录包含 ReqRadar V1 (v0.8.0) 的全部源代码和配置的归档副本。

V2 重构启动后（2026-06），所有 V1 代码已从此处归档，新版本开发在根目录 `src/reqradar/` 下进行。

## V1 技术栈

- Python 3.12+ / Poetry
- FastAPI + SQLAlchemy async + SQLite/PostgreSQL
- React 19 / TypeScript / Vite 8 / Ant Design 6
- LiteLLM / ChromaDB / JWT / bcrypt

## V1 项目结构

```
v1/
├── src/reqradar/        # V1 Python 源码
│   ├── agent/           # ReAct Agent + tools + prompts
│   ├── web/             # FastAPI app + API routers + services + models
│   ├── modules/         # llm_client, code_parser, git_analyzer, memory, vector_store
│   ├── core/            # exceptions, context, report
│   ├── infrastructure/  # config, paths, logging
│   ├── mcp/             # MCP server
│   ├── cli/             # Click CLI
│   └── templates/       # report templates (YAML + Jinja2)
├── tests/               # V1 测试套件（unit / integration / e2e）
├── alembic/             # V1 数据库迁移（10 个版本）
├── docker/              # Dockerfile + entrypoint
├── pyproject.toml       # Poetry 配置
├── poetry.lock
├── docker-compose.yml
├── alembic.ini
└── ...
```

## 如何使用此归档

```bash
cd v1
poetry install
alembic upgrade head
reqradar serve
```

## 相关文档

V2 重构文档在根目录 `docs/` 下，V1 代码全景参考在 `docs/CODE_WIKI.md`。
