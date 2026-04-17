"""Agent 5步工作流实现 - Phase 3 增强版"""

import json
import logging
import re
from collections import Counter
from datetime import datetime
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

logger = logging.getLogger("reqradar.agent")

SYSTEM_PROMPT = """你是一个专业的需求分析助手。你的职责是深入理解需求文档，提取结构化信息。
请严格按照要求输出JSON，不要输出任何其他内容。每个术语都必须有定义，每个约束都要分类。"""

EXTRACT_PROMPT = """请深入分析以下需求文档，提取结构化信息。

{terminology_section}

{project_context_section}

需求文档内容：
---
{content}
---

请提取并输出JSON。术语必须包含定义和所属领域；约束请按类型分类（performance/security/compatibility/api_contract/ux/compliance），并注明来源（requirement_document/architecture/implicit）。"""

RETRIEVE_PROMPT = """基于以下关键词和检索到的相似需求，评估每个需求的关联度和参考价值。

关键词：{keywords}

检索到的相似需求：
{results}

输出JSON，evaluations 为数组，每个元素包含 id/title/relevance/reason。"""

ANALYZE_PROMPT = """基于以下需求信息和项目知识，评估技术影响和风险。

需求摘要：{summary}

{modules_section}

{contributors_section}

{project_context_section}

{terminology_section}

请评估技术影响和风险。即使没有代码匹配信息，也请根据需求内容和项目知识进行合理推断。
变更评估（change_assessment）：根据需求内容推断可能受影响的模块和变更类型。
风险（risks）：至少提供2个结构化风险项。
验证要点（verification_points）：至少提供3个评审时应重点验证的事项。
实施建议（implementation_hints）：提供实施方向、工作量评估和前置依赖。"""

GENERATE_PROMPT = """基于以下分析上下文，生成需求分析报告的关键叙述段落。

需求摘要：{summary}

影响模块：{modules}

评审人建议：{contributors}

风险评估：{risk_level} - {risk_details}

变更评估：{change_assessment}

{project_context_section}

请分别生成以下段落，要求有深度、有分析、有建议，不要泛泛而谈：
- requirement_understanding: 需求理解（150-200字，包含背景、核心问题、成功标准）
- impact_narrative: 影响范围描述（100-150字，描述涉及的技术组件和数据流向）
- risk_narrative: 风险分析描述（150-200字，主要风险和缓解思路）
- implementation_suggestion: 实施方向建议（100-150字，优先级建议和关键注意事项）"""


# ============== Schemas ==============

EXTRACT_SCHEMA = {
    "name": "extract_requirement",
    "description": "从需求文档中提取结构化信息",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "从业务视角的需求理解：背景、要解决的问题、成功标准（200字以内）",
            },
            "terms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string", "description": "术语/关键词"},
                        "definition": {"type": "string", "description": "术语的定义或含义"},
                        "domain": {"type": "string", "description": "所属领域（认证/前端/数据库/部署/...）"},
                    },
                    "required": ["term", "definition"],
                },
                "description": "需求涉及的关键术语及其定义（至少3个）",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5-10个关键术语和关键词（用于代码搜索）",
            },
            "structured_constraints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "约束内容"},
                        "constraint_type": {
                            "type": "string",
                            "enum": [
                                "performance",
                                "security",
                                "compatibility",
                                "api_contract",
                                "ux",
                                "compliance",
                                "other",
                            ],
                            "description": "约束类型",
                        },
                        "source": {
                            "type": "string",
                            "enum": ["requirement_document", "architecture", "implicit"],
                            "description": "约束来源",
                        },
                    },
                    "required": ["description", "constraint_type"],
                },
                "description": "结构化约束条件",
            },
            "business_goals": {"type": "string", "description": "业务目标描述"},
            "priority_suggestion": {
                "type": "string",
                "enum": ["urgent", "high", "medium", "low"],
                "description": "优先级建议",
            },
            "priority_reason": {
                "type": "string",
                "description": "优先级建议的理由（50字以内）",
            },
        },
        "required": ["summary", "terms"],
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
                "enum": ["low", "medium", "high", "critical"],
                "description": "总体风险等级",
            },
            "risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "风险描述"},
                        "severity": {"type": "string", "description": "严重程度（low/medium/high）"},
                        "scope": {"type": "string", "description": "影响范围"},
                        "mitigation": {"type": "string", "description": "缓解建议"},
                    },
                    "required": ["description", "severity"],
                },
                "description": "结构化风险列表（至少2个）",
            },
            "change_assessment": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module": {"type": "string", "description": "模块名称或路径"},
                        "change_type": {
                            "type": "string",
                            "enum": ["new", "modify", "remove", "refactor"],
                            "description": "变更类型",
                        },
                        "impact_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "影响等级",
                        },
                        "reason": {"type": "string", "description": "评估理由"},
                    },
                    "required": ["module", "change_type", "impact_level"],
                },
                "description": "变更评估列表",
            },
            "verification_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "评审时应重点验证的事项（至少3个）",
            },
            "implementation_hints": {
                "type": "object",
                "properties": {
                    "approach": {"type": "string", "description": "建议的实施方向"},
                    "effort_estimate": {"type": "string", "description": "工作量评估（small/medium/large）"},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "前置依赖",
                    },
                },
                "description": "实施建议",
            },
        },
        "required": ["risk_level"],
    },
}

