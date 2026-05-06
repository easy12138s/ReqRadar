from reqradar.agent.tools.base import BaseTool, ToolResult


class GetProjectProfileTool(BaseTool):
    name = "get_project_profile"
    description = "获取项目画像信息，包括项目描述、技术栈和架构风格"
    required_permissions = ["read:memory"]
    parameters_schema = {
        "name": "get_project_profile",
        "description": "获取项目画像信息，包括项目描述、技术栈和架构风格",
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

        profile = self.memory_data.get("project_profile", {})
        if not profile or not profile.get("description"):
            return ToolResult(success=True, data="项目画像尚未建立，请先运行 reqradar index")

        lines = [f"项目名称: {profile.get('name', '未知')}"]
        lines.append(f"描述: {profile.get('description', '未知')}")
        lines.append(f"架构风格: {profile.get('architecture_style', '未知')}")

        tech_stack = profile.get("tech_stack", {})
        if tech_stack:
            langs = tech_stack.get("languages", [])
            frameworks = tech_stack.get("frameworks", [])
            deps = tech_stack.get("key_dependencies", [])
            if langs:
                lines.append(f"编程语言: {', '.join(langs)}")
            if frameworks:
                lines.append(f"框架: {', '.join(frameworks)}")
            if deps:
                lines.append(f"关键依赖: {', '.join(deps)}")

        return ToolResult(success=True, data="\n".join(lines))
