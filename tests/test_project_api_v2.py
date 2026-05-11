import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory

TEST_SECRET_KEY = "test-secret-key-project-v2"


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
    db_path = tmp_path / "test_reqradar_project_v2.db"
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

    yield session_factory, data_root

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    dep_module.async_session_factory = original_factory
    auth_module.SECRET_KEY = original_secret
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire
    config_module.load_config = original_config


@pytest_asyncio.fixture
async def auth_client(setup_db, tmp_path):
    session_factory, data_root = setup_db
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
    import os

    os.makedirs(local_path, exist_ok=True)
    with open(os.path.join(local_path, "main.py"), "w") as f:
        f.write("print('hello')")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={
                "email": "projv2@example.com",
                "password": "Secret123",
                "display_name": "Proj V2 User",
            },
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "projv2@example.com", "password": "Secret123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        yield client, headers, data_root, local_path


@pytest.mark.asyncio
async def test_create_project_from_local(auth_client):
    client, headers, data_root, local_path = auth_client
    response = await client.post(
        "/api/projects/from-local",
        json={"name": "local-proj", "description": "A local project", "local_path": local_path},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "local-proj"
    assert data["source_type"] == "local"


@pytest.mark.asyncio
async def test_create_project_from_local_duplicate_name(auth_client):
    client, headers, data_root, local_path = auth_client
    await client.post(
        "/api/projects/from-local",
        json={"name": "dup-proj", "description": "First", "local_path": local_path},
        headers=headers,
    )
    response = await client.post(
        "/api/projects/from-local",
        json={"name": "dup-proj", "description": "Second", "local_path": local_path},
        headers=headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_project_invalid_name(auth_client):
    client, headers, data_root, local_path = auth_client
    response = await client.post(
        "/api/projects/from-local",
        json={"name": "bad name!", "description": "Invalid name", "local_path": local_path},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_from_zip(auth_client, tmp_path):
    client, headers, data_root, local_path = auth_client
    zip_dir = tmp_path / "zip_content"
    zip_dir.mkdir()
    (zip_dir / "main.py").write_text("print('hello')")
    import zipfile

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in zip_dir.iterdir():
            zf.write(f, f.name)

    with open(zip_path, "rb") as f:
        response = await client.post(
            "/api/projects/from-zip",
            data={"name": "zip-proj", "description": "A zip project"},
            files={"file": ("test.zip", f, "application/zip")},
            headers=headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "zip-proj"
    assert data["source_type"] == "zip"


@pytest.mark.asyncio
async def test_list_projects(auth_client):
    client, headers, data_root, local_path = auth_client
    await client.post(
        "/api/projects/from-local",
        json={"name": "list-proj", "description": "For listing", "local_path": local_path},
        headers=headers,
    )
    response = await client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(p["name"] == "list-proj" for p in data)


@pytest.mark.asyncio
async def test_get_project(auth_client):
    client, headers, data_root, local_path = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "get-proj", "description": "For getting", "local_path": local_path},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "get-proj"


@pytest.mark.asyncio
async def test_get_project_files(auth_client):
    client, headers, data_root, local_path = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "files-proj", "description": "For files", "local_path": local_path},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}/files", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_delete_project(auth_client):
    client, headers, data_root, local_path = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "del-proj", "description": "For deletion", "local_path": local_path},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.delete(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_project(auth_client):
    client, headers, data_root, local_path = auth_client
    create_resp = await client.post(
        "/api/projects/from-local",
        json={"name": "upd-proj", "description": "For update", "local_path": local_path},
        headers=headers,
    )
    project_id = create_resp.json()["id"]
    response = await client.put(
        f"/api/projects/{project_id}",
        json={"description": "Updated description"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"
