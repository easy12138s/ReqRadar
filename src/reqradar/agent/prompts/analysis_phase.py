from reqradar.agent.dimension import DimensionTracker

ANALYSIS_SYSTEM_PROMPT = """你是一位专业的需求分析架构师。你的目标是为给定需求生成一份完整、可验证的分析报告，覆盖所有必要维度。

## 行为规范
1. 优先使用工具获取信息，不要猜测
2. 每个结论必须有证据支撑，引用具体来源
3. 关注用户指定的关注领域（如安全性、性能）
4. 达到最大步数时停止收集信息，生成报告
5. 不可执行代码、不可写入文件（报告除外）

## 分析维度
每个维度必须覆盖，但可自主决定详细程度：
- understanding（需求理解）: 业务和技术理解
- impact（影响域）: 受影响的模块、文件、接口
- risk（风险）: 技术、业务、合规风险
- change（变更评估）: 具体变更点、工作量估算
- decision（决策建议）: 面向管理层的决策要点
- evidence（证据支撑）: 所有结论的证据列表
- verification（验证要点）: 评审时需要验证的事项
"""

def build_analysis_system_prompt(
    project_memory: str = "",
    user_memory: str = "",
    historical_context: str = "",
    dimension_status: dict[str, str] | None = None,
    template_sections: list[dict] | None = None,
) -> str:
    parts = [ANALYSIS_SYSTEM_PROMPT]
    if project_memory:
        parts.append(f"\n## 项目画像\n{project_memory}")
    if user_memory:
        parts.append(f"\n## 用户偏好\n{user_memory}")
    if historical_context:
        parts.append(f"\n## 相似历史需求\n{historical_context}")
    if dimension_status:
        status_lines = [f"- {dim}: {status}" for dim, status in dimension_status.items()]
        parts.append(f"\n## 当前维度状态\n" + "\n".join(status_lines))
    if template_sections:
        section_lines = []
        for sec in template_sections:
            req = sec.get("requirements", "")
            dims = ", ".join(sec.get("dimensions", []))
            section_lines.append(f"- {sec['title']}（{sec['id']}）: {sec['description']}" + (f" [{dims}]" if dims else ""))
            if req:
                section_lines.append(f"  写作要求: {req}")
        if section_lines:
            parts.append("\n## 报告章节要求\n" + "\n".join(section_lines))
    return "\n".join(parts)

def build_analysis_user_prompt(requirement_text: str, agent_context: str = "") -> str:
    parts = [f"## 需求内容\n{requirement_text}"]
    if agent_context:
        parts.append(f"\n## 当前分析状态\n{agent_context}")
    parts.append("\n请选择合适的工具继续分析，或在信息充分时生成报告。")
    return "\n".join(parts)

def build_termination_prompt() -> str:
    return """你已达到分析步数上限或所有维度已达标。请基于已收集的所有证据，直接输出最终分析结果。

输出要求：
1. 所有结论必须引用具体证据来源
2. 每个维度都应有明确内容
3. 风险评级必须基于代码依据
4. 提出可操作的决策建议"""
