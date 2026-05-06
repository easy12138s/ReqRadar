import logging

from reqradar.agent.analysis_agent import AnalysisAgent
from reqradar.agent.llm_utils import _call_llm_structured
from reqradar.agent.prompts.memory_evolution import (
    MEMORY_EVOLUTION_SYSTEM_PROMPT,
    build_memory_evolution_user_prompt,
)
from reqradar.agent.schemas import MEMORY_EVOLUTION_SCHEMA
from reqradar.modules.project_memory import ProjectMemory

logger = logging.getLogger("reqradar.agent.memory_evolution")


def extract_candidates_from_analysis(agent: AnalysisAgent) -> dict:
    report = agent.final_report_data or {}

    terms_candidates = []
    for t in report.get("terms", []):
        if isinstance(t, dict) and t.get("term") and t.get("definition"):
            terms_candidates.append(
                {
                    "term": t["term"],
                    "definition": t["definition"],
                    "domain": t.get("domain", ""),
                }
            )

    modules_candidates = []
    for m in report.get("impact_modules", []):
        if isinstance(m, dict):
            relevance = m.get("relevance", "low")
            if relevance in ("high", "medium"):
                modules_candidates.append(
                    {
                        "name": m.get("path", m.get("module", "")),
                        "responsibility": m.get("relevance_reason", ""),
                        "key_classes": m.get("symbols", []),
                    }
                )

    constraints_candidates = []
    for c in report.get("structured_constraints", []):
        if isinstance(c, dict) and c.get("description"):
            constraints_candidates.append(
                {
                    "description": c["description"],
                    "type": c.get("constraint_type", "other"),
                }
            )

    tech_stack = {}
    domains = report.get("impact_domains", [])
    if domains:
        tech_stack["frameworks"] = [
            d.get("domain", "") for d in domains if isinstance(d, dict) and d.get("domain")
        ]

    overview = report.get("technical_summary", "")

    return {
        "terms": terms_candidates,
        "modules": modules_candidates,
        "constraints": constraints_candidates,
        "tech_stack_additions": tech_stack,
        "overview_insights": overview,
    }


async def evolve_memory_after_analysis(
    agent: AnalysisAgent,
    project_memory: ProjectMemory | None,
    llm_client,
) -> None:
    if project_memory is None:
        logger.debug("No ProjectMemory available, skipping memory evolution")
        return

    candidates = extract_candidates_from_analysis(agent)

    has_any = any(
        [
            candidates["terms"],
            candidates["modules"],
            candidates["constraints"],
            candidates["tech_stack_additions"],
            bool(candidates["overview_insights"]),
        ]
    )
    if not has_any:
        logger.debug("No candidates extracted, skipping memory evolution")
        return

    user_prompt = build_memory_evolution_user_prompt(
        existing_memory=project_memory.to_text(),
        new_terms=candidates["terms"],
        new_modules=candidates["modules"],
        new_constraints=candidates["constraints"],
        tech_stack_additions=candidates["tech_stack_additions"],
        overview_insights=candidates["overview_insights"],
    )

    try:
        result = await _call_llm_structured(
            llm_client,
            messages=[
                {"role": "system", "content": MEMORY_EVOLUTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            schema=MEMORY_EVOLUTION_SCHEMA,
        )
    except Exception as e:
        logger.warning("Memory evolution LLM call failed: %s", e)
        return

    if not result:
        return

    for op in result.get("operations", []):
        try:
            _apply_operation(project_memory, op)
        except Exception as e:
            logger.warning("Failed to apply memory operation %s: %s", op.get("target", ""), e)

    changelog_entry = result.get("changelog_entry", "分析后记忆更新")
    project_memory._save_changelog(changelog_entry)
    project_memory.save()

    logger.info(
        "Memory evolution complete: %d operations, changelog: %s",
        len(result.get("operations", [])),
        changelog_entry,
    )


def _apply_operation(memory: ProjectMemory, op: dict) -> None:
    target = op.get("target", "")
    action = op.get("action", "")
    data = op.get("data", {})
    if action == "skip":
        return

    if target == "terms":
        term = data.get("term", "")
        definition = data.get("definition", "")
        domain = data.get("domain", "")
        if term and len(definition) >= 10:
            memory.add_term(term, definition, domain)
    elif target == "modules":
        name = data.get("name", "")
        if name:
            memory.add_module(
                name,
                data.get("responsibility", ""),
                data.get("key_classes", []),
            )
    elif target == "constraints":
        desc = data.get("description", "")
        if desc:
            memory.batch_add_constraints(
                [
                    {
                        "description": desc,
                        "type": data.get("type", "other"),
                    }
                ]
            )
    elif target == "tech_stack":
        for cat, items in data.items():
            if isinstance(items, list) and items:
                memory.add_tech_stack(cat, items)
    elif target == "overview":
        overview = data.get("overview", "")
        if overview:
            memory.update_overview(overview)
