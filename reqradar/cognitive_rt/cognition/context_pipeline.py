"""Context Pipeline — 五阶段上下文管线（Collect → Score → Select → Compress → Assemble）。

Context Pipeline 是 ReqRadar V2 认知运行时的核心组件，
负责将多源上下文片段经过评分、选择、压缩、组装后
注入 LLM 推理循环，确保输出严格满足 Token 预算约束。
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import defaultdict
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from reqradar.kernel.exceptions import ContextBudgetExceededException
from reqradar.kernel.types import ContextKind

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ContextKind 基础权重
# ---------------------------------------------------------------------------

CONTEXT_KIND_WEIGHTS: dict[ContextKind, float] = {
    ContextKind.SOURCE_CODE: 1.0,
    ContextKind.REQUIREMENT: 0.95,
    ContextKind.ARCH_DOC: 0.9,
    ContextKind.GIT_HISTORY: 0.7,
    ContextKind.MEMORY: 0.6,
    ContextKind.INFERRED_KNOWLEDGE: 0.4,
}

# ContextKind 默认半衰期（天）
_DEFAULT_HALF_LIFE: dict[ContextKind, float] = {
    ContextKind.SOURCE_CODE: 90.0,
    ContextKind.REQUIREMENT: 180.0,
    ContextKind.ARCH_DOC: 120.0,
    ContextKind.GIT_HISTORY: 30.0,
    ContextKind.MEMORY: 60.0,
    ContextKind.INFERRED_KNOWLEDGE: 7.0,
}

# Assemble 阶段中 ContextKind 的展示顺序
_ASSEMBLE_KIND_ORDER: list[ContextKind] = [
    ContextKind.REQUIREMENT,
    ContextKind.SOURCE_CODE,
    ContextKind.ARCH_DOC,
    ContextKind.GIT_HISTORY,
    ContextKind.MEMORY,
    ContextKind.INFERRED_KNOWLEDGE,
]

# Assemble 阶段的 ContextKind 分组标题
_KIND_SECTION_TITLES: dict[ContextKind, str] = {
    ContextKind.REQUIREMENT: "Requirement Context",
    ContextKind.SOURCE_CODE: "Code Context",
    ContextKind.ARCH_DOC: "Architecture Context",
    ContextKind.GIT_HISTORY: "Git History Context",
    ContextKind.MEMORY: "Memory Context",
    ContextKind.INFERRED_KNOWLEDGE: "Inferred Knowledge",
}

# ---------------------------------------------------------------------------
# Pydantic 数据模型
# ---------------------------------------------------------------------------


class ScoredContextItem(BaseModel):
    """Score 阶段输出 — 携带综合评分的上下文条目。"""

    item_id: str = Field(description="条目唯一标识")
    context_kind: ContextKind = Field(description="上下文类型")
    source_name: str = Field(description="来源适配器名称")
    content: str = Field(description="上下文内容文本")
    token_count: int = Field(default=0, ge=0, description="Token 数量")
    composite_score: float = Field(ge=0.0, le=1.0, description="综合得分")
    semantic_similarity: float = Field(default=0.0, ge=0.0, le=1.0, description="语义相似度")
    time_decay: float = Field(default=1.0, ge=0.0, le=1.0, description="时间衰减值")
    final_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="ContextKind 最终权重")
    metadata: dict = Field(default_factory=dict, description="元数据")
    timestamp: datetime | None = Field(default=None, description="内容时间戳")
    l3_confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="L3 知识置信度")
    content_hash: str = Field(default="", description="内容哈希, 用于去重")


class CompressedContextItem(BaseModel):
    """Compress 阶段输出 — 压缩后的上下文条目。"""

    item_id: str = Field(description="原始条目 ID")
    context_kind: ContextKind = Field(description="上下文类型")
    source_name: str = Field(description="来源适配器名称")
    content: str = Field(description="压缩后的内容")
    token_count: int = Field(default=0, ge=0, description="压缩后的 Token 数")
    composite_score: float = Field(ge=0.0, le=1.0, description="综合得分")
    compressed: bool = Field(default=False, description="是否经过压缩")
    compression_method: str = Field(default="", description="压缩方法")
    original_token_count: int = Field(default=0, ge=0, description="压缩前的 Token 数")
    metadata: dict = Field(default_factory=dict, description="元数据")


class QualityGateResult(BaseModel):
    """Quality Gate 检查结果。"""

    passed: bool = Field(description="是否通过质量检查")
    total_items: int = Field(description="有效上下文条目总数")
    max_semantic_score: float = Field(default=0.0, description="最高语义得分")
    code_evidence_count: int = Field(default=0, description="代码证据数")
    low_context_confidence: bool = Field(
        default=False, description="是否进入 LOW_CONTEXT_CONFIDENCE 模式"
    )
    failures: list[str] = Field(default_factory=list, description="未通过的检查项列表")


class PipelineResult(BaseModel):
    """Pipeline 执行结果。"""

    context: str = Field(description="组装后的最终上下文文本")
    token_count: int = Field(ge=0, description="实际 Token 数")
    budget: int = Field(ge=0, description="Token 预算")
    items_count: int = Field(ge=0, description="包含的上下文条目数")
    quality_gate_result: QualityGateResult = Field(description="Quality Gate 检查结果")
    strategy_name: str = Field(description="使用的策略名称")


# ---------------------------------------------------------------------------
# Token 计数器
# ---------------------------------------------------------------------------


class TokenCounter:
    """Token 计数器 — 优先使用 tiktoken，降级为字符数估算。"""

    def __init__(self) -> None:
        self._encoder: object | None = None
        try:
            import tiktoken

            self._encoder = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            logger.warning("tiktoken 不可用, 降级使用字符数估算(1 token ≈ 4 字符)")

    def count(self, text: str) -> int:
        """计算文本的 Token 数量。

        Args:
            text: 待计数的文本

        Returns:
            Token 数量
        """
        if not text:
            return 0
        if self._encoder is not None:
            return len(self._encoder.encode(text))  # type: ignore[union-attr]
        return max(1, len(text) // 4)

    def count_items(self, items: list[ScoredContextItem | CompressedContextItem]) -> int:
        """统计条目列表的总 Token 数。

        Args:
            items: 上下文条目列表

        Returns:
            总 Token 数
        """
        return sum(item.token_count for item in items)


# ---------------------------------------------------------------------------
# Quality Gate
# ---------------------------------------------------------------------------


class QualityGate:
    """Quality Gate 质量检查器 — Collect 之后、Score 之前执行。"""

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        """初始化 Quality Gate。

        Args:
            thresholds: 自定义阈值，缺省使用 min_items=2,
                        min_semantic_score=0.65, min_code_evidence=1
        """
        self.thresholds: dict[str, float] = thresholds or {
            "min_items": 2,
            "min_semantic_score": 0.65,
            "min_code_evidence": 1,
        }

    def check(self, items: list[dict]) -> QualityGateResult:
        """执行 Quality Gate 检查。

        Args:
            items: Collect 阶段产出的上下文条目列表（字典形式），
                   每个字典至少包含 context_kind 和 metadata 字段

        Returns:
            QualityGateResult 检查结果
        """
        failures: list[str] = []

        total_items = len(items)
        min_items = int(self.thresholds["min_items"])
        if total_items < min_items:
            failures.append(f"有效 context 条目数 {total_items} < {min_items}")

        max_semantic = max(
            (item.get("metadata", {}).get("retrieval_score", 0.0) for item in items),
            default=0.0,
        )
        min_semantic = self.thresholds["min_semantic_score"]
        if max_semantic < min_semantic:
            failures.append(f"最高语义得分 {max_semantic:.2f} < {min_semantic:.2f}")

        code_count = sum(1 for item in items if item.get("context_kind") == ContextKind.SOURCE_CODE)
        min_code = int(self.thresholds["min_code_evidence"])
        if code_count < min_code:
            failures.append(f"代码证据数 {code_count} < {min_code}")

        passed = len(failures) == 0
        return QualityGateResult(
            passed=passed,
            total_items=total_items,
            max_semantic_score=max_semantic,
            code_evidence_count=code_count,
            low_context_confidence=not passed,
            failures=failures,
        )


# ---------------------------------------------------------------------------
# 评分函数
# ---------------------------------------------------------------------------


def compute_time_decay(
    item_timestamp: datetime | None,
    now: datetime,
    half_life_days: float = 30.0,
) -> float:
    """指数时间衰减函数。

    Args:
        item_timestamp: 上下文条目的时间戳
        now: 当前时间
        half_life_days: 半衰期（天），默认 30 天

    Returns:
        衰减系数，范围 (0.0, 1.0]
    """
    if item_timestamp is None:
        return 1.0
    age_days = (now - item_timestamp).total_seconds() / 86400.0
    if age_days < 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def compute_final_weight(
    context_kind: ContextKind,
    l3_confidence: float | None = None,
) -> float:
    """计算 ContextKind 的最终权重。

    权重叠加规则：MEMORY 类型若携带 l3_confidence 则乘以该置信度。

    Args:
        context_kind: 上下文类型
        l3_confidence: L3 知识置信度（仅 MEMORY 类型适用）

    Returns:
        最终权重，范围 [0.0, 1.0]
    """
    base_weight = CONTEXT_KIND_WEIGHTS[context_kind]
    if l3_confidence is not None and context_kind == ContextKind.MEMORY:
        return base_weight * l3_confidence
    return base_weight


def compute_content_hash(content: str) -> str:
    """计算内容的 SHA-256 哈希值（前 16 位十六进制）。

    Args:
        content: 文本内容

    Returns:
        哈希摘要字符串
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def score_items(
    items: list,
    query_embedding: list[float] | None = None,
    weights: dict[str, float] | None = None,
    now: datetime | None = None,
) -> list[ScoredContextItem]:
    """对 Collect 阶段产出的条目进行综合评分。

    综合得分 = semantic_similarity × w1 + time_decay × w2
            + user_mark × w3 + final_weight × w4

    Args:
        items: Collect 阶段产出的条目列表（需含 content / context_kind /
               source_name / metadata / timestamp 等属性或键）
        query_embedding: 查询向量嵌入（用于语义相似度计算）
        weights: 自定义权重 {w1, w2, w3, w4}
        now: 当前时间，缺省为 datetime.now(UTC)

    Returns:
        评分后的 ScoredContextItem 列表
    """
    w = weights or {"w1": 0.4, "w2": 0.15, "w3": 0.15, "w4": 0.3}
    w1 = w.get("w1", 0.4)
    w2 = w.get("w2", 0.15)
    w3 = w.get("w3", 0.15)
    w4 = w.get("w4", 0.3)
    current_time = now or datetime.now(UTC)

    scored: list[ScoredContextItem] = []
    for item in items:
        item_id = _get_attr(item, "item_id", "")
        context_kind: ContextKind = _get_attr(item, "context_kind", ContextKind.MEMORY)
        source_name = _get_attr(item, "source_name", "")
        content = _get_attr(item, "content", "")
        metadata: dict = _get_attr(item, "metadata", {})
        timestamp: datetime | None = _get_attr(item, "timestamp", None)
        l3_confidence: float | None = _get_attr(item, "l3_confidence", None)
        user_marked: bool = _get_attr(item, "user_marked", False)

        semantic_sim: float = metadata.get("retrieval_score", 0.0)
        if query_embedding is not None:
            item_embedding = _get_attr(item, "embedding", None)
            if item_embedding is not None:
                semantic_sim = _compute_cosine_similarity(item_embedding, query_embedding)

        half_life = _DEFAULT_HALF_LIFE.get(context_kind, 30.0)
        time_decay = compute_time_decay(timestamp, current_time, half_life)
        user_mark = 1.0 if user_marked else 0.0
        final_weight = compute_final_weight(context_kind, l3_confidence)

        composite = semantic_sim * w1 + time_decay * w2 + user_mark * w3 + final_weight * w4
        composite = max(0.0, min(1.0, composite))

        token_count: int = _get_attr(item, "token_count", 0)
        content_hash = _get_attr(item, "content_hash", "")
        if not content_hash:
            content_hash = compute_content_hash(content)

        scored.append(
            ScoredContextItem(
                item_id=item_id,
                context_kind=context_kind,
                source_name=source_name,
                content=content,
                token_count=token_count,
                composite_score=composite,
                semantic_similarity=semantic_sim,
                time_decay=time_decay,
                final_weight=final_weight,
                metadata=metadata,
                timestamp=timestamp,
                l3_confidence=l3_confidence,
                content_hash=content_hash,
            )
        )

    return scored


