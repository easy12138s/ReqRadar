from pathlib import Path

import pytest

from reqradar.infrastructure.config import Config, HomeConfig, WebConfig


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """覆盖默认 test_config，所有数据写入 tmp_path 隔离目录。"""
    data_root = tmp_path / "data"
    reports_path = tmp_path / "reports"
    data_root.mkdir(parents=True, exist_ok=True)
    reports_path.mkdir(parents=True, exist_ok=True)
    return Config(
        home=HomeConfig(path=str(tmp_path / "home")),
        web=WebConfig(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
            secret_key="change-me-in-production",
            debug=True,
            auto_create_tables=False,
            data_root=str(data_root),
            reports_path=str(reports_path),
            max_upload_size=50,
        ),
    )
