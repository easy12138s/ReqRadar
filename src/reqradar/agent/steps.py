"""Agent 5步工作流实现 - Phase 3 增强版"""

import json
import logging
import re
from pathlib import Path

from reqradar.core.context import (
    AnalysisContext,
    ChangeAssessment,
    DeepAnalysis,
    GeneratedContent,
    ImplementationHints,
    RequirementUnderstanding,
    RetrievedContext,
    RiskItem,
    StructuredConstraint,
    TermDefinition,
)
from reqradar.core.exceptions import LLMException
from reqradar.agent.schemas import (
    ANALYZE_SCHEMA,
    EXTRACT_SCHEMA,
    GENERATE_SCHEMA,
    KEYWORD_MAPPING_SCHEMA,
    RETRIEVE_SCHEMA,
)
from reqradar.agent.prompts import (
    ANALYZE_PROMPT,
    EXTRACT_PROMPT,
    GENERATE_PROMPT,
    KEYWORD_MAPPING_PROMPT,
    RETRIEVE_PROMPT,
    SYSTEM_PROMPT,
)
from reqradar.agent.llm_utils import _call_llm_structured, _parse_json_response
from reqradar.agent.smart_matching import (
    _get_module_from_memory,
    _smart_module_matching,
)
from reqradar.agent.project_profile import step_build_project_profile

logger = logging.getLogger("reqradar.agent")


def _build_terminology_section(memory_data: dict | None) -> str:
    """从记忆数据构建术语注入段落"""
    if not memory_data or not memory_data.get("terminology"):
        return ""
    terms = memory_data["terminology"]
    if not terms:
        return ""
    lines = ["项目已知术语（请优先识别这些术语）："]
    for t in terms:
        line = f"- {t.get('term', '')}"
        if t.get("definition"):
            line += f": {t['definition']}"
        if t.get("domain"):
            line += f"（{t['domain']}）"
        lines.append(line)
    return "\n".join(lines)


def _build_project_context_section(memory_data: dict | None) -> str:
    """从记忆数据构建项目上下文注入段落"""
    if not memory_data:
        return ""
    sections = []
    profile = memory_data.get("project_profile")
    if profile and isinstance(profile, dict):
        lines = ["项目知识上下文："]
        if profile.get("name"):
            lines.append(f"- 项目名称：{profile['name']}")
        if profile.get("description"):
            lines.append(f"- 项目描述：{profile['description']}")
        tech_stack = profile.get("tech_stack")
        if tech_stack and isinstance(tech_stack, dict):
            langs = tech_stack.get("languages", [])
            frameworks = tech_stack.get("frameworks", [])
            if langs or frameworks:
                parts = langs + frameworks
                lines.append(f"- 技术栈：{', '.join(parts)}")
        if profile.get("architecture_style"):
            lines.append(f"- 架构风格：{profile['architecture_style']}")
        sections.append("\n".join(lines))
    modules = memory_data.get("modules")
    if modules and isinstance(modules, list) and modules:
        lines = ["项目模块："]
        for m in modules[:10]:
            name = m.get("name", "")
            responsibility = m.get("responsibility", "")
            if name:
                lines.append(f"- {name}：{responsibility}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _build_constraints_section(memory_data: dict | None) -> str:
    """从记忆数据构建约束注入段落"""
    if not memory_data or not memory_data.get("constraints"):
        return ""
    constraints = memory_data["constraints"]
    if not constraints:
        return ""
    lines = ["项目已知约束："]
    for c in constraints:
        if isinstance(c, dict):
            ctype = c.get("constraint_type", "other")
            desc = c.get("description", c.get("constraint", ""))
            if ctype != "other":
                lines.append(f"- [{ctype}] {desc}")
            else:
                lines.append(f"- {desc}")
    return "\n".join(lines)


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
    """Step 2: 提取关键术语和结构化信息"""
    understanding = RequirementUnderstanding()
    understanding.raw_text = context.requirement_text

    try:
        terminology_section = _build_terminology_section(context.memory_data)
        project_context_section = _build_project_context_section(context.memory_data)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": EXTRACT_PROMPT.format(
                    content=context.requirement_text[:4000],
                    terminology_section=terminology_section,
                    project_context_section=project_context_section,
                ),
            },
        ]

        result = await _call_llm_structured(llm_client, messages, EXTRACT_SCHEMA, max_tokens=2048)

        understanding.summary = result.get("summary", "")
        understanding.keywords = result.get("keywords", [])
        understanding.business_goals = result.get("business_goals", "")
        understanding.priority_suggestion = result.get("priority_suggestion", "")
        understanding.priority_reason = result.get("priority_reason", "")

        for t in result.get("terms", []):
            if isinstance(t, dict) and t.get("term"):
                understanding.terms.append(
                    TermDefinition(
                        term=t.get("term", ""),
                        definition=t.get("definition", ""),
                        domain=t.get("domain", ""),
                    )
                )

        for c in result.get("structured_constraints", []):
            if isinstance(c, dict) and c.get("description"):
                understanding.structured_constraints.append(
                    StructuredConstraint(
                        description=c.get("description", ""),
                        constraint_type=c.get("constraint_type", "other"),
                        source=c.get("source", "requirement_document"),
                    )
                )

        understanding.constraints = [
            c.description for c in understanding.structured_constraints
        ] + result.get("constraints", [])

        if not understanding.keywords:
            understanding.keywords = [t.term for t in understanding.terms]

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
        "的", "了", "和", "是", "在", "我", "有", "个", "与", "及", "等",
        "the", "a", "an", "is", "are", "and", "or", "this", "that",
    }

    keywords = [w for w in set(words) if w not in stopwords and len(w) > 1]
    return keywords[:10]


