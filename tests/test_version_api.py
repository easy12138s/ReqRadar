import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory

TEST_SECRET_KEY = "test-secret-key-versions"


@pytest_asyncio.fixture
async def setup_db(tmp_path):
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module
    import reqradar.infrastructure.config as config_module

    original_secret = auth_module.SECRET_KEY
    original_expire = auth_module.ACCESS_TOKEN_EXPIRE_MINUTES
    original_factory = dep_module.async_session_factory
    original_config = config_module.load_config

    data_root = str(tmp_path / "data")
    db_path = tmp_path / "test_reqradar_versions.db"
    test_database_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_engine(test_database_url)
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = TEST_SECRET_KEY
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = 1440

    home_dir = str(tmp_path / "home")

    def _test_config(path=None):
        c = original_config(path)
        c.home.path = home_dir
        c.web.auto_create_tables = True
        c.web.debug = True
        c.web.database_url = test_database_url
        c.web.data_root = data_root
        return c

    config_module.load_config = _test_config

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    dep_module.async_session_factory = original_factory
    auth_module.SECRET_KEY = original_secret
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire
    config_module.load_config = original_config


@pytest_asyncio.fixture
async def auth_client(setup_db, tmp_path):
    app = create_app()

    from reqradar.infrastructure.paths import get_paths
    from reqradar.web.services.report_storage import ReportStorage

    import reqradar.infrastructure.config as config_module

    config = config_module.load_config()
    paths = get_paths(config)
    report_storage = ReportStorage(paths["reports"])
    app.state.paths = paths
    app.state.report_storage = report_storage

    local_path = str(tmp_path / "source")
    os.makedirs(local_path, exist_ok=True)
    with open(os.path.join(local_path, "main.py"), "w") as f:
        f.write("print('hello')")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={
                "email": "versions@example.com",
                "password": "Secret123",
                "display_name": "Versions User",
            },
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "versions@example.com", "password": "Secret123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        proj_resp = await client.post(
            "/api/projects/from-local",
            json={"name": "Versions-Project", "description": "test", "local_path": local_path},
            headers=headers,
        )
        project_id = proj_resp.json()["id"]

        from reqradar.web.models import AnalysisTask, Project, TaskStatus, User

        async with setup_db() as session:
            user_result = await session.execute(
                select(User).where(User.email == "versions@example.com")
            )
            user = user_result.scalar_one()
            task = AnalysisTask(
                project_id=project_id,
                user_id=user.id,
                requirement_name="Test Requirement",
                requirement_text="Test requirement text",
                status=TaskStatus.COMPLETED,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        yield client, headers, project_id, task_id


@pytest.mark.asyncio
async def test_list_versions_empty(auth_client):
    client, headers, project_id, task_id = auth_client
    response = await client.get(
        f"/api/analyses/{task_id}/reports/versions",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "versions" in data


@pytest.mark.asyncio
async def test_get_version_not_found(auth_client):
    client, headers, project_id, task_id = auth_client
    response = await client.get(
        "/api/analyses/999/reports/versions/1",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_version_not_found(auth_client):
    client, headers, project_id, task_id = auth_client
    response = await client.post(
        "/api/analyses/999/reports/rollback",
        json={"version_number": 1},
        headers=headers,
    )
    assert response.status_code == 404
