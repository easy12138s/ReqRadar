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
    """将风险等级转换为可视化徽章"""
    badges = {
        "critical": "🔴 极高",
        "high": "🟠 高",
        "medium": "🟡 中",
        "low": "🟢 低",
        "unknown": "⚪ 未知",
    }
    return badges.get(risk_level.lower(), "⚪ 未知")


class ReportRenderer:
    """报告渲染器"""

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
        """渲染报告"""

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

        impact_scope = len(analysis.impact_modules) if analysis else 0
        if analysis and analysis.change_assessment:
            impact_scope = max(impact_scope, len(analysis.change_assessment))

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
        "terms": [t.__dict__ for t in understanding.terms] if understanding and understanding.terms else [],
        "keywords": understanding.keywords if understanding else [],
        "constraints": understanding.constraints if understanding else [],
        "structured_constraints": [c.__dict__ for c in understanding.structured_constraints] if understanding and understanding.structured_constraints else [],
        "similar_requirements": retrieved.similar_requirements if retrieved else [],
        "impact_modules": analysis.impact_modules if analysis else [],
        "change_assessment": [ca.__dict__ for ca in analysis.change_assessment] if analysis and analysis.change_assessment else [],
        "impact_narrative": impact_narrative,
        "contributors": analysis.contributors if analysis else [],
        "risk_level": risk_level,
        "risk_badge": risk_badge,
        "risks": [r.__dict__ for r in analysis.risks] if analysis and analysis.risks else [],
        "risk_details": analysis.risk_details if analysis else [],
        "risk_narrative": risk_narrative,
        "verification_points": analysis.verification_points if analysis else [],
        "implementation_hints": analysis.implementation_hints.__dict__ if analysis and analysis.implementation_hints else None,
        "implementation_suggestion": implementation_suggestion,
        "priority": priority,
        "priority_reason": priority_reason,
        "impact_scope": impact_scope,
        "confidence": context.overall_confidence * 100,
        "completeness": context.completeness,
        "content_confidence": context.content_confidence,
        "warnings": warnings,
        "project_profile": formatted_project_profile,
        "modules_info": modules_info,
        }

        return self.template.render(**template_data)

    def save(self, content: str, output_path: Path):
        """保存报告到文件"""
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
| 影响范围 | {{ impact_scope }} 个模块 |
| 建议优先级 | {{ priority }} |

---

## 1. 需求理解

### 1.1 需求概述

{{ requirement_understanding | default("暂无需求理解数据") }}

{% if terms %}
### 1.2 核心术语

| 术语 | 定义 | 所属领域 |
|:---|:---|:---|
{% for t in terms %}
| {{ t.term }} | {{ t.definition }} | {{ t.domain }} |
{% endfor %}
{% endif %}

---

## 2. 影响分析

{% if impact_modules %}
### 2.1 代码影响范围

| 模块 | 核心类/方法 |
|:---|:---|
{% for m in impact_modules %}
| {{ m.path }} | {{ m.symbols | join(", ") }} |
{% endfor %}
{% endif %}

{% if change_assessment %}
### 2.2 变更评估

| 模块 | 变更类型 | 影响等级 | 原因 |
|:---|:---|:---|:---|
{% for ca in change_assessment %}
| {{ ca.module }} | {{ ca.change_type }} | {{ ca.impact_level }} | {{ ca.reason }} |
{% endfor %}
{% endif %}

---

## 3. 风险评估

**总体风险等级**：{{ risk_badge }}

{% if risks %}
| 风险项 | 等级 | 影响范围 | 缓解建议 |
|:---|:---|:---|:---|
{% for r in risks %}
| {{ r.description }} | {{ r.severity }} | {{ r.scope }} | {{ r.mitigation }} |
{% endfor %}
{% endif %}

{% if verification_points %}
### 验证要点

{% for v in verification_points %}
{{ loop.index }}. {{ v }}
{% endfor %}
{% endif %}

---

## 4. 建议评审人

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

## 5. 实施建议

### 5.1 建议优先级

{{ priority }}

### 5.2 实施方向

{{ implementation_suggestion | default("暂无实施建议") }}

---

## 附录. 数据完整性

- 分析置信度：{{ confidence | round(1) }}%
- 数据完整度：{{ completeness }}
- 内容可信度：{{ content_confidence }}

{% if warnings %}
### 警告

{% for w in warnings %}
- {{ w }}
{% endfor %}
{% endif %}

---

*本报告由 ReqRadar 自动生成，仅供参考。*
"""
