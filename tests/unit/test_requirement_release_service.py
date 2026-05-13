"""需求发布服务单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from reqradar.core.exceptions import ReportException
from reqradar.web.services.requirement_release_service import (
    archive_release,
    create_release,
    delete_release,
    get_release,
    list_releases,
    publish_release,
    supersede_release,
    update_release,
)


class TestCreateRelease:
    @pytest.mark.asyncio
    async def test_creates_draft_with_auto_version(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        release = await create_release(
            db=db,
            project_id=1,
            user_id=10,
            release_code="REQ-001",
            title="Test Release",
            content="Content here",
        )

        assert release is not None


class TestGetRelease:
    @pytest.mark.asyncio
    async def test_found(self):
        db = AsyncMock()
        mock_release = MagicMock(id=5)
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))

        result = await get_release(db, 5)
        assert result.id == 5

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await get_release(db, 999)
        assert result is None


class TestListReleases:
    @pytest.mark.asyncio
    async def test_default_params(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(all=MagicMock(return_value=[]))))

        results = await list_releases(db)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_filter_by_project_and_status(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(all=MagicMock(return_value=[]))))

        results = await list_releases(db, project_id=5, status="published", limit=20, offset=10)
        assert isinstance(results, list)


class TestUpdateRelease:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        db = AsyncMock()
        mock_release = MagicMock(status="draft")
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await update_release(db, 1, title="New Title", content="New Content")
        assert result.title == "New Title"
        assert result.content == "New Content"

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await update_release(db, 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_cannot_update_non_draft(self):
        db = AsyncMock()
        mock_release = MagicMock(status="published")
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))

        with pytest.raises(ReportException) as ctx:
            await update_release(db, 1, title="Try Update")
        assert "Only draft" in str(ctx.value)


class TestPublishRelease:
    @pytest.mark.asyncio
    async def test_publishes_draft(self):
        db = AsyncMock()
        mock_release = MagicMock(status="draft", task_id=None)
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await publish_release(db, 1)
        assert result.status == "published"

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await publish_release(db, 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_cannot_publish_non_draft(self):
        db = AsyncMock()
        mock_release = MagicMock(status="archived")
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))

        with pytest.raises(ReportException) as ctx:
            await publish_release(db, 1)
        assert "Only draft" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_requires_completed_task(self):
        db = AsyncMock()
        mock_release = MagicMock(status="draft", task_id=100)
        mock_task = MagicMock(status="running")
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_task)),
            ]
        )

        with pytest.raises(ReportException) as ctx:
            await publish_release(db, 1)
        assert "must be completed" in str(ctx.value)


class TestArchiveRelease:
    @pytest.mark.asyncio
    async def test_archives_published(self):
        db = AsyncMock()
        mock_release = MagicMock(status="published")
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await archive_release(db, 1)
        assert result.status == "archived"

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await archive_release(db, 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_only_published_can_be_archived(self):
        db = AsyncMock()
        mock_release = MagicMock(status="draft")
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))

        with pytest.raises(ReportException) as ctx:
            await archive_release(db, 1)
        assert "Only published" in str(ctx.value)


class TestSupersedeRelease:
    @pytest.mark.asyncio
    async def test_supersedes_published_releases(self):
        db = AsyncMock()
        old_release = MagicMock(status="published")
        new_release = MagicMock(status="published")
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=old_release)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=new_release)),
            ]
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await supersede_release(db, release_id=1, superseded_by_id=2)
        assert result.superseded_by == 2

    @pytest.mark.asyncio
    async def test_old_release_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[MagicMock(scalar_one_or_none=MagicMock(return_value=None))]
        )

        result = await supersede_release(db, release_id=999, superseded_by_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_old_must_be_published(self):
        db = AsyncMock()
        draft_release = MagicMock(status="draft")
        db.execute = AsyncMock(
            side_effect=[MagicMock(scalar_one_or_none=MagicMock(return_value=draft_release))]
        )

        with pytest.raises(ReportException) as ctx:
            await supersede_release(db, release_id=1, superseded_by_id=2)
        assert "Only published" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_new_release_not_found(self):
        db = AsyncMock()
        published_old = MagicMock(status="published")
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=published_old)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            ]
        )

        with pytest.raises(ReportException) as ctx:
            await supersede_release(db, release_id=1, superseded_by_id=999)
        assert "not found" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_new_must_be_published(self):
        db = AsyncMock()
        published_old = MagicMock(status="published")
        draft_new = MagicMock(status="draft")
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=published_old)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=draft_new)),
            ]
        )

        with pytest.raises(ReportException) as ctx:
            await supersede_release(db, release_id=1, superseded_by_id=2)
        assert "must be published" in str(ctx.value)


class TestDeleteRelease:
    @pytest.mark.asyncio
    async def test_deletes_draft(self):
        db = AsyncMock()
        mock_release = MagicMock(status="draft")
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_release)))
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        result = await delete_release(db, 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_not_found_returns_false(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await delete_release(db, 999)
        assert result is False

    @pytest.mark.asyncio
    async def test_only_drafts_can_be_deleted(self):
        db = AsyncMock()
        published_release = MagicMock(status="published")
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=published_release)))

        with pytest.raises(ReportException) as ctx:
            await delete_release(db, 1)
        assert "Only draft" in str(ctx.value)
