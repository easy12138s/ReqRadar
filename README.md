# ReqRadar

需求从提出到评审再到开发，参与的人各有各的视角，信息经常对不齐。ReqRadar 在动手之前帮团队把信息串起来。

它是一个固定流程的垂直领域 Agent：读取需求文档，提取关键术语，检索相似历史需求，匹配代码模块和贡献者，最终生成一份结构化的分析报告。

## 工作流程

```
reqradar index    →  代码解析 + 文档向量化  →  索引
reqradar analyze  →  5步固定流程            →  Markdown 报告
```

5 步流程：读取文档 → 提取术语 → 检索相似需求 + 匹配代码 → 分析贡献者 → 生成报告

流程固定、模板固定，LLM 仅用于填充自然语言片段，不参与流程决策。

## 安装

需要 Python 3.12+ 和 Poetry。

```bash
git clone https://github.com/your-org/reqradar.git
cd reqradar
poetry install
poetry shell
```

可选依赖（按需安装）：

```bash
poetry install --all-extras   # 安装全部可选依赖（PDF、DOCX）
pip install pdfplumber         # 仅 PDF 支持
pip install python-docx        # 仅 DOCX 支持
```

## 配置

复制示例配置文件：

```bash
cp .reqradar.yaml.example .reqradar.yaml
```

编辑 `.reqradar.yaml`，填入 OpenAI API Key（或切换为 Ollama）：

```yaml
llm:
  provider: openai          # 或 ollama
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}   # 或直接填写 key

# 图片处理需要视觉模型（独立于分析 LLM）
vision:
  provider: openai
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}

# 项目记忆（自动积累领域知识）
memory:
  enabled: true
  storage_path: .reqradar/memory
```

也可以通过环境变量设置：

```bash
export OPENAI_API_KEY=sk-xxx
```

## 使用

### 1. 构建索引

```bash
# 索引代码仓库（必须）
reqradar index -r ./src -o .reqradar/index

# 同时索引需求文档（支持 .md/.txt/.rst/.pdf/.docx/.csv/.json）
reqradar index -r ./src -d ./docs/requirements -o .reqradar/index
```

首次运行会自动下载嵌入模型（BGE-large-zh，约 1.3GB）。

### 2. 分析需求

```bash
reqradar analyze ./docs/requirements/new-feature.md -i .reqradar/index
```

报告输出到 `./reports/` 目录。分析完成后，项目记忆会自动积累术语、团队信息和历史发现。

### 使用 Ollama（本地模型）

```bash
reqradar analyze ./docs/requirements/new-feature.md -i .reqradar/index --llm-backend ollama
```

需要在配置中指定 Ollama host：

```yaml
llm:
  provider: ollama
  model: qwen2.5:14b
  host: http://localhost:11434
```

## 支持的文档格式

| 格式 | 扩展名 | 依赖 | 说明 |
|:---|:---|:---|:---|
| 文本 | .md .txt .rst | 内置 | 默认支持 |
| PDF | .pdf | pdfplumber | 可选 |
| Word | .docx | python-docx | 可选 |
| 图片 | .png .jpg .jpeg .gif .bmp .webp | vision LLM | 需要 vision 配置 |
| 飞书聊天 | *feishu*.json *chat*.json | 内置 | 飞书导出格式 |
| CSV 聊天 | .csv | 内置 | 通用聊天记录 |

## 命令参考

```
reqradar index       构建代码和文档索引
  -r, --repo-path    代码仓库路径（必填）
  -d, --docs-path    需求文档目录（可选）
  -o, --output       索引输出目录（默认 .reqradar/index）

reqradar analyze     分析需求并生成报告
  REQUIREMENT_FILE   需求文档路径（必填）
  -i, --index-path   索引目录路径（默认 .reqradar/index）
  -o, --output       报告输出目录（默认 ./reports）
  --llm-backend      LLM 后端：openai 或 ollama
  -v, --verbose      详细输出
```

## 项目结构

```
src/reqradar/
├── cli/              CLI 入口
├── core/             调度器、上下文、报告渲染、异常定义
├── modules/          能力模块
│   ├── code_parser.py    Python AST 代码解析
│   ├── vector_store.py   Chroma 向量检索
│   ├── git_analyzer.py   Git 贡献者分析
│   ├── llm_client.py     OpenAI/Ollama LLM 客户端（含视觉能力）
│   ├── memory.py         项目记忆管理器
│   └── loaders/           文档加载器
│       ├── base.py           ABC + 注册表
│       ├── text_loader.py    Markdown/Text/RST
│       ├── pdf_loader.py     PDF（可选依赖）
│       ├── docx_loader.py    Word DOCX（可选依赖）
│       ├── image_loader.py   图片（LLM 视觉）
│       ├── chat_loader.py    飞书 JSON + 通用 CSV
│       └── chat_types.py     ChatMessage/ChatConversation
├── agent/            5 步工作流实现
├── infrastructure/    配置、日志、注册表
└── templates/         报告模板
```

## 开发

```bash
poetry install          # 安装依赖
poetry run pytest      # 运行测试
poetry run black .     # 代码格式化
poetry run ruff check .  # 静态检查
```

建议启用 pre-commit 钩子：

```bash
pre-commit install
```

详细架构设计见 [DESIGN.md](DESIGN.md)，贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 技术栈

Python 3.12 / Click / Pydantic / Chroma / BGE-large-zh / OpenAI API / Jinja2

## 许可证

MIT