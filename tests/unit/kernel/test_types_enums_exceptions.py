"""Kernel 类型、枚举、异常的单元测试。"""

import pytest

from reqradar.kernel.enums import (
    ChangeStatus,
    CheckpointType,
    EventType,
    EvidenceType,
    FreshnessStatus,
    ReleaseStatus,
    SessionStatus,
    TaskStatus,
)
from reqradar.kernel.exceptions import (
    CheckpointException,
    ConfigException,
    ContextBudgetExceededException,
    FatalError,
    GitException,
    IndexException,
    LLMException,
    LoaderException,
    ParseException,
    ReportException,
    ReqRadarException,
    SessionException,
    ToolExecutionError,
    VectorStoreException,
    VisionNotConfiguredError,
)
from reqradar.kernel.types import (
    ContextItem,
    ContextKind,
    Domain,
    Scope,
    ScoredContextItem,
    TokenBudget,
)

# ---------------------------------------------------------------------------
# 类型测试
# ---------------------------------------------------------------------------


class TestContextKind:
    def test_all_values_are_strings(self):
        for member in ContextKind:
            assert isinstance(member.value, str)

    def test_source_code_value(self):
        assert ContextKind.SOURCE_CODE == "SOURCE_CODE"

    def test_inferred_knowledge_value(self):
        assert ContextKind.INFERRED_KNOWLEDGE == "INFERRED_KNOWLEDGE"


class TestScope:
    def test_scope_ordering(self):
        assert Scope.GLOBAL == "global"
        assert Scope.PROJECT == "project"
        assert Scope.USER == "user"


class TestDomain:
    def test_all_domains_exist(self):
        expected = {"session", "event", "checkpoint", "evidence", "llm", "tool", "context", "l3"}
        actual = {d.value for d in Domain}
        assert actual == expected


class TestTokenBudget:
    def test_available_equals_total_when_no_reserved(self):
        budget = TokenBudget(total=1000)
        assert budget.available == 1000

    def test_available_reduced_by_reserved(self):
        budget = TokenBudget(total=1000, reserved=200)
        assert budget.available == 800

    def test_available_never_negative(self):
        budget = TokenBudget(total=100, reserved=500)
        assert budget.available == 0

    def test_frozen(self):
        budget = TokenBudget(total=1000)
        with pytest.raises(AttributeError):
            budget.total = 2000


class TestContextItem:
    def test_default_metadata_is_empty_dict(self):
        item = ContextItem(content="test", kind=ContextKind.MEMORY)
        assert item.metadata == {}

    def test_metadata_isolation(self):
        item1 = ContextItem(content="a", kind=ContextKind.MEMORY)
        item2 = ContextItem(content="b", kind=ContextKind.MEMORY)
        item1.metadata["key"] = "value"
        assert "key" not in item2.metadata


class TestScoredContextItem:
    def test_defaults(self):
        item = ContextItem(content="test", kind=ContextKind.SOURCE_CODE)
        scored = ScoredContextItem(item=item)
        assert scored.score == 0.0
        assert scored.token_count == 0


# ---------------------------------------------------------------------------
# 枚举测试
# ---------------------------------------------------------------------------


class TestSessionStatus:
    def test_created_is_default(self):
        assert SessionStatus.CREATED == "CREATED"

    def test_all_11_states_exist(self):
        expected = {
            "CREATED",
            "READY",
            "RUNNING",
            "CHECKPOINTING",
            "COMPLETED",
            "FAILED",
            "CANCELLING",
            "CANCELLED",
            "TIMEOUT",
            "ABORTED",
            "WAITING_INPUT",
        }
        actual = {s.value for s in SessionStatus}
        assert actual == expected


class TestEventType:
    def test_session_events_exist(self):
        session_events = [
            EventType.SESSION_CREATED,
            EventType.SESSION_STARTED,
            EventType.SESSION_COMPLETED,
            EventType.SESSION_FAILED,
        ]
        for evt in session_events:
            assert isinstance(evt.value, str)

    def test_tool_events_exist(self):
        assert EventType.TOOL_INVOKED == "TOOL_INVOKED"
        assert EventType.TOOL_RETURNED == "TOOL_RETURNED"


class TestEvidenceType:
    def test_all_10_types(self):
        assert len(EvidenceType) == 10

    def test_code_evidence_value(self):
        assert EvidenceType.CODE_EVIDENCE == "code_evidence"


class TestCheckpointType:
    def test_step_complete(self):
        assert CheckpointType.STEP_COMPLETE == "STEP_COMPLETE"


class TestFreshnessStatus:
    def test_all_states(self):
        expected = {"active", "historical", "superseded", "deprecated", "stale", "conflicted"}
        actual = {s.value for s in FreshnessStatus}
        assert actual == expected


class TestV1Enums:
    def test_task_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"

    def test_change_status_values(self):
        assert ChangeStatus.PENDING == "pending"
        assert ChangeStatus.ACCEPTED == "accepted"

    def test_release_status_values(self):
        assert ReleaseStatus.DRAFT == "draft"
        assert ReleaseStatus.PUBLISHED == "published"


# ---------------------------------------------------------------------------
# 异常测试
# ---------------------------------------------------------------------------


class TestReqRadarException:
    def test_message_stored(self):
        exc = ReqRadarException("test error")
        assert exc.message == "test error"
        assert str(exc) == "test error"

    def test_cause_chain(self):
        original = ValueError("root cause")
        exc = ReqRadarException("wrapped", cause=original)
        assert exc.cause is original
        assert exc.__cause__ is original

    def test_no_cause(self):
        exc = ReqRadarException("no cause")
        assert exc.cause is None
        assert exc.__cause__ is None


class TestExceptionHierarchy:
    def test_all_subclasses_inherit_from_base(self):
        subclasses = [
            FatalError,
            ConfigException,
            LLMException,
            ParseException,
            VectorStoreException,
            GitException,
            IndexException,
            ReportException,
            LoaderException,
            VisionNotConfiguredError,
            ToolExecutionError,
            CheckpointException,
            SessionException,
            ContextBudgetExceededException,
        ]
        for cls in subclasses:
            assert issubclass(
                cls, ReqRadarException
            ), f"{cls.__name__} should inherit ReqRadarException"

    def test_fatal_error_is_exception(self):
        with pytest.raises(ReqRadarException):
            raise FatalError("fatal")

    def test_llm_exception_with_cause(self):
        original = ConnectionError("timeout")
        exc = LLMException("LLM failed", cause=original)
        assert exc.__cause__ is original


class TestContextBudgetExceededException:
    def test_budget_and_actual_stored(self):
        exc = ContextBudgetExceededException("over budget", budget=1000, actual=1200)
        assert exc.budget == 1000
        assert exc.actual == 1200

    def test_defaults_to_zero(self):
        exc = ContextBudgetExceededException("over")
        assert exc.budget == 0
        assert exc.actual == 0
