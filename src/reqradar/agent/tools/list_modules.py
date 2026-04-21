from reqradar.agent.tools.base import BaseTool, ToolResult


class ListModulesTool(BaseTool):
    name = "list_modules"
    description = "列出项目中的所有模块及其职责"
    parameters_schema = {
        "name": "list_modules",
        "description": "列出项目中的所有模块及其职责",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    }

    def __init__(self, memory_data: dict | None = None):
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        if not self.memory_data:
            return ToolResult(success=False, data="", error="No memory data")

        modules = self.memory_data.get("modules", [])
        if not modules:
            return ToolResult(success=True, data="项目尚未建立模块画像")

        lines = []
        for m in modules:
            line = f"- {m.get('name', 'unknown')}: {m.get('responsibility', '职责未定义')}"
            lines.append(line)

        return ToolResult(success=True, data="\n".join(lines))
