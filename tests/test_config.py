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
