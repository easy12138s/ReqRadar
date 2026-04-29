"""CLI 项目管理命令测试"""

import asyncio
import os

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from reqradar.cli.main import cli
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.enums import TaskStatus
from reqradar.web.models import AnalysisTask, Project, Report, ReportVersion, User


@pytest.fixture
def db_url(tmp_path):
    db_file = tmp_path / "test_cli.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest.fixture
def runner(db_url, monkeypatch, tmp_path):
    from reqradar.infrastructure import config as config_mod
    from reqradar.cli import main as cli_main

    engine = create_engine(db_url)

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = create_session_factory(engine)
        async with session_factory() as s:
            s.add(
                User(
                    id=1,
                    email="cli@test.com",
                    password_hash="test",
                    display_name="CLI",
                    role="admin",
                )
            )
            await s.commit()
        await engine.dispose()

    asyncio.run(init_db())

    original_load = config_mod.load_config

    def mock_config(path=None):
        cfg = original_load(path)
        cfg.web.database_url = db_url
        data_root = str(tmp_path / "data")
        os.makedirs(data_root, exist_ok=True)
        cfg.web.data_root = data_root
        return cfg

    monkeypatch.setattr(config_mod, "load_config", mock_config)
    monkeypatch.setattr(cli_main, "load_config", mock_config)

    return CliRunner()


class TestProjectCreate:
    def test_create_from_local(self, runner, tmp_path, db_url):
        code_dir = tmp_path / "test_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("print('hello')")

        result = runner.invoke(
            cli,
            ["project", "create", "--name", "test-proj", "--local-path", str(code_dir)],
        )
        assert result.exit_code == 0
        assert "创建成功" in result.output

    def test_create_no_source(self, runner):
        result = runner.invoke(
            cli,
            ["project", "create", "--name", "no-source"],
        )
        assert result.exit_code != 0


class TestProjectList:
    def test_list_empty(self, runner):
        result = runner.invoke(cli, ["project", "list"])
        assert result.exit_code == 0
        assert "暂无项目" in result.output

    def test_list_with_projects(self, runner, tmp_path, db_url):
        code_dir = tmp_path / "test_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("print('hello')")

        runner.invoke(cli, ["project", "create", "--name", "proj-a", "--local-path", str(code_dir)])
        runner.invoke(cli, ["project", "create", "--name", "proj-b", "--local-path", str(code_dir)])

        result = runner.invoke(cli, ["project", "list"])
        assert result.exit_code == 0
        assert "proj-a" in result.output
        assert "proj-b" in result.output


class TestProjectShow:
    def test_show_not_found(self, runner):
        result = runner.invoke(cli, ["project", "show", "999"])
        assert result.exit_code != 0

    def test_show_existing(self, runner, tmp_path, db_url):
        code_dir = tmp_path / "test_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("def hello(): pass")

        runner.invoke(
            cli,
            ["project", "create", "--name", "show-proj", "--local-path", str(code_dir)],
        )

        result = runner.invoke(cli, ["project", "show", "1"])
        assert result.exit_code == 0
        assert "show-proj" in result.output


class TestProjectDelete:
    def test_delete_not_found(self, runner):
        result = runner.invoke(cli, ["project", "delete", "999", "--force"])
        assert result.exit_code != 0

    def test_delete_force(self, runner, tmp_path, db_url):
        code_dir = tmp_path / "test_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("def hello(): pass")

        runner.invoke(
            cli,
            ["project", "create", "--name", "del-force", "--local-path", str(code_dir)],
        )

        result = runner.invoke(cli, ["project", "delete", "1", "--force"])
        assert result.exit_code == 0
        assert "已删除" in result.output


class TestAnalyzeSubmit:
    def test_submit_no_source(self, runner):
        result = runner.invoke(cli, ["analyze", "submit", "-p", "1"])
        assert result.exit_code != 0

    def test_submit_project_not_found(self, runner):
        result = runner.invoke(
            cli,
            ["analyze", "submit", "-p", "999", "-t", "test"],
        )
        assert result.exit_code != 0


class TestAnalyzeList:
    def test_list_empty(self, runner):
        result = runner.invoke(cli, ["analyze", "list"])
        assert result.exit_code == 0
        assert "暂无分析任务" in result.output


class TestAnalyzeStatus:
    def test_status_not_found(self, runner):
        result = runner.invoke(cli, ["analyze", "status", "999"])
        assert result.exit_code != 0


class TestReportGet:
    def test_get_not_found(self, runner):
        result = runner.invoke(cli, ["report", "get", "999"])
        assert result.exit_code != 0


class TestReportVersions:
    def test_versions_not_found(self, runner):
        result = runner.invoke(cli, ["report", "versions", "999"])
        assert result.exit_code != 0


class TestReportEvidence:
    def test_evidence_not_found(self, runner):
        result = runner.invoke(cli, ["report", "evidence", "999"])
        assert result.exit_code != 0


class TestFullWorkflow:
    def test_create_submit_and_list(self, runner, tmp_path, db_url):
        code_dir = tmp_path / "test_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("def hello(): pass")

        runner.invoke(
            cli,
            ["project", "create", "--name", "workflow-proj", "--local-path", str(code_dir)],
        )

        result = runner.invoke(
            cli,
            ["analyze", "submit", "-p", "1", "-t", "Add user login", "-n", "login-req"],
        )
        assert result.exit_code == 0
        assert "已提交" in result.output

        result = runner.invoke(cli, ["analyze", "list"])
        assert result.exit_code == 0
        assert "login-req" in result.output

    def test_cancel_pending_task(self, runner, tmp_path, db_url):
        code_dir = tmp_path / "test_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("def hello(): pass")

        runner.invoke(
            cli,
            ["project", "create", "--name", "cancel-proj", "--local-path", str(code_dir)],
        )
        runner.invoke(
            cli,
            ["analyze", "submit", "-p", "1", "-t", "Test", "-n", "cancel-test"],
        )

        result = runner.invoke(cli, ["analyze", "cancel", "1"])
        assert result.exit_code == 0
        assert "已取消" in result.output

    def test_report_pending_task(self, runner, tmp_path, db_url):
        code_dir = tmp_path / "test_code"
        code_dir.mkdir()
        (code_dir / "main.py").write_text("def hello(): pass")

        runner.invoke(
            cli,
            ["project", "create", "--name", "report-proj", "--local-path", str(code_dir)],
        )
        runner.invoke(
            cli,
            ["analyze", "submit", "-p", "1", "-t", "Test", "-n", "pending-test"],
        )

        result = runner.invoke(cli, ["report", "get", "1"])
        assert result.exit_code != 0
        assert "尚未生成报告" in result.output
