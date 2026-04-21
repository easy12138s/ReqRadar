from reqradar.agent.tool_call_tracker import ToolCallTracker


def test_track_call_increments_count():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    tracker.track_call("search_code", {"keyword": "auth"})
    assert tracker.call_count == 1
    assert tracker.tool_counts["search_code"] == 1


def test_dedup_same_call():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    tracker.track_call("search_code", {"keyword": "auth"})
    assert tracker.is_duplicate("search_code", {"keyword": "auth"}) is True
    assert tracker.is_duplicate("search_code", {"keyword": "memory"}) is False


def test_within_budget():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    assert tracker.within_token_budget(3000) is True
    tracker.add_tokens(4000)
    assert tracker.within_token_budget(2000) is False


def test_within_round_limit():
    tracker = ToolCallTracker(max_rounds=3, max_total_tokens=50000)
    for i in range(3):
        tracker.track_call("search_code", {"keyword": f"kw{i}"})
    assert tracker.within_round_limit() is False

    tracker2 = ToolCallTracker(max_rounds=5, max_total_tokens=50000)
    tracker2.track_call("search_code", {"keyword": "test"})
    assert tracker2.within_round_limit() is True


def test_summary():
    tracker = ToolCallTracker(max_rounds=10, max_total_tokens=5000)
    tracker.track_call("search_code", {"keyword": "auth"})
    tracker.add_tokens(500)
    summary = tracker.summary()
    assert "search_code" in summary
    assert "Total tool tokens" in summary
