# ReqRadar 版本发布流程

## 一、版本号规范

遵循 [Semantic Versioning](https://semver.org/spec/v2.0.0.html)：

| 变更类型 | 版本号示例 | 说明 |
|---------|-----------|------|
| 修复 Bug | `0.6.0` → `0.6.1` | 向后兼容的 bug 修复 |
| 新增功能 | `0.6.0` → `0.7.0` | 向后兼容的功能添加 |
| 重大变更 | `0.6.0` → `1.0.0` | 不兼容的 API 变更 |

> PyPI 不允许同名同版本覆盖，每次发布必须改版本号。

## 二、发布步骤

### Step 1: 更新 CHANGELOG

在 `CHANGELOG.md` 顶部添加新版本条目：

```markdown
## [0.7.0] - 2026-04-29

### Added

- 新功能描述

### Changed

- 变更描述

### Fixed

- 修复描述
```

### Step 2: 修改版本号

修改以下两个文件，保持版本号一致：

| 文件 | 修改位置 |
|------|---------|
| `pyproject.toml` | `version = "0.7.0"` |
| `src/reqradar/__init__.py` | `__version__ = "0.7.0"` |

### Step 3: 提交代码到 GitHub

```bash
git add -A
git commit -m "chore: bump version to 0.7.0"
git push
```

### Step 4: 构建分发包

```bash
# 清理旧包
rm -rf dist/ build/ *.egg-info

# 构建
python -m build
```

构建完成后会在 `dist/` 目录生成两个文件：
- `reqradar-0.7.0-py3-none-any.whl` — wheel 包
- `reqradar-0.7.0.tar.gz` — 源码包

### Step 5: 上传到 PyPI

```bash
# 检查包
twine check dist/*

# 上传（会提示输入 API token）
twine upload dist/*
```

> 推荐使用 API Token 而非密码：https://pypi.org/manage/account/token/

### Step 6: 验证

```bash
# 安装新版本
pip install --upgrade reqradar

# 检查版本
reqradar --version

# 快速功能测试
reqradar --help
```

## 三、完整命令速查

```bash
# 1. 改版本号（手动编辑）
#    - pyproject.toml
#    - src/reqradar/__init__.py

# 2. 提交
git add -A && git commit -m "chore: bump version to X.Y.Z" && git push

# 3. 构建
rm -rf dist/ build/ *.egg-info && python -m build

# 4. 发布
twine upload dist/*

# 5. 验证
pip install --upgrade reqradar && reqradar --version
```
