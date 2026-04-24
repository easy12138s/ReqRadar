import pytest
from unittest.mock import AsyncMock

from reqradar.web.services.version_service import VersionService, VERSION_LIMIT_DEFAULT
from reqradar.web.services.chatback_service import ChatbackService, classify_intent


def test_classify_intent_all_types():
    assert classify_intent("为什么风险评估是中？") == "explain"
    assert classify_intent("影响模块遗漏了 xxx") == "correct"
    assert classify_intent("请详细分析数据库影响") == "deepen"
    assert classify_intent("去看看 auth 模块") == "explore"
    assert classify_intent("谢谢") == "other"
    assert classify_intent("能不能解释一下风险？") == "explain"


def test_version_service_version_limit():
    assert VERSION_LIMIT_DEFAULT == 10


def test_chatback_service_fallback_reply():
    service = ChatbackService(version_service=AsyncMock())
    reply = service._generate_fallback_reply(
        report_data={"risk_level": "high", "requirement_title": "Add SSO"},
        context_snapshot={
            "evidence_list": [
                {
                    "id": "ev-001",
                    "type": "code",
                    "source": "src/auth.py",
                    "content": "Auth module",
                    "confidence": "high",
                    "dimensions": ["impact"],
                }
            ],
            "dimension_status": {"impact": {"status": "sufficient", "evidence_ids": ["ev-001"]}},
            "visited_files": ["src/auth.py"],
            "tool_calls": [],
        },
        user_message="为什么风险是高？",
        intent="explain",
    )
    assert "high" in reply or "高风险" in reply or "风险" in reply


def test_chatback_service_fallback_correct():
    service = ChatbackService(version_service=AsyncMock())
    reply = service._generate_fallback_reply(
        report_data={"risk_level": "medium"},
        context_snapshot={
            "evidence_list": [],
            "dimension_status": {},
            "visited_files": [],
            "tool_calls": [],
        },
        user_message="遗漏了 xx 模块",
        intent="correct",
    )
    assert "纠正" in reply or "修改" in reply or "版本" in reply


def test_chatback_service_fallback_explore():
    service = ChatbackService(version_service=AsyncMock())
    reply = service._generate_fallback_reply(
        report_data={"risk_level": "low"},
        context_snapshot={
            "evidence_list": [],
            "dimension_status": {},
            "visited_files": ["src/app.py", "src/models.py"],
            "tool_calls": [],
        },
        user_message="去看看 auth",
        intent="explore",
    )
    assert "src/app.py" in reply or "文件" in reply


def test_agent_snapshot_roundtrip():
    from reqradar.agent.analysis_agent import AnalysisAgent, AgentState

    agent = AnalysisAgent(
        "Test requirement", project_id=1, user_id=1, depth="standard"
    )
    agent.record_evidence(
        type="code",
        source="src/main.py:50",
        content="Main entry point",
        confidence="high",
        dimensions=["impact", "understanding"],
    )
    agent.dimension_tracker.mark_sufficient("understanding")
    agent.step_count = 3

    snapshot = agent.get_context_snapshot()

    assert len(snapshot["evidence_list"]) == 1
    assert snapshot["dimension_status"]["understanding"]["status"] == "sufficient"
    assert snapshot["step_count"] == 3
    assert "src/main.py" in snapshot["visited_files"]

    agent2 = AnalysisAgent(
        "Test requirement", project_id=1, user_id=1, depth="standard"
    )
    agent2.restore_from_snapshot(snapshot)

    assert len(agent2.evidence_collector.evidences) == 1
    assert agent2.dimension_tracker.dimensions["understanding"].status == "sufficient"
    assert agent2.step_count == 3
    assert "src/main.py" in agent2.visited_files
