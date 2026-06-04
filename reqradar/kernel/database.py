"""数据库基类与会话工厂 — SQLAlchemy 声明式基类和引擎创建。"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类，所有 V2 ORM 模型继承此类。"""

    pass


def create_engine(url: str, pool_size: int = 5, max_overflow: int = 10):
    """创建异步数据库引擎，自动适配 SQLite 和 PostgreSQL。

    Args:
        url: 数据库连接 URL
        pool_size: 连接池大小（仅 PostgreSQL）
        max_overflow: 溢出连接数（仅 PostgreSQL）

    Returns:
        AsyncEngine 实例
    """
    is_sqlite = url.startswith("sqlite")

    engine_kwargs: dict = {"echo": False}

    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_size"] = pool_size
        engine_kwargs["max_overflow"] = max_overflow
        engine_kwargs["pool_pre_ping"] = True

    engine = create_async_engine(url, **engine_kwargs)

    if is_sqlite:

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """创建异步会话工厂。

    Args:
        engine: SQLAlchemy 异步引擎

    Returns:
        async_sessionmaker 实例
    """
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
