import json
import logging

from reqradar.agent.llm_utils import _call_llm_structured, _complete_with_tools, _parse_json_response
from reqradar.agent.tool_call_tracker import ToolCallTracker
from reqradar.agent.tools.base import ToolResult

logger = logging.getLogger("reqradar.agent.tool_use_loop")


def _estimate_tokens(text: str) -> int:
    return len(text) // 3


async def run_tool_use_loop(
    llm_client,
    system_prompt: str,
    user_prompt: str,
    tools: list[str],
    tool_registry,
    output_schema: dict,
    max_rounds: int = 5,
    max_total_tokens: int = 8000,
    **kwargs,
) -> dict:
    tracker = ToolCallTracker(max_rounds=max_rounds, max_total_tokens=max_total_tokens)
    tool_schemas = tool_registry.get_schemas(tools) if tools else []
    tool_map = (
        {name: tool_registry._tools[name] for name in tools if name in tool_registry._tools}
        if tools
        else {}
    )

    if not tool_schemas:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await _call_llm_structured(llm_client, messages, output_schema, **kwargs)
        return result or {}

    supported = await llm_client.supports_tool_calling()
    if not supported:
        logger.info("Model does not support tool calling, using complete_structured fallback")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await _call_llm_structured(llm_client, messages, output_schema, **kwargs)
        return result or {}

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for round_idx in range(max_rounds + 1):
        if not tracker.within_round_limit() and round_idx > 0:
            logger.info(
                "Tool use loop reached max rounds (%d), forcing final output", max_rounds
            )
            messages.append(
                {
                    "role": "user",
                    "content": "请基于已获取的信息，直接输出最终分析结果，不要再调用工具。",
                }
            )
            break

        if tool_schemas:
            response = await _complete_with_tools(llm_client, messages, tool_schemas, **kwargs)
        else:
            response = None

        if response is None:
            # Tool calling failed or not supported – single fallback to structured output
            result = await _call_llm_structured(llm_client, messages, output_schema, **kwargs)
            return result or {}

        if "tool_calls" in response and response["tool_calls"]:
            assistant_msg = response.get("assistant_message", {})
            if assistant_msg:
                messages.append(assistant_msg)

            for tool_call in response["tool_calls"]:
                tc_name = tool_call.get("name", "")
                tc_id = tool_call.get("id", "")
                tc_args_str = tool_call.get("arguments", "{}")

                try:
                    tc_args = json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
                except json.JSONDecodeError:
                    tc_args = {}

                if tc_name not in tool_map:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": f"Error: Unknown tool '{tc_name}'",
                        }
                    )
                    continue

                if tracker.is_duplicate(tc_name, tc_args):
                    logger.debug("Dedup: skipping duplicate call to %s", tc_name)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": "(此调用已去重，跳过重复请求)",
                        }
                    )
                    continue

                tracker.track_call(tc_name, tc_args)
                tool = tool_map[tc_name]

                try:
                    result = await tool.execute(**tc_args)
                    result_text = result.data if result.success else f"Error: {result.error}"
                except Exception as e:
                    result_text = f"Error executing {tc_name}: {e}"

                tokens = _estimate_tokens(result_text)
                if tracker.within_token_budget(tokens):
                    tracker.add_tokens(tokens)
                else:
                    result_text = (
                        f"Error: Token budget exceeded (used {tracker._total_tokens}/{max_total_tokens})"
                    )

                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result_text})

                logger.info(
                    "Tool #%d: %s(%s) -> %d chars",
                    tracker.call_count,
                    tc_name,
                    json.dumps(tc_args, ensure_ascii=False)[:60],
                    len(result_text),
                )

        elif "content" in response:
            content = response["content"]
            try:
                parsed = _parse_json_response(content)
                return parsed
            except (json.JSONDecodeError, ValueError):
                return {"content": content}

    logger.info("Generating final structured output after tool use loop")
    logger.info("Tool usage summary:\n%s", tracker.summary())
    result = await _call_llm_structured(llm_client, messages, output_schema, **kwargs)
    return result or {}
