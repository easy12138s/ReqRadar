import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from reqradar.web.database import Base
from reqradar.web.models import PendingChange
from reqradar.modules.pending_changes import PendingChangeManager


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_pending_change(db_session):
    manager = PendingChangeManager(db_session)
    change = await manager.create(
        project_id=1,
        change_type="profile",
        target_id="module:auth",
        old_value="",
        new_value="### auth\nAuthentication module",
        diff="+ ### auth\n+ Authentication module",
        source="agent",
    )
    assert change.id is not None
    assert change.status == "pending"
    assert change.change_type == "profile"


@pytest.mark.asyncio
async def test_accept_pending_change(db_session):
    manager = PendingChangeManager(db_session)
    change = await manager.create(
        project_id=1,
        change_type="synonym",
        target_id="term:配置",
        old_value="",
        new_value='["config", "settings"]',
        diff="",
        source="agent",
    )
    accepted = await manager.accept(change.id, resolved_by=1)
    assert accepted.status == "accepted"
    assert accepted.resolved_by == 1


@pytest.mark.asyncio
async def test_reject_pending_change(db_session):
    manager = PendingChangeManager(db_session)
    change = await manager.create(
        project_id=1,
        change_type="profile",
        target_id="overview",
        old_value="Old overview",
        new_value="New overview",
        diff="+ New overview",
        source="agent",
    )
    rejected = await manager.reject(change.id, resolved_by=1)
    assert rejected.status == "rejected"


@pytest.mark.asyncio
async def test_list_pending_changes(db_session):
    manager = PendingChangeManager(db_session)
    await manager.create(
        project_id=1, change_type="profile", target_id="t1", old_value="", new_value="n1", diff="d1", source="agent"
    )
    await manager.create(
        project_id=1, change_type="synonym", target_id="t2", old_value="", new_value="n2", diff="d2", source="agent"
    )
    await manager.create(
        project_id=2, change_type="profile", target_id="t3", old_value="", new_value="n3", diff="d3", source="agent"
    )

    pending_1 = await manager.list_pending(project_id=1)
    assert len(pending_1) == 2

    pending_2 = await manager.list_pending(project_id=2)
    assert len(pending_2) == 1
