import pytest
from reqradar.agent.analysis_agent import AnalysisAgent


def test_runner_v2_initialization():
    from reqradar.web.services.analysis_runner_v2 import AnalysisRunnerV2
    runner = AnalysisRunnerV2()
    assert runner is not None


def test_build_report_data_from_agent():
    from reqradar.web.services.analysis_runner_v2 import build_report_data_from_agent
    agent = AnalysisAgent(
        requirement_text="Add SSO support",
        project_id=1,
        user_id=1,
        depth="standard",
    )
    agent.record_evidence(type="code", source="src/auth.py", content="Auth module", confidence="high", dimensions=["impact", "change"])
    agent.dimension_tracker.mark_sufficient("understanding")
    agent.dimension_tracker.mark_sufficient("impact")
    report_data = build_report_data_from_agent(agent, {})
    assert report_data is not None
    assert "requirement_title" in report_data
    assert "evidence_items" in report_data


def test_build_fallback_report_data():
    from reqradar.web.services.analysis_runner_v2 import _build_fallback_report_data
    agent = AnalysisAgent("Test requirement", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="src/main.py", content="Main entry", confidence="high", dimensions=["impact"])
    result = _build_fallback_report_data(agent)
    assert result["requirement_title"] == "Test requirement"
    assert result["risk_level"] == "unknown"
    assert len(result["evidence_items"]) == 1
