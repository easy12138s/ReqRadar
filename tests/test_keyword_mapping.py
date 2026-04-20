"""测试关键词映射功能"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from reqradar.agent.schemas import KEYWORD_MAPPING_SCHEMA
from reqradar.agent.prompts import KEYWORD_MAPPING_PROMPT
from reqradar.agent.steps import step_map_keywords, _expand_keywords
from reqradar.core.context import AnalysisContext, RequirementUnderstanding, TermDefinition


class TestExpandKeywords:
    def test_basic_expansion(self):
        original = ["双因素认证", "用户登录"]
        mappings = {
            "双因素认证": ["two_factor", "2fa", "mfa", "auth"],
            "用户登录": ["login", "signin", "user_auth"],
        }

        result = _expand_keywords(original, mappings)

        assert "双因素认证" in result
        assert "用户登录" in result
        assert "two_factor" in result
        assert "2fa" in result
        assert "login" in result
        assert len(result) == 9  # 2 original + 7 mapped

    def test_empty_mappings(self):
        original = ["API", "认证"]
        mappings = {}

        result = _expand_keywords(original, mappings)

        # Order may differ due to set conversion, check membership
        assert set(result) == set(original)

    def test_partial_mappings(self):
        original = ["API", "认证", "数据库"]
        mappings = {
            "认证": ["auth", "authentication"],
        }

        result = _expand_keywords(original, mappings)

        assert "API" in result
        assert "认证" in result
        assert "数据库" in result
        assert "auth" in result
        assert "authentication" in result


class TestStepMapKeywords:
    @pytest.mark.asyncio
    async def test_successful_mapping(self):
        understanding = RequirementUnderstanding(
            terms=[
                TermDefinition(term="双因素认证", definition=""),
                TermDefinition(term="用户登录", definition=""),
            ]
        )
        context = AnalysisContext(requirement_path="test.md")
        context.understanding = understanding

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value={
            "mappings": [
                {
                    "business_term": "双因素认证",
                    "code_terms": ["two_factor", "2fa", "mfa"],
                },
                {
                    "business_term": "用户登录",
                    "code_terms": ["login", "signin"],
                },
            ]
        })

        result = await step_map_keywords(context, mock_llm)

        assert "双因素认证" in result
        assert "two_factor" in context.expanded_keywords
        assert "login" in context.expanded_keywords

    @pytest.mark.asyncio
    async def test_using_keywords_when_no_terms(self):
        understanding = RequirementUnderstanding(
            keywords=["API", "认证"]
        )
        context = AnalysisContext(requirement_path="test.md")
        context.understanding = understanding

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value={
            "mappings": [
                {"business_term": "API", "code_terms": ["api", "rest"]},
            ]
        })

        result = await step_map_keywords(context, mock_llm)

        assert "API" in result

    @pytest.mark.asyncio
    async def test_empty_understanding(self):
        context = AnalysisContext(requirement_path="test.md")

        mock_llm = AsyncMock()

        result = await step_map_keywords(context, mock_llm)

        assert result == {}
        assert context.expanded_keywords == []

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        understanding = RequirementUnderstanding(
            terms=[TermDefinition(term="认证", definition="")]
        )
        context = AnalysisContext(requirement_path="test.md")
        context.understanding = understanding

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value=None)
        mock_llm.complete = AsyncMock(return_value="")

        result = await step_map_keywords(context, mock_llm)

        # Should fallback to original terms
        assert "认证" in context.expanded_keywords


class TestKeywordMappingSchema:
    def test_schema_structure(self):
        assert KEYWORD_MAPPING_SCHEMA["name"] == "map_keywords_to_code"
        assert "mappings" in KEYWORD_MAPPING_SCHEMA["parameters"]["properties"]

    def test_required_fields(self):
        required = KEYWORD_MAPPING_SCHEMA["parameters"]["required"]
        assert "mappings" in required


class TestKeywordMappingPrompt:
    def test_prompt_format(self):
        terms = ["双因素认证", "用户登录"]
        formatted = KEYWORD_MAPPING_PROMPT.format(
            terms="\n".join(f"- {t}" for t in terms)
        )

        assert "双因素认证" in formatted
        assert "用户登录" in formatted
        assert "代码层术语" in formatted
