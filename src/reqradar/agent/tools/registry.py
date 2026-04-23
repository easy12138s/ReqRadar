from reqradar.agent.tools.base import BaseTool, ToolResult
from reqradar.agent.tools.security import ToolPermissionChecker, check_tool_permissions


class ToolRegistry:
    def __init__(self, user_permissions: set[str] | None = None):
        self._tools: dict[str, BaseTool] = {}
        self._permission_checker = ToolPermissionChecker(user_permissions)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_schemas(self, names: list[str] | None = None) -> list[dict]:
        if names is None:
            return [t.openai_schema() for t in self._tools.values()]
        return [
            self._tools[n].openai_schema() for n in names if n in self._tools
        ]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    async def execute_with_permissions(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(success=False, data="", error=f"Tool not found: {name}")
        if not check_tool_permissions(tool.required_permissions, self._permission_checker.user_permissions):
            return ToolResult(
                success=False,
                data="",
                error=f"Permission denied: tool '{name}' requires {tool.required_permissions}",
            )
        return await tool.execute(**kwargs)
