import pytest

from reqradar.agent.tools.base import BaseTool, ToolResult
from reqradar.agent.tools.registry import ToolRegistry


class FakeTool(BaseTool):
    name = "fake_tool"
    description = "A fake tool for testing"
    parameters_schema = {
        "name": "fake_tool",
        "description": "A fake tool for testing",
        "parameters": {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data=f"echo: {kwargs.get('input', '')}")


def test_registry_register_and_get():
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)
    assert registry.get("fake_tool") is tool


def test_registry_get_nonexistent():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_registry_get_schemas():
    registry = ToolRegistry()
    registry.register(FakeTool())
    schemas = registry.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "fake_tool"
    assert schemas[0]["function"]["description"] == "A fake tool for testing"
    assert schemas[0]["function"]["parameters"]["type"] == "object"


def test_registry_get_subset():
    registry = ToolRegistry()
    registry.register(FakeTool())
    schemas = registry.get_schemas(["fake_tool"])
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "fake_tool"
    schemas2 = registry.get_schemas(["nonexistent"])
    assert len(schemas2) == 0


def test_registry_wraps_legacy_schema_to_openai_tool_format():
    registry = ToolRegistry()
    registry.register(FakeTool())

    schema = registry.get_schemas()[0]

    assert schema == {
        "type": "function",
        "function": {
            "name": "fake_tool",
            "description": "A fake tool for testing",
            "parameters": {
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
            },
        },
    }


def test_registry_list_names():
    registry = ToolRegistry()
    registry.register(FakeTool())
    assert registry.list_names() == ["fake_tool"]
