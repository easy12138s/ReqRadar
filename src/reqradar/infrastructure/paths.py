import os
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from reqradar.infrastructure.config import Config

logger = logging.getLogger("reqradar.paths")


def resolve_home(config: Config) -> Path:
    home = Path(os.path.expanduser(config.home.path)).resolve()
    home.mkdir(parents=True, exist_ok=True)
    return home


def get_paths(config: Config) -> dict:
    home = resolve_home(config)

    def _resolve(configured: str, default: Path) -> Path:
        if configured and Path(configured).is_absolute():
            p = Path(os.path.expanduser(configured))
            p.mkdir(parents=True, exist_ok=True)
            return p
        p = default
        p.mkdir(parents=True, exist_ok=True)
        return p

    return {
        "home": home,
        "database": home / "reqradar.db",
        "projects": _resolve(config.web.data_root, home / "projects"),
        "memories": _resolve(config.memory.storage_path, home / "memories"),
        "reports": _resolve(config.web.reports_path, home / "reports"),
        "models": _resolve(config.index.model_cache, home / "models"),
        "log_dir": home / "logs",
    }


def derive_database_url(config: Config) -> str:
    if config.web.database_url:
        parsed = urlparse(config.web.database_url)
        if ":memory:" not in config.web.database_url and parsed.scheme.startswith("sqlite"):
            db_path = Path(parsed.path.lstrip("/"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return config.web.database_url
    paths = get_paths(config)
    db_path = paths["database"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"
