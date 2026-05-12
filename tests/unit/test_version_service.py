import pytest

from reqradar.web.models import ReportVersion
from reqradar.web.services.version_service import VersionService
from tests.factories import build_analysis_task, build_project


@pytest.fixture
async def task(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="version_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    task = build_analysis_task(project_id=project.id, user_id=regular_user.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest.mark.asyncio
async def test_create_version_increments_version_number_and_updates_task(db_session, task):
    service = VersionService(db_session)

    first = await service.create_version(task.id, {"summary": "v1"}, {}, "# V1", "<h1>V1</h1>")
    second = await service.create_version(task.id, {"summary": "v2"}, {}, "# V2", "<h1>V2</h1>")

    assert first.version_number == 1
    assert second.version_number == 2
    assert task.current_version == 2


@pytest.mark.asyncio
async def test_list_versions_orders_newest_first(db_session, task):
    service = VersionService(db_session)
    await service.create_version(task.id, {"summary": "v1"}, {}, "# V1", "<h1>V1</h1>")
    await service.create_version(task.id, {"summary": "v2"}, {}, "# V2", "<h1>V2</h1>")

    versions = await service.list_versions(task.id)

    assert [version.version_number for version in versions] == [2, 1]


@pytest.mark.asyncio
async def test_get_current_version_returns_none_without_task_or_current_version(db_session):
    service = VersionService(db_session)

    assert await service.get_current_version(999) is None


@pytest.mark.asyncio
async def test_rollback_creates_new_version_from_target(db_session, task):
    service = VersionService(db_session)
    await service.create_version(task.id, {"summary": "v1"}, {"ctx": 1}, "# V1", "<h1>V1</h1>")
    await service.create_version(task.id, {"summary": "v2"}, {"ctx": 2}, "# V2", "<h1>V2</h1>")

    rollback = await service.rollback(task.id, 1, task.user_id)

    assert rollback is not None
    assert rollback.version_number == 3
    assert rollback.trigger_type == "rollback"
    assert rollback.content_markdown == "# V1"


@pytest.mark.asyncio
async def test_enforce_version_limit_removes_oldest_versions(db_session, task):
    service = VersionService(db_session, version_limit=2)
    await service.create_version(task.id, {"summary": "v1"}, {}, "# V1", "<h1>V1</h1>")
    await service.create_version(task.id, {"summary": "v2"}, {}, "# V2", "<h1>V2</h1>")
    await service.create_version(task.id, {"summary": "v3"}, {}, "# V3", "<h1>V3</h1>")

    versions = await service.list_versions(task.id)

    assert [version.version_number for version in versions] == [3, 2]


@pytest.mark.asyncio
async def test_get_context_snapshot_handles_missing_and_non_dict_snapshot(db_session, task):
    service = VersionService(db_session)
    version = ReportVersion(
        task_id=task.id,
        version_number=1,
        report_data={},
        context_snapshot=["unexpected"],
        content_markdown="# V1",
        content_html="<h1>V1</h1>",
        created_by=task.user_id,
    )
    db_session.add(version)
    await db_session.commit()

    assert await service.get_context_snapshot(task.id, 2) is None
    assert await service.get_context_snapshot(task.id, 1) == {}