GENERATE_SCHEMA = {
    "name": "generate_report_content",
    "description": "生成需求分析报告的关键叙述段落",
    "parameters": {
        "type": "object",
        "properties": {
            "requirement_understanding": {
                "type": "string",
                "description": "需求理解（150-200字，包含背景、核心问题、成功标准）",
            },
            "impact_narrative": {
                "type": "string",
                "description": "影响范围描述（100-150字）",
            },
            "risk_narrative": {
                "type": "string",
                "description": "主要风险和缓解思路的自然语言描述（150-200字）",
            },
            "implementation_suggestion": {
                "type": "string",
                "description": "实施方向建议和注意事项（100-150字）",
            },
        },
        "required": ["requirement_understanding"],
    },
}

PROJECT_PROFILE_SCHEMA = {
    "name": "build_project_profile",
    "description": "根据代码结构和技术栈信息，构建项目画像",
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "项目的一句话描述（50字以内）",
            },
            "architecture_style": {
                "type": "string",
                "description": "架构风格（如：分层架构、微服务、单体应用等）",
            },
            "tech_stack": {
                "type": "object",
                "properties": {
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "使用的编程语言",
                    },
                    "frameworks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "使用的框架",
                    },
                    "key_dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键依赖库",
                    },
                },
                "description": "技术栈信息",
            },
            "modules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "模块名称"},
                        "responsibility": {"type": "string", "description": "模块职责描述"},
                        "key_classes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "核心类名列表",
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "依赖的其他模块",
                        },
                    },
                    "required": ["name", "responsibility"],
                },
                "description": "项目模块列表（按目录划分，最多10个）",
            },
        },
        "required": ["description", "architecture_style", "modules"],
    },
}

PROJECT_PROFILE_PROMPT = """请根据以下项目代码结构信息，总结项目画像。

项目文件统计：
{file_stats}

主要目录结构：
{directory_structure}

核心文件（含主要类/函数）：
{key_files}

依赖文件内容：
{dependencies_content}

请分析并输出：
1. 项目描述：一句话概括项目用途
2. 架构风格：如分层架构、微服务、CLI工具等
3. 技术栈：语言、框架、关键依赖
4. 模块划分：按目录划分，每个模块的职责和核心类

要求：
- 模块划分要合理，通常按目录层级
- 每个模块的职责描述要具体
- 核心类列表最多5个
"""

KEYWORD_MAPPING_SCHEMA = {
    "name": "map_keywords_to_code",
    "description": "将业务术语映射为可能对应的代码层术语，用于代码搜索",
    "parameters": {
        "type": "object",
        "properties": {
            "mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "business_term": {
                            "type": "string",
                            "description": "业务术语（中文或英文）",
                        },
                        "code_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "可能对应的代码层术语（英文、驼峰命名、下划线命名），至少3个",
                        },
                    },
                    "required": ["business_term", "code_terms"],
                },
                "description": "每个业务术语对应的代码搜索词列表",
            }
        },
        "required": ["mappings"],
    },
}

KEYWORD_MAPPING_PROMPT = """请将以下业务术语映射为可能的代码层搜索词。

业务术语列表：
{terms}

对于每个业务术语，请提供至少3个可能的代码层术语，包括：
1. 英文翻译或同义词
2. 驼峰命名形式（camelCase）
3. 下划线命名形式（snake_case）
4. 常见缩写

例如：
- "双因素认证" → ["two_factor", "2fa", "mfa", "auth", "totp", "otp"]
- "用户登录" → ["login", "signin", "auth", "user_auth"]
- "IDE集成" → ["extension", "plugin", "vscode", "ide", "language_server"]

请输出JSON格式的映射列表。"""


