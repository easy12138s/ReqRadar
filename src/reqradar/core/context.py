"""分析上下文 - 管理步骤间的数据传递"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class StepResult:
    step: str
    success: bool
    confidence: float = 1.0
    data: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def mark_failed(self, error: str, confidence: float = 0.0):
        self.success = False
        self.error = error
        self.confidence = confidence


@dataclass
class TermDefinition:
    term: str = ""
    definition: str = ""
    domain: str = ""


@dataclass
class StructuredConstraint:
    description: str = ""
    constraint_type: str = ""
    source: str = ""


@dataclass
class RequirementUnderstanding:
    raw_text: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    terms: list[TermDefinition] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    structured_constraints: list[StructuredConstraint] = field(default_factory=list)
    business_goals: str = ""
    priority_suggestion: str = ""
    priority_reason: str = ""


@dataclass
class RetrievedContext:
    similar_requirements: list = field(default_factory=list)
    code_files: list = field(default_factory=list)


@dataclass
class RiskItem:
    description: str = ""
    severity: str = ""
    scope: str = ""
    mitigation: str = ""


@dataclass
class ChangeAssessment:
    module: str = ""
    change_type: str = ""
    impact_level: str = ""
    reason: str = ""


@dataclass
class ImplementationHints:
    approach: str = ""
    effort_estimate: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class DeepAnalysis:
    impact_modules: list = field(default_factory=list)
    contributors: list = field(default_factory=list)
    risk_level: str = "unknown"
    risk_details: list = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    change_assessment: list[ChangeAssessment] = field(default_factory=list)
    decision_summary: "DecisionSummary" = field(default_factory=lambda: DecisionSummary())
    evidence_items: list["EvidenceItem"] = field(default_factory=list)
    impact_domains: list["ImpactDomain"] = field(default_factory=list)
    verification_points: list[str] = field(default_factory=list)
    implementation_hints: ImplementationHints = field(default_factory=ImplementationHints)
    impact_narrative: str = ""
    risk_narrative: str = ""


@dataclass
class GeneratedContent:
    requirement_understanding: str = ""
    executive_summary: str = ""
    technical_summary: str = ""
    decision_highlights: list[str] = field(default_factory=list)
    impact_narrative: str = ""
    risk_narrative: str = ""
    implementation_suggestion: str = ""


@dataclass
class DecisionSummaryItem:
    topic: str = ""
    decision: str = ""
    rationale: str = ""
    implications: list[str] = field(default_factory=list)


@dataclass
class DecisionSummary:
    summary: str = ""
    decisions: list[DecisionSummaryItem] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)


@dataclass
class EvidenceItem:
    kind: str = ""
    source: str = ""
    summary: str = ""
    confidence: str = "medium"


@dataclass
class ImpactDomain:
    domain: str = ""
    confidence: str = "medium"
    basis: str = ""
    inferred: bool = False


@dataclass
class ModuleAnalysisResult:
    path: str = ""
    symbols: list[str] = field(default_factory=list)
    relevance: str = "low"
    relevance_reason: str = ""
    suggested_changes: str = ""


@dataclass
class CodeAnalysisResult:
    modules: list[ModuleAnalysisResult] = field(default_factory=list)
    overall_assessment: dict = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class AnalysisContext:
    requirement_path: Path
    requirement_text: str = ""
    memory_data: Optional[dict] = None
    understanding: Optional[RequirementUnderstanding] = None
    retrieved_context: Optional[RetrievedContext] = None
    deep_analysis: Optional[DeepAnalysis] = None
    generated_content: Optional[GeneratedContent] = None
    decision_summary: Optional[DecisionSummary] = None
    expanded_keywords: list[str] = field(default_factory=list)
    code_analysis: Optional[CodeAnalysisResult] = None
    step_results: dict[str, StepResult] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None

    @property
    def process_completion(self) -> str:
        steps_completed = sum(1 for r in self.step_results.values() if r.success)
        total_steps = len(self.step_results)
        if total_steps == 0:
            return "empty"
        ratio = steps_completed / total_steps
        if ratio >= 1.0:
            return "full"
        if ratio >= 0.5:
            return "partial"
        return "degraded"

    @property
    def completeness(self) -> str:
        return self.process_completion

    @property
    def overall_confidence(self) -> float:
        if not self.step_results:
            return 0.0
        return sum(r.confidence for r in self.step_results.values()) / len(self.step_results)

    @property
    def content_completeness(self) -> str:
        sections = 0

        if self.understanding and self.understanding.summary.strip():
            sections += 1

        if self.deep_analysis and any(
            (
                bool(self.deep_analysis.impact_narrative.strip()),
                bool(self.deep_analysis.risk_narrative.strip()),
                bool(self.deep_analysis.risks),
                bool(self.deep_analysis.change_assessment),
                bool(self.deep_analysis.verification_points),
            )
        ):
            sections += 1

        if self.generated_content and any(
            bool(value.strip())
            for value in (
                self.generated_content.requirement_understanding,
                self.generated_content.executive_summary,
                self.generated_content.technical_summary,
                self.generated_content.impact_narrative,
                self.generated_content.risk_narrative,
                self.generated_content.implementation_suggestion,
            )
        ):
            sections += 1

        decision_summary = self.decision_summary
        if not decision_summary and self.deep_analysis:
            decision_summary = self.deep_analysis.decision_summary
        if decision_summary and (
            bool(decision_summary.summary.strip())
            or bool(decision_summary.decisions)
            or bool(decision_summary.open_questions)
            or bool(decision_summary.follow_ups)
        ):
            sections += 1

        if sections >= 3:
            return "full"
        if sections >= 1:
            return "partial"
        return "low"

    @property
    def evidence_support(self) -> str:
        if not self.deep_analysis:
            return "low"

        evidence_items = self.deep_analysis.evidence_items
        impact_domains = self.deep_analysis.impact_domains

        has_evidence = any(
            bool(item.summary.strip()) or bool(item.source.strip())
            for item in evidence_items
        )
        has_domains = any(
            bool(domain.domain.strip()) or bool(domain.basis.strip())
            for domain in impact_domains
        )

        if has_evidence and has_domains:
            return "high"
        if has_evidence or has_domains:
            return "medium"
        return "low"

    @property
    def content_confidence(self) -> str:
        has_risk = self.deep_analysis and self.deep_analysis.risk_level not in ("unknown", "")
        has_terms = self.understanding and len(self.understanding.terms) > 0
        has_understanding = self.understanding and bool(self.understanding.summary)
        has_generated_content = self.generated_content and any(
            bool(value.strip())
            for value in (
                self.generated_content.requirement_understanding,
                self.generated_content.impact_narrative,
                self.generated_content.risk_narrative,
                self.generated_content.implementation_suggestion,
            )
        )
        decision_summary = self.decision_summary
        if not decision_summary and self.deep_analysis:
            decision_summary = self.deep_analysis.decision_summary

        has_decision_summary = decision_summary and (
            bool(decision_summary.summary.strip())
            or any(
                bool(item.topic.strip())
                or bool(item.decision.strip())
                or bool(item.rationale.strip())
                or any(bool(implication.strip()) for implication in item.implications)
                for item in decision_summary.decisions
            )
            or any(bool(question.strip()) for question in decision_summary.open_questions)
            or any(bool(follow_up.strip()) for follow_up in decision_summary.follow_ups)
        )
        has_substantive_content = bool(has_generated_content or has_decision_summary)

        if has_risk and has_understanding and has_substantive_content:
            return "high"
        elif has_risk or has_terms or has_understanding or has_substantive_content:
            return "medium"
        else:
            return "low"

    def store_result(self, step: str, result: StepResult):
        self.step_results[step] = result

    def get_result(self, step: str) -> Optional[StepResult]:
        return self.step_results.get(step)

    def finalize(self):
        self.completed_at = datetime.now()
