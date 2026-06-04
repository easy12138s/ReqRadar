"""Bug 记录器 — 在测试中发现的项目 bug 用 xfail 标记。

用法:
    from tests.helpers.bug_recorder import known_bug

    @known_bug("BUG-1", "简短标题")
    async def test_something():
        ...
"""

from __future__ import annotations

import pytest


def known_bug(bug_id: str, title: str):
    return pytest.mark.xfail(reason=f"{bug_id}: {title}")
