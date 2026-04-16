"""Agent 5步工作流实现"""

import json
import logging
import re

from reqradar.core.context import (
    AnalysisContext,
    DeepAnalysis,
    RequirementUnderstanding,
    RetrievedContext,
)
from reqradar.core.exceptions import LLMException

logger = logging.getLogger("reqradar.agent")

SYSTEM_PROMPT = """你是一个需求分析助手。请严格按照要求输出JSON，不要输出任何其他内容，不要使用markdown代码块。

你的职责：
1. 准确提取需求的核心内容和目标
2. 识别关键业务术语和技术关键词
3. 识别潜在的非功能性约束
4. 生成简洁的需求摘要"""

EXTRACT_PROMPT = """请分析以下需求文档，提取关键信息。直接输出JSON，不要输出其他内容。

{terminology_section}

需求文档内容：
---
{content}
---

请提取并输出JSON：
{{"summary": "需求摘要（100-200字）", "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"], "constraints": ["约束1", "约束2"], "business_goals": "业务目标描述"}}"""

RETRIEVE_PROMPT = """基于以下关键词和检索到的相似需求，评估每个需求的关联度和参考价值。直接输出JSON，不要输出其他内容。

关键词：{keywords}

检索到的相似需求：
{results}

输出JSON数组：
[{{"id": "...", "title": "...", "relevance": "high/medium/low", "reason": "关联原因（20字以内）"}}]"""

ANALYZE_PROMPT = """基于以下分析结果，评估技术影响和风险。直接输出JSON，不要输出其他内容。

需求摘要：{summary}

涉及模块：{modules}

建议评审人：{contributors}

输出JSON：
{{"risk_level": "low/medium/high", "risk_details": ["风险点1", "风险点2"], "verification_points": ["验证点1", "验证点2"]}}"""

GENERATE_PROMPT = """基于以下分析结果，生成需求分析报告的自然语言段落。直接输出JSON，不要输出其他内容。

需求摘要：{summary}

相似需求：{similar_reqs}

影响模块：{modules}

评审人建议：{contributors}

风险评估：{risk_analysis}

输出JSON：
{{"understanding": "需求理解（100字以内）", "relation": "关联说明（50字以内）", "constraints": "约束描述（100字以内）"}}"""

EXTRACT_SCHEMA = {
    "name": "extract_requirement",
    "description": "从需求文档中提取关键信息",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "需求摘要（100-200字）"},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5-10个关键术语和关键词",
            },
            "constraints": {
                "type": "array",
                "items": {"type": "string"},
                "description": "非功能性约束列表",
            },
            "business_goals": {"type": "string", "description": "业务目标描述"},
        },
        "required": ["summary", "keywords"],
    },
}

RETRIEVE_SCHEMA = {
    "name": "evaluate_requirements",
    "description": "评估相似需求的关联度",
    "parameters": {
        "type": "object",
        "properties": {
            "evaluations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "需求ID"},
                        "title": {"type": "string", "description": "需求标题"},
                        "relevance": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "关联度",
                        },
                        "reason": {"type": "string", "description": "关联原因（20字以内）"},
                    },
                    "required": ["id", "relevance"],
                },
                "description": "每个需求关联度的评估结果",
            }
        },
        "required": ["evaluations"],
    },
}

ANALYZE_SCHEMA = {
    "name": "analyze_risks",
    "description": "评估技术影响和风险",
    "parameters": {
        "type": "object",
        "properties": {
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "总体风险等级",
            },
            "risk_details": {
                "type": "array",
                "items": {"type": "string"},
                "description": "风险点列表",
            },
            "verification_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "验证点列表",
            },
        },
        "required": ["risk_level"],
    },
}

GENERATE_SCHEMA = {
    "name": "generate_report_sections",
    "description": "生成需求分析报告的自然语言段落",
    "parameters": {
        "type": "object",
        "properties": {
            "understanding": {"type": "string", "description": "需求理解（100字以内）"},
            "relation": {"type": "string", "description": "关联说明（50字以内）"},
            "constraints": {"type": "string", "description": "约束描述（100字以内）"},
        },
        "required": ["understanding"],
    },
}


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
        terminology_section = ""
        if context.memory_data and context.memory_data.get("terminology"):
            terms = context.memory_data["terminology"]
            if terms:
                lines = ["项目已知术语（请优先识别这些术语）："]
                for t in terms:
                    line = f"- {t['term']}"
                    if t.get("definition"):
                        line += f": {t['definition']}"
                    lines.append(line)
                terminology_section = "\n".join(lines)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": EXTRACT_PROMPT.format(
                    content=context.requirement_text[:4000],
                    terminology_section=terminology_section,
                ),
            },
        ]

        result = await _call_llm_structured(llm_client, messages, EXTRACT_SCHEMA, max_tokens=1024)

        understanding.summary = result.get("summary", "")
        understanding.keywords = result.get("keywords", [])
        understanding.constraints = result.get("constraints", [])
        understanding.business_goals = result.get("business_goals", "")

    except (json.JSONDecodeError, LLMException) as e:
        logger.warning("LLM extract failed, using fallback keyword extraction: %s", e)
        understanding.keywords = _fallback_keyword_extraction(context.requirement_text)
    except Exception as e:
        logger.warning("Unexpected error in step_extract, using fallback: %s", e)
        understanding.keywords = _fallback_keyword_extraction(context.requirement_text)

    context.understanding = understanding
    return understanding


