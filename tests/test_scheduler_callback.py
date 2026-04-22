"""Test Scheduler callback support for Web progress push."""
import asyncio
from pathlib import Path

import pytest

from reqradar.core.context import AnalysisContext, StepResult
from reqradar.core.scheduler import Scheduler


async def _handler_read(ctx):
    return "content"


async def _handler_extract(ctx):
    return None


async def _handler_fail(ctx):
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_scheduler_calls_on_step_start():
    started_steps = []

    async def on_start(step_name: str, step_desc: str):
        started_steps.append(step_name)

    scheduler = Scheduler(
        read_handler=_handler_read,
        extract_handler=_handler_extract,
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_start=on_start)
    assert "read" in started_steps
    assert "extract" in started_steps


@pytest.mark.asyncio
async def test_scheduler_calls_on_step_complete():
    completed = []

    async def on_complete(step_name: str, result: StepResult):
        completed.append((step_name, result.success))

    scheduler = Scheduler(
        read_handler=_handler_read,
        extract_handler=_handler_extract,
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_complete=on_complete)
    step_names = [name for name, _ in completed]
    assert "read" in step_names
    assert all(success for _, success in completed)


@pytest.mark.asyncio
async def test_scheduler_no_callback_is_default():
    scheduler = Scheduler(
        read_handler=_handler_read,
        extract_handler=_handler_extract,
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    result = await scheduler.run(context)
    assert result.is_complete


@pytest.mark.asyncio
async def test_scheduler_callback_on_failed_step():
    failed_step = None

    async def on_complete(step_name: str, result: StepResult):
        nonlocal failed_step
        if not result.success:
            failed_step = step_name

    scheduler = Scheduler(
        read_handler=_handler_fail,
        extract_handler=_handler_extract,
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_complete=on_complete)
    assert failed_step == "read"


@pytest.mark.asyncio
async def test_scheduler_callback_receives_step_desc():
    descriptions = {}

    async def on_start(step_name: str, step_desc: str):
        descriptions[step_name] = step_desc

    scheduler = Scheduler(
        read_handler=_handler_read,
        extract_handler=_handler_extract,
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_start=on_start)
    assert descriptions["read"] == "读取需求文档"
    assert descriptions["extract"] == "提取关键术语"


@pytest.mark.asyncio
async def test_scheduler_both_callbacks():
    events = []

    async def on_start(step_name: str, step_desc: str):
        events.append(("start", step_name))

    async def on_complete(step_name: str, result: StepResult):
        events.append(("complete", step_name, result.success))

    scheduler = Scheduler(
        read_handler=_handler_read,
        extract_handler=_handler_extract,
    )
    context = AnalysisContext(requirement_path=Path("test.md"))
    await scheduler.run(context, on_step_start=on_start, on_step_complete=on_complete)

    assert events[0] == ("start", "read")
    assert events[1] == ("complete", "read", True)
    assert events[2] == ("start", "extract")
    assert events[3] == ("complete", "extract", True)
