import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI

logger = logging.getLogger("reqradar.web.app")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, update

from reqradar.core.exceptions import ReqRadarException
from reqradar.web.api.auth import router as auth_router, SECRET_KEY as AUTH_SECRET_KEY, ALGORITHM
from reqradar.web.api.projects import router as projects_router
from reqradar.web.api.analyses import router as analyses_router
from reqradar.web.api.reports import router as reports_router
from reqradar.web.api.memory import router as memory_router
from reqradar.web.api.configs import router as configs_router
from reqradar.web.api.synonyms import router as synonyms_router
from reqradar.web.api.templates import router as templates_router
from reqradar.web.api.profile import router as profile_router
from reqradar.web.api.chatback import router as chatback_router
from reqradar.web.api.users import router as users_router
from reqradar.web.api.versions import router as versions_router
from reqradar.web.api.evidence_api import router as evidence_router
from reqradar.web.api.requirements import router as requirements_router
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.dependencies import async_session_factory, CurrentUser, DbSession
from reqradar.web.exceptions import reqradar_exception_handler
from reqradar.web.middleware.rate_limit import RateLimitMiddleware
from reqradar.web.models import AnalysisTask, Project
from reqradar.web.enums import TaskStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module
    import reqradar.infrastructure.config as config_module

    config = config_module.load_config()
    web_config = config.web

    engine = create_engine(
        web_config.database_url,
        pool_size=web_config.db_pool_size,
        max_overflow=web_config.db_pool_max_overflow,
    )
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = web_config.secret_key
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = web_config.access_token_expire_minutes
    app.state.secret_key = web_config.secret_key

    if web_config.secret_key == "change-me-in-production" and not web_config.debug:
        logger.warning(
            "Using default JWT secret key — not secure for production! "
            "Set REQRADAR_SECRET_KEY env var or web.secret_key in .reqradar.yaml"
        )

    from sqlalchemy import inspect

    async with engine.begin() as conn:
        def _check_tables(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()

        existing_tables = await conn.run_sync(_check_tables)
        if not existing_tables:
            logger.warning(
                "Database tables not found — auto-creating. "
                "Use Alembic migrations in production."
            )
            await conn.run_sync(Base.metadata.create_all)
        elif web_config.auto_create_tables:
            logger.warning("auto_create_tables is enabled — use Alembic migrations in production")
            await conn.run_sync(Base.metadata.create_all)

    try:
        async with session_factory() as session:
            await session.execute(
                update(AnalysisTask)
                .where(AnalysisTask.status == TaskStatus.RUNNING)
                .values(status=TaskStatus.FAILED, error_message="Server restarted during analysis")
            )
            await session.commit()
    except Exception:
        logger.debug("No RUNNING tasks to recover or table not yet created")

    from reqradar.web.seed import seed_all

    async with session_factory() as seed_session:
        await seed_all(seed_session)

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.config = config

    from reqradar.web.services.analysis_runner import runner

    runner._semaphore = asyncio.Semaphore(web_config.max_concurrent_analyses)
    runner.session_factory = session_factory

    yield

    await engine.dispose()


def create_app(config_path: Optional[Path] = None):
    import reqradar.infrastructure.config as config_module

    if config_path is not None:
        original_load = config_module.load_config

        def _load_with_path():
            return original_load(config_path)

        config_module.load_config = _load_with_path

    config = config_module.load_config()
    cors_origins = config.web.cors_origins if hasattr(config.web, "cors_origins") else None
    if cors_origins and isinstance(cors_origins, str):
        import json

        try:
            cors_origins = json.loads(cors_origins)
        except json.JSONDecodeError:
            cors_origins = [cors_origins]
    if not cors_origins:
        if config.web.debug:
            cors_origins = ["*"]
        else:
            cors_origins = [
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]

    app = FastAPI(title="ReqRadar", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    app.add_exception_handler(ReqRadarException, reqradar_exception_handler)

    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(analyses_router)
    app.include_router(reports_router)
    app.include_router(memory_router)
    app.include_router(configs_router)
    app.include_router(synonyms_router)
    app.include_router(templates_router)
    app.include_router(profile_router)
    app.include_router(chatback_router)
    app.include_router(versions_router)
    app.include_router(evidence_router)
    app.include_router(requirements_router)
    app.include_router(users_router)

    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/app/assets", StaticFiles(directory=str(static_path / "assets")), name="assets")

    @app.get("/app")
    @app.get("/app/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        index_file = static_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"detail": "Not found"}

    @app.get("/health")
    async def health():
        db_ok = False
        try:
            async with app.state.session_factory() as session:
                await session.execute(select(1))
                db_ok = True
        except Exception:
            pass

        status_val = "ok" if db_ok else "degraded"
        return {"status": status_val, "database": db_ok}

    @app.get("/api/metrics")
    async def metrics(current_user: CurrentUser, db: DbSession):
        project_count = (await db.execute(select(func.count(Project.id)))).scalar_one()
        task_counts = {}
        for status in ("pending", "running", "completed", "failed"):
            task_counts[status] = (
                await db.execute(
                    select(func.count(AnalysisTask.id)).where(AnalysisTask.status == status)
                )
            ).scalar_one()
        return {"project_count": project_count, "task_counts": task_counts}

    return app