async def step_map_keywords(context: AnalysisContext, llm_client) -> dict:
    """将业务术语映射为代码搜索词"""
    understanding = context.understanding
    if not understanding or (not understanding.terms and not understanding.keywords):
        logger.info("No terms or keywords to map")
        return {}

    terms_to_map = []
    if understanding.terms:
        terms_to_map = [t.term for t in understanding.terms]
    elif understanding.keywords:
        terms_to_map = understanding.keywords[:10]

    if not terms_to_map:
        return {}

    try:
        messages = [
            {
                "role": "user",
                "content": KEYWORD_MAPPING_PROMPT.format(
                    terms="\n".join(f"- {t}" for t in terms_to_map)
                ),
            },
        ]

        result = await _call_llm_structured(
            llm_client, messages, KEYWORD_MAPPING_SCHEMA, max_tokens=1024
        )

        mappings = {}
        if result and "mappings" in result:
            for m in result["mappings"]:
                if isinstance(m, dict) and m.get("business_term"):
                    mappings[m["business_term"]] = m.get("code_terms", [])

        if mappings:
            context.expanded_keywords = _expand_keywords(terms_to_map, mappings)
            logger.info(
                "Keyword mapping completed: %d terms mapped to %d search keywords",
                len(mappings),
                len(context.expanded_keywords),
            )

        return mappings

    except Exception as e:
        logger.warning("Keyword mapping failed: %s", e)
        context.expanded_keywords = terms_to_map
        return {}


def _expand_keywords(original_terms: list[str], mappings: dict) -> list[str]:
    """扩展关键词列表"""
    expanded = set(original_terms)

    for term in original_terms:
        if term in mappings:
            for code_term in mappings[term]:
                expanded.add(code_term)

    return list(expanded)