# ============== Smart Module Query Schemas ==============

QUERY_MODULES_SCHEMA = {
    "name": "query_relevant_modules",
    "description": "根据需求内容，主动查询项目中相关的模块",
    "parameters": {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string", "description": "模块名称或路径"},
                        "query_reason": {"type": "string", "description": "为什么需要分析这个模块"},
                    },
                    "required": ["module_name", "query_reason"],
                },
                "description": "需要详细分析的模块列表（最多10个）",
            },
            "reasoning": {
                "type": "string",
                "description": "整体分析推理过程",
            },
        },
        "required": ["queries"],
    },
}

QUERY_MODULES_PROMPT = """你是一位架构师，请分析需求并主动查询相关模块。

## 项目画像
{project_profile}

## 已知模块及其职责
{modules_overview}

## 当前需求
- 摘要: {summary}
- 核心术语: {terms}

## 任务
1. 分析需求的核心功能点
2. 结合项目架构和模块职责，推断可能涉及的模块
3. 考虑以下维度：
   - 直接功能相关性（模块直接实现需求功能）
   - 数据流相关性（模块处理相关数据）
   - 接口依赖相关性（模块依赖或提供相关接口）
   - 配置/基础设施相关性（涉及配置、中间件等）

请输出需要详细分析的模块列表，并说明每个模块的查询理由。
"""

ANALYZE_MODULE_RELEVANCE_SCHEMA = {
    "name": "analyze_module_relevance",
    "description": "深度分析模块与需求的关联，输出具体的代码影响",
    "parameters": {
        "type": "object",
        "properties": {
            "modules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "涉及的关键函数/类",
                        },
                        "relevance": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "关联程度",
                        },
                        "relevance_reason": {"type": "string", "description": "关联理由"},
                        "suggested_changes": {"type": "string", "description": "建议的变更内容"},
                    },
                    "required": ["path", "relevance", "relevance_reason"],
                },
            },
            "overall_assessment": {
                "type": "object",
                "properties": {
                    "impact_scope": {"type": "string", "description": "整体影响范围描述"},
                    "key_integration_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键集成点",
                    },
                },
            },
        },
        "required": ["modules"],
    },
}

ANALYZE_MODULE_RELEVANCE_PROMPT = """你是一位资深开发者，请深度分析模块与需求的具体关联。

## 需求内容
{requirement_text}

## 需求理解
- 摘要: {summary}
- 核心术语: {terms}

## 候选模块详情
{modules_detail}

## 任务
对于每个模块：
1. 分析其代码摘要与需求的具体关联点
2. 识别需要修改或新增的函数/类
3. 描述建议的变更内容
4. 评估影响程度（high/medium/low）

请输出详细的模块分析结果。
"""


# ============== Helper Functions ==============


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


# ============== Step Functions ==============


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

    # === 在此处添加智能模块匹配 ===
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
            logger.warning("Smart module matching failed, falling back: %s", e)

    # 如果智能匹配未成功，使用原有逻辑
    if not analysis.impact_modules:
        keywords = context.expanded_keywords if context.expanded_keywords else (
            context.understanding.keywords if context.understanding else []
        )
        if code_graph and keywords:
            matched_files = code_graph.find_symbols(keywords)
            analysis.impact_modules = [
                {"path": f.path, "symbols": [s.name for s in f.symbols[:5]]}
                for f in matched_files[:10]
            ]
    # ==================================

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


# ============== Project Profile Building ==============


