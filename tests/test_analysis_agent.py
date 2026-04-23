import importlib
import sys
import pytest

_analysis_agent_mod = importlib.import_module("reqradar.agent.analysis_agent")
AnalysisAgent = _analysis_agent_mod.AnalysisAgent
AgentState = _analysis_agent_mod.AgentState

_evidence_mod = importlib.import_module("reqradar.agent.evidence")
EvidenceCollector = _evidence_mod.EvidenceCollector

_dimension_mod = importlib.import_module("reqradar.agent.dimension")
DimensionTracker = _dimension_mod.DimensionTracker


def test_agent_initial_state():
    agent = AnalysisAgent(
        requirement_text="Add user authentication",
        project_id=1,
        user_id=1,
        depth="standard",
        max_steps=15,
    )
    assert agent.state == AgentState.INIT
    assert agent.step_count == 0
    assert agent.max_steps == 15
    assert agent.dimension_tracker is not None
    assert agent.evidence_collector is not None


def test_agent_depth_mapping():
    agent_quick = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    assert agent_quick.max_steps == 10

    agent_standard = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    assert agent_standard.max_steps == 15

    agent_deep = AnalysisAgent("test", project_id=1, user_id=1, depth="deep")
    assert agent_deep.max_steps == 25


def test_agent_should_terminate_max_steps():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    agent.step_count = 10
    assert agent.should_terminate()


def test_agent_should_not_terminate_under_limit():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent.step_count = 5
    assert not agent.should_terminate()


def test_agent_should_terminate_all_dimensions_sufficient():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    for dim_id in agent.dimension_tracker.dimensions:
        agent.dimension_tracker.mark_sufficient(dim_id)
    assert agent.should_terminate()


def test_agent_record_evidence():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    ev_id = agent.record_evidence(
        type="code",
        source="src/app.py:10",
        content="Main application entry point",
        confidence="high",
        dimensions=["impact"],
    )
    assert ev_id is not None
    assert len(agent.evidence_collector.evidences) == 1


def test_agent_get_context_text():
    agent = AnalysisAgent("Add SSO support", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="src/auth.py", content="Auth module", confidence="high", dimensions=["impact"])
    context = agent.get_context_text()
    assert "Auth module" in context


def test_agent_state_transitions():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    assert agent.state == AgentState.INIT

    agent.state = AgentState.ANALYZING
    assert agent.state == AgentState.ANALYZING

    agent.state = AgentState.GENERATING
    assert agent.state == AgentState.GENERATING

    agent.state = AgentState.COMPLETED
    assert agent.state == AgentState.COMPLETED


def test_agent_lightweight_context_snapshot():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    agent.dimension_tracker.mark_in_progress("impact")

    snapshot = agent.get_context_snapshot()
    assert "evidence_list" in snapshot
    assert "dimension_status" in snapshot
    assert "visited_files" in snapshot
    assert "tool_calls" in snapshot
    assert len(snapshot["evidence_list"]) == 1
    assert snapshot["dimension_status"]["impact"]["status"] == "in_progress"


def test_agent_restore_from_snapshot():
    agent = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="f1", content="c1", confidence="high", dimensions=["impact"])
    agent.dimension_tracker.mark_in_progress("impact")

    snapshot = agent.get_context_snapshot()

    agent2 = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent2.restore_from_snapshot(snapshot)
    assert len(agent2.evidence_collector.evidences) == 1
    assert agent2.dimension_tracker.dimensions["impact"].status == "in_progress"
