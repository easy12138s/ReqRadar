"""OutputTaskStore — Output Service 的 PG 持久化任务存储。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from reqradar.kernel.enums import TaskStatus

logger = logging.getLogger(__name__)


class OutputTaskStore:
    """Output Service 的任务存储 — 支持 PG 持久化。

    当 db_session_factory 为 None 时降级为内存模式。
    """

    def __init__(self, db_session_factory: object | None = None) -> None:
        """初始化任务存储。

        Args:
            db_session_factory: 可选的数据库会话工厂（PG 持久化）
        """
        self._db_session_factory = db_session_factory
        # 内存模式降级
        self._tasks: dict[str, dict] = {}
        self._session_tasks: dict[str, list[str]] = {}

    async def create(
        self,
        session_id: str,
        output_format: str = "markdown",
        template_id: str | None = None,
    ) -> dict:
        """创建报告生成任务。

        Args:
            session_id: Session ID
            output_format: 输出格式
            template_id: 模板 ID

        Returns:
            任务信息字典
        """
        task_id = str(uuid4())
        task_data = {
            "task_id": task_id,
            "session_id": session_id,
            "status": TaskStatus.PENDING.value,
            "output_format": output_format,
            "template_id": template_id,
            "output_uri": None,
            "content": "",
            "size_bytes": 0,
            "created_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "error": "",
        }

        # PG 持久化
        if self._db_session_factory:
            try:
                from reqradar.kernel.models import OutputTask

                async with self._db_session_factory() as db_session:
                    db_session.add(
                        OutputTask(
                            task_id=task_id,
                            session_id=session_id,
                            status=TaskStatus.PENDING.value,
                            output_format=output_format,
                            template_id=template_id,
                        )
                    )
                    await db_session.commit()
            except Exception as e:
                logger.warning("OutputTask PG 持久化失败: %s", e, exc_info=True)

        # 内存缓存
        self._tasks[task_id] = task_data
        if session_id not in self._session_tasks:
            self._session_tasks[session_id] = []
        self._session_tasks[session_id].append(task_id)

        return task_data

    async def get(self, task_id: str) -> dict | None:
        """获取任务信息。

        Args:
            task_id: 任务 ID

        Returns:
            任务信息字典，不存在返回 None
        """
        # 先查内存缓存
        if task_id in self._tasks:
            return self._tasks[task_id]

        # 从 PG 加载
        if self._db_session_factory:
            try:
                from sqlalchemy import select

                from reqradar.kernel.models import OutputTask

                async with self._db_session_factory() as db_session:
                    result = await db_session.execute(
                        select(OutputTask).where(OutputTask.task_id == task_id)
                    )
                    row = result.scalar_one_or_none()
                    if row:
                        task_data = {
                            "task_id": row.task_id,
                            "session_id": row.session_id,
                            "status": row.status,
                            "output_format": row.output_format,
                            "template_id": row.template_id,
                            "output_uri": row.output_uri,
                            "content": row.content or "",
                            "size_bytes": row.size_bytes or 0,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                            "error": row.error or "",
                        }
                        # 写入内存缓存
                        self._tasks[task_id] = task_data
                        return task_data
            except Exception as e:
                logger.warning("OutputTask PG 查询失败: %s", e, exc_info=True)

        return None

    async def update(
        self,
        task_id: str,
        status: str | None = None,
        output_uri: str | None = None,
        content: str | None = None,
        size_bytes: int | None = None,
        error: str | None = None,
    ) -> bool:
        """更新任务信息。

        Args:
            task_id: 任务 ID
            status: 新状态
            output_uri: 输出 URI
            content: 报告内容
            size_bytes: 报告大小
            error: 错误信息

        Returns:
            是否更新成功
        """
        # 更新内存缓存
        if task_id in self._tasks:
            task = self._tasks[task_id]
            if status is not None:
                task["status"] = status
            if output_uri is not None:
                task["output_uri"] = output_uri
            if content is not None:
                task["content"] = content
            if size_bytes is not None:
                task["size_bytes"] = size_bytes
            if error is not None:
                task["error"] = error
            if status == TaskStatus.COMPLETED.value:
                task["completed_at"] = datetime.now(UTC).isoformat()

        # PG 持久化
        if self._db_session_factory:
            try:
                from sqlalchemy import update

                from reqradar.kernel.models import OutputTask

                update_data = {}
                if status is not None:
                    update_data["status"] = status
                if output_uri is not None:
                    update_data["output_uri"] = output_uri
                if content is not None:
                    update_data["content"] = content
                if size_bytes is not None:
                    update_data["size_bytes"] = size_bytes
                if error is not None:
                    update_data["error"] = error
                if status == TaskStatus.COMPLETED.value:
                    update_data["completed_at"] = datetime.now(UTC)

                if update_data:
                    async with self._db_session_factory() as db_session:
                        await db_session.execute(
                            update(OutputTask)
                            .where(OutputTask.task_id == task_id)
                            .values(**update_data)
                        )
                        await db_session.commit()
            except Exception as e:
                logger.warning("OutputTask PG 更新失败: %s", e, exc_info=True)

        return True

    async def get_latest_for_session(self, session_id: str) -> dict | None:
        """获取指定 Session 的最新已完成任务。

        Args:
            session_id: Session ID

        Returns:
            任务信息字典，不存在返回 None
        """
        # 内存缓存查找
        task_ids = self._session_tasks.get(session_id, [])
        for tid in reversed(task_ids):
            task = self._tasks.get(tid)
            if task and task["status"] == TaskStatus.COMPLETED.value:
                return task

        # PG 查找
        if self._db_session_factory:
            try:
                from sqlalchemy import desc, select

                from reqradar.kernel.models import OutputTask

                async with self._db_session_factory() as db_session:
                    result = await db_session.execute(
                        select(OutputTask)
                        .where(
                            OutputTask.session_id == session_id,
                            OutputTask.status == TaskStatus.COMPLETED.value,
                        )
                        .order_by(desc(OutputTask.created_at))
                        .limit(1)
                    )
                    row = result.scalar_one_or_none()
                    if row:
                        return {
                            "task_id": row.task_id,
                            "session_id": row.session_id,
                            "status": row.status,
                            "output_format": row.output_format,
                            "template_id": row.template_id,
                            "output_uri": row.output_uri,
                            "content": row.content or "",
                            "size_bytes": row.size_bytes or 0,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                            "error": row.error or "",
                        }
            except Exception as e:
                logger.warning("OutputTask PG 查询失败: %s", e, exc_info=True)

        return None

    def clear(self) -> None:
        """清空内存缓存。"""
        self._tasks.clear()
        self._session_tasks.clear()
