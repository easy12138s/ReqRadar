import pytest


@pytest.mark.asyncio
async def test_user_list_requires_admin(client, auth_headers):
    response = await client.get("/api/users", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_users(client, admin_headers, regular_user, admin_user):
    response = await client.get("/api/users", headers=admin_headers)

    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert {regular_user.email, admin_user.email}.issubset(emails)


@pytest.mark.asyncio
async def test_admin_can_update_user(client, admin_headers, regular_user):
    response = await client.put(
        f"/api/users/{regular_user.id}",
        headers=admin_headers,
        json={"display_name": "Updated User", "role": "admin", "is_active": True},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated User"
    assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_can_delete_user(client, admin_headers, regular_user):
    response = await client.delete(f"/api/users/{regular_user.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {"deleted": True}


@pytest.mark.asyncio
async def test_admin_delete_missing_user_returns_404(client, admin_headers):
    response = await client.delete("/api/users/99999", headers=admin_headers)

    assert response.status_code == 404
