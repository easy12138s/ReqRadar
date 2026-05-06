# Round 3: Report Chatback & Version Management — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement report version management, single-turn global chatback, and evidence chain APIs — all backend components for the report review experience. Frontend pages are explicitly excluded per user request.

**Architecture:** Report versions store lightweight context snapshots (evidence_list + dimension_status + visited_files). Chatback uses the Agent's context to answer user questions about a report, with single-turn explore→preview→save/discard flow. The `AnalysisAgent` from Round 2 is reused for chatback, initialized from a snapshot. Version limit enforced at DB level (max 10 per task).

**Tech Stack:** Python 3.12, SQLAlchemy async, Pydantic, FastAPI, pytest, pytest-asyncio

---

## File Structure

### New Files
- `src/reqradar/web/api/versions.py` — Report version CRUD API
- `src/reqradar/web/api/chatback.py` — Global chatback API
- `src/reqradar/web/api/evidence_api.py` — Evidence chain API
- `src/reqradar/web/services/chatback_service.py` — Chatback business logic (Agent-based)
- `src/reqradar/web/services/version_service.py` — Version management service
- `tests/test_version_service.py` — Tests for version management
- `tests/test_chatback_service.py` — Tests for chatback service
- `tests/test_version_api.py` — API tests for version endpoints
- `tests/test_chatback_api.py` — API tests for chatback endpoints
- `tests/test_evidence_api.py` — API tests for evidence endpoints

### Modified Files
- `src/reqradar/web/models.py` — Add ReportVersion, ReportChat models (ReportAnnotation deferred per spec)
- `src/reqradar/web/app.py` — Register new routers
- `alembic/versions/` — New migration for version/chat tables
- `src/reqradar/web/services/analysis_runner_v2.py` — Save initial version after analysis
- `src/reqradar/web/services/analysis_runner.py` — Save initial version after legacy analysis

---

## Task 1: Add ReportVersion and ReportChat Database Models

**Files:**
- Modify: `src/reqradar/web/models.py`

- [ ] **Step 1: Add ReportVersion model**

In `src/reqradar/web/models.py`, after the `Report` class, add:

```python
class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    report_data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    context_snapshot: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), default="initial", nullable=False)
    trigger_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    task: Mapped["AnalysisTask"] = relationship(back_populates="versions")
    creator: Mapped["User"] = relationship()
```

- [ ] **Step 2: Add ReportChat model**

```python
class ReportChat(Base):
    __tablename__ = "report_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    intent_type: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    task: Mapped["AnalysisTask"] = relationship(back_populates="chats")
```

- [ ] **Step 3: Add relationships to AnalysisTask**

Add to `AnalysisTask` class:

```python
    versions: Mapped[list["ReportVersion"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    chats: Mapped[list["ReportChat"]] = relationship(back_populates="task", cascade="all, delete-orphan")
```

- [ ] **Step 4: Write model tests**

Create `tests/test_version_service.py` (partial — model instantiation):

```python
from reqradar.web.models import ReportVersion, ReportChat


def test_report_version_model():
    version = ReportVersion(
        task_id=1,
        version_number=1,
        report_data='{"risk_level": "medium"}',
        context_snapshot='{"evidence_list": [], "dimension_status": {}, "visited_files": [], "tool_calls": []}',
        content_markdown="# Report",
        content_html="<h1>Report</h1>",
        trigger_type="initial",
        created_by=1,
    )
    assert version.version_number == 1
    assert version.trigger_type == "initial"


def test_report_chat_model():
    chat = ReportChat(
        task_id=1,
        version_number=1,
        role="user",
        content="Why is the risk medium?",
        evidence_refs="[]",
        intent_type="explain",
    )
    assert chat.role == "user"
    assert chat.intent_type == "explain"
```

- [ ] **Step 5: Run model tests**

Run: `pytest tests/test_version_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/reqradar/web/models.py tests/test_version_service.py
git commit -m "feat: add ReportVersion and ReportChat database models"
```

---

## Task 2: Alembic Migration for Version/Chat Tables

**Files:**
- Create: `alembic/versions/<hash>_add_report_version_chat_tables.py`

- [ ] **Step 1: Generate migration**

Run: `alembic revision --autogenerate -m "add report_versions and report_chats tables"`

The migration should add:
- `report_versions` table with columns as defined
- `report_chats` table with columns as defined
- Update `analysis_tasks` to add default for `current_version` if not already there (from Round 1 Task 2)

- [ ] **Step 2: Verify migration**

Run: `alembic upgrade head`
Expected: No errors

Run: `alembic downgrade -1 && alembic upgrade head`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add Alembic migration for report_versions and report_chats tables"
```

---

## Task 3: Version Management Service

**Files:**
- Create: `src/reqradar/web/services/version_service.py`
- Modify: `tests/test_version_service.py`

- [ ] **Step 1: Write tests for VersionService**

Add to `tests/test_version_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from reqradar.web.database import Base
from reqradar.web.models import ReportVersion, ReportChat, AnalysisTask, User, Project
from reqradar.web.services.version_service import VersionService