def _compute_cosine_similarity(
    vec_a: list[float],
    vec_b: list[float],
) -> float:
    """计算两个向量的余弦相似度，归一化到 [0.0, 1.0]。

    Args:
        vec_a: 向量 A
        vec_b: 向量 B

    Returns:
        归一化后的相似度，范围 [0.0, 1.0]
    """
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    raw = dot / (norm_a * norm_b)
    return (raw + 1.0) / 2.0


def _get_attr(item: object, name: str, default: object = None) -> object:
    """从对象或字典中获取属性值。

    Args:
        item: 对象实例或字典
        name: 属性名
        default: 缺省值

    Returns:
        属性值
    """
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _dataclass_to_dict(item: object) -> dict:
    """将 dataclass 或带公共属性的对象转为字典（供 Quality Gate 检查用）。

    Args:
        item: dataclass 实例或普通对象

    Returns:
        字典表示
    """
    if hasattr(item, "__dataclass_fields__"):
        return {
            k: getattr(item, k)
            for k in item.__dataclass_fields__  # type: ignore[attr-defined]
        }
    if isinstance(item, dict):
        return item
    result: dict = {}
    for attr in ("context_kind", "metadata", "content", "source_uri"):
        if hasattr(item, attr):
            result[attr] = getattr(item, attr)
    return result


