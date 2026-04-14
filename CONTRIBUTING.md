# Contributing to ReqRadar

感谢你对 ReqRadar 的关注！本文档将帮助你参与项目贡献。

## 快速开始

### 环境准备

```bash
# 克隆项目
git clone https://github.com/your-org/reqradar.git
cd reqradar

# 安装依赖（需要 Poetry）
poetry install

# 激活虚拟环境
poetry shell
```

### 配置

```bash
# 复制配置示例文件
cp .reqradar.yaml.example .reqradar.yaml

# 编辑配置（设置 OpenAI API Key 等）
vim .reqradar.yaml
```

## 开发流程

### 1. 创建分支

```bash
git checkout -b feat/your-feature-name
# 或修复 bug
git checkout -b fix/your-bug-fix
```

### 2. 开发与测试

```bash
# 运行测试
poetry run pytest

# 代码格式化
poetry run black .

# 静态检查
poetry run ruff check .
```

### 3. 提交代码

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
feat: 新功能
fix: 修复问题
docs: 文档更新
refactor: 重构（不改变行为）
test: 测试相关
chore: 构建/工具更新
```

示例：

```bash
git commit -m "feat: add TypeScript code parser support"
git commit -m "fix: handle empty vector store gracefully"
git commit -m "docs: update DESIGN.md with new module description"
```

### 4. 提交 PR

1. Push 到你的 fork
2. 创建 Pull Request 到 `main` 分支
3. 填写 PR 模板中的清单
4. 等待 Review

## 代码规范

### 格式化

- **Black**：行宽 100
- **Ruff**：规则集 `E, F, W, I, N, UP, B`，忽略 `E501`

### 类型检查

- 推荐使用 MyPy 进行类型检查（非强制）

### 测试

- 使用 pytest
- 核心模块覆盖率目标 > 80%
- 新功能必须附带测试

## 项目架构

请参阅 [DESIGN.md](DESIGN.md) 了解项目的架构设计和核心原则。

### 关键原则

- **流程固定**：分析步骤顺序不可变
- **模板固定**：报告结构由模板预定义
- **确定性优先**：相同输入产生一致输出
- **隐私优先**：敏感数据本地处理
- **容错降级**：子模块失败不阻塞整体流程

### 代码结构

```
src/reqradar/
├── cli/              # CLI 入口（Click）
├── core/             # 核心调度器、上下文、报告
├── modules/          # 能力模块（解析器、检索器等）
├── agent/            # 5步工作流实现
├── infrastructure/    # 配置、日志、错误、注册表
└── templates/        # 报告模板
```

## 报告 Bug

请使用 [Bug Report 模板](https://github.com/your-org/reqradar/issues/new?template=bug_report.md) 提交 Issue，包含：

- 复现步骤
- 预期行为 vs 实际行为
- 环境信息（OS、Python 版本、ReqRadar 版本）
- 相关日志

## 提出功能建议

请使用 [Feature Request 模板](https://github.com/your-org/reqradar/issues/new?template=feature_request.md) 提交 Issue。

## 许可证

本项目采用 [MIT License](LICENSE) 开源。提交代码即表示你同意你的贡献将以相同许可证发布。