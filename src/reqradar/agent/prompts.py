"""Agent 层 - LLM prompt 模板"""

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

GENERATE_BATCH_MODULE_SUMMARIES_PROMPT = """请为以下所有模块生成代码摘要。

## 模块列表
{modules_info}

## 任务
为每个模块生成一段 100-200 字的功能摘要，描述：
1. 模块的核心职责
2. 主要功能和关键函数
3. 在项目中的作用

请输出 JSON 格式的摘要列表。
"""
