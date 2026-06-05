"""基础设施层日志上下文管理。"""

from __future__ import annotations

import contextvars
import logging

_logger = logging.getLogger(__name__)

_session_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")


def set_log_context(session_id: str) -> None:
    """设置日志上下文（Session ID）。

    通过 contextvars 绑定 session_id，供后续日志格式化使用。
    """
    _session_id_ctx.set(session_id)


def clear_log_context() -> None:
    """清除日志上下文。"""
    _session_id_ctx.set("")


def get_session_id() -> str:
    """获取当前日志上下文中的 Session ID。"""
    return _session_id_ctx.get("")
