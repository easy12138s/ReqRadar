"""配置管理器 - 支持三层配置优先级解析与热加载"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import Config
from reqradar.web.models import ProjectConfig, SystemConfig, UserConfig

logger = logging.getLogger("reqradar.config_manager")


class ConfigManager:
    """配置管理器：支持三层配置优先级解析

    解析优先级（从高到低）：
    1. 用户级配置 (user_configs)
    2. 项目级配置 (project_configs)
    3. 系统级配置 (system_configs)
    4. .reqradar.yaml 文件
    5. Pydantic 代码默认值
    """

    def __init__(self, db_session: AsyncSession, file_config: Config):
        self._db = db_session
        self._file_config = file_config

    # ------------------------------------------------------------------
    # 读取接口
    # ------------------------------------------------------------------

    async def get(
        self,
        key: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
        default: Any = None,
        as_type: str | None = None,
    ) -> Any:
        """按优先级解析配置值。

        Args:
            key: 配置键（点分式，如 "llm.model"）
            user_id: 当前用户 ID（查询用户级配置）
            project_id: 当前项目 ID（查询项目级配置）
            default: 所有层级都找不到时的默认值
            as_type: 强制类型转换（"string", "integer", "float", "boolean", "json"）

        Returns:
            解析后的配置值（已做类型转换）
        """
        raw_value = None
        value_type = as_type or "string"

        # 1. 用户级
        if user_id is not None:
            raw_value, value_type = await self._get_from_db(UserConfig, key, user_id=user_id)

        # 2. 项目级
        if raw_value is None and project_id is not None:
            raw_value, value_type = await self._get_from_db(
                ProjectConfig, key, project_id=project_id
            )

        # 3. 系统级
        if raw_value is None:
            raw_value, value_type = await self._get_from_db(SystemConfig, key)

        # 4. 文件配置（YAML）
        if raw_value is None:
            raw_value = self._get_from_file(key)
            if raw_value is not None:
                # 文件配置没有显式 value_type，根据值推断
                value_type = self._infer_type(raw_value)

        # 5. 代码默认值
        if raw_value is None and default is not None:
            raw_value = default
            value_type = self._infer_type(default)

        if raw_value is None:
            return None

        return self._convert_type(raw_value, as_type or value_type)

    async def get_str(
        self,
        key: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
        default: str = "",
    ) -> str:
        result = await self.get(
            key, user_id=user_id, project_id=project_id, default=default, as_type="string"
        )
        return str(result) if result is not None else default

    async def get_int(
        self,
        key: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
        default: int = 0,
    ) -> int:
        result = await self.get(
            key, user_id=user_id, project_id=project_id, default=default, as_type="integer"
        )
        return result if result is not None else default

    async def get_float(
        self,
        key: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
        default: float = 0.0,
    ) -> float:
        result = await self.get(
            key, user_id=user_id, project_id=project_id, default=default, as_type="float"
        )
        return result if result is not None else default

    async def get_bool(
        self,
        key: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
        default: bool = False,
    ) -> bool:
        result = await self.get(
            key, user_id=user_id, project_id=project_id, default=default, as_type="boolean"
        )
        return result if result is not None else default

    async def get_json(
        self,
        key: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
        default: Any = None,
    ) -> Any:
        return await self.get(
            key, user_id=user_id, project_id=project_id, default=default, as_type="json"
        )

    async def get_masked(
        self,
        key: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
        default: str = "",
    ) -> str:
        """获取掩码后的值（用于 API 返回）"""
        value = await self.get_str(key, user_id=user_id, project_id=project_id, default=default)
        return self._mask_sensitive(value)

    async def is_set(
        self, key: str, *, user_id: int | None = None, project_id: int | None = None
    ) -> bool:
        """检查某层级是否有显式配置（非继承）"""
        if user_id is not None:
            row = await self._db.execute(
                select(UserConfig).where(
                    UserConfig.user_id == user_id, UserConfig.config_key == key
                )
            )
            if row.scalar_one_or_none():
                return True

        if project_id is not None:
            row = await self._db.execute(
                select(ProjectConfig).where(
                    ProjectConfig.project_id == project_id, ProjectConfig.config_key == key
                )
            )
            if row.scalar_one_or_none():
                return True

        row = await self._db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        if row.scalar_one_or_none():
            return True

        return self._get_from_file(key) is not None

    # ------------------------------------------------------------------
    # 写入接口（系统级）
    # ------------------------------------------------------------------

    async def set_system(
        self,
        key: str,
        value: Any,
        value_type: str | None = None,
        description: str = "",
        is_sensitive: bool = False,
    ) -> SystemConfig:
        """创建或更新系统级配置"""
        str_value = self._serialize_value(value)
        inferred_type = value_type or self._infer_type(value)

        result = await self._db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        existing = result.scalar_one_or_none()

        if existing:
            existing.config_value = str_value
            existing.value_type = inferred_type
            existing.description = description
            existing.is_sensitive = is_sensitive
            await self._db.commit()
            await self._db.refresh(existing)
            logger.info("Updated system config: %s", key)
            return existing
        else:
            config = SystemConfig(
                config_key=key,
                config_value=str_value,
                value_type=inferred_type,
                description=description,
                is_sensitive=is_sensitive,
            )
            self._db.add(config)
            await self._db.commit()
            await self._db.refresh(config)
            logger.info("Created system config: %s", key)
            return config

    async def delete_system(self, key: str) -> bool:
        """删除系统级配置"""
        result = await self._db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        existing = result.scalar_one_or_none()
        if existing:
            await self._db.delete(existing)
            await self._db.commit()
            logger.info("Deleted system config: %s", key)
            return True
        return False

    # ------------------------------------------------------------------
    # 写入接口（项目级）
    # ------------------------------------------------------------------

    async def set_project(
        self,
        project_id: int,
        key: str,
        value: Any,
        value_type: str | None = None,
        is_sensitive: bool = False,
    ) -> ProjectConfig:
        """创建或更新项目级配置"""
        str_value = self._serialize_value(value)
        inferred_type = value_type or self._infer_type(value)

        result = await self._db.execute(
            select(ProjectConfig).where(
                ProjectConfig.project_id == project_id, ProjectConfig.config_key == key
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.config_value = str_value
            existing.value_type = inferred_type
            existing.is_sensitive = is_sensitive
            await self._db.commit()
            await self._db.refresh(existing)
            logger.info("Updated project config: %s (project=%d)", key, project_id)
            return existing
        else:
            config = ProjectConfig(
                project_id=project_id,
                config_key=key,
                config_value=str_value,
                value_type=inferred_type,
                is_sensitive=is_sensitive,
            )
            self._db.add(config)
            await self._db.commit()
            await self._db.refresh(config)
            logger.info("Created project config: %s (project=%d)", key, project_id)
            return config

    async def delete_project(self, project_id: int, key: str) -> bool:
        """删除项目级配置"""
        result = await self._db.execute(
            select(ProjectConfig).where(
                ProjectConfig.project_id == project_id, ProjectConfig.config_key == key
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await self._db.delete(existing)
            await self._db.commit()
            logger.info("Deleted project config: %s (project=%d)", key, project_id)
            return True
        return False

    # ------------------------------------------------------------------
    # 写入接口（用户级）
    # ------------------------------------------------------------------

    async def set_user(
        self,
        user_id: int,
        key: str,
        value: Any,
        value_type: str | None = None,
        is_sensitive: bool = False,
    ) -> UserConfig:
        """创建或更新用户级配置"""
        str_value = self._serialize_value(value)
        inferred_type = value_type or self._infer_type(value)

        result = await self._db.execute(
            select(UserConfig).where(UserConfig.user_id == user_id, UserConfig.config_key == key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.config_value = str_value
            existing.value_type = inferred_type
            existing.is_sensitive = is_sensitive
            await self._db.commit()
            await self._db.refresh(existing)
            logger.info("Updated user config: %s (user=%d)", key, user_id)
            return existing
        else:
            config = UserConfig(
                user_id=user_id,
                config_key=key,
                config_value=str_value,
                value_type=inferred_type,
                is_sensitive=is_sensitive,
            )
            self._db.add(config)
            await self._db.commit()
            await self._db.refresh(config)
            logger.info("Created user config: %s (user=%d)", key, user_id)
            return config

    async def delete_user(self, user_id: int, key: str) -> bool:
        """删除用户级配置"""
        result = await self._db.execute(
            select(UserConfig).where(UserConfig.user_id == user_id, UserConfig.config_key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            await self._db.delete(existing)
            await self._db.commit()
            logger.info("Deleted user config: %s (user=%d)", key, user_id)
            return True
        return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _get_from_db(
        self, model_class: type, key: str, user_id: int | None = None, project_id: int | None = None
    ) -> tuple[str | None, str]:
        """从数据库读取配置值和类型"""
        query = select(model_class).where(model_class.config_key == key)
        if user_id is not None and hasattr(model_class, "user_id"):
            query = query.where(model_class.user_id == user_id)
        if project_id is not None and hasattr(model_class, "project_id"):
            query = query.where(model_class.project_id == project_id)

        result = await self._db.execute(query)
        row = result.scalar_one_or_none()
        if row:
            return row.config_value, row.value_type
        return None, "string"

    def _get_from_file(self, key: str) -> Any:
        """从 .reqradar.yaml 文件配置读取"""
        parts = key.split(".")
        current: Any = self._file_config

        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

        return current

    @staticmethod
    def _serialize_value(value: Any) -> str:
        """将任意值序列化为字符串存储"""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _infer_type(value: Any) -> str:
        """推断值类型"""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "float"
        if isinstance(value, (list, dict)):
            return "json"
        return "string"

    @staticmethod
    def _convert_type(value: Any, target_type: str) -> Any:
        """将字符串值转换为目标类型"""
        if value is None:
            return None

        str_value = str(value)

        if target_type in ("bool", "boolean"):
            return str_value.lower() in ("true", "1", "yes", "on")
        if target_type in ("int", "integer"):
            try:
                return int(str_value)
            except ValueError:
                return None
        if target_type in ("float", "number"):
            try:
                return float(str_value)
            except ValueError:
                return None
        if target_type == "json":
            try:
                return json.loads(str_value)
            except json.JSONDecodeError:
                return None
        return str_value

    @staticmethod
    def _mask_sensitive(value: str) -> str:
        """敏感值掩码：长度>8保留前3后3，其余***"""
        if not value:
            return value
        if len(value) <= 8:
            return "***"
        return value[:3] + "***" + value[-3:]
