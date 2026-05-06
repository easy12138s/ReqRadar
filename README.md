<p align="left">
<h1 align="left">ReqRadar</h1>
<p align="left"><strong>需求透镜</strong></p>
<p align="left">业务即产品</p>
</p>

ReqRadar——需求分析 Agent，在写代码前把需求想清楚。支持多文件/多格式需求上传，通过预处理整合为结构化文档，再由 ReAct Agent（9 工具 + 7 维度追踪）生成决策导向的双层分析报告，分析后自动更新项目记忆。

## 架构

- **后端**：Python (^3.12) / FastAPI / SQLAlchemy 2 (async) / JWT / WebSocket
- **前端**：React 19 / TypeScript / Ant Design 6 / Vite 8（深色科技风主题）
- **Agent**：ReAct 单层循环 + CoT 提示词引导 + 7 维度 LLM 自评估 + 记忆自进化
- **存储**：SQLite (WAL) / ChromaDB 向量库
- **分析工具**（9 种）：代码搜索 / 文件读取 / 模块摘要 / 依赖分析 / 语义检索 / Git 贡献者 / 项目画像 / 术语查询

## 快速开始

```bash
git clone https://github.com/easy12138s/reqradar.git
cd reqradar
cp .reqradar.yaml.example .reqradar.yaml
export OPENAI_API_KEY=sk-xxx

# 一键安装并启动
pip install reqradar
reqradar serve
# 浏览器打开 http://localhost:8000/app/

# 前端开发
cd frontend && npm install && npm run dev
```

## CLI

```bash
# === 项目管理 ===
reqradar project create -n myproj --local-path ./src
reqradar project list
reqradar project show 1
reqradar project delete 1 --force
reqradar project index 1                     # 构建索引

# === 需求预处理（v0.8） ===
reqradar requirement preprocess -p 1 -f spec.pdf screenshot.png notes.md -n "SSO需求"
# → LLM 整合多文件为结构化 Markdown → 确认保存 → 输出 requirement_document_id

# === 分析任务 ===
reqradar analyze submit -p 1 -t "需求描述"      # 文本直接分析
reqradar analyze submit -p 1 -r 42              # 引用预处理文档分析（v0.8）
reqradar analyze file ./req.md -i .reqradar/index   # 本地文件离线分析
reqradar analyze list
reqradar analyze status 1
reqradar analyze cancel 1

# === 报告 ===
reqradar report get 1
reqradar report get 1 -f html -o report.html
reqradar report versions 1
reqradar report evidence 1

# === 配置管理 ===
reqradar config init
reqradar config list
reqradar config set llm.model gpt-4o
```

## Web 界面

```
http://localhost:8000/app/
```

- **Dashboard** — 项目/术语/模块统计总览 + 快捷操作
- **项目管理** — 创建/搜索/删除项目，文件浏览，知识库管理
- **需求预处理** — 多文件上传（PDF/DOCX/图片/Markdown），LLM 整合为结构化需求文档，编辑确认后提交分析
- **分析提交** — 文本/文件/预处理文档三种方式，可调深度+模板
- **实时进度** — WebSocket 推送，维度进度可视化，自动重连
- **报告查看** — 结构化渲染 + TOC 导航 + 证据面板 + 对话追问

## 记忆自进化（v0.7）

每次分析完成后，系统自动从报告中提取候选知识（术语/模块/约束/技术栈），与已有项目记忆比对去重，合并更新。分析越多，项目知识库越完整。

## 分析深度

| 深度 | 步数 | 适用场景 |
|------|------|----------|
| quick | 10 | 快速评估，聚焦 2-3 个核心风险 |
| standard | 15 | 常规分析，覆盖全部 7 维度 |
| deep | 25 | 深度审查，穷举证据和影响面 |

## 配置三层优先级

用户级 > 项目级 > 系统级 > `.reqradar.yaml` > 代码默认值

## 许可证

MIT
