<p align="left">
<h1 align="left">ReqRadar</h1>
<p align="left"><strong>需求透镜</strong></p>
<p align="left">业务即产品</p>
</p>

ReqRadar——需求分析 Agent，在写代码前把需求想清楚。提取术语、检索历史、匹配代码、定位风险，生成决策导向的双层分析报告。

## 架构

Python / FastAPI + React / TypeScript / Ant Design + OpenAI-compatible LLM + ChromaDB + MarkItDown

## 快速开始

```bash
git clone https://github.com/easy12138s/reqradar.git
cd reqradar && poetry install
reqradar serve
# 浏览器打开 http://localhost:8000/app/
```

## Web 界面

启动后访问 `http://localhost:8000/app/`，提供完整的需求分析工作台：

- **LLM 配置**：多 provider 支持（OpenAI / Ollama / 兼容接口）、连通性测试、键值遮盖
- **项目管理**：ZIP 上传 / Git 克隆创建项目，代码图浏览、文件树、向量索引、画像查看与编辑
- **需求预处理**：多文件上传（PDF / DOCX / PPTX / XLSX / HTML / 图片 / EPUB 等，基于 Microsoft MarkItDown 统一转换），LLM 合并为结构化需求文档，支持在线编辑后提交分析
- **分析任务**：文本输入 / 文件上传 / 引用预处理文档三种提交方式，可选分析深度和报告模板，WebSocket 实时进度推送
- **报告查看**：固定头部 + 可滚动 Markdown 报告 + 固定底部追问面板，SSE 流式对话，风险等级识别，版本管理与回滚
- **项目画像**：LLM 自动构建项目画像（概述 / 技术栈 / 模块 / 术语），支持编辑保存和待确认变更管理
- **用户管理**：Admin 用户管理 / 密码修改 / Token 撤销 / 登录登出

## 命令行

```bash
reqradar serve                   # 启动 Web 服务
reqradar project create ...      # 项目管理
reqradar analyze submit ...      # 提交分析
reqradar requirement preprocess  # 需求预处理
reqradar report get ...          # 获取报告
reqradar config set ...          # 配置管理
```

## 许可证

MIT
