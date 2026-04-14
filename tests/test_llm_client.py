"""测试 LLM 客户端"""


import pytest
from reqradar.modules.llm_client import OllamaClient, OpenAIClient, create_llm_client


def test_create_llm_client_openai():
    client = create_llm_client("openai", api_key="test", model="gpt-4o")
    assert isinstance(client, OpenAIClient)
    assert client.model == "gpt-4o"


def test_create_llm_client_ollama():
    client = create_llm_client("ollama", model="qwen2.5")
    assert isinstance(client, OllamaClient)
    assert client.model == "qwen2.5"


def test_create_llm_client_unknown():
    with pytest.raises(ValueError):
        create_llm_client("unknown")
