"""Kernel 数据库基类和会话工厂的单元测试。"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reqradar.kernel.database import Base, create_engine, create_session_factory


class TestBase:
    def test_base_is_declarative_base(self):
        assert hasattr(Base, "metadata")

    def test_base_metadata_is_valid(self):
        assert hasattr(Base.metadata, "tables")
        assert hasattr(Base.metadata, "create_all")


class TestCreateEngine:
    def test_sqlite_engine_creation(self, tmp_path):
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
        assert engine is not None
        assert str(engine.url).startswith("sqlite")

    def test_sqlite_engine_with_custom_pool_size(self, tmp_path):
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite+aiosqlite:///{db_path}", pool_size=10)
        assert engine is not None


class TestCreateSessionFactory:
    def test_factory_returns_async_sessionmaker(self, tmp_path):
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
        factory = create_session_factory(engine)
        assert isinstance(factory, async_sessionmaker)

    def test_factory_can_create_session(self, tmp_path):
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
        factory = create_session_factory(engine)
        session = factory()
        assert isinstance(session, AsyncSession)
        session.sync_session.close()


@pytest.mark.asyncio
async def test_sqlite_pragma_set(tmp_path):
    db_path = tmp_path / "pragma_test.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    factory = create_session_factory(engine)

    async with factory() as session:
        result = await session.execute(text("PRAGMA foreign_keys"))
        fk_value = result.scalar()
        assert fk_value == 1
