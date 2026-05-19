import pytest

from tests.factories import build_report_template


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_set_default_template(client, auth_headers, db_session):
    template = build_report_template(name="Candidate", is_default=False)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    response = await client.post(f"/api/templates/{template.id}/set-default", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"success": True}
