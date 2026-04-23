def build_report_generation_prompt(
    requirement_text: str,
    evidence_text: str,
    dimension_status: dict[str, str],
    template_sections: list[dict] | None = None,
) -> str:
    parts = [
        "你正在生成需求分析报告。请基于以下证据和维度状态，为报告的每个章节生成内容。",
        "",
        f"## 需求内容\n{requirement_text}",
        "",
        f"## 维度状态\n" + "\n".join(f"- {k}: {v}" for k, v in dimension_status.items()),
        "",
        f"## 已收集证据\n{evidence_text}",
    ]
    if template_sections:
        parts.append("\n## 章节生成要求\n")
        for sec in template_sections:
            parts.append(f"### {sec['title']}（{sec['id']}）")
            parts.append(f"章节描述：{sec['description']}")
            if sec.get("requirements"):
                parts.append(f"写作要求：{sec['requirements']}")
            if sec.get("dimensions"):
                parts.append(f"所需维度：{', '.join(sec['dimensions'])}")
            parts.append("")
    parts.append("\n请输出完整的 JSON 格式报告数据，包含上述所有章节对应字段。")
    return "\n".join(parts)

def build_dimension_section_prompt(
    section_id: str,
    section_title: str,
    section_description: str,
    section_requirements: str,
    section_dimensions: list[str],
    evidence_for_dimensions: str,
) -> str:
    return f"""你正在生成报告的第X章：{section_title}

章节描述：{section_description}
写作要求：{section_requirements}
所需维度：{', '.join(section_dimensions) if section_dimensions else '无特定维度'}

请基于以下证据和上下文生成该章节内容：

{evidence_for_dimensions}"""
