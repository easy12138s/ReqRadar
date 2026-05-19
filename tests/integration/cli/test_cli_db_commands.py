import pytest
from click.testing import CliRunner
from sqlalchemy.ext.asyncio import async_sessionmaker

from reqradar.cli.main import cli
from reqradar.web.models import AnalysisTask
from tests.factories import build_analysis_task, build_project, build_report, build_report_version


@pytest.fixture
def cli_runner(monkeypatch, test_config, db_engine):
    import reqradar.cli.analyses as analyses_module
    import reqradar.cli.config as config_module
    import reqradar.cli.main as main_module
    import reqradar.cli.projects as projects_module
    import reqradar.cli.reports as reports_module

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(main_module, "load_config", lambda path=None: test_config)

    for module in (projects_module, analyses_module, reports_module, config_module):
        monkeypatch.setattr(module, "get_db_session", lambda config: (None, session_factory))

        async def fake_close_db(engine):
            return None

        monkeypatch.setattr(module, "close_db", fake_close_db)

    runner = CliRunner()
    runner.session_factory = session_factory
    runner.main = cli
    return runner


@pytest.fixture
async def cli_project(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="cli_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project.id


@pytest.fixture
async def cli_task(db_session, regular_user, cli_project):
    task = build_analysis_task(project_id=cli_project, user_id=regular_user.id, status="completed")
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task.id


def test_project_create_requires_exactly_one_source(cli_runner):
    result = cli_runner.invoke(cli, ["project", "create", "--name", "invalid"])

    assert result.exit_code == 1
    assert "必须且只能指定一种来源" in result.output


def test_project_list_show_and_delete(cli_runner, cli_project):
    list_result = cli_runner.invoke(cli, ["project", "list"])
    show_result = cli_runner.invoke(cli, ["project", "show", str(cli_project)])
    delete_result = cli_runner.invoke(cli, ["project", "delete", str(cli_project), "--force"])

    assert list_result.exit_code == 0
    assert "cli_project" in list_result.output
    assert show_result.exit_code == 0
    assert "cli_project" in show_result.output
    assert delete_result.exit_code == 0
    assert "已删除" in delete_result.output


def test_analyze_submit_requires_text_or_file(cli_runner, cli_project):
    result = cli_runner.invoke(cli, ["analyze", "submit", "--project-id", str(cli_project)])

    assert result.exit_code == 1
    assert "必须指定 --text 或 --file" in result.output


def test_analyze_list_status_and_cancel(cli_runner, cli_task):
    list_result = cli_runner.invoke(cli, ["analyze", "list"])
    status_result = cli_runner.invoke(cli, ["analyze", "status", str(cli_task)])
    cancel_result = cli_runner.invoke(cli, ["analyze", "cancel", str(cli_task)])

    assert list_result.exit_code == 0
    assert "Requirement" in list_result.output
    assert status_result.exit_code == 0
    assert "Requirement" in status_result.output
    assert cancel_result.exit_code == 1
    assert "无法取消状态为" in cancel_result.output


def test_report_get_versions_and_evidence_sync(cli_runner, cli_task):
    import asyncio

    async def seed():
        async with cli_runner.session_factory() as session:
            report = build_report(cli_task, content_markdown="# CLI Report")
            version = build_report_version(
                cli_task,
                1,
                context_snapshot={
                    "evidence_list": [
                        {
                            "id": "ev-1",
                            "type": "code",
                            "source": "app.py",
                            "confidence": "0.9",
                            "dimensions": ["scope"],
                            "content": "evidence",
                        }
                    ]
                },
            )
            task = await session.get(AnalysisTask, cli_task)
            task.current_version = 1
            session.add_all([report, version])
            await session.commit()

    asyncio.run(seed())

    get_result = cli_runner.invoke(cli, ["report", "get", str(cli_task)])
    versions_result = cli_runner.invoke(cli, ["report", "versions", str(cli_task)])
    evidence_result = cli_runner.invoke(cli, ["report", "evidence", str(cli_task)])

    assert get_result.exit_code == 0
    assert "CLI Report" in get_result.output
    assert versions_result.exit_code == 0
    assert "v1" in versions_result.output
    assert evidence_result.exit_code == 0
    assert "ev-1" in evidence_result.output


def test_config_set_get_list_and_delete(cli_runner):
    set_result = cli_runner.invoke(cli, ["config", "set", "llm.model", "test-model"])
    get_result = cli_runner.invoke(cli, ["config", "get", "llm.model"])
    list_result = cli_runner.invoke(cli, ["config", "list", "--scope", "user"])
    delete_result = cli_runner.invoke(cli, ["config", "delete", "llm.model"])

    assert set_result.exit_code == 0
    assert get_result.exit_code == 0
    assert "test-model" in get_result.output
    assert list_result.exit_code == 0
    assert "llm.model" in list_result.output
    assert delete_result.exit_code == 0
