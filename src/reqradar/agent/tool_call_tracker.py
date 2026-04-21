import json
import logging

logger = logging.getLogger("reqradar.tool_tracker")


class ToolCallTracker:
    def __init__(self, max_rounds: int = 15, max_total_tokens: int = 8000):
        self.max_rounds = max_rounds
        self.max_total_tokens = max_total_tokens
        self.call_count = 0
        self.tool_counts: dict[str, int] = {}
        self._seen_calls: dict[str, set] = {}
        self._total_tokens = 0

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

    def add_tokens(self, tokens: int) -> None:
        self._total_tokens += tokens
        logger.debug(
            "Tool token usage: %d/%d", self._total_tokens, self.max_total_tokens
        )

    def within_token_budget(self, estimated_tokens: int) -> bool:
        return (self._total_tokens + estimated_tokens) <= self.max_total_tokens

    def within_round_limit(self) -> bool:
        return self.call_count < self.max_rounds

    def summary(self) -> str:
        lines = [f"Total tool calls: {self.call_count}/{self.max_rounds}"]
        for name, count in self.tool_counts.items():
            lines.append(f"  {name}: {count} calls")
        lines.append(
            f"Total tool tokens: {self._total_tokens}/{self.max_total_tokens}"
        )
        return "\n".join(lines)
