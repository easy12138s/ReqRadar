import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.models import User, Project
from reqradar.web.api.auth import hash_password, create_access_token


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_SECRET_KEY = "test-secret-key-for-testing"


@pytest.fixture(autouse=True)
def set_test_secret_key():
    import reqradar.web.api.auth as auth_module

    original_secret = auth_module.SECRET_KEY
    original_expire = auth_module.ACCESS_TOKEN_EXPIRE_MINUTES
    original_testing = os.environ.get("REQRADAR_TESTING")
    auth_module.SECRET_KEY = TEST_SECRET_KEY
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = 1440
    os.environ["REQRADAR_TESTING"] = "1"
    yield
    auth_module.SECRET_KEY = original_secret
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire
    if original_testing is not None:
        os.environ["REQRADAR_TESTING"] = original_testing
    else:
        os.environ.pop("REQRADAR_TESTING", None)


@pytest_asyncio.fixture
async def setup_db():
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module
    import reqradar.infrastructure.config as config_module

    original_factory = dep_module.async_session_factory
    original_config = config_module.load_config

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = TEST_SECRET_KEY
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = 1440

    def _test_config():
        c = original_config()
        c.web.auto_create_tables = True
        c.web.debug = True
        c.web.database_url = TEST_DATABASE_URL
        return c

    config_module.load_config = _test_config

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    dep_module.async_session_factory = original_factory
    config_module.load_config = original_config


@pytest_asyncio.fixture
async def db_session(setup_db):
    async with setup_db() as session:
        yield session


@pytest_asyncio.fixture
async def client(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def test_user(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        register_resp = await c.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "TestPass123",
                "display_name": "Test User",
            },
        )
        assert register_resp.status_code == 201

        login_resp = await c.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "TestPass123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_data = register_resp.json()

        yield c, headers, token, user_data


@pytest_asyncio.fixture
async def test_project(test_user):
    c, headers, token, user_data = test_user
    proj_resp = await c.post(
        "/api/projects/from-local",
        json={
            "name": "test-project",
            "description": "A test project",
            "local_path": "/tmp",
        },
        headers=headers,
    )
    assert proj_resp.status_code in (200, 201)
    project_id = proj_resp.json()["id"]
    yield c, headers, token, user_data, project_id
