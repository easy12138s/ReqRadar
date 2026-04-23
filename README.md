<p align="left">
  <h1 align="left">ReqRadar</h1>
  <p align="left"><strong>需求透镜</strong></p>
  <p align="left">业务即产品</p>
</p>

以业务定义产品，以 AI 重构开发。

ReqRadar 帮助团队在动手写代码之前，把需求彻底想清楚——提取术语、检索历史、匹配代码、定位风险，最终生成决策导向的分析报告。目前支持需求文档分析、代码索引、知识库记忆和 Web 可视化操作。

## 使用

### 安装

```bash
git clone https://github.com/your-org/reqradar.git
cd reqradar
poetry install
```

### 配置

```bash
cp .reqradar.yaml.example .reqradar.yaml
export OPENAI_API_KEY=sk-xxx
```

### 构建索引

```bash
reqradar index -r ./src -o .reqradar/index
```

### 分析需求

```bash
reqradar analyze ./docs/requirements/new-feature.md -i .reqradar/index
```

报告输出到 `./reports/`。也支持 Ollama 本地模型：`--llm-backend ollama`

### Web 界面

```bash
# 创建管理员账号
reqradar createsuperuser

# 启动 Web 服务
reqradar serve
```

浏览器打开 `http://localhost:8000/app/` 即可使用。

## 许可证

MIT
