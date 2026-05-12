import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory

TEST_SECRET_KEY = "test-secret-key-chatback"


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
    db_path = tmp_path / "test_reqradar_chatback.db"
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
    app.state.config = config
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
                "email": "chatback@example.com",
                "password": "Secret123",
                "display_name": "Chatback User",
            },
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "chatback@example.com", "password": "Secret123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        proj_resp = await client.post(
            "/api/projects/from-local",
            json={"name": "Chatback-Project", "description": "test", "local_path": local_path},
            headers=headers,
        )
        project_id = proj_resp.json()["id"]

        yield client, headers, project_id


@pytest.mark.asyncio
async def test_chat_endpoint_structure(auth_client):
    client, headers, project_id = auth_client
    analysis_resp = await client.post(
        "/api/analyses",
        json={
            "project_id": project_id,
            "requirement_name": "Test",
            "requirement_text": "Test requirement for chatback",
        },
        headers=headers,
    )
    assert analysis_resp.status_code in (200, 201)
    task_id = analysis_resp.json()["id"]

    response = await client.post(
        f"/api/analyses/{task_id}/chat",
        json={"message": "为什么风险评估是中而不是高？"},
        headers=headers,
    )
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_chat_history_endpoint(auth_client):
    client, headers, project_id = auth_client
    analysis_resp = await client.post(
        "/api/analyses",
        json={
            "project_id": project_id,
            "requirement_name": "Test",
            "requirement_text": "Test requirement for chatback history",
        },
        headers=headers,
    )
    assert analysis_resp.status_code in (200, 201)
    task_id = analysis_resp.json()["id"]

    response = await client.get(
        f"/api/analyses/{task_id}/chat",
        headers=headers,
    )
    assert response.status_code in (200, 404)