# ---------------------------------------------------------------------------
# Select 阶段
# ---------------------------------------------------------------------------


def select_context(
    items: list[ScoredContextItem],
    token_budget: int,
    min_score: float = 0.3,
    max_same_kind_ratio: float = 0.4,
) -> list[ScoredContextItem]:
    """Token 预算约束下的贪心选择。

    策略：
    1. 按综合得分降序排列
    2. 过滤低于最低质量阈值的条目
    3. 贪心填充直到 Token 预算用尽
    4. 多样性检查：同类型占比不超过 max_same_kind_ratio

    Args:
        items: 评分后的条目列表
        token_budget: Token 预算上限
        min_score: 最低综合得分阈值
        max_same_kind_ratio: 同一 ContextKind 占选中条目的最大比例

    Returns:
        选中的条目列表
    """
    sorted_items = sorted(items, key=lambda x: x.composite_score, reverse=True)
    qualified = [item for item in sorted_items if item.composite_score >= min_score]

    selected: list[ScoredContextItem] = []
    used_tokens = 0
    kind_counts: dict[ContextKind, int] = defaultdict(int)

    for item in qualified:
        if used_tokens + item.token_count > token_budget:
            continue

        # 多样性检查：已有 ≥2 条选中时才约束同类型占比
        if len(selected) >= 2:
            total_after = len(selected) + 1
            new_kind_count = kind_counts[item.context_kind] + 1
            if new_kind_count / total_after > max_same_kind_ratio:
                continue

        selected.append(item)
        used_tokens += item.token_count
        kind_counts[item.context_kind] = kind_counts[item.context_kind] + 1

    return selected


