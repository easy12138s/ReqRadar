"""CLI 共享工具函数"""

import asyncio

from reqradar.infrastructure.config import Config
from reqradar.web.database import Base, create_engine, create_session_factory


def get_db_session(config: Config):
    engine = create_engine(config.web.database_url)

    async def _ensure_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_ensure_tables())

    session_factory = create_session_factory(engine)
    return engine, session_factory


async def close_db(engine):
    await engine.dispose()
