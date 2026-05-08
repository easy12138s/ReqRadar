"""测试 LLM 客户端"""

import pytest
from reqradar.modules.llm_client import LiteLLMClient, create_llm_client


def test_create_llm_client_litellm():
    client = create_llm_client(
        model="gpt-4o-mini", api_key="test", base_url="https://api.openai.com/v1"
    )
    assert isinstance(client, LiteLLMClient)
    assert client.model == "gpt-4o-mini"


def test_create_llm_client_ollama():
    client = create_llm_client(model="ollama/qwen2.5:14b", api_base="http://localhost:11434/v1")
    assert isinstance(client, LiteLLMClient)
    assert "ollama/" in client.model


def test_create_llm_client_default_model():
    client = create_llm_client()
    assert client.model == "gpt-4o-mini"


class TestLiteLLMClientAttributes:
    def test_client_has_all_methods(self):
        llm = LiteLLMClient(model="gpt-4o-mini", api_key="test")
        assert hasattr(llm, "complete")
        assert hasattr(llm, "stream_complete")
        assert hasattr(llm, "complete_structured")
        assert hasattr(llm, "complete_with_tools")
        assert hasattr(llm, "complete_vision")
        assert hasattr(llm, "supports_tool_calling")

    def test_ollama_host_routing(self):
        llm = LiteLLMClient(model="ollama/qwen2.5", host="http://localhost:11434")
        assert llm.api_base == "http://localhost:11434/v1"

    def test_deepseek_model(self):
        llm = LiteLLMClient(
            model="deepseek/deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
        )
        assert llm.model == "deepseek/deepseek-chat"
        assert llm.api_base == "https://api.deepseek.com/v1"
