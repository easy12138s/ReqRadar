"""ToolCallTracker 单元测试"""

import pytest

from reqradar.agent.tool_call_tracker import ToolCallTracker


class TestToolCallTrackerInit:
    def test_default_max_calls(self):
        tracker = ToolCallTracker()
        assert tracker.max_calls_per_tool == 10

    def test_custom_max_calls(self):
        tracker = ToolCallTracker(max_calls_per_tool=5)
        assert tracker.max_calls_per_tool == 5

    def test_initial_state_empty(self):
        tracker = ToolCallTracker()
        assert tracker.call_count == 0
        assert tracker.tool_counts == {}
        assert tracker._seen_calls == {}


class TestTrackCall:
    def test_increments_call_count(self):
        tracker = ToolCallTracker()
        tracker.track_call("search_code", {"query": "test"})
        assert tracker.call_count == 1

    def test_counts_per_tool(self):
        tracker = ToolCallTracker()
        tracker.track_call("tool_a", {})
        tracker.track_call("tool_a", {})
        tracker.track_call("tool_b", {})
        assert tracker.tool_counts["tool_a"] == 2
        assert tracker.tool_counts["tool_b"] == 1

    def test_tracks_unique_calls(self):
        tracker = ToolCallTracker()
        args1 = {"query": "a"}
        args2 = {"query": "b"}
        tracker.track_call("search", args1)
        tracker.track_call("search", args2)
        assert len(tracker._seen_calls["search"]) == 2


class TestIsDuplicate:
    def test_first_call_not_duplicate(self):
        tracker = ToolCallTracker()
        assert tracker.is_duplicate("tool", {}) is False

    def test_same_args_is_duplicate(self):
        tracker = ToolCallTracker()
        tracker.track_call("tool", {"x": 1})
        assert tracker.is_duplicate("tool", {"x": 1}) is True

    def test_different_args_not_duplicate(self):
        tracker = ToolCallTracker()
        tracker.track_call("tool", {"x": 1})
        assert tracker.is_duplicate("tool", {"x": 2}) is False

    def test_different_tools_independent(self):
        tracker = ToolCallTracker()
        tracker.track_call("tool_a", {})
        assert tracker.is_duplicate("tool_b", {}) is False


class TestIsToolOverLimit:
    def test_under_limit(self):
        tracker = ToolCallTracker(max_calls_per_tool=3)
        for _ in range(3):
            tracker.track_call("t", {})
        assert tracker.is_tool_over_limit("t") is True
        assert tracker.is_tool_over_limit("other") is False

    def test_exactly_at_limit(self):
        tracker = ToolCallTracker(max_calls_per_tool=1)
        tracker.track_call("t", {})
        assert tracker.is_tool_over_limit("t") is True


class TestSummary:
    def test_empty_summary(self):
        tracker = ToolCallTracker()
        text = tracker.summary()
        assert "Total tool calls: 0" in text

    def test_populated_summary(self):
        tracker = ToolCallTracker()
        tracker.track_call("search_code", {})
        tracker.track_call("search_code", {})
        tracker.track_call("read_file", {})
        text = tracker.summary()
        assert "Total tool calls: 3" in text
        assert "search_code: 2" in text
        assert "read_file: 1" in text
