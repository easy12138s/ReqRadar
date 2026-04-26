"""ConfigManager 单元测试"""

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import Config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.models import Project, ProjectConfig, SystemConfig, User, UserConfig

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_config_manager.db"


@pytest_asyncio.fixture
async def db_session():
    """创建测试数据库会话，并预置测试用户和项目"""
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # 预置测试用户
        user = User(email="test@example.com", password_hash="hash", display_name="Test", role="user")
        session.add(user)
        await session.flush()

        # 预置测试项目
        project = Project(name="Test-Project", description="", source_type="local", source_url="/tmp", owner_id=user.id)
        session.add(project)
        await session.commit()

        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    db_path = "./test_config_manager.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def file_config():
    """创建一个测试用的文件配置"""
    return Config()


@pytest_asyncio.fixture
async def config_manager(db_session: AsyncSession, file_config):
    """创建 ConfigManager 实例"""
    return ConfigManager(db_session, file_config)


class TestConfigManagerGet:
    """测试配置读取与优先级解析"""

    async def test_get_from_file_config(self, config_manager):
        """测试从文件配置读取默认值"""
        result = await config_manager.get("llm.model")
        assert result == "gpt-4o-mini"  # Config 默认值

    async def test_get_system_override_file(self, config_manager, db_session):
        """测试系统级配置覆盖文件配置"""
        await config_manager.set_system("llm.model", "gpt-4o")
        result = await config_manager.get("llm.model")
        assert result == "gpt-4o"

    async def test_get_project_override_system(self, config_manager, db_session):
        """测试项目级配置覆盖系统级"""
        await config_manager.set_system("llm.model", "gpt-4o")
        await config_manager.set_project(1, "llm.model", "qwen2.5")
        result = await config_manager.get("llm.model", project_id=1)
        assert result == "qwen2.5"

    async def test_get_user_override_project(self, config_manager, db_session):
        """测试用户级配置覆盖项目级"""
        await config_manager.set_project(1, "llm.model", "qwen2.5")
        await config_manager.set_user(1, "llm.model", "deepseek-chat")
        result = await config_manager.get("llm.model", user_id=1, project_id=1)
        assert result == "deepseek-chat"

    async def test_get_priority_chain(self, config_manager, db_session):
        """测试完整优先级链：用户 > 项目 > 系统 > 文件 > 默认"""
        # 只有文件默认值
        result = await config_manager.get("analysis.max_similar_reqs")
        assert result == 5  # Config 默认值

        # 系统级覆盖
        await config_manager.set_system("analysis.max_similar_reqs", 10)
        result = await config_manager.get("analysis.max_similar_reqs")
        assert result == 10

        # 项目级覆盖
        await config_manager.set_project(1, "analysis.max_similar_reqs", 15)
        result = await config_manager.get("analysis.max_similar_reqs", project_id=1)
        assert result == 15

        # 用户级覆盖
        await config_manager.set_user(1, "analysis.max_similar_reqs", 20)
        result = await config_manager.get("analysis.max_similar_reqs", user_id=1, project_id=1)
        assert result == 20

    async def test_get_with_default(self, config_manager):
        """测试自定义默认值"""
        result = await config_manager.get("nonexistent.key", default="fallback")
        assert result == "fallback"

    async def test_get_returns_none_when_not_found(self, config_manager):
        """测试找不到配置时返回 None"""
        result = await config_manager.get("nonexistent.key")
        assert result is None


class TestConfigManagerTypeConversion:
    """测试类型转换"""

    async def test_get_str(self, config_manager):
        await config_manager.set_system("test.string", "hello")
        result = await config_manager.get_str("test.string")
        assert result == "hello"

    async def test_get_int(self, config_manager):
        await config_manager.set_system("test.int", 42)
        result = await config_manager.get_int("test.int")
        assert result == 42
        assert isinstance(result, int)

    async def test_get_int_from_string(self, config_manager):
        await config_manager.set_system("test.int_str", "42", value_type="integer")
        result = await config_manager.get_int("test.int_str")
        assert result == 42

    async def test_get_float(self, config_manager):
        await config_manager.set_system("test.float", 3.14)
        result = await config_manager.get_float("test.float")
        assert result == 3.14
        assert isinstance(result, float)

    async def test_get_bool_true(self, config_manager):
        await config_manager.set_system("test.bool", True)
        result = await config_manager.get_bool("test.bool")
        assert result is True

    async def test_get_bool_false(self, config_manager):
        await config_manager.set_system("test.bool", False)
        result = await config_manager.get_bool("test.bool")
        assert result is False

    async def test_get_bool_from_string(self, config_manager):
        await config_manager.set_system("test.bool_str", "true", value_type="boolean")
        result = await config_manager.get_bool("test.bool_str")
        assert result is True

    async def test_get_json(self, config_manager):
        await config_manager.set_system("test.json", ["a", "b", "c"], value_type="json")
        result = await config_manager.get_json("test.json")
        assert result == ["a", "b", "c"]

    async def test_get_with_explicit_type(self, config_manager):
        await config_manager.set_system("test.type", "123", value_type="string")
        result = await config_manager.get("test.type", as_type="integer")
        assert result == 123
        assert isinstance(result, int)


