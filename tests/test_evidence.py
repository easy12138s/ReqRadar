import pytest

from reqradar.agent.evidence import Evidence, EvidenceCollector


def test_evidence_creation():
    ev = Evidence(
        id="ev-001",
        type="code",
        source="src/web/app.py:42",
        content="Route handler for /api/analyses",
        confidence="high",
        dimensions=["impact", "change"],
    )
    assert ev.id == "ev-001"
    assert ev.type == "code"
    assert ev.confidence == "high"


def test_evidence_collector_add():
    collector = EvidenceCollector()
    ev_id = collector.add(
        type="code",
        source="src/web/app.py:42",
        content="Route handler",
        confidence="high",
        dimensions=["impact"],
    )
    assert ev_id.startswith("ev-")
    assert len(collector.evidences) == 1


def test_evidence_collector_auto_id():
    collector = EvidenceCollector()
    id1 = collector.add(type="code", source="f1", content="c1", confidence="medium")
    id2 = collector.add(type="code", source="f2", content="c2", confidence="high")
    assert id1 != id2


def test_evidence_collector_get_by_dimension():
    collector = EvidenceCollector()
    collector.add(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    collector.add(type="code", source="f2", content="c2", confidence="high", dimensions=["risk"])
    collector.add(type="code", source="f3", content="c3", confidence="medium", dimensions=["impact", "change"])

    impact_evs = collector.get_by_dimension("impact")
    assert len(impact_evs) == 2

    risk_evs = collector.get_by_dimension("risk")
    assert len(risk_evs) == 1


def test_evidence_collector_to_lightweight_snapshot():
    collector = EvidenceCollector()
    collector.add(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    collector.add(type="history", source="analysis-123", content="Similar requirement", confidence="medium", dimensions=["risk"])

    snapshot = collector.to_snapshot()
    assert len(snapshot) == 2
    assert snapshot[0]["id"].startswith("ev-")
    assert snapshot[0]["type"] == "code"
    assert snapshot[1]["type"] == "history"


def test_evidence_collector_from_snapshot():
    collector = EvidenceCollector()
    collector.add(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])

    snapshot = collector.to_snapshot()
    collector2 = EvidenceCollector()
    collector2.from_snapshot(snapshot)
    assert len(collector2.evidences) == 1
    assert collector2.evidences[0].source == "f1"