async def step_build_project_profile(
    code_graph,
    llm_client,
    memory_manager,
    repo_path: str = ".",
) -> dict:
    """构建项目画像并存入记忆"""
    if not code_graph or not code_graph.files:
        logger.warning("No code files to build project profile")
        return {}

    try:
        file_stats = _build_file_stats(code_graph)
        directory_structure = _build_directory_structure(code_graph)
        key_files = _build_key_files(code_graph)
        dependencies_content = _extract_dependencies(repo_path)

        messages = [
            {
                "role": "user",
                "content": PROJECT_PROFILE_PROMPT.format(
                    file_stats=file_stats,
                    directory_structure=directory_structure,
                    key_files=key_files,
                    dependencies_content=dependencies_content,
                ),
            },
        ]

        result = await _call_llm_structured(
            llm_client, messages, PROJECT_PROFILE_SCHEMA, max_tokens=2048
        )

        if result:
            profile = {
                "name": Path(repo_path).name,
                "description": result.get("description", ""),
                "architecture_style": result.get("architecture_style", ""),
                "tech_stack": result.get("tech_stack", {}),
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "source": "llm_inferred",
            }

            memory_manager.update_project_profile(profile)
            logger.info("Project profile updated: %s", profile.get("description", ""))

            for module in result.get("modules", []):
                if isinstance(module, dict) and module.get("name"):
                    module_name = module.get("name", "")
                    memory_manager.add_module(
                        name=module_name,
                        responsibility=module.get("responsibility", ""),
                        key_classes=module.get("key_classes", []),
                        dependencies=module.get("dependencies", []),
                        path=_infer_module_path(module_name, code_graph),
                    )

            memory_manager.save()
            logger.info("Project profile saved to memory")

            return {
                "project_profile": profile,
                "modules": result.get("modules", []),
            }

    except Exception as e:
        logger.warning("Failed to build project profile: %s", e)

    return {}


def _build_file_stats(code_graph) -> str:
    """构建文件统计信息"""
    total_files = len(code_graph.files)
    total_symbols = sum(len(f.symbols) for f in code_graph.files)

    extensions = Counter(Path(f.path).suffix for f in code_graph.files if Path(f.path).suffix)
    top_extensions = extensions.most_common(5)

    lines = [
        f"- 总文件数: {total_files}",
        f"- 总符号数: {total_symbols}",
        f"- 文件类型分布: {', '.join(f'{ext}({count})' for ext, count in top_extensions)}",
    ]
    return "\n".join(lines)


def _build_directory_structure(code_graph) -> str:
    """构建目录结构"""
    dirs = set()
    for f in code_graph.files:
        parts = Path(f.path).parts
        for i in range(1, min(len(parts), 4)):
            dirs.add("/".join(parts[:i]))

    sorted_dirs = sorted(dirs)[:20]
    return "\n".join(f"- {d}" for d in sorted_dirs)


def _build_key_files(code_graph) -> str:
    """构建核心文件列表"""
    files_with_symbols = [
        (f.path, len(f.symbols), [s.name for s in f.symbols[:5]])
        for f in code_graph.files
        if f.symbols
    ]
    files_with_symbols.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for path, count, symbols in files_with_symbols[:10]:
        lines.append(f"- {path} ({count} symbols: {', '.join(symbols)})")

    return "\n".join(lines)


def _extract_dependencies(repo_path: str) -> str:
    """提取依赖文件内容"""
    repo = Path(repo_path)
    dep_files = [
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
    ]

    contents = []
    for dep_file in dep_files:
        path = repo / dep_file
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")[:1000]
                contents.append(f"=== {dep_file} ===\n{content}\n")
            except Exception:
                pass

    if not contents:
        contents.append("未找到依赖文件")

    return "\n".join(contents)


def _infer_module_path(module_name: str, code_graph) -> str:
    """推断模块路径"""
    for f in code_graph.files:
        if module_name.lower() in f.path.lower():
            return str(Path(f.path).parent)
    return ""


def _get_module_from_memory(memory_data: dict, module_name: str) -> dict | None:
    """从记忆中获取指定模块信息

    Args:
        memory_data: 项目记忆数据
        module_name: 模块名称（支持模糊匹配）

    Returns:
        模块字典的副本，或 None
    """
    for module in memory_data.get("modules", []):
        if module.get("name") == module_name or module_name.lower() in module.get("name", "").lower():
            return module.copy()
    return None


