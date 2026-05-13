"""DimensionTracker 单元测试"""

import pytest

from reqradar.agent.dimension import DEFAULT_DIMENSIONS, DimensionState, DimensionTracker


class TestDimensionState:
    def test_default_state(self):
        state = DimensionState(id="test")
        assert state.id == "test"
        assert state.status == "pending"
        assert state.evidence_ids == []
        assert state.draft_content is None

    def test_mark_in_progress_from_pending(self):
        state = DimensionState(id="test")
        state.mark_in_progress()
        assert state.status == "in_progress"

    def test_mark_in_progress_idempotent(self):
        state = DimensionState(id="test", status="sufficient")
        state.mark_in_progress()
        assert state.status == "sufficient"

    def test_mark_sufficient(self):
        state = DimensionState(id="test")
        state.mark_sufficient()
        assert state.status == "sufficient"

    def test_mark_insufficient(self):
        state = DimensionState(id="test")
        state.mark_insufficient()
        assert state.status == "insufficient"

    def test_add_evidence(self):
        state = DimensionState(id="test")
        state.add_evidence("ev1")
        assert state.evidence_ids == ["ev1"]

    def test_add_evidence_dedup(self):
        state = DimensionState(id="test", evidence_ids=["ev1"])
        state.add_evidence("ev1")
        assert len(state.evidence_ids) == 1

    def test_add_multiple_evidence(self):
        state = DimensionState(id="test")
        state.add_evidence("ev1")
        state.add_evidence("ev2")
        state.add_evidence("ev3")
        assert len(state.evidence_ids) == 3


class TestDimensionTracker:
    def test_init_with_defaults(self):
        tracker = DimensionTracker()
        assert set(tracker.dimensions.keys()) == set(DEFAULT_DIMENSIONS)
        for dim_id, state in tracker.dimensions.items():
            assert state.status == "pending"

    def test_init_with_custom_dimensions(self):
        custom = ["dim1", "dim2"]
        tracker = DimensionTracker(dimensions=custom)
        assert list(tracker.dimensions.keys()) == custom

    def test_mark_in_progress(self):
        tracker = DimensionTracker()
        tracker.mark_in_progress("understanding")
        assert tracker.dimensions["understanding"].status == "in_progress"

    def test_mark_in_progress_unknown_dimension(self):
        tracker = DimensionTracker()
        tracker.mark_in_progress("unknown_dim")
        assert "unknown_dim" not in tracker.dimensions

    def test_mark_sufficient(self):
        tracker = DimensionTracker()
        tracker.mark_sufficient("risk")
        assert tracker.dimensions["risk"].status == "sufficient"

    def test_mark_insufficient(self):
        tracker = DimensionTracker()
        tracker.mark_insufficient("evidence")
        assert tracker.dimensions["evidence"].status == "insufficient"

    def test_add_evidence_to_dimension(self):
        tracker = DimensionTracker()
        tracker.add_evidence("understanding", "ev1")
        assert "ev1" in tracker.dimensions["understanding"].evidence_ids

    def test_get_weak_dimensions_all_pending(self):
        tracker = DimensionTracker()
        weak = tracker.get_weak_dimensions()
        assert len(weak) == len(DEFAULT_DIMENSIONS)

    def test_get_weak_dimensions_some_sufficient(self):
        tracker = DimensionTracker()
        tracker.mark_sufficient("understanding")
        weak = tracker.get_weak_dimensions()
        assert "understanding" not in weak
        assert len(weak) == len(DEFAULT_DIMENSIONS) - 1

    def test_all_sufficient_false_when_pending(self):
        tracker = DimensionTracker()
        assert tracker.all_sufficient() is False

    def test_all_sufficient_true_when_all_done(self):
        tracker = DimensionTracker()
        for dim_id in tracker.dimensions:
            tracker.mark_sufficient(dim_id)
        assert tracker.all_sufficient() is True

    def test_status_summary(self):
        tracker = DimensionTracker()
        tracker.mark_sufficient("impact")
        summary = tracker.status_summary()
        assert summary["impact"] == "sufficient"
        assert summary["understanding"] == "pending"

    def test_to_snapshot(self):
        tracker = DimensionTracker()
        tracker.add_evidence("risk", "ev1")
        snapshot = tracker.to_snapshot()
        assert "risk" in snapshot
        assert snapshot["risk"]["evidence_ids"] == ["ev1"]
        assert snapshot["risk"]["status"] == "pending"

    def test_from_snapshot(self):
        tracker = DimensionTracker()
        snapshot = {
            "understanding": {"status": "sufficient", "evidence_ids": ["ev1"]},
            "risk": {"status": "insufficient", "evidence_ids": []},
        }
        tracker.from_snapshot(snapshot)
        assert tracker.dimensions["understanding"].status == "sufficient"
        assert tracker.dimensions["risk"].status == "insufficient"
        assert "ev1" in tracker.dimensions["understanding"].evidence_ids

    def test_from_snapshot_ignores_unknown_dims(self):
        tracker = DimensionTracker()
        snapshot = {"unknown_dim": {"status": "sufficient", "evidence_ids": []}}
        tracker.from_snapshot(snapshot)
        assert "unknown_dim" not in tracker.dimensions
