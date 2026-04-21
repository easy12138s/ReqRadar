import pytest

from reqradar.agent.tools.base import BaseTool, ToolResult


def test_tool_result_success():
    result = ToolResult(success=True, data="hello")
    assert result.success is True
    assert result.data == "hello"
    assert result.error == ""
    assert result.truncated is False


def test_tool_result_failure():
    result = ToolResult(success=False, data="", error="file not found")
    assert result.success is False
    assert result.error == "file not found"


def test_base_tool_is_abstract():
    with pytest.raises(TypeError):
        BaseTool()


def test_concrete_subclass_returns_tool_result():
    class EchoTool(BaseTool):
        name = "echo"
        description = "Echo back input"
        parameters_schema = {"name": "echo", "parameters": {"type": "object"}}

        async def execute(self, **kwargs):
            return ToolResult(success=True, data=kwargs.get("text", ""))

    tool = EchoTool()
    assert tool.name == "echo"
    assert tool.parameters_schema is not None


def test_parameters_schema_not_shared_between_subclasses():
    class ToolA(BaseTool):
        name = "a"
        parameters_schema = {"name": "a"}

        async def execute(self, **kwargs):
            return ToolResult(success=True, data="")

    class ToolB(BaseTool):
        name = "b"
        parameters_schema = {"name": "b"}

        async def execute(self, **kwargs):
            return ToolResult(success=True, data="")

    assert ToolA.parameters_schema is not ToolB.parameters_schema
