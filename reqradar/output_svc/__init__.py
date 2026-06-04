"""output_svc — 输出服务，报告渲染与版本管理。"""

from __future__ import annotations

from reqradar.output_svc.report import ReportRenderer, _risk_level_to_badge

__all__ = [
    "ReportRenderer",
    "_risk_level_to_badge",
]
