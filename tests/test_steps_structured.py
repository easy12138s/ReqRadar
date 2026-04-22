"""测试结构化输出与 analyze 结果映射逻辑"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from reqradar.agent.schemas import ANALYZE_SCHEMA, EXTRACT_SCHEMA, GENERATE_SCHEMA
from reqradar.agent.llm_utils import _call_llm_structured, _parse_json_response
from reqradar.agent.prompts import ANALYZE_PROMPT, GENERATE_PROMPT
from reqradar.agent.steps import _populate_analysis_from_result, step_analyze, step_generate
from reqradar.core.context import AnalysisContext, DeepAnalysis, RequirementUnderstanding


class TestCallLlmStructured:
    @pytest.mark.asyncio
    async def test_function_calling_succeeds(self):
        llm = AsyncMock()
        llm.complete_structured = AsyncMock(
            return_value={"summary": "test", "keywords": ["a", "b"]}
        )

        result = await _call_llm_structured(
            llm,
            messages=[{"role": "user", "content": "test"}],
            schema=EXTRACT_SCHEMA,
        )

        assert result["summary"] == "test"
        assert result["keywords"] == ["a", "b"]
        llm.complete_structured.assert_called_once()
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_text_parsing(self):
        llm = AsyncMock()
        llm.complete_structured = AsyncMock(return_value=None)
        llm.complete = AsyncMock(return_value='{"summary": "fallback", "keywords": ["x"]}')

        result = await _call_llm_structured(
            llm,
            messages=[{"role": "user", "content": "test"}],
            schema=EXTRACT_SCHEMA,
        )

        assert result["summary"] == "fallback"
        llm.complete_structured.assert_called_once()
        llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_with_markdown_code_block(self):
        llm = AsyncMock()
        llm.complete_structured = AsyncMock(return_value=None)
        llm.complete = AsyncMock(
            return_value='```json\n{"summary": "in block", "keywords": []}\n```'
        )

        result = await _call_llm_structured(
            llm,
            messages=[{"role": "user", "content": "test"}],
            schema=EXTRACT_SCHEMA,
        )

        assert result["summary"] == "in block"


class TestParseJsonResponse:
    def test_plain_json_object(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        result = _parse_json_response('Here is the result: {"key": "value"} End.')
        assert result == {"key": "value"}

    def test_json_array_of_strings(self):
        result = _parse_json_response('["alpha", "beta", "gamma"]')
        assert len(result) == 3
        assert result[0] == "alpha"

    def test_json_object_in_surrounding_text(self):
        result = _parse_json_response('Results:\n[{"id": "1"}]\nDone.')
        assert result == {"id": "1"}

    def test_markdown_code_block(self):
        result = _parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_markdown_code_block_array(self):
        result = _parse_json_response('```\n[{"id": "1"}]\n```')
        assert len(result) == 1

    def test_plain_string_array(self):
        data = '["alpha", "beta", "gamma"]'
        result = _parse_json_response(data)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_json_with_think_tags_and_text(self):
        data = '<think>reasoning here</think>\nHere is the answer:\n{"key": "value"}\nDone.'
        result = _parse_json_response(data)
        assert result == {"key": "value"}

    def test_json_code_block_with_surrounding_text(self):
        data = 'some intro\n```json\n{"summary": "ok", "keywords": []}\n```\ntrailing note'
        result = _parse_json_response(data)
        assert result == {"summary": "ok", "keywords": []}


class TestAnalyzeStructuredOutputs:
    def test_analyze_schema_supports_decision_grade_fields(self):
        properties = ANALYZE_SCHEMA["parameters"]["properties"]

        assert "decision_summary" in properties
        assert "evidence_items" in properties
        assert "impact_domains" in properties

    def test_analyze_prompt_mentions_inferred_domains_and_evidence(self):
        assert "decision_summary" in ANALYZE_PROMPT
        assert "evidence_items" in ANALYZE_PROMPT
        assert "impact_domains" in ANALYZE_PROMPT
        assert "未找到直接代码匹配" in ANALYZE_PROMPT

    def test_populate_analysis_maps_decision_grade_fields(self):
        analysis = DeepAnalysis()

        result = {
            "risk_level": "high",
            "decision_summary": {
                "summary": "Need staged rollout before merge.",
                "decisions": [
                    {
                        "topic": "release strategy",
                        "decision": "use feature flag",
                        "rationale": "limits blast radius",
                        "implications": ["flag wiring", "ops validation"],
                    }
                ],
                "open_questions": ["Need fallback owner?"],
                "follow_ups": ["Confirm rollout checklist"],
            },
            "evidence_items": [
                {
                    "kind": "code_match",
                    "source": "src/service.py:12",
                    "summary": "Existing request validation path.",
                    "confidence": "high",
                }
            ],
            "impact_domains": [
                {"domain": "api", "confidence": "high", "basis": "matched router"},
                {
                    "domain": "operations",
                    "confidence": "medium",
                    "basis": "inferred from deployment dependency",
                    "inferred": True,
                },
            ],
            "verification_points": ["Check rollout config"],
        }

        _populate_analysis_from_result(analysis, result)

        assert analysis.decision_summary.summary == "Need staged rollout before merge."
        assert analysis.decision_summary.decisions[0].topic == "release strategy"
        assert analysis.decision_summary.decisions[0].implications == [
            "flag wiring",
            "ops validation",
        ]
        assert analysis.decision_summary.open_questions == ["Need fallback owner?"]
        assert analysis.evidence_items[0].kind == "code_match"
        assert analysis.evidence_items[0].source == "src/service.py:12"
        assert analysis.evidence_items[0].summary == "Existing request validation path."
        assert analysis.evidence_items[0].confidence == "high"
        assert analysis.impact_domains[0].domain == "api"
        assert analysis.impact_domains[0].inferred is False
        assert analysis.impact_domains[1].domain == "operations"
        assert analysis.impact_domains[1].basis == "inferred from deployment dependency"
        assert analysis.impact_domains[1].inferred is True

    def test_populate_analysis_normalizes_scalar_list_like_fields(self):
        analysis = DeepAnalysis()

        result = {
            "risk_level": "medium",
            "decision_summary": {
                "summary": "Proceed after review.",
                "decisions": "not-a-list",
                "open_questions": "single open question",
                "follow_ups": "single follow-up",
            },
            "verification_points": "check migration",
            "implementation_hints": {
                "approach": "incremental",
                "effort_estimate": "small",
                "dependencies": "feature flag service",
            },
        }

        _populate_analysis_from_result(analysis, result)

        assert analysis.decision_summary.decisions == []
        assert analysis.decision_summary.open_questions == ["single open question"]
        assert analysis.decision_summary.follow_ups == ["single follow-up"]
        assert analysis.verification_points == ["check migration"]
        assert analysis.implementation_hints.dependencies == ["feature flag service"]

    @pytest.mark.asyncio
    async def test_step_analyze_preserves_inferred_impact_domains_without_code_matches(self):
        context = AnalysisContext(
            requirement_path=Path("dummy.md"),
            requirement_text="Need safer rollout controls.",
            understanding=RequirementUnderstanding(
                summary="Need safer rollout controls.",
                keywords=["rollout", "feature flag"],
            ),
            memory_data={
                "project_profile": {"description": "CLI service"},
            },
        )

        llm_client = AsyncMock()
        llm_client.complete_structured = AsyncMock(
            return_value={
                "risk_level": "medium",
                "decision_summary": {
                    "summary": "Likely cross-cutting operational change.",
                    "decisions": [],
                    "open_questions": [],
                    "follow_ups": [],
                },
                "evidence_items": [
                    {
                        "kind": "inference",
                        "source": "project context",
                        "summary": "No direct symbol match; inferred from release process language.",
                        "confidence": "medium",
                    }
                ],
                "impact_domains": [
                    {
                        "domain": "operations",
                        "confidence": "medium",
                        "basis": "No direct code match; inferred from requirement wording",
                        "inferred": True,
                    }
                ],
            }
        )

        class EmptyCodeGraph:
            def find_symbols(self, keywords):
                return []

        analysis = await step_analyze(
            context,
            code_graph=EmptyCodeGraph(),
            git_analyzer=None,
            llm_client=llm_client,
            tool_registry=None,
            analysis_config=None,
        )

        assert analysis.risk_level == "medium"
        assert analysis.impact_modules == []
        assert analysis.decision_summary.summary == "Likely cross-cutting operational change."
        assert analysis.evidence_items[0].kind == "inference"
        assert analysis.impact_domains[0].domain == "operations"
        assert analysis.impact_domains[0].basis == "No direct code match; inferred from requirement wording"
        assert analysis.impact_domains[0].inferred is True

    @pytest.mark.asyncio
    async def test_step_analyze_updates_context_for_content_confidence(self):
        context = AnalysisContext(
            requirement_path=Path("dummy.md"),
            requirement_text="Need safer rollout controls.",
            understanding=RequirementUnderstanding(
                summary="Need safer rollout controls.",
                keywords=["rollout"],
            ),
            memory_data={"project_profile": {"description": "CLI service"}},
        )

        llm_client = AsyncMock()
        llm_client.complete_structured = AsyncMock(
            return_value={
                "risk_level": "medium",
                "decision_summary": {
                    "summary": "Ship behind a feature flag.",
                    "decisions": [
                        {
                            "topic": "rollout",
                            "decision": "feature flag",
                            "rationale": "reduces blast radius",
                            "implications": [],
                        }
                    ],
                    "open_questions": [],
                    "follow_ups": [],
                },
            }
        )

        analysis = await step_analyze(
            context,
            code_graph=None,
            git_analyzer=None,
            llm_client=llm_client,
            tool_registry=None,
            analysis_config=None,
        )

        context.deep_analysis = analysis

        assert context.content_confidence == "high"
        assert context.decision_summary is not None
        assert context.decision_summary.summary == "Ship behind a feature flag."


class TestGenerateStructuredOutputs:
    def test_generate_schema_supports_dual_layer_fields(self):
        properties = GENERATE_SCHEMA["parameters"]["properties"]

        assert "executive_summary" in properties
        assert "technical_summary" in properties
        assert "decision_highlights" in properties

    def test_generate_prompt_mentions_dual_layer_structure(self):
        assert "决策摘要" in GENERATE_PROMPT
        assert "技术支撑" in GENERATE_PROMPT
        assert "不要重新判断风险和范围" in GENERATE_PROMPT

    @pytest.mark.asyncio
    async def test_step_generate_returns_dual_layer_content(self):
        context = AnalysisContext(
            requirement_path=Path("dummy.md"),
            understanding=RequirementUnderstanding(summary="Build safer rollout controls."),
            deep_analysis=DeepAnalysis(
                risk_level="medium",
                impact_narrative="Touches release pipeline and config loading.",
                risk_narrative="Main risk is rollout inconsistency.",
            ),
        )

        llm_client = AsyncMock()
        llm_client.complete_structured = AsyncMock(
            return_value={
                "requirement_understanding": "Need safer progressive rollout controls.",
                "executive_summary": "Recommend phased delivery with feature flags.",
                "technical_summary": "Affects rollout configuration, runtime gating, and observability.",
                "decision_highlights": [
                    "Ship behind feature flag",
                    "Validate rollback path before rollout",
                ],
                "impact_narrative": "Touches release pipeline and config loading.",
                "risk_narrative": "Main risk is rollout inconsistency.",
                "implementation_suggestion": "Implement backend gating first, then add operator-facing visibility.",
            }
        )

        generated = await step_generate(
            context,
            llm_client=llm_client,
            tool_registry=None,
            analysis_config=None,
        )

        assert generated.requirement_understanding == "Need safer progressive rollout controls."
        assert generated.executive_summary == "Recommend phased delivery with feature flags."
        assert generated.technical_summary == "Affects rollout configuration, runtime gating, and observability."
        assert generated.decision_highlights == [
            "Ship behind feature flag",
            "Validate rollback path before rollout",
        ]