# ---------------------------------------------------------------------------
# Compress 阶段
# ---------------------------------------------------------------------------


def compress_context(
    items: list[ScoredContextItem],
    token_budget: int,
    token_counter: TokenCounter | None = None,
) -> list[CompressedContextItem]:
    """压缩选中条目以适应 Token 预算。

    若总 Token 数已在预算内则直接转换；否则从最低分条目开始截断压缩。

    Args:
        items: 选中的条目列表
        token_budget: Token 预算上限
        token_counter: Token 计数器实例（可选）

    Returns:
        压缩后的 CompressedContextItem 列表
    """
    counter = token_counter or TokenCounter()

    compressed: list[CompressedContextItem] = []
    for item in items:
        compressed.append(
            CompressedContextItem(
                item_id=item.item_id,
                context_kind=item.context_kind,
                source_name=item.source_name,
                content=item.content,
                token_count=item.token_count,
                composite_score=item.composite_score,
                compressed=False,
                compression_method="",
                original_token_count=item.token_count,
                metadata=item.metadata,
            )
        )

    total_tokens = sum(c.token_count for c in compressed)
    if total_tokens <= token_budget:
        return compressed

    overflow = total_tokens - token_budget
    sorted_indices = sorted(
        range(len(compressed)),
        key=lambda i: compressed[i].composite_score,
    )

    for idx in sorted_indices:
        if overflow <= 0:
            break

        item = compressed[idx]
        if item.token_count <= 1:
            continue

        target_tokens = max(1, item.token_count - overflow)
        truncated_content = _truncate_to_tokens(item.content, target_tokens, counter)
        new_token_count = counter.count(truncated_content)

        saved = item.token_count - new_token_count
        if saved > 0:
            compressed[idx] = CompressedContextItem(
                item_id=item.item_id,
                context_kind=item.context_kind,
                source_name=item.source_name,
                content=truncated_content,
                token_count=new_token_count,
                composite_score=item.composite_score,
                compressed=True,
                compression_method="truncation",
                original_token_count=item.original_token_count,
                metadata=item.metadata,
            )
            overflow -= saved

    return compressed


