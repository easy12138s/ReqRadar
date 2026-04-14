"""测试上下文管理"""

from pathlib import Path

from reqradar.core.context import AnalysisContext, StepResult


def test_analysis_context_creation():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    assert ctx.requirement_path == Path("test.md")
    assert ctx.step_results == {}
    assert not ctx.is_complete


def test_step_result_storage():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    result = StepResult(step="test", success=True, confidence=1.0)
    ctx.store_result("test", result)

    assert ctx.get_result("test") == result
    assert ctx.get_result("nonexistent") is None


def test_completeness_calculation():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    assert ctx.completeness == "empty"

    ctx.store_result("step1", StepResult(step="step1", success=True))
    ctx.store_result("step2", StepResult(step="step2", success=False))

    assert ctx.completeness == "partial"

    ctx.store_result("step3", StepResult(step="step3", success=True))
    ctx.store_result("step4", StepResult(step="step4", success=True))

    assert ctx.completeness == "partial"

    ctx.store_result("step2", StepResult(step="step2", success=True))

    assert ctx.completeness == "full"


def test_confidence_calculation():
    ctx = AnalysisContext(requirement_path=Path("test.md"))

    ctx.store_result("step1", StepResult(step="step1", success=True, confidence=1.0))
    ctx.store_result("step2", StepResult(step="step2", success=True, confidence=0.5))

    assert ctx.overall_confidence == 0.75
