"""Test Pydantic migration of core context models."""
import json
from datetime import datetime
from pathlib import Path

from reqradar.core.context import (
    AnalysisContext,
    ChangeAssessment,
    DecisionSummary,
    DecisionSummaryItem,
    DeepAnalysis,
    EvidenceItem,
    GeneratedContent,
    ImpactDomain,
    ImplementationHints,
    RequirementUnderstanding,
    RetrievedContext,
    RiskItem,
    StepResult,
    StructuredConstraint,
    TermDefinition,
)


def test_term_definition_serialization():
    t = TermDefinition(term="Web模块", definition="浏览器端操作界面", domain="frontend")
    data = t.model_dump()
    assert data["term"] == "Web模块"
    assert data["definition"] == "浏览器端操作界面"
    t2 = TermDefinition.model_validate(data)
    assert t2.term == t.term


def test_step_result_timestamp_serialization():
    sr = StepResult(step="read", success=True)
    data = sr.model_dump()
    assert "timestamp" in data
    sr2 = StepResult.model_validate(data)
    assert isinstance(sr2.timestamp, datetime)


def test_requirement_understanding_serialization():
    u = RequirementUnderstanding(
        raw_text="test",
        summary="A test requirement",
        keywords=["web", "api"],
        terms=[TermDefinition(term="web", definition="网页")],
    )
    data = u.model_dump()
    u2 = RequirementUnderstanding.model_validate(data)
    assert u2.summary == u.summary
    assert len(u2.terms) == 1


def test_deep_analysis_serialization():
    da = DeepAnalysis(
        risk_level="high",
        risks=[RiskItem(description="risk1", severity="high", scope="scope1", mitigation="mit1")],
        change_assessment=[
            ChangeAssessment(module="core", change_type="modify", impact_level="high", reason="reason1")
        ],
        decision_summary=DecisionSummary(
            summary="test decision",
            decisions=[DecisionSummaryItem(topic="t1", decision="d1", rationale="r1")],
        ),
        evidence_items=[EvidenceItem(kind="code_match", source="src/main.py", summary="found")],
        impact_domains=[ImpactDomain(domain="api", confidence="high", basis="code ref")],
    )
    data = da.model_dump()
    da2 = DeepAnalysis.model_validate(data)
    assert da2.risk_level == "high"
    assert len(da2.risks) == 1
    assert len(da2.decision_summary.decisions) == 1


def test_analysis_context_round_trip():
    ctx = AnalysisContext(requirement_path=Path("docs/req.md"))
    ctx.requirement_text = "test content"
    ctx.understanding = RequirementUnderstanding(summary="test")
    ctx.store_result("read", StepResult(step="read", success=True, data="ok"))
    ctx.deep_analysis = DeepAnalysis(risk_level="medium")
    ctx.generated_content = GeneratedContent(executive_summary="summary")
    ctx.decision_summary = DecisionSummary(summary="decide")

    json_str = ctx.model_dump_json()
    ctx2 = AnalysisContext.model_validate_json(json_str)
    assert isinstance(ctx2.requirement_path, Path)
    assert ctx2.understanding.summary == "test"
    assert ctx2.deep_analysis.risk_level == "medium"


def test_model_dump_excludes_private():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    data = ctx.model_dump()
    for key in data:
        assert not key.startswith("_")
        assert not key.startswith("__pydantic")


def test_step_result_mark_failed():
    sr = StepResult(step="read", success=True)
    sr.mark_failed("error msg", confidence=0.2)
    assert sr.success is False
    assert sr.error == "error msg"
    assert sr.confidence == 0.2


def test_analysis_context_path_coercion():
    data = {"requirement_path": "docs/req.md"}
    ctx = AnalysisContext.model_validate(data)
    assert isinstance(ctx.requirement_path, Path)
    assert str(ctx.requirement_path) == "docs/req.md"


def test_analysis_context_properties_survive_serialization():
    ctx = AnalysisContext(requirement_path=Path("test.md"))
    ctx.understanding = RequirementUnderstanding(summary="test")
    ctx.deep_analysis = DeepAnalysis(risk_level="high")
    ctx.store_result("read", StepResult(step="read", success=True))

    json_str = ctx.model_dump_json()
    ctx2 = AnalysisContext.model_validate_json(json_str)
    assert ctx2.process_completion == ctx.process_completion
    assert ctx2.overall_confidence == ctx.overall_confidence
