# Contributing to ReqRadar

感谢你对 ReqRadar 的关注！本文档将帮助你参与项目贡献。

## 快速开始

```bash
git clone https://github.com/your-org/reqradar.git
cd reqradar
poetry install
poetry shell
cp .reqradar.yaml.example .reqradar.yaml
export OPENAI_API_KEY=sk-xxx
```

## 开发流程

```bash
# 创建分支
git checkout -b feat/your-feature-name

# 运行测试
PYTHONPATH=src pytest

# 代码格式化 + 静态检查
poetry run black .
poetry run ruff check .
```

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`

## 关键原则

- **流程固定**：分析步骤顺序不可变
- **模板固定**：报告结构由模板预定义
- **结论附证据**：双层报告中每个结论需有证据支撑
- **容错降级**：子模块失败不阻塞整体流程

## 许可证

本项目采用 [MIT License](LICENSE) 开源。提交代码即表示你同意你的贡献将以相同许可证发布。
