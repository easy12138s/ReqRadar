#!/usr/bin/env python3
"""MiniMax API 测试 - 检查 function calling 响应格式"""

import asyncio
import json
import os

import httpx


async def test_minimax_function_calling():
    """测试 MiniMax API 的 function calling 响应"""

    api_key = "sk-api-fNt5hVLGuZuJknY2UYk96G-1celhCTbAcLSprVcHKZBt2sEKBdQTD8zdCu7XBEkbzdUQO_2lJk9HJ_LWzt1knk9MNs8tXbdRgO7IAO9P3b1rI4am_ftHPJ4"
    base_url = "https://api.minimax.chat/v1"
    model = "MiniMax-Text-01"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    schema = {
        "name": "extract_terms",
        "description": "提取需求文档中的关键术语",
        "parameters": {
            "type": "object",
            "properties": {
                "terms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "term": {"type": "string", "description": "术语名称"},
                            "definition": {"type": "string", "description": "术语定义"},
                        },
                        "required": ["term", "definition"],
                    },
                    "description": "提取的术语列表",
                }
            },
            "required": ["terms"],
        },
    }

    tools = [
        {
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["parameters"],
            },
        }
    ]

    # 测试 1: 使用 tool_choice
    print("=" * 60)
    print("测试 1: 使用 tool_choice 参数")
    print("=" * 60)

    payload1 = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个专业的需求分析助手。"},
            {"role": "user", "content": "请提取以下需求中的关键术语：用户登录功能需要支持双因素认证。"},
        ],
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "extract_terms"}},
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload1,
            )
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"错误: {e}")

    # 测试 2: 不使用 tool_choice
    print("\n" + "=" * 60)
    print("测试 2: 不使用 tool_choice 参数")
    print("=" * 60)

    payload2 = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个专业的需求分析助手。"},
            {"role": "user", "content": "请提取以下需求中的关键术语，以JSON格式输出：用户登录功能需要支持双因素认证。"},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload2,
            )
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"错误: {e}")

    # 测试 3: 使用 "auto" tool_choice
    print("\n" + "=" * 60)
    print("测试 3: 使用 tool_choice='auto'")
    print("=" * 60)

    payload3 = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个专业的需求分析助手。"},
            {"role": "user", "content": "请提取以下需求中的关键术语：用户登录功能需要支持双因素认证。"},
        ],
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload3,
            )
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(test_minimax_function_calling())
