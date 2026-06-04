"""V1 vs V2 对比测试框架 — P1.10 质量评估基础设施。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class QualityDimension:
    """质量评估维度。"""

    name: str
    description: str
    v1_score: float = 0.0
    v2_score: float = 0.0
    weight: float = 1.0


@dataclass
class ComparisonResult:
    """单次对比测试结果。"""

    req_file: str
    v1_context: str = ""
    v2_context: str = ""
    v1_token_count: int = 0
    v2_token_count: int = 0
    v1_latency_ms: float = 0.0
    v2_latency_ms: float = 0.0
    dimensions: list[QualityDimension] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    fail_fast_triggered: bool = False
    fail_fast_reason: str = ""


QUALITY_DIMENSIONS = [
    QualityDimension("risk_identification", "风险识别准确率：V2 是否识别了 V1 识别到的所有风险点"),
    QualityDimension("evidence_traceability", "证据溯源完整度：结论是否可追溯到 L0/L1 证据"),
    QualityDimension("analysis_coverage", "分析覆盖度：应覆盖模块的命中率"),
    QualityDimension("overall_quality", "整体质量：LLM-as-judge 对完整性/准确性/可操作性打分"),
]

COST_DIMENSIONS = [
    QualityDimension("token_cost_ratio", "Token 成本比：V2 token / V1 token ≤ 1.5"),
    QualityDimension("assembly_latency", "Assembly 延迟：Collect → Assemble ≤ 2s"),
    QualityDimension("total_latency_ratio", "总延迟比：V2 延迟 / V1 延迟 ≤ 1.3"),
]


LLM_JUDGE_PROMPT_TEMPLATE = """你是一个软件工程需求分析质量评审专家。

请对以下两份需求分析报告进行对比评审，从 4 个维度分别打分（1-10 分）：

## 评审维度

1. **风险识别准确率**：报告是否识别了需求中的潜在风险？
2. **证据溯源完整度**：每个结论是否有明确的证据来源？
3. **分析覆盖度**：报告是否覆盖了需求涉及的所有关键模块？
4. **整体质量**：报告的完整性、准确性、可操作性综合评分

## 需求文档

{requirement_text}

## V1 分析报告

{v1_report}

## V2 分析报告

{v2_report}

## 输出格式（JSON）

```json
{{
  "risk_identification": {{"v1": <score>, "v2": <score>, "reason": "<对比说明>"}},
  "evidence_traceability": {{"v1": <score>, "v2": <score>, "reason": "<对比说明>"}},
  "analysis_coverage": {{"v1": <score>, "v2": <score>, "reason": "<对比说明>"}},
  "overall_quality": {{"v1": <score>, "v2": <score>, "reason": "<对比说明>"}}
}}
```
"""


FAIL_FAST_CONDITIONS = {
    "critical_risk_missed": "关键风险完全未识别（人工标注的高风险点在 V2 报告中无任何提及）",
    "assembly_latency_exceeded": "Assembly 延迟 > 5s（用户不可接受的等待）",
    "token_cost_exceeded": "Token 成本 > V1 的 2 倍（成本失控）",
}


def check_fail_fast(result: ComparisonResult) -> tuple[bool, str]:
    """检查是否触发 fail-fast 条件。

    Args:
        result: 对比测试结果

    Returns:
        (是否触发, 原因)
    """
    if result.v2_latency_ms > 5000:
        return True, FAIL_FAST_CONDITIONS["assembly_latency_exceeded"]

    if result.v1_token_count > 0:
        ratio = result.v2_token_count / result.v1_token_count
        if ratio > 2.0:
            return True, FAIL_FAST_CONDITIONS["token_cost_exceeded"]

    return False, ""


def generate_report(results: list[ComparisonResult], output_path: str | None = None) -> dict:
    """生成对比测试汇总报告。

    Args:
        results: 所有对比测试结果
        output_path: 输出文件路径（可选）

    Returns:
        汇总报告字典
    """
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_tests": len(results),
        "fail_fast_count": sum(1 for r in results if r.fail_fast_triggered),
        "quality_summary": {},
        "cost_summary": {},
        "details": [],
    }

    for dim in QUALITY_DIMENSIONS:
        v1_avg = sum(
            next((d.v1_score for d in r.dimensions if d.name == dim.name), 0.0) for r in results
        ) / max(len(results), 1)
        v2_avg = sum(
            next((d.v2_score for d in r.dimensions if d.name == dim.name), 0.0) for r in results
        ) / max(len(results), 1)
        report["quality_summary"][dim.name] = {
            "v1_avg": round(v1_avg, 2),
            "v2_avg": round(v2_avg, 2),
            "v2_better": v2_avg >= v1_avg,
        }

    for r in results:
        report["details"].append(
            {
                "req_file": r.req_file,
                "v1_tokens": r.v1_token_count,
                "v2_tokens": r.v2_token_count,
                "v1_latency_ms": r.v1_latency_ms,
                "v2_latency_ms": r.v2_latency_ms,
                "fail_fast": r.fail_fast_triggered,
            }
        )

    if output_path:
        Path(output_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return report
