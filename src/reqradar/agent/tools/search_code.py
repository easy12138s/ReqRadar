from reqradar.agent.tools.base import BaseTool, ToolResult


class SearchCodeTool(BaseTool):
    name = "search_code"
    description = "在项目代码中搜索包含指定关键词的类、函数或变量"
    parameters_schema = {
        "name": "search_code",
        "description": "在项目代码中搜索包含指定关键词的类、函数或变量",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（英文，如 auth、scheduler、memory）",
                },
                "symbol_type": {
                    "type": "string",
                    "enum": ["class", "function", "all"],
                    "description": "要搜索的符号类型，默认 all",
                },
            },
            "required": ["keyword"],
        },
    }

    def __init__(self, code_graph=None, repo_path: str = ""):
        self.code_graph = code_graph
        self.repo_path = repo_path

    async def execute(self, **kwargs) -> ToolResult:
        keyword = kwargs.get("keyword", "")
        symbol_type = kwargs.get("symbol_type", "all")

        if not self.code_graph or not keyword:
            return ToolResult(success=False, data="", error="No code graph or keyword")

        matches = self.code_graph.find_symbols([keyword])
        if not matches:
            return ToolResult(success=True, data=f"未找到包含 '{keyword}' 的代码符号")

        lines = []
        for f in matches[:10]:
            symbols = [s for s in f.symbols if symbol_type == "all" or s.type == symbol_type]
            if symbols:
                sym_str = ", ".join(f"{s.name}({s.type})" for s in symbols[:5])
                lines.append(f"- {f.path}: {sym_str}")

        if not lines:
            return ToolResult(
                success=True,
                data=f"未找到类型为 '{symbol_type}' 且包含 '{keyword}' 的符号",
            )

        return ToolResult(success=True, data="\n".join(lines))
