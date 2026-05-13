from datetime import timedelta

import pytest

from reqradar.infrastructure.config import MCPConfig
from reqradar.web.enums import ReleaseStatus
from reqradar.web.models import MCPToolCall, utc_now
from reqradar.web.services import mcp_audit_service, mcp_auth_service, requirement_release_service
from tests.factories import build_analysis_task, build_project

MCP_CONFIG = MCPConfig(host="0.0.0.0", port=8765, path="/mcp")


class TestSanitizeArgs:
    def test_redacts_api_key(self):
        result = mcp_audit_service.sanitize_args({"api_key": "sk-123", "query": "test"})

        assert result == {"api_key": "***REDACTED***", "query": "test"}

    def test_redacts_case_insensitive_nested(self):
        result = mcp_audit_service.sanitize_args({"nested": {"Token": "abc"}})

        assert result == {"nested": {"Token": "***REDACTED***"}}

    def test_redacts_in_list_of_dicts(self):
        result = mcp_audit_service.sanitize_args({"items": [{"key": "val", "password": "secret"}]})

        assert result == {"items": [{"key": "***REDACTED***", "password": "***REDACTED***"}]}

    def test_no_redaction_when_no_sensitive_keys(self):
        result = mcp_audit_service.sanitize_args({"safe_key": "value"})

        assert result == {"safe_key": "value"}

    @pytest.mark.parametrize(
        ("key",),
        [("authorization",), ("token",), ("api_key",), ("key",), ("password",), ("secret",)],
    )
    def test_redacts_each_sensitive_key(self, key):
        result = mcp_audit_service.sanitize_args({key: "sensitive"})

        assert result[key] == "***REDACTED***"

    def test_preserves_non_dict_items_in_list(self):
        result = mcp_audit_service.sanitize_args({"items": ["plain", 42, None]})

        assert result == {"items": ["plain", 42, None]}

    def test_deeply_nested(self):
        result = mcp_audit_service.sanitize_args({"a": {"b": {"Secret": "deep"}}})

        assert result == {"a": {"b": {"Secret": "***REDACTED***"}}}

    def test_empty_dict(self):
        assert mcp_audit_service.sanitize_args({}) == {}


class TestRecordCall:
    async def test_record_call_creates_tool_call(self, db_session):
        row = await mcp_audit_service.record_call(
            db_session,
            access_key_id=None,
            tool_name="analyze",
            arguments={"query": "test"},
            result_summary="ok",
            duration_ms=50,
            success=True,
        )

        assert row.id is not None
        assert row.tool_name == "analyze"
        assert row.arguments_json == {"query": "test"}
        assert row.result_summary == "ok"
        assert row.duration_ms == 50
        assert row.success is True
        assert row.error_message is None

    async def test_record_call_sanitizes_arguments(self, db_session):
        row = await mcp_audit_service.record_call(
            db_session,
            access_key_id=None,
            tool_name="analyze",
            arguments={"api_key": "sk-secret", "query": "test"},
            result_summary="ok",
            duration_ms=10,
        )

        assert row.arguments_json == {"api_key": "***REDACTED***", "query": "test"}

    async def test_record_call_with_error(self, db_session):
        row = await mcp_audit_service.record_call(
            db_session,
            access_key_id=None,
            tool_name="analyze",
            arguments={},
            result_summary="failed",
            duration_ms=100,
            success=False,
            error_message="timeout",
        )

        assert row.success is False
        assert row.error_message == "timeout"


class TestQueryCalls:
    async def test_query_calls_returns_all_by_default(self, db_session):
        for idx in range(3):
            await mcp_audit_service.record_call(
                db_session,
                None,
                f"tool_{idx}",
                {},
                "",
                10,
            )

        rows = await mcp_audit_service.query_calls(db_session)

        assert len(rows) == 3

    async def test_query_calls_filters_by_access_key_id(self, db_session):
        await mcp_audit_service.record_call(db_session, 1, "t1", {}, "", 10)
        await mcp_audit_service.record_call(db_session, 2, "t2", {}, "", 10)

        rows = await mcp_audit_service.query_calls(db_session, access_key_id=1)

        assert len(rows) == 1
        assert rows[0].access_key_id == 1

    async def test_query_calls_filters_by_tool_name(self, db_session):
        await mcp_audit_service.record_call(db_session, None, "analyze", {}, "", 10)
        await mcp_audit_service.record_call(db_session, None, "search", {}, "", 10)

        rows = await mcp_audit_service.query_calls(db_session, tool_name="analyze")

        assert len(rows) == 1
        assert rows[0].tool_name == "analyze"

    async def test_query_calls_respects_limit_and_offset(self, db_session):
        for _ in range(5):
            await mcp_audit_service.record_call(db_session, None, "tool", {}, "", 10)

        rows = await mcp_audit_service.query_calls(db_session, limit=2, offset=1)

        assert len(rows) == 2


