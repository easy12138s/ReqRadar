"""KnowledgePrecipitator — L3 知识沉淀器。

负责在 Session 完成后，将推理结果中的可沉淀知识提取并写入 L3 知识库。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("reqradar.cognitive_rt.cognition.knowledge_precipitator")

# 重试配置
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 0.5


class KnowledgePrecipitator:
    """L3 知识沉淀器 — 从推理结果中提取可沉淀知识并写入 index-service。"""

    def __init__(
        self,
        service_url: str | None = None,
        internal_api_key: str | None = None,
    ) -> None:
        """初始化知识沉淀器。

        Args:
            service_url: index-service 的 URL，默认从环境变量获取
            internal_api_key: 内部 API Key，默认从环境变量获取
        """
        self._service_url = service_url or os.environ.get(
            "REQRADAR_INDEX_SERVICE_URL", "http://index-service:8003"
        )
        self._internal_api_key = internal_api_key or os.environ.get(
            "REQRADAR_INTERNAL_API_KEY", ""
        )

    async def precipitate(
        self,
        project_id: str,
        session_id: str,
        agent_data: dict[str, Any],
    ) -> bool:
        """将推理结果中的知识沉淀到 L3 知识库。

        Args:
            project_id: 项目 ID
            session_id: Session ID
            agent_data: Agent 的上下文快照数据

        Returns:
            是否成功沉淀
        """
        if not self._service_url:
            logger.warning("KnowledgePrecipitator: service_url 未配置")
            return False

        try:
            # 提取可沉淀知识
            knowledge_items = self._extract_knowledge(agent_data)
            if not knowledge_items:
                logger.info("没有可沉淀的知识")
                return True

            # 写入 index-service
            success_count = 0
            for item in knowledge_items:
                success = await self._write_knowledge(
                    project_id=project_id,
                    session_id=session_id,
                    knowledge_type=item["type"],
                    content=item["content"],
                    topic=item.get("topic", ""),
                    confidence=item.get("confidence", 0.5),
                )
                if success:
                    success_count += 1

            logger.info(
                "知识沉淀完成: project_id=%s, session_id=%s, total=%d, success=%d",
                project_id,
                session_id,
                len(knowledge_items),
                success_count,
            )
            return success_count > 0

        except Exception as e:
            logger.warning("知识沉淀失败: %s", e)
            return False

    def _extract_knowledge(self, agent_data: dict[str, Any]) -> list[dict[str, Any]]:
        """从 Agent 数据中提取可沉淀知识。

        Args:
            agent_data: Agent 的上下文快照数据

        Returns:
            可沉淀知识列表
        """
        items = []

        # 提取术语知识
        evidence_list = agent_data.get("evidence_list", [])
        for evidence in evidence_list:
            if evidence.get("type") == "term":
                items.append({
                    "type": "glossary",
                    "content": evidence.get("content", ""),
                    "topic": evidence.get("source", ""),
                    "confidence": self._confidence_to_float(evidence.get("confidence", "medium")),
                })
            elif evidence.get("type") == "analysis":
                # 提取风险相关知识
                content = evidence.get("content", "")
                if any(keyword in content.lower() for keyword in ["risk", "danger", "warning", "caution"]):
                    items.append({
                        "type": "risk_pattern",
                        "content": content,
                        "topic": "risk_analysis",
                        "confidence": self._confidence_to_float(evidence.get("confidence", "medium")),
                    })

        # 提取维度状态知识
        dimension_status = agent_data.get("dimension_status", {})
        if dimension_status.get("risk") == "sufficient":
            # 提取风险维度的证据
            risk_evidences = [
                e for e in evidence_list
                if "risk" in e.get("dimensions", [])
            ]
            for ev in risk_evidences[:3]:  # 最多取 3 条
                items.append({
                    "type": "risk_pattern",
                    "content": ev.get("content", ""),
                    "topic": "dimension_risk",
                    "confidence": self._confidence_to_float(ev.get("confidence", "medium")),
                })

        return items

    def _confidence_to_float(self, confidence: str) -> float:
        """将置信度字符串转换为浮点数。

        Args:
            confidence: 置信度字符串 ("high", "medium", "low")

        Returns:
            浮点数置信度
        """
        mapping = {"high": 0.9, "medium": 0.6, "low": 0.3}
        return mapping.get(confidence, 0.5)

    async def _write_knowledge(
        self,
        project_id: str,
        session_id: str,
        knowledge_type: str,
        content: str,
        topic: str = "",
        confidence: float = 0.5,
    ) -> bool:
        """写入知识到 index-service。

        Args:
            project_id: 项目 ID
            session_id: Session ID
            knowledge_type: 知识类型
            content: 知识内容
            topic: 主题
            confidence: 置信度

        Returns:
            是否成功写入
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "%s/internal/v2/knowledge/append" % self._service_url,
                    json={
                        "project_id": project_id,
                        "knowledge_type": knowledge_type,
                        "content": content,
                        "topic": topic,
                        "source_session_ids": [session_id],
                        "confidence_score": confidence,
                    },
                    headers={"X-Internal-API-Key": self._internal_api_key},
                )
                if resp.status_code != 200:
                    logger.warning("写入知识失败: HTTP %d", resp.status_code)
                    return False
                return True
        except Exception as e:
            logger.warning("写入知识异常: %s", e)
            return False
