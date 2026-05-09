"""共享 ReAct 分析执行逻辑 - CLI 和 Web 共用"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reqradar.web.websocket import ConnectionManager

from reqradar.agent.analysis_agent import AgentState, AnalysisAgent
from reqradar.agent.llm_utils import (
    _call_llm_structured,
    _complete_with_tools,
    _parse_json_response,
)
from reqradar.agent.prompts.analysis_phase import (
    build_dynamic_system_prompt,
    build_step_user_prompt,
    build_termination_prompt,
)
from reqradar.agent.prompts.report_phase import build_report_generation_prompt
from reqradar.agent.schemas import STEP_OUTPUT_SCHEMA
from reqradar.agent.tool_call_tracker import ToolCallTracker
from reqradar.agent.tools import ToolRegistry

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

_RESULT_TRUNCATE_LENGTH = 4000


def _truncate_result(text: str, max_len: int = _RESULT_TRUNCATE_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...(截断)"


def _build_messages_chain(
    system_prompt: str,
    user_prompt: str,
    history: list[dict],
    max_history_messages: int = 6,
) -> list[dict]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if history:
        recent = history[-max_history_messages:]
        messages = messages[:1] + recent + messages[1:]
    return messages


def update_agent_from_step_result(agent: AnalysisAgent, step_data: dict) -> None:
    for dim, new_status in step_data.get("dimension_status", {}).items():
        if new_status == "sufficient":
            agent.dimension_tracker.mark_sufficient(dim)

    for finding in step_data.get("key_findings", []):
        agent.record_evidence(
            type="analysis",
            source=f"step:{agent.step_count}",
            content=finding.get("finding", ""),
            confidence=finding.get("confidence", "medium"),
            dimensions=[finding.get("dimension", "")],
        )

    agent._pending_actions = step_data.get("next_actions", [])
    agent._llm_declared_terminal = step_data.get("final_step", False)


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
        "decision_summary": {
            "summary": "",
            "decisions": [],
            "open_questions": [],
            "follow_ups": [],
        },
        "evidence_items": [
            {
                "kind": ev.type,
                "source": ev.source,
                "summary": ev.content,
                "confidence": ev.confidence,
            }
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


async def _execute_tool_calls(
    tool_calls: list[dict],
    tool_registry: ToolRegistry,
    tracker: ToolCallTracker,
    ws_manager=None,
    task_id: int | None = None,
) -> list[dict]:
    tool_results = []
    for tc in tool_calls:
        tc_name = tc.get("name", "")
        tc_id = tc.get("id", "")
        tc_args_str = tc.get("arguments", "{}")

        try:
            tc_args = json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
        except json.JSONDecodeError:
            tc_args = {}

        if ws_manager and task_id:
            await ws_manager.broadcast(
                task_id,
                {
                    "type": "agent_action",
                    "task_id": task_id,
                    "message": f"调用工具: {tc_name}",
                    "tool": tc_name,
                    "args": tc_args,
                },
            )

        if tc_name not in tool_registry._tools:
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": f"Error: Unknown tool '{tc_name}'",
                }
            )
            continue

        if tracker.is_duplicate(tc_name, tc_args):
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": "(此调用已去重，跳过重复请求)",
                }
            )
            continue

        tracker.track_call(tc_name, tc_args)

        try:
            result = await tool_registry.execute_with_permissions(tc_name, **tc_args)
            result_text = result.data if result.success else f"Error: {result.error}"
        except Exception as e:
            result_text = f"Error executing {tc_name}: {e}"

        result_text = _truncate_result(result_text)
        tool_results.append(
            {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result_text,
            }
        )

        logger.info(
            "Tool #%d: %s(%s) -> %d chars",
            tracker.call_count,
            tc_name,
            json.dumps(tc_args, ensure_ascii=False)[:60],
            len(result_text),
        )

    return tool_results


async def run_react_analysis(
    agent: AnalysisAgent,
    llm_client,
    tool_registry: ToolRegistry,
    config=None,
    section_descriptions=None,
    project_memory=None,
    requirement_text: str | None = None,
    ws_manager: "ConnectionManager | None" = None,  # type: ignore[name-defined]
    task_id: int | None = None,
) -> dict:
    if requirement_text:
        agent.requirement_text = requirement_text

    tool_schemas = tool_registry.get_schemas(tool_registry.list_names())
    tracker = ToolCallTracker()
    conversation_history: list[dict] = []

    agent.state = AgentState.ANALYZING

    while True:
        agent.step_count += 1

        if ws_manager and task_id:
            await ws_manager.broadcast(
                task_id,
                {
                    "type": "dimension_progress",
                    "task_id": task_id,
                    "step": agent.step_count,
                    "dimensions": agent.dimension_tracker.status_summary(),
                },
            )

        ds = agent.dimension_tracker.status_summary()
        system_prompt = build_dynamic_system_prompt(
            dimension_status=ds,
            project_memory=agent.project_memory_text,
            user_memory=agent.user_memory_text,
            historical_context=agent.historical_context,
            template_sections=section_descriptions,
            pending_actions=agent._pending_actions,
        )

        user_prompt = build_step_user_prompt(
            requirement_text=agent.requirement_text,
            step_count=agent.step_count,
            max_steps=agent.max_steps,
            weak_dimensions=agent.get_weak_dimensions_text(),
            evidence_count=len(agent.evidence_collector.evidences),
            depth=agent.depth,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if conversation_history:
            recent = conversation_history[-6:]
            messages = messages[:1] + recent + messages[1:]

        if not tool_schemas:
            result = await _call_llm_structured(llm_client, messages, STEP_OUTPUT_SCHEMA)
            if result:
                update_agent_from_step_result(agent, result)
            if agent.should_terminate():
                break
            await asyncio.sleep(0)
            continue

        supported = await llm_client.supports_tool_calling()
        if not supported:
            result = await _call_llm_structured(llm_client, messages, STEP_OUTPUT_SCHEMA)
            if result:
                update_agent_from_step_result(agent, result)
            if agent.should_terminate():
                break
            await asyncio.sleep(0)
            continue

        response = await _complete_with_tools(llm_client, messages, tool_schemas)

        if response is None:
            agent._consecutive_failures += 1
            if agent.should_terminate():
                break
            await asyncio.sleep(0)
            continue

        agent._consecutive_failures = 0

        if response.get("tool_calls"):
            assistant_msg = response.get("assistant_message", {})
            if assistant_msg:
                conversation_history.append(assistant_msg)

            tool_results = await _execute_tool_calls(
                response["tool_calls"], tool_registry, tracker, ws_manager, task_id
            )
            conversation_history.extend(tool_results)
            await asyncio.sleep(0)
            continue

        if response.get("content"):
            try:
                parsed = _parse_json_response(response["content"])
                update_agent_from_step_result(agent, parsed)

                if len(parsed.get("key_findings", [])) == 0:
                    agent._consecutive_empty_steps += 1
                else:
                    agent._consecutive_empty_steps = 0
            except (json.JSONDecodeError, ValueError):
                agent._consecutive_empty_steps += 1
                conversation_history.append(
                    {
                        "role": "assistant",
                        "content": response["content"],
                    }
                )

        if agent.should_terminate():
            break

        await asyncio.sleep(0)

    agent.state = AgentState.GENERATING

    ds = agent.dimension_tracker.status_summary()
    final_system_prompt = build_dynamic_system_prompt(
        dimension_status=ds,
        project_memory=agent.project_memory_text,
        user_memory=agent.user_memory_text,
        historical_context=agent.historical_context,
        template_sections=section_descriptions,
    )
    report_data = await generate_report(
        agent, llm_client, final_system_prompt, section_descriptions
    )
    agent.final_report_data = report_data

    enable_memory_evolution = (
        config and hasattr(config, "memory_evolution") and config.memory_evolution.enabled
    )
    if enable_memory_evolution and project_memory is not None:
        try:
            from reqradar.agent.memory_evolution import evolve_memory_after_analysis

            await evolve_memory_after_analysis(agent, project_memory, llm_client)
        except Exception as e:
            logger.warning("Memory evolution failed: %s", e)

    agent.state = AgentState.COMPLETED
    return report_data