def _truncate_to_tokens(text: str, max_tokens: int, counter: TokenCounter) -> str:
    """将文本截断到指定 Token 数。

    Args:
        text: 原始文本
        max_tokens: 最大 Token 数
        counter: Token 计数器

    Returns:
        截断后的文本
    """
    if counter.count(text) <= max_tokens:
        return text

    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if counter.count(text[:mid]) <= max_tokens:
            lo = mid
        else:
            hi = mid - 1

    result = text[:lo]
    if len(result) < len(text):
        result = result.rstrip() + "..."
    return result


# ---------------------------------------------------------------------------
# Assemble 阶段
# ---------------------------------------------------------------------------


def assemble_context(
    items: list[CompressedContextItem],
    session_metadata: dict | None = None,
    low_context_confidence: bool = False,
) -> tuple[str, int]:
    """组装最终上下文文本。

    按 ContextKind 分组展示，每条添加元数据标记。
    若 low_context_confidence 为 True，追加免责声明。

    Args:
        items: 压缩后的条目列表
        session_metadata: 会话元信息（project_name / analysis_phase 等）
        low_context_confidence: 是否处于低上下文置信度模式

    Returns:
        (组装后的文本, 总 Token 数)
    """
    counter = TokenCounter()
    sections: list[str] = []

    if session_metadata:
        project_name = session_metadata.get("project_name", "Unknown")
        analysis_phase = session_metadata.get("analysis_phase", "")
        total_tokens = sum(item.token_count for item in items)
        header_lines = [
            "## Session Context",
            f"Project: {project_name}",
        ]
        if analysis_phase:
            header_lines.append(f"Analysis Phase: {analysis_phase}")
        header_lines.append(f"Token Budget: {total_tokens}")
        sections.append("\n".join(header_lines))

    kind_groups: dict[ContextKind, list[CompressedContextItem]] = defaultdict(list)
    for item in items:
        kind_groups[item.context_kind].append(item)

    for kind in _ASSEMBLE_KIND_ORDER:
        if kind not in kind_groups:
            continue
        group_items = kind_groups[kind]
        title = _KIND_SECTION_TITLES.get(kind, kind.value)
        section_lines = [f"## {title}"]
        for item in group_items:
            section_lines.append(_format_item_with_markers(item))
        sections.append("\n\n".join(section_lines))

    if low_context_confidence:
        sections.append(
            "## LOW_CONTEXT_CONFIDENCE WARNING\n"
            "当前上下文质量未达到最低标准, 分析结论仅供参考.\n"
            "建议: 补充更多需求文档或代码索引后重新分析."
        )

    assembled = "\n\n".join(sections)
    total_token_count = counter.count(assembled)
    return assembled, total_token_count


def _format_item_with_markers(item: CompressedContextItem) -> str:
    """为上下文片段添加元数据标记。

    Args:
        item: 压缩后的上下文条目

    Returns:
        带标记的文本片段
    """
    if item.composite_score >= 0.7:
        confidence_label = "high"
    elif item.composite_score >= 0.4:
        confidence_label = "medium"
    else:
        confidence_label = "low"

    markers = [
        f"[Source: {item.source_name}]",
        f"[Type: {item.context_kind.value}]",
        f"[Confidence: {confidence_label}]",
    ]
    if item.compressed:
        markers.append(f"[Compressed: {item.compression_method}]")

    header = " ".join(markers)
    return f"{header}\n{item.content}"


# ---------------------------------------------------------------------------
# ContextPipeline 主编排器
# ---------------------------------------------------------------------------


