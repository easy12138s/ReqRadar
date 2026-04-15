"""聊天记录加载器 - 支持飞书 JSON 和通用 CSV"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from reqradar.modules.loaders.base import DocumentLoader, LoadedDocument
from reqradar.modules.loaders.chat_types import ChatConversation, ChatMessage

logger = logging.getLogger("reqradar.loaders.chat")


class FeishuJSONParser:
    """飞书聊天记录 JSON 解析器

    Expected format: a JSON array or object with messages.
    Each message should have fields like 'msg_type', 'content', 'sender', 'create_time'.
    Actual Feishu export format may vary; this handles common structures.
    """

    def parse(self, file_path: Path) -> list[ChatConversation]:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            messages = data
        elif isinstance(data, dict):
            messages = data.get("messages", data.get("data", []))
            if not isinstance(messages, list):
                messages = [data]
        else:
            logger.warning("Unexpected Feishu JSON structure in %s", file_path)
            return []

        chat_messages = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue

            content = self._extract_content(msg)
            sender = self._extract_sender(msg)
            timestamp = self._extract_timestamp(msg)

            if content:
                chat_messages.append(
                    ChatMessage(
                        role="user",
                        content=content,
                        timestamp=timestamp,
                        sender=sender,
                    )
                )

        if not chat_messages:
            return []

        return [
            ChatConversation(
                messages=chat_messages,
                metadata={
                    "source": str(file_path),
                    "format": "feishu_json",
                    "participant_count": len({m.sender for m in chat_messages if m.sender}),
                },
            )
        ]

    def _extract_content(self, msg: dict) -> str:
        content = msg.get("content", msg.get("text", msg.get("body", "")))
        if isinstance(content, dict):
            content = content.get(
                "text", content.get("content", json.dumps(content, ensure_ascii=False))
            )
        if content is None:
            content = ""
        return str(content).strip()

    def _extract_sender(self, msg: dict) -> Optional[str]:
        sender = msg.get("sender", msg.get("from", msg.get("user_name", None)))
        if isinstance(sender, dict):
            sender = sender.get("name", sender.get("nickname", str(sender)))
        return sender

    def _extract_timestamp(self, msg: dict) -> Optional[datetime]:
        ts = msg.get("create_time", msg.get("timestamp", msg.get("time", None)))
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
        if isinstance(ts, str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
        return None


class GenericCSVParser:
    """通用 CSV 聊天记录解析器

    Expected CSV format with header:
    - Must have a 'content' column
    - Optional columns: 'sender'/'role', 'timestamp'/'time'
    """

    def parse(self, file_path: Path) -> list[ChatConversation]:
        chat_messages = []

        with open(file_path, encoding="utf-8", newline="") as f:
            sample = f.read(4096)
            f.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample)
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                content = self._get_value(row, ["content", "text", "message", "消息"])
                if not content:
                    continue

                sender = self._get_value(row, ["sender", "role", "user", "发送者"])
                timestamp_str = self._get_value(row, ["timestamp", "time", "时间"])

                timestamp = None
                if timestamp_str:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                        try:
                            timestamp = datetime.strptime(timestamp_str, fmt)
                            break
                        except ValueError:
                            continue

                chat_messages.append(
                    ChatMessage(
                        role="user",
                        content=content.strip(),
                        timestamp=timestamp,
                        sender=sender,
                    )
                )

        if not chat_messages:
            return []

        return [
            ChatConversation(
                messages=chat_messages,
                metadata={
                    "source": str(file_path),
                    "format": "csv",
                    "participant_count": len({m.sender for m in chat_messages if m.sender}),
                },
            )
        ]

    def _get_value(self, row: dict, keys: list[str]) -> Optional[str]:
        for key in keys:
            if key in row and row[key]:
                return row[key]
        return None


class ChatLoader(DocumentLoader):
    """聊天记录加载器

    Supports .feishu.json, .chat.json, and .csv files.
    Returns LoadedDocument with chat conversations converted to text.
    """

    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._feishu_parser = FeishuJSONParser()
        self._csv_parser = GenericCSVParser()

    def supported_extensions(self) -> list[str]:
        return [".json", ".csv"]

    def supports(self, file_path: Path) -> bool:
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            return True
        if suffix == ".json":
            name_lower = file_path.name.lower()
            if "feishu" in name_lower or "chat" in name_lower or "message" in name_lower:
                return True
            return False
        return False

    def load(self, file_path: Path, **kwargs) -> list[LoadedDocument]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()
        conversations = []

        if suffix == ".csv":
            conversations = self._csv_parser.parse(file_path)
        elif suffix == ".json":
            conversations = self._feishu_parser.parse(file_path)

        if not conversations:
            logger.warning("No chat conversations extracted from: %s", file_path)
            return []

        return self._conversations_to_documents(conversations, file_path)

    def _conversations_to_documents(
        self, conversations: list[ChatConversation], file_path: Path
    ) -> list[LoadedDocument]:
        documents = []
        for conv in conversations:
            text = conv.to_text()
            if self.chunk_size and len(text) > self.chunk_size:
                chunks = self._chunk_chat_text(
                    text, chunk_size=self.chunk_size, overlap=self.chunk_overlap
                )
                for i, chunk in enumerate(chunks):
                    documents.append(
                        LoadedDocument(
                            content=chunk,
                            source=str(file_path),
                            format="chat",
                            metadata={
                                "title": file_path.stem,
                                "chunk_index": i,
                                "participant_count": conv.participant_count,
                                "message_count": conv.message_count,
                                **conv.metadata,
                            },
                        )
                    )
            else:
                documents.append(
                    LoadedDocument(
                        content=text,
                        source=str(file_path),
                        format="chat",
                        metadata={
                            "title": file_path.stem,
                            "participant_count": conv.participant_count,
                            "message_count": conv.message_count,
                            **conv.metadata,
                        },
                    )
                )
        return documents

    @staticmethod
    def _chunk_chat_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
        lines = text.split("\n")
        chunks = []
        current = []

        for line in lines:
            if sum(len(ln) for ln in current) + len(line) > chunk_size and current:
                chunks.append("\n".join(current))
                current = [line] if overlap < chunk_size else []
            else:
                current.append(line)

        if current:
            chunks.append("\n".join(current))

        return chunks if chunks else [text]
