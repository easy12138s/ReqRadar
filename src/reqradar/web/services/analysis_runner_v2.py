import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import markdown
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.evidence import EvidenceCollector
from reqradar.agent.dimension import DimensionTracker
from reqradar.agent.llm_utils import _call_llm_structured, _parse_json_response
from reqradar.agent.prompts.analysis_phase import build_analysis_system_prompt, build_analysis_user_prompt, build_termination_prompt
from reqradar.agent.prompts.report_phase import build_report_generation_prompt
from reqradar.agent.schemas import ANALYZE_SCHEMA
from reqradar.agent.tools import ToolRegistry
from reqradar.agent.tools.security import PathSandbox, SensitiveFileFilter, check_tool_permissions
from reqradar.core.report import ReportRenderer
from reqradar.infrastructure.config import Config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.infrastructure.template_loader import TemplateLoader
from reqradar.modules.memory_manager import AnalysisMemoryManager
from reqradar.modules.synonym_resolver import SynonymResolver
from reqradar.web.models import AnalysisTask, Report, Project
from reqradar.web.services.project_store import project_store
from reqradar.web.websocket import manager as ws_manager

logger = logging.getLogger("reqradar.web.services.analysis_runner_v2")

REPORT_DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "requirement_title": {"type": "string"},
        "requirement_understanding": {"type": "string"},
        "executive_summary": {"type": "string"},
        "technical_summary": {"type": "string"},
        "impact_narrative": {"type": "string"},
        "risk_narrative": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["critical", "high", "medium", "low", "unknown"]},
        "decision_highlights": {"type": "array", "items": {"type": "string"}},
        "impact_domains": {"type": "array"},
        "impact_modules": {"type": "array"},
        "change_assessment": {"type": "array"},
        "risks": {"type": "array"},
        "decision_summary": {"type": "object"},
        "evidence_items": {"type": "array"},
        "verification_points": {"type": "array", "items": {"type": "string"}},
        "implementation_suggestion": {"type": "string"},
        "priority": {"type": "string"},
        "priority_reason": {"type": "string"},
        "terms": {"type": "array"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "structured_constraints": {"type": "array"},
        "contributors": {"type": "array"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["requirement_title", "risk_level"],
}


class AnalysisRunnerV2:
    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[int, asyncio.Task] = {}

    def submit(self, task_id: int, project: Project, config: Config) -> asyncio.Task:
        if task_id in self._active_tasks and not self._active_tasks[task_id].done():
            raise ValueError(f"Task {task_id} is already running")

        task = asyncio.create_task(self._run_analysis(task_id, project, config))

        def _on_done(t):
            self._active_tasks.pop(task_id, None)

        task.add_done_callback(_on_done)
        self._active_tasks[task_id] = task
        return task

    async def _run_analysis(self, task_id: int, project: Project, config: Config):
        async with self._semaphore:
            import reqradar.web.dependencies as dep_module

            async with dep_module.async_session_factory() as db:
                try:
                    await self._execute_agent(task_id, project, config, db)
                except asyncio.CancelledError:
                    logger.info("Agent analysis task %d cancelled", task_id)
                    raise
                except Exception:
                    logger.exception("Agent analysis task %d failed", task_id)

    async def _execute_agent(self, task_id: int, project: Project, config: Config, db: AsyncSession):
        from reqradar.modules.llm_client import create_llm_client
        from reqradar.modules.memory import MemoryManager
        from reqradar.modules.git_analyzer import GitAnalyzer
        from reqradar.agent.tools import (
            SearchCodeTool,
            ReadFileTool,
            ReadModuleSummaryTool,
            ListModulesTool,
            SearchRequirementsTool,
            GetDependenciesTool,
            GetContributorsTool,
            GetProjectProfileTool,
            GetTerminologyTool,
        )
        from reqradar.agent.tool_use_loop import run_tool_use_loop

        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        await ws_manager.broadcast(task_id, {"type": "analysis_started", "task_id": task_id})

        try:
            depth = task.depth if hasattr(task, "depth") and task.depth else "standard"
            agent = AnalysisAgent(
                requirement_text=task.requirement_text,
                project_id=project.id,
                user_id=task.user_id,
                depth=depth,
            )
            agent.state = AgentState.ANALYZING

            memory_manager = MemoryManager(
                storage_path=str(Path(project.repo_path) / config.memory.storage_path)
                if project.repo_path else config.memory.storage_path
            )
            memory_data = memory_manager.load() if config.memory.enabled else None

            analysis_memory = AnalysisMemoryManager(
                project_id=project.id,
                user_id=task.user_id,
                project_storage_path=str(Path(project.repo_path) / config.memory.project_storage_path)
                if project.repo_path else config.memory.project_storage_path,
                user_storage_path=str(Path(project.repo_path) / config.memory.user_storage_path)
                if project.repo_path else config.memory.user_storage_path,
                memory_enabled=config.memory.enabled,
            )

            agent.project_memory_text = analysis_memory.get_project_profile_text()
            agent.user_memory_text = analysis_memory.get_user_memory_text()

            cm = ConfigManager(db, config)
            provider = await cm.get_str("llm.provider", user_id=task.user_id, project_id=project.id, default=config.llm.provider)
            llm_model = await cm.get_str("llm.model", user_id=task.user_id, project_id=project.id, default=config.llm.model)
            llm_api_key = await cm.get_str("llm.api_key", user_id=task.user_id, project_id=project.id, default=config.llm.api_key or "")
            llm_base_url = await cm.get_str("llm.base_url", user_id=task.user_id, project_id=project.id, default=config.llm.base_url or "https://api.openai.com/v1")

            llm_kwargs = {
                "openai": {
                    "api_key": llm_api_key,
                    "model": llm_model,
                    "base_url": llm_base_url,
                    "timeout": config.llm.timeout,
                    "max_retries": config.llm.max_retries,
                    "embedding_model": config.llm.embedding_model,
                    "embedding_dim": config.llm.embedding_dim,
                },
                "ollama": {
                    "model": llm_model,
                    "host": config.llm.host or "http://localhost:11434",
                    "embedding_dim": config.llm.embedding_dim,
                },
            }
            llm_client = create_llm_client(provider, **llm_kwargs.get(provider, {}))

            index_path = project.index_path or str(Path(project.repo_path) / ".reqradar" / "index")
            repo_path = project.repo_path or "."

            code_graph = await project_store.get_code_graph(project.id, index_path)
            vector_store = await project_store.get_vector_store(project.id, index_path)

            path_sandbox = PathSandbox(allowed_root=repo_path)
            sensitive_filter = SensitiveFileFilter()
            user_permissions = {"read:code", "read:memory", "read:history", "read:git", "write:report", "read:user_memory"}
            tool_registry = ToolRegistry(user_permissions=user_permissions)

            if code_graph:
                tool_registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path))
                tool_registry.register(GetDependenciesTool(code_graph=code_graph, memory_data=memory_data))

            tool_registry.register(ReadFileTool(repo_path=repo_path))
            tool_registry.register(ReadModuleSummaryTool(memory_data=memory_data))
            tool_registry.register(ListModulesTool(memory_data=memory_data))
            tool_registry.register(GetProjectProfileTool(memory_data=memory_data))
            tool_registry.register(GetTerminologyTool(memory_data=memory_data))

            if vector_store:
                tool_registry.register(SearchRequirementsTool(vector_store=vector_store))

            try:
                git_analyzer = None
                if project.repo_path and Path(project.repo_path, ".git").exists():
                    git_analyzer = GitAnalyzer(repo_path=Path(project.repo_path), lookback_months=config.git.lookback_months)
                if git_analyzer:
                    tool_registry.register(GetContributorsTool(git_analyzer=git_analyzer))
            except Exception:
                logger.warning("Failed to init GitAnalyzer for project %d", project.id)

            template_loader = TemplateLoader()
            template_def = None
            template_id = config.reporting.default_template_id if hasattr(config, "reporting") else None
            if template_id:
                from reqradar.web.models import ReportTemplate
                tmpl_result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
                tmpl_obj = tmpl_result.scalar_one_or_none()
                if tmpl_obj:
                    template_def = template_loader.load_from_db_data(tmpl_obj.definition, tmpl_obj.render_template)

            if template_def is None:
                try:
                    template_def = template_loader.load_definition(template_loader.get_default_template_path())
                except Exception:
                    template_def = None

            section_descriptions = None
            if template_def:
                section_descriptions = [
                    {"id": s.id, "title": s.title, "description": s.description, "requirements": s.requirements, "dimensions": s.dimensions, "required": s.required}
                    for s in template_def.sections
                ]

            system_prompt = build_analysis_system_prompt(
                project_memory=agent.project_memory_text,
                user_memory=agent.user_memory_text,
                historical_context=agent.historical_context,
                dimension_status=agent.dimension_tracker.status_summary(),
                template_sections=section_descriptions,
            )

            tool_names = tool_registry.list_names()
            analysis_tools = tool_names

            await ws_manager.broadcast(task_id, {
                "type": "agent_thinking",
                "task_id": task_id,
                "message": "开始分析需求...",
            })

            while not agent.should_terminate():
                user_prompt = build_analysis_user_prompt(
                    requirement_text=agent.requirement_text,
                    agent_context=agent.get_context_text() + "\n\n" + agent.get_weak_dimensions_text(),
                )

                tool_result_data = await run_tool_use_loop(
                    llm_client,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tools=analysis_tools,
                    tool_registry=tool_registry,
                    output_schema=ANALYZE_SCHEMA,
                    max_rounds=min(agent.max_steps - agent.step_count, 3),
                    max_total_tokens=config.analysis.tool_use_max_tokens if hasattr(config.analysis, "tool_use_max_tokens") else 8000,
                )

                if tool_result_data:
                    self._update_agent_from_tool_result(agent, tool_result_data)

                agent.step_count += 1

                await ws_manager.broadcast(task_id, {
                    "type": "dimension_progress",
                    "task_id": task_id,
                    "step": agent.step_count,
                    "max_steps": agent.max_steps,
                    "dimensions": agent.dimension_tracker.status_summary(),
                    "evidence_count": len(agent.evidence_collector.evidences),
                })

                await asyncio.sleep(0)

            agent.state = AgentState.GENERATING
            report_data = await self._generate_report(agent, llm_client, system_prompt, section_descriptions, config)
            agent.final_report_data = report_data
            agent.state = AgentState.COMPLETED

            renderer = ReportRenderer(config, template_definition=template_def)
            report_data.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            report_data.setdefault("requirement_path", agent.requirement_text[:50])
            report_data.setdefault("impact_scope", "")
            report_data.setdefault("content_confidence", "N/A")
            report_data.setdefault("process_completion", "N/A")
            report_data.setdefault("content_completeness", "N/A")
            report_data.setdefault("evidence_support", "N/A")
            report_data.setdefault("risk_badge", report_data.get("risk_level", "unknown"))

            try:
                report_markdown = renderer.template.render(**report_data)
            except Exception:
                try:
                    from jinja2 import Template as JinjaTemplate
                    from reqradar.core.report import _INLINE_FALLBACK_TEMPLATE
                    fallback_tmpl = JinjaTemplate(_INLINE_FALLBACK_TEMPLATE)
                    report_markdown = fallback_tmpl.render(**report_data)
                except Exception:
                    report_markdown = json.dumps(report_data, ensure_ascii=False, indent=2, default=str)

            report_html = markdown.markdown(report_markdown, extensions=["extra", "codehilite", "toc", "tables"])
            risk_level = report_data.get("risk_level", "unknown")

            task.context_json = json.dumps(agent.get_context_snapshot(), ensure_ascii=False, default=str)
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

            db.add(Report(
                task_id=task_id,
                content_markdown=report_markdown,
                content_html=report_html,
            ))

            await db.commit()

            await ws_manager.broadcast(task_id, {
                "type": "analysis_complete",
                "task_id": task_id,
                "risk_level": risk_level,
            })

        except asyncio.CancelledError:
            task.status = "cancelled"
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await ws_manager.broadcast(task_id, {"type": "analysis_cancelled", "task_id": task_id})
            raise

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)[:2000]
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await ws_manager.broadcast(task_id, {
                "type": "analysis_failed",
                "task_id": task_id,
                "error": str(e)[:500],
            })

    def _update_agent_from_tool_result(self, agent: AnalysisAgent, data: dict) -> None:
        if data.get("terms"):
            for t in data.get("terms", []):
                if isinstance(t, dict) and t.get("term"):
                    dimensions = ["understanding"]
                    agent.record_evidence(
                        type="term",
                        source=f"llm_extract:{t['term']}",
                        content=f"{t['term']}: {t.get('definition', '')}",
                        confidence="medium",
                        dimensions=dimensions,
                    )

        if data.get("impact_modules"):
            for m in data.get("impact_modules", []):
                if isinstance(m, dict):
                    agent.record_evidence(
                        type="code",
                        source=m.get("path", "unknown"),
                        content=m.get("relevance_reason", "Unknown relevance"),
                        confidence=m.get("relevance", "low"),
                        dimensions=["impact", "change"],
                    )
                    agent.dimension_tracker.mark_in_progress("impact")

        if data.get("risks"):
            for r in data.get("risks", []):
                if isinstance(r, dict):
                    confidence_map = {"high": "high", "medium": "medium", "low": "low"}
                    agent.record_evidence(
                        type="history",
                        source=f"risk:{r.get('description', '')[:50]}",
                        content=r.get("description", ""),
                        confidence=confidence_map.get(r.get("severity", ""), "medium"),
                        dimensions=["risk"],
                    )
                    agent.dimension_tracker.mark_in_progress("risk")

    async def _generate_report(self, agent: AnalysisAgent, llm_client, system_prompt: str, section_descriptions, config: Config) -> dict:
        termination_prompt = build_termination_prompt()
        evidence_text = agent.evidence_collector.get_all_evidence_text()

        report_prompt = build_report_generation_prompt(
            requirement_text=agent.requirement_text,
            evidence_text=evidence_text,
            dimension_status=agent.dimension_tracker.status_summary(),
            template_sections=section_descriptions,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": report_prompt},
            {"role": "assistant", "content": termination_prompt},
        ]

        try:
            result = await _call_llm_structured(llm_client, messages, REPORT_DATA_SCHEMA)
            if result:
                result.setdefault("requirement_title", agent.requirement_text[:100])
                result.setdefault("warnings", [])
                return result
        except Exception as e:
            logger.warning("Report generation failed, using fallback: %s", e)

        return _build_fallback_report_data(agent)

    def cancel(self, task_id: int):
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()