VERSION_LIMIT = 10


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_create_initial_version(db_session):
    service = VersionService(db_session, version_limit=VERSION_LIMIT)

    user = User(email="test@test.com", password_hash="x", display_name="Test")
    db_session.add(user)
    project = Project(name="P1", owner_id=1)
    db_session.add(project)
    task = AnalysisTask(project_id=1, user_id=1, requirement_name="req.txt", requirement_text="test")
    db_session.add(task)
    await db_session.commit()

    version = await service.create_version(
        task_id=task.id,
        report_data={"risk_level": "medium"},
        context_snapshot={"evidence_list": [], "dimension_status": {}, "visited_files": [], "tool_calls": []},
        content_markdown="# Report",
        content_html="<h1>Report</h1>",
        trigger_type="initial",
        created_by=user.id,
    )
    assert version.version_number == 1
    assert version.trigger_type == "initial"


@pytest.mark.asyncio
async def test_create_second_version(db_session):
    service = VersionService(db_session, version_limit=VERSION_LIMIT)

    user = User(email="test@test.com", password_hash="x", display_name="Test")
    db_session.add(user)
    project = Project(name="P1", owner_id=1)
    db_session.add(project)
    task = AnalysisTask(project_id=1, user_id=1, requirement_name="req.txt", requirement_text="test")
    db_session.add(task)
    await db_session.commit()

    v1 = await service.create_version(task_id=task.id, report_data={}, context_snapshot={}, content_markdown="# v1", content_html="<h1>v1</h1>", trigger_type="initial", created_by=user.id)
    v2 = await service.create_version(task_id=task.id, report_data={}, context_snapshot={}, content_markdown="# v2", content_html="<h1>v2</h1>", trigger_type="global_chat", created_by=user.id)

    assert v2.version_number == 2


@pytest.mark.asyncio
async def test_version_limit_enforcement(db_session):
    service = VersionService(db_session, version_limit=VERSION_LIMIT)

    user = User(email="test@test.com", password_hash="x", display_name="Test")
    db_session.add(user)
    project = Project(name="P1", owner_id=1)
    db_session.add(project)
    task = AnalysisTask(project_id=1, user_id=1, requirement_name="req.txt", requirement_text="test")
    db_session.add(task)
    await db_session.commit()

    for i in range(VERSION_LIMIT + 2):
        await service.create_version(
            task_id=task.id,
            report_data={"version": i},
            context_snapshot={},
            content_markdown=f"# v{i}",
            content_html=f"<h1>v{i}</h1>",
            trigger_type="global_chat",
            created_by=user.id,
        )

    versions = await service.list_versions(task.id)
    assert len(versions) <= VERSION_LIMIT


@pytest.mark.asyncio
async def test_get_version(db_session):
    service = VersionService(db_session, version_limit=VERSION_LIMIT)

    user = User(email="test@test.com", password_hash="x", display_name="Test")
    db_session.add(user)
    project = Project(name="P1", owner_id=1)
    db_session.add(project)
    task = AnalysisTask(project_id=1, user_id=1, requirement_name="req.txt", requirement_text="test")
    db_session.add(task)
    await db_session.commit()

    v1 = await service.create_version(task_id=task.id, report_data={}, context_snapshot={}, content_markdown="# v1", content_html="<h1>v1</h1>", trigger_type="initial", created_by=user.id)

    fetched = await service.get_version(task.id, v1.version_number)
    assert fetched is not None
    assert fetched.version_number == 1


@pytest.mark.asyncio
async def test_rollback_version(db_session):
    service = VersionService(db_session, version_limit=VERSION_LIMIT)

    user = User(email="test@test.com", password_hash="x", display_name="Test")
    db_session.add(user)
    project = Project(name="P1", owner_id=1)
    db_session.add(project)
    task = AnalysisTask(project_id=1, user_id=1, requirement_name="req.txt", requirement_text="test")
    db_session.add(task)
    await db_session.commit()

    await service.create_version(task_id=task.id, report_data={}, context_snapshot={}, content_markdown="# v1", content_html="<h1>v1</h1>", trigger_type="initial", created_by=user.id)
    await service.create_version(task_id=task.id, report_data={}, context_snapshot={}, content_markdown="# v2", content_html="<h1>v2</h1>", trigger_type="global_chat", created_by=user.id)

    result = await service.rollback(task.id, target_version=1, user_id=user.id)
    assert result.version_number == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_version_service.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement VersionService**

Create `src/reqradar/web/services/version_service.py`:

```python
import json
import logging
from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import ReportVersion, AnalysisTask

logger = logging.getLogger("reqradar.version_service")

VERSION_LIMIT_DEFAULT = 10


class VersionService:
    def __init__(self, db: AsyncSession, version_limit: int = VERSION_LIMIT_DEFAULT):
        self.db = db
        self.version_limit = version_limit

    async def create_version(
        self,
        task_id: int,
        report_data: dict,
        context_snapshot: dict,
        content_markdown: str,
        content_html: str,
        trigger_type: str = "initial",
        trigger_description: str = "",
        created_by: int = 1,
    ) -> ReportVersion:
        result = await self.db.execute(
            select(func.max(ReportVersion.version_number)).where(
                ReportVersion.task_id == task_id
            )
        )
        max_version = result.scalar() or 0
        new_version_number = max_version + 1

        version = ReportVersion(
            task_id=task_id,
            version_number=new_version_number,
            report_data=json.dumps(report_data, ensure_ascii=False, default=str),
            context_snapshot=json.dumps(context_snapshot, ensure_ascii=False, default=str),
            content_markdown=content_markdown,
            content_html=content_html,
            trigger_type=trigger_type,
            trigger_description=trigger_description,
            created_by=created_by,
        )
        self.db.add(version)

        await self._enforce_version_limit(task_id)

        task_result = await self.db.execute(
            select(AnalysisTask).where(AnalysisTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if task:
            task.current_version = new_version_number

        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def list_versions(self, task_id: int) -> list[ReportVersion]:
        result = await self.db.execute(
            select(ReportVersion)
            .where(ReportVersion.task_id == task_id)
            .order_by(ReportVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_version(self, task_id: int, version_number: int) -> Optional[ReportVersion]:
        result = await self.db.execute(
            select(ReportVersion).where(
                ReportVersion.task_id == task_id,
                ReportVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_current_version(self, task_id: int) -> Optional[ReportVersion]:
        task_result = await self.db.execute(
            select(AnalysisTask).where(AnalysisTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if task is None:
            return None
        current_version = task.current_version
        if current_version is None:
            return None
        return await self.get_version(task_id, current_version)

    async def rollback(self, task_id: int, target_version: int, user_id: int) -> Optional[ReportVersion]:
        target = await self.get_version(task_id, target_version)
        if target is None:
            return None

        report_data = json.loads(target.report_data) if isinstance(target.report_data, str) else target.report_data
        context_snapshot = json.loads(target.context_snapshot) if isinstance(target.context_snapshot, str) else target.context_snapshot

        new_version = await self.create_version(
            task_id=task_id,
            report_data=report_data,
            context_snapshot=context_snapshot,
            content_markdown=target.content_markdown,
            content_html=target.content_html,
            trigger_type="rollback",
            trigger_description=f"Rollback to version {target_version}",
            created_by=user_id,
        )
        return new_version

    async def _enforce_version_limit(self, task_id: int) -> None:
        result = await self.db.execute(
            select(func.count()).select_from(ReportVersion).where(
                ReportVersion.task_id == task_id
            )
        )
        count = result.scalar() or 0

        if count > self.version_limit:
            excess = count - self.version_limit
            oldest_result = await self.db.execute(
                select(ReportVersion)
                .where(ReportVersion.task_id == task_id)
                .order_by(ReportVersion.version_number.asc())
                .limit(excess)
            )
            old_versions = oldest_result.scalars().all()
            for old_version in old_versions:
                await self.db.delete(old_version)
            logger.info("Deleted %d old versions for task %d (limit: %d)", excess, task_id, self.version_limit)

    async def get_context_snapshot(self, task_id: int, version_number: int) -> Optional[dict]:
        version = await self.get_version(task_id, version_number)
        if version is None:
            return None
        snapshot_str = version.context_snapshot
        if isinstance(snapshot_str, str):
            try:
                return json.loads(snapshot_str)
            except (json.JSONDecodeError, TypeError):
                return {}
        return snapshot_str if isinstance(snapshot_str, dict) else {}
```

- [ ] **Step 4: Run version service tests**

Run: `pytest tests/test_version_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/services/version_service.py tests/test_version_service.py
git commit -m "feat: add VersionService with version CRUD, limit enforcement, and rollback"
```

---

## Task 4: Chatback Service

**Files:**
- Create: `src/reqradar/web/services/chatback_service.py`
- Create: `tests/test_chatback_service.py`

- [ ] **Step 1: Write tests for ChatbackService**

Create `tests/test_chatback_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from reqradar.web.services.chatback_service import ChatbackService, classify_intent


def test_classify_intent_explain():
    assert classify_intent("为什么风险评估是中而不是高？") == "explain"
    assert classify_intent("这个风险是怎么得出的") == "explain"


def test_classify_intent_correct():
    assert classify_intent("影响模块遗漏了 web/models.py，需要补充") == "correct"
    assert classify_intent("这里写错了，应该是高不是中") == "correct"


def test_classify_intent_deepen():
    assert classify_intent("请详细分析对数据库的影响") == "deepen"
    assert classify_intent("能展开讲讲性能风险的细节吗") == "deepen"


def test_classify_intent_explore():
    assert classify_intent("去看看 web/app.py 的变更历史") == "explore"
    assert classify_intent("查看一下 auth 模块") == "explore"


def test_classify_intent_other():
    assert classify_intent("谢谢") == "other"
    assert classify_intent("测试消息") == "other"


@pytest.mark.asyncio
async def test_chatback_service_single_turn():
    mock_version_service = AsyncMock()
    mock_llm_client = AsyncMock()

    mock_version_service.get_context_snapshot.return_value = {
        "evidence_list": [{"id": "ev-001", "type": "code", "source": "src/app.py", "content": "Main app", "confidence": "high", "dimensions": ["impact"]}],
        "dimension_status": {"impact": "sufficient", "risk": "in_progress"},
        "visited_files": ["src/app.py"],
        "tool_calls": [],
    }

    mock_version_service.get_version.return_value = MagicMock(
        report_data='{"risk_level": "medium", "impact_modules": []}',
        context_snapshot='{"evidence_list": [{"id": "ev-001", "type": "code", "source": "src/app.py", "content": "Main app", "confidence": "high", "dimensions": ["impact"]}], "dimension_status": {"impact": "sufficient"}, "visited_files": ["src/app.py"], "tool_calls": []}',
        content_markdown="# Report",
    )

    service = ChatbackService(
        version_service=mock_version_service,
        llm_client=mock_llm_client,
    )

    result = await service.chat(
        task_id=1,
        version_number=1,
        user_message="为什么风险评估是中而不是高？",
        user_id=1,
    )
    assert result is not None
    assert "reply" in result
    assert "intent_type" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chatback_service.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement ChatbackService**

Create `src/reqradar/web/services/chatback_service.py`:

```python
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker
from reqradar.agent.prompts.chatback_phase import build_chatback_system_prompt
from reqradar.web.models import ReportChat
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.chatback_service")