async def _query_relevant_modules_from_memory(
    understanding: RequirementUnderstanding,
    memory_data: dict | None,
    llm_client,
) -> list[dict]:
    """从记忆中查询相关模块

    Args:
        understanding: 需求理解
        memory_data: 项目记忆数据
        llm_client: LLM 客户端

    Returns:
        相关模块列表，每个模块包含 query_reason
    """
    if not memory_data or not memory_data.get("modules"):
        logger.info("No memory data or modules available for query")
        return []

    modules_overview = "\n".join(
        f"- {m.get('name', 'unknown')}: {m.get('responsibility', '')}"
        for m in memory_data.get("modules", [])[:20]
    )

    profile = memory_data.get("project_profile", {})
    project_profile = json.dumps(
        {
            "description": profile.get("description", ""),
            "architecture_style": profile.get("architecture_style", ""),
            "tech_stack": profile.get("tech_stack", {}),
        },
        ensure_ascii=False,
        indent=2,
    )

    terms_str = ", ".join(t.term for t in understanding.terms[:5]) if understanding.terms else ""

    messages = [
        {
            "role": "user",
            "content": QUERY_MODULES_PROMPT.format(
                project_profile=project_profile,
                modules_overview=modules_overview,
                summary=understanding.summary,
                terms=terms_str,
            ),
        },
    ]

    try:
        result = await _call_llm_structured(
            llm_client, messages, QUERY_MODULES_SCHEMA, max_tokens=1024
        )

        queries = result.get("queries", [])
        modules_with_reason = []

        for q in queries:
            module_name = q.get("module_name", "")
            query_reason = q.get("query_reason", "")

            module_info = _get_module_from_memory(memory_data, module_name)
            if module_info:
                module_info["query_reason"] = query_reason
                modules_with_reason.append(module_info)

        logger.info("Queried %d relevant modules from memory", len(modules_with_reason))
        return modules_with_reason

    except Exception as e:
        logger.warning("Failed to query modules from memory: %s", e)
        return []


async def _analyze_module_relevance(
    understanding: RequirementUnderstanding,
    candidate_modules: list[dict],
    llm_client,
) -> list[dict]:
    """分析模块与需求的关联程度

    Args:
        understanding: 需求理解
        candidate_modules: 候选模块列表
        llm_client: LLM 客户端

    Returns:
        分析后的模块列表，包含 path, symbols, relevance, relevance_reason, suggested_changes
    """
    if not candidate_modules:
        logger.info("No candidate modules to analyze")
        return []

    modules_detail = []
    for m in candidate_modules[:10]:
        detail = {
            "name": m.get("name", ""),
            "responsibility": m.get("responsibility", ""),
            "key_classes": m.get("key_classes", []),
            "code_summary": m.get("code_summary", ""),
            "query_reason": m.get("query_reason", ""),
        }
        modules_detail.append(detail)

    modules_detail_str = json.dumps(modules_detail, ensure_ascii=False, indent=2)

    terms_str = ", ".join(t.term for t in understanding.terms[:5]) if understanding.terms else ""

    messages = [
        {
            "role": "user",
            "content": ANALYZE_MODULE_RELEVANCE_PROMPT.format(
                requirement_text=understanding.raw_text[:1000] if understanding.raw_text else "",
                summary=understanding.summary,
                terms=terms_str,
                modules_detail=modules_detail_str,
            ),
        },
    ]

    try:
        result = await _call_llm_structured(
            llm_client, messages, ANALYZE_MODULE_RELEVANCE_SCHEMA, max_tokens=2048
        )

        analyzed_modules = []
        for m in result.get("modules", []):
            analyzed = {
                "path": m.get("path", ""),
                "symbols": m.get("symbols", []),
                "relevance": m.get("relevance", "low"),
                "relevance_reason": m.get("relevance_reason", ""),
                "suggested_changes": m.get("suggested_changes", ""),
            }
            analyzed_modules.append(analyzed)

        logger.info("Analyzed %d modules for relevance", len(analyzed_modules))
        return analyzed_modules

    except Exception as e:
        logger.warning("Failed to analyze module relevance: %s", e)
        return []


async def _smart_module_matching(
    understanding: RequirementUnderstanding,
    memory_data: dict | None,
    code_graph,
    llm_client,
) -> list[dict]:
    """智能模块匹配：LLM 主动查询 + 深度分析

    Args:
        understanding: 需求理解
        memory_data: 项目记忆数据
        code_graph: 代码图（暂不使用，保留接口）
        llm_client: LLM 客户端

    Returns:
        匹配的模块列表，包含详细信息
    """
    relevant_modules = await _query_relevant_modules_from_memory(
        understanding, memory_data, llm_client
    )

    if not relevant_modules:
        logger.info("No relevant modules found from memory")
        return []

    analyzed_modules = await _analyze_module_relevance(
        understanding, relevant_modules, llm_client
    )

    return analyzed_modules
