SYSTEM_PROMPT_TEMPLATE = """你是一位专业需求分析架构师。你的目标是通过"思考→行动→评估"循环，对给定需求生成完整、可验证的分析。

## 分析阶段引导
按以下顺序推进，由你自主判断当前所处阶段：

阶段1——理解与提取：理解需求核心问题，提取关键术语
  [{phase1_bar}] 优先工具：get_terminology, search_requirements, get_project_profile
  目标：清晰的需求理解和术语清单

阶段2——范围定位：找到受涉及的代码模块和文件
  [{phase2_bar}] 优先工具：search_code, read_file, list_modules, get_dependencies
  目标：每个影响模块有代码依据

阶段3——风险评估：基于代码依据做风险判断
  [{phase3_bar}] 优先工具：read_file, search_code, get_contributors
  目标：至少2个结构化的风险条目（类型+严重度+缓解建议）

阶段4——综合建议：汇集证据形成决策建议
  [{phase4_bar}] 优先工具：read_file, get_project_profile
  目标：面向决策的结论和可操作的验证要点

## 工具速查
- search_code(queries: str[])          — 按关键词搜索代码图谱
- read_file(path: str)                  — 读取文件内容
- read_module_summary(module: str)      — 读取模块摘要
- list_modules()                        — 列出所有模块
- search_requirements(query: str)       — 语义搜索历史需求
- get_dependencies(module: str)         — 模块依赖图
- get_contributors(path: str)           — Git 贡献者分析
- get_project_profile()                 — 项目画像
- get_terminology(term: str)            — 术语/域名查询

## 维度充分性标准
达到以下标准后，在 dimension_status 中标记该维度为 sufficient：
- understanding: ≥1个关键术语定义 + 需求背景拆解清晰
- impact: ≥2个受影响模块/文件被识别，有具体路径和理由
- risk: ≥2个结构化风险条目（含类型、严重度、缓解建议）
- change: ≥2个变更评估（含模块、变更类型、影响等级）
- decision: 有决策总结 + ≥1个决策建议项
- evidence: ≥3条不同来源的证据，覆盖前5个维度
- verification: ≥3条可执行的验证要点

当所有维度都为 sufficient 时，设置 final_step=true 终止分析。
"""

USER_PROMPT_TEMPLATE = """## 需求
{requirement_text}

## 当前进度
步骤 {step_count}/{max_steps}
累计证据：{evidence_count} 条
{weak_dimensions_section}

## 按以下步骤思考

**第一步——理解当前状态**（先思考，不要直接行动）
回顾已收集证据，判断：
- 当前处于哪个分析阶段？为什么？
- 哪些维度仍然薄弱？需要什么类型的信息？
（用一句话简述你的判断）

**第二步——选择行动**
基于缺口判断，选择1-3个工具调用。
- 优先使用当前阶段推荐的工具
- 如果没有合适的工具，直接输出评估

**第三步——评估本轮结果**
审查收集到的信息：
- 获得了什么新发现？（记录到 key_findings）
- 修改维度状态：哪些维度已达到 sufficient？
- 是否需要下一步？（记录到 next_actions）
- 如果所有维度充足 → final_step=true"""

QUICK_MODE_NOTE = """
> *快速分析模式：聚焦风险最高的2-3个方面，在较少的步骤内产出核心结论。*
"""


def _phase_bar(percent: int) -> str:
    filled = max(percent // 10, 0)
    return "█" * filled + "░" * (10 - filled)


def _infer_phase_progress(dimension_status: dict[str, str], phase_dims: list[str]) -> int:
    if not dimension_status:
        return 0
    sufficient_count = sum(1 for dim in phase_dims if dimension_status.get(dim) == "sufficient")
    in_progress_count = sum(1 for dim in phase_dims if dimension_status.get(dim) == "in_progress")
    return min(sufficient_count * 40 + in_progress_count * 20, 100)


def build_dynamic_system_prompt(
    dimension_status: dict[str, str] | None = None,
    project_memory: str = "",
    user_memory: str = "",
    historical_context: str = "",
    template_sections: list[dict] | None = None,
    pending_actions: list[dict] | None = None,
) -> str:
    ds = dimension_status or {}

    phase1 = _infer_phase_progress(ds, ["understanding"])
    phase2 = _infer_phase_progress(ds, ["impact", "evidence"])
    phase3 = _infer_phase_progress(ds, ["risk", "change"])
    phase4 = _infer_phase_progress(ds, ["decision", "verification"])

    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        phase1_bar=_phase_bar(phase1),
        phase2_bar=_phase_bar(phase2),
        phase3_bar=_phase_bar(phase3),
        phase4_bar=_phase_bar(phase4),
    )

    context_parts = []

    if project_memory:
        context_parts.append(f"## 项目画像\n{project_memory}")
    if user_memory:
        context_parts.append(f"## 用户偏好\n{user_memory}")
    if historical_context:
        context_parts.append(f"## 相似历史需求\n{historical_context}")
    if ds:
        status_lines = [f"- {dim}: {status}" for dim, status in ds.items()]
        context_parts.append("## 当前维度状态\n" + "\n".join(status_lines))
    if pending_actions:
        pa_lines = [
            f"- [{a.get('priority', '?')}] {a.get('action', '')}" for a in pending_actions[:3]
        ]
        if pa_lines:
            context_parts.append("## 上轮建议的后续行动\n" + "\n".join(pa_lines))

    if context_parts:
        prompt += "\n## 当前位置\n" + "\n\n".join(context_parts)

    if template_sections:
        section_lines = []
        for sec in template_sections:
            req = sec.get("requirements", "")
            dims = ", ".join(sec.get("dimensions", []))
            section_lines.append(
                f"- {sec['title']}（{sec['id']}）: {sec['description']}"
                + (f" [{dims}]" if dims else "")
            )
            if req:
                section_lines.append(f"  写作要求: {req}")
        if section_lines:
            prompt += "\n## 报告章节要求\n" + "\n".join(section_lines)

    return prompt


def build_step_user_prompt(
    requirement_text: str,
    step_count: int,
    max_steps: int,
    weak_dimensions: str = "",
    evidence_count: int = 0,
    depth: str = "standard",
) -> str:
    weak_section = f"需要补充证据的维度：{weak_dimensions}" if weak_dimensions else ""
    prompt = USER_PROMPT_TEMPLATE.format(
        requirement_text=requirement_text,
        step_count=step_count,
        max_steps=max_steps,
        evidence_count=evidence_count,
        weak_dimensions_section=weak_section,
    )
    if depth == "quick":
        prompt = QUICK_MODE_NOTE + "\n" + prompt
    return prompt


def build_termination_prompt() -> str:
    return """你已达到分析步数上限或所有维度已达标。请基于已收集的所有证据，直接输出最终分析结果。

输出要求：
1. 所有结论必须引用具体证据来源
2. 每个维度都应有明确内容
3. 风险评级必须基于代码依据
4. 提出可操作的决策建议"""
