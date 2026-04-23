import pytest
from unittest.mock import AsyncMock, MagicMock

from reqradar.web.services.chatback_service import ChatbackService, classify_intent


def test_classify_intent_explain():
    assert classify_intent("为什么风险评估是中而不是高？") == "explain"
    assert classify_intent("这个风险是怎么得出的") == "explain"


def test_classify_intent_correct():
    assert classify_intent("影响模块遗漏了 web/models.py，需要补充") == "correct"
    assert classify_intent("这里写错了，应该是高不是中") == "correct"


def test_classify_intent_deepen():
    assert classify_intent("请详细分析对数据库的影响") == "deepen"
    assert classify_intent("能展开讲讲性能风险的细节吗") == "deepen"


def test_classify_intent_explore():
    assert classify_intent("去看看 web/app.py 的变更历史") == "explore"
    assert classify_intent("查看一下 auth 模块") == "explore"


def test_classify_intent_other():
    assert classify_intent("谢谢") == "other"
    assert classify_intent("测试消息") == "other"


def test_chatback_service_fallback_reply():
    service = ChatbackService(version_service=AsyncMock())
    reply = service._generate_fallback_reply(
        report_data={"risk_level": "high", "requirement_title": "Add SSO"},
        context_snapshot={
            "evidence_list": [{"id": "ev-001", "type": "code", "source": "src/auth.py", "content": "Auth module", "confidence": "high", "dimensions": ["impact"]}],
            "dimension_status": {"impact": "sufficient"},
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
        context_snapshot={"evidence_list": [], "dimension_status": {}, "visited_files": [], "tool_calls": []},
        user_message="遗漏了 xx 模块",
        intent="correct",
    )
    assert "纠正" in reply or "修改" in reply or "版本" in reply


def test_chatback_service_fallback_explore():
    service = ChatbackService(version_service=AsyncMock())
    reply = service._generate_fallback_reply(
        report_data={"risk_level": "low"},
        context_snapshot={"evidence_list": [], "dimension_status": {}, "visited_files": ["src/app.py", "src/models.py"], "tool_calls": []},
        user_message="去看看 auth",
        intent="explore",
    )
    assert "src/app.py" in reply or "文件" in reply