async def step_retrieve(
    context: AnalysisContext, vector_store, llm_client=None
) -> RetrievedContext:
    """Step 3: 检索相似需求与代码"""
    retrieved = RetrievedContext()

    keywords = context.understanding.keywords if context.understanding else []
    expanded_keywords = context.expanded_keywords if context.expanded_keywords else keywords

    if not keywords:
        logger.info("No keywords extracted, skipping retrieval")
        return retrieved

    if vector_store:
        try:
            search_terms = expanded_keywords if expanded_keywords else keywords
            query = " ".join(search_terms[:10])
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
    context: AnalysisContext, code_graph, git_analyzer, llm_client=None
) -> DeepAnalysis:
    """Step 4: 深度分析"""
    analysis = DeepAnalysis()

    if llm_client and context.memory_data and context.understanding:
        try:
            impact_modules = await _smart_module_matching(
                context.understanding,
                context.memory_data,
                code_graph,
                llm_client,
            )
            analysis.impact_modules = impact_modules
            logger.info("Smart module matching found %d modules", len(impact_modules))
        except Exception as e:
            logger.warning(
                "Smart module matching failed for requirement '%s', falling back: %s",
                context.understanding.summary[:50] if context.understanding else "unknown",
                e,
            )

    if not analysis.impact_modules:
        keywords = context.expanded_keywords if context.expanded_keywords else (
            context.understanding.keywords if context.understanding else []
        )
        if code_graph and keywords:
            matched_files = code_graph.find_symbols(keywords)
            analysis.impact_modules = [
                {
                    "path": f.path,
                    "symbols": [s.name for s in f.symbols[:5]],
                    "relevance": "unknown",
                    "relevance_reason": "基于关键词匹配",
                    "suggested_changes": "",
                }
                for f in matched_files[:10]
            ]

    if git_analyzer and analysis.impact_modules:
        try:
            file_paths = [m["path"] for m in analysis.impact_modules]
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

    if llm_client:
        try:
            modules_text = ""
            if analysis.impact_modules:
                modules_text = "\n".join(
                    f"- {m['path']} ({', '.join(m['symbols'][:3])})"
                    for m in analysis.impact_modules[:5]
                )
            else:
                modules_text = "无匹配代码模块（请根据项目知识推断）"

            contributors_text = ""
            if analysis.contributors:
                contributors_text = "\n".join(
                    f"- {c['name']} ({c['file']})" for c in analysis.contributors[:3]
                )

            project_context_section = _build_project_context_section(context.memory_data)
            terminology_section = _build_terminology_section(context.memory_data)

            messages = [
                {
                    "role": "user",
                    "content": ANALYZE_PROMPT.format(
                        summary=context.understanding.summary if context.understanding else "",
                        modules_section=f"涉及模块：\n{modules_text}",
                        contributors_section=f"建议评审人：\n{contributors_text}" if contributors_text else "建议评审人：暂无",
                        project_context_section=project_context_section,
                        terminology_section=terminology_section,
                    ),
                },
            ]
            result = await _call_llm_structured(
                llm_client, messages, ANALYZE_SCHEMA, max_tokens=2048
            )

            analysis.risk_level = result.get("risk_level", "medium")

            for r in result.get("risks", []):
                if isinstance(r, dict):
                    analysis.risks.append(
                        RiskItem(
                            description=r.get("description", ""),
                            severity=r.get("severity", "medium"),
                            scope=r.get("scope", ""),
                            mitigation=r.get("mitigation", ""),
                        )
                    )
            analysis.risk_details = [r.description for r in analysis.risks]

            for ca in result.get("change_assessment", []):
                if isinstance(ca, dict):
                    analysis.change_assessment.append(
                        ChangeAssessment(
                            module=ca.get("module", ""),
                            change_type=ca.get("change_type", "modify"),
                            impact_level=ca.get("impact_level", "medium"),
                            reason=ca.get("reason", ""),
                        )
                    )

            analysis.verification_points = result.get("verification_points", [])

            impl_hints = result.get("implementation_hints", {})
            if isinstance(impl_hints, dict):
                analysis.implementation_hints = ImplementationHints(
                    approach=impl_hints.get("approach", ""),
                    effort_estimate=impl_hints.get("effort_estimate", ""),
                    dependencies=impl_hints.get("dependencies", []),
                )

        except (json.JSONDecodeError, LLMException, Exception) as e:
            logger.warning("LLM analyze failed, using defaults: %s", e)
            if analysis.risk_level == "unknown":
                analysis.risk_level = "medium"

    return analysis


async def step_generate(context: AnalysisContext, llm_client) -> GeneratedContent:
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
        risk_analysis = analysis.risk_level
        if analysis.risk_details:
            risk_analysis += ": " + ", ".join(analysis.risk_details[:3])

    change_assessment_str = ""
    if analysis and analysis.change_assessment:
        for ca in analysis.change_assessment[:3]:
            change_assessment_str += f"- {ca.module}: {ca.change_type} ({ca.impact_level})\n"

    project_context_section = _build_project_context_section(context.memory_data)

    prompt = GENERATE_PROMPT.format(
        summary=understanding.summary if understanding else "",
        modules=modules_str or "无",
        contributors=contributors_str or "无",
        risk_level=analysis.risk_level if analysis else "unknown",
        risk_details=risk_analysis,
        change_assessment=change_assessment_str or "无",
        project_context_section=project_context_section,
    )

    try:
        messages = [
            {"role": "user", "content": prompt},
        ]
        result = await _call_llm_structured(
            llm_client, messages, GENERATE_SCHEMA, max_tokens=2048
        )

        return GeneratedContent(
            requirement_understanding=result.get("requirement_understanding", ""),
            impact_narrative=result.get("impact_narrative", ""),
            risk_narrative=result.get("risk_narrative", ""),
            implementation_suggestion=result.get("implementation_suggestion", ""),
        )
    except (json.JSONDecodeError, LLMException, Exception) as e:
        logger.warning("LLM generate failed, using fallback: %s", e)
        return GeneratedContent(
            requirement_understanding=understanding.summary if understanding else "无法生成",
            impact_narrative="",
            risk_narrative="",
            implementation_suggestion="",
        )
