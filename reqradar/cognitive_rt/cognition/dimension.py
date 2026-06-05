from __future__ import annotations

from dataclasses import dataclass, field

from reqradar.kernel.enums import DimensionStatus

DEFAULT_DIMENSIONS = [
    "understanding",
    "impact",
    "risk",
    "change",
    "decision",
    "evidence",
    "verification",
]


@dataclass
class DimensionState:
    id: str
    status: DimensionStatus = DimensionStatus.PENDING
    evidence_ids: list[str] = field(default_factory=list)
    draft_content: str | None = None

    def mark_in_progress(self) -> None:
        if self.status == DimensionStatus.PENDING:
            self.status = DimensionStatus.IN_PROGRESS

    def mark_sufficient(self) -> None:
        self.status = DimensionStatus.SUFFICIENT

    def mark_insufficient(self) -> None:
        self.status = DimensionStatus.INSUFFICIENT

    def add_evidence(self, evidence_id: str) -> None:
        if evidence_id not in self.evidence_ids:
            self.evidence_ids.append(evidence_id)


class DimensionTracker:
    def __init__(self, dimensions: list[str] | None = None):
        dim_list = dimensions if dimensions is not None else DEFAULT_DIMENSIONS
        self.dimensions: dict[str, DimensionState] = {
            dim_id: DimensionState(id=dim_id) for dim_id in dim_list
        }

    def mark_in_progress(self, dimension_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].mark_in_progress()

    def mark_sufficient(self, dimension_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].mark_sufficient()

    def mark_insufficient(self, dimension_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].mark_insufficient()

    def add_evidence(self, dimension_id: str, evidence_id: str) -> None:
        if dimension_id in self.dimensions:
            self.dimensions[dimension_id].add_evidence(evidence_id)

    def get_weak_dimensions(self) -> list[str]:
        return [
            dim_id
            for dim_id, state in self.dimensions.items()
            if state.status
            in (DimensionStatus.PENDING, DimensionStatus.IN_PROGRESS, DimensionStatus.INSUFFICIENT)
        ]

    def all_sufficient(self) -> bool:
        return all(s.status == DimensionStatus.SUFFICIENT for s in self.dimensions.values())

    def status_summary(self) -> dict[str, str]:
        return {dim_id: state.status for dim_id, state in self.dimensions.items()}

    def to_snapshot(self) -> dict:
        return {
            dim_id: {
                "status": state.status,
                "evidence_ids": state.evidence_ids,
                "draft_content": state.draft_content,
            }
            for dim_id, state in self.dimensions.items()
        }

    def from_snapshot(self, snapshot: dict) -> None:
        for dim_id, data in snapshot.items():
            if dim_id in self.dimensions:
                self.dimensions[dim_id].status = data.get("status", "pending")
                self.dimensions[dim_id].evidence_ids = data.get("evidence_ids", [])
                self.dimensions[dim_id].draft_content = data.get("draft_content")
