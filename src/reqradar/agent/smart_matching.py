"""Agent 层 - 智能模块匹配（Phase 4）"""

import json
import logging

from reqradar.agent.schemas import (
    ANALYZE_MODULE_RELEVANCE_SCHEMA,
    GENERATE_BATCH_MODULE_SUMMARIES_SCHEMA,
    QUERY_MODULES_SCHEMA,
)
from reqradar.agent.prompts import (
    ANALYZE_MODULE_RELEVANCE_PROMPT,
    GENERATE_BATCH_MODULE_SUMMARIES_PROMPT,
    QUERY_MODULES_PROMPT,
)
from reqradar.agent.llm_utils import _call_llm_structured
from reqradar.core.context import RequirementUnderstanding
from reqradar.core.exceptions import LLMException

logger = logging.getLogger("reqradar.agent")


def _get_module_from_memory(memory_data: dict, module_name: str) -> dict | None:
    """从记忆中获取指定模块信息

    Args:
        memory_data: 项目记忆数据
        module_name: 模块名称（支持模糊匹配）

    Returns:
        模块字典的副本，或 None
    """
    for module in memory_data.get("modules", []):
        if module.get("name") == module_name or module_name.lower() in module.get("name", "").lower():
            return module.copy()
    return None


async def _query_relevant_modules_from_memory(
    understanding: RequirementUnderstanding,
    memory_data: dict | None,
    llm_client,
) -> list[dict]:
    """从记忆中查询相关模块

    Args:
        understanding: 需求理解
        memory_data: 项目记忆数据
        llm_client: LLM 客户端

    Returns:
        相关模块列表，每个模块包含 query_reason
    """
    if not memory_data or not memory_data.get("modules"):
        logger.info("No memory data or modules available for query")
        return []

    modules_overview = "\n".join(
        f"- {m.get('name', 'unknown')}: {m.get('responsibility', '')}"
        for m in memory_data.get("modules", [])[:20]
    )

    profile = memory_data.get("project_profile", {})
    project_profile = json.dumps(
        {
            "description": profile.get("description", ""),
            "architecture_style": profile.get("architecture_style", ""),
            "tech_stack": profile.get("tech_stack", {}),
        },
        ensure_ascii=False,
        indent=2,
    )

    terms_str = ", ".join(t.term for t in understanding.terms[:5]) if understanding.terms else ""

    messages = [
        {
            "role": "user",
            "content": QUERY_MODULES_PROMPT.format(
                project_profile=project_profile,
                modules_overview=modules_overview,
                summary=understanding.summary,
                terms=terms_str,
            ),
        },
    ]

    try:
        result = await _call_llm_structured(
            llm_client, messages, QUERY_MODULES_SCHEMA, max_tokens=1024
        )

        queries = result.get("queries", [])
        modules_with_reason = []

        for q in queries:
            module_name = q.get("module_name", "")
            query_reason = q.get("query_reason", "")

            module_info = _get_module_from_memory(memory_data, module_name)
            if module_info:
                module_info["query_reason"] = query_reason
                modules_with_reason.append(module_info)

        logger.info("Queried %d relevant modules from memory", len(modules_with_reason))
        return modules_with_reason

    except (LLMException, json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to query modules from memory: %s", e)
        return []


async def _analyze_module_relevance(
    understanding: RequirementUnderstanding,
    candidate_modules: list[dict],
    llm_client,
) -> list[dict]:
    """分析模块与需求的关联程度

    Args:
        understanding: 需求理解
        candidate_modules: 候选模块列表
        llm_client: LLM 客户端

    Returns:
        分析后的模块列表，包含 path, symbols, relevance, relevance_reason, suggested_changes
    """
    if not candidate_modules:
        logger.info("No candidate modules to analyze")
        return []

    modules_detail = []
    for m in candidate_modules[:10]:
        detail = {
            "name": m.get("name", ""),
            "responsibility": m.get("responsibility", ""),
            "key_classes": m.get("key_classes", []),
            "code_summary": m.get("code_summary", ""),
            "query_reason": m.get("query_reason", ""),
        }
        modules_detail.append(detail)

    modules_detail_str = json.dumps(modules_detail, ensure_ascii=False, indent=2)

    terms_str = ", ".join(t.term for t in understanding.terms[:5]) if understanding.terms else ""

    messages = [
        {
            "role": "user",
            "content": ANALYZE_MODULE_RELEVANCE_PROMPT.format(
                requirement_text=understanding.raw_text[:1000] if understanding.raw_text else "",
                summary=understanding.summary,
                terms=terms_str,
                modules_detail=modules_detail_str,
            ),
        },
    ]

    try:
        result = await _call_llm_structured(
            llm_client, messages, ANALYZE_MODULE_RELEVANCE_SCHEMA, max_tokens=2048
        )

        analyzed_modules = []
        for m in result.get("modules", []):
            analyzed = {
                "path": m.get("path", ""),
                "symbols": m.get("symbols", []),
                "relevance": m.get("relevance", "low"),
                "relevance_reason": m.get("relevance_reason", ""),
                "suggested_changes": m.get("suggested_changes", ""),
            }
            analyzed_modules.append(analyzed)

        logger.info("Analyzed %d modules for relevance", len(analyzed_modules))
        return analyzed_modules

    except (LLMException, json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to analyze module relevance: %s", e)
        return []


async def _smart_module_matching(
    understanding: RequirementUnderstanding,
    memory_data: dict | None,
    code_graph,
    llm_client,
) -> list[dict]:
    """智能模块匹配：LLM 主动查询 + 深度分析

    Args:
        understanding: 需求理解
        memory_data: 项目记忆数据
        code_graph: 代码图（暂不使用，保留接口）
        llm_client: LLM 客户端

    Returns:
        匹配的模块列表，包含详细信息
    """
    relevant_modules = await _query_relevant_modules_from_memory(
        understanding, memory_data, llm_client
    )

    if not relevant_modules:
        logger.info("No relevant modules found from memory")
        return []

    analyzed_modules = await _analyze_module_relevance(
        understanding, relevant_modules, llm_client
    )

    return analyzed_modules
