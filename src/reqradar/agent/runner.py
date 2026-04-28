"""共享 ReAct 分析执行逻辑 - CLI 和 Web 共用"""

import asyncio
import logging

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.llm_utils import _call_llm_structured
from reqradar.agent.prompts.analysis_phase import (
    build_analysis_system_prompt,
    build_analysis_user_prompt,
    build_termination_prompt,
)
from reqradar.agent.prompts.report_phase import build_report_generation_prompt
from reqradar.agent.schemas import ANALYZE_SCHEMA
from reqradar.agent.tools import ToolRegistry
from reqradar.agent.tool_use_loop import run_tool_use_loop

logger = logging.getLogger("reqradar.agent.runner")

REPORT_DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "requirement_title": {"type": "string"},
        "requirement_understanding": {"type": "string"},
        "executive_summary": {"type": "string"},
        "technical_summary": {"type": "string"},
        "impact_narrative": {"type": "string"},
        "risk_narrative": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["critical", "high", "medium", "low", "unknown"]},
        "decision_highlights": {"type": "array", "items": {"type": "string"}},
        "impact_domains": {"type": "array"},
        "impact_modules": {"type": "array"},
        "change_assessment": {"type": "array"},
        "risks": {"type": "array"},
        "decision_summary": {"type": "object"},
        "evidence_items": {"type": "array"},
        "verification_points": {"type": "array", "items": {"type": "string"}},
        "implementation_suggestion": {"type": "string"},
        "priority": {"type": "string"},
        "priority_reason": {"type": "string"},
        "terms": {"type": "array"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "structured_constraints": {"type": "array"},
        "contributors": {"type": "array"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["requirement_title", "risk_level"],
}


def update_agent_from_tool_result(agent: AnalysisAgent, data: dict) -> None:
    if data.get("terms"):
        for t in data.get("terms", []):
            if isinstance(t, dict) and t.get("term"):
                agent.record_evidence(
                    type="term",
                    source=f"llm_extract:{t['term']}",
                    content=f"{t['term']}: {t.get('definition', '')}",
                    confidence="medium",
                    dimensions=["understanding"],
                )

    if data.get("impact_modules"):
        for m in data.get("impact_modules", []):
            if isinstance(m, dict):
                agent.record_evidence(
                    type="code",
                    source=m.get("path", "unknown"),
                    content=m.get("relevance_reason", "Unknown relevance"),
                    confidence=m.get("relevance", "low"),
                    dimensions=["impact", "change"],
                )
                agent.dimension_tracker.mark_in_progress("impact")

    if data.get("risks"):
        for r in data.get("risks", []):
            if isinstance(r, dict):
                confidence_map = {"high": "high", "medium": "medium", "low": "low"}
                agent.record_evidence(
                    type="history",
                    source=f"risk:{r.get('description', '')[:50]}",
                    content=r.get("description", ""),
                    confidence=confidence_map.get(r.get("severity", ""), "medium"),
                    dimensions=["risk"],
                )
                agent.dimension_tracker.mark_in_progress("risk")


async def generate_report(
    agent: AnalysisAgent,
    llm_client,
    system_prompt: str,
    section_descriptions=None,
) -> dict:
    termination_prompt = build_termination_prompt()
    evidence_text = agent.evidence_collector.get_all_evidence_text()

    report_prompt = build_report_generation_prompt(
        requirement_text=agent.requirement_text,
        evidence_text=evidence_text,
        dimension_status=agent.dimension_tracker.status_summary(),
        template_sections=section_descriptions,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": report_prompt},
        {"role": "assistant", "content": termination_prompt},
    ]

    try:
        result = await _call_llm_structured(llm_client, messages, REPORT_DATA_SCHEMA)
        if result:
            result.setdefault("requirement_title", agent.requirement_text[:100])
            result.setdefault("warnings", [])
            return result
    except Exception as e:
        logger.warning("Report generation failed, using fallback: %s", e)

    return build_fallback_report_data(agent)


def build_fallback_report_data(agent: AnalysisAgent) -> dict:
    return {
        "requirement_title": agent.requirement_text[:100],
        "requirement_understanding": f"需求理解: {agent.requirement_text[:200]}",
        "executive_summary": "分析完成，但有部分信息不完整。",
        "technical_summary": "",
        "impact_narrative": "",
        "risk_narrative": "",
        "risk_level": "unknown",
        "decision_highlights": [],
        "impact_domains": [],
        "impact_modules": [],
        "change_assessment": [],
        "risks": [],
        "decision_summary": {"summary": "", "decisions": [], "open_questions": [], "follow_ups": []},
        "evidence_items": [
            {"kind": ev.type, "source": ev.source, "summary": ev.content, "confidence": ev.confidence}
            for ev in agent.evidence_collector.evidences
        ],
        "verification_points": [],
        "implementation_suggestion": "",
        "priority": "medium",
        "priority_reason": "",
        "terms": [],
        "keywords": [],
        "constraints": [],
        "structured_constraints": [],
        "contributors": [],
        "warnings": ["Agent analysis completed with partial data due to insufficient evidence."],
    }


def build_report_data_from_agent(agent: AnalysisAgent, llm_result: dict) -> dict:
    report_data = llm_result.copy() if llm_result else {}
    report_data.setdefault("requirement_title", agent.requirement_text[:100])
    report_data.setdefault("risk_level", "unknown")
    report_data.setdefault("warnings", [])
    evidence_items = [
        {"kind": ev.type, "source": ev.source, "summary": ev.content, "confidence": ev.confidence}
        for ev in agent.evidence_collector.evidences
    ]
    report_data.setdefault("evidence_items", evidence_items)
    return report_data


async def run_react_analysis(
    agent: AnalysisAgent,
    llm_client,
    tool_registry: ToolRegistry,
    config=None,
    section_descriptions=None,
) -> dict:
    system_prompt = build_analysis_system_prompt(
        project_memory=agent.project_memory_text,
        user_memory=agent.user_memory_text,
        historical_context=agent.historical_context,
        dimension_status=agent.dimension_tracker.status_summary(),
        template_sections=section_descriptions,
    )

    tool_names = tool_registry.list_names()

    max_total_tokens = 8000
    if config and hasattr(config, "analysis") and hasattr(config.analysis, "tool_use_max_tokens"):
        max_total_tokens = config.analysis.tool_use_max_tokens

    while not agent.should_terminate():
        user_prompt = build_analysis_user_prompt(
            requirement_text=agent.requirement_text,
            agent_context=agent.get_context_text() + "\n\n" + agent.get_weak_dimensions_text(),
        )

        tool_result_data = await run_tool_use_loop(
            llm_client,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tools=tool_names,
            tool_registry=tool_registry,
            output_schema=ANALYZE_SCHEMA,
            max_rounds=5,
            max_total_tokens=max_total_tokens,
        )

        if tool_result_data:
            update_agent_from_tool_result(agent, tool_result_data)

        agent.step_count += 1
        await asyncio.sleep(0)

    agent.state = AgentState.GENERATING
    report_data = await generate_report(agent, llm_client, system_prompt, section_descriptions)
    agent.final_report_data = report_data
    agent.state = AgentState.COMPLETED

    return report_data
