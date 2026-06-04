"""报告生成器"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Template

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
    def __init__(self, config=None, template_definition=None, render_template_str=None):
        self.config = config
        self.template_definition = template_definition
        if render_template_str:
            from jinja2 import Template as JinjaTemplate

            self.template = JinjaTemplate(render_template_str)
        else:
            template_path = DEFAULT_TEMPLATE_PATH
            if (
                config
                and hasattr(config, "output")
                and config.output.report_template
                and config.output.report_template != "default"
            ):
                custom_path = Path(config.output.report_template)
                if custom_path.exists():
                    template_path = custom_path
            with open(template_path, "r", encoding="utf-8") as f:
                from jinja2 import Template as JinjaTemplate

                self.template = JinjaTemplate(f.read())

    def render_from_data(self, report_data: dict) -> str:
        template_data = dict(report_data)
        risk_level = template_data.get("risk_level", "unknown")
        template_data.setdefault("risk_badge", _risk_level_to_badge(risk_level))
        template_data.setdefault("content_completeness", "partial")
        template_data.setdefault("evidence_support", "low")
        template_data.setdefault("content_confidence", "medium")
        template_data.setdefault("process_completion", "full")
        template_data.setdefault("priority", "unknown")
        template_data.setdefault("priority_reason", "")
        template_data.setdefault("warnings", [])
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
