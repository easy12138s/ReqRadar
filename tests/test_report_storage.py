import pytest
import json
from pathlib import Path
from reqradar.web.services.report_storage import ReportStorage


@pytest.fixture
def storage(tmp_path):
    return ReportStorage(tmp_path / "reports")


@pytest.mark.asyncio
async def test_save_and_read_report(storage):
    rel_md, rel_html = await storage.save_report(1, "# Report", "<h1>Report</h1>")
    assert rel_md == "1/report.md"
    assert rel_html == "1/report.html"
    md, html = await storage.read_report(1)
    assert md == "# Report"
    assert html == "<h1>Report</h1>"


@pytest.mark.asyncio
async def test_save_and_read_version(storage):
    rel_md, rel_html = await storage.save_version(1, 2, "# V2", "<h1>V2</h1>")
    assert rel_md == "1/versions/v2.md"
    md, html = await storage.read_version(1, 2)
    assert md == "# V2"
    assert html == "<h1>V2</h1>"


@pytest.mark.asyncio
async def test_read_nonexistent_returns_none(storage):
    md, html = await storage.read_report(999)
    assert md is None
    assert html is None


@pytest.mark.asyncio
async def test_delete_task_reports(storage):
    await storage.save_report(5, "md", "html")
    assert (storage._root / "5" / "report.md").exists()
    await storage.delete_task_reports(5)
    assert not (storage._root / "5").exists()


@pytest.mark.asyncio
async def test_delete_version_files(storage):
    await storage.save_version(5, 1, "v1md", "v1html")
    await storage.save_version(5, 2, "v2md", "v2html")
    await storage.delete_version_files(5, 1)
    md, html = await storage.read_version(5, 1)
    assert md is None
    md, html = await storage.read_version(5, 2)
    assert md == "v2md"


@pytest.mark.asyncio
async def test_save_report_with_context(storage):
    await storage.save_report(10, "md", "html", context={"risk_level": "high"})
    ctx_path = storage._root / "10" / "context.json"
    assert ctx_path.exists()
    data = json.loads(ctx_path.read_text())
    assert data["risk_level"] == "high"


@pytest.mark.asyncio
async def test_atomic_write(storage):
    large_md = "x" * 100000
    await storage.save_report(20, large_md, "html")
    md, _ = await storage.read_report(20)
    assert md == large_md
