from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    data: str
    error: str = ""
    truncated: bool = False


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters_schema: dict | None = None

    @classmethod
    def openai_schema(cls) -> dict:
        schema: dict = cls.parameters_schema or {}
        if schema.get("type") == "function" and isinstance(schema.get("function"), dict):
            return schema

        return {
            "type": "function",
            "function": {
                "name": schema.get("name", cls.name),
                "description": schema.get("description", cls.description),
                "parameters": schema.get(
                    "parameters",
                    {
                        "type": "object",
                        "properties": {},
                    },
                ),
            },
        }

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...
