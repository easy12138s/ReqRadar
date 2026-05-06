# Issue: 工具调用循环疑似未执行 — MiniMax 模型兼容性问题

**发现日期**: 2026-04-23
**严重级别**: 高
**影响范围**: 所有分析步骤（extract/analyze/generate）
**状态**: ✅ 已修复

## 现象

分析日志显示所有 HTTP 请求返回 200 OK，但：
- **没有看到任何 tool call 日志**（如 `Tool call #X: search_code(...)`）
- 日志中出现 `complete_with_tools error: OpenAI API key is missing or empty`（在 API key 未正确加载时）
- 修复 API key 后，工具调用仍无日志

## 预期行为

`tool_use_loop.py` 应该输出类似：
```
Tool call #1: search_code({"query": "config"}) -> 123 chars
Tool call #2: read_file({"path": "src/reqradar/infrastructure/config.py"}) -> 456 chars
```

## 根因分析

**高度怀疑：MiniMax-Text-01 模型不支持 OpenAI function calling 格式**

证据：
1. 配置使用 `provider: openai`，但 base_url 指向 `https://api.minimax.chat/v1`
2. 使用的是 MiniMax 自研模型，而非 OpenAI 官方模型
3. 日志中 `_complete_with_tools` 可能在调用 tools 后没有收到 `tool_calls` 字段
4. 所有步骤都降级到了 `complete_structured` fallback

## 相关文件

- `src/reqradar/agent/llm_utils.py` — `_complete_with_tools` 实现
- `src/reqradar/agent/tool_use_loop.py` — 工具调用循环
- `src/reqradar/modules/llm_client.py` — LLMClient 基类

## 影响评估

- **工具调用是 ReqRadar 的核心能力** — 没有工具调用，系统只能做关键词匹配，无法深入代码理解
- 当前报告质量大幅下降（空段落、无风险评估、无变更评估）
- 用户体验：用户上传需求后得到的报告是"半成品"

## 修复建议

1. **验证 MiniMax 是否支持 function calling**
   - 查阅 MiniMax API 文档，确认是否支持 `tools` / `function_call` 参数
   - 如果不支持，需要为 MiniMax 单独实现工具调用协议

2. **增加工具调用兼容性检测**
   - 在 `llm_client.py` 中增加 `supports_tool_calling()` 方法
   - 启动时检测模型能力，不支持则提前降级并提示用户

3. **考虑引入 LiteLLM 或类似库**
   - 统一封装不同 LLM provider 的工具调用差异
   - 避免为每个 provider 写独立的工具调用逻辑

4. **增加工具调用调试日志**
   - 在 `_complete_with_tools` 中打印完整的 request/response
   - 方便排查 provider 兼容性问题
