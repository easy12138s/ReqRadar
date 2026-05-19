import pytest

from tests.factories import build_report_template


async def test_template_crud_flow(client, auth_headers):
    create_response = await client.post(
        "/api/templates",
        headers=auth_headers,
        json={
            "name": "Custom Template",
            "description": "custom",
            "definition": "{}",
            "render_template": "# {{ title }}",
        },
    )
    assert create_response.status_code == 201
    template_id = create_response.json()["id"]

    list_response = await client.get("/api/templates", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(item["id"] == template_id for item in list_response.json())

    get_response = await client.get(f"/api/templates/{template_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Custom Template"

    update_response = await client.put(
        f"/api/templates/{template_id}",
        headers=auth_headers,
        json={"name": "Renamed Template"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed Template"

    delete_response = await client.delete(f"/api/templates/{template_id}", headers=auth_headers)
    assert delete_response.status_code == 204


async def test_default_template_cannot_be_modified_or_deleted(client, auth_headers, db_session):
    template = build_report_template(name="Default", is_default=True)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    update_response = await client.put(
        f"/api/templates/{template.id}", headers=auth_headers, json={"name": "Blocked"}
    )
    delete_response = await client.delete(f"/api/templates/{template.id}", headers=auth_headers)

    assert update_response.status_code == 403
    assert delete_response.status_code == 403


async def test_set_default_template(client, auth_headers, db_session):
    template = build_report_template(name="Candidate", is_default=False)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    response = await client.post(f"/api/templates/{template.id}/set-default", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"success": True}


async def test_get_nonexistent_template_returns_404(client, auth_headers):
    response = await client.get("/api/templates/99999", headers=auth_headers)
    assert response.status_code == 404


async def test_put_nonexistent_template_returns_404(client, auth_headers):
    response = await client.put("/api/templates/99999", headers=auth_headers, json={"name": "x"})
    assert response.status_code == 404


async def test_delete_nonexistent_template_returns_404(client, auth_headers):
    response = await client.delete("/api/templates/99999", headers=auth_headers)
    assert response.status_code == 404


async def test_list_templates_returns_empty_list(client, auth_headers, db_session):
    response = await client.get("/api/templates", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_create_template_missing_required_fields(client, auth_headers):
    response = await client.post("/api/templates", headers=auth_headers, json={"name": "x"})
    assert response.status_code == 422


class TestUnauthenticated:
    """未认证访问应返回 401/403。"""

    async def test_list_unauthenticated(self, client):
        resp = await client.get("/api/templates")
        assert resp.status_code in (401, 403)

    async def test_create_unauthenticated(self, client):
        resp = await client.post(
            "/api/templates",
            json={"name": "x", "description": "x", "definition": "{}", "render_template": "# t"},
        )
        assert resp.status_code in (401, 403)

    async def test_get_unauthenticated(self, client):
        resp = await client.get("/api/templates/1")
        assert resp.status_code in (401, 403)

    async def test_update_unauthenticated(self, client):
        resp = await client.put("/api/templates/1", json={"name": "x"})
        assert resp.status_code in (401, 403)

    async def test_delete_unauthenticated(self, client):
        resp = await client.delete("/api/templates/1")
        assert resp.status_code in (401, 403)

    async def test_set_default_unauthenticated(self, client):
        resp = await client.post("/api/templates/1/set-default")
        assert resp.status_code in (401, 403)
