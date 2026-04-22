from reqradar.agent.tools.base import BaseTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

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
