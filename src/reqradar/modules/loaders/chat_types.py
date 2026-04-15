"""聊天数据类型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: Optional[datetime] = None
    sender: Optional[str] = None


@dataclass
class ChatConversation:
    messages: list[ChatMessage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def participant_count(self) -> int:
        senders = {m.sender for m in self.messages if m.sender}
        return len(senders)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_text(self) -> str:
        lines = []
        for m in self.messages:
            sender = m.sender or m.role
            lines.append(f"{sender}: {m.content}")
        return "\n".join(lines)
