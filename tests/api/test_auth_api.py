import pytest


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_token(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "new-user@example.com",
            "password": "Password123",
            "display_name": "New User",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new-user@example.com"
    assert body["role"] == "user"


@pytest.mark.asyncio
async def test_register_rejects_weak_password(client):
    response = await client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "password": "weak", "display_name": "Weak"},
    )

    assert response.status_code == 400
    assert "Password must be at least" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_returns_token_for_valid_credentials(client, regular_user):
    response = await client.post(
        "/api/auth/login",
        json={"email": regular_user.email, "password": "Password123"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(client, regular_user):
    response = await client.post(
        "/api/auth/login",
        json={"email": regular_user.email, "password": "wrong"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_me_password_changes_current_user_password(client, auth_headers, regular_user):
    response = await client.put(
        "/api/auth/me/password",
        headers=auth_headers,
        json={"old_password": "Password123", "new_password": "NewPassword123"},
    )
    login_response = await client.post(
        "/api/auth/login",
        json={"email": regular_user.email, "password": "NewPassword123"},
    )

    assert response.status_code == 200
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_put_me_password_rejects_wrong_old_password(client, auth_headers):
    response = await client.put(
        "/api/auth/me/password",
        headers=auth_headers,
        json={"old_password": "WrongPassword123", "new_password": "NewPassword123"},
    )

    assert response.status_code == 400
