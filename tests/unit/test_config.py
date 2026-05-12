from pathlib import Path

import pytest

from reqradar.infrastructure.config import Config, HomeConfig, LLMConfig, WebConfig, load_config


def test_home_config_expands_user_path():
    config = HomeConfig(path="~/.reqradar-test")

    assert config.path == str(Path("~/.reqradar-test").expanduser())


def test_llm_config_resolves_env_api_key(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-value")

    config = LLMConfig(api_key="${TEST_LLM_KEY}")

    assert config.api_key == "secret-value"


def test_config_allows_default_secret_when_testing(monkeypatch):
    monkeypatch.setenv("REQRADAR_TESTING", "1")

    config = Config(web=WebConfig(debug=False))

    assert config.web.secret_key == "change-me-in-production"


def test_config_warns_default_secret_outside_testing(monkeypatch):
    monkeypatch.delenv("REQRADAR_TESTING", raising=False)

    with pytest.warns(UserWarning, match="default JWT secret key"):
        Config(web=WebConfig(debug=False))


def test_load_config_resolves_nested_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("REQRADAR_TEST_KEY", "resolved-key")
    config_path = tmp_path / ".reqradar.yaml"
    config_path.write_text(
        "llm:\n  api_key: ${REQRADAR_TEST_KEY}\nweb:\n  debug: true\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.llm.api_key == "resolved-key"
    assert config.web.debug is True
