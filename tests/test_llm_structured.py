"""测试 LLM 结构化输出（function calling）—— LiteLLM 适配"""

import pytest

from reqradar.modules.llm_client import LiteLLMClient


class TestLiteLLMCompleteStructured:
    def test_client_has_structured_method(self):
        client = LiteLLMClient(api_key="test-key", model="test-model")
        assert hasattr(client, "complete_structured")
        assert hasattr(client, "complete_with_tools")

    def test_client_has_vision_method(self):
        client = LiteLLMClient(api_key="test-key", model="gpt-4o")
        assert hasattr(client, "complete_vision")

    def test_client_supports_tool_calling_by_default(self):
        client = LiteLLMClient(api_key="test-key", model="test-model")
        assert hasattr(client, "supports_tool_calling")

    def test_ollama_model_sets_api_base(self):
        client = LiteLLMClient(model="ollama/qwen2.5", host="http://localhost:11434")
        assert client.api_base == "http://localhost:11434/v1"

    def test_deepseek_model_routing(self):
        client = LiteLLMClient(
            model="deepseek/deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
        )
        assert "deepseek/" in client.model
        assert client.api_base == "https://api.deepseek.com/v1"

    def test_default_timeout_and_retries(self):
        client = LiteLLMClient()
        assert client.timeout == 60
        assert client.max_retries == 2
