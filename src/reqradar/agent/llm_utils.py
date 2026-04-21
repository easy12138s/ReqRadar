"""Agent 层 - LLM 调用工具函数"""

import json
import logging

logger = logging.getLogger("reqradar.agent")


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


async def _call_llm_structured(llm_client, messages: list[dict], schema: dict, **kwargs) -> dict:
    """调用 LLM 获取结构化输出，function calling 优先，文本解析降级"""
    structured = await llm_client.complete_structured(messages, schema, **kwargs)
    if structured is not None:
        logger.info("LLM function calling succeeded for %s", schema.get("name", "unknown"))
        return structured

    logger.info("Function calling not available or failed, falling back to text parsing")
    response = await llm_client.complete(messages, **kwargs)
    return _parse_json_response(response)


async def _complete_with_tools(
    llm_client, messages: list[dict], tools: list[dict], **kwargs
) -> dict | None:
    """调用LLM的tool_use接口，失败时返回None"""
    try:
        result = await llm_client.complete_with_tools(messages, tools, **kwargs)
        return result
    except Exception as e:
        logger.warning("complete_with_tools error: %s", e)
        return None
