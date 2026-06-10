"""Kernel ORM 模型的单元测试 — 使用独立 SQLite 验证映射正确性。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.kernel.database import Base, create_engine, create_session_factory
from reqradar.kernel.models import (
    AnalysisTask,
    Checkpoint,
    CognitiveSession,
    DimensionResult,
    Event,
    EvidenceRecord,
    EvidenceRelation,
    LLMCallLog,
    MCPAccessKey,
    MCPToolCall,
    PendingChange,
    Project,
    ProjectConfig,
    ReleaseStatus,
    Report,
    ReportChat,
    ReportTemplate,
    ReportVersion,
    RequirementDocument,
    RequirementRelease,
    RevokedToken,
    SynonymMapping,
    SystemConfig,
    TaskStatus,
    UploadedFile,
    User,
    UserConfig,
)


@pytest.fixture
async def db_session(tmp_path):
    """创建独立 SQLite 数据库的异步会话。"""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


class TestModelMapping:
    def test_all_models_have_tablename(self):
        models = [
            User,
            Project,
            RevokedToken,
            UserConfig,
            SystemConfig,
            ProjectConfig,
            ReportTemplate,
            RequirementDocument,
            AnalysisTask,
            Report,
            UploadedFile,
            PendingChange,
            SynonymMapping,
            ReportVersion,
            ReportChat,
            LLMCallLog,
            MCPAccessKey,
            RequirementRelease,
            MCPToolCall,
            CognitiveSession,
            Event,
            Checkpoint,
            EvidenceRecord,
            EvidenceRelation,
            DimensionResult,
        ]
        for model in models:
            assert hasattr(model, "__tablename__"), f"{model.__name__} missing __tablename__"

    def test_all_tables_registered_in_metadata(self):
        expected_tables = {
            "users",
            "projects",
            "revoked_tokens",
            "user_configs",
            "system_configs",
            "project_configs",
            "report_templates",
            "requirement_documents",
            "analysis_tasks",
            "reports",
            "uploaded_files",
            "pending_changes",
            "synonym_mappings",
            "report_versions",
            "report_chats",
            "llm_call_logs",
            "mcp_access_keys",
            "requirement_releases",
            "mcp_tool_calls",
            "cognitive_sessions",
            "events",
            "checkpoints",
            "evidence_records",
            "evidence_relations",
            "dimension_results",
        }
        actual_tables = set(Base.metadata.tables.keys())
        assert expected_tables.issubset(
            actual_tables
        ), f"Missing: {expected_tables - actual_tables}"

    def test_total_table_count(self):
        assert len(Base.metadata.tables) == 33


class TestUserModel:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )
        db_session.add(user)
        await db_session.flush()
        assert user.id is not None

    @pytest.mark.asyncio
    async def test_user_defaults(self, db_session: AsyncSession):
        user = User(
            username="defaults",
            email="defaults@example.com",
            hashed_password="hashed",
        )
        db_session.add(user)
        await db_session.flush()
        assert user.is_active is True
        assert user.is_superuser is False


class TestProjectModel:
    @pytest.mark.asyncio
    async def test_create_project(self, db_session: AsyncSession):
        user = User(username="owner", email="owner@example.com", hashed_password="hashed")
        db_session.add(user)
        await db_session.flush()

        project = Project(name="Test Project", owner_id=user.id)
        db_session.add(project)
        await db_session.flush()
        assert project.id is not None

    @pytest.mark.asyncio
    async def test_project_owner_relationship(self, db_session: AsyncSession):
        user = User(username="rel_user", email="rel@example.com", hashed_password="hashed")
        db_session.add(user)
        await db_session.flush()

        project = Project(name="Rel Project", owner_id=user.id)
        db_session.add(project)
        await db_session.flush()

        assert project.owner.username == "rel_user"


class TestCognitiveSessionModel:
    @pytest.mark.asyncio
    async def test_create_session(self, db_session: AsyncSession):
        user = User(username="sess_user", email="sess@example.com", hashed_password="hashed")
        db_session.add(user)
        await db_session.flush()

        project = Project(name="Sess Project", owner_id=user.id)
        db_session.add(project)
        await db_session.flush()

        session = CognitiveSession(
            project_id=project.id,
            user_id=user.id,
            config={"context_strategy": "default"},
        )
        db_session.add(session)
        await db_session.flush()
        assert session.session_id is not None
        assert session.status == "CREATED"


class TestEventModel:
    @pytest.mark.asyncio
    async def test_create_event(self, db_session: AsyncSession):
        user = User(username="evt_user", email="evt@example.com", hashed_password="hashed")
        db_session.add(user)
        await db_session.flush()

        project = Project(name="Evt Project", owner_id=user.id)
        db_session.add(project)
        await db_session.flush()

        session = CognitiveSession(project_id=project.id, user_id=user.id, config={})
        db_session.add(session)
        await db_session.flush()

        from datetime import UTC, datetime

        event = Event(
            session_id=session.session_id,
            sequence=1,
            event_type="SESSION_CREATED",
            event_level="session",
            timestamp=datetime.now(UTC),
            producer="test",
        )
        db_session.add(event)
        await db_session.flush()
        assert event.event_id is not None


class TestCheckpointModel:
    @pytest.mark.asyncio
    async def test_create_checkpoint(self, db_session: AsyncSession):
        user = User(username="cp_user", email="cp@example.com", hashed_password="hashed")
        db_session.add(user)
        await db_session.flush()

        project = Project(name="CP Project", owner_id=user.id)
        db_session.add(project)
        await db_session.flush()

        session = CognitiveSession(project_id=project.id, user_id=user.id, config={})
        db_session.add(session)
        await db_session.flush()

        checkpoint = Checkpoint(
            session_id=session.session_id,
            version=1,
            type="STEP_COMPLETE",
            state_summary={"step": 1},
        )
        db_session.add(checkpoint)
        await db_session.flush()
        assert checkpoint.checkpoint_id is not None


class TestSystemConfigModel:
    @pytest.mark.asyncio
    async def test_create_system_config(self, db_session: AsyncSession):
        config = SystemConfig(
            config_key="session.max_steps",
            config_value="50",
            value_type="integer",
        )
        db_session.add(config)
        await db_session.flush()
        assert config.id is not None


class TestEnumDefaults:
    def test_task_status_default_pending(self):
        assert TaskStatus.PENDING == "pending"

    def test_release_status_default_draft(self):
        assert ReleaseStatus.DRAFT == "draft"
