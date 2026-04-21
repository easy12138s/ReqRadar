from reqradar.agent.tools.base import BaseTool, ToolResult


class ReadModuleSummaryTool(BaseTool):
    name = "read_module_summary"
    description = "获取指定模块的职责描述和代码摘要"
    parameters_schema = {
        "name": "read_module_summary",
        "description": "获取指定模块的职责描述和代码摘要",
        "parameters": {
            "type": "object",
            "properties": {
                "module_name": {
                    "type": "string",
                    "description": "模块名称（如 agent、modules/memory）",
                },
            },
            "required": ["module_name"],
        },
    }

    def __init__(self, memory_data: dict | None = None):
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        module_name = kwargs.get("module_name", "")

        if not self.memory_data or not module_name:
            return ToolResult(success=False, data="", error="No memory data or module name")

        for m in self.memory_data.get("modules", []):
            if m.get("name") == module_name or module_name.lower() in m.get("name", "").lower():
                lines = [f"模块: {m.get('name', '')}"]
                if m.get("responsibility"):
                    lines.append(f"职责: {m['responsibility']}")
                if m.get("code_summary"):
                    lines.append(f"代码摘要: {m['code_summary']}")
                if m.get("key_classes"):
                    lines.append(f"核心类: {', '.join(m['key_classes'])}")
                return ToolResult(success=True, data="\n".join(lines))

        return ToolResult(success=True, data=f"未找到模块: {module_name}")
