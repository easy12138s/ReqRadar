"""测试聊天加载器"""

import json
from pathlib import Path

import pytest

from reqradar.modules.loaders.chat_loader import ChatLoader, FeishuJSONParser, GenericCSVParser
from reqradar.modules.loaders.chat_types import ChatConversation, ChatMessage


class TestChatMessage:
    def test_defaults(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.timestamp is None
        assert msg.sender is None

    def test_with_sender(self):
        msg = ChatMessage(role="user", content="hello", sender="Alice")
        assert msg.sender == "Alice"


class TestChatConversation:
    def test_message_count(self):
        conv = ChatConversation(
            messages=[
                ChatMessage(role="user", content="hi", sender="Alice"),
                ChatMessage(role="user", content="hello", sender="Bob"),
            ]
        )
        assert conv.message_count == 2

    def test_participant_count(self):
        conv = ChatConversation(
            messages=[
                ChatMessage(role="user", content="hi", sender="Alice"),
                ChatMessage(role="user", content="hello", sender="Bob"),
                ChatMessage(role="user", content="hey", sender="Alice"),
            ]
        )
        assert conv.participant_count == 2

    def test_to_text(self):
        conv = ChatConversation(
            messages=[
                ChatMessage(role="user", content="hi", sender="Alice"),
                ChatMessage(role="user", content="hello", sender="Bob"),
            ]
        )
        text = conv.to_text()
        assert "Alice: hi" in text
        assert "Bob: hello" in text


class TestFeishuJSONParser:
    def test_parse_array_format(self, tmp_path):
        data = [
            {"content": "讨论认证方案", "sender": {"name": "张三"}, "create_time": 1713139200},
            {"content": "用 OAuth2 吧", "sender": {"name": "李四"}, "create_time": 1713139260},
        ]
        json_file = tmp_path / "feishu_chat.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        parser = FeishuJSONParser()
        convs = parser.parse(json_file)

        assert len(convs) == 1
        assert convs[0].message_count == 2
        assert "认证方案" in convs[0].messages[0].content

    def test_parse_object_with_messages_key(self, tmp_path):
        data = {
            "messages": [
                {"content": "需求变更", "sender": "张三"},
                {"text": "收到", "sender": "李四"},
            ]
        }
        json_file = tmp_path / "feishu_chat.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        parser = FeishuJSONParser()
        convs = parser.parse(json_file)
        assert len(convs) == 1
        assert convs[0].message_count == 2

    def test_parse_empty(self, tmp_path):
        json_file = tmp_path / "empty.json"
        json_file.write_text("[]", encoding="utf-8")

        parser = FeishuJSONParser()
        convs = parser.parse(json_file)
        assert len(convs) == 0


class TestGenericCSVParser:
    def test_parse_csv_with_header(self, tmp_path):
        csv_file = tmp_path / "chat.csv"
        csv_file.write_text(
            "sender,content,timestamp\nAlice,需求讨论,2024-04-15 10:00:00\nBob,同意,2024-04-15 10:01:00",
            encoding="utf-8",
        )

        parser = GenericCSVParser()
        convs = parser.parse(csv_file)

        assert len(convs) == 1
        assert convs[0].message_count == 2
        assert convs[0].participant_count == 2

    def test_parse_csv_chinese_headers(self, tmp_path):
        csv_file = tmp_path / "chat.csv"
        csv_file.write_text(
            "发送者,消息,时间\nAlice,hello,2024-04-15 10:00:00",
            encoding="utf-8",
        )

        parser = GenericCSVParser()
        convs = parser.parse(csv_file)

        assert len(convs) == 1
        assert convs[0].message_count == 1

    def test_parse_empty_csv(self, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("sender,content\n", encoding="utf-8")

        parser = GenericCSVParser()
        convs = parser.parse(csv_file)
        assert len(convs) == 0


class TestChatLoader:
    def test_supported_extensions(self):
        loader = ChatLoader()
        exts = loader.supported_extensions()
        assert ".json" in exts
        assert ".csv" in exts

    def test_supports_feishu_json(self):
        loader = ChatLoader()
        assert loader.supports(Path("feishu_chat.json")) is True
        assert loader.supports(Path("chat_export.json")) is True
        assert loader.supports(Path("random_data.json")) is False

    def test_supports_csv(self):
        loader = ChatLoader()
        assert loader.supports(Path("chat.csv")) is True

    def test_load_csv(self, tmp_path):
        csv_file = tmp_path / "chat.csv"
        csv_file.write_text(
            "sender,content,timestamp\nAlice,需求讨论,2024-04-15 10:00:00",
            encoding="utf-8",
        )

        loader = ChatLoader()
        docs = loader.load(csv_file)

        assert len(docs) >= 1
        assert docs[0].format == "chat"
        assert "Alice" in docs[0].content

    def test_load_feishu_json(self, tmp_path):
        data = [
            {"content": "讨论认证方案", "sender": "张三"},
            {"content": "用OAuth2吧", "sender": "李四"},
        ]
        json_file = tmp_path / "feishu_chat.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        loader = ChatLoader()
        docs = loader.load(json_file)

        assert len(docs) >= 1
        assert docs[0].format == "chat"

    def test_load_nonexistent_file(self):
        loader = ChatLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(Path("/nonexistent/chat.json"))

    def test_load_plain_json_not_chat(self, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text('{"key": "value"}', encoding="utf-8")

        loader = ChatLoader()
        assert loader.supports(json_file) is False

    def test_chunk_long_conversation(self, tmp_path):
        messages = [{"content": f"Message {i} " * 20, "sender": f"User{i % 3}"} for i in range(50)]
        data = {"messages": messages}
        json_file = tmp_path / "feishu_chat.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        loader = ChatLoader(chunk_size=300)
        docs = loader.load(json_file)

        assert len(docs) > 1
