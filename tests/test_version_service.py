from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock

from reqradar.web.models import ReportVersion, ReportChat
from reqradar.web.services.version_service import VersionService


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


def test_version_service_accepts_report_storage():
    report_storage = MagicMock()
    db = MagicMock()
    svc = VersionService(db, report_storage=report_storage)
    assert svc.report_storage is report_storage


def test_version_service_report_storage_defaults_none():
    db = MagicMock()
    svc = VersionService(db)
    assert svc.report_storage is None


@pytest.mark.asyncio
async def test_version_service_create_version_calls_save(tmp_path):
    from reqradar.web.services.report_storage import ReportStorage

    storage = ReportStorage(tmp_path / "reports")
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    max_version_result = MagicMock()
    max_version_result.scalar.return_value = None

    count_result = MagicMock()
    count_result.scalar.return_value = 0

    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(side_effect=[max_version_result, count_result, task_result])

    svc = VersionService(db, report_storage=storage)

    version = ReportVersion(
        task_id=1,
        version_number=1,
        markdown_path="1/versions/v1.md",
        html_path="1/versions/v1.html",
    )
    db.refresh.return_value = version

    await svc.create_version(
        task_id=1,
        report_data={"risk_level": "high"},
        context_snapshot={},
        content_markdown="# V1",
        content_html="<h1>V1</h1>",
    )

    md, html = await storage.read_version(1, 1)
    assert md == "# V1"
    assert html == "<h1>V1</h1>"


@pytest.mark.asyncio
async def test_version_service_enforce_limit_deletes_files(tmp_path):
    from reqradar.web.services.report_storage import ReportStorage

    storage = ReportStorage(tmp_path / "reports")
    db = AsyncMock()

    count_result = MagicMock()
    count_result.scalar.return_value = 3
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = None

    old_v1 = MagicMock()
    old_v1.version_number = 1
    old_v1.task_id = 10
    old_v1.markdown_path = "10/versions/v1.md"
    old_v1.html_path = "10/versions/v1.html"

    old_v2 = MagicMock()
    old_v2.version_number = 2
    old_v2.task_id = 10
    old_v2.markdown_path = "10/versions/v2.md"
    old_v2.html_path = "10/versions/v2.html"

    oldest_result = MagicMock()
    oldest_result.scalars.return_value.all.return_value = [old_v1, old_v2]

    db.execute.side_effect = [count_result, oldest_result, task_result]
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    await storage.save_version(10, 1, "# V1", "<h1>V1</h1>")
    await storage.save_version(10, 2, "# V2", "<h1>V2</h1>")
    await storage.save_version(10, 3, "# V3", "<h1>V3</h1>")

    svc = VersionService(db, report_storage=storage, version_limit=1)
    await svc._enforce_version_limit(10)

    assert await storage.read_version(10, 1) == (None, None)
    assert await storage.read_version(10, 2) == (None, None)
    v3_md, v3_html = await storage.read_version(10, 3)
    assert v3_md == "# V3"
