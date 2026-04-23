from reqradar.agent.tools.base import BaseTool, ToolResult


class GetDependenciesTool(BaseTool):
    name = "get_dependencies"
    description = "查询指定模块的上下游依赖关系"
    required_permissions = ["read:code"]
    parameters_schema = {
        "name": "get_dependencies",
        "description": "查询指定模块的上下游依赖关系",
        "parameters": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "模块名称（如 agent、modules/memory）",
                },
            },
            "required": ["module"],
        },
    }

    def __init__(self, code_graph=None, memory_data: dict | None = None):
        self.code_graph = code_graph
        self.memory_data = memory_data

    async def execute(self, **kwargs) -> ToolResult:
        module_name = kwargs.get("module", "")

        if not module_name:
            return ToolResult(success=False, data="", error="No module name")

        lines = [f"模块 '{module_name}' 的依赖分析:"]

        if self.memory_data:
            for m in self.memory_data.get("modules", []):
                if m.get("name") == module_name or module_name.lower() in m.get("name", "").lower():
                    deps = m.get("dependencies", [])
                    if deps:
                        lines.append(f"声明依赖: {', '.join(deps)}")
                    else:
                        lines.append("声明依赖: 无（可能需从代码推断）")

        if self.code_graph:
            import_lines = []
            for f in self.code_graph.files:
                if module_name.lower() in f.path.lower():
                    for imp in f.imports:
                        if "reqradar" in imp:
                            import_lines.append(f"  {imp}")
            if import_lines:
                lines.append("代码级依赖（reqradar内部）:")
                lines.extend(import_lines[:10])

        return ToolResult(success=True, data="\n".join(lines))
