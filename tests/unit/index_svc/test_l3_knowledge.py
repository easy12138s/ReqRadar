"""P5 L3 知识系统单元测试 — 模型、治理、写入、关系、上下文源。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from reqradar.index_svc.context_source import L3ContextSource
from reqradar.index_svc.knowledge.governance import (
    ConfidenceCalculator,
    FreshnessManager,
    KnowledgeChangelog,
)
from reqradar.index_svc.knowledge.models import (
    ConfidenceMetadata,
    L3KnowledgeBase,
)
from reqradar.index_svc.knowledge.relations import (
    KnowledgeRelation,
    RelationStore,
    RelationType,
)
from reqradar.index_svc.knowledge.writer import L3Writer
from reqradar.kernel.enums import FreshnessStatus, KnowledgeNodeType
from reqradar.kernel.types import ContextItem, ContextKind


def _make_knowledge(
    knowledge_type: KnowledgeNodeType = KnowledgeNodeType.GLOSSARY,
    project_id: str = "proj-1",
    confidence_score: float = 0.5,
    last_verified_at: datetime | None = None,
    human_verified: bool = False,
    verification_count: int = 0,
    freshness: FreshnessStatus = FreshnessStatus.ACTIVE,
) -> L3KnowledgeBase:
    """快速创建测试用知识条目。"""
    return L3KnowledgeBase(
        project_id=project_id,
        knowledge_type=knowledge_type,
        freshness=freshness,
        confidence=ConfidenceMetadata(
            confidence_score=confidence_score,
            verification_count=verification_count,
            human_verified=human_verified,
            last_verified_at=last_verified_at,
        ),
    )


# ---------------------------------------------------------------------------
# TestGlossaryEntry — 术语表条目基础测试
# ---------------------------------------------------------------------------


class TestGlossaryEntry:
    """术语表知识条目（GLOSSARY 类型）的基本属性测试。"""

    def test_create_glossary_entry(self):
        """创建 GLOSSARY 类型知识条目，验证 id 自动生成。"""
        entry = L3KnowledgeBase(
            project_id="proj-1",
            knowledge_type=KnowledgeNodeType.GLOSSARY,
        )
        assert entry.id is not None
        assert len(entry.id) > 0
        assert entry.project_id == "proj-1"
        assert entry.knowledge_type == KnowledgeNodeType.GLOSSARY

    def test_glossary_default_freshness(self):
        """默认新鲜度为 ACTIVE。"""
        entry = L3KnowledgeBase(knowledge_type=KnowledgeNodeType.GLOSSARY)
        assert entry.freshness == FreshnessStatus.ACTIVE

    def test_glossary_confidence_metadata(self):
        """默认置信度元数据：confidence_score 为 0.5。"""
        entry = L3KnowledgeBase(knowledge_type=KnowledgeNodeType.GLOSSARY)
        assert entry.confidence.confidence_score == 0.5
        assert entry.confidence.verification_count == 0
        assert entry.confidence.human_verified is False
        assert entry.confidence.last_verified_at is None


# ---------------------------------------------------------------------------
# TestKnowledgeTypes — 七种知识类型覆盖测试
# ---------------------------------------------------------------------------


class TestKnowledgeTypes:
    """验证 KnowledgeNodeType 枚举值与各类型特有字段。"""

    def test_all_types_exist(self):
        """所有知识类型都可以实例化为 L3KnowledgeBase。"""
        for node_type in KnowledgeNodeType:
            kb = L3KnowledgeBase(
                knowledge_type=node_type,
                project_id="proj-test",
            )
            assert kb.knowledge_type == node_type

    def test_module_profile_fields(self):
        """ModuleProfile 类型可以承载模块名和职责字段。"""
        kb = L3KnowledgeBase(knowledge_type=KnowledgeNodeType.MODULE_PROFILE)
        kb.module_name = "index_svc"
        kb.responsibility = "知识索引服务"
        assert kb.module_name == "index_svc"
        assert kb.responsibility == "知识索引服务"
        assert kb.knowledge_type == KnowledgeNodeType.MODULE_PROFILE

    def test_architecture_constraint_fields(self):
        """Constraint 类型可以承载约束类型和作用域字段。"""
        kb = L3KnowledgeBase(knowledge_type=KnowledgeNodeType.CONSTRAINT)
        kb.constraint_type = "nfr_security"
        kb.scope = "project-wide"
        kb.description = "所有 API 必须经过认证"
        assert kb.constraint_type == "nfr_security"
        assert kb.scope == "project-wide"
        assert kb.description == "所有 API 必须经过认证"

    def test_incident_memory_fields(self):
        """Incident 类型可以承载事件类型和严重程度字段。"""
        kb = L3KnowledgeBase(knowledge_type=KnowledgeNodeType.INCIDENT)
        kb.incident_type = "performance_degradation"
        kb.severity = "high"
        kb.risk_description = "数据库查询超时导致服务降级"
        assert kb.incident_type == "performance_degradation"
        assert kb.severity == "high"
        assert kb.risk_description == "数据库查询超时导致服务降级"


# ---------------------------------------------------------------------------
# TestFreshnessManager — 新鲜度管理器测试
# ---------------------------------------------------------------------------


class TestFreshnessManager:
    """新鲜度管理器的过期检测、状态更新与冲突标记测试。"""

    def test_active_knowledge_stays_active(self):
        """近期验证过的知识保持 ACTIVE 状态。"""
        fm = FreshnessManager()
        kb = _make_knowledge(
            last_verified_at=datetime.now(UTC) - timedelta(days=5),
        )
        status = fm.check_staleness(kb)
        assert status == FreshnessStatus.ACTIVE

    def test_stale_detection(self):
        """超过 91 天未验证的知识应被检测为 STALE。"""
        fm = FreshnessManager(stale_days=90)
        kb = _make_knowledge(
            last_verified_at=datetime.now(UTC) - timedelta(days=91),
        )
        status = fm.check_staleness(kb)
        assert status == FreshnessStatus.STALE

    def test_update_freshness(self):
        """update_freshness 会将过期知识的状态更新为 STALE。"""
        fm = FreshnessManager(stale_days=90)
        kb = _make_knowledge(
            last_verified_at=datetime.now(UTC) - timedelta(days=100),
        )
        assert kb.freshness == FreshnessStatus.ACTIVE
        result = fm.update_freshness(kb)
        assert result.freshness == FreshnessStatus.STALE

    def test_mark_conflicted(self):
        """mark_conflicted 将知识标记为 CONFLICTED 状态。"""
        fm = FreshnessManager()
        kb = _make_knowledge()
        assert kb.freshness == FreshnessStatus.ACTIVE
        result = fm.mark_conflicted(kb)
        assert result.freshness == FreshnessStatus.CONFLICTED


# ---------------------------------------------------------------------------
# TestConfidenceCalculator — 置信度计算器测试
# ---------------------------------------------------------------------------


class TestConfidenceCalculator:
    """置信度计算的基准分、验证加分、人工确认加分和过期惩罚测试。"""

    def test_base_confidence(self):
        """新知识返回 base_score（无验证加分和惩罚）。"""
        calc = ConfidenceCalculator()
        kb = _make_knowledge(confidence_score=0.6)
        score = calc.calculate(kb)
        assert score == 0.6

    def test_verification_increases_score(self):
        """多次验证提升置信度评分。"""
        calc = ConfidenceCalculator()
        kb = _make_knowledge(
            confidence_score=0.5,
            verification_count=4,
            last_verified_at=datetime.now(UTC),
        )
        score = calc.calculate(kb)
        assert score > 0.5

    def test_human_verify_bonus(self):
        """人工确认额外增加 0.2 置信度加分。"""
        calc = ConfidenceCalculator()
        kb_no_human = _make_knowledge(confidence_score=0.5, human_verified=False)
        kb_human = _make_knowledge(confidence_score=0.5, human_verified=True)
        score_no_human = calc.calculate(kb_no_human)
        score_human = calc.calculate(kb_human)
        assert pytest.approx(score_human - score_no_human, abs=0.01) == 0.2

    def test_staleness_penalty(self):
        """长期未验证的知识会受到过期惩罚，降低置信度。"""
        calc = ConfidenceCalculator()
        kb_fresh = _make_knowledge(
            confidence_score=0.5,
            last_verified_at=datetime.now(UTC),
        )
        kb_old = _make_knowledge(
            confidence_score=0.5,
            last_verified_at=datetime.now(UTC) - timedelta(days=365),
        )
        score_fresh = calc.calculate(kb_fresh)
        score_old = calc.calculate(kb_old)
        assert score_old < score_fresh


# ---------------------------------------------------------------------------
# TestKnowledgeChangelog — 知识变更日志测试
# ---------------------------------------------------------------------------


class TestKnowledgeChangelog:
    """变更日志的记录、查询和追加语义测试。"""

    def test_record_creates_entry(self):
        """record() 创建一条 ChangelogEntry。"""
        cl = KnowledgeChangelog()
        entry = cl.record(
            knowledge_id="k-1",
            knowledge_type="glossary",
            action="create",
            session_id="s-1",
        )
        assert entry.knowledge_id == "k-1"
        assert entry.knowledge_type == "glossary"
        assert entry.action == "create"
        assert entry.session_id == "s-1"

    def test_get_history(self):
        """get_history 按 knowledge_id 过滤变更记录。"""
        cl = KnowledgeChangelog()
        cl.record(knowledge_id="k-1", knowledge_type="glossary", action="create")
        cl.record(knowledge_id="k-2", knowledge_type="risk", action="create")
        cl.record(knowledge_id="k-1", knowledge_type="glossary", action="update")
        history = cl.get_history("k-1")
        assert len(history) == 2
        assert all(e.knowledge_id == "k-1" for e in history)

    def test_append_only(self):
        """已有的变更记录不会被修改（append-only 语义）。"""
        cl = KnowledgeChangelog()
        entry1 = cl.record(knowledge_id="k-1", knowledge_type="glossary", action="create")
        original_action = entry1.action
        original_id = entry1.id
        cl.record(knowledge_id="k-1", knowledge_type="glossary", action="update")
        assert entry1.action == original_action
        assert entry1.id == original_id
        assert len(cl._entries) == 2


# ---------------------------------------------------------------------------
# TestL3Writer — L3 知识写入器测试
# ---------------------------------------------------------------------------


class TestL3Writer:
    """L3Writer 的追加、更新、废弃和替代操作测试。"""

    def test_append_knowledge(self):
        """append() 存储知识并记录变更日志。"""
        writer = L3Writer()
        kb = _make_knowledge(knowledge_type=KnowledgeNodeType.GLOSSARY)
        result = writer.append(kb, session_id="s-1")
        assert result.id == kb.id
        assert writer.get(kb.id) is kb

    def test_update_knowledge(self):
        """update() 修改字段并记录字段级变更。"""
        writer = L3Writer()
        kb = _make_knowledge(knowledge_type=KnowledgeNodeType.GLOSSARY)
        writer.append(kb, session_id="s-1")
        updated = writer.update(
            kb.id,
            {"project_id": "proj-new"},
            session_id="s-2",
        )
        assert updated is not None
        assert updated.project_id == "proj-new"

    def test_deprecate_knowledge(self):
        """deprecate() 将知识标记为 DEPRECATED。"""
        writer = L3Writer()
        kb = _make_knowledge(knowledge_type=KnowledgeNodeType.RISK)
        writer.append(kb, session_id="s-1")
        result = writer.deprecate(kb.id, session_id="s-2")
        assert result is not None
        assert result.freshness == FreshnessStatus.DEPRECATED

    def test_supersede_knowledge(self):
        """supersede() 将旧知识标记为 SUPERSEDED 并创建新知识。"""
        writer = L3Writer()
        old_kb = _make_knowledge(knowledge_type=KnowledgeNodeType.CONSTRAINT)
        writer.append(old_kb, session_id="s-1")

        new_kb = _make_knowledge(
            knowledge_type=KnowledgeNodeType.CONSTRAINT,
            project_id="proj-1",
        )
        result = writer.supersede(old_kb.id, new_kb, session_id="s-2")
        assert result is not None
        assert result.id == new_kb.id
        old = writer.get(old_kb.id)
        assert old is not None
        assert old.freshness == FreshnessStatus.SUPERSEDED
        assert old.superseded_by == new_kb.id


# ---------------------------------------------------------------------------
# TestRelationStore — 知识关系存储测试
# ---------------------------------------------------------------------------


class TestRelationStore:
    """关系存储的添加、查询和双向获取测试。"""

    def test_add_relation(self):
        """add() 存储一条关系记录。"""
        store = RelationStore()
        rel = KnowledgeRelation(
            source_id="k-1",
            target_id="k-2",
            relation_type=RelationType.DEPENDS_ON,
        )
        result = store.add(rel)
        assert result.id == rel.id
        assert len(store._relations) == 1

    def test_query_by_source(self):
        """query(source_id=...) 按源 ID 过滤关系。"""
        store = RelationStore()
        store.add(KnowledgeRelation(source_id="k-1", target_id="k-2"))
        store.add(KnowledgeRelation(source_id="k-3", target_id="k-4"))
        store.add(KnowledgeRelation(source_id="k-1", target_id="k-5"))
        results = store.query(source_id="k-1")
        assert len(results) == 2
        assert all(r.source_id == "k-1" for r in results)

    def test_get_related(self):
        """get_related 返回包含指定知识的所有关系（双向）。"""
        store = RelationStore()
        rel1 = store.add(KnowledgeRelation(source_id="k-1", target_id="k-2"))
        rel2 = store.add(KnowledgeRelation(source_id="k-3", target_id="k-1"))
        rel3 = store.add(KnowledgeRelation(source_id="k-4", target_id="k-5"))
        related = store.get_related("k-1")
        assert len(related) == 2
        related_ids = {r.id for r in related}
        assert rel1.id in related_ids
        assert rel2.id in related_ids
        assert rel3.id not in related_ids


# ---------------------------------------------------------------------------
# TestL3ContextSource — L3 上下文数据源测试
# ---------------------------------------------------------------------------


class TestL3ContextSource:
    """L3ContextSource 的收集、过滤和空存储测试。"""

    @pytest.mark.asyncio
    async def test_collect_returns_context_items(self):
        """collect() 返回 ContextItem 列表。"""
        writer = L3Writer()
        kb = _make_knowledge(
            knowledge_type=KnowledgeNodeType.GLOSSARY,
            confidence_score=0.8,
            last_verified_at=datetime.now(UTC),
        )
        writer.append(kb)
        source = L3ContextSource(knowledge_store=writer)
        items = await source.collect(
            session_id="s-1",
            project_id="proj-1",
            query="术语定义",
        )
        assert len(items) >= 1
        assert all(isinstance(item, ContextItem) for item in items)
        assert items[0].kind == ContextKind.MEMORY

    @pytest.mark.asyncio
    async def test_collect_filters_by_confidence(self):
        """低于置信度阈值的条目被排除。"""
        writer = L3Writer()
        high_conf = _make_knowledge(
            confidence_score=0.9,
            last_verified_at=datetime.now(UTC),
        )
        low_conf = _make_knowledge(
            confidence_score=0.3,
            last_verified_at=datetime.now(UTC),
        )
        writer.append(high_conf)
        writer.append(low_conf)
        source = L3ContextSource(knowledge_store=writer, min_confidence=0.6)
        items = await source.collect(
            session_id="s-1",
            project_id="proj-1",
            query="测试查询",
        )
        returned_ids = {item.metadata.get("knowledge_id") for item in items}
        assert high_conf.id in returned_ids
        assert low_conf.id not in returned_ids

    @pytest.mark.asyncio
    async def test_collect_empty_when_no_store(self):
        """无存储时 collect() 返回空列表。"""
        source = L3ContextSource(knowledge_store=None)
        items = await source.collect(
            session_id="s-1",
            project_id="proj-1",
            query="任意查询",
        )
        assert items == []