class TestCleanupExpired:
    async def test_cleanup_expired_removes_old_records(self, db_session):
        await mcp_audit_service.record_call(db_session, None, "old", {}, "", 10)
        old_call = await db_session.get(MCPToolCall, 1)
        old_call.created_at = utc_now() - timedelta(days=100)
        await db_session.commit()

        removed = await mcp_audit_service.cleanup_expired(db_session, retention_days=90)

        assert removed == 1

    async def test_cleanup_expired_keeps_recent_records(self, db_session):
        await mcp_audit_service.record_call(db_session, None, "recent", {}, "", 10)

        removed = await mcp_audit_service.cleanup_expired(db_session, retention_days=90)

        assert removed == 0


class TestGenerateKey:
    async def test_generate_key_returns_mcp_config_with_raw_key(self, db_session, regular_user):
        result = await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "test-key",
            ["read"],
            MCP_CONFIG,
        )

        assert "mcpServers" in result
        assert "reqradar" in result["mcpServers"]
        server = result["mcpServers"]["reqradar"]
        assert server["url"] == "http://localhost:8765/mcp"
        assert server["headers"]["Authorization"].startswith("Bearer rr_mcp_")

    async def test_generate_key_persists_access_key(self, db_session, regular_user):
        await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "test-key",
            ["read", "write"],
            MCP_CONFIG,
        )

        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)

        assert len(keys) == 1
        assert keys[0].name == "test-key"
        assert keys[0].scopes == ["read", "write"]
        assert keys[0].is_active is True

    async def test_generate_key_prefix_matches_db(self, db_session, regular_user):
        result = await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "prefix-test",
            ["read"],
            MCP_CONFIG,
        )
        raw_key = result["mcpServers"]["reqradar"]["headers"]["Authorization"].replace(
            "Bearer ", ""
        )
        prefix = raw_key[:12]

        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)

        assert keys[0].key_prefix == prefix


class TestVerifyKey:
    async def test_verify_key_returns_active_key(self, db_session, regular_user):
        result = await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "verify-test",
            ["read"],
            MCP_CONFIG,
        )
        raw_key = result["mcpServers"]["reqradar"]["headers"]["Authorization"].replace(
            "Bearer ", ""
        )

        verified = await mcp_auth_service.verify_key(db_session, raw_key)

        assert verified is not None
        assert verified.name == "verify-test"

    async def test_verify_key_returns_none_for_invalid(self, db_session):
        verified = await mcp_auth_service.verify_key(
            db_session, "rr_mcp_invalidkey12345678901234567890"
        )

        assert verified is None

    async def test_verify_key_returns_none_for_revoked_key(self, db_session, regular_user):
        result = await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "revoke-verify",
            ["read"],
            MCP_CONFIG,
        )
        raw_key = result["mcpServers"]["reqradar"]["headers"]["Authorization"].replace(
            "Bearer ", ""
        )
        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)
        await mcp_auth_service.revoke_key(db_session, keys[0].id, regular_user.id)

        verified = await mcp_auth_service.verify_key(db_session, raw_key)

        assert verified is None

    async def test_verify_key_updates_last_used_at(self, db_session, regular_user):
        result = await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "last-used",
            ["read"],
            MCP_CONFIG,
        )
        raw_key = result["mcpServers"]["reqradar"]["headers"]["Authorization"].replace(
            "Bearer ", ""
        )

        verified = await mcp_auth_service.verify_key(db_session, raw_key)

        assert verified.last_used_at is not None


