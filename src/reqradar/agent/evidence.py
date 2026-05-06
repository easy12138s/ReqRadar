import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Evidence:
    id: str
    type: str
    source: str
    content: str
    confidence: str = "medium"
    dimensions: list[str] = field(default_factory=list)
    timestamp: Optional[str] = None


class EvidenceCollector:
    def __init__(self):
        self.evidences: list[Evidence] = []
        self._counter: int = 0

    def add(
        self,
        type: str,
        source: str,
        content: str,
        confidence: str = "medium",
        dimensions: list[str] | None = None,
    ) -> str:
        self._counter += 1
        ev_id = f"ev-{self._counter:03d}"
        evidence = Evidence(
            id=ev_id,
            type=type,
            source=source,
            content=content,
            confidence=confidence,
            dimensions=dimensions or [],
        )
        self.evidences.append(evidence)
        return ev_id

    def get_by_dimension(self, dimension: str) -> list[Evidence]:
        return [ev for ev in self.evidences if dimension in ev.dimensions]

    def get_by_type(self, evidence_type: str) -> list[Evidence]:
        return [ev for ev in self.evidences if ev.type == evidence_type]

    def get_all_evidence_text(self) -> str:
        if not self.evidences:
            return "暂无证据"
        lines = []
        for ev in self.evidences:
            dim_str = ", ".join(ev.dimensions) if ev.dimensions else "无特定维度"
            lines.append(
                f"[{ev.id}] ({ev.type}, {ev.confidence}) {ev.source}: {ev.content} [维度: {dim_str}]"
            )
        return "\n".join(lines)

    def to_snapshot(self) -> list[dict]:
        return [
            {
                "id": ev.id,
                "type": ev.type,
                "source": ev.source,
                "content": ev.content,
                "confidence": ev.confidence,
                "dimensions": ev.dimensions,
                "timestamp": ev.timestamp,
            }
            for ev in self.evidences
        ]

    def from_snapshot(self, snapshot: list[dict]) -> None:
        self.evidences = []
        self._counter = 0
        for item in snapshot:
            ev = Evidence(
                id=item["id"],
                type=item["type"],
                source=item["source"],
                content=item["content"],
                confidence=item.get("confidence", "medium"),
                dimensions=item.get("dimensions", []),
                timestamp=item.get("timestamp"),
            )
            self.evidences.append(ev)
            try:
                num = int(item["id"].split("-")[1])
                self._counter = max(self._counter, num)
            except (ValueError, IndexError):
                pass

    def to_context_text(self) -> str:
        if not self.evidences:
            return ""
        lines = ["已收集证据："]
        for ev in self.evidences:
            lines.append(f"- [{ev.id}] ({ev.type}/{ev.confidence}) {ev.source}: {ev.content[:200]}")
        return "\n".join(lines)
