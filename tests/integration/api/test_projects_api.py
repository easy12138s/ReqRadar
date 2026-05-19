import io
import zipfile

import pytest

from tests.factories import build_project


def make_zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_create_project_from_local_list_get_update_files_and_delete(
    client, auth_headers, sample_repo
):
    create_response = await client.post(
        "/api/projects/from-local",
        headers=auth_headers,
        json={
            "name": "local_project",
            "description": "Local project",
            "local_path": str(sample_repo),
        },
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    list_response = await client.get("/api/projects", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "local_project"

    get_response = await client.get(f"/api/projects/{project_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["description"] == "Local project"

    update_response = await client.put(
        f"/api/projects/{project_id}",
        headers=auth_headers,
        json={"description": "Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Updated"

    files_response = await client.get(f"/api/projects/{project_id}/files", headers=auth_headers)
    assert files_response.status_code == 200
    assert files_response.json()

    delete_response = await client.delete(f"/api/projects/{project_id}", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True


@pytest.mark.asyncio
async def test_create_project_from_local_rejects_missing_path(client, auth_headers, tmp_path):
    response = await client.post(
        "/api/projects/from-local",
        headers=auth_headers,
        json={"name": "missing_project", "local_path": str(tmp_path / "missing")},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_project_from_zip_and_reject_duplicate_name(client, auth_headers):
    response = await client.post(
        "/api/projects/from-zip",
        headers=auth_headers,
        data={"name": "zip_project", "description": "Zip"},
        files={"file": ("project.zip", make_zip({"app.py": "print(1)"}), "application/zip")},
    )
    duplicate_response = await client.post(
        "/api/projects/from-zip",
        headers=auth_headers,
        data={"name": "zip_project", "description": "Zip"},
        files={"file": ("project.zip", make_zip({"app.py": "print(1)"}), "application/zip")},
    )

    assert response.status_code == 201
    assert duplicate_response.status_code == 409


@pytest.mark.asyncio
async def test_create_project_from_zip_rejects_path_traversal(client, auth_headers):
    response = await client.post(
        "/api/projects/from-zip",
        headers=auth_headers,
        data={"name": "unsafe_zip", "description": "Zip"},
        files={"file": ("project.zip", make_zip({"../evil.py": "bad"}), "application/zip")},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_project_access_is_limited_to_owner(client, auth_headers, db_session, admin_user):
    project = build_project(owner_id=admin_user.id, name="private_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    response = await client.get(f"/api/projects/{project.id}", headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_index_returns_accepted(client, auth_headers, db_session, regular_user, monkeypatch):
    calls = []

    async def fake_build_index(self, project, db, config):
        calls.append(project.id)

    monkeypatch.setattr(
        "reqradar.web.services.project_index_service.ProjectIndexService.build_index",
        fake_build_index,
    )
    project = build_project(owner_id=regular_user.id, name="index_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    response = await client.post(f"/api/projects/{project.id}/index", headers=auth_headers)

    assert response.status_code == 202
    assert response.json()["project_id"] == project.id
    assert calls
