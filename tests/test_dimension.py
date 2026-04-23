import pytest

from reqradar.agent.dimension import DimensionState, DimensionTracker


def test_dimension_tracker_init():
    tracker = DimensionTracker()
    assert len(tracker.dimensions) == 7
    assert all(d.status == "pending" for d in tracker.dimensions.values())


def test_dimension_tracker_mark_in_progress():
    tracker = DimensionTracker()
    tracker.mark_in_progress("impact")
    assert tracker.dimensions["impact"].status == "in_progress"


def test_dimension_tracker_mark_sufficient():
    tracker = DimensionTracker()
    tracker.mark_sufficient("impact")
    assert tracker.dimensions["impact"].status == "sufficient"


def test_dimension_tracker_add_evidence():
    tracker = DimensionTracker()
    tracker.add_evidence("impact", "ev-001")
    assert "ev-001" in tracker.dimensions["impact"].evidence_ids


def test_dimension_tracker_get_weak_dimensions():
    tracker = DimensionTracker()
    tracker.mark_sufficient("understanding")
    tracker.mark_sufficient("impact")
    weak = tracker.get_weak_dimensions()
    assert "risk" in weak
    assert "understanding" not in weak


def test_dimension_tracker_all_sufficient():
    tracker = DimensionTracker()
    for dim_id in tracker.dimensions:
        tracker.mark_sufficient(dim_id)
    assert tracker.all_sufficient()


def test_dimension_tracker_status_summary():
    tracker = DimensionTracker()
    tracker.mark_sufficient("understanding")
    tracker.mark_in_progress("impact")
    summary = tracker.status_summary()
    assert summary["understanding"] == "sufficient"
    assert summary["impact"] == "in_progress"
    assert summary["risk"] == "pending"


def test_dimension_tracker_custom_dimensions():
    tracker = DimensionTracker(dimensions=["impact", "risk", "change"])
    assert len(tracker.dimensions) == 3
    assert "impact" in tracker.dimensions
    assert "understanding" not in tracker.dimensions
