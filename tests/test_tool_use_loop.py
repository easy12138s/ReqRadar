import pytest
from unittest.mock import AsyncMock, MagicMock

from reqradar.agent.tool_use_loop import run_tool_use_loop
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
async def test_loop_returns_structured_output_immediately():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(return_value={"content": '{"summary": "test result"}'})
    llm.complete_structured = AsyncMock(return_value={"summary": "test result"})

    registry = ToolRegistry()
    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="You are a test assistant",
        user_prompt="Analyze this",
        tools=[],
        tool_registry=registry,
        output_schema={"name": "test_output", "parameters": {"type": "object"}},
    )
    assert result == {"summary": "test result"}


@pytest.mark.asyncio
async def test_loop_calls_tool_then_returns():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(
        side_effect=[
            {
                "tool_calls": [
                    {"id": "tc1", "name": "echo", "arguments": '{"text": "hello"}'}
                ],
                "assistant_message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "echo",
                                "arguments": '{"text": "hello"}',
                            },
                        }
                    ],
                },
            },
            {"content": '{"result": "done with echo: hello"}'},
        ]
    )

    registry = ToolRegistry()
    registry.register(EchoTool())
    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="test",
        user_prompt="test",
        tools=["echo"],
        tool_registry=registry,
        output_schema={"name": "test", "parameters": {"type": "object"}},
        max_rounds=5,
    )
    assert "done" in result.get("result", "")


@pytest.mark.asyncio
async def test_loop_dedup_same_tool_call():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(
        side_effect=[
            {
                "tool_calls": [
                    {"id": "tc1", "name": "echo", "arguments": '{"text": "same"}'},
                    {"id": "tc2", "name": "echo", "arguments": '{"text": "same"}'},
                ],
                "assistant_message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "echo",
                                "arguments": '{"text": "same"}',
                            },
                        },
                        {
                            "id": "tc2",
                            "type": "function",
                            "function": {
                                "name": "echo",
                                "arguments": '{"text": "same"}',
                            },
                        },
                    ],
                },
            },
            {"content": '{"result": "ok"}'},
        ]
    )

    registry = ToolRegistry()
    registry.register(EchoTool())
    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="test",
        user_prompt="test",
        tools=["echo"],
        tool_registry=registry,
        output_schema={"name": "test", "parameters": {"type": "object"}},
        max_rounds=5,
    )
    assert result.get("result") == "ok"


@pytest.mark.asyncio
async def test_loop_fallback_when_no_tool_use_support():
    llm = AsyncMock()
    llm.complete_with_tools = AsyncMock(return_value=None)
    llm.complete_structured = AsyncMock(return_value={"summary": "fallback"})

    result = await run_tool_use_loop(
        llm_client=llm,
        system_prompt="test",
        user_prompt="test",
        tools=[],
        tool_registry=ToolRegistry(),
        output_schema={"name": "test", "parameters": {"type": "object"}},
    )
    assert result == {"summary": "fallback"}
