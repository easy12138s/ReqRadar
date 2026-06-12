"""Checkpoint 创建逻辑 — Session 状态快照管理。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from reqradar.kernel.enums import CheckpointType

logger = logging.getLogger(__name__)


@dataclass
class StateSummary:
    """状态摘要 — 热状态数据。"""

    current_step: int = 0
    total_steps: int = 0
    evidence_count: int = 0
    dimension_status: dict = field(default_factory=dict)
    context_usage: int = 0
    context_budget: int = 0


@dataclass
class CheckpointRecord:
    """Checkpoint 记录。"""

    checkpoint_id: str
    session_id: str
    version: int
    previous_version: int | None
    created_at: datetime
    created_by: str
    type: CheckpointType
    state_summary: StateSummary
    diff: dict = field(default_factory=lambda: {"added": [], "removed": [], "modified": []})
    hot_state: dict = field(default_factory=dict)
    full_state_uri: str | None = None
    metadata: dict = field(default_factory=dict)


class CheckpointManager:
    """Checkpoint 管理器 — 创建和管理 Session 快照。"""

    def __init__(self, storage: object | None = None) -> None:
        """初始化 Checkpoint 管理器。

        Args:
            storage: 可选的存储后端（实现 save/load 方法）
        """
        self._storage = storage
        self._checkpoints: dict[str, list[CheckpointRecord]] = {}  # session_id -> checkpoints
        self._versions: dict[str, int] = {}  # session_id -> next version

    def create_checkpoint(
        self,
        session_id: str,
        checkpoint_type: CheckpointType,
        state_summary: StateSummary,
        hot_state: dict | None = None,
        created_by: str = "cognitive-rt",
        metadata: dict | None = None,
    ) -> CheckpointRecord:
        """创建 Checkpoint。

        Args:
            session_id: Session ID
            checkpoint_type: Checkpoint 类型
            state_summary: 状态摘要
            hot_state: 热状态数据
            created_by: 创建者
            metadata: 元数据

        Returns:
            创建的 Checkpoint 记录
        """
        version = self._versions.get(session_id, 0) + 1
        self._versions[session_id] = version

        checkpoints = self._checkpoints.get(session_id, [])
        previous_version = checkpoints[-1].version if checkpoints else None

        record = CheckpointRecord(
            checkpoint_id=str(uuid4()),
            session_id=session_id,
            version=version,
            previous_version=previous_version,
            created_at=datetime.now(UTC),
            created_by=created_by,
            type=checkpoint_type,
            state_summary=state_summary,
            hot_state=hot_state or {},
            metadata=metadata or {},
        )

        # 计算 diff
        if checkpoints:
            record.diff = self._compute_diff(checkpoints[-1], record)

        if session_id not in self._checkpoints:
            self._checkpoints[session_id] = []
        self._checkpoints[session_id].append(record)

        # 持久化到存储后端
        if self._storage is not None:
            try:
                self._storage.save(record)
            except Exception as e:
                logger.warning("Checkpoint 持久化失败: %s", e)

        logger.info(
            "Checkpoint 创建: session=%s, version=%s, type=%s",
            session_id,
            version,
            checkpoint_type.value,
        )
        return record

    def get_latest(self, session_id: str) -> CheckpointRecord | None:
        """获取最新的 Checkpoint。"""
        checkpoints = self._checkpoints.get(session_id, [])
        return checkpoints[-1] if checkpoints else None

    def get_version(self, session_id: str, version: int) -> CheckpointRecord | None:
        """获取指定版本的 Checkpoint。"""
        for cp in self._checkpoints.get(session_id, []):
            if cp.version == version:
                return cp
        return None

    def get_all(self, session_id: str) -> list[CheckpointRecord]:
        """获取所有 Checkpoint。"""
        return list(self._checkpoints.get(session_id, []))

    def get_version_count(self, session_id: str) -> int:
        """获取版本数量。"""
        return len(self._checkpoints.get(session_id, []))

    def sync_version(self, session_id: str, version: int) -> None:
        """同步版本计数器（服务重启恢复时使用）。

        将内存中的版本计数器设置为不低于给定 version 的值，
        避免重启后从 1 开始计数与 PG 已有记录冲突。
        """
        current = self._versions.get(session_id, 0)
        if version > current:
            self._versions[session_id] = version
            logger.debug(
                "Checkpoint 版本计数器同步: session=%s, version=%s",
                session_id,
                version,
            )

    def _compute_diff(self, old: CheckpointRecord, new: CheckpointRecord) -> dict:
        """计算两个 Checkpoint 之间的差异。"""
        old_dims = set(old.state_summary.dimension_status.keys())
        new_dims = set(new.state_summary.dimension_status.keys())

        return {
            "added": list(new_dims - old_dims),
            "removed": list(old_dims - new_dims),
            "modified": [
                d
                for d in old_dims & new_dims
                if old.state_summary.dimension_status[d] != new.state_summary.dimension_status[d]
            ],
        }
