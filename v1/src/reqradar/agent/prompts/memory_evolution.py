MEMORY_EVOLUTION_SYSTEM_PROMPT = """你是项目记忆维护助手。你的任务是将本次需求分析中发现的持久化知识，合理地合并到项目记忆中。

## 行为规则
1. 严格比对：每条候选知识与已有记忆逐条对照
2. 质量优先：模糊、泛泛而谈的内容不要写入
3. 去重优先：已有记忆中的等价内容必须标记 skip
4. 冲突时合并：定义矛盾时取更完整/准确的内容"""


def build_memory_evolution_user_prompt(
    existing_memory: str,
    new_terms: list[dict],
    new_modules: list[dict],
    new_constraints: list[dict],
    tech_stack_additions: dict,
    overview_insights: str,
) -> str:
    parts = [
        "## 已有项目记忆",
        existing_memory or "（暂无已有记忆）",
        "",
        "## 本次分析发现的候选知识",
    ]

    if new_terms:
        parts.append("### 新术语")
        for t in new_terms:
            parts.append(
                f"- {t.get('term', '?')}: {t.get('definition', '')} [domain: {t.get('domain', '')}]"
            )

    if new_modules:
        parts.append("### 受影响的模块")
        for m in new_modules:
            classes = ", ".join(m.get("key_classes", []))
            parts.append(
                f"- {m.get('name', '?')}: {m.get('responsibility', '')}"
                + (f" (核心类: {classes})" if classes else "")
            )

    if new_constraints:
        parts.append("### 新发现的约束")
        for c in new_constraints:
            parts.append(f"- [{c.get('type', 'other')}] {c.get('description', '')}")

    if tech_stack_additions:
        parts.append("### 技术栈补充")
        for cat, items in tech_stack_additions.items():
            if items:
                parts.append(f"- {cat}: {', '.join(items)}")

    if overview_insights:
        parts.append(f"### 项目概览更新建议\n{overview_insights}")

    parts.extend(
        [
            "",
            "## 按以下步骤执行",
            "",
            "**第1步——逐条比对**",
            "对每条候选知识与已有记忆对照：",
            "- 完全重复 → action: skip",
            "- 更新已有条目（新信息更完整） → action: update，写出具体更新内容",
            "- 已有记忆中不存在 → action: add",
            "- 与已有记忆冲突 → action: merge，写出合并后内容",
            "- 模糊/无实质内容 → action: skip",
            "",
            "**第2步——控制质量**",
            "- 术语定义必须 ≥10 字才写入",
            "- 模块名称必须来自代码路径或已有模块列表",
            "- 约束必须有具体描述",
            "",
            "**第3步——输出操作列表**",
            "在 operations 字段中输出具体写入操作，在 changelog_entry 中写变更摘要。",
        ]
    )

    return "\n".join(parts)
