"""E2E 测试 — 报告版本管理流程 (mock-mode)"""

import pytest
from sqlalchemy import select

from reqradar.web.enums import TaskStatus
from reqradar.web.models import AnalysisTask, Report, ReportVersion

pytestmark = [pytest.mark.e2e]


@pytest.fixture
async def task_with_report(e2e_project, e2e_session_factory):
    """创建带有报告和版本的分析任务。"""
    client, headers, token, user_data, user_id, project_id = e2e_project

    async with e2e_session_factory() as db:
        task = AnalysisTask(
            project_id=project_id,
            user_id=user_id,
            requirement_name="E2E-版本测试",
            requirement_text="需求文本",
            depth="quick",
            status=TaskStatus.COMPLETED,
            context_json={"risk_level": "low"},
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        report = Report(
            task_id=task.id,
            content_markdown="# Version 1 Report\n\n分析结果",
            content_html="<h1>Version 1 Report</h1>",
            markdown_path="",
            html_path="",
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

        version = ReportVersion(
            task_id=task.id,
            version_number=1,
            report_data={"summary": "版本1报告"},
            context_snapshot={"created_at": "2026-01-01"},
            content_markdown="# Version 1 Report",
            content_html="<h1>Version 1 Report</h1>",
            trigger_type="initial",
            trigger_description="Initial report",
            created_by=user_id,
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)

        task_id = task.id

    yield (client, headers, token, user_data, user_id, project_id, task_id)


class TestReportVersioning:
    """报告版本管理。"""

    async def test_get_report(self, task_with_report):
        """获取报告。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.get(f"/api/reports/{task_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task_id
        assert "content_markdown" in data

    async def test_get_report_markdown(self, task_with_report):
        """获取报告 Markdown 格式。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.get(f"/api/reports/{task_id}/markdown", headers=headers)
        assert resp.status_code == 200
        assert "Version 1 Report" in resp.text

    async def test_get_report_html(self, task_with_report):
        """获取报告 HTML 格式。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.get(f"/api/reports/{task_id}/html", headers=headers)
        assert resp.status_code == 200
        assert "Version 1 Report" in resp.text

    async def test_get_report_not_found(self, e2e_client, e2e_user):
        """不存在的任务报告应返回 404。"""
        client, headers, *_ = e2e_user
        resp = await client.get("/api/reports/999999", headers=headers)
        assert resp.status_code == 404

    async def test_list_versions(self, task_with_report):
        """获取版本列表。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.get(f"/api/analyses/{task_id}/reports/versions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        versions = data["versions"]
        assert len(versions) >= 1
        assert versions[0]["version_number"] == 1

    async def test_get_specific_version(self, task_with_report):
        """获取特定版本。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.get(f"/api/analyses/{task_id}/reports/versions/1", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["version_number"] == 1
        assert "content_markdown" in data
        assert "content_html" in data

    async def test_version_not_found(self, task_with_report):
        """不存在的版本号应返回 404。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.get(f"/api/analyses/{task_id}/reports/versions/999", headers=headers)
        assert resp.status_code == 404

    async def test_nonexistent_task_versions(self, e2e_client, e2e_user):
        """不存在的任务应返回 404。"""
        client, headers, *_ = e2e_user
        resp = await client.get("/api/analyses/999999/reports/versions", headers=headers)
        assert resp.status_code == 404

    async def test_rollback_to_version(self, task_with_report):
        """回滚到指定版本。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.post(
            f"/api/analyses/{task_id}/reports/rollback",
            headers=headers,
            json={"version_number": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["current_version"] >= 1

    async def test_rollback_nonexistent_version(self, task_with_report):
        """回滚到不存在的版本应返回 404。"""
        client, headers, *_, task_id = task_with_report
        resp = await client.post(
            f"/api/analyses/{task_id}/reports/rollback",
            headers=headers,
            json={"version_number": 999},
        )
        assert resp.status_code == 404

    async def test_rollback_nonexistent_task(self, e2e_client, e2e_user):
        """不存在的任务回滚应返回 404。"""
        client, headers, *_ = e2e_user
        resp = await client.post(
            "/api/analyses/999999/reports/rollback",
            headers=headers,
            json={"version_number": 1},
        )
        assert resp.status_code == 404

    async def test_report_requires_auth(self, e2e_client, e2e_user):
        """报告端点需要认证。"""
        resp = await e2e_client.get("/api/reports/1")
        assert resp.status_code == 401

    async def test_versions_require_auth(self, e2e_client):
        """版本端点需要认证。"""
        resp = await e2e_client.get("/api/analyses/1/reports/versions")
        assert resp.status_code == 401
