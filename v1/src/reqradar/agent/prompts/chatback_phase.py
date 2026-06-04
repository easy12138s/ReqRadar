CHATBACK_SYSTEM_PROMPT = """你是一位需求分析顾问，正在与用户讨论已生成的分析报告。你的任务是理解用户的意图，基于现有证据回答问题，或在必要时补充新证据。你应当专业、谦逊，承认不确定性。

## 行为规范

- 解释型问题：基于版本上下文中的证据回答，引用具体来源
- 纠正型问题：接受用户纠正，标记需要更新的维度
- 深入型问题：判断是否需要新证据，如需则说明需要查询什么
- 探索型问题：调用工具获取新信息，追加到版本上下文中
- 不确定时明确说"我不确定"，不要编造

## 可用上下文

报告数据：
{report_summary}

维度状态：
{dimension_status}

已收集证据：
{evidence_summary}
"""


def build_chatback_system_prompt(
    report_data: dict,
    context_snapshot: dict,
) -> str:
    risk = report_data.get("risk_level", "unknown")
    title = report_data.get("requirement_title", "未命名需求")
    summary_lines = [
        f"需求: {title}",
        f"风险等级: {risk}",
    ]
    if report_data.get("impact_modules"):
        modules = report_data["impact_modules"]
        if isinstance(modules, list):
            for m in modules[:5]:
                if isinstance(m, dict):
                    summary_lines.append(
                        f"  - {m.get('path', m.get('module', 'unknown'))}: {m.get('relevance_reason', '')}"
                    )
                elif isinstance(m, str):
                    summary_lines.append(f"  - {m}")
    report_summary = "\n".join(summary_lines)

    dimension_status = context_snapshot.get("dimension_status", {})
    dim_text = "\n".join(f"- {k}: {v}" for k, v in dimension_status.items())

    evidence_list = context_snapshot.get("evidence_list", [])
    ev_text = (
        "\n".join(
            f"- [{ev.get('id', '?')}] ({ev.get('type', '?')}) {ev.get('source', '?')}: {str(ev.get('content', ''))[:100]}"
            for ev in evidence_list[:10]
        )
        if evidence_list
        else "暂无证据"
    )

    return CHATBACK_SYSTEM_PROMPT.format(
        report_summary=report_summary,
        dimension_status=dim_text or "无维度状态",
        evidence_summary=ev_text,
    )
