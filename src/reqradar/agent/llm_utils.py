"""Agent 层 - LLM 调用工具函数"""

import json
import logging
import re

logger = logging.getLogger("reqradar.agent")


def _strip_thinking_tags(text: str) -> str:
    """Remove MiniMax-style ◀thinking▶ and ◀reasoning_content▶ tags."""
    text = re.sub(r'◀thinking▶.*?◀/thinking▶', '', text, flags=re.DOTALL)
    text = re.sub(r'◀reasoning_content▶.*?◀/reasoning_content▶', '', text, flags=re.DOTALL)
    return text.strip()


def _parse_json_response(response: str):
    """从 LLM 响应中提取 JSON，兼容 markdown 代码块包裹和 JSON 数组"""
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        text = text[start_brace : end_brace + 1]
        return json.loads(text)
    start_bracket = text.find("[")
    end_bracket = text.rfind("]")
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        text = text[start_bracket : end_bracket + 1]
        return json.loads(text)
    return json.loads(text)


async def _call_llm_structured(llm_client, messages: list[dict], schema: dict, **kwargs) -> dict | None:
    """调用 LLM 获取结构化输出。function calling 优先，失败时 fallback 到 complete + 文本解析。"""
    structured = await llm_client.complete_structured(messages, schema, **kwargs)
    if structured is not None:
        logger.debug("LLM function calling succeeded for %s", schema.get("name", "unknown"))
        return structured

    # Fallback: complete + parse JSON from response text
    logger.info("Function calling returned None for %s, falling back to complete + text parsing", schema.get("name", "unknown"))
    response = await llm_client.complete(messages, **kwargs)
    if response:
        cleaned = _strip_thinking_tags(response)
        try:
            return _parse_json_response(cleaned)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Fallback text parsing also failed for %s: %s", schema.get("name", "unknown"), e)
    return None


async def _complete_with_tools(
    llm_client, messages: list[dict], tools: list[dict], **kwargs
) -> dict | None:
    """调用LLM的tool_use接口，失败时返回None"""
    try:
        result = await llm_client.complete_with_tools(messages, tools, **kwargs)
        if result is not None:
            if "tool_calls" in result:
                logger.debug(
                    "complete_with_tools returned %d tool calls",
                    len(result["tool_calls"]),
                )
            elif "content" in result:
                logger.debug("complete_with_tools returned content (%d chars)", len(result["content"]))
        return result
    except Exception as e:
        logger.warning("complete_with_tools error: %s", e)
        return None
