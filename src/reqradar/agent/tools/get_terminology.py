from reqradar.agent.tools.base import BaseTool, ToolResult


class GetTerminologyTool(BaseTool):
    name = "get_terminology"
    description = "获取项目已知的术语定义列表"
    parameters_schema = {
        "name": "get_terminology",
        "description": "获取项目已知的术语定义列表",
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

        terms = self.memory_data.get("terminology", [])
        if not terms:
            return ToolResult(success=True, data="项目尚未积累术语定义")

        lines = []
        for t in terms:
            line = f"- {t.get('term', '')}: {t.get('definition', '未定义')}"
            if t.get("domain"):
                line += f" [{t['domain']}]"
            lines.append(line)

        return ToolResult(success=True, data="\n".join(lines))