class ContextPipeline:
    """Context Pipeline 主接口 — 五阶段流水线的编排器。

    使用方式::

        pipeline = ContextPipeline(
            sources=[CodeGraphSource(), VectorResultSource(), ...],
            strategy=RiskAnalysisStrategy(),
        )
        result = await pipeline.execute(
            session_id="...",
            project_id="...",
            query="分析支付模块的安全风险",
            context_budget=128000,
        )
    """

    def __init__(
        self,
        sources: list,
        strategy: object,
        token_counter: TokenCounter | None = None,
        quality_gate: QualityGate | None = None,
    ) -> None:
        """初始化 Context Pipeline。

        Args:
            sources: ContextSource 适配器列表，每个需实现
                     collect / supported_kind / is_available 方法
            strategy: ContextStrategy 策略对象，需实现
                      get_source_budgets / get_score_weights 等方法
            token_counter: Token 计数器实例，缺省自动创建
            quality_gate: Quality Gate 检查器实例，缺省自动创建
        """
        self.sources = sources
        self.strategy = strategy
        self.token_counter = token_counter or TokenCounter()
        self.quality_gate = quality_gate or QualityGate()

    async def execute(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_budget: int,
    ) -> PipelineResult:
        """执行完整的五阶段流水线。

        Args:
            session_id: 当前 Session ID
            project_id: 项目 ID
            query: 当前推理步骤的查询意图
            context_budget: Token 预算上限

        Returns:
            PipelineResult 包含组装后的上下文和元信息

        Raises:
            ContextBudgetExceededException: 组装后仍超出预算 105% 时抛出
        """
        effective_budget = int(context_budget * 0.45)

        collected = await self._collect(session_id, project_id, query)
        collected_dicts = [
            item if isinstance(item, dict) else _dataclass_to_dict(item) for item in collected
        ]

        gate_result = self.quality_gate.check(collected_dicts)

        scored = score_items(collected, now=datetime.now(UTC))

        select_min_score = 0.2 if gate_result.low_context_confidence else 0.3
        selected = select_context(
            scored,
            token_budget=effective_budget,
            min_score=select_min_score,
        )

        compressed = compress_context(
            selected,
            token_budget=effective_budget,
            token_counter=self.token_counter,
        )

        assembled_text, total_token_count = assemble_context(
            compressed,
            low_context_confidence=gate_result.low_context_confidence,
        )

        tolerance = int(effective_budget * 1.05)
        if total_token_count > tolerance:
            raise ContextBudgetExceededException(
                message=(
                    f"Assemble 后 Token 数 {total_token_count} "
                    f"超出有效预算 {effective_budget} 的 105%"
                ),
                budget=effective_budget,
                actual=total_token_count,
            )

        strategy_name = type(self.strategy).__name__
        logger.info(
            f"Pipeline 完成: strategy={strategy_name}, "
            f"collected={len(collected)}, scored={len(scored)}, "
            f"selected={len(selected)}, compressed={len(compressed)}, "
            f"tokens={total_token_count}/{context_budget}"
        )

        return PipelineResult(
            context=assembled_text,
            token_count=total_token_count,
            budget=context_budget,
            items_count=len(compressed),
            quality_gate_result=gate_result,
            strategy_name=strategy_name,
        )

    async def _collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
    ) -> list:
        """Collect 阶段 — 并行调用激活的 ContextSource。

        单个数据源失败不阻塞整体收集，失败时返回空列表并记录警告。

        Args:
            session_id: 当前 Session ID
            project_id: 项目 ID
            query: 当前推理步骤的查询意图

        Returns:
            合并后的上下文条目列表
        """
        collected: list = []
        seen_hashes: set[str] = set()

        for source in self.sources:
            try:
                if not source.is_available(project_id):
                    continue
                items = await source.collect(
                    session_id=session_id,
                    project_id=project_id,
                    query=query,
                    context_kind=source.supported_kind(),
                )
                for item in items:
                    content = _get_attr(item, "content", "")
                    item_hash = compute_content_hash(content)
                    if item_hash not in seen_hashes:
                        seen_hashes.add(item_hash)
                        collected.append(item)
            except Exception:
                source_name = type(source).__name__
                logger.warning(
                    f"ContextSource {source_name} 收集失败, 跳过",
                    exc_info=True,
                )

        return collected
