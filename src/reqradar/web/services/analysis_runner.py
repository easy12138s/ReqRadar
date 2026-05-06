import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import markdown
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.agent.analysis_agent import AnalysisAgent, AgentState
from reqradar.agent.runner import run_react_analysis
from reqradar.agent.tools import ToolRegistry
from reqradar.core.report import ReportRenderer
from reqradar.infrastructure.config import Config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.infrastructure.template_loader import TemplateLoader
from reqradar.modules.memory_manager import AnalysisMemoryManager
from reqradar.web.models import AnalysisTask, Report, Project
from reqradar.web.enums import TaskStatus
from reqradar.web.services.project_file_service import ProjectFileService
from reqradar.web.services.project_store import project_store
from reqradar.web.websocket import manager as ws_manager

logger = logging.getLogger("reqradar.web.services.analysis_runner")

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


class AnalysisRunner:
    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[int, asyncio.Task] = {}
        self.session_factory = None

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
            if self.session_factory is None:
                import reqradar.web.dependencies as dep_module

                factory = dep_module.async_session_factory
            else:
                factory = self.session_factory

            async with factory() as db:
                try:
                    await self._execute_agent(task_id, project, config, db)
                except asyncio.CancelledError:
                    logger.info("Agent analysis task %d cancelled", task_id)
                    raise
                except Exception:
                    logger.exception("Agent analysis task %d failed", task_id)

    async def _init_agent(
        self, task: AnalysisTask, project: Project, config: Config, db: AsyncSession
    ) -> tuple[AnalysisAgent, AnalysisMemoryManager, ConfigManager, object | None]:
        from reqradar.modules.memory import MemoryManager

        depth = task.depth if hasattr(task, "depth") and task.depth else "standard"
        agent = AnalysisAgent(
            requirement_text=task.requirement_text,
            project_id=project.id,
            user_id=task.user_id,
            depth=depth,
        )
        agent.state = AgentState.ANALYZING

        file_svc = ProjectFileService(config.web)
        memory_path = str(file_svc.get_memory_path(project.name))

        memory_manager = MemoryManager(storage_path=memory_path)
        memory_data = memory_manager.load() if config.memory.enabled else None

        analysis_memory = AnalysisMemoryManager(
            project_id=project.id,
            user_id=task.user_id,
            project_storage_path=memory_path,
            user_storage_path=memory_path,
            memory_enabled=config.memory.enabled,
        )

        agent.project_memory_text = analysis_memory.get_project_profile_text()
        agent.user_memory_text = analysis_memory.get_user_memory_text()

        cm = ConfigManager(db, config)

        return agent, analysis_memory, cm, memory_data

    async def _init_tools(
        self,
        agent: AnalysisAgent,
        task: AnalysisTask,
        project: Project,
        config: Config,
        db: AsyncSession,
        cm: ConfigManager,
        memory_data,
    ) -> tuple[ToolRegistry, object]:
        from reqradar.modules.llm_client import create_llm_client
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
        from reqradar.agent.tools.security import PathSandbox, SensitiveFileFilter

        provider = await cm.get_str(
            "llm.provider", user_id=task.user_id, project_id=project.id, default=config.llm.provider
        )
        llm_model = await cm.get_str(
            "llm.model", user_id=task.user_id, project_id=project.id, default=config.llm.model
        )
        llm_api_key = await cm.get_str(
            "llm.api_key",
            user_id=task.user_id,
            project_id=project.id,
            default=config.llm.api_key or "",
        )
        llm_base_url = await cm.get_str(
            "llm.base_url",
            user_id=task.user_id,
            project_id=project.id,
            default=config.llm.base_url or "https://api.openai.com/v1",
        )

        llm_kwargs = {
            "openai": {
                "api_key": llm_api_key,
                "model": llm_model,
                "base_url": llm_base_url,
                "timeout": config.llm.timeout,
                "max_retries": config.llm.max_retries,
            },
            "ollama": {
                "model": llm_model,
                "host": config.llm.host or "http://localhost:11434",
            },
        }
        llm_client = create_llm_client(provider, **llm_kwargs.get(provider, {}))
        llm_client._current_task_id = task.id

        file_svc = ProjectFileService(config.web)
        repo_path = str(file_svc.detect_code_root(project.name))
        index_path = str(file_svc.get_index_path(project.name))

        code_graph = await project_store.get_code_graph(project.id, index_path)
        vector_store = await project_store.get_vector_store(project.id, index_path)

        path_sandbox = PathSandbox(allowed_root=repo_path)
        sensitive_filter = SensitiveFileFilter()
        user_permissions = {
            "read:code",
            "read:memory",
            "read:history",
            "read:git",
            "write:report",
            "read:user_memory",
        }
        tool_registry = ToolRegistry(user_permissions=user_permissions)

        if code_graph:
            tool_registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path))
            tool_registry.register(
                GetDependenciesTool(code_graph=code_graph, memory_data=memory_data)
            )

        tool_registry.register(ReadFileTool(repo_path=repo_path))
        tool_registry.register(ReadModuleSummaryTool(memory_data=memory_data))
        tool_registry.register(ListModulesTool(memory_data=memory_data))
        tool_registry.register(GetProjectProfileTool(memory_data=memory_data))
        tool_registry.register(GetTerminologyTool(memory_data=memory_data))

        if vector_store:
            tool_registry.register(SearchRequirementsTool(vector_store=vector_store))

        try:
            git_analyzer = None
            if Path(repo_path, ".git").exists():
                git_analyzer = GitAnalyzer(
                    repo_path=Path(repo_path), lookback_months=config.git.lookback_months
                )
            if git_analyzer:
                tool_registry.register(GetContributorsTool(git_analyzer=git_analyzer))
        except Exception:
            logger.warning("Failed to init GitAnalyzer for project %d", project.id)

        return tool_registry, llm_client

    async def _load_template(self, config: Config, db: AsyncSession):
        from reqradar.web.models import ReportTemplate

        template_loader = TemplateLoader()
        template_def = None
        template_id = config.reporting.default_template_id if hasattr(config, "reporting") else None
        if template_id:
            tmpl_result = await db.execute(
                select(ReportTemplate).where(ReportTemplate.id == template_id)
            )
            tmpl_obj = tmpl_result.scalar_one_or_none()
            if tmpl_obj:
                template_def = template_loader.load_from_db_data(
                    tmpl_obj.definition, tmpl_obj.render_template
                )

        if template_def is None:
            try:
                template_def = template_loader.load_definition(
                    template_loader.get_default_template_path()
                )
            except Exception:
                template_def = None

        return template_def

    async def _save_report(
        self,
        task: AnalysisTask,
        agent: AnalysisAgent,
        report_data: dict,
        report_markdown: str,
        report_html: str,
        db: AsyncSession,
    ):
        from reqradar.web.services.version_service import VersionService

        task.context_json = agent.get_context_snapshot()
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)

        db.add(
            Report(
                task_id=task.id,
                content_markdown=report_markdown,
                content_html=report_html,
            )
        )

        version_service = VersionService(db)
        context_snapshot = agent.get_context_snapshot()
        await version_service.create_version(
            task_id=task.id,
            report_data=report_data,
            context_snapshot=context_snapshot,
            content_markdown=report_markdown,
            content_html=report_html,
            trigger_type="initial",
            created_by=task.user_id,
        )

        await db.commit()

    async def _execute_agent(
        self, task_id: int, project: Project, config: Config, db: AsyncSession
    ):
        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        await ws_manager.broadcast(task_id, {"type": "analysis_started", "task_id": task_id})

        try:
            agent, analysis_memory, cm, memory_data = await self._init_agent(
                task, project, config, db
            )
            tool_registry, llm_client = await self._init_tools(
                agent, task, project, config, db, cm, memory_data
            )
            template_def = await self._load_template(config, db)

            section_descriptions = None
            if template_def:
                section_descriptions = [
                    {
                        "id": s.id,
                        "title": s.title,
                        "description": s.description,
                        "requirements": s.requirements,
                        "dimensions": s.dimensions,
                        "required": s.required,
                    }
                    for s in template_def.sections
                ]

            await ws_manager.broadcast(
                task_id,
                {
                    "type": "agent_thinking",
                    "task_id": task_id,
                    "message": "开始分析需求...",
                },
            )

            report_data = await run_react_analysis(
                agent=agent,
                llm_client=llm_client,
                tool_registry=tool_registry,
                config=config,
                section_descriptions=section_descriptions,
                project_memory=analysis_memory.project_memory if analysis_memory else None,
            )

            renderer = ReportRenderer(config, template_definition=template_def)
            report_data.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            report_data.setdefault("requirement_path", agent.requirement_text[:50])
            report_data.setdefault("impact_scope", "")

            try:
                report_markdown = renderer.render_from_data(report_data)
            except Exception:
                try:
                    from jinja2 import Template as JinjaTemplate
                    from reqradar.core.report import _INLINE_FALLBACK_TEMPLATE

                    fallback_tmpl = JinjaTemplate(_INLINE_FALLBACK_TEMPLATE)
                    report_markdown = fallback_tmpl.render(**report_data)
                except Exception:
                    report_markdown = json.dumps(
                        report_data, ensure_ascii=False, indent=2, default=str
                    )

            report_html = markdown.markdown(
                report_markdown, extensions=["extra", "codehilite", "toc", "tables"]
            )
            risk_level = report_data.get("risk_level", "unknown")

            await self._save_report(task, agent, report_data, report_markdown, report_html, db)

            await ws_manager.broadcast(
                task_id,
                {
                    "type": "analysis_complete",
                    "task_id": task_id,
                    "risk_level": risk_level,
                },
            )

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await ws_manager.broadcast(task_id, {"type": "analysis_cancelled", "task_id": task_id})
            raise

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)[:2000]
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await ws_manager.broadcast(
                task_id,
                {
                    "type": "analysis_failed",
                    "task_id": task_id,
                    "error": str(e)[:500],
                },
            )

    def cancel(self, task_id: int):
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()


runner = AnalysisRunner()
