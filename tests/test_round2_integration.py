import pytest

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker, DEFAULT_DIMENSIONS
from reqradar.agent.tools.security import PathSandbox, SensitiveFileFilter, ToolPermissionChecker, check_tool_permissions
from reqradar.agent.prompts.analysis_phase import build_analysis_system_prompt, build_analysis_user_prompt, build_termination_prompt
from reqradar.agent.prompts.report_phase import build_report_generation_prompt
from reqradar.infrastructure.template_loader import TemplateLoader


def test_agent_full_lifecycle():
    agent = AnalysisAgent(
        requirement_text="Implement SSO authentication",
        project_id=1,
        user_id=1,
        depth="standard",
    )
    assert agent.state == AgentState.INIT
    assert agent.step_count == 0

    agent.state = AgentState.ANALYZING
    agent.record_evidence(
        type="code",
        source="src/auth/sso.py",
        content="SSO implementation",
        confidence="high",
        dimensions=["impact", "change"],
    )
    agent.dimension_tracker.mark_in_progress("impact")
    agent.dimension_tracker.mark_sufficient("understanding")
    agent.step_count += 1

    assert agent.step_count == 1
    assert len(agent.evidence_collector.evidences) == 1
    assert agent.dimension_tracker.dimensions["impact"].status == "in_progress"
    assert agent.dimension_tracker.dimensions["understanding"].status == "sufficient"

    snapshot = agent.get_context_snapshot()
    assert len(snapshot["evidence_list"]) == 1
    assert snapshot["dimension_status"]["impact"]["status"] == "in_progress"

    agent2 = AnalysisAgent("test", project_id=1, user_id=1, depth="standard")
    agent2.restore_from_snapshot(snapshot)
    assert len(agent2.evidence_collector.evidences) == 1


def test_security_components():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert sandbox.is_allowed("/home/user/project/src/app.py")
    assert not sandbox.is_allowed("/etc/passwd")

    sf = SensitiveFileFilter()
    assert sf.is_sensitive(".env")
    assert not sf.is_sensitive("src/app.py")

    checker = ToolPermissionChecker(user_permissions={"read:code", "read:memory"})
    assert checker.is_allowed("read:code")
    assert not checker.is_allowed("write:report")


def test_prompt_builders():
    sys_prompt = build_analysis_system_prompt(
        project_memory="Project: ReqRadar\nLanguages: Python",
        user_memory="User prefers deep analysis",
        dimension_status={"understanding": "sufficient", "impact": "in_progress"},
    )
    assert "ReqRadar" in sys_prompt
    assert "understanding" in sys_prompt

    user_prompt = build_analysis_user_prompt("Add SSO support")
    assert "SSO" in user_prompt

    term_prompt = build_termination_prompt()
    assert "分析步数上限" in term_prompt or "达到" in term_prompt


def test_template_section_injection():
    loader = TemplateLoader()
    defn = loader.load_definition(loader.get_default_template_path())
    section_descs = [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "requirements": s.requirements,
            "dimensions": s.dimensions,
        }
        for s in defn.sections[:3]
    ]
    prompt = build_analysis_system_prompt(template_sections=section_descs)
    assert "需求理解" in prompt or "understanding" in prompt


def test_report_generation_prompt():
    prompt = build_report_generation_prompt(
        requirement_text="Add SSO",
        evidence_text="[ev-001] (code/high) src/auth.py: SSO module",
        dimension_status={"impact": "sufficient", "risk": "in_progress"},
    )
    assert "SSO" in prompt
    assert "impact" in prompt


def test_depth_step_limits():
    quick = AnalysisAgent("test", project_id=1, user_id=1, depth="quick")
    assert quick.max_steps == 10

    deep = AnalysisAgent("test", project_id=1, user_id=1, depth="deep")
    assert deep.max_steps == 25

    custom = AnalysisAgent("test", project_id=1, user_id=1, depth="standard", max_steps=20)
    assert custom.max_steps == 20


def test_dimension_tracker_default_dimensions():
    tracker = DimensionTracker()
    assert set(tracker.dimensions.keys()) == set(DEFAULT_DIMENSIONS)
    assert "understanding" in tracker.dimensions
    assert "evidence" in tracker.dimensions
