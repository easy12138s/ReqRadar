"""测试上下文管理"""

from pathlib import Path

from reqradar.core.context import (
    AnalysisContext,
    DecisionSummary,
    DecisionSummaryItem,
    DeepAnalysis,
    GeneratedContent,
    RequirementUnderstanding,
    StepResult,
    TermDefinition,
)


def test_analysis_context_creation():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    assert ctx.requirement_path == Path("test.md")
    assert ctx.step_results == {}
    assert not ctx.is_complete


def test_step_result_storage():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    result = StepResult(step="test", success=True, confidence=1.0)
    ctx.store_result("test", result)

    assert ctx.get_result("test") == result
    assert ctx.get_result("nonexistent") is None


def test_completeness_calculation():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    assert ctx.completeness == "empty"

    ctx.store_result("step1", StepResult(step="step1", success=True))
    ctx.store_result("step2", StepResult(step="step2", success=False))

    assert ctx.completeness == "partial"

    ctx.store_result("step3", StepResult(step="step3", success=True))
    ctx.store_result("step4", StepResult(step="step4", success=True))

    assert ctx.completeness == "partial"

    ctx.store_result("step2", StepResult(step="step2", success=True))

    assert ctx.completeness == "full"


def test_process_completion_reflects_step_success_ratio():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    assert ctx.process_completion == "empty"

    ctx.store_result("step1", StepResult(step="step1", success=True))
    ctx.store_result("step2", StepResult(step="step2", success=False))

    assert ctx.process_completion == "partial"


def test_content_completeness_requires_multiple_content_sections():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    ctx.understanding = RequirementUnderstanding(summary="Test summary")

    assert ctx.content_completeness == "partial"

    ctx.deep_analysis = DeepAnalysis(
        risk_level="medium",
        impact_narrative="Affects API and service layers.",
        risk_narrative="Integration risk remains manageable.",
    )
    ctx.generated_content = GeneratedContent(
        requirement_understanding="Detailed understanding",
        executive_summary="Proceed in phases.",
        technical_summary="Touches API and orchestration.",
        implementation_suggestion="Start with read-only scope.",
    )

    assert ctx.content_completeness == "full"


def test_evidence_support_requires_explicit_evidence_or_impact_domains():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    ctx.deep_analysis = DeepAnalysis(risk_level="medium")

    assert ctx.evidence_support == "low"

    ctx.deep_analysis.evidence_items = [
        type("Evidence", (), {"summary": "Requirement cites API scope.", "confidence": "high"})()
    ]

    assert ctx.evidence_support == "medium"

    ctx.deep_analysis.impact_domains = [
        type("ImpactDomain", (), {"domain": "web_api", "basis": "Requirement mandates API layer."})()
    ]

    assert ctx.evidence_support == "high"


def test_confidence_calculation():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    ctx.store_result("step1", StepResult(step="step1", success=True, confidence=1.0))
    ctx.store_result("step2", StepResult(step="step2", success=True, confidence=0.5))

    assert ctx.overall_confidence == 0.75


def test_deep_analysis_has_narrative_fields():
    da = DeepAnalysis()
    assert hasattr(da, "impact_narrative")
    assert hasattr(da, "risk_narrative")
    assert da.impact_narrative == ""
    assert da.risk_narrative == ""


def test_decision_summary_defaults_to_empty_structure():
    summary = DecisionSummary()

    assert summary.summary == ""
    assert summary.decisions == []
    assert summary.open_questions == []
    assert summary.follow_ups == []


def test_content_confidence_is_not_high_without_substantive_report_content():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    ctx.understanding = RequirementUnderstanding(
        summary="Test summary",
        terms=[TermDefinition(term="API", definition="接口")],
    )
    ctx.deep_analysis = DeepAnalysis(risk_level="medium")

    assert ctx.content_confidence == "medium"


def test_content_confidence_is_high_with_generated_report_content():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    ctx.understanding = RequirementUnderstanding(
        summary="Test summary",
        terms=[TermDefinition(term="API", definition="接口")],
    )
    ctx.deep_analysis = DeepAnalysis(risk_level="medium")
    ctx.generated_content = GeneratedContent(
        requirement_understanding="Detailed requirement understanding",
        impact_narrative="Impact reaches API and service layers.",
        risk_narrative="Performance regression is the primary risk.",
    )

    assert ctx.content_confidence == "high"


def test_content_confidence_is_high_with_decision_summary_content():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    ctx.understanding = RequirementUnderstanding(summary="Test summary")
    ctx.deep_analysis = DeepAnalysis(risk_level="medium")
    ctx.decision_summary = DecisionSummary(
        summary="Adopt incremental rollout for the API change.",
        decisions=[
            DecisionSummaryItem(
                topic="release_strategy",
                decision="Use a feature flag for rollout.",
                rationale="Reduces production risk while validating behavior.",
            )
        ],
    )

    assert ctx.content_confidence == "high"


def test_content_confidence_ignores_empty_decision_summary_items():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    ctx.understanding = RequirementUnderstanding(summary="Test summary")
    ctx.deep_analysis = DeepAnalysis(risk_level="medium")
    ctx.decision_summary = DecisionSummary(
        decisions=[DecisionSummaryItem()],
    )

    assert ctx.content_confidence == "medium"
