import os
from pathlib import Path
from reqradar.infrastructure.config import Config
from reqradar.infrastructure.paths import get_paths, derive_database_url, resolve_home, ensure_dirs


def test_resolve_home_returns_path(tmp_path):
    config = Config(home={"path": str(tmp_path / "test_home")})
    home = resolve_home(config)
    assert home == (tmp_path / "test_home").resolve()


def test_ensure_dirs_creates_directories(tmp_path):
    config = Config(home={"path": str(tmp_path / "rh")})
    paths = get_paths(config)
    for key in ("projects", "memories", "reports", "models"):
        assert not paths[key].exists()
    ensure_dirs(paths)
    for key in ("projects", "memories", "reports", "models", "log_dir"):
        assert paths[key].exists()


def test_get_paths_derives_from_home(tmp_path):
    config = Config(home={"path": str(tmp_path / "rh")})
    paths = get_paths(config)
    assert paths["home"] == (tmp_path / "rh").resolve()
    assert paths["projects"] == (tmp_path / "rh" / "projects")
    assert paths["memories"] == (tmp_path / "rh" / "memories")
    assert paths["reports"] == (tmp_path / "rh" / "reports")
    assert paths["models"] == (tmp_path / "rh" / "models")
    assert paths["database"] == (tmp_path / "rh" / "reqradar.db")


def test_get_paths_explicit_absolute_overrides(tmp_path):
    explicit = str(tmp_path / "custom_projects")
    config = Config(home={"path": str(tmp_path / "rh")}, web={"data_root": explicit})
    paths = get_paths(config)
    assert paths["projects"] == tmp_path / "custom_projects"


def test_get_paths_relative_uses_default(tmp_path):
    config = Config(home={"path": str(tmp_path / "rh")}, web={"data_root": "relative/path"})
    paths = get_paths(config)
    assert paths["projects"] == (tmp_path / "rh" / "projects")


def test_derive_database_url_empty_uses_home(tmp_path):
    config = Config(home={"path": str(tmp_path / "rh")}, web={"database_url": ""})
    url = derive_database_url(config)
    assert str(tmp_path / "rh" / "reqradar.db") in url
    assert url.startswith("sqlite+aiosqlite:///")


def test_derive_database_url_explicit_non_sqlite(tmp_path):
    config = Config(
        home={"path": str(tmp_path / "rh")},
        web={"database_url": "postgresql+asyncpg://user:pass@localhost/db"},
    )
    url = derive_database_url(config)
    assert url == "postgresql+asyncpg://user:pass@localhost/db"


def test_derive_database_url_memory(tmp_path):
    config = Config(
        home={"path": str(tmp_path / "rh")}, web={"database_url": "sqlite+aiosqlite:///:memory:"}
    )
    url = derive_database_url(config)
    assert url == "sqlite+aiosqlite:///:memory:"
