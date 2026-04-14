"""Agent 5步工作流实现"""

import json

from reqradar.core.context import (
    AnalysisContext,
    DeepAnalysis,
    RequirementUnderstanding,
    RetrievedContext,
)
from reqradar.core.exceptions import LLMException


def _parse_json_response(response: str) -> dict:
    """从 LLM 响应中提取 JSON，兼容 markdown 代码块包裹"""
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)

SYSTEM_PROMPT = """你是一个需求分析助手。请严格按照要求输出JSON，不要输出任何其他内容，不要使用markdown代码块。

你的职责：
1. 准确提取需求的核心内容和目标
2. 识别关键业务术语和技术关键词
3. 识别潜在的非功能性约束
4. 生成简洁的需求摘要

输出格式（直接输出JSON，不要包裹在代码块中）：
{"summary": "需求摘要", "keywords": ["关键词1", "关键词2"], "constraints": ["约束1", "约束2"], "business_goals": "业务目标描述"}
"""

EXTRACT_PROMPT = """请分析以下需求文档，提取关键信息。直接输出JSON，不要输出任何其他内容。

需求文档内容：
---
{content}
---

请提取并输出JSON：
{{"summary": "需求摘要（100-200字）", "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"], "constraints": ["约束1", "约束2"], "business_goals": "业务目标描述"}}"""


RETRIEVE_PROMPT = """基于以下关键词，评估相似需求的检索结果。直接输出JSON，不要输出其他内容。

关键词：{keywords}

检索到的相似需求：
{results}

输出JSON：
[{{"id": "...", "title": "...", "relevance": "high/medium/low", "reason": "关联原因"}}]"""


ANALYZE_PROMPT = """基于以下分析结果，评估技术影响和风险。直接输出JSON，不要输出其他内容。

需求摘要：{summary}

涉及模块：{modules}

建议评审人：{contributors}

输出JSON：
{{"risk_level": "low/medium/high", "risk_details": ["风险点1", "风险点2"], "verification_points": ["验证点1"]}}"""


GENERATE_PROMPT = """基于以下分析结果，生成需求分析报告的自然语言段落。直接输出JSON，不要输出其他内容。

需求摘要：{summary}

相似需求：{similar_reqs}

影响模块：{modules}

评审人建议：{contributors}

风险评估：{risk_analysis}

输出JSON：
{{"understanding": "需求理解（100字以内）", "relation": "关联说明（50字以内）", "constraints": "约束描述（100字以内）"}}"""


async def step_read(context: AnalysisContext) -> str:
    """Step 1: 读取需求文档"""
    path = context.requirement_path

    if not path.exists():
        raise FileNotFoundError(f"Requirement file not found: {path}")

    with open(path, encoding="utf-8") as f:
        content = f.read()

    context.requirement_text = content

    return content


async def step_extract(context: AnalysisContext, llm_client) -> RequirementUnderstanding:
    """Step 2: 提取关键术语"""
    understanding = RequirementUnderstanding()
    understanding.raw_text = context.requirement_text

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": EXTRACT_PROMPT.format(content=context.requirement_text[:4000]),
            },
        ]

        response = await llm_client.complete(messages, max_tokens=1024)
        result = _parse_json_response(response)
        understanding.summary = result.get("summary", "")
        understanding.keywords = result.get("keywords", [])
        understanding.constraints = result.get("constraints", [])
        understanding.business_goals = result.get("business_goals", "")

    except (json.JSONDecodeError, LLMException, Exception):
        understanding.keywords = _fallback_keyword_extraction(context.requirement_text)

    context.understanding = understanding
    return understanding


def _fallback_keyword_extraction(text: str) -> list[str]:
    """降级：基于规则提取关键词"""
    import re

    words = re.findall(r"\b[a-zA-Z\u4e00-\u9fa5]{2,}\b", text)

    stopwords = {
        "的",
        "了",
        "和",
        "是",
        "在",
        "我",
        "有",
        "个",
        "与",
        "及",
        "等",
        "the",
        "a",
        "an",
        "is",
        "are",
        "and",
        "or",
        "the",
        "this",
        "that",
    }

    keywords = [w for w in set(words) if w not in stopwords and len(w) > 1]
    return keywords[:10]


async def step_retrieve(
    context: AnalysisContext,
    vector_store,
) -> RetrievedContext:
    """Step 3: 检索相似需求与代码"""
    retrieved = RetrievedContext()

    keywords = context.understanding.keywords if context.understanding else []
    if not keywords:
        return retrieved

    try:
        query = " ".join(keywords[:5])
        results = vector_store.search(query, top_k=5)

        retrieved.similar_requirements = [
            {
                "id": r.id,
                "content": r.content,
                "metadata": r.metadata,
                "distance": r.distance,
            }
            for r in results
        ]
    except Exception:
        retrieved.similar_requirements = []

    return retrieved


async def step_analyze(
    context: AnalysisContext,
    code_graph,
    git_analyzer,
    llm_client,
) -> DeepAnalysis:
    """Step 4: 深度分析"""
    analysis = DeepAnalysis()

    keywords = context.understanding.keywords if context.understanding else []

    if code_graph and keywords:
        matched_files = code_graph.find_symbols(keywords)
        analysis.impact_modules = [
            {"path": f.path, "symbols": [s.name for s in f.symbols[:5]]} for f in matched_files[:10]
        ]

        if git_analyzer and matched_files:
            file_paths = [f.path for f in matched_files]
            contributor_info = git_analyzer.get_file_contributors(file_paths)

            analysis.contributors = [
                {
                    "name": c.primary_contributor.name if c.primary_contributor else "未知",
                    "email": c.primary_contributor.email if c.primary_contributor else "",
                    "file": c.file_path,
                    "reason": "主要贡献者",
                }
                for c in contributor_info[:5]
                if c.primary_contributor
            ]

    return analysis


async def step_generate(
    context: AnalysisContext,
    llm_client,
) -> dict:
    """Step 5: 生成报告段落"""
    understanding = context.understanding
    analysis = context.deep_analysis
    retrieved = context.retrieved_context

    similar_reqs_str = ""
    if retrieved and retrieved.similar_requirements:
        for req in retrieved.similar_requirements[:3]:
            similar_reqs_str += f"- {req.get('metadata', {}).get('title', 'Unknown')}\n"

    modules_str = ""
    if analysis and analysis.impact_modules:
        for m in analysis.impact_modules[:5]:
            modules_str += f"- {m['path']}\n"

    contributors_str = ""
    if analysis and analysis.contributors:
        for c in analysis.contributors[:3]:
            contributors_str += f"- {c['name']} ({c['file']})\n"

    prompt = GENERATE_PROMPT.format(
        summary=understanding.summary if understanding else "",
        similar_reqs=similar_reqs_str or "无",
        modules=modules_str or "无",
        contributors=contributors_str or "无",
        risk_analysis="待评估",
    )

    try:
        messages = [
            {"role": "user", "content": prompt},
        ]
        response = await llm_client.complete(messages, max_tokens=1024)

        result = _parse_json_response(response)
        return result
    except (json.JSONDecodeError, LLMException, Exception):
        return {
            "understanding": understanding.summary if understanding else "无法生成",
            "relation": "基于关键词匹配",
            "constraints": ", ".join(understanding.constraints) if understanding else "无",
        }
