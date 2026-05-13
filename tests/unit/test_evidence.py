"""EvidenceCollector 单元测试"""

import pytest

from reqradar.agent.evidence import Evidence, EvidenceCollector


class TestEvidence:
    def test_creation_with_defaults(self):
        ev = Evidence(id="ev1", type="code", source="file.py", content="test")
        assert ev.id == "ev1"
        assert ev.type == "code"
        assert ev.source == "file.py"
        assert ev.content == "test"
        assert ev.confidence == "medium"
        assert ev.dimensions == []
        assert ev.timestamp is None

    def test_creation_with_all_fields(self):
        ev = Evidence(
            id="ev2",
            type="git",
            source="commit abc",
            content="change",
            confidence="high",
            dimensions=["impact", "risk"],
            timestamp="2026-01-01T00:00:00Z",
        )
        assert ev.confidence == "high"
        assert len(ev.dimensions) == 2
        assert ev.timestamp is not None


class TestEvidenceCollector:
    def test_init_empty(self):
        collector = EvidenceCollector()
        assert collector.evidences == []
        assert collector._counter == 0

    def test_add_evidence_returns_id(self):
        collector = EvidenceCollector()
        ev_id = collector.add(type="code", source="main.py", content="function")
        assert ev_id == "ev-001"

    def test_add_multiple_evidences_increments(self):
        collector = EvidenceCollector()
        id1 = collector.add(type="code", source="f1.py", content="c1")
        id2 = collector.add(type="git", source="commit1", content="c2")
        id3 = collector.add(type="code", source="f2.py", content="c3")
        assert id1 == "ev-001"
        assert id2 == "ev-002"
        assert id3 == "ev-003"

    def test_add_evidence_with_dimensions(self):
        collector = EvidenceCollector()
        collector.add(
            type="code",
            source="auth.py",
            content="login function",
            dimensions=["understanding", "impact"],
        )
        assert len(collector.evidences) == 1
        assert len(collector.evidences[0].dimensions) == 2

    def test_get_by_dimension(self):
        collector = EvidenceCollector()
        collector.add(type="code", source="a.py", content="x", dimensions=["risk"])
        collector.add(type="code", source="b.py", content="y", dimensions=["impact"])
        collector.add(type="git", source="c1", content="z", dimensions=["risk", "evidence"])

        risk_evs = collector.get_by_dimension("risk")
        assert len(risk_evs) == 2

        impact_evs = collector.get_by_dimension("impact")
        assert len(impact_evs) == 1

    def test_get_by_type(self):
        collector = EvidenceCollector()
        collector.add(type="code", source="a.py", content="x")
        collector.add(type="git", source="c1", content="y")
        collector.add(type="code", source="b.py", content="z")

        code_evs = collector.get_by_type("code")
        assert len(code_evs) == 2

        git_evs = collector.get_by_type("git")
        assert len(git_evs) == 1

    def test_get_all_evidence_text_empty(self):
        collector = EvidenceCollector()
        text = collector.get_all_evidence_text()
        assert text == "暂无证据"

    def test_get_all_evidence_text_with_data(self):
        collector = EvidenceCollector()
        collector.add(type="code", source="main.py", content="important code", dimensions=["understanding"])
        text = collector.get_all_evidence_text()
        assert "ev-001" in text
        assert "main.py" in text
        assert "important code" in text
        assert "understanding" in text

    def test_to_snapshot_empty(self):
        collector = EvidenceCollector()
        snapshot = collector.to_snapshot()
        assert snapshot == []

    def test_to_snapshot_with_data(self):
        collector = EvidenceCollector()
        collector.add(type="code", source="f.py", content="data", confidence="high")
        snapshot = collector.to_snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["type"] == "code"
        assert snapshot[0]["confidence"] == "high"

    def test_from_snapshot_restores_state(self):
        collector = EvidenceCollector()
        snapshot = [
            {
                "id": "ev-005",
                "type": "code",
                "source": "test.py",
                "content": "restored",
                "confidence": "low",
                "dimensions": ["risk"],
                "timestamp": None,
            }
        ]
        collector.from_snapshot(snapshot)
        assert len(collector.evidences) == 1
        assert collector._counter == 5
        assert collector.evidences[0].id == "ev-005"

    def test_from_snapshot_handles_bad_ids(self):
        collector = EvidenceCollector()
        snapshot = [{"id": "bad-id", "type": "code", "source": "f.py", "content": "x"}]
        collector.from_snapshot(snapshot)
        assert collector._counter == 0

    def test_to_context_text_empty(self):
        collector = EvidenceCollector()
        text = collector.to_context_text()
        assert text == ""

    def test_to_context_text_with_data(self):
        collector = EvidenceCollector()
        collector.add(type="code", source="long_file.py", content="x" * 300)
        text = collector.to_context_text()
        assert "已收集证据：" in text
        assert "ev-001" in text
