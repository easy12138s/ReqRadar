from __future__ import annotations

from reqradar.kernel.types import ContextKind


class RiskAnalysisStrategy:
    """风险分析策略 — 偏好代码证据、Git 历史、L3 风险记忆"""

    def get_source_budgets(self) -> dict[ContextKind, int]:
        """返回每种 ContextKind 的 max_items 预算"""
        return {
            ContextKind.SOURCE_CODE: 20,
            ContextKind.GIT_HISTORY: 15,
            ContextKind.MEMORY: 10,
            ContextKind.REQUIREMENT: 10,
        }

    def get_score_weights(self) -> dict[str, float]:
        """返回 Score 阶段的权重配置"""
        return {
            "w1": 0.35,
            "w2": 0.2,
            "w3": 0.1,
            "w4": 0.35,
        }

    def get_select_min_score(self) -> float:
        """返回 Select 阶段最低得分阈值"""
        return 0.35

    def get_quality_gate_thresholds(self) -> dict[str, float]:
        """返回 Quality Gate 阈值"""
        return {
            "min_items": 3,
            "min_semantic_score": 0.65,
            "min_code_evidence": 1,
        }


class ArchitectureUnderstandingStrategy:
    """架构理解策略 — 偏好架构文档、代码依赖、L3 约束"""

    def get_source_budgets(self) -> dict[ContextKind, int]:
        """返回每种 ContextKind 的 max_items 预算"""
        return {
            ContextKind.SOURCE_CODE: 15,
            ContextKind.REQUIREMENT: 10,
            ContextKind.ARCH_DOC: 15,
            ContextKind.MEMORY: 15,
            ContextKind.GIT_HISTORY: 5,
        }

    def get_score_weights(self) -> dict[str, float]:
        """返回 Score 阶段的权重配置"""
        return {
            "w1": 0.45,
            "w2": 0.1,
            "w3": 0.15,
            "w4": 0.3,
        }

    def get_select_min_score(self) -> float:
        """返回 Select 阶段最低得分阈值"""
        return 0.25

    def get_quality_gate_thresholds(self) -> dict[str, float]:
        """返回 Quality Gate 阈值"""
        return {
            "min_items": 2,
            "min_semantic_score": 0.6,
            "min_code_evidence": 1,
        }