def _fallback_keyword_extraction(text: str) -> list[str]:
    """降级：基于规则提取关键词"""
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
        "this",
        "that",
    }

    keywords = [w for w in set(words) if w not in stopwords and len(w) > 1]
    return keywords[:10]


async def step_retrieve(
    context: AnalysisContext,
    vector_store,
    llm_client=None,
) -> RetrievedContext:
    """Step 3: 检索相似需求与代码"""
    retrieved = RetrievedContext()

    keywords = context.understanding.keywords if context.understanding else []
    if not keywords:
        logger.info("No keywords extracted, skipping retrieval")
        return retrieved

    if vector_store:
        try:
            query = " ".join(keywords[:5])
            results = vector_store.search(query, top_k=5)

            raw_reqs = [
                {
                    "id": r.id,
                    "content": r.content,
                    "metadata": r.metadata,
                    "distance": r.distance,
                }
                for r in results
            ]

            if llm_client and raw_reqs:
                try:
                    results_text = "\n".join(
                        f"- [{r['id']}] {r['metadata'].get('title', 'Unknown')}: {r['content'][:200]}"
                        for r in raw_reqs[:5]
                    )
                    messages = [
                        {
                            "role": "user",
                            "content": RETRIEVE_PROMPT.format(
                                keywords=", ".join(keywords[:5]),
                                results=results_text,
                            ),
                        },
                    ]
                    evaluated = await _call_llm_structured(
                        llm_client, messages, RETRIEVE_SCHEMA, max_tokens=1024
                    )
                    evaluations = evaluated.get("evaluations", evaluated)
                    if isinstance(evaluations, list):
                        for ev in evaluations:
                            for r in raw_reqs:
                                if r["id"] == ev.get("id", ""):
                                    r["relevance"] = ev.get("relevance", "unknown")
                                    r["reason"] = ev.get("reason", "")
                                    break
                except (json.JSONDecodeError, LLMException, Exception) as e:
                    logger.warning("LLM retrieve evaluation failed, using raw results: %s", e)

            retrieved.similar_requirements = raw_reqs
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            retrieved.similar_requirements = []

    return retrieved


async def step_analyze(
    context: AnalysisContext,
    code_graph,
    git_analyzer,
    llm_client=None,
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
            try:
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
            except Exception as e:
                logger.warning("Git analysis failed: %s", e)

        if llm_client and analysis.impact_modules:
            try:
                modules_text = "\n".join(
                    f"- {m['path']} ({', '.join(m['symbols'][:3])})"
                    for m in analysis.impact_modules[:5]
                )
                contributors_text = "\n".join(
                    f"- {c['name']} ({c['file']})" for c in analysis.contributors[:3]
                )
                messages = [
                    {
                        "role": "user",
                        "content": ANALYZE_PROMPT.format(
                            summary=context.understanding.summary if context.understanding else "",
                            modules=modules_text or "无",
                            contributors=contributors_text or "无",
                        ),
                    },
                ]
                result = await _call_llm_structured(
                    llm_client, messages, ANALYZE_SCHEMA, max_tokens=1024
                )
                analysis.risk_level = result.get("risk_level", "unknown")
                analysis.risk_details = result.get("risk_details", [])
            except (json.JSONDecodeError, LLMException, Exception) as e:
                logger.warning("LLM analyze failed, using defaults: %s", e)

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

    risk_analysis = "待评估"
    if analysis and analysis.risk_level != "unknown":
        risk_analysis = f"{analysis.risk_level}"
        if analysis.risk_details:
            risk_analysis += ": " + ", ".join(analysis.risk_details[:3])

    prompt = GENERATE_PROMPT.format(
        summary=understanding.summary if understanding else "",
        similar_reqs=similar_reqs_str or "无",
        modules=modules_str or "无",
        contributors=contributors_str or "无",
        risk_analysis=risk_analysis,
    )

    try:
        messages = [
            {"role": "user", "content": prompt},
        ]
        result = await _call_llm_structured(llm_client, messages, GENERATE_SCHEMA, max_tokens=1024)
        return result
    except (json.JSONDecodeError, LLMException, Exception) as e:
        logger.warning("LLM generate failed, using fallback: %s", e)
        return {
            "understanding": understanding.summary if understanding else "无法生成",
            "relation": "基于关键词匹配",
            "constraints": (
                ", ".join(understanding.constraints)
                if understanding and understanding.constraints
                else "无"
            ),
        }
