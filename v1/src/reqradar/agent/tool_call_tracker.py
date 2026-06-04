import json
import logging

logger = logging.getLogger("reqradar.tool_tracker")


class ToolCallTracker:
    def __init__(self, max_calls_per_tool: int = 10):
        self.max_calls_per_tool = max_calls_per_tool
        self.call_count = 0
        self.tool_counts: dict[str, int] = {}
        self._seen_calls: dict[str, set] = {}

    def track_call(self, tool_name: str, arguments: dict) -> None:
        self.call_count += 1
        self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
        if tool_name not in self._seen_calls:
            self._seen_calls[tool_name] = set()
        key = json.dumps(arguments, sort_keys=True)
        self._seen_calls[tool_name].add(key)

    def is_duplicate(self, tool_name: str, arguments: dict) -> bool:
        if tool_name not in self._seen_calls:
            return False
        key = json.dumps(arguments, sort_keys=True)
        return key in self._seen_calls[tool_name]

    def is_tool_over_limit(self, tool_name: str) -> bool:
        return self.tool_counts.get(tool_name, 0) >= self.max_calls_per_tool

    def summary(self) -> str:
        lines = [f"Total tool calls: {self.call_count}"]
        for name, count in self.tool_counts.items():
            lines.append(f"  {name}: {count} calls")
        return "\n".join(lines)
