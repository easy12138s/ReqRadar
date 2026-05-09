"""测试基础设施层"""


def test_config_default():
    from reqradar.infrastructure.config import Config

    config = Config()
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-4o-mini"


def test_config_env_var_resolution():
    import os

    from reqradar.infrastructure.config import Config

    os.environ["TEST_API_KEY"] = "test-key-123"

    config_dict = {"llm": {"api_key": "${TEST_API_KEY}"}}
    resolved = Config(**config_dict)

    assert resolved.llm.api_key == "test-key-123"


def test_agent_config_defaults():
    from reqradar.infrastructure.config import AgentConfig, ReportingConfig

    agent = AgentConfig()
    assert agent.max_steps == 15
    assert agent.max_steps_quick == 10
    assert agent.max_steps_deep == 25
    assert agent.version_limit == 10

    reporting = ReportingConfig()
    assert reporting.default_template_id == 1


def test_home_config_default():
    from reqradar.infrastructure.config import HomeConfig

    hc = HomeConfig()
    assert hc.path == "~/.reqradar" or "~" not in hc.path


def test_home_config_custom():
    from reqradar.infrastructure.config import HomeConfig

    hc = HomeConfig(path="/custom/home")
    assert hc.path == "/custom/home"


def test_config_home_default():
    from reqradar.infrastructure.config import Config

    c = Config()
    assert c.home is not None


def test_web_config_data_root_default():
    from reqradar.infrastructure.config import WebConfig

    wc = WebConfig()
    assert wc.data_root == ""


def test_web_config_reports_path_default():
    from reqradar.infrastructure.config import WebConfig

    wc = WebConfig()
    assert wc.reports_path == ""


def test_memory_config_simplified():
    from reqradar.infrastructure.config import MemoryConfig

    mc = MemoryConfig()
    assert mc.storage_path == ""
    assert not hasattr(mc, "project_storage_path")
    assert not hasattr(mc, "user_storage_path")
