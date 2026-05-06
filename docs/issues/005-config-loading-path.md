# Issue: 配置加载路径不一致 — `.reqradar.yaml` vs `.reqradar/config.yaml`

**发现日期**: 2026-04-23
**严重级别**: 低（用户体验）
**影响范围**: CLI 首次使用
**状态**: ✅ 已修复

## 现象

1. `load_config()` 默认查找 `.reqradar.yaml`（项目根目录）
2. 但项目中实际配置存储在 `.reqradar/config.yaml`
3. 导致首次运行 `reqradar analyze` 时，`api_key` 为 `None`，所有 LLM 调用失败

## 错误日志

```
complete_with_tools error: OpenAI API key is missing or empty
Tool use not available, falling back to complete_structured
LLM extract failed, using fallback keyword extraction: OpenAI API key is missing or empty
```

## 根因分析

配置系统有两个入口：
1. `load_config(config_path=None)` — 默认查找 `./.reqradar.yaml`
2. `.reqradar/config.yaml` — 项目初始化时创建的配置

两者路径不一致，用户可能在 `.reqradar/` 目录下管理所有数据，但 CLI 却在根目录找 `.reqradar.yaml`。

## 修复建议

方案 A: 统一配置路径
- 将 `.reqradar/config.yaml` 软链接或复制为 `.reqradar.yaml`
- 或在 `load_config()` 中增加回退逻辑：先找 `.reqradar.yaml`，找不到再找 `.reqradar/config.yaml`

方案 B: 明确文档说明
- 在 README 中明确说明配置文件位置
- CLI 启动时如果找不到配置，给出明确的提示

推荐 **方案 A**，对用户最友好。

## 相关文件

- `src/reqradar/infrastructure/config.py` — `load_config()` 实现
- `src/reqradar/cli/main.py` — CLI 入口
