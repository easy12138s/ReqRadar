from reqradar.web.models import MCPAccessKey, MCPToolCall


async def _create_key(db, user_id, name="test-key", scopes=None):
    key = MCPAccessKey(
        user_id=user_id,
        key_prefix="rr_mcp_test",
        key_hash="$2b$12$placeholderhash",
        name=name,
        scopes=scopes or ["read"],
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


async def _create_tool_call(db, access_key_id=None, tool_name="analyze", success=True):
    call = MCPToolCall(
        access_key_id=access_key_id,
        tool_name=tool_name,
        arguments_json={"query": "test"},
        result_summary="ok",
        duration_ms=100,
        success=success,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)
    return call


async def test_get_config_returns_mcp_config_for_admin(client, admin_headers):
    response = await client.get("/api/mcp/config", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert "port" in body
    assert "host" in body
    assert "path" in body
    assert "audit_enabled" in body
    assert "audit_retention_days" in body


async def test_get_config_forbidden_for_regular_user(client, auth_headers):
    response = await client.get("/api/mcp/config", headers=auth_headers)

    assert response.status_code == 403


async def test_get_config_unauthorized_without_token(client):
    response = await client.get("/api/mcp/config")

    assert response.status_code == 401


async def test_update_config_partial_update(client, admin_headers):
    response = await client.put(
        "/api/mcp/config",
        headers=admin_headers,
        json={"enabled": True, "port": 9999},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["port"] == 9999


async def test_update_config_all_fields(client, admin_headers):
    response = await client.put(
        "/api/mcp/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "auto_start_with_web": False,
            "host": "127.0.0.1",
            "port": 5555,
            "path": "/custom-mcp",
            "public_url": "https://example.com/mcp",
            "audit_enabled": False,
            "audit_retention_days": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["auto_start_with_web"] is False
    assert body["host"] == "127.0.0.1"
    assert body["port"] == 5555
    assert body["path"] == "/custom-mcp"
    assert body["public_url"] == "https://example.com/mcp"
    assert body["audit_enabled"] is False
    assert body["audit_retention_days"] == 30


async def test_update_config_forbidden_for_regular_user(client, auth_headers):
    response = await client.put(
        "/api/mcp/config",
        headers=auth_headers,
        json={"enabled": True},
    )

    assert response.status_code == 403


async def test_update_config_unauthorized_without_token(client):
    response = await client.put("/api/mcp/config", json={"enabled": True})

    assert response.status_code == 401


async def test_update_config_invalid_port(client, admin_headers):
    response = await client.put(
        "/api/mcp/config",
        headers=admin_headers,
        json={"port": "not-a-number"},
    )

    assert response.status_code == 422


async def test_get_keys_admin_sees_all(client, admin_headers, regular_user, db_session):
    await _create_key(db_session, regular_user.id, name="user-key")

    response = await client.get("/api/mcp/keys", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert any(k["name"] == "user-key" for k in body)


async def test_get_keys_regular_user_sees_own(client, auth_headers, regular_user, db_session):
    await _create_key(db_session, regular_user.id, name="my-key")

    response = await client.get("/api/mcp/keys", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert all(k["user_id"] == regular_user.id for k in body)


async def test_get_keys_empty_list(client, auth_headers):
    response = await client.get("/api/mcp/keys", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_get_keys_unauthorized_without_token(client):
    response = await client.get("/api/mcp/keys")

    assert response.status_code == 401


async def test_create_key_success(client, auth_headers):
    response = await client.post(
        "/api/mcp/keys",
        headers=auth_headers,
        json={"name": "my-api-key"},
    )

    assert response.status_code == 201
    body = response.json()
    assert "mcpServers" in body
    assert "reqradar" in body["mcpServers"]
    assert "url" in body["mcpServers"]["reqradar"]
    assert "headers" in body["mcpServers"]["reqradar"]


async def test_create_key_with_custom_scopes(client, auth_headers):
    response = await client.post(
        "/api/mcp/keys",
        headers=auth_headers,
        json={"name": "scoped-key", "scopes": ["read", "write"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert "mcpServers" in body


async def test_create_key_missing_name(client, auth_headers):
    response = await client.post(
        "/api/mcp/keys",
        headers=auth_headers,
        json={"scopes": ["read"]},
    )

    assert response.status_code == 422


async def test_create_key_unauthorized_without_token(client):
    response = await client.post(
        "/api/mcp/keys",
        json={"name": "key-no-auth"},
    )

    assert response.status_code == 401


async def test_revoke_key_owner_can_revoke(client, auth_headers, regular_user, db_session):
    key = await _create_key(db_session, regular_user.id)

    response = await client.post(
        f"/api/mcp/keys/{key.id}/revoke",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    assert body["revoked_at"] is not None


async def test_revoke_key_admin_can_revoke_any(client, admin_headers, regular_user, db_session):
    key = await _create_key(db_session, regular_user.id)

    response = await client.post(
        f"/api/mcp/keys/{key.id}/revoke",
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False


async def test_revoke_key_not_found(client, auth_headers):
    response = await client.post(
        "/api/mcp/keys/99999/revoke",
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_revoke_key_admin_not_found(client, admin_headers):
    response = await client.post(
        "/api/mcp/keys/99999/revoke",
        headers=admin_headers,
    )

    assert response.status_code == 404


async def test_revoke_key_unauthorized_without_token(client):
    response = await client.post("/api/mcp/keys/1/revoke")

    assert response.status_code == 401


async def test_re_export_key_owner(client, auth_headers, regular_user, db_session):
    key = await _create_key(db_session, regular_user.id)

    response = await client.post(
        f"/api/mcp/keys/{key.id}/re-export",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "mcp_config" in body
    assert "note" in body


async def test_re_export_key_admin(client, admin_headers, regular_user, db_session):
    key = await _create_key(db_session, regular_user.id)

    response = await client.post(
        f"/api/mcp/keys/{key.id}/re-export",
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "mcp_config" in body


async def test_re_export_key_not_found(client, auth_headers):
    response = await client.post(
        "/api/mcp/keys/99999/re-export",
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_re_export_key_admin_not_found(client, admin_headers):
    response = await client.post(
        "/api/mcp/keys/99999/re-export",
        headers=admin_headers,
    )

    assert response.status_code == 404


async def test_re_export_key_unauthorized_without_token(client):
    response = await client.post("/api/mcp/keys/1/re-export")

    assert response.status_code == 401


async def test_get_tool_calls_admin(client, admin_headers, db_session):
    key = await _create_key(db_session, 1)
    await _create_tool_call(db_session, access_key_id=key.id, tool_name="analyze")

    response = await client.get("/api/mcp/tool-calls", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert "tool_name" in body[0]
    assert "success" in body[0]


async def test_get_tool_calls_empty(client, admin_headers):
    response = await client.get("/api/mcp/tool-calls", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_get_tool_calls_with_filters(client, admin_headers, db_session):
    key = await _create_key(db_session, 1)
    await _create_tool_call(db_session, access_key_id=key.id, tool_name="search")
    await _create_tool_call(db_session, access_key_id=key.id, tool_name="analyze")

    response = await client.get(
        "/api/mcp/tool-calls",
        headers=admin_headers,
        params={"tool_name": "search", "limit": 10, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert all(c["tool_name"] == "search" for c in body)


async def test_get_tool_calls_with_key_id_filter(client, admin_headers, db_session):
    key = await _create_key(db_session, 1)
    await _create_tool_call(db_session, access_key_id=key.id, tool_name="analyze")

    response = await client.get(
        "/api/mcp/tool-calls",
        headers=admin_headers,
        params={"access_key_id": key.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert all(c["access_key_id"] == key.id for c in body)


async def test_get_tool_calls_forbidden_for_regular_user(client, auth_headers):
    response = await client.get("/api/mcp/tool-calls", headers=auth_headers)

    assert response.status_code == 403


async def test_get_tool_calls_unauthorized_without_token(client):
    response = await client.get("/api/mcp/tool-calls")

    assert response.status_code == 401


async def test_get_tool_calls_invalid_limit(client, admin_headers):
    response = await client.get(
        "/api/mcp/tool-calls",
        headers=admin_headers,
        params={"limit": "not-a-number"},
    )

    assert response.status_code == 422


async def test_audit_cleanup_admin(client, admin_headers):
    response = await client.post("/api/mcp/audit/cleanup", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert "deleted" in body
    assert isinstance(body["deleted"], int)


async def test_audit_cleanup_deletes_expired(client, admin_headers, db_session):
    from datetime import UTC, datetime, timedelta

    expired_call = MCPToolCall(
        access_key_id=None,
        tool_name="old_tool",
        arguments_json={},
        result_summary="expired",
        duration_ms=50,
        success=True,
        created_at=datetime.now(UTC) - timedelta(days=365),
    )
    db_session.add(expired_call)
    await db_session.commit()

    response = await client.post("/api/mcp/audit/cleanup", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["deleted"] >= 1


async def test_audit_cleanup_forbidden_for_regular_user(client, auth_headers):
    response = await client.post("/api/mcp/audit/cleanup", headers=auth_headers)

    assert response.status_code == 403


async def test_audit_cleanup_unauthorized_without_token(client):
    response = await client.post("/api/mcp/audit/cleanup")

    assert response.status_code == 401
