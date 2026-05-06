# Issue: 报告核心段落大面积缺失

**发现日期**: 2026-04-23
**严重级别**: 高
**影响范围**: 所有 LLM 驱动的报告生成步骤
**状态**: ✅ 已修复

## 现象

本次分析报告中，以下段落**完全为空**：

| 段落 | 状态 | 所在层级 |
|:---|:---|:---|
| `executive_summary`（决策摘要） | 空白 | 决策层 |
| `technical_summary`（技术支撑概览） | 空白 | 技术层 |
| `risks`（结构化风险列表） | 空白 | 技术层 |
| `change_assessment`（变更评估） | 空白 | 技术层 |
| `evidence_items`（支撑证据） | 空白 | 决策层 |
| `impact_domains`（影响域） | 空白 | 技术层 |
| `decision_summary.decisions` | 空白 | 决策层 |
| `decision_summary.open_questions` | 空白 | 决策层 |
| `decision_summary.follow_ups` | 空白 | 决策层 |
| `implementation_suggestion`（实施建议） | 空白 | 技术层 |

报告评估指标：
- 流程完成度: full（6/6 步骤执行成功）
- 内容完整度: partial
- 证据支撑度: low

## 根因分析

这是 **Issue #002（工具调用未工作）** 的连锁反应。

当工具调用失败后，系统降级到 `complete_structured`，此时：
1. LLM 无法主动查询代码库（`search_code`, `read_file`, `list_modules`）
2. 无法获取模块依赖（`get_dependencies`）
3. 无法获取贡献者信息（`get_contributors`）
4. 无法获取项目画像（`get_project_profile`）

缺少这些上下文，LLM 无法做出有意义的分析判断，因此所有需要"基于代码实际情况"的段落都为空。

此外，Generate 步骤的 prompt 中明确要求：
> "不要重新判断风险和范围，而是根据已有分析结果组织成两层"

这意味着如果 Analyze 步骤产出的数据为空，Generate 步骤也无数据可组织。

## 相关文件

- `src/reqradar/agent/steps.py` — `step_analyze`, `step_generate`
- `src/reqradar/agent/prompts.py` — `ANALYZE_PROMPT`, `GENERATE_PROMPT`
- `src/reqradar/agent/tool_use_loop.py` — 降级逻辑

## 修复建议

1. **首要修复 Issue #002** — 恢复工具调用能力
2. **增加降级时的提示质量** — 即使没有工具调用，prompt 中也应该包含更多项目上下文（如模块列表、文件树）
3. **增加内容完整性校验** — 在报告生成后检查关键段落是否为空，为空时自动重试或提示用户
4. **改进 Generate Prompt** — 明确要求即使 analyze 数据不完整，也要基于已有信息生成有价值的段落
