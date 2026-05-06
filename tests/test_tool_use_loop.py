import pytest
from unittest.mock import AsyncMock

from reqradar.agent.analysis_agent import AnalysisAgent
from reqradar.agent.runner import run_react_analysis, update_agent_from_step_result
from reqradar.agent.tools.base import BaseTool, ToolResult
from reqradar.agent.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo back the input"
    parameters_schema = {
        "name": "echo",
        "description": "Echo back the input",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data=f"echo: {kwargs.get('text', '')}")


@pytest.mark.asyncio
async def test_single_call_returns_step_output_immediately():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(
        return_value={
            "content": '{"reasoning": "test", "dimension_status": {"understanding": "sufficient", "impact": "in_progress", "risk": "insufficient", "change": "insufficient", "decision": "insufficient", "evidence": "insufficient", "verification": "insufficient"}, "final_step": true}'
        }
    )
    llm.complete_structured = AsyncMock(
        return_value={
            "reasoning": "test",
            "dimension_status": {},
            "final_step": False,
        }
    )
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test requirement", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    result = await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert isinstance(result, dict)
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_tool_call_then_step_output():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(
        side_effect=[
            {
                "tool_calls": [{"id": "tc1", "name": "echo", "arguments": '{"text": "hello"}'}],
                "assistant_message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {"name": "echo", "arguments": '{"text": "hello"}'},
                        }
                    ],
                },
            },
            {
                "content": '{"reasoning": "got echo", "dimension_status": {}, "final_step": false}',
            },
            {
                "content": '{"reasoning": "done", "dimension_status": {"understanding": "sufficient", "impact": "sufficient", "risk": "sufficient", "change": "sufficient", "decision": "sufficient", "evidence": "sufficient", "verification": "sufficient"}, "final_step": true}',
            },
        ]
    )
    llm.complete_structured = AsyncMock(
        return_value={
            "requirement_title": "test",
            "risk_level": "medium",
        }
    )
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test requirement", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()
    registry.register(EchoTool())

    result = await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert isinstance(result, dict)
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_terminates_on_max_steps():
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "content": f'{{"reasoning": "step {call_count}", "dimension_status": {{}}, "final_step": false}}',
        }

    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(side_effect=side_effect)
    llm.complete_structured = AsyncMock(
        return_value={
            "requirement_title": "test",
            "risk_level": "medium",
        }
    )
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    result = await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert agent.step_count <= agent.max_steps
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_dimension_sufficiency_updated():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")

    step_data = {
        "reasoning": "test",
        "dimension_status": {
            "understanding": "sufficient",
            "impact": "sufficient",
            "risk": "sufficient",
            "change": "sufficient",
            "decision": "sufficient",
            "evidence": "sufficient",
            "verification": "sufficient",
        },
        "key_findings": [
            {"dimension": "impact", "finding": "Found auth module", "confidence": "high"}
        ],
        "final_step": False,
    }
    update_agent_from_step_result(agent, step_data)
    assert agent.dimension_tracker.all_sufficient()
    assert len(agent.evidence_collector.evidences) == 1


@pytest.mark.asyncio
async def test_no_tools_falls_back_to_structured():
    llm = AsyncMock()
    llm.complete_structured = AsyncMock(
        return_value={
            "reasoning": "no tools",
            "dimension_status": {},
            "final_step": False,
        }
    )
    llm.supports_tool_calling = AsyncMock(return_value=False)

    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert agent.state.value == "completed"


@pytest.mark.asyncio
async def test_consecutive_failures_terminate():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(return_value=None)
    llm.complete_structured = AsyncMock(
        return_value={
            "requirement_title": "test",
            "risk_level": "medium",
        }
    )
    llm.supports_tool_calling = AsyncMock(return_value=True)

    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    registry = ToolRegistry()

    await run_react_analysis(
        agent=agent,
        llm_client=llm,
        tool_registry=registry,
    )
    assert agent.state.value == "completed"
    assert agent._consecutive_failures >= 3 or agent.step_count >= agent.max_steps
