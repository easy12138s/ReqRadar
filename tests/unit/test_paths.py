"""基础设施路径管理单元测试"""

import os
from pathlib import Path

import pytest
from unittest.mock import patch

from reqradar.infrastructure.config import Config, HomeConfig, WebConfig
from reqradar.infrastructure.paths import derive_database_url, ensure_dirs, get_paths, resolve_home


@pytest.fixture
def base_config(tmp_path: Path) -> Config:
    return Config(
        home=HomeConfig(path=str(tmp_path / "home")),
        web=WebConfig(
            database_url="",
            data_root="",
            reports_path="",
        ),
    )


class TestResolveHome:
    def test_expands_tilde(self):
        config = Config(home=HomeConfig(path="~/.test"))
        home = resolve_home(config)
        assert str(home) != "~/.test"
        assert home.is_absolute()

    def test_resolves_relative(self, tmp_path: Path):
        rel = tmp_path / "relative"
        config = Config(home=HomeConfig(path=str(rel)))
        home = resolve_home(config)
        assert home.is_absolute()

    def test_keeps_absolute(self, tmp_path: Path):
        config = Config(home=HomeConfig(path=str(tmp_path)))
        home = resolve_home(config)
        assert home == tmp_path.resolve()


class TestGetPaths:
    def test_returns_all_required_keys(self, base_config):
        paths = get_paths(base_config)
        required = {"home", "database", "projects", "memories", "reports", "models", "log_dir"}
        assert required.issubset(set(paths.keys()))

    def test_defaults_to_subdirs_of_home(self, base_config):
        paths = get_paths(base_config)
        assert paths["database"] == paths["home"] / "reqradar.db"
        assert paths["projects"] == paths["home"] / "projects"
        assert paths["reports"] == paths["home"] / "reports"

    def test_custom_data_root(self, base_config, tmp_path: Path):
        custom = str(tmp_path / "custom_projects")
        base_config.web.data_root = custom
        paths = get_paths(base_config)
        assert str(paths["projects"]) == os.path.expanduser(custom)

    def test_custom_reports_path(self, base_config, tmp_path: Path):
        custom = str(tmp_path / "custom_reports")
        base_config.web.reports_path = custom
        paths = get_paths(base_config)
        assert str(paths["reports"]) == os.path.expanduser(custom)


class TestEnsureDirs:
    def test_creates_missing_dirs(self, base_config):
        paths = get_paths(base_config)
        for p in paths.values():
            if p.exists():
                p.rmdir() if p.is_dir() else p.unlink()
        ensure_dirs(paths)
        for key in ("home", "projects", "memories", "reports", "models", "log_dir"):
            assert paths[key].is_dir()

    def test_idempotent(self, base_config):
        paths = get_paths(base_config)
        ensure_dirs(paths)
        ensure_dirs(paths)


class TestDeriveDatabaseUrl:
    def test_returns_explicit_url(self, base_config):
        base_config.web.database_url = "sqlite+aiosqlite:///test.db"
        url = derive_database_url(base_config)
        assert url == "sqlite+aiosqlite:///test.db"

    def test_in_memory_url_passthrough(self, base_config):
        base_config.web.database_url = "sqlite+aiosqlite:///:memory:"
        url = derive_database_url(base_config)
        assert ":memory:" in url

    def test_falls_back_to_default_path(self, base_config):
        base_config.web.database_url = ""
        url = derive_database_url(base_config)
        assert "reqradar.db" in url
        assert "sqlite+aiosqlite" in url

    def test_creates_parent_dir_for_sqlite(self, base_config, tmp_path: Path):
        db_file = str(tmp_path / "sub" / "test.db")
        base_config.web.database_url = f"sqlite+aiosqlite:///{db_file}"
        derive_database_url(base_config)
        assert (tmp_path / "sub").is_dir()