class TestRevokeKey:
    async def test_revoke_key_deactivates_key(self, db_session, regular_user):
        await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "revoke-test",
            ["read"],
            MCP_CONFIG,
        )
        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)

        revoked = await mcp_auth_service.revoke_key(db_session, keys[0].id, regular_user.id)

        assert revoked is not None
        assert revoked.is_active is False
        assert revoked.revoked_at is not None

    async def test_revoke_key_returns_none_for_wrong_user(
        self, db_session, regular_user, admin_user
    ):
        await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "wrong-user",
            ["read"],
            MCP_CONFIG,
        )
        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)

        revoked = await mcp_auth_service.revoke_key(db_session, keys[0].id, admin_user.id)

        assert revoked is None

    async def test_revoke_key_returns_none_for_nonexistent(self, db_session, regular_user):
        revoked = await mcp_auth_service.revoke_key(db_session, 99999, regular_user.id)

        assert revoked is None


class TestListKeys:
    async def test_list_keys_returns_only_user_keys(self, db_session, regular_user, admin_user):
        await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "reg-key",
            ["read"],
            MCP_CONFIG,
        )
        await mcp_auth_service.generate_key(
            db_session,
            admin_user.id,
            "admin-key",
            ["read"],
            MCP_CONFIG,
        )

        regular_keys = await mcp_auth_service.list_keys(db_session, regular_user.id)
        admin_keys = await mcp_auth_service.list_keys(db_session, admin_user.id)

        assert len(regular_keys) == 1
        assert len(admin_keys) == 1
        assert regular_keys[0].name == "reg-key"
        assert admin_keys[0].name == "admin-key"

    async def test_list_keys_returns_empty_for_user_with_no_keys(self, db_session, regular_user):
        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)

        assert keys == []


class TestReExportKey:
    async def test_re_export_key_returns_info(self, db_session, regular_user):
        await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "export-test",
            ["read"],
            MCP_CONFIG,
        )
        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)

        exported = await mcp_auth_service.re_export_key(
            db_session, keys[0].id, regular_user.id, MCP_CONFIG
        )

        assert exported is not None
        assert "mcp_config" in exported

    async def test_re_export_key_returns_none_for_wrong_user(
        self, db_session, regular_user, admin_user
    ):
        await mcp_auth_service.generate_key(
            db_session,
            regular_user.id,
            "export-wrong",
            ["read"],
            MCP_CONFIG,
        )
        keys = await mcp_auth_service.list_keys(db_session, regular_user.id)

        exported = await mcp_auth_service.re_export_key(
            db_session, keys[0].id, admin_user.id, MCP_CONFIG
        )

        assert exported is None

    async def test_re_export_key_returns_none_for_nonexistent(self, db_session, regular_user):
        exported = await mcp_auth_service.re_export_key(
            db_session, 99999, regular_user.id, MCP_CONFIG
        )

        assert exported is None


class TestBuildMcpPublicUrl:
    def test_builds_url_from_host_port_path(self):
        url = mcp_auth_service.build_mcp_public_url(MCP_CONFIG)

        assert url == "http://localhost:8765/mcp"

    def test_uses_public_url_when_set(self):
        config = MCPConfig(host="0.0.0.0", port=8765, path="/mcp", public_url="https://example.com")
        url = mcp_auth_service.build_mcp_public_url(config)

        assert url == "https://example.com/mcp"

    def test_does_not_duplicate_path(self):
        config = MCPConfig(
            host="0.0.0.0", port=8765, path="/mcp", public_url="https://example.com/mcp"
        )
        url = mcp_auth_service.build_mcp_public_url(config)

        assert url == "https://example.com/mcp"

    def test_uses_host_when_not_wildcard(self):
        config = MCPConfig(host="192.168.1.1", port=9000, path="/api/mcp")
        url = mcp_auth_service.build_mcp_public_url(config)

        assert url == "http://192.168.1.1:9000/api/mcp"


@pytest.fixture
async def project_with_user(db_session, regular_user):
    project = build_project(owner_id=regular_user.id, name="release_project")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project, regular_user


