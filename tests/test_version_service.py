from reqradar.web.models import ReportVersion, ReportChat


def test_report_version_model():
    version = ReportVersion(
        task_id=1,
        version_number=1,
        report_data='{"risk_level": "medium"}',
        context_snapshot='{"evidence_list": [], "dimension_status": {}, "visited_files": [], "tool_calls": []}',
        content_markdown="# Report",
        content_html="<h1>Report</h1>",
        trigger_type="initial",
        created_by=1,
    )
    assert version.version_number == 1
    assert version.trigger_type == "initial"


def test_report_chat_model():
    chat = ReportChat(
        task_id=1,
        version_number=1,
        role="user",
        content="Why is the risk medium?",
        evidence_refs="[]",
        intent_type="explain",
    )
    assert chat.role == "user"
    assert chat.intent_type == "explain"
