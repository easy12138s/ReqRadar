# ReqRadar

需求从提出到评审再到开发，参与的人各有各的视角，信息经常对不齐。ReqRadar 在动手之前帮团队把信息串起来。

它是一个固定流程的垂直领域 Agent：读取需求文档，提取关键术语，检索相似历史需求，匹配代码模块和贡献者，最终生成一份**决策导向的双层分析报告**。

## 目标

让需求评审有据可依——产品/管理层拿到可直接决策的摘要，开发者/架构师拿到完整的技术依据，每个结论都有证据支撑。

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
