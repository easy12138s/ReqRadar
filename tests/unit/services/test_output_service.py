"""Output Service 集成测试 — 报告生成 / 状态查询 / 最新报告 / 模板重载 / 内容获取。"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from services.output.app import _task_store, app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _generate(client: TestClient, session_id: str | None = None, **kwargs) -> dict:
    payload = {"session_id": session_id or str(uuid.uuid4()), **kwargs}
    resp = client.post("/internal/v2/reports/generate", json=payload)
    assert resp.status_code == 202
    return resp.json()


def _generate_and_complete(client: TestClient, session_id: str | None = None, **kwargs) -> dict:
    data = _generate(client, session_id, **kwargs)
    task_id = data["task_id"]
    resp = client.get(f"/internal/v2/reports/{task_id}/status")
    assert resp.status_code == 200
    return resp.json()


class TestHealth:
    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "output"


class TestReportGeneration:
    def test_generate_returns_202(self, client: TestClient):
        resp = client.post(
            "/internal/v2/reports/generate",
            json={"session_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 202
        assert "task_id" in resp.json()

    def test_generate_response_fields(self, client: TestClient):
        data = _generate(client)
        assert "task_id" in data
        assert data["status"] == "queued"
        assert "estimated_duration_ms" in data
        assert isinstance(data["estimated_duration_ms"], int)

    def test_generate_with_format(self, client: TestClient):
        data = _generate(client, output_format="html")
        assert data["estimated_duration_ms"] == 8000

    def test_generate_with_template_id(self, client: TestClient):
        template_id = str(uuid.uuid4())
        data = _generate(client, template_id=template_id)
        assert "task_id" in data


class TestReportStatus:
    def test_status_queued(self, client: TestClient):
        data = _generate(client)
        task_id = data["task_id"]
        resp = client.get(f"/internal/v2/reports/{task_id}/status")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("queued", "running", "completed")

    def test_status_completed(self, client: TestClient):
        result = _generate_and_complete(client)
        assert result["status"] == "completed"

    def test_status_not_found(self, client: TestClient):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/internal/v2/reports/{fake_id}/status")
        assert resp.status_code == 404

    def test_status_completed_fields(self, client: TestClient):
        result = _generate_and_complete(client)
        assert "output_uri" in result
        assert "format" in result
        assert "size_bytes" in result
        assert "completed_at" in result


class TestLatestReport:
    def test_latest_no_report(self, client: TestClient):
        session_id = str(uuid.uuid4())
        resp = client.get(f"/internal/v2/reports/latest/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["reports"] == []

    def test_latest_after_generate(self, client: TestClient):
        session_id = str(uuid.uuid4())
        _generate_and_complete(client, session_id)
        resp = client.get(f"/internal/v2/reports/latest/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["output_uri"] is not None

    def test_latest_returns_most_recent(self, client: TestClient):
        session_id = str(uuid.uuid4())
        _generate_and_complete(client, session_id, output_format="markdown")
        _generate_and_complete(client, session_id, output_format="html")
        resp = client.get(f"/internal/v2/reports/latest/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "html"


class TestTemplateReload:
    def test_reload_templates(self, client: TestClient):
        resp = client.post("/internal/v2/reports/reload-templates")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_reload_returns_count(self, client: TestClient):
        resp = client.post("/internal/v2/reports/reload-templates")
        data = resp.json()
        assert "templates_loaded" in data
        assert isinstance(data["templates_loaded"], int)
        assert data["templates_loaded"] > 0


class TestReportContent:
    def test_content_after_complete(self, client: TestClient):
        session_id = str(uuid.uuid4())
        data = _generate(client, session_id)
        task_id = data["task_id"]
        _generate_and_complete(client, session_id)
        resp = client.get(f"/internal/v2/reports/{task_id}/content")
        assert resp.status_code == 200
        result = resp.json()
        assert result["task_id"] == task_id
        assert "content" in result
        assert len(result["content"]) > 0

    def test_content_not_ready(self, client: TestClient):
        from services.output.app import ReportTask

        task = ReportTask(
            task_id="pending-task",
            session_id="sess",
            status="running",
        )
        _task_store._tasks[task.task_id] = task
        resp = client.get(f"/internal/v2/reports/{task.task_id}/content")
        assert resp.status_code == 400