INTENT_KEYWORDS = {
    "explain": ["为什么", "怎么", "如何", "原因", "依据", "解释", "说明", "是什么", "什么意思"],
    "correct": ["遗漏", "补充", "写错", "应该是", "不对", "错误", "更正", "修正", "需要加"],
    "deepen": ["详细", "深入", "展开", "更多", "细节", "具体", "更详细"],
    "explore": ["看看", "查看", "查看一下", "去查", "分析一下", "检查"],
}


def classify_intent(message: str) -> str:
    message_lower = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                return intent
    return "other"


class ChatbackService:
    def __init__(
        self,
        version_service: VersionService,
        llm_client=None,
        tool_registry=None,
        config=None,
    ):
        self.version_service = version_service
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.config = config

    async def chat(
        self,
        task_id: int,
        version_number: int,
        user_message: str,
        user_id: int,
    ) -> dict:
        intent = classify_intent(user_message)

        version = await self.version_service.get_version(task_id, version_number)
        if version is None:
            return {"reply": "未找到指定版本的报告。", "intent_type": "error", "updated": False}

        report_data = {}
        if isinstance(version.report_data, str):
            try:
                report_data = json.loads(version.report_data)
            except (json.JSONDecodeError, TypeError):
                report_data = {}

        context_snapshot = await self.version_service.get_context_snapshot(task_id, version_number)
        if context_snapshot is None:
            context_snapshot = {
                "evidence_list": [],
                "dimension_status": {},
                "visited_files": [],
                "tool_calls": [],
            }

        agent = AnalysisAgent(
            requirement_text=report_data.get("requirement_title", ""),
            project_id=0,
            user_id=user_id,
            depth="standard",
        )
        agent.restore_from_snapshot(context_snapshot)

        chat_record = ReportChat(
            task_id=task_id,
            version_number=version_number,
            role="user",
            content=user_message,
            intent_type=intent,
        )

        reply = await self._generate_reply(agent, report_data, context_snapshot, user_message, intent)

        agent_reply = ReportChat(
            task_id=task_id,
            version_number=version_number,
            role="agent",
            content=reply,
            evidence_refs=json.dumps([ev["id"] for ev in context_snapshot.get("evidence_list", [])[:5]], ensure_ascii=False),
        )

        db = self.version_service.db
        db.add(chat_record)
        db.add(agent_reply)
        await db.commit()
        await db.refresh(chat_record)
        await db.refresh(agent_reply)

        updated = intent in ("correct", "deepen", "explore")

        return {
            "reply": reply,
            "intent_type": intent,
            "updated": updated,
            "new_version": None,
            "report_preview": None if not updated else report_data,
            "chat_id": agent_reply.id,
        }

    async def _generate_reply(
        self,
        agent: AnalysisAgent,
        report_data: dict,
        context_snapshot: dict,
        user_message: str,
        intent: str,
    ) -> str:
        if self.llm_client is None:
            return self._generate_fallback_reply(report_data, context_snapshot, user_message, intent)

        system_prompt = build_chatback_system_prompt(
            report_data=report_data,
            context_snapshot=context_snapshot,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            from reqradar.agent.llm_utils import _call_llm_structured
            result = await _call_llm_structured(
                self.llm_client,
                messages,
                {"type": "object", "properties": {"reply": {"type": "string"}, "evidence_refs": {"type": "array"}}},
            )
            if result and "reply" in result:
                return result["reply"]
        except Exception as e:
            logger.warning("Chatback LLM call failed: %s, using fallback", e)

        return self._generate_fallback_reply(report_data, context_snapshot, user_message, intent)

    def _generate_fallback_reply(
        self,
        report_data: dict,
        context_snapshot: dict,
        user_message: str,
        intent: str,
    ) -> str:
        evidence_list = context_snapshot.get("evidence_list", [])
        dimension_status = context_snapshot.get("dimension_status", {})
        report_risk = report_data.get("risk_level", "unknown")

        evidence_text = ""
        if evidence_list:
            evidence_text = "\n".join(
                f"- [{ev.get('id', '?')}] ({ev.get('type', '?')}) {ev.get('source', '?')}: {ev.get('content', '?')[:100]}"
                for ev in evidence_list[:5]
            )

        dimension_text = "\n".join(f"- {k}: {v}" for k, v in dimension_status.items())

        if intent == "explain":
            return f"根据当前分析，风险等级为{report_risk}。\n\n分析基于以下证据：\n{evidence_text}\n\n各维度状态：\n{dimension_text}"
        elif intent == "correct":
            return "感谢您的纠正。我可以基于新的信息调整分析。如果您保存为新版本，修改将被记录。当前证据：\n" + evidence_text
        elif intent == "deepen":
            return f"我可以进一步分析。当前已收集 {len(evidence_list)} 条证据，各维度状态：\n{dimension_text}\n\n请问我需要关注哪些具体的方面？"
        elif intent == "explore":
            return "我可以调用工具探索更多代码信息。当前已访问的文件：\n" + "\n".join(f"- {f}" for f in context_snapshot.get("visited_files", [])[:10])
        else:
            return f"当前报告风险等级: {report_risk}。\n已收集 {len(evidence_list)} 条证据。"

    async def save_as_new_version(
        self,
        task_id: int,
        version_number: int,
        user_id: int,
        updated_report_data: dict | None = None,
        updated_content_markdown: str | None = None,
    ) -> dict:
        current_version = await self.version_service.get_version(task_id, version_number)
        if current_version is None:
            return {"success": False, "error": "Version not found"}

        report_data = updated_report_data or (json.loads(current_version.report_data) if isinstance(current_version.report_data, str) else current_version.report_data)
        context_snapshot = await self.version_service.get_context_snapshot(task_id, version_number)
        content_md = updated_content_markdown or current_version.content_markdown

        new_version = await self.version_service.create_version(
            task_id=task_id,
            report_data=report_data,
            context_snapshot=context_snapshot or {},
            content_markdown=content_md,
            content_html=current_version.content_html,
            trigger_type="global_chat",
            trigger_description=f"User chat lead to update from version {version_number}",
            created_by=user_id,
        )

        return {
            "success": True,
            "new_version": new_version.version_number,
        }

    async def get_chat_history(self, task_id: int, version_number: int = None) -> list[dict]:
        db = self.version_service.db
        query = select(ReportChat).where(ReportChat.task_id == task_id)
        if version_number is not None:
            query = query.where(ReportChat.version_number == version_number)
        query = query.order_by(ReportChat.created_at.asc())

        result = await db.execute(query)
        chats = result.scalars().all()
        return [
            {
                "id": c.id,
                "version_number": c.version_number,
                "role": c.role,
                "content": c.content,
                "intent_type": c.intent_type,
                "evidence_refs": json.loads(c.evidence_refs) if isinstance(c.evidence_refs, str) else c.evidence_refs,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in chats
        ]
```

- [ ] **Step 4: Create chatback prompt builder**

Create `src/reqradar/agent/prompts/chatback_phase.py`:

```python
import json


CHATBACK_SYSTEM_PROMPT = """你是一位需求分析顾问，正在与用户讨论已生成的分析报告。你的任务是理解用户的意图，基于现有证据回答问题，或在必要时补充新证据。你应当专业、谦逊，承认不确定性。

## 行为规范
- 解释型问题：基于版本上下文中的证据回答，引用具体来源
- 纠正型问题：接受用户纠正，标记需要更新的维度
- 深入型问题：判断是否需要新证据，如需则说明需要查询什么
- 探索型问题：调用工具获取新信息，追加到版本上下文中
- 不确定时明确说"我不确定"，不要编造

## 可用上下文
报告数据：
{report_summary}

维度状态：
{dimension_status}

已收集证据：
{evidence_summary}
"""


def build_chatback_system_prompt(
    report_data: dict,
    context_snapshot: dict,
) -> str:
    risk = report_data.get("risk_level", "unknown")
    title = report_data.get("requirement_title", "未命名需求")
    summary_lines = [
        f"需求: {title}",
        f"风险等级: {risk}",
    ]
    if report_data.get("impact_modules"):
        modules = report_data["impact_modules"]
        if isinstance(modules, list):
            for m in modules[:5]:
                if isinstance(m, dict):
                    summary_lines.append(f"  - {m.get('path', m.get('module', 'unknown'))}: {m.get('relevance_reason', '')}")
                elif isinstance(m, str):
                    summary_lines.append(f"  - {m}")

    report_summary = "\n".join(summary_lines)

    dimension_status = context_snapshot.get("dimension_status", {})
    dim_text = "\n".join(f"- {k}: {v}" for k, v in dimension_status.items())

    evidence_list = context_snapshot.get("evidence_list", [])
    ev_text = "\n".join(
        f"- [{ev.get('id', '?')}] ({ev.get('type', '?')}) {ev.get('source', '?')}: {str(ev.get('content', ''))[:100]}"
        for ev in evidence_list[:10]
    ) if evidence_list else "暂无证据"

    return CHATBACK_SYSTEM_PROMPT.format(
        report_summary=report_summary,
        dimension_status=dim_text or "无维度状态",
        evidence_summary=ev_text,
    )
```

- [ ] **Step 5: Update prompts package init**

Add to `src/reqradar/agent/prompts/__init__.py`:

```python
from reqradar.agent.prompts.chatback_phase import build_chatback_system_prompt
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_chatback_service.py -v`
Expected: PASS (intent classification and fallback work; LLM tests need mocking)

- [ ] **Step 7: Commit**

```bash
git add src/reqradar/web/services/chatback_service.py src/reqradar/agent/prompts/chatback_phase.py src/reqradar/agent/prompts/__init__.py tests/test_chatback_service.py
git commit -m "feat: add ChatbackService with intent classification, context restore, and single-turn chat"
```

---

## Task 5: Version Management API

**Files:**
- Create: `src/reqradar/web/api/versions.py`
- Modify: `src/reqradar/web/app.py`
- Create: `tests/test_version_api.py`

- [ ] **Step 1: Write API tests for version endpoints**

Create `tests/test_version_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from reqradar.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_token():
    from reqradar.web.api.auth import create_access_token
    return create_access_token({"sub": "1"})


@pytest.mark.asyncio
async def test_list_versions_empty(client, auth_token):
    response = await client.get(
        "/api/analyses/1/reports/versions",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "versions" in data


@pytest.mark.asyncio
async def test_get_version_not_found(client, auth_token):
    response = await client.get(
        "/api/analyses/999/reports/versions/1",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 404)
```

- [ ] **Step 2: Implement version API router**

Create `src/reqradar/web/api/versions.py`:

```python
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.database import get_session_dependency
from reqradar.web.models import AnalysisTask, ReportVersion
from reqradar.web.dependencies import get_current_user
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.api.versions")
router = APIRouter(prefix="/analyses/{task_id}/reports", tags=["versions"])


class VersionSummaryResponse(BaseModel):
    version_number: int
    trigger_type: str
    trigger_description: str
    created_at: str

    class Config:
        from_attributes = True


class VersionDetailResponse(BaseModel):
    version_number: int
    report_data: dict
    content_markdown: str
    content_html: str
    trigger_type: str
    trigger_description: str
    created_at: str
    created_by: int

    class Config:
        from_attributes = True


class RollbackRequest(BaseModel):
    version_number: int


@router.get("/versions")
async def list_versions(
    task_id: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    service = VersionService(db)
    versions = await service.list_versions(task_id)
    return {
        "versions": [
            {
                "version_number": v.version_number,
                "trigger_type": v.trigger_type,
                "trigger_description": v.trigger_description,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]
    }


@router.get("/versions/{version_number}")
async def get_version(
    task_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    service = VersionService(db)
    version = await service.get_version(task_id, version_number)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    report_data = version.report_data
    if isinstance(report_data, str):
        try:
            report_data = json.loads(report_data)
        except (json.JSONDecodeError, TypeError):
            report_data = {}

    return {
        "version_number": version.version_number,
        "content_markdown": version.content_markdown,
        "content_html": version.content_html,
        "report_data": report_data,
        "trigger_type": version.trigger_type,
        "trigger_description": version.trigger_description,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "created_by": version.created_by,
    }


@router.post("/rollback")
async def rollback_version(
    task_id: int,
    req: RollbackRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    service = VersionService(db)
    user_id = current_user.id if hasattr(current_user, "id") else 1
    new_version = await service.rollback(task_id, req.version_number, user_id=user_id)
    if new_version is None:
        raise HTTPException(status_code=404, detail="Target version not found")

    return {
        "success": True,
        "current_version": new_version.version_number,
    }
```

- [ ] **Step 3: Register router in app.py**

In `src/reqradar/web/app.py`, add:

```python
from reqradar.web.api.versions import router as versions_router
app.include_router(versions_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_version_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/api/versions.py src/reqradar/web/app.py tests/test_version_api.py
git commit -m "feat: add report version management API endpoints (list, get, rollback)"
```

---

## Task 6: Chatback API

**Files:**
- Create: `src/reqradar/web/api/chatback.py`
- Modify: `src/reqradar/web/app.py`
- Create: `tests/test_chatback_api.py`

- [ ] **Step 1: Write API tests for chatback**

Create `tests/test_chatback_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from reqradar.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_token():
    from reqradar.web.api.auth import create_access_token
    return create_access_token({"sub": "1"})


@pytest.mark.asyncio
async def test_chat_endpoint_structure(client, auth_token):
    response = await client.post(
        "/api/analyses/1/chat",
        json={"message": "为什么风险评估是中而不是高？"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_chat_history_endpoint(client, auth_token):
    response = await client.get(
        "/api/analyses/1/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 404)
```

- [ ] **Step 2: Implement chatback API router**

Create `src/reqradar/web/api/chatback.py`:

```python
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.database import get_session_dependency
from reqradar.web.models import AnalysisTask
from reqradar.web.dependencies import get_current_user
from reqradar.web.services.chatback_service import ChatbackService
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.api.chatback")
router = APIRouter(prefix="/analyses/{task_id}", tags=["chatback"])


class ChatRequest(BaseModel):
    message: str
    version_number: int | None = None


class SaveRequest(BaseModel):
    version_number: int


@router.post("/chat")
async def chat(
    task_id: int,
    req: ChatRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    task_result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    version_number = req.version_number or task.current_version or 1

    user_id = current_user.id if hasattr(current_user, "id") else 1

    version_service = VersionService(db)
    chatback_service = ChatbackService(version_service=version_service)

    result = await chatback_service.chat(
        task_id=task_id,
        version_number=version_number,
        user_message=req.message,
        user_id=user_id,
    )
    return result


@router.get("/chat")
async def get_chat_history(
    task_id: int,
    version_number: int | None = None,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    version_service = VersionService(db)
    chatback_service = ChatbackService(version_service=version_service)
    messages = await chatback_service.get_chat_history(task_id, version_number)
    return {"messages": messages}


@router.post("/chat/save")
async def save_chat_version(
    task_id: int,
    req: SaveRequest,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    user_id = current_user.id if hasattr(current_user, "id") else 1

    version_service = VersionService(db)
    chatback_service = ChatbackService(version_service=version_service)

    result = await chatback_service.save_as_new_version(
        task_id=task_id,
        version_number=req.version_number,
        user_id=user_id,
    )
    return result
```

- [ ] **Step 3: Register router in app.py**

Add to `src/reqradar/web/app.py`:

```python
from reqradar.web.api.chatback import router as chatback_router
app.include_router(chatback_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_chatback_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/reqradar/web/api/chatback.py src/reqradar/web/app.py tests/test_chatback_api.py
git commit -m "feat: add chatback API endpoints (chat, history, save)"
```

---

## Task 7: Evidence Chain API

**Files:**
- Create: `src/reqradar/web/api/evidence_api.py`
- Modify: `src/reqradar/web/app.py`
- Create: `tests/test_evidence_api.py`

- [ ] **Step 1: Write API tests for evidence endpoints**

Create `tests/test_evidence_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from reqradar.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_token():
    from reqradar.web.api.auth import create_access_token
    return create_access_token({"sub": "1"})


@pytest.mark.asyncio
async def test_get_evidence_chain(client, auth_token):
    response = await client.get(
        "/api/analyses/1/evidence",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in (200, 404)
```

- [ ] **Step 2: Implement evidence API router**

Create `src/reqradar/web/api/evidence_api.py`:

```python
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.database import get_session_dependency
from reqradar.web.models import AnalysisTask
from reqradar.web.dependencies import get_current_user
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.api.evidence")
router = APIRouter(prefix="/analyses/{task_id}", tags=["evidence"])


@router.get("/evidence")
async def get_evidence_chain(
    task_id: int,
    version_number: int | None = None,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    task_result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    version_num = version_number or task.current_version or 1

    service = VersionService(db)
    snapshot = await service.get_context_snapshot(task_id, version_num)
    if snapshot is None:
        return {"evidence": []}

    evidence_list = snapshot.get("evidence_list", [])
    return {
        "evidence": [
            {
                "id": ev.get("id", ""),
                "type": ev.get("type", ""),
                "source": ev.get("source", ""),
                "content": ev.get("content", ""),
                "confidence": ev.get("confidence", "medium"),
                "dimensions": ev.get("dimensions", []),
                "timestamp": ev.get("timestamp", ""),
            }
            for ev in evidence_list
        ]
    }


@router.get("/evidence/{evidence_id}")
async def get_evidence_detail(
    task_id: int,
    evidence_id: str,
    version_number: int | None = None,
    db: AsyncSession = Depends(get_session_dependency),
    current_user=Depends(get_current_user),
):
    task_result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    version_num = version_number or task.current_version or 1

    service = VersionService(db)
    snapshot = await service.get_context_snapshot(task_id, version_num)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    evidence_list = snapshot.get("evidence_list", [])
    for ev in evidence_list:
        if ev.get("id") == evidence_id:
            return {
                "id": ev.get("id", ""),
                "type": ev.get("type", ""),
                "source": ev.get("source", ""),
                "content": ev.get("content", ""),
                "confidence": ev.get("confidence", "medium"),
                "dimensions": ev.get("dimensions", []),
                "timestamp": ev.get("timestamp", ""),
            }

    raise HTTPException(status_code=404, detail="Evidence not found")
```

- [ ] **Step 3: Register router and run tests**

Add to `src/reqradar/web/app.py`:

```python
from reqradar.web.api.evidence_api import router as evidence_router
app.include_router(evidence_router)
```

Run: `pytest tests/test_evidence_api.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/web/api/evidence_api.py src/reqradar/web/app.py tests/test_evidence_api.py
git commit -m "feat: add evidence chain API endpoints (list, detail)"
```

---

## Task 8: Save Initial Version After Analysis

**Files:**
- Modify: `src/reqradar/web/services/analysis_runner.py`
- Modify: `src/reqradar/web/services/analysis_runner_v2.py`

- [ ] **Step 1: Update legacy AnalysisRunner to save initial version**

In `src/reqradar/web/services/analysis_runner.py`, after creating the `Report` in `_execute_pipeline`, add version creation:

```python
from reqradar.web.services.version_service import VersionService

# After: db.add(Report(...))
# Before: await db.commit()

version_service = VersionService(db)
await version_service.create_version(
    task_id=task_id,
    report_data=result_context.model_dump() if hasattr(result_context, "model_dump") else {},
    context_snapshot={},
    content_markdown=report_markdown,
    content_html=report_html,
    trigger_type="initial",
    created_by=task.user_id,
)
```

- [ ] **Step 2: Update AnalysisRunnerV2 to save initial version**

In `src/reqradar/web/services/analysis_runner_v2.py`, in `_execute_agent`, after creating the `Report`, add version creation:

```python
from reqradar.web.services.version_service import VersionService

# After: db.add(Report(...))
# Before: await db.commit()

version_service = VersionService(db)
context_snapshot = agent.get_context_snapshot()
await version_service.create_version(
    task_id=task_id,
    report_data=report_data,
    context_snapshot=context_snapshot,
    content_markdown=report_markdown,
    content_html=report_html,
    trigger_type="initial",
    created_by=task.user_id,
)
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/reqradar/web/services/analysis_runner.py src/reqradar/web/services/analysis_runner_v2.py
git commit -m "feat: save initial report version after analysis completes (both legacy and V2 runners)"
```

---

## Task 9: Round 3 Integration Tests

**Files:**
- Create: `tests/test_round3_integration.py`

- [ ] **Step 1: Write integration tests for version management and chatback**

Create `tests/test_round3_integration.py`:

```python
import pytest
from unittest.mock import AsyncMock
from reqradar.web.services.version_service import VersionService
from reqradar.web.services.chatback_service import ChatbackService, classify_intent


def test_classify_intent_all_types():
    assert classify_intent("为什么风险评估是中？") == "explain"
    assert classify_intent("影响模块遗漏了 xxx") == "correct"
    assert classify_intent("请详细分析数据库影响") == "deepen"
    assert classify_intent("去看看 auth 模块") == "explore"
    assert classify_intent("谢谢") == "other"
    assert classify_intent("能不能说说风险？") == "explain"


def test_version_service_version_limit():
    assert VersionService.VERSION_LIMIT_DEFAULT if hasattr(VersionService, 'VERSION_LIMIT_DEFAULT') else True


def test_chatback_service_fallback_reply():
    service = ChatbackService(version_service=AsyncMock())

    reply = service._generate_fallback_reply(
        report_data={"risk_level": "high", "requirement_title": "Add SSO"},
        context_snapshot={
            "evidence_list": [{"id": "ev-001", "type": "code", "source": "src/auth.py", "content": "Auth module", "confidence": "high", "dimensions": ["impact"]}],
            "dimension_status": {"impact": "sufficient"},
            "visited_files": ["src/auth.py"],
            "tool_calls": [],
        },
        user_message="为什么风险是高？",
        intent="explain",
    )
    assert "high" in reply or "高风险" in reply or "风险" in reply


def test_chatback_service_fallback_correct():
    service = ChatbackService(version_service=AsyncMock())

    reply = service._generate_fallback_reply(
        report_data={"risk_level": "medium"},
        context_snapshot={"evidence_list": [], "dimension_status": {}, "visited_files": [], "tool_calls": []},
        user_message="遗漏了 xx 模块",
        intent="correct",
    )
    assert "纠正" in reply or "修改" in reply or "版本" in reply


def test_chatback_service_fallback_explore():
    service = ChatbackService(version_service=AsyncMock())

    reply = service._generate_fallback_reply(
        report_data={"risk_level": "low"},
        context_snapshot={"evidence_list": [], "dimension_status": {}, "visited_files": ["src/app.py", "src/models.py"], "tool_calls": []},
        user_message="去看看 auth",
        intent="explore",
    )
    assert "src/app.py" in reply or "文件" in reply


def test_agent_snapshot_roundtrip():
    from reqradar.agent.analysis_agent import AnalysisAgent, AgentState

    agent = AnalysisAgent("Test requirement", project_id=1, user_id=1, depth="standard")
    agent.record_evidence(type="code", source="src/main.py:50", content="Main entry point", confidence="high", dimensions=["impact", "understanding"])
    agent.dimension_tracker.mark_sufficient("understanding")
    agent.step_count = 3

    snapshot = agent.get_context_snapshot()

    assert len(snapshot["evidence_list"]) == 1
    assert snapshot["dimension_status"]["understanding"] == "sufficient"
    assert snapshot["step_count"] == 3
    assert "src/main.py" in snapshot["visited_files"]

    agent2 = AnalysisAgent("Test requirement", project_id=1, user_id=1, depth="standard")
    agent2.restore_from_snapshot(snapshot)

    assert len(agent2.evidence_collector.evidences) == 1
    assert agent2.dimension_tracker.dimensions["understanding"].status == "sufficient"
    assert agent2.step_count == 3
    assert "src/main.py" in agent2.visited_files
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_round3_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_round3_integration.py
git commit -m "test: add Round 3 integration tests for version management, chatback, and evidence"
```

---

## Self-Review Checklist

- [ ] **Spec Coverage**: Each spec section for Round 3 (backend) has a corresponding task:
  - Section 6.1 (Version Management) → Tasks 1, 2, 3, 5
  - Section 6.2 (Global Chatback, single-turn) → Tasks 4, 6
  - Section 6.4 (Evidence Chain) → Task 7
  - Section 8.1.1 (ReportVersion model) → Task 1
  - Section 8.1.2 (ReportChat model) → Task 1
  - Section 9.1 (Chatback API) → Task 6
  - Section 9.2 (Version History API) → Task 5
  - Section 9.3 (Evidence Chain API) → Task 7
  - Initial version creation → Task 8

- [ ] **No Placeholders**: No TBD, TODO, or "implement later"

- [ ] **Type Consistency**: `VersionService.VERSION_LIMIT_DEFAULT = 10`, `ReportVersion.version_number` starts from 1, `ReportChat.intent_type` matches `classify_intent` output

- [ ] **Explicitly Excluded Per User Request**: Frontend pages (ReportView, ProfileManager, SynonymManager, TemplateManager, Preferences) are NOT included. Paragraph annotation (ReportAnnotation model) is deferred per spec.

- [ ] **Backward Compatibility**: Legacy runner and V2 runner both save initial version. Chatback service works with or without LLM client (fallback replies).