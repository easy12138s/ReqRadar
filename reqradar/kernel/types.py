"""共享类型定义 — 被所有 V2 服务引用的最小类型集合。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class ContextKind(str, Enum):
    """上下文来源类型，用于 Context Pipeline 的 Collect 和 Score 阶段。"""

    SOURCE_CODE = "SOURCE_CODE"
    REQUIREMENT = "REQUIREMENT"
    ARCH_DOC = "ARCH_DOC"
    GIT_HISTORY = "GIT_HISTORY"
    MEMORY = "MEMORY"
    INFERRED_KNOWLEDGE = "INFERRED_KNOWLEDGE"


class Scope(str, Enum):
    """配置作用域，决定配置的优先级层次。"""

    GLOBAL = "global"
    PROJECT = "project"
    USER = "user"


class Domain(str, Enum):
    """配置业务域，用于 Scope×Domain 配置矩阵。"""

    SESSION = "session"
    EVENT = "event"
    CHECKPOINT = "checkpoint"
    EVIDENCE = "evidence"
    LLM = "llm"
    TOOL = "tool"
    CONTEXT = "context"
    L3 = "l3"


@dataclass(frozen=True)
class TokenBudget:
    """Token 预算约束，用于 Context Pipeline 的 Select 阶段。"""

    total: int
    reserved: int = 0

    @property
    def available(self) -> int:
        """可用 Token 数量（总数减去预留）。"""
        return max(0, self.total - self.reserved)


@dataclass
class ContextItem:
    """上下文条目，Context Pipeline 的基本数据单元。"""

    content: str
    kind: ContextKind
    source_uri: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def context_kind(self) -> ContextKind:
        """兼容别名 — Pipeline 使用 context_kind 访问。"""
        return self.kind


@dataclass
class ScoredContextItem:
    """评分后的上下文条目，用于 Select 阶段。"""

    item: ContextItem
    score: float = 0.0
    token_count: int = 0


@runtime_checkable
class ContextSourceProtocol(Protocol):
    """上下文数据源协议，定义 Context Pipeline Collect 阶段的数据源接口。"""

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        max_items: int = 50,
    ) -> list[ContextItem]:
        """从数据源收集上下文条目。"""
        ...

    def supported_kind(self) -> ContextKind:
        """返回该数据源提供的 ContextKind。"""
        ...

    def is_available(self, project_id: str) -> bool:
        """检查该数据源对指定项目是否可用。"""
        ...


@runtime_checkable
class ContextStrategyProtocol(Protocol):
    """上下文策略协议，定义 Context Pipeline 各阶段的参数配置接口。"""

    def get_source_budgets(self) -> dict[ContextKind, int]:
        """返回每个 ContextKind 的 max_items 预算。"""
        ...

    def get_score_weights(self) -> dict[str, float]:
        """返回 Score 阶段权重 {w1_semantic, w2_time_decay, w3_user_mark, w4_context_kind}。"""
        ...

    def get_select_min_score(self) -> float:
        """返回 Select 阶段的最低分数阈值。"""
        ...

    def get_quality_gate_thresholds(self) -> dict[str, float]:
        """返回 Quality Gate 阈值。"""
        ...
