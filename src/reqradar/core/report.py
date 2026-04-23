"""报告生成器"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Template

from reqradar.core.context import AnalysisContext
from reqradar.infrastructure.config import Config

logger = logging.getLogger("reqradar.report")

DEFAULT_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "report.md.j2"


def _risk_level_to_badge(risk_level: str) -> str:
    badges = {
        "critical": "🔴 极高",
        "high": "🟠 高",
        "medium": "🟡 中",
        "low": "🟢 低",
        "unknown": "⚪ 未知",
    }
    return badges.get(risk_level.lower(), "⚪ 未知")


class ReportRenderer:

    def __init__(self, config: Optional[Config] = None):
        self.config = config
        template_path = DEFAULT_TEMPLATE_PATH
        if config and config.output.report_template and config.output.report_template != "default":
            custom_path = Path(config.output.report_template)
            if custom_path.exists():
                template_path = custom_path
            else:
                logger.warning("Custom template not found: %s, using default", custom_path)

        try:
            with open(template_path, encoding="utf-8") as f:
                self.template = Template(f.read())
        except FileNotFoundError:
            logger.warning("Template file not found: %s, using inline fallback", template_path)
            self.template = Template(_INLINE_FALLBACK_TEMPLATE)

    def render(self, context: AnalysisContext, generated_content: dict = None) -> str:
        understanding = context.understanding
        analysis = context.deep_analysis
        retrieved = context.retrieved_context
        gen = context.generated_content

        warnings = []
        for step_name, result in context.step_results.items():
            if not result.success:
                warnings.append(f"步骤 {step_name} 执行失败: {result.error}")

        risk_level = analysis.risk_level if analysis else "unknown"
        risk_badge = _risk_level_to_badge(risk_level)

        code_hits = len(analysis.impact_modules) if analysis else 0
        domain_count = len(analysis.impact_domains) if analysis else 0
        if analysis and analysis.change_assessment:
            code_hits = max(code_hits, len(analysis.change_assessment))
        if domain_count > 0:
            impact_scope = f"{code_hits} 个代码命中 + {domain_count} 个推断影响域"
        elif code_hits > 0:
            impact_scope = f"{code_hits} 个代码命中"
        else:
            impact_scope = "未匹配到直接代码"

        priority = understanding.priority_suggestion if understanding and understanding.priority_suggestion else "未定"
        priority_reason = understanding.priority_reason if understanding else ""

        project_profile = None
        modules_info = None
        if context.memory_data:
            project_profile = context.memory_data.get("project_profile")
            modules_info = context.memory_data.get("modules", [])

        impact_narrative = gen.impact_narrative if gen and gen.impact_narrative else ""
        if not impact_narrative and analysis and analysis.impact_narrative:
            impact_narrative = analysis.impact_narrative

        risk_narrative = gen.risk_narrative if gen and gen.risk_narrative else ""
        if not risk_narrative and analysis and analysis.risk_narrative:
            risk_narrative = analysis.risk_narrative

        implementation_suggestion = gen.implementation_suggestion if gen and gen.implementation_suggestion else ""
        executive_summary = gen.executive_summary if gen and gen.executive_summary else ""
        technical_summary = gen.technical_summary if gen and gen.technical_summary else ""
        decision_highlights = gen.decision_highlights if gen and gen.decision_highlights else []

        decision_summary = analysis.decision_summary if analysis else None
        evidence_items = analysis.evidence_items if analysis else []
        impact_domains = analysis.impact_domains if analysis else []

        formatted_project_profile = None
        if project_profile and isinstance(project_profile, dict):
            formatted_project_profile = dict(project_profile)
            ts = formatted_project_profile.get("tech_stack", {})
            if isinstance(ts, dict):
                parts = []
                if ts.get("languages"):
                    parts.append("语言: " + ", ".join(ts["languages"]))
                if ts.get("frameworks"):
                    parts.append("框架: " + ", ".join(ts["frameworks"]))
                if ts.get("key_dependencies"):
                    parts.append("依赖: " + ", ".join(ts["key_dependencies"]))
                formatted_project_profile["tech_stack"] = "; ".join(parts) if parts else "未知"

        template_data = {
            "requirement_title": context.requirement_path.stem,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "requirement_path": str(context.requirement_path),
            "requirement_understanding": gen.requirement_understanding if gen else (understanding.summary if understanding else "无法生成"),
            "executive_summary": executive_summary,
            "technical_summary": technical_summary,
            "decision_highlights": decision_highlights,
            "decision_summary": decision_summary,
            "evidence_items": evidence_items,
            "impact_domains": impact_domains,
            "terms": [t.model_dump() for t in understanding.terms] if understanding and understanding.terms else [],
            "keywords": understanding.keywords if understanding else [],
            "constraints": understanding.constraints if understanding else [],
            "structured_constraints": [c.model_dump() for c in understanding.structured_constraints] if understanding and understanding.structured_constraints else [],
            "similar_requirements": retrieved.similar_requirements if retrieved else [],
            "impact_modules": analysis.impact_modules if analysis else [],
            "change_assessment": [ca.model_dump() for ca in analysis.change_assessment] if analysis and analysis.change_assessment else [],
            "impact_narrative": impact_narrative,
            "contributors": analysis.contributors if analysis else [],
            "risk_level": risk_level,
            "risk_badge": risk_badge,
            "risks": [r.model_dump() for r in analysis.risks] if analysis and analysis.risks else [],
            "risk_details": analysis.risk_details if analysis else [],
            "risk_narrative": risk_narrative,
            "verification_points": analysis.verification_points if analysis else [],
            "implementation_hints": analysis.implementation_hints.model_dump() if analysis and analysis.implementation_hints else None,
            "implementation_suggestion": implementation_suggestion,
            "priority": priority,
            "priority_reason": priority_reason,
            "impact_scope": impact_scope,
            "confidence": context.overall_confidence * 100,
            "process_completion": context.process_completion,
            "content_completeness": context.content_completeness,
            "evidence_support": context.evidence_support,
            "content_confidence": context.content_confidence,
            "warnings": warnings,
            "project_profile": formatted_project_profile,
            "modules_info": modules_info,
        }

        return self.template.render(**template_data)

    def save(self, content: str, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)


_INLINE_FALLBACK_TEMPLATE = """# 需求分析报告：{{ requirement_title }}

