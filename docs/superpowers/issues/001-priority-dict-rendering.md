# Issue: 模板渲染 Bug — priority 字段显示为 Python dict 字符串

**发现日期**: 2026-04-23
**严重级别**: 中等
**影响范围**: 所有生成的需求分析报告
**状态**: ✅ 已修复

## 现象

在分析报告中，"建议优先级"字段渲染成了 Python dict 的字符串表示，而不是格式化的人类可读文本：

```markdown
建议优先级：{'suggestion': '高优先级', 'reason': '当前配置系统存在安全风险、扩展性不足和用户体验差的问题...'}
```

## 预期行为

```markdown
建议优先级：高
理由：当前配置系统存在安全风险、扩展性不足和用户体验差的问题...
```

## 根因分析

LLM 返回的 JSON 中 `priority_suggestion` 是一个 dict（`{"suggestion": "...", "reason": "..."}`），但当前代码的 `EXTRACT_SCHEMA` 定义 `priority_suggestion` 为 string enum（`["urgent", "high", "medium", "low"]`）。

可能的两种情况：
1. MiniMax 模型没有严格遵循 schema，而是返回了 dict
2. `_parse_json_response` 对嵌套结构解析异常

需要检查 `agent/llm_utils.py` 中的 JSON 解析逻辑和 `agent/schemas.py` 中的 schema 定义是否匹配。

## 相关文件

- `src/reqradar/agent/schemas.py` — EXTRACT_SCHEMA 定义
- `src/reqradar/agent/llm_utils.py` — `_parse_json_response` 实现
- `src/reqradar/agent/steps.py` — `step_extract` 中对 priority 的处理
- `src/reqradar/core/report.py` — `ReportRenderer` 中 priority 的渲染

## 复现步骤

1. 准备任意需求文档
2. 使用 MiniMax 模型运行 `reqradar analyze`
3. 查看生成的报告中的"建议优先级"字段

## 修复建议

方案 A: 修改 schema，让 LLM 分别返回 `priority_level` (string) 和 `priority_reason` (string)
方案 B: 在 `step_extract` 中增加后处理，如果收到 dict 则自动展开
方案 C: 在 `ReportRenderer.render()` 中增加类型检查，如果是 dict 则格式化输出

推荐 **方案 A + C** 的组合：既修正 schema 让 LLM 行为可预期，又在渲染层做防御性处理。
