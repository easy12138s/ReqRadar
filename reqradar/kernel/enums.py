"""全局枚举定义 — V1 + V2 合并的唯一枚举定义源。"""

from enum import Enum


class SessionStatus(str, Enum):
    """认知会话状态，对应 11 状态状态机。"""

    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    CHECKPOINTING = "CHECKPOINTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    ABORTED = "ABORTED"
    WAITING_INPUT = "WAITING_INPUT"


class EventType(str, Enum):
    """事件类型，对应 Event Stream 三级事件体系。"""

    SESSION_CREATED = "SESSION_CREATED"
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_CHECKPOINTED = "SESSION_CHECKPOINTED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_FAILED = "SESSION_FAILED"
    SESSION_CANCELLING = "SESSION_CANCELLING"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"
    SESSION_ABORTED = "SESSION_ABORTED"
    SESSION_WAITING_INPUT = "SESSION_WAITING_INPUT"
    SESSION_RESUMED = "SESSION_RESUMED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    TOOL_INVOKED = "TOOL_INVOKED"
    TOOL_RETURNED = "TOOL_RETURNED"
    TOOL_RETRY = "TOOL_RETRY"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_PERMISSION_DENIED = "TOOL_PERMISSION_DENIED"
    TOOL_CHECKPOINT_FAILED = "TOOL_CHECKPOINT_FAILED"
    CONTEXT_COLLECTED = "CONTEXT_COLLECTED"
    CONTEXT_SCORED = "CONTEXT_SCORED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    DIMENSION_CHANGED = "DIMENSION_CHANGED"


class EventLevel(str, Enum):
    """事件层级。"""

    SESSION = "session"
    REASONING = "reasoning"
    COGNITIVE = "cognitive"


class EvidenceType(str, Enum):
    """证据类型，对应 10 种证据分类。"""

    CODE_EVIDENCE = "code_evidence"
    REQUIREMENT_REF = "requirement_ref"
    ARCHITECTURE_DOC = "architecture_doc"
    GIT_HISTORY = "git_history"
    MEMORY_REF = "memory_ref"
    TOOL_OUTPUT = "tool_output"
    INFERENCE = "inference"
    CONSTRAINT = "constraint"
    RISK_INDICATOR = "risk_indicator"
    VERIFICATION_RESULT = "verification_result"


class EvidenceStatus(str, Enum):
    """证据状态。"""

    DISCOVERED = "discovered"
    VERIFIED = "verified"
    CHALLENGED = "challenged"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"


class CheckpointType(str, Enum):
    """检查点类型。"""

    STEP_COMPLETE = "STEP_COMPLETE"
    TOOL_PRE = "TOOL_PRE"
    TOOL_POST = "TOOL_POST"
    MANUAL = "MANUAL"
    PERIODIC = "PERIODIC"
    CHATBACK_SNAPSHOT = "CHATBACK_SNAPSHOT"


class DimensionStatus(str, Enum):
    """七维度评估状态（M-02 §3.1）。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class RiskLevel(str, Enum):
    """风险等级。"""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FreshnessStatus(str, Enum):
    """L3 知识新鲜度状态。"""

    ACTIVE = "active"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    STALE = "stale"
    CONFLICTED = "conflicted"


class RelationType(str, Enum):
    """知识图谱关系类型。"""

    DEPENDS_ON = "DEPENDS_ON"
    IMPACTS = "IMPACTS"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    EVOLVES_FROM = "EVOLVES_FROM"
    MITIGATES = "MITIGATES"
    VIOLATES = "VIOLATES"
    DERIVED_FROM = "DERIVED_FROM"
    CORROBORATES = "CORROBORATES"
    SUPERSEDES = "SUPERSEDES"


class KnowledgeNodeType(str, Enum):
    """知识图谱节点类型。"""

    GLOSSARY = "glossary"
    MODULE_PROFILE = "module_profile"
    CONSTRAINT = "constraint"
    DECISION = "decision"
    RISK = "risk"
    REQUIREMENT = "requirement"
    INCIDENT = "incident"
    PATTERN = "pattern"


class TaskStatus(str, Enum):
    """V1 分析任务状态（过渡期保留）。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChangeStatus(str, Enum):
    """变更审核状态。"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReleaseStatus(str, Enum):
    """需求发布状态。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
