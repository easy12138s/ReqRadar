import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker
from reqradar.agent.prompts.chatback_phase import build_chatback_system_prompt
from reqradar.web.models import ReportChat
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.chatback_service")

INTENT_KEYWORDS = {
    "explain": ["为什么", "怎么", "如何", "原因", "依据", "解释", "说明", "是什么", "什么意思"],
    "correct": ["遗漏", "补充", "写错", "应该是", "不对", "错误", "更正", "修正", "需要加"],
    "deepen": ["详细", "深入", "展开", "更多", "细节", "具体", "更详细"],
    "explore": ["看看", "查看", "查看一下", "去查", "分析一下", "检查"],
}


def classify_intent(message: str) -> str:
    message_lower = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                return intent
    return "other"


class ChatbackService:
    def __init__(
        self,
        version_service: VersionService,
        llm_client=None,
        tool_registry=None,
        config=None,
    ):
        self.version_service = version_service
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.config = config

    async def chat(
        self,
        task_id: int,
        version_number: int,
        user_message: str,
        user_id: int,
    ) -> dict:
        intent = classify_intent(user_message)

        version = await self.version_service.get_version(task_id, version_number)
        if version is None:
            return {"reply": "未找到指定版本的报告。", "intent_type": "error", "updated": False}

        report_data = version.report_data or {}

        context_snapshot = await self.version_service.get_context_snapshot(task_id, version_number)
        if context_snapshot is None:
            context_snapshot = {
                "evidence_list": [],
                "dimension_status": {},
                "visited_files": [],
                "tool_calls": [],
            }

        agent = AnalysisAgent(
            requirement_text=report_data.get("requirement_title", ""),
            project_id=0,
            user_id=user_id,
            depth="standard",
        )
        agent.restore_from_snapshot(context_snapshot)

        chat_record = ReportChat(
            task_id=task_id,
            version_number=version_number,
            role="user",
            content=user_message,
            intent_type=intent,
        )

        reply = await self._generate_reply(
            agent, report_data, context_snapshot, user_message, intent
        )

        agent_reply = ReportChat(
            task_id=task_id,
            version_number=version_number,
            role="agent",
            content=reply,
            evidence_refs=[ev["id"] for ev in context_snapshot.get("evidence_list", [])[:5]],
        )

        db = self.version_service.db
        db.add(chat_record)
        db.add(agent_reply)
        await db.commit()
        await db.refresh(chat_record)
        await db.refresh(agent_reply)

        updated = intent in ("correct", "deepen", "explore")

        return {
            "reply": reply,
            "intent_type": intent,
            "updated": updated,
            "new_version": None,
            "report_preview": None if not updated else report_data,
            "chat_id": agent_reply.id,
        }

    async def _generate_reply(
        self,
        agent: AnalysisAgent,
        report_data: dict,
        context_snapshot: dict,
        user_message: str,
        intent: str,
    ) -> str:
        if self.llm_client is None:
            return self._generate_fallback_reply(
                report_data, context_snapshot, user_message, intent
            )

        system_prompt = build_chatback_system_prompt(
            report_data=report_data,
            context_snapshot=context_snapshot,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.llm_client.complete(messages)
            if response and response.strip():
                return response.strip()
            logger.warning("Chatback LLM call returned empty response")
        except Exception as e:
            logger.warning("Chatback LLM call failed: %s, using fallback", e)

        return self._generate_fallback_reply(report_data, context_snapshot, user_message, intent)

    def _generate_fallback_reply(
        self,
        report_data: dict,
        context_snapshot: dict,
        user_message: str,
        intent: str,
    ) -> str:
        return "LLM 未配置或调用失败，无法生成智能回复。请在设置页面配置大模型后再试。"

    async def save_as_new_version(
        self,
        task_id: int,
        version_number: int,
        user_id: int,
        updated_report_data: dict | None = None,
        updated_content_markdown: str | None = None,
    ) -> dict:
        current_version = await self.version_service.get_version(task_id, version_number)
        if current_version is None:
            return {"success": False, "error": "Version not found"}

        report_data = updated_report_data or current_version.report_data or {}
        context_snapshot = await self.version_service.get_context_snapshot(task_id, version_number)
        content_md = updated_content_markdown or current_version.content_markdown

        new_version = await self.version_service.create_version(
            task_id=task_id,
            report_data=report_data,
            context_snapshot=context_snapshot or {},
            content_markdown=content_md,
            content_html=current_version.content_html,
            trigger_type="global_chat",
            trigger_description=f"User chat lead to update from version {version_number}",
            created_by=user_id,
        )

        return {
            "success": True,
            "new_version": new_version.version_number,
        }

    async def get_chat_history(self, task_id: int, version_number: int = None) -> list[dict]:
        db = self.version_service.db
        query = select(ReportChat).where(ReportChat.task_id == task_id)
        if version_number is not None:
            query = query.where(ReportChat.version_number == version_number)
        query = query.order_by(ReportChat.created_at.asc())
        result = await db.execute(query)
        chats = result.scalars().all()
        return [
            {
                "id": c.id,
                "version_number": c.version_number,
                "role": c.role,
                "content": c.content,
                "intent_type": c.intent_type,
                "evidence_refs": c.evidence_refs or [],
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in chats
        ]