class TestCreateRelease:
    async def test_create_release_with_draft_status(self, db_session, project_with_user):
        project, user = project_with_user

        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "REL-001",
            "v1",
            "Initial content",
        )

        assert release.id is not None
        assert release.release_code == "REL-001"
        assert release.title == "v1"
        assert release.content == "Initial content"
        assert release.status == ReleaseStatus.DRAFT
        assert release.version == 1

    async def test_create_release_auto_increments_version(self, db_session, project_with_user):
        project, user = project_with_user

        first = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "REL-002",
            "v1",
            "Content v1",
        )
        second = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "REL-002",
            "v2",
            "Content v2",
        )

        assert first.version == 1
        assert second.version == 2

    async def test_create_release_with_context_and_task(self, db_session, project_with_user):
        project, user = project_with_user
        task = build_analysis_task(project_id=project.id, user_id=user.id, status="completed")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "REL-003",
            "t1",
            "Content",
            {"ctx": True},
            task.id,
        )

        assert release.context_json == {"ctx": True}
        assert release.task_id == task.id

    async def test_create_release_with_empty_context(self, db_session, project_with_user):
        project, user = project_with_user

        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "REL-004",
            "t1",
            "Content",
        )

        assert release.context_json == {}


class TestGetRelease:
    async def test_get_release_returns_existing(self, db_session, project_with_user):
        project, user = project_with_user
        created = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "REL-010",
            "t1",
            "Content",
        )

        found = await requirement_release_service.get_release(db_session, created.id)

        assert found is not None
        assert found.id == created.id

    async def test_get_release_returns_none_for_missing(self, db_session):
        found = await requirement_release_service.get_release(db_session, 99999)

        assert found is None


class TestListReleases:
    async def test_list_releases_filters_by_project(self, db_session, project_with_user):
        project, user = project_with_user
        other_project = build_project(owner_id=user.id, name="other_project")
        db_session.add(other_project)
        await db_session.commit()
        await db_session.refresh(other_project)
        await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "P1-001",
            "t1",
            "Content",
        )
        await requirement_release_service.create_release(
            db_session,
            other_project.id,
            user.id,
            "P2-001",
            "t2",
            "Content",
        )

        releases = await requirement_release_service.list_releases(
            db_session, project_id=project.id
        )

        assert len(releases) == 1
        assert releases[0].release_code == "P1-001"

    async def test_list_releases_filters_by_status(self, db_session, project_with_user):
        project, user = project_with_user
        await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "S-001",
            "draft",
            "Content",
        )

        drafts = await requirement_release_service.list_releases(
            db_session,
            project_id=project.id,
            status=ReleaseStatus.DRAFT,
        )
        published = await requirement_release_service.list_releases(
            db_session,
            project_id=project.id,
            status=ReleaseStatus.PUBLISHED,
        )

        assert len(drafts) == 1
        assert len(published) == 0

    async def test_list_releases_respects_limit_and_offset(self, db_session, project_with_user):
        project, user = project_with_user
        for idx in range(5):
            await requirement_release_service.create_release(
                db_session,
                project.id,
                user.id,
                f"L-{idx:03d}",
                f"t{idx}",
                "Content",
            )

        page = await requirement_release_service.list_releases(
            db_session,
            project_id=project.id,
            limit=2,
            offset=0,
        )

        assert len(page) == 2


class TestUpdateRelease:
    async def test_update_release_modifies_draft(self, db_session, project_with_user):
        project, user = project_with_user
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "U-001",
            "old title",
            "old content",
        )

        updated = await requirement_release_service.update_release(
            db_session,
            release.id,
            title="new title",
            content="new content",
        )

        assert updated is not None
        assert updated.title == "new title"
        assert updated.content == "new content"

    async def test_update_release_updates_context_json(self, db_session, project_with_user):
        project, user = project_with_user
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "U-002",
            "t1",
            "Content",
        )

        updated = await requirement_release_service.update_release(
            db_session,
            release.id,
            context_json={"updated": True},
        )

        assert updated.context_json == {"updated": True}

    async def test_update_release_raises_for_published(self, db_session, project_with_user):
        project, user = project_with_user
        task = build_analysis_task(project_id=project.id, user_id=user.id, status="completed")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "U-003",
            "t1",
            "Content",
            task_id=task.id,
        )
        await requirement_release_service.publish_release(db_session, release.id)

        with pytest.raises(Exception, match="Only draft releases can be updated"):
            await requirement_release_service.update_release(db_session, release.id, title="new")

    async def test_update_release_returns_none_for_missing(self, db_session):
        result = await requirement_release_service.update_release(db_session, 99999, title="x")

        assert result is None

    async def test_update_release_partial_update(self, db_session, project_with_user):
        project, user = project_with_user
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "U-004",
            "original",
            "original content",
        )

        updated = await requirement_release_service.update_release(
            db_session,
            release.id,
            title="changed",
        )

        assert updated.title == "changed"
        assert updated.content == "original content"


