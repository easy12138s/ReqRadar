from reqradar.agent.tool_call_tracker import ToolCallTracker


def test_track_call_increments_count():
    tracker = ToolCallTracker()
    tracker.track_call("search_code", {"keyword": "auth"})
    assert tracker.call_count == 1
    assert tracker.tool_counts["search_code"] == 1


def test_dedup_same_call():
    tracker = ToolCallTracker()
    tracker.track_call("search_code", {"keyword": "auth"})
    assert tracker.is_duplicate("search_code", {"keyword": "auth"}) is True
    assert tracker.is_duplicate("search_code", {"keyword": "memory"}) is False


def test_is_tool_over_limit():
    tracker = ToolCallTracker(max_calls_per_tool=3)
    for i in range(3):
        tracker.track_call("search_code", {"keyword": f"kw{i}"})
    assert tracker.is_tool_over_limit("search_code") is True


def test_is_tool_under_limit():
    tracker = ToolCallTracker(max_calls_per_tool=5)
    tracker.track_call("search_code", {"keyword": "test"})
    assert tracker.is_tool_over_limit("search_code") is False


def test_summary():
    tracker = ToolCallTracker()
    tracker.track_call("search_code", {"keyword": "auth"})
    summary = tracker.summary()
    assert "search_code" in summary
    assert "Total tool calls" in summary
