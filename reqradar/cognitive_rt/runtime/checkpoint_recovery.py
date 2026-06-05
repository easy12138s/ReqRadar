"""Checkpoint 恢复逻辑 — 从快照恢复 Session 运行时状态。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RecoveryResult:
    """恢复结果。"""

    success: bool
    session_id: str
    version: int
    restored_state: dict = field(default_factory=dict)
    error_message: str = ""
    evidence_chain_valid: bool = True


class CheckpointRecovery:
    """Checkpoint 恢复器 — 从快照恢复 Session 状态。"""

    def __init__(self, storage: object, event_store: object | None = None) -> None:
        """初始化恢复器。

        Args:
            storage: Checkpoint 存储（实现 load_latest/load_version 方法）
            event_store: 事件存储（用于验证 Evidence 链）
        """
        self._storage = storage
        self._event_store = event_store

    def recover(
        self,
        session_id: str,
        version: int | None = None,
    ) -> RecoveryResult:
        """从 Checkpoint 恢复 Session 状态。

        Args:
            session_id: Session ID
            version: 指定版本（None 则取最新）

        Returns:
            恢复结果
        """
        try:
            if version is not None:
                state = self._storage.load_version(session_id, version)
            else:
                state = self._storage.load_latest(session_id)

            if state is None:
                return RecoveryResult(
                    success=False,
                    session_id=session_id,
                    version=version or 0,
                    error_message=f"未找到 Checkpoint: session={session_id}, version={version}",
                )

            restored_version = state.get("version", 0)

            # 验证 Evidence 链完整性
            evidence_valid = self._verify_evidence_chain(session_id, restored_version)

            if not evidence_valid:
                logger.warning(
                    "Evidence 链校验失败: session=%s, version=%s",
                    session_id,
                    restored_version,
                )
                # 尝试恢复到上一个版本
                if restored_version > 1:
                    prev_state = self._storage.load_version(session_id, restored_version - 1)
                    if prev_state:
                        return RecoveryResult(
                            success=True,
                            session_id=session_id,
                            version=restored_version - 1,
                            restored_state=prev_state,
                            evidence_chain_valid=False,
                            error_message="Evidence 链校验失败，回退到上一版本",
                        )

                return RecoveryResult(
                    success=False,
                    session_id=session_id,
                    version=restored_version,
                    error_message="Evidence 链校验失败，无可用版本",
                    evidence_chain_valid=False,
                )

            logger.info("Checkpoint 恢复成功: session=%s, version=%s", session_id, restored_version)
            return RecoveryResult(
                success=True,
                session_id=session_id,
                version=restored_version,
                restored_state=state,
            )

        except Exception as e:
            logger.error("Checkpoint 恢复异常: %s", e)
            return RecoveryResult(
                success=False,
                session_id=session_id,
                version=version or 0,
                error_message=f"恢复异常: {e}",
            )

    def _verify_evidence_chain(self, session_id: str, version: int) -> bool:
        """验证 Evidence 链完整性。

        Args:
            session_id: Session ID
            version: Checkpoint 版本

        Returns:
            是否完整
        """
        if self._event_store is None:
            return True  # 无事件存储时跳过验证

        try:
            events = self._event_store.get_events(session_id)
            if not events:
                return True  # 无事件时视为完整

            # 检查事件序列是否连续
            sequences = sorted(e.sequence for e in events)
            for i in range(1, len(sequences)):
                if sequences[i] != sequences[i - 1] + 1:
                    # 允许小的间隙（可能是并行事件）
                    if sequences[i] - sequences[i - 1] > 10:
                        return False

            return True
        except Exception:
            return False