## 报告概况

| 字段 | 内容 |
|:---|:---|
| 需求标题 | {{ requirement_title }} |
| 分析时间 | {{ timestamp }} |
| 需求来源 | {{ requirement_path }} |
| 风险等级 | {{ risk_badge }} |
| 影响范围 | {{ impact_scope }} |
| 建议优先级 | {{ priority }} |
| 内容可信度 | {{ content_confidence }} |

---

## 第一层：决策摘要

> 面向产品、管理层和评审人——提供可操作的结论与依据。

{% if executive_summary %}
## 总体判断

{{ executive_summary }}
{% endif %}

{% if decision_summary and decision_summary.summary %}
## 决策摘要

{{ decision_summary.summary }}
{% endif %}

{% if decision_summary and decision_summary.decisions %}
### 1. 结论与证据

| 主题 | 决策 | 依据 | 影响 |
|:---|:---|:---|:---|
{% for d in decision_summary.decisions %}
| {{ d.topic }} | {{ d.decision }} | {{ d.rationale }} | {{ d.implications | join("；") }} |
{% endfor %}
{% elif decision_highlights %}
### 1. 结论与证据

{% for h in decision_highlights %}
- {{ h }}
{% endfor %}
{% endif %}

{% if evidence_items %}
### 2. 支撑证据

| 类型 | 来源 | 摘要 | 可信度 |
|:---|:---|:---|:---|
{% for e in evidence_items %}
| {{ e.kind }} | {{ e.source }} | {{ e.summary }} | {{ e.confidence }} |
{% endfor %}
{% endif %}

{% if decision_summary and decision_summary.open_questions %}
### 3. 待定问题

{% for q in decision_summary.open_questions %}
- {{ q }}
{% endfor %}
{% endif %}

{% if decision_summary and decision_summary.follow_ups %}
### 4. 后续跟进

{% for f in decision_summary.follow_ups %}
- {{ f }}
{% endfor %}
{% endif %}

---

## 技术支撑

> 面向开发者与架构师——提供完整的技术依据与实施细节。

{% if technical_summary %}
## 技术概述

{{ technical_summary }}
{% endif %}

## 需求理解

### 需求概述

{{ requirement_understanding | default("暂无需求理解数据") }}

{% if terms %}
### 核心术语

| 术语 | 定义 | 所属领域 |
|:---|:---|:---|
{% for t in terms %}
| {{ t.term }} | {{ t.definition }} | {{ t.domain }} |
{% endfor %}
{% endif %}

---

## 影响分析

{% if impact_domains %}
### 4. 影响域与模块

| 影响域 | 置信度 | 推断依据 | 推断 |
|:---|:---|:---|:---|
{% for d in impact_domains %}
| {{ d.domain }} | {{ d.confidence }} | {{ d.basis }} | {% if d.inferred %}是{% else %}否{% endif %} |
{% endfor %}
{% endif %}

{% if impact_modules %}
### 代码命中

| 模块 | 核心类/方法 |
|:---|:---|
{% for m in impact_modules %}
| {{ m.path }} | {{ m.symbols | join(", ") }} |
{% endfor %}
{% endif %}

{% if change_assessment %}
### 变更评估

| 模块 | 变更类型 | 影响等级 | 原因 |
|:---|:---|:---|:---|
{% for ca in change_assessment %}
| {{ ca.module }} | {{ ca.change_type }} | {{ ca.impact_level }} | {{ ca.reason }} |
{% endfor %}
{% endif %}

{% if impact_narrative %}
### 影响范围描述

{{ impact_narrative }}
{% endif %}

---

## 风险评估

**总体风险等级**：{{ risk_badge }}

{% if risks %}
| 风险项 | 等级 | 影响范围 | 缓解建议 |
|:---|:---|:---|:---|
{% for r in risks %}
| {{ r.description }} | {{ r.severity }} | {{ r.scope }} | {{ r.mitigation }} |
{% endfor %}
{% endif %}

{% if risk_narrative %}
### 风险分析描述

{{ risk_narrative }}
{% endif %}

{% if verification_points %}
### 验证要点

{% for v in verification_points %}
{{ loop.index }}. {{ v }}
{% endfor %}
{% endif %}

---

## 建议评审人

{% if contributors %}
| 姓名 | 角色 | 负责模块 |
|:---|:---|:---|
{% for c in contributors %}
| {{ c.name }} | {{ c.role }} | {{ c.file }} |
{% endfor %}
{% else %}
*未找到相关评审人信息*
{% endif %}

---

## 实施建议

### 建议优先级

{{ priority }}

### 实施方向

{{ implementation_suggestion | default("暂无实施建议") }}

---

## 附录. 数据完整性

| 指标 | 值 |
|:---|:---|
| 流程完成度 | {{ process_completion }} |
| 内容完整度 | {{ content_completeness }} |
| 证据支撑度 | {{ evidence_support }} |

{% if warnings %}
### 警告

{% for w in warnings %}
- {{ w }}
{% endfor %}
{% endif %}

---

*本报告由 ReqRadar 自动生成，仅供参考。*
"""
