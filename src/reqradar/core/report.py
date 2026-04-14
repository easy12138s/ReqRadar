"""报告生成器"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Template

from reqradar.core.context import AnalysisContext
from reqradar.infrastructure.config import Config

DEFAULT_TEMPLATE = """# 需求透视报告：{{ requirement_title }}

> 分析时间：{{ timestamp }}
> 需求文件：{{ requirement_path }}

---

## 一、需求摘要

{{ summary | default("无法生成摘要") }}

**关键词**：{{ keywords | join(", ") | default("无") }}

**约束条件**：
{% if constraints %}
{% for c in constraints %}
- {{ c }}
{% endfor %}
{% else %}
- 无
{% endif %}

---

## 二、相似历史需求

{% if similar_requirements %}
{% for req in similar_requirements %}
- **{{ req.metadata.title | default(req.id) }}** (相似度: {{ (1 - req.distance) | round(2) }})
  {{ req.metadata.outcome | default("") }}
{% endfor %}
{% else %}
*未发现相似历史需求*
{% endif %}

---

## 三、技术影响分析

{% if impact_modules %}
### 3.1 涉及模块

| 模块 | 相关函数 |
|:---|:---|
{% for m in impact_modules %}
| {{ m.path }} | {{ m.symbols | join(", ") }} |
{% endfor %}

{% else %}
暂无代码影响分析数据
{% endif %}

---

## 四、建议评审人

{% if contributors %}
{% for c in contributors %}
- **{{ c.name }}**（{{ c.reason }}）
  - 文件：{{ c.file }}
{% endfor %}
{% else %}
*未找到相关评审人信息*
{% endif %}

---

## 五、风险评估

**总体风险等级**：{{ risk_level | default("unknown") }}

---

## 六、自然语言描述

{{ understanding | default("无") }}

---

## 七、数据完整性说明

- 分析置信度：{{ confidence | round(2) }}%
- 数据完整度：{{ completeness }}

{% if warnings %}
### 警告
{% for w in warnings %}
- {{ w }}
{% endfor %}
{% endif %}

---

*本报告由 ReqRadar 自动生成，仅供参考。*
"""


class ReportRenderer:
    """报告渲染器"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config
        self.template = Template(DEFAULT_TEMPLATE)

    def render(self, context: AnalysisContext, generated_content: dict = None) -> str:
        """渲染报告"""

        understanding = context.understanding
        analysis = context.deep_analysis
        retrieved = context.retrieved_context

        warnings = []
        for step_name, result in context.step_results.items():
            if not result.success:
                warnings.append(f"步骤 {step_name} 执行失败: {result.error}")

        template_data = {
            "requirement_title": context.requirement_path.stem,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "requirement_path": str(context.requirement_path),
            "summary": understanding.summary if understanding else "无法生成",
            "keywords": understanding.keywords if understanding else [],
            "constraints": understanding.constraints if understanding else [],
            "similar_requirements": retrieved.similar_requirements if retrieved else [],
            "impact_modules": analysis.impact_modules if analysis else [],
            "contributors": analysis.contributors if analysis else [],
            "risk_level": analysis.risk_level if analysis else "unknown",
            "understanding": generated_content.get("understanding") if generated_content else None,
            "confidence": context.overall_confidence * 100,
            "completeness": context.completeness,
            "warnings": warnings,
        }

        return self.template.render(**template_data)

    def save(self, content: str, output_path: Path):
        """保存报告到文件"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