class TestPublishRelease:
    async def test_publish_release_changes_status(self, db_session, project_with_user):
        project, user = project_with_user
        task = build_analysis_task(project_id=project.id, user_id=user.id, status="completed")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "PUB-001",
            "t1",
            "Content",
            task_id=task.id,
        )

        published = await requirement_release_service.publish_release(db_session, release.id)

        assert published is not None
        assert published.status == ReleaseStatus.PUBLISHED
        assert published.published_at is not None

    async def test_publish_release_without_task_id(self, db_session, project_with_user):
        project, user = project_with_user
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "PUB-002",
            "t1",
            "Content",
        )

        published = await requirement_release_service.publish_release(db_session, release.id)

        assert published is not None
        assert published.status == ReleaseStatus.PUBLISHED

    async def test_publish_release_raises_for_non_draft(self, db_session, project_with_user):
        project, user = project_with_user
        task = build_analysis_task(project_id=project.id, user_id=user.id, status="completed")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "PUB-003",
            "t1",
            "Content",
            task_id=task.id,
        )
        await requirement_release_service.publish_release(db_session, release.id)

        with pytest.raises(Exception, match="Only draft releases can be published"):
            await requirement_release_service.publish_release(db_session, release.id)

    async def test_publish_release_raises_when_task_not_completed(
        self, db_session, project_with_user
    ):
        project, user = project_with_user
        task = build_analysis_task(project_id=project.id, user_id=user.id, status="running")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "PUB-004",
            "t1",
            "Content",
            task_id=task.id,
        )

        with pytest.raises(Exception, match="Associated analysis task must be completed"):
            await requirement_release_service.publish_release(db_session, release.id)

    async def test_publish_release_returns_none_for_missing(self, db_session):
        result = await requirement_release_service.publish_release(db_session, 99999)

        assert result is None


class TestArchiveRelease:
    async def test_archive_release_changes_status(self, db_session, project_with_user):
        project, user = project_with_user
        task = build_analysis_task(project_id=project.id, user_id=user.id, status="completed")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "ARC-001",
            "t1",
            "Content",
            task_id=task.id,
        )
        await requirement_release_service.publish_release(db_session, release.id)

        archived = await requirement_release_service.archive_release(db_session, release.id)

        assert archived is not None
        assert archived.status == ReleaseStatus.ARCHIVED
        assert archived.archived_at is not None

    async def test_archive_release_raises_for_draft(self, db_session, project_with_user):
        project, user = project_with_user
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "ARC-002",
            "t1",
            "Content",
        )

        with pytest.raises(Exception, match="Only published releases can be archived"):
            await requirement_release_service.archive_release(db_session, release.id)

    async def test_archive_release_returns_none_for_missing(self, db_session):
        result = await requirement_release_service.archive_release(db_session, 99999)

        assert result is None


class TestDeleteRelease:
    async def test_delete_release_removes_draft(self, db_session, project_with_user):
        project, user = project_with_user
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "DEL-001",
            "t1",
            "Content",
        )

        deleted = await requirement_release_service.delete_release(db_session, release.id)

        assert deleted is True
        assert await requirement_release_service.get_release(db_session, release.id) is None

    async def test_delete_release_raises_for_non_draft(self, db_session, project_with_user):
        project, user = project_with_user
        task = build_analysis_task(project_id=project.id, user_id=user.id, status="completed")
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        release = await requirement_release_service.create_release(
            db_session,
            project.id,
            user.id,
            "DEL-002",
            "t1",
            "Content",
            task_id=task.id,
        )
        await requirement_release_service.publish_release(db_session, release.id)

        with pytest.raises(Exception, match="Only draft releases can be deleted"):
            await requirement_release_service.delete_release(db_session, release.id)

    async def test_delete_release_returns_false_for_missing(self, db_session):
        deleted = await requirement_release_service.delete_release(db_session, 99999)

        assert deleted is False
