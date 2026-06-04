"""分析上下文 - 数据模型定义"""

from pydantic import BaseModel, Field


class TermDefinition(BaseModel):
    term: str = ""
    definition: str = ""
    domain: str = ""


class StructuredConstraint(BaseModel):
    description: str = ""
    constraint_type: str = ""
    source: str = ""


class RequirementUnderstanding(BaseModel):
    raw_text: str = ""
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    terms: list[TermDefinition] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    structured_constraints: list[StructuredConstraint] = Field(default_factory=list)
    business_goals: str = ""
    priority_suggestion: str = ""
    priority_reason: str = ""


class RetrievedContext(BaseModel):
    similar_requirements: list = Field(default_factory=list)
    code_files: list = Field(default_factory=list)


class RiskItem(BaseModel):
    description: str = ""
    severity: str = ""
    scope: str = ""
    mitigation: str = ""


class ChangeAssessment(BaseModel):
    module: str = ""
    change_type: str = ""
    impact_level: str = ""
    reason: str = ""


class ImplementationHints(BaseModel):
    approach: str = ""
    effort_estimate: str = ""
    dependencies: list[str] = Field(default_factory=list)


class DecisionSummaryItem(BaseModel):
    topic: str = ""
    decision: str = ""
    rationale: str = ""
    implications: list[str] = Field(default_factory=list)


class DecisionSummary(BaseModel):
    summary: str = ""
    decisions: list[DecisionSummaryItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    kind: str = ""
    source: str = ""
    summary: str = ""
    confidence: str = "medium"


class ImpactDomain(BaseModel):
    domain: str = ""
    confidence: str = "medium"
    basis: str = ""
    inferred: bool = False


class DeepAnalysis(BaseModel):
    impact_modules: list = Field(default_factory=list)
    contributors: list = Field(default_factory=list)
    risk_level: str = "unknown"
    risk_details: list = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    change_assessment: list[ChangeAssessment] = Field(default_factory=list)
    decision_summary: DecisionSummary = Field(default_factory=DecisionSummary)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    impact_domains: list[ImpactDomain] = Field(default_factory=list)
    verification_points: list[str] = Field(default_factory=list)
    implementation_hints: ImplementationHints = Field(default_factory=ImplementationHints)
    impact_narrative: str = ""
    risk_narrative: str = ""


class GeneratedContent(BaseModel):
    requirement_understanding: str = ""
    executive_summary: str = ""
    technical_summary: str = ""
    decision_highlights: list[str] = Field(default_factory=list)
    impact_narrative: str = ""
    risk_narrative: str = ""
    implementation_suggestion: str = ""


class ModuleAnalysisResult(BaseModel):
    path: str = ""
    symbols: list[str] = Field(default_factory=list)
    relevance: str = "low"
    relevance_reason: str = ""
    suggested_changes: str = ""


class CodeAnalysisResult(BaseModel):
    modules: list[ModuleAnalysisResult] = Field(default_factory=list)
    overall_assessment: dict = Field(default_factory=dict)
    confidence: float = 0.0
