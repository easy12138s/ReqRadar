<p align="left">
<h1>ReqRadar</h1>
<p><strong>需求透镜 —— 在写代码前把需求想清楚</strong></p>
</p>

---

ReqRadar 是一个垂直领域需求分析 Agent。输入需求描述或多份需求文件，系统调用多种分析工具生成决策导向的分析报告，并在分析后自动更新项目知识库。

## 架构

Python / FastAPI + React / TypeScript / Ant Design + OpenAI-compatible LLM + ChromaDB

## 快速开始

```bash
pip install reqradar
export OPENAI_API_KEY=sk-xxx
reqradar serve
# 浏览器打开 http://localhost:8000/app/
```

或从源码：

```bash
git clone https://github.com/easy12138s/reqradar.git
cd reqradar && poetry install
cp .reqradar.yaml.example .reqradar.yaml
reqradar serve
```

## CLI 用法

```bash
# 项目
reqradar project create -n myproj --local-path ./src
reqradar project list

# 需求预处理：多文件上传 + LLM 整合为结构化需求文档
reqradar requirement preprocess -p 1 -f spec.pdf screenshot.png notes.md

# 分析
reqradar analyze submit -p 1 -t "需求描述"         # 文本直接分析
reqradar analyze submit -p 1 -r 42                 # 引用预处理文档
reqradar analyze file ./req.md -i .reqradar/index  # 离线分析

# 报告
reqradar report get 1
reqradar report get 1 -f html -o report.html

# 配置
reqradar config set llm.model gpt-4o
```

## Web 界面

启动后访问 `http://localhost:8000/app/`：

- 项目管理、文件浏览、知识库
- 多文件需求预处理（PDF/DOCX/图片/Markdown）
- 分析任务提交与实时进度
- 报告查看、版本对比、证据链追溯

## 许可证

MIT
