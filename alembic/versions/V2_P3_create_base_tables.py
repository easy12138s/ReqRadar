"""创建 V2 基础表（19 张）。

Revision ID: c1a2b3d4e5f6
Revises: None
Create Date: 2026-06-08

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import reqradar.kernel.models  # noqa: F401
    from reqradar.kernel.database import Base

    op.run_sync(Base.metadata.create_all)


def downgrade() -> None:
    import reqradar.kernel.models  # noqa: F401
    from reqradar.kernel.database import Base

    op.run_sync(Base.metadata.drop_all)
