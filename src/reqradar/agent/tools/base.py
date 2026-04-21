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

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...
