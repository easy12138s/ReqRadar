import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker, DEFAULT_DIMENSIONS

logger = logging.getLogger("reqradar.agent.analysis_agent")


class AgentState(Enum):
    INIT = "init"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


DEPTH_MAX_STEPS = {
    "quick": 10,
    "standard": 15,
    "deep": 25,
}


class AnalysisAgent:
    def __init__(
        self,
        requirement_text: str,
        project_id: int,
        user_id: int,
        depth: str = "standard",
        max_steps: int | None = None,
    ):
        self.requirement_text = requirement_text
        self.project_id = project_id
        self.user_id = user_id
        self.depth = depth
        self.max_steps = max_steps or DEPTH_MAX_STEPS.get(depth, 15)
        self.state: AgentState = AgentState.INIT
        self.step_count: int = 0
        self.evidence_collector = EvidenceCollector()
        self.dimension_tracker = DimensionTracker()
        self.visited_files: list[str] = []
        self.tool_call_history: list[dict] = []
        self.project_memory_text: str = ""
        self.user_memory_text: str = ""
        self.historical_context: str = ""
        self.final_report_data: dict | None = None
        self._cancelled: bool = False
        self._llm_declared_terminal: bool = False
        self._consecutive_empty_steps: int = 0
        self._consecutive_failures: int = 0
        self._pending_actions: list[dict] = []

    def cancel(self) -> None:
        self._cancelled = True
        self.state = AgentState.CANCELLED

    def should_terminate(self) -> bool:
        if self._cancelled:
            return True
        if self.step_count >= self.max_steps:
            return True
        if self._llm_declared_terminal:
            return True
        if self.dimension_tracker.all_sufficient():
            return True
        if self._consecutive_empty_steps >= 3:
            return True
        if self._consecutive_failures >= 3:
            return True
        return False

    def get_current_phase(self) -> str:
        ds = self.dimension_tracker.status_summary()
        if ds.get("understanding") != "sufficient":
            return "understand"
        if ds.get("impact") != "sufficient" or ds.get("evidence") != "sufficient":
            return "scope"
        if ds.get("risk") != "sufficient" or ds.get("change") != "sufficient":
            return "assess"
        return "decide"

    def record_evidence(
        self,
        type: str,
        source: str,
        content: str,
        confidence: str = "medium",
        dimensions: list[str] | None = None,
    ) -> str:
        ev_id = self.evidence_collector.add(
            type=type,
            source=source,
            content=content,
            confidence=confidence,
            dimensions=dimensions,
        )
        if dimensions:
            for dim in dimensions:
                self.dimension_tracker.add_evidence(dim, ev_id)
        if source not in self.visited_files and type == "code":
            self.visited_files.append(source.split(":")[0] if ":" in source else source)
        return ev_id

    def record_tool_call(self, tool_name: str, parameters: dict, result_summary: str) -> None:
        self.tool_call_history.append(
            {
                "step": self.step_count,
                "tool": tool_name,
                "parameters": parameters,
                "result_summary": result_summary[:200],
            }
        )

    def get_context_text(self) -> str:
        parts = []
        if self.project_memory_text:
            parts.append(f"## 项目画像\n{self.project_memory_text}")
        if self.user_memory_text:
            parts.append(f"## 用户偏好\n{self.user_memory_text}")
        if self.historical_context:
            parts.append(f"## 相似历史需求\n{self.historical_context}")
        parts.append(f"## 当前需求\n{self.requirement_text}")
        parts.append(f"## 维度状态\n{self._dimension_status_text()}")
        ev_text = self.evidence_collector.to_context_text()
        if ev_text:
            parts.append(ev_text)
        parts.append(f"## 步骤计数\n已用 {self.step_count}/{self.max_steps} 步")
        return "\n\n".join(parts)

    def _dimension_status_text(self) -> str:
        lines = []
        for dim_id, state in self.dimension_tracker.dimensions.items():
            ev_count = len(state.evidence_ids)
            lines.append(f"- {dim_id}: {state.status} ({ev_count} 条证据)")
        return "\n".join(lines)

    def get_weak_dimensions_text(self) -> str:
        weak = self.dimension_tracker.get_weak_dimensions()
        if not weak:
            return "所有维度已达标"
        return "需要补充证据的维度：" + ", ".join(weak)

    def get_context_snapshot(self) -> dict:
        return {
            "evidence_list": self.evidence_collector.to_snapshot(),
            "dimension_status": self.dimension_tracker.to_snapshot(),
            "visited_files": list(self.visited_files),
            "tool_calls": list(self.tool_call_history),
            "step_count": self.step_count,
            "_llm_declared_terminal": self._llm_declared_terminal,
            "_consecutive_empty_steps": self._consecutive_empty_steps,
        }

    def restore_from_snapshot(self, snapshot: dict) -> None:
        if "evidence_list" in snapshot:
            self.evidence_collector.from_snapshot(snapshot["evidence_list"])
        if "dimension_status" in snapshot:
            self.dimension_tracker.from_snapshot(snapshot["dimension_status"])
        if "visited_files" in snapshot:
            self.visited_files = list(snapshot["visited_files"])
        if "tool_calls" in snapshot:
            self.tool_call_history = list(snapshot["tool_calls"])
        if "step_count" in snapshot:
            self.step_count = snapshot["step_count"]
        if "_llm_declared_terminal" in snapshot:
            self._llm_declared_terminal = snapshot["_llm_declared_terminal"]
        if "_consecutive_empty_steps" in snapshot:
            self._consecutive_empty_steps = snapshot["_consecutive_empty_steps"]
