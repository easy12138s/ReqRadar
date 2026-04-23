from reqradar.agent.prompts._legacy import (
    SYSTEM_PROMPT,
    EXTRACT_PROMPT,
    RETRIEVE_PROMPT,
    ANALYZE_PROMPT,
    GENERATE_PROMPT,
    PROJECT_PROFILE_PROMPT,
    KEYWORD_MAPPING_PROMPT,
    QUERY_MODULES_PROMPT,
    ANALYZE_MODULE_RELEVANCE_PROMPT,
    GENERATE_BATCH_MODULE_SUMMARIES_PROMPT,
)
from reqradar.agent.prompts.analysis_phase import build_analysis_system_prompt, build_analysis_user_prompt, build_termination_prompt
from reqradar.agent.prompts.report_phase import build_report_generation_prompt, build_dimension_section_prompt
