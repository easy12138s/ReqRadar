# ReqRadar

需求从提出到评审再到开发，参与的人各有各的视角，信息经常对不齐。ReqRadar 在动手之前帮团队把信息串起来。

它是一个固定流程的垂直领域 Agent：读取需求文档，提取关键术语，检索相似历史需求，匹配代码模块和贡献者，最终生成一份**决策导向的双层分析报告**。

## 目标

让需求评审有据可依——产品/管理层拿到可直接决策的摘要，开发者/架构师拿到完整的技术依据，每个结论都有证据支撑。

## 已完成

- **双层决策报告**：决策摘要层（面向产品/管理层）+ 技术支撑层（面向开发者/架构师），结论必附证据
- **工具调用循环**：LLM 可主动调用 9 种分析工具（代码搜索、模块查询、贡献者分析等），多轮迭代获取充分信息
- **决策摘要与证据链**：自动生成关键决策项、支撑证据、影响域和待定问题
- **影响域推断**：即使没有直接代码命中，也能根据上下文推断受影响的技术/业务域
- **项目画像自动构建**：`reqradar index` 自动调用 LLM 分析代码结构，构建项目画像
- **术语带定义提取**：每个术语包含定义和所属领域，自动积累到项目记忆
- **结构化风险评估**：风险项含描述、严重程度、影响范围、缓解建议
- **多格式文档支持**：Markdown、PDF、Word、图片（LLM 视觉）、飞书聊天记录
- **项目记忆系统**：自动积累术语、模块、贡献者和分析历史，后续分析可复用

## 使用

### 1. 安装

需要 Python 3.12+ 和 Poetry。

```bash
git clone https://github.com/your-org/reqradar.git
cd reqradar
poetry install
poetry shell
```

### 2. 配置

```bash
cp .reqradar.yaml.example .reqradar.yaml
export OPENAI_API_KEY=sk-xxx
```

### 3. 构建索引

```bash
reqradar index -r ./src -o .reqradar/index
```

首次运行自动下载嵌入模型（BGE-large-zh，约 1.3GB）。

### 4. 分析需求

```bash
reqradar analyze ./docs/requirements/new-feature.md -i .reqradar/index
```

报告输出到 `./reports/`。也支持 Ollama 本地模型：`--llm-backend ollama`

## 许可证

MIT