class TestConfigManagerMasking:
    """测试敏感值掩码"""

    async def test_mask_short_value(self, config_manager):
        result = ConfigManager._mask_sensitive("abc")
        assert result == "***"

    async def test_mask_long_value(self, config_manager):
        result = ConfigManager._mask_sensitive("sk-abc123def456")
        assert result == "sk-***456"

    async def test_get_masked(self, config_manager):
        await config_manager.set_system("llm.api_key", "sk-secret-key", is_sensitive=True)
        result = await config_manager.get_masked("llm.api_key")
        assert result == "sk-***key"


class TestConfigManagerWrite:
    """测试配置写入"""

    async def test_set_system_create(self, config_manager, db_session):
        config = await config_manager.set_system("test.key", "value")
        assert config.config_key == "test.key"
        assert config.config_value == "value"
        assert config.value_type == "string"

    async def test_set_system_update(self, config_manager, db_session):
        await config_manager.set_system("test.key", "old")
        config = await config_manager.set_system("test.key", "new")
        assert config.config_value == "new"

    async def test_delete_system(self, config_manager, db_session):
        await config_manager.set_system("test.key", "value")
        deleted = await config_manager.delete_system("test.key")
        assert deleted is True
        result = await config_manager.get("test.key")
        assert result is None

    async def test_delete_system_not_found(self, config_manager):
        deleted = await config_manager.delete_system("nonexistent")
        assert deleted is False

    async def test_set_project(self, config_manager, db_session):
        config = await config_manager.set_project(1, "test.key", "value")
        assert config.project_id == 1
        assert config.config_key == "test.key"

    async def test_set_user(self, config_manager, db_session):
        config = await config_manager.set_user(1, "test.key", "value")
        assert config.user_id == 1
        assert config.config_key == "test.key"

    async def test_set_with_value_type(self, config_manager):
        config = await config_manager.set_system("test.key", "42", value_type="integer")
        assert config.value_type == "integer"

    async def test_set_sensitive(self, config_manager):
        config = await config_manager.set_system("test.key", "secret", is_sensitive=True)
        assert config.is_sensitive is True


class TestConfigManagerIsSet:
    """测试显式配置检查"""

    async def test_is_set_true(self, config_manager):
        await config_manager.set_system("test.key", "value")
        assert await config_manager.is_set("test.key") is True

    async def test_is_set_false(self, config_manager):
        assert await config_manager.is_set("nonexistent") is False

    async def test_is_set_user_level(self, config_manager):
        await config_manager.set_user(1, "test.key", "value")
        assert await config_manager.is_set("test.key", user_id=1) is True
        assert await config_manager.is_set("test.key", user_id=2) is False


class TestConfigManagerFileConfigFallback:
    """测试文件配置兜底"""

    async def test_file_config_bool(self, config_manager):
        """文件配置中的布尔值"""
        result = await config_manager.get("memory.enabled")
        assert result is True  # Config 默认值

    async def test_file_config_nested(self, config_manager):
        """文件配置中的嵌套属性"""
        result = await config_manager.get("analysis.max_similar_reqs")
        assert result == 5

    async def test_file_config_not_found(self, config_manager):
        """文件配置中不存在的键"""
        result = await config_manager.get("nonexistent.nested.key")
        assert result is None


class TestConfigManagerSerialization:
    """测试序列化逻辑"""

    def test_serialize_bool(self):
        assert ConfigManager._serialize_value(True) == "true"
        assert ConfigManager._serialize_value(False) == "false"

    def test_serialize_list(self):
        assert ConfigManager._serialize_value(["a", "b"]) == '["a", "b"]'

    def test_serialize_dict(self):
        assert ConfigManager._serialize_value({"k": "v"}) == '{"k": "v"}'

    def test_serialize_int(self):
        assert ConfigManager._serialize_value(42) == "42"


class TestConfigManagerInferType:
    """测试类型推断"""

    def test_infer_bool(self):
        assert ConfigManager._infer_type(True) == "boolean"

    def test_infer_int(self):
        assert ConfigManager._infer_type(42) == "integer"

    def test_infer_float(self):
        assert ConfigManager._infer_type(3.14) == "float"

    def test_infer_list(self):
        assert ConfigManager._infer_type([1, 2]) == "json"

    def test_infer_dict(self):
        assert ConfigManager._infer_type({"a": 1}) == "json"

    def test_infer_string(self):
        assert ConfigManager._infer_type("hello") == "string"
