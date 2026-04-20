# ReqRadar

需求从提出到评审再到开发，参与的人各有各的视角，信息经常对不齐。ReqRadar 在动手之前帮团队把信息串起来。

它是一个固定流程的垂直领域 Agent：读取需求文档，提取关键术语，检索相似历史需求，匹配代码模块和贡献者，最终生成一份结构化的分析报告。

## 工作流程

```
reqradar index → 代码解析 + 文档向量化 + 项目画像构建 → 索引 + 记忆
reqradar analyze → 6步固定流程 → Markdown 报告
```

6 步流程：读取文档 → 提取术语 → 关键词映射 → 检索相似需求 + 匹配代码 → 分析贡献者 → 生成报告

流程固定、模板固定，LLM 仅用于填充自然语言片段，不参与流程决策。

## 主要特性

- **项目画像自动构建**：`reqradar index` 自动调用 LLM 分析代码结构，构建项目画像
- **术语带定义提取**：从需求文档提取的每个术语都包含定义和所属领域
- **结构化风险评估**：风险项包含描述、严重程度、影响范围、缓解建议
- **变更评估表**：每个需求自动生成变更评估（模块、变更类型、影响等级）
- **语义关键词映射**：将中文业务术语映射为英文代码搜索词

## 安装

需要 Python 3.12+ 和 Poetry。

```bash
git clone https://github.com/your-org/reqradar.git
cd reqradar
poetry install
poetry shell
```

可选依赖：`poetry install --all-extras`（PDF、DOCX 支持）

## 配置

复制示例配置：`cp .reqradar.yaml.example .reqradar.yaml`

编辑 `.reqradar.yaml`：

```yaml
llm:
  provider: openai  # 或 ollama
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}

vision:  # 图片处理需要视觉模型
  provider: openai
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}

memory:  # 项目记忆（自动积累领域知识）
  enabled: true
  storage_path: .reqradar/memory
```

或通过环境变量：`export OPENAI_API_KEY=sk-xxx`

## 使用

### 1. 构建索引

```bash
# 索引代码仓库（必须）
reqradar index -r ./src -o .reqradar/index

# 同时索引需求文档
reqradar index -r ./src -d ./docs/requirements -o .reqradar/index

# 禁用项目画像构建
reqradar index -r ./src --no-build-profile
```

首次运行会自动下载嵌入模型（BGE-large-zh，约 1.3GB）。

索引完成后，`.reqradar/memory/memory.yaml` 将包含项目画像、模块列表、已知术语。

### 2. 分析需求

```bash
reqradar analyze ./docs/requirements/new-feature.md -i .reqradar/index
```

报告输出到 `./reports/` 目录。分析完成后，项目记忆会自动积累术语、团队信息和历史发现。

### 使用 Ollama（本地模型）

```bash
reqradar analyze ./docs/requirements/new-feature.md -i .reqradar/index --llm-backend ollama
```

## 支持的文档格式

| 格式 | 扩展名 | 依赖 | 说明 |
|:---|:---|:---|:---|
| 文本 | .md .txt .rst | 内置 | 默认支持 |
| PDF | .pdf | pdfplumber | 可选 |
| Word | .docx | python-docx | 可选 |
| 图片 | .png .jpg .jpeg .gif .bmp .webp | vision LLM | 需要 vision 配置 |
| 飞书聊天 | *feishu*.json *chat*.json | 内置 | 飞书导出格式 |

## 命令参考

```
reqradar index 构建代码和文档索引
  -r, --repo-path   代码仓库路径（必填）
  -d, --docs-path   需求文档目录（可选）
  -o, --output      索引输出目录（默认 .reqradar/index）
  --build-profile/--no-build-profile  是否构建项目画像

reqradar analyze 分析需求并生成报告
  REQUIREMENT_FILE  需求文档路径（必填）
  -i, --index-path  索引目录路径（默认 .reqradar/index）
  -o, --output      报告输出目录（默认 ./reports）
  --llm-backend     LLM 后端：openai 或 ollama
```

## 报告结构

| 章节 | 内容 |
|:---|:---|
| 报告概况 | 风险等级、影响范围、优先级、内容可信度 |
| 需求理解 | 需求概述、核心术语表、约束条件 |
| 影响分析 | 代码影响范围、变更评估表、相似历史需求 |
| 风险评估 | 风险概览表、验证要点 |
| 建议评审人 | 相关贡献者列表 |
| 实施建议 | 优先级、工作量、前置依赖 |

## 项目结构

```
src/reqradar/
├── cli/           CLI 入口（index、analyze 命令）
├── core/          调度器、上下文、报告渲染
├── modules/       能力模块
│   ├── code_parser.py    Python AST 代码解析
│   ├── vector_store.py   Chroma 向量检索
│   ├── git_analyzer.py   Git 贡献者分析
│   ├── llm_client.py     OpenAI/Ollama LLM 客户端
│   ├── memory.py         项目记忆管理器
│   └── loaders/          文档加载器
├── agent/         6 步工作流实现
├── infrastructure/ 配置、日志
└── templates/     报告模板
```

## 开发

```bash
poetry install          # 安装依赖
poetry run pytest       # 运行测试
poetry run black .      # 代码格式化
poetry run ruff check . # 静态检查
pre-commit install      # 启用 pre-commit 钩子
```

详细架构设计见 [DESIGN.md](DESIGN.md)，贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT
