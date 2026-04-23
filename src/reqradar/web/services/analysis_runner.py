import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import markdown
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.core.context import AnalysisContext, StepResult
from reqradar.core.report import ReportRenderer
from reqradar.core.scheduler import Scheduler
from reqradar.infrastructure.config import Config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.models import AnalysisTask, Project, Report
from reqradar.web.services.project_store import project_store
from reqradar.web.websocket import manager as ws_manager

logger = logging.getLogger("reqradar.web.services.analysis_runner")


async def _load_template_definition(db, template_id, template_loader):
    from reqradar.web.models import ReportTemplate

    result = await db.execute(
        select(ReportTemplate).where(ReportTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if tmpl:
        return template_loader.load_from_db_data(tmpl.definition, tmpl.render_template)
    return None


class AnalysisRunner:
    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[int, asyncio.Task] = {}

    def submit(self, task_id: int, project: Project, config: Config) -> asyncio.Task:
        if task_id in self._active_tasks and not self._active_tasks[task_id].done():
            raise ValueError(f"Task {task_id} is already running")

        task = asyncio.create_task(self._run_analysis(task_id, project, config))

        def _on_done(t: asyncio.Task):
            self._active_tasks.pop(task_id, None)

        task.add_done_callback(_on_done)
        self._active_tasks[task_id] = task
        return task

    async def _run_analysis(self, task_id: int, project: Project, config: Config):
        async with self._semaphore:
            import reqradar.web.dependencies as dep_module

            async with dep_module.async_session_factory() as db:
                try:
                    await self._execute_pipeline(task_id, project, config, db)
                except asyncio.CancelledError:
                    logger.info("Analysis task %d cancelled", task_id)
                    raise
                except Exception:
                    logger.exception("Analysis task %d failed", task_id)

    async def _execute_pipeline(self, task_id: int, project: Project, config: Config, db: AsyncSession):
        from reqradar.agent.steps import (
            step_analyze,
            step_extract,
            step_generate,
            step_map_keywords,
            step_read,
            step_retrieve,
        )
        from reqradar.modules.llm_client import create_llm_client
        from reqradar.agent.tools import (
            ToolRegistry,
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
        from reqradar.modules.git_analyzer import GitAnalyzer
        from reqradar.modules.memory import MemoryManager

        result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        await ws_manager.broadcast(task_id, {"type": "analysis_started", "task_id": task_id})

        try:
            index_path = project.index_path or str(Path(project.repo_path) / ".reqradar" / "index")
            repo_path = project.repo_path or "."

            code_graph = await project_store.get_code_graph(project.id, index_path)
            vector_store = await project_store.get_vector_store(project.id, index_path)

            memory_manager = MemoryManager(
                storage_path=str(Path(project.repo_path) / config.memory.storage_path)
                if project.repo_path else config.memory.storage_path
            )
            memory_data = memory_manager.load() if config.memory.enabled else None

            from reqradar.modules.memory_manager import AnalysisMemoryManager

            analysis_memory = AnalysisMemoryManager(
                project_id=project.id,
                user_id=task.user_id,
                project_storage_path=str(Path(project.repo_path) / config.memory.project_storage_path)
                if project.repo_path else config.memory.project_storage_path,
                user_storage_path=str(Path(project.repo_path) / config.memory.user_storage_path)
                if project.repo_path else config.memory.user_storage_path,
                memory_enabled=config.memory.enabled,
            )

            from reqradar.infrastructure.template_loader import TemplateLoader

            template_loader = TemplateLoader()
            if config.reporting.default_template_id:
                template_def = await _load_template_definition(db, config.reporting.default_template_id, template_loader)
            else:
                template_def = None

            cm = ConfigManager(db, config)

            context = AnalysisContext(
                requirement_path=Path(task.requirement_name),
                requirement_text=task.requirement_text,
                memory_data=memory_data,
            )

            provider = await cm.get_str("llm.provider", user_id=task.user_id, project_id=project.id, default=config.llm.provider)
            llm_model = await cm.get_str("llm.model", user_id=task.user_id, project_id=project.id, default=config.llm.model)
            llm_api_key = await cm.get_str("llm.api_key", user_id=task.user_id, project_id=project.id, default=config.llm.api_key or "")
            llm_base_url = await cm.get_str("llm.base_url", user_id=task.user_id, project_id=project.id, default=config.llm.base_url or "https://api.openai.com/v1")
            llm_timeout = await cm.get_int("llm.timeout", user_id=task.user_id, project_id=project.id, default=config.llm.timeout)
            llm_max_retries = await cm.get_int("llm.max_retries", user_id=task.user_id, project_id=project.id, default=config.llm.max_retries)

            llm_kwargs = {
                "openai": {
                    "api_key": llm_api_key,
                    "model": llm_model,
                    "base_url": llm_base_url,
                    "timeout": llm_timeout,
                    "max_retries": llm_max_retries,
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

            git_analyzer = None
            if project.repo_path and Path(project.repo_path, ".git").exists():
                try:
                    git_analyzer = GitAnalyzer(
                        repo_path=Path(project.repo_path),
                        lookback_months=config.git.lookback_months,
                    )
                except Exception:
                    logger.warning("Failed to init GitAnalyzer for project %d", project.id)

            tool_registry = ToolRegistry()
            repo_path_str = str(project.repo_path) if project.repo_path else "."

            if code_graph:
                tool_registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path_str))
                tool_registry.register(GetDependenciesTool(code_graph=code_graph, memory_data=memory_data))

            tool_registry.register(ReadFileTool(repo_path=repo_path_str))
            tool_registry.register(ReadModuleSummaryTool(memory_data=memory_data))
            tool_registry.register(ListModulesTool(memory_data=memory_data))
            tool_registry.register(GetProjectProfileTool(memory_data=memory_data))
            tool_registry.register(GetTerminologyTool(memory_data=memory_data))

            if vector_store:
                tool_registry.register(SearchRequirementsTool(vector_store=vector_store))

            if git_analyzer:
                tool_registry.register(GetContributorsTool(git_analyzer=git_analyzer))

            async def wrapped_extract(ctx):
                return await step_extract(ctx, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)

            async def wrapped_map_keywords(ctx):
                return await step_map_keywords(ctx, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)

            async def wrapped_retrieve(ctx):
                result = await step_retrieve(ctx, vector_store, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)
                ctx.retrieved_context = result
                return result

            async def wrapped_analyze(ctx):
                result = await step_analyze(ctx, code_graph, git_analyzer, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)
                ctx.deep_analysis = result
                return result

            async def wrapped_generate(ctx):
                return await step_generate(ctx, llm_client, tool_registry=tool_registry, analysis_config=config.analysis)

            async def on_step_start(step_name: str, step_desc: str):
                await ws_manager.broadcast(task_id, {
                    "type": "step_start",
                    "task_id": task_id,
                    "step": step_name,
                    "description": step_desc,
                })

            async def on_step_complete(step_name: str, step_result: StepResult):
                await ws_manager.broadcast(task_id, {
                    "type": "step_complete",
                    "task_id": task_id,
                    "step": step_name,
                    "success": step_result.success,
                    "confidence": step_result.confidence,
                })

            scheduler = Scheduler(
                read_handler=step_read,
                extract_handler=wrapped_extract,
                map_keywords_handler=wrapped_map_keywords,
                retrieve_handler=wrapped_retrieve,
                analyze_handler=wrapped_analyze,
                generate_handler=wrapped_generate,
            )

            result_context = await scheduler.run(
                context,
                on_step_start=on_step_start,
                on_step_complete=on_step_complete,
            )

            renderer = ReportRenderer(config, template_definition=template_def)
            generate_result = result_context.get_result("generate")
            generated_content = (
                generate_result.data if generate_result and generate_result.success else None
            )
            report_markdown = renderer.render(result_context, generated_content)
            report_html = markdown.markdown(
                report_markdown,
                extensions=["extra", "codehilite", "toc", "tables"],
            )

            risk_level = "unknown"
            if result_context.deep_analysis and result_context.deep_analysis.risk_level:
                risk_level = result_context.deep_analysis.risk_level

            task.context_json = result_context.model_dump_json()
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

    def cancel(self, task_id: int):
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()


runner = AnalysisRunner()


def get_runner(config: Config):
    if hasattr(config, "agent") and config.agent.mode == "react":
        from reqradar.web.services.analysis_runner_v2 import runner_v2
        return runner_v2
    return runner