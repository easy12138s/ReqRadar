# Contributing to ReqRadar

感谢你对 ReqRadar 的关注！

## 快速开始

```bash
git clone https://github.com/your-org/reqradar.git
cd reqradar
poetry install
cp .reqradar.yaml.example .reqradar.yaml
export OPENAI_API_KEY=sk-xxx
```

## 开发

```bash
# 后端测试
poetry run pytest tests/ -q

# 前端开发
cd frontend && npm install && npm run dev   # http://localhost:5173，代理 API 到 :8000

# 前端构建
cd frontend && npm run build                # → src/reqradar/web/static/

# 启动后端
PYTHONPATH=src reqradar serve
```

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`

## 许可证

MIT
