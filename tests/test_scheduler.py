"""测试固定流程调度器"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from reqradar.core.context import AnalysisContext, StepResult
from reqradar.core.exceptions import FatalError
from reqradar.core.scheduler import Scheduler


def _make_context() -> AnalysisContext:
    return AnalysisContext(requirement_path=Path("test.md"))


def _async_handler(return_value=None):
    handler = AsyncMock(return_value=return_value)
    return handler


def _all_step_handlers(**overrides):
    defaults = {
        "read_handler": _async_handler({"text": "doc"}),
        "extract_handler": _async_handler({"terms": []}),
        "map_keywords_handler": _async_handler({"mapped": []}),
        "retrieve_handler": _async_handler({"results": []}),
        "analyze_handler": _async_handler({"analysis": {}}),
        "generate_handler": _async_handler({"report": ""}),
    }
    defaults.update(overrides)
    return defaults


class TestStepResult:
    def test_creation_with_defaults(self):
        r = StepResult(step="read", success=True)
        assert r.step == "read"
        assert r.success is True
        assert r.confidence == 1.0
        assert r.data is None
        assert r.error is None

    def test_creation_with_all_fields(self):
        r = StepResult(step="extract", success=False, confidence=0.5, data={"k": "v"}, error="boom")
        assert r.step == "extract"
        assert r.success is False
        assert r.confidence == 0.5
        assert r.data == {"k": "v"}
        assert r.error == "boom"

    def test_mark_failed(self):
        r = StepResult(step="read", success=True, confidence=1.0)
        r.mark_failed("oops", confidence=0.2)
        assert r.success is False
        assert r.error == "oops"
        assert r.confidence == 0.2


@pytest.mark.asyncio
async def test_all_steps_successful():
    handlers = _all_step_handlers()
    scheduler = Scheduler(**handlers)
    ctx = _make_context()
    result = await scheduler.run(ctx)

    assert result.is_complete
    assert result.completeness == "full"
    for step_name, _ in Scheduler.STEPS:
        sr = result.get_result(step_name)
        assert sr is not None
        assert sr.success is True
        assert sr.confidence == 1.0
        assert sr.error is None


@pytest.mark.asyncio
async def test_fatal_error_stops_execution():
    fatal_handler = _async_handler()
    fatal_handler.side_effect = FatalError("unrecoverable")

    handlers = _all_step_handlers(extract_handler=fatal_handler)
    scheduler = Scheduler(**handlers)
    ctx = _make_context()
    result = await scheduler.run(ctx)

    assert result.is_complete
    extract_result = result.get_result("extract")
    assert extract_result is not None
    assert extract_result.success is False
    assert extract_result.error == "unrecoverable"
    assert extract_result.confidence == 0.0

    assert result.get_result("read") is not None
    assert result.get_result("read").success is True

    assert result.get_result("map_keywords") is None
    assert result.get_result("retrieve") is None
    assert result.get_result("analyze") is None
    assert result.get_result("generate") is None


@pytest.mark.asyncio
async def test_non_fatal_exception_continues():
    failing_handler = _async_handler()
    failing_handler.side_effect = RuntimeError("transient")

    handlers = _all_step_handlers(retrieve_handler=failing_handler)
    scheduler = Scheduler(**handlers)
    ctx = _make_context()
    result = await scheduler.run(ctx)

    assert result.is_complete
    retrieve_result = result.get_result("retrieve")
    assert retrieve_result is not None
    assert retrieve_result.success is False
    assert retrieve_result.error == "transient"
    assert retrieve_result.confidence == 0.0

    assert result.get_result("analyze") is not None
    assert result.get_result("analyze").success is True
    assert result.get_result("generate") is not None
    assert result.get_result("generate").success is True


@pytest.mark.asyncio
async def test_step_results_stored_and_accessible():
    handler = _async_handler({"custom": "payload"})
    handlers = _all_step_handlers(read_handler=handler)
    scheduler = Scheduler(**handlers)
    ctx = _make_context()
    result = await scheduler.run(ctx)

    read_result = result.get_result("read")
    assert read_result is not None
    assert read_result.data == {"custom": "payload"}

    assert result.get_result("nonexistent_step") is None


@pytest.mark.asyncio
async def test_completeness_calculation():
    failing = _async_handler()
    failing.side_effect = ValueError("bad")

    handlers = _all_step_handlers(analyze_handler=failing)
    scheduler = Scheduler(**handlers)
    ctx = _make_context()
    result = await scheduler.run(ctx)

    assert result.completeness == "partial"


@pytest.mark.asyncio
async def test_missing_handler_skips_step():
    handlers = _all_step_handlers()
    del handlers["map_keywords_handler"]
    scheduler = Scheduler(**handlers)
    ctx = _make_context()
    result = await scheduler.run(ctx)

    assert result.is_complete
    assert result.get_result("map_keywords") is None


@pytest.mark.asyncio
async def test_before_and_after_hooks():
    before_hook = AsyncMock()
    after_hook = AsyncMock()

    handlers = _all_step_handlers()
    scheduler = Scheduler(**handlers)
    scheduler.register_before_hook("read", before_hook)
    scheduler.register_after_hook("read", after_hook)

    ctx = _make_context()
    await scheduler.run(ctx)

    before_hook.assert_awaited_once()
    after_hook.assert_awaited_once()
