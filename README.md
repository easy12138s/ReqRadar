<p align="left">
<h1 align="left">ReqRadar</h1>
<p align="left"><strong>需求透镜</strong></p>
<p align="left">业务即产品</p>
</p>

需求分析 Agent——在写代码前把需求想清楚。提取术语、检索历史、匹配代码、定位风险，生成决策导向的双层分析报告。

## 架构

- **后端**：Python / FastAPI / SQLAlchemy 2 (async) / JWT / WebSocket
- **前端**：React / TypeScript / Ant Design
- **AI**：OpenAI 或 Ollama，6 步固定流程 + ReAct Agent 双引擎
- **存储**：SQLite (WAL) / Chroma 向量库

## 使用

```bash
git clone https://github.com/your-org/reqradar.git
cd reqradar
poetry install
cp .reqradar.yaml.example .reqradar.yaml
export OPENAI_API_KEY=sk-xxx

# CLI 分析
reqradar index -r ./src -o .reqradar/index
reqradar analyze ./docs/requirements/new-feature.md -i .reqradar/index

# Web 界面
reqradar createsuperuser
reqradar serve
# 浏览器打开 http://localhost:8000/app/

# 前端开发
cd frontend && npm install && npm run dev
```

## 许可证

MIT
