from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from reqradar.core.exceptions import ReqRadarException
from reqradar.infrastructure.config import load_config
from reqradar.web.api.auth import router as auth_router, SECRET_KEY as AUTH_SECRET_KEY, ALGORITHM
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.dependencies import async_session_factory
from reqradar.web.exceptions import reqradar_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module

    config = load_config()
    web_config = config.web

    engine = create_engine(web_config.database_url)
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = web_config.secret_key
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = web_config.access_token_expire_minutes

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.config = config

    yield

    await engine.dispose()


def create_app(config_path: Optional[Path] = None):
    if config_path is not None:
        import reqradar.infrastructure.config as config_module

        original_load = config_module.load_config

        def _load_with_path():
            return original_load(config_path)

        config_module.load_config = _load_with_path

    app = FastAPI(title="ReqRadar", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ReqRadarException, reqradar_exception_handler)

    app.include_router(auth_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app