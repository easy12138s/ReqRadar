from pathlib import Path

import pytest

from reqradar.infrastructure.config import Config, HomeConfig, WebConfig

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_FIXED_DATA = _PROJECT_ROOT / "tmp_test_data"


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """覆盖默认 test_config，将数据目录固定到项目根目录下的 tmp_test_data/。"""
    data_root = _FIXED_DATA / "data"
    reports_path = _FIXED_DATA / "reports"
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
