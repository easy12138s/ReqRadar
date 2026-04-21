"""测试基础设施层"""


def test_config_default():
    from reqradar.infrastructure.config import Config

    config = Config()
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-4o-mini"
    assert config.llm.embedding_model == "text-embedding-3-small"
    assert config.llm.embedding_dim == 1024


def test_config_env_var_resolution():
    import os

    from reqradar.infrastructure.config import Config

    os.environ["TEST_API_KEY"] = "test-key-123"

    config_dict = {"llm": {"api_key": "${TEST_API_KEY}"}}
    resolved = Config(**config_dict)

    assert resolved.llm.api_key == "test-key-123"


def test_analysis_config_tool_use_defaults():
    from reqradar.infrastructure.config import AnalysisConfig

    config = AnalysisConfig()
    assert config.tool_use_max_rounds == 15
    assert config.tool_use_max_tokens == 8000
    assert config.tool_use_enabled is True


def test_analysis_config_tool_use_custom():
    from reqradar.infrastructure.config import AnalysisConfig

    config = AnalysisConfig(tool_use_max_rounds=5, tool_use_max_tokens=3000, tool_use_enabled=False)
    assert config.tool_use_max_rounds == 5
    assert config.tool_use_max_tokens == 3000
    assert config.tool_use_enabled is False
