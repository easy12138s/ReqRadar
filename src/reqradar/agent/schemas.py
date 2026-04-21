"""Agent 层 - LLM function calling schemas"""

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
            "impact_narrative": {
                "type": "string",
                "description": "影响范围的自然语言描述（100-150字，描述涉及的技术组件和数据流向）",
            },
            "risk_narrative": {
                "type": "string",
                "description": "风险分析的自然语言描述（150-200字，主要风险和缓解思路）",
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

GENERATE_BATCH_MODULE_SUMMARIES_SCHEMA = {
    "name": "generate_batch_module_summaries",
    "description": "批量生成多个模块的代码摘要",
    "parameters": {
        "type": "object",
        "properties": {
            "summaries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string", "description": "模块名称"},
                        "summary": {"type": "string", "description": "模块功能摘要（100-200字）"},
                    },
                    "required": ["module_name", "summary"],
                },
                "description": "所有模块的摘要列表",
            },
        },
        "required": ["summaries"],
    },
}
