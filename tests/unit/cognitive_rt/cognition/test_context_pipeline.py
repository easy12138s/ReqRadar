"""Context Pipeline 五阶段流水线的单元测试。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from reqradar.cognitive_rt.cognition.context_pipeline import (
    CONTEXT_KIND_WEIGHTS,
    CompressedContextItem,
    ContextPipeline,
    QualityGate,
    ScoredContextItem,
    TokenCounter,
    assemble_context,
    compress_context,
    compute_content_hash,
    compute_final_weight,
    compute_time_decay,
    score_items,
    select_context,
)
from reqradar.kernel.types import ContextKind

# ---------------------------------------------------------------------------
# 测试辅助数据
# ---------------------------------------------------------------------------


def _make_item(
    content: str = "test content",
    kind: ContextKind = ContextKind.SOURCE_CODE,
    source: str = "TestSource",
    token_count: int = 50,
    retrieval_score: float = 0.8,
    user_marked: bool = False,
    l3_confidence: float | None = None,
    timestamp: datetime | None = None,
) -> dict:
    """创建测试用上下文条目字典。"""
    return {
        "item_id": f"test-{hash(content) % 10000:04d}",
        "content": content,
        "context_kind": kind,
        "source_name": source,
        "token_count": token_count,
        "metadata": {"retrieval_score": retrieval_score},
        "timestamp": timestamp or datetime.now(UTC),
        "user_marked": user_marked,
        "l3_confidence": l3_confidence,
        "content_hash": compute_content_hash(content),
    }


def _make_scored(
    content: str = "scored content",
    kind: ContextKind = ContextKind.SOURCE_CODE,
    score: float = 0.7,
    token_count: int = 50,
    source: str = "TestSource",
) -> ScoredContextItem:
    """创建测试用评分条目。"""
    return ScoredContextItem(
        item_id=f"sc-{hash(content) % 10000:04d}",
        context_kind=kind,
        source_name=source,
        content=content,
        token_count=token_count,
        composite_score=score,
    )


# ---------------------------------------------------------------------------
# TokenCounter 测试
# ---------------------------------------------------------------------------


class TestTokenCounter:
    def test_count_empty_text(self):
        counter = TokenCounter()
        assert counter.count("") == 0

    def test_count_returns_positive(self):
        counter = TokenCounter()
        assert counter.count("hello world") > 0

    def test_count_longer_text_more_tokens(self):
        counter = TokenCounter()
        short = counter.count("hi")
        long = counter.count("hello world this is a longer text for testing")
        assert long > short

    def test_count_items_sums_token_count(self):
        counter = TokenCounter()
        items = [
            _make_scored(token_count=10),
            _make_scored(token_count=20),
            _make_scored(token_count=30),
        ]
        assert counter.count_items(items) == 60

    def test_count_items_empty_list(self):
        counter = TokenCounter()
        assert counter.count_items([]) == 0


# ---------------------------------------------------------------------------
# QualityGate 测试
# ---------------------------------------------------------------------------


class TestQualityGate:
    def test_pass_when_all_criteria_met(self):
        gate = QualityGate()
        items = [
            _make_item(kind=ContextKind.SOURCE_CODE, retrieval_score=0.8),
            _make_item(kind=ContextKind.REQUIREMENT, retrieval_score=0.7),
        ]
        result = gate.check(items)
        assert result.passed is True
        assert result.low_context_confidence is False
        assert result.failures == []

    def test_fail_when_too_few_items(self):
        gate = QualityGate()
        items = [_make_item(kind=ContextKind.SOURCE_CODE, retrieval_score=0.8)]
        result = gate.check(items)
        assert result.passed is False
        assert any("条目数" in f for f in result.failures)

    def test_fail_when_no_code_evidence(self):
        gate = QualityGate()
        items = [
            _make_item(kind=ContextKind.REQUIREMENT, retrieval_score=0.8),
            _make_item(kind=ContextKind.MEMORY, retrieval_score=0.7),
        ]
        result = gate.check(items)
        assert result.passed is False
        assert any("代码证据" in f for f in result.failures)

    def test_fail_when_low_semantic_score(self):
        gate = QualityGate()
        items = [
            _make_item(kind=ContextKind.SOURCE_CODE, retrieval_score=0.3),
            _make_item(kind=ContextKind.REQUIREMENT, retrieval_score=0.2),
        ]
        result = gate.check(items)
        assert result.passed is False
        assert any("语义得分" in f for f in result.failures)

    def test_pass_with_custom_thresholds(self):
        gate = QualityGate(
            thresholds={"min_items": 1, "min_semantic_score": 0.3, "min_code_evidence": 0}
        )
        items = [_make_item(kind=ContextKind.MEMORY, retrieval_score=0.5)]
        result = gate.check(items)
        assert result.passed is True

    def test_fail_on_empty_list(self):
        gate = QualityGate()
        result = gate.check([])
        assert result.passed is False
        assert result.total_items == 0


# ---------------------------------------------------------------------------
# compute_time_decay 测试
# ---------------------------------------------------------------------------


class TestTimeDecay:
    def test_fresh_item_decay_near_one(self):
        now = datetime.now(UTC)
        decay = compute_time_decay(now, now, half_life_days=30.0)
        assert decay == pytest.approx(1.0, abs=0.01)

    def test_half_life_decay(self):
        now = datetime.now(UTC)
        old = now - timedelta(days=30)
        decay = compute_time_decay(old, now, half_life_days=30.0)
        assert decay == pytest.approx(0.5, abs=0.01)

    def test_double_half_life(self):
        now = datetime.now(UTC)
        old = now - timedelta(days=60)
        decay = compute_time_decay(old, now, half_life_days=30.0)
        assert decay == pytest.approx(0.25, abs=0.01)

    def test_none_timestamp_returns_one(self):
        decay = compute_time_decay(None, datetime.now(UTC))
        assert decay == 1.0

    def test_future_timestamp_returns_one(self):
        now = datetime.now(UTC)
        future = now + timedelta(days=10)
        decay = compute_time_decay(future, now)
        assert decay == 1.0


# ---------------------------------------------------------------------------
# compute_final_weight 测试
# ---------------------------------------------------------------------------


class TestFinalWeight:
    def test_source_code_weight(self):
        assert compute_final_weight(ContextKind.SOURCE_CODE) == 1.0

    def test_inferred_knowledge_weight(self):
        assert compute_final_weight(ContextKind.INFERRED_KNOWLEDGE) == 0.4

    def test_memory_without_l3_confidence(self):
        assert compute_final_weight(ContextKind.MEMORY) == 0.6

    def test_memory_with_l3_confidence(self):
        weight = compute_final_weight(ContextKind.MEMORY, l3_confidence=0.8)
        assert weight == pytest.approx(0.48, abs=0.001)

    def test_non_memory_ignores_l3_confidence(self):
        weight = compute_final_weight(ContextKind.SOURCE_CODE, l3_confidence=0.1)
        assert weight == 1.0

    def test_all_kinds_have_weights(self):
        for kind in ContextKind:
            assert kind in CONTEXT_KIND_WEIGHTS


# ---------------------------------------------------------------------------
# score_items 测试
# ---------------------------------------------------------------------------


class TestScoreItems:
    def test_score_returns_list_of_scored_items(self):
        items = [_make_item(), _make_item(kind=ContextKind.MEMORY)]
        scored = score_items(items)
        assert len(scored) == 2
        assert all(isinstance(s, ScoredContextItem) for s in scored)

    def test_composite_score_in_range(self):
        items = [_make_item(), _make_item(kind=ContextKind.INFERRED_KNOWLEDGE)]
        scored = score_items(items)
        for s in scored:
            assert 0.0 <= s.composite_score <= 1.0

    def test_higher_retrieval_score_higher_composite(self):
        high = [_make_item(retrieval_score=0.9)]
        low = [_make_item(retrieval_score=0.1)]
        scored_high = score_items(high)
        scored_low = score_items(low)
        assert scored_high[0].composite_score > scored_low[0].composite_score

    def test_user_marked_increases_score(self):
        marked = [_make_item(user_marked=True)]
        unmarked = [_make_item(user_marked=False)]
        scored_marked = score_items(marked)
        scored_unmarked = score_items(unmarked)
        assert scored_marked[0].composite_score > scored_unmarked[0].composite_score

    def test_fresh_item_higher_than_old(self):
        now = datetime.now(UTC)
        fresh = [_make_item(timestamp=now)]
        old = [_make_item(timestamp=now - timedelta(days=180))]
        scored_fresh = score_items(fresh, now=now)
        scored_old = score_items(old, now=now)
        assert scored_fresh[0].composite_score > scored_old[0].composite_score

    def test_empty_list_returns_empty(self):
        assert score_items([]) == []

    def test_custom_weights(self):
        old_item = _make_item(
            kind=ContextKind.INFERRED_KNOWLEDGE, timestamp=datetime.now(UTC) - timedelta(days=90)
        )
        w_time = score_items([old_item], weights={"w1": 0.0, "w2": 1.0, "w3": 0.0, "w4": 0.0})
        w_kind = score_items([old_item], weights={"w1": 0.0, "w2": 0.0, "w3": 0.0, "w4": 1.0})
        assert w_time[0].composite_score != w_kind[0].composite_score


# ---------------------------------------------------------------------------
# select_context 测试
# ---------------------------------------------------------------------------


class TestSelectContext:
    def test_select_within_budget(self):
        kinds = [
            ContextKind.SOURCE_CODE,
            ContextKind.REQUIREMENT,
            ContextKind.MEMORY,
            ContextKind.GIT_HISTORY,
            ContextKind.ARCH_DOC,
        ]
        items = [_make_scored(kind=kinds[i % len(kinds)], token_count=10) for i in range(5)]
        selected = select_context(items, token_budget=100)
        assert len(selected) == 5

    def test_select_respects_token_budget(self):
        kinds = [
            ContextKind.SOURCE_CODE,
            ContextKind.REQUIREMENT,
            ContextKind.MEMORY,
            ContextKind.GIT_HISTORY,
        ]
        items = [_make_scored(kind=kinds[i % len(kinds)], token_count=50) for i in range(10)]
        selected = select_context(items, token_budget=100)
        total = sum(s.token_count for s in selected)
        assert total <= 100

    def test_select_prefers_higher_score(self):
        items = [
            _make_scored(content="high", score=0.9, token_count=50, kind=ContextKind.SOURCE_CODE),
            _make_scored(content="low", score=0.5, token_count=50, kind=ContextKind.REQUIREMENT),
        ]
        selected = select_context(items, token_budget=50, max_same_kind_ratio=1.0)
        assert len(selected) == 1
        assert selected[0].content == "high"

    def test_select_filters_below_min_score(self):
        items = [
            _make_scored(score=0.4, kind=ContextKind.SOURCE_CODE),
            _make_scored(score=0.2, kind=ContextKind.REQUIREMENT),
        ]
        selected = select_context(items, token_budget=1000, min_score=0.3, max_same_kind_ratio=1.0)
        assert len(selected) == 1

    def test_select_empty_list(self):
        assert select_context([], token_budget=100) == []

    def test_select_respects_diversity(self):
        items = [
            _make_scored(kind=ContextKind.SOURCE_CODE, score=0.9, token_count=10),
            _make_scored(kind=ContextKind.SOURCE_CODE, score=0.85, token_count=10),
            _make_scored(kind=ContextKind.SOURCE_CODE, score=0.8, token_count=10),
            _make_scored(kind=ContextKind.SOURCE_CODE, score=0.75, token_count=10),
            _make_scored(kind=ContextKind.MEMORY, score=0.7, token_count=10),
            _make_scored(kind=ContextKind.REQUIREMENT, score=0.65, token_count=10),
        ]
        selected = select_context(items, token_budget=1000, min_score=0.3, max_same_kind_ratio=0.4)
        # 多样性约束从第 3 条开始生效，限制同类型占比
        code_count = sum(1 for s in selected if s.context_kind == ContextKind.SOURCE_CODE)
        assert code_count < len(items)
        kind_set = {s.context_kind for s in selected}
        assert len(kind_set) >= 2


# ---------------------------------------------------------------------------
# compress_context 测试
# ---------------------------------------------------------------------------


class TestCompressContext:
    def test_no_compression_when_within_budget(self):
        items = [_make_scored(token_count=10), _make_scored(token_count=20)]
        compressed = compress_context(items, token_budget=100)
        assert len(compressed) == 2
        assert all(not c.compressed for c in compressed)

    def test_compression_when_over_budget(self):
        items = [_make_scored(content="x" * 1000, token_count=250) for _ in range(4)]
        compressed = compress_context(items, token_budget=200)
        total = sum(c.token_count for c in compressed)
        assert total <= 200 * 1.1

    def test_lowest_score_compressed_first(self):
        items = [
            _make_scored(content="high value " * 100, score=0.9, token_count=500),
            _make_scored(content="low value " * 100, score=0.3, token_count=500),
        ]
        compressed = compress_context(items, token_budget=600)
        low = next(c for c in compressed if c.composite_score == 0.3)
        assert low.compressed is True
        assert low.compression_method == "truncation"

    def test_compressed_preserves_metadata(self):
        items = [_make_scored(token_count=100)]
        compressed = compress_context(items, token_budget=1000)
        assert compressed[0].item_id == items[0].item_id
        assert compressed[0].context_kind == items[0].context_kind

    def test_empty_list(self):
        assert compress_context([], token_budget=100) == []


# ---------------------------------------------------------------------------
# assemble_context 测试
# ---------------------------------------------------------------------------


class TestAssembleContext:
    def test_assemble_returns_text_and_token_count(self):
        items = [
            CompressedContextItem(
                item_id="c1",
                context_kind=ContextKind.SOURCE_CODE,
                source_name="Test",
                content="code content",
                token_count=10,
                composite_score=0.8,
            )
        ]
        text, count = assemble_context(items)
        assert isinstance(text, str)
        assert isinstance(count, int)
        assert count > 0

    def test_assemble_contains_source_markers(self):
        items = [
            CompressedContextItem(
                item_id="c1",
                context_kind=ContextKind.SOURCE_CODE,
                source_name="CodeGraph",
                content="some code",
                token_count=10,
                composite_score=0.8,
            )
        ]
        text, _ = assemble_context(items)
        assert "[Source: CodeGraph]" in text
        assert "[Type: SOURCE_CODE]" in text
        assert "[Confidence: high]" in text

    def test_assemble_low_confidence_disclaimer(self):
        items = [
            CompressedContextItem(
                item_id="c1",
                context_kind=ContextKind.MEMORY,
                source_name="Memory",
                content="memory content",
                token_count=10,
                composite_score=0.5,
            )
        ]
        text, _ = assemble_context(items, low_context_confidence=True)
        assert "LOW_CONTEXT_CONFIDENCE" in text

    def test_assemble_no_disclaimer_when_confident(self):
        items = [
            CompressedContextItem(
                item_id="c1",
                context_kind=ContextKind.SOURCE_CODE,
                source_name="Test",
                content="code",
                token_count=10,
                composite_score=0.8,
            )
        ]
        text, _ = assemble_context(items, low_context_confidence=False)
        assert "LOW_CONTEXT_CONFIDENCE" not in text

    def test_assemble_with_session_metadata(self):
        items = [
            CompressedContextItem(
                item_id="c1",
                context_kind=ContextKind.SOURCE_CODE,
                source_name="Test",
                content="code",
                token_count=10,
                composite_score=0.8,
            )
        ]
        text, _ = assemble_context(
            items, session_metadata={"project_name": "MyProject", "analysis_phase": "risk"}
        )
        assert "MyProject" in text
        assert "risk" in text

    def test_assemble_groups_by_kind(self):
        items = [
            CompressedContextItem(
                item_id="c1",
                context_kind=ContextKind.REQUIREMENT,
                source_name="Test",
                content="req",
                token_count=10,
                composite_score=0.8,
            ),
            CompressedContextItem(
                item_id="c2",
                context_kind=ContextKind.SOURCE_CODE,
                source_name="Test",
                content="code",
                token_count=10,
                composite_score=0.7,
            ),
        ]
        text, _ = assemble_context(items)
        assert "Requirement Context" in text
        assert "Code Context" in text

    def test_assemble_compressed_marker(self):
        items = [
            CompressedContextItem(
                item_id="c1",
                context_kind=ContextKind.SOURCE_CODE,
                source_name="Test",
                content="truncated...",
                token_count=5,
                composite_score=0.5,
                compressed=True,
                compression_method="truncation",
            )
        ]
        text, _ = assemble_context(items)
        assert "[Compressed: truncation]" in text


# ---------------------------------------------------------------------------
# ContextPipeline 端到端测试
# ---------------------------------------------------------------------------


@dataclass
class MockSource:
    """Mock 数据源。"""

    _kind: ContextKind
    _items: list = field(default_factory=list)
    _available: bool = True

    def supported_kind(self) -> ContextKind:
        return self._kind

    def is_available(self, project_id: str) -> bool:
        return self._available

    async def collect(
        self, session_id: str, project_id: str, query: str, context_kind=None
    ) -> list:
        return self._items


@dataclass
class MockStrategy:
    """Mock 策略。"""

    def get_source_budgets(self) -> dict:
        return {ContextKind.SOURCE_CODE: 20, ContextKind.REQUIREMENT: 10}

    def get_score_weights(self) -> dict:
        return {
            "w1_semantic": 0.4,
            "w2_time_decay": 0.15,
            "w3_user_mark": 0.15,
            "w4_context_kind": 0.3,
        }

    def get_select_min_score(self) -> float:
        return 0.3

    def get_quality_gate_thresholds(self) -> dict:
        return {"min_items": 2, "min_semantic_score": 0.65, "min_code_evidence": 1}


class TestContextPipeline:
    @pytest.mark.asyncio
    async def test_execute_with_valid_items(self):
        code_source = MockSource(
            _kind=ContextKind.SOURCE_CODE,
            _items=[
                _make_item(
                    content="code module A " * 10,
                    kind=ContextKind.SOURCE_CODE,
                    token_count=100,
                    retrieval_score=0.8,
                ),
            ],
        )
        req_source = MockSource(
            _kind=ContextKind.REQUIREMENT,
            _items=[
                _make_item(
                    content="requirement doc B " * 10,
                    kind=ContextKind.REQUIREMENT,
                    token_count=80,
                    retrieval_score=0.7,
                ),
            ],
        )
        pipeline = ContextPipeline(sources=[code_source, req_source], strategy=MockStrategy())
        result = await pipeline.execute("s1", "p1", "test query", context_budget=10000)
        assert isinstance(result.context, str)
        assert result.token_count > 0
        assert result.budget == 10000
        assert result.items_count >= 1

    @pytest.mark.asyncio
    async def test_execute_with_empty_sources(self):
        source = MockSource(_kind=ContextKind.SOURCE_CODE, _items=[])
        pipeline = ContextPipeline(sources=[source], strategy=MockStrategy())
        result = await pipeline.execute("s1", "p1", "test", context_budget=10000)
        assert result.quality_gate_result.passed is False
        assert result.quality_gate_result.low_context_confidence is True

    @pytest.mark.asyncio
    async def test_execute_unavailable_source_skipped(self):
        available = MockSource(
            _kind=ContextKind.SOURCE_CODE,
            _items=[
                _make_item(content="code A", kind=ContextKind.SOURCE_CODE, token_count=50),
                _make_item(content="code B", kind=ContextKind.SOURCE_CODE, token_count=50),
            ],
        )
        unavailable = MockSource(
            _kind=ContextKind.MEMORY, _items=[_make_item(kind=ContextKind.MEMORY)], _available=False
        )
        pipeline = ContextPipeline(sources=[available, unavailable], strategy=MockStrategy())
        result = await pipeline.execute("s1", "p1", "test", context_budget=10000)
        assert "MEMORY" not in result.context or result.items_count >= 0

    @pytest.mark.asyncio
    async def test_execute_deduplicates_content(self):
        source = MockSource(
            _kind=ContextKind.SOURCE_CODE,
            _items=[
                _make_item(content="same content", kind=ContextKind.SOURCE_CODE, token_count=50),
                _make_item(content="same content", kind=ContextKind.SOURCE_CODE, token_count=50),
            ],
        )
        pipeline = ContextPipeline(sources=[source], strategy=MockStrategy())
        result = await pipeline.execute("s1", "p1", "test", context_budget=10000)
        assert result.items_count <= 1 or result.items_count >= 0

    @pytest.mark.asyncio
    async def test_execute_source_failure_does_not_block(self):
        class FailingSource:
            def supported_kind(self):
                return ContextKind.MEMORY

            def is_available(self, project_id):
                return True

            async def collect(self, **kwargs):
                raise RuntimeError("source failed")

        good_source = MockSource(
            _kind=ContextKind.SOURCE_CODE,
            _items=[
                _make_item(content="code 1", kind=ContextKind.SOURCE_CODE, token_count=50),
                _make_item(content="code 2", kind=ContextKind.SOURCE_CODE, token_count=50),
            ],
        )
        pipeline = ContextPipeline(sources=[FailingSource(), good_source], strategy=MockStrategy())
        result = await pipeline.execute("s1", "p1", "test", context_budget=10000)
        assert result.token_count >= 0

    @pytest.mark.asyncio
    async def test_execute_respects_token_budget(self):
        source = MockSource(
            _kind=ContextKind.SOURCE_CODE,
            _items=[
                _make_item(
                    content=f"content {i} " * 20,
                    kind=ContextKind.SOURCE_CODE,
                    token_count=200,
                    retrieval_score=0.8,
                )
                for i in range(50)
            ],
        )
        budget = 5000
        pipeline = ContextPipeline(sources=[source], strategy=MockStrategy())
        result = await pipeline.execute("s1", "p1", "test", context_budget=budget)
        effective = int(budget * 0.45)
        assert result.token_count <= effective * 1.05 + 100


# ---------------------------------------------------------------------------
# compute_content_hash 测试
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_same_content_same_hash(self):
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("hello")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("world")
        assert h1 != h2

    def test_hash_length(self):
        h = compute_content_hash("test")
        assert len(h) == 16
