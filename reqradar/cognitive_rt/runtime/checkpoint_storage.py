"""Checkpoint 存储分区 — 热/冷/可重建三区策略。"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class HotStateStorage:
    """热状态存储 — PG JSONB 模拟（内存字典）。"""
    
    def __init__(self, max_hot: int = 3) -> None:
        """初始化热状态存储。
        
        Args:
            max_hot: 每个 Session 保留的热状态数量
        """
        self._max_hot = max_hot
        self._hot_states: dict[str, list[dict]] = {}  # session_id -> list of states
    
    def save(self, checkpoint_record: object) -> None:
        """保存热状态。"""
        session_id = getattr(checkpoint_record, "session_id", "")
        state = {
            "checkpoint_id": getattr(checkpoint_record, "checkpoint_id", ""),
            "version": getattr(checkpoint_record, "version", 0),
            "state_summary": _serialize(getattr(checkpoint_record, "state_summary", {})),
            "hot_state": getattr(checkpoint_record, "hot_state", {}),
            "created_at": str(getattr(checkpoint_record, "created_at", "")),
        }
        
        if session_id not in self._hot_states:
            self._hot_states[session_id] = []
        self._hot_states[session_id].append(state)
        
        # 保留最近 N 个
        if len(self._hot_states[session_id]) > self._max_hot:
            self._hot_states[session_id] = self._hot_states[session_id][-self._max_hot:]
    
    def load(self, session_id: str, version: int | None = None) -> dict | None:
        """加载热状态。"""
        states = self._hot_states.get(session_id, [])
        if not states:
            return None
        if version is not None:
            for s in states:
                if s["version"] == version:
                    return s
            return None
        return states[-1]
    
    def get_all(self, session_id: str) -> list[dict]:
        """获取所有热状态。"""
        return list(self._hot_states.get(session_id, []))


class ColdStateStorage:
    """冷状态存储 — MinIO 模拟（本地文件系统）。"""
    
    def __init__(self, base_path: str | Path | None = None) -> None:
        """初始化冷状态存储。
        
        Args:
            base_path: 冷状态存储根目录
        """
        self._base_path = Path(base_path) if base_path else None
        self._cold_states: dict[str, dict] = {}  # checkpoint_id -> state
    
    def save(self, checkpoint_record: object) -> str | None:
        """保存冷状态，返回 URI。"""
        checkpoint_id = getattr(checkpoint_record, "checkpoint_id", "")
        session_id = getattr(checkpoint_record, "session_id", "")
        state = {
            "checkpoint_id": checkpoint_id,
            "session_id": session_id,
            "version": getattr(checkpoint_record, "version", 0),
            "full_state": _serialize(checkpoint_record),
            "created_at": str(getattr(checkpoint_record, "created_at", "")),
        }
        
        self._cold_states[checkpoint_id] = state
        
        # 写入本地文件
        if self._base_path:
            session_dir = self._base_path / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            file_path = session_dir / f"{checkpoint_id}.json"
            file_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(file_path)
        
        return f"memory://{checkpoint_id}"
    
    def load(self, uri: str) -> dict | None:
        """从 URI 加载冷状态。"""
        if uri.startswith("memory://"):
            cp_id = uri.replace("memory://", "")
            return self._cold_states.get(cp_id)
        
        path = Path(uri)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None


class CheckpointStorage:
    """Checkpoint 存储管理器 — 三区策略协调。"""
    
    def __init__(
        self,
        hot_storage: HotStateStorage | None = None,
        cold_storage: ColdStateStorage | None = None,
        archive_days: int = 30,
        delete_days: int = 90,
    ) -> None:
        """初始化存储管理器。
        
        Args:
            hot_storage: 热状态存储
            cold_storage: 冷状态存储
            archive_days: 归档天数
            delete_days: 删除天数
        """
        self.hot = hot_storage or HotStateStorage()
        self.cold = cold_storage or ColdStateStorage()
        self._archive_days = archive_days
        self._delete_days = delete_days
    
    def save(self, checkpoint_record: object) -> None:
        """保存 Checkpoint 到热区和冷区。"""
        self.hot.save(checkpoint_record)
        uri = self.cold.save(checkpoint_record)
        logger.debug(f"Checkpoint 存储: hot + cold (uri={uri})")
    
    def load_latest(self, session_id: str) -> dict | None:
        """加载最新的热状态。"""
        return self.hot.load(session_id)
    
    def load_version(self, session_id: str, version: int) -> dict | None:
        """加载指定版本的热状态，不存在则从冷区加载。"""
        hot = self.hot.load(session_id, version)
        if hot:
            return hot
        
        # 从冷区加载
        for state in self.hot.get_all(session_id):
            if state.get("version") == version:
                return state
        
        return None


def _serialize(obj: object) -> dict | str:
    """序列化对象为字典。"""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)