def _build_fallback_report_data(agent: AnalysisAgent) -> dict:
    return {
        "requirement_title": agent.requirement_text[:100],
        "requirement_understanding": f"需求理解: {agent.requirement_text[:200]}",
        "executive_summary": "分析完成，但有部分信息不完整。",
        "technical_summary": "",
        "impact_narrative": "",
        "risk_narrative": "",
        "risk_level": "unknown",
        "decision_highlights": [],
        "impact_domains": [],
        "impact_modules": [],
        "change_assessment": [],
        "risks": [],
        "decision_summary": {"summary": "", "decisions": [], "open_questions": [], "follow_ups": []},
        "evidence_items": [{"kind": ev.type, "source": ev.source, "summary": ev.content, "confidence": ev.confidence} for ev in agent.evidence_collector.evidences],
        "verification_points": [],
        "implementation_suggestion": "",
        "priority": "medium",
        "priority_reason": "",
        "terms": [],
        "keywords": [],
        "constraints": [],
        "structured_constraints": [],
        "contributors": [],
        "warnings": ["Agent analysis completed with partial data due to insufficient evidence."],
    }


def build_report_data_from_agent(agent: AnalysisAgent, llm_result: dict) -> dict:
    report_data = llm_result.copy() if llm_result else {}
    report_data.setdefault("requirement_title", agent.requirement_text[:100])
    report_data.setdefault("risk_level", "unknown")
    report_data.setdefault("warnings", [])
    evidence_items = [
        {"kind": ev.type, "source": ev.source, "summary": ev.content, "confidence": ev.confidence}
        for ev in agent.evidence_collector.evidences
    ]
    report_data.setdefault("evidence_items", evidence_items)
    return report_data


runner_v2 = AnalysisRunnerV2()
