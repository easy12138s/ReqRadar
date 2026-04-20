"""测试智能模块匹配功能"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from reqradar.agent.smart_matching import (
    _get_module_from_memory,
    _query_relevant_modules_from_memory,
    _analyze_module_relevance,
    _smart_module_matching,
)
from reqradar.core.context import RequirementUnderstanding, TermDefinition


class TestGetModuleFromMemory:
    def test_exact_match(self):
        memory_data = {
            "modules": [
                {"name": "auth", "responsibility": "认证模块"},
                {"name": "user", "responsibility": "用户管理"},
            ]
        }

        result = _get_module_from_memory(memory_data, "auth")
        assert result is not None
        assert result["name"] == "auth"
        assert result["responsibility"] == "认证模块"

    def test_fuzzy_match_lowercase(self):
        memory_data = {
            "modules": [
                {"name": "AuthService", "responsibility": "认证服务"},
            ]
        }

        result = _get_module_from_memory(memory_data, "auth")
        assert result is not None
        assert result["name"] == "AuthService"

    def test_no_match(self):
        memory_data = {
            "modules": [
                {"name": "auth", "responsibility": "认证模块"},
            ]
        }

        result = _get_module_from_memory(memory_data, "payment")
        assert result is None

    def test_empty_memory(self):
        result = _get_module_from_memory({}, "auth")
        assert result is None

    def test_returns_copy(self):
        memory_data = {
            "modules": [
                {"name": "auth", "responsibility": "认证模块", "key_classes": ["AuthService"]},
            ]
        }

        result = _get_module_from_memory(memory_data, "auth")
        result["responsibility"] = "modified"
        
        original = memory_data["modules"][0]
        assert original["responsibility"] == "认证模块"


class TestQueryRelevantModulesFromMemory:
    @pytest.mark.asyncio
    async def test_query_returns_modules(self):
        understanding = RequirementUnderstanding(
            summary="实现用户登录认证功能",
            terms=[TermDefinition(term="登录", definition="用户登录")],
        )

        memory_data = {
            "modules": [
                {"name": "auth", "responsibility": "用户认证模块", "key_classes": ["AuthService"]},
                {"name": "user", "responsibility": "用户管理", "key_classes": ["UserModel"]},
            ],
            "project_profile": {
                "description": "测试项目",
                "architecture_style": "分层架构",
                "tech_stack": {"languages": ["Python"]},
            },
        }

        llm = AsyncMock()
        llm.complete_structured = AsyncMock(
            return_value={
                "queries": [
                    {"module_name": "auth", "query_reason": "直接负责认证功能"},
                    {"module_name": "user", "query_reason": "用户数据相关"},
                ],
                "reasoning": "认证需求涉及 auth 和 user 模块",
            }
        )

        result = await _query_relevant_modules_from_memory(
            understanding, memory_data, llm
        )

        assert len(result) == 2
        assert result[0]["name"] == "auth"
        assert "query_reason" in result[0]
        assert result[0]["query_reason"] == "直接负责认证功能"

    @pytest.mark.asyncio
    async def test_query_with_empty_memory(self):
        understanding = RequirementUnderstanding(
            summary="测试需求",
            terms=[],
        )

        llm = AsyncMock()

        result = await _query_relevant_modules_from_memory(
            understanding, None, llm
        )

        assert result == []
        llm.complete_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_fuzzy_match_module_names(self):
        understanding = RequirementUnderstanding(
            summary="实现支付功能",
            terms=[TermDefinition(term="支付", definition="在线支付")],
        )

        memory_data = {
            "modules": [
                {"name": "PaymentService", "responsibility": "支付服务", "key_classes": []},
            ],
            "project_profile": {"description": "测试", "architecture_style": "", "tech_stack": {}},
        }

        llm = AsyncMock()
        llm.complete_structured = AsyncMock(
            return_value={
                "queries": [
                    {"module_name": "payment", "query_reason": "支付相关"},
                ],
                "reasoning": "",
            }
        )

        result = await _query_relevant_modules_from_memory(
            understanding, memory_data, llm
        )

        assert len(result) == 1
        assert result[0]["name"] == "PaymentService"


class TestAnalyzeModuleRelevance:
    @pytest.mark.asyncio
    async def test_analyze_returns_detailed_results(self):
        understanding = RequirementUnderstanding(
            raw_text="实现用户双因素认证",
            summary="添加双因素认证支持",
            terms=[TermDefinition(term="认证", definition="用户认证")],
        )

        candidate_modules = [
            {
                "name": "auth",
                "responsibility": "认证模块",
                "key_classes": ["AuthService", "TokenManager"],
                "code_summary": "处理用户登录和令牌管理",
                "query_reason": "核心认证逻辑",
            },
        ]

        llm = AsyncMock()
        llm.complete_structured = AsyncMock(
            return_value={
                "modules": [
                    {
                        "path": "src/auth",
                        "symbols": ["AuthService", "TokenManager"],
                        "relevance": "high",
                        "relevance_reason": "直接负责认证功能实现",
                        "suggested_changes": "添加双因素验证方法",
                    }
                ],
                "overall_assessment": {
                    "impact_scope": "认证流程",
                    "key_integration_points": ["AuthService.authenticate"],
                },
            }
        )

        result = await _analyze_module_relevance(
            understanding, candidate_modules, llm
        )

        assert len(result) == 1
        assert result[0]["path"] == "src/auth"
        assert result[0]["relevance"] == "high"
        assert "suggested_changes" in result[0]

    @pytest.mark.asyncio
    async def test_analyze_empty_candidates(self):
        understanding = RequirementUnderstanding(summary="测试")

        llm = AsyncMock()

        result = await _analyze_module_relevance(understanding, [], llm)

        assert result == []
        llm.complete_structured.assert_not_called()


class TestSmartModuleMatching:
    @pytest.mark.asyncio
    async def test_smart_matching_integration(self):
        understanding = RequirementUnderstanding(
            raw_text="实现用户登录",
            summary="用户登录认证",
            terms=[TermDefinition(term="登录", definition="用户登录")],
        )

        memory_data = {
            "modules": [
                {"name": "auth", "responsibility": "认证", "key_classes": ["AuthService"]},
            ],
            "project_profile": {"description": "测试", "architecture_style": "", "tech_stack": {}},
        }

        llm = AsyncMock()
        llm.complete_structured = AsyncMock(
            side_effect=[
                {
                    "queries": [
                        {"module_name": "auth", "query_reason": "认证相关"},
                    ],
                    "reasoning": "",
                },
                {
                    "modules": [
                        {
                            "path": "auth",
                            "symbols": ["AuthService"],
                            "relevance": "high",
                            "relevance_reason": "核心认证",
                            "suggested_changes": "添加登录方法",
                        }
                    ],
                },
            ]
        )

        result = await _smart_module_matching(
            understanding, memory_data, None, llm
        )

        assert len(result) == 1
        assert result[0]["relevance"] == "high"

    @pytest.mark.asyncio
    async def test_smart_matching_no_memory(self):
        understanding = RequirementUnderstanding(summary="测试")

        llm = AsyncMock()

        result = await _smart_module_matching(
            understanding, None, None, llm
        )

        assert result == []
