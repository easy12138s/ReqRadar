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
    verification_points: list[str] = field(default_factory=list)
    implementation_hints: ImplementationHints = field(default_factory=ImplementationHints)


@dataclass
class GeneratedContent:
    requirement_understanding: str = ""
    impact_narrative: str = ""
    risk_narrative: str = ""
    implementation_suggestion: str = ""


@dataclass
class AnalysisContext:
    requirement_path: Path
    requirement_text: str = ""
    memory_data: Optional[dict] = None
    understanding: Optional[RequirementUnderstanding] = None
    retrieved_context: Optional[RetrievedContext] = None
    deep_analysis: Optional[DeepAnalysis] = None
    generated_content: Optional[GeneratedContent] = None
    expanded_keywords: list[str] = field(default_factory=list)
    step_results: dict[str, StepResult] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None

    @property
    def completeness(self) -> str:
        steps_completed = sum(1 for r in self.step_results.values() if r.success)
        total_steps = len(self.step_results)
        if total_steps == 0:
            return "empty"
        ratio = steps_completed / total_steps
        if ratio >= 1.0:
            return "full"
        elif ratio >= 0.5:
            return "partial"
        else:
            return "degraded"

    @property
    def overall_confidence(self) -> float:
        if not self.step_results:
            return 0.0
        return sum(r.confidence for r in self.step_results.values()) / len(self.step_results)

    @property
    def content_confidence(self) -> str:
        has_risk = self.deep_analysis and self.deep_analysis.risk_level not in ("unknown", "")
        has_terms = self.understanding and len(self.understanding.terms) > 0
        has_understanding = self.understanding and bool(self.understanding.summary)
        if has_risk and has_terms and has_understanding:
            return "high"
        elif has_risk or has_terms or has_understanding:
            return "medium"
        else:
            return "low"

    def store_result(self, step: str, result: StepResult):
        self.step_results[step] = result

    def get_result(self, step: str) -> Optional[StepResult]:
        return self.step_results.get(step)

    def finalize(self):
        self.completed_at = datetime.now()
