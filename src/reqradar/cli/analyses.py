"""CLI 分析任务管理命令"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from reqradar.cli.utils import get_db_session, close_db
from reqradar.web.models import Project, AnalysisTask
from reqradar.web.enums import TaskStatus

console = Console()


@click.group()
def analyze():
    """分析任务管理"""
    pass


@analyze.command("submit")
@click.option("--project-id", "-p", required=True, type=int, help="项目 ID")
@click.option("--text", "-t", help="需求文本（直接传入）")
@click.option("--file", "-f", "req_file", type=click.Path(exists=True), help="需求文件路径")
@click.option("--name", "-n", default=None, help="需求名称（默认使用文件名或时间戳）")
@click.option(
    "--depth", type=click.Choice(["quick", "standard", "deep"]), default="standard", help="分析深度"
)
@click.option("-r", "--req-doc-id", type=int, help="预处理需求文档 ID")
@click.pass_context
def analyze_submit(ctx, project_id, text, req_file, name, depth, req_doc_id):
    """提交分析任务"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    if not text and not req_file:
        console.print("[red]错误: 必须指定 --text 或 --file[/red]")
        raise SystemExit(1)

    if text and req_file:
        console.print("[red]错误: --text 和 --file 不能同时指定[/red]")
        raise SystemExit(1)

    if req_file:
        text = Path(req_file).read_text(encoding="utf-8")
        if not name:
            name = Path(req_file).stem

    if not name:
        name = f"Analysis-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    if req_doc_id:
        from reqradar.web.models import RequirementDocument

        async def _lookup_doc():
            async with session_factory() as db:
                return (
                    await db.execute(
                        select(RequirementDocument).where(RequirementDocument.id == req_doc_id)
                    )
                ).scalar_one_or_none()

        doc = asyncio.run(_lookup_doc())
        if doc:
            text = doc.consolidated_text or text
            if not name:
                name = doc.title or name
        else:
            console.print(f"[red]错误: 预处理文档 {req_doc_id} 不存在[/red]")
            return

    async def _submit():
        async with session_factory() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if project is None:
                console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            task = AnalysisTask(
                project_id=project_id,
                user_id=1,
                requirement_name=name,
                requirement_text=text,
                depth=depth,
                status=TaskStatus.PENDING,
                requirement_document_id=req_doc_id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            console.print(f"[green]✓[/green] 分析任务已提交 (id={task.id})")
            console.print(f"  项目: {project.name}")
            console.print(f"  名称: {name}")
            console.print(f"  深度: {depth}")
            console.print(f"  状态: {task.status}")

            console.print("\n[yellow]启动分析...[/yellow]")

            from reqradar.web.services.analysis_runner import runner

            project_obj = Project(
                id=project.id,
                name=project.name,
                description=project.description,
                source_type=project.source_type,
                source_url=project.source_url,
                owner_id=project.owner_id,
            )

            await session.close()
            await close_db(engine)

            runner.submit(task.id, project_obj, config)

            console.print(f"[green]✓[/green] 分析任务正在后台运行")
            console.print(f"  使用 'reqradar analyze status {task.id}' 查看进度")

    try:
        asyncio.run(_submit())
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]提交失败: {e}[/red]")
        raise SystemExit(1)


@analyze.command("list")
@click.option("--project-id", "-p", type=int, default=None, help="按项目 ID 筛选")
@click.option(
    "--status",
    "-s",
    "status_filter",
    type=click.Choice(["pending", "running", "completed", "failed", "cancelled"]),
    default=None,
    help="按状态筛选",
)
@click.pass_context
def analyze_list(ctx, project_id, status_filter):
    """列出分析任务"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _list():
        async with session_factory() as session:
            query = select(AnalysisTask).order_by(AnalysisTask.created_at.desc())
            if project_id is not None:
                query = query.where(AnalysisTask.project_id == project_id)
            if status_filter is not None:
                query = query.where(AnalysisTask.status == status_filter)

            result = await session.execute(query)
            tasks = result.scalars().all()

            if not tasks:
                console.print("[yellow]暂无分析任务[/yellow]")
                await close_db(engine)
                return

            table = Table(title="分析任务列表")
            table.add_column("ID", style="cyan")
            table.add_column("名称", style="green")
            table.add_column("项目ID")
            table.add_column("状态", style="yellow")
            table.add_column("深度")
            table.add_column("创建时间")

            status_colors = {
                "pending": "yellow",
                "running": "blue",
                "completed": "green",
                "failed": "red",
                "cancelled": "dim",
            }

            for t in tasks:
                color = status_colors.get(t.status, "white")
                table.add_row(
                    str(t.id),
                    t.requirement_name[:30],
                    str(t.project_id),
                    f"[{color}]{t.status}[/{color}]",
                    t.depth,
                    t.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)

        await close_db(engine)

    try:
        asyncio.run(_list())
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1)


@analyze.command("status")
@click.argument("task_id", type=int)
@click.pass_context
def analyze_status(ctx, task_id):
    """查看分析任务状态和进度"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _status():
        async with session_factory() as session:
            result = await session.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
            task = result.scalar_one_or_none()

            if task is None:
                console.print(f"[red]错误: 任务 ID {task_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            status_colors = {
                "pending": "yellow",
                "running": "blue",
                "completed": "green",
                "failed": "red",
                "cancelled": "dim",
            }
            color = status_colors.get(task.status, "white")

            table = Table(title=f"分析任务 #{task.id}: {task.requirement_name}")
            table.add_column("属性", style="cyan")
            table.add_column("值", style="green")

            table.add_row("ID", str(task.id))
            table.add_row("名称", task.requirement_name)
            table.add_row("状态", f"[{color}]{task.status}[/{color}]")
            table.add_row("深度", task.depth)
            table.add_row("创建时间", task.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            if task.started_at:
                table.add_row("开始时间", task.started_at.strftime("%Y-%m-%d %H:%M:%S"))
            if task.completed_at:
                table.add_row("完成时间", task.completed_at.strftime("%Y-%m-%d %H:%M:%S"))
            if task.error_message:
                table.add_row("错误信息", f"[red]{task.error_message}[/red]")

            if task.context_json:
                step_results = task.context_json.get("step_results", {})
                if step_results:
                    table.add_row("已执行步骤", str(len(step_results)))

            console.print(table)

            if task.status == "completed":
                console.print(f"\n[green]✓[/green] 使用 'reqradar report get {task_id}' 查看报告")

        await close_db(engine)

    try:
        asyncio.run(_status())
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1)


@analyze.command("cancel")
@click.argument("task_id", type=int)
@click.pass_context
def analyze_cancel(ctx, task_id):
    """取消运行中的分析任务"""
    from datetime import datetime, timezone

    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _cancel():
        async with session_factory() as session:
            result = await session.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
            task = result.scalar_one_or_none()

            if task is None:
                console.print(f"[red]错误: 任务 ID {task_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                console.print(f"[red]错误: 无法取消状态为 '{task.status}' 的任务[/red]")
                await close_db(engine)
                raise SystemExit(1)

            try:
                from reqradar.web.services.analysis_runner import runner

                runner.cancel(task_id)
            except Exception:
                pass

            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            await session.commit()

            console.print(f"[green]✓[/green] 任务 '{task.requirement_name}' 已取消")

        await close_db(engine)

    try:
        asyncio.run(_cancel())
    except Exception as e:
        console.print(f"[red]取消失败: {e}[/red]")
        raise SystemExit(1)


@analyze.command("file")
@click.argument("requirement_file", type=click.Path(exists=True))
@click.option(
    "--index-path",
    "-i",
    type=click.Path(exists=True, file_okay=False),
    default=".reqradar/index",
    help="索引目录路径",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False),
    default="./reports",
    help="报告输出目录",
)
@click.option(
    "--llm-backend",
    type=click.Choice(["openai", "ollama"]),
    default=None,
    help="LLM 后端",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="详细输出",
)
@click.pass_context
def analyze_file(ctx, requirement_file, index_path, output, llm_backend, verbose):
    """本地文件分析（ReAct Agent 模式，无需数据库）"""
    import json

    from reqradar.agent.analysis_agent import AnalysisAgent
    from reqradar.agent.runner import run_react_analysis
    from reqradar.core.report import ReportRenderer
    from reqradar.modules.git_analyzer import GitAnalyzer
    from reqradar.modules.llm_client import create_llm_client
    from reqradar.modules.vector_store import ChromaVectorStore
    from reqradar.infrastructure.logging import setup_logging

    config = ctx.obj["config"]
    log_level = "DEBUG" if verbose else config.log.level
    setup_logging(level=log_level)

    index_path_obj = Path(index_path)
    code_graph_path = index_path_obj / "code_graph.json"
    vectorstore_path = index_path_obj / "vectorstore"

    async def run_analysis():
        from datetime import datetime
        from reqradar.modules.memory import MemoryManager
        from reqradar.modules.memory_manager import AnalysisMemoryManager

        memory_manager = MemoryManager(storage_path=config.memory.storage_path)
        memory_data = memory_manager.load() if config.memory.enabled else None

        requirement_path = Path(requirement_file)
        requirement_text = requirement_path.read_text(encoding="utf-8")

        agent = AnalysisAgent(
            requirement_text=requirement_text,
            project_id=0,
            user_id=0,
            depth="standard",
        )

        analysis_memory = AnalysisMemoryManager(
            project_id=0,
            user_id=0,
            project_storage_path=config.memory.storage_path,
            user_storage_path=config.memory.storage_path,
            memory_enabled=config.memory.enabled,
        )

        agent.project_memory_text = analysis_memory.get_project_profile_text()
        agent.user_memory_text = analysis_memory.get_user_memory_text()

        provider = llm_backend or config.llm.provider
        llm_kwargs = {
            "openai": {
                "api_key": config.llm.api_key,
                "model": config.llm.model,
                "base_url": config.llm.base_url or "https://api.openai.com/v1",
                "timeout": config.llm.timeout,
                "max_retries": config.llm.max_retries,
            },
            "ollama": {
                "model": config.llm.model if llm_backend == "ollama" else "qwen2.5:14b",
                "host": config.llm.host or "http://localhost:11434",
            },
        }

        llm_client = create_llm_client(provider, **llm_kwargs[provider])

        vector_store = None
        if vectorstore_path.exists():
            vector_store = ChromaVectorStore(persist_directory=str(vectorstore_path))

        code_graph = None
        if code_graph_path.exists():
            with open(code_graph_path, encoding="utf-8") as f:
                graph_data = json.load(f)
            from reqradar.modules.code_parser import CodeFile, CodeGraph, CodeSymbol

            code_graph = CodeGraph(
                files=[
                    CodeFile(
                        path=f["path"],
                        symbols=[CodeSymbol(**s) for s in f.get("symbols", [])],
                        imports=f.get("imports", []),
                    )
                    for f in graph_data.get("files", [])
                ]
            )

        git_analyzer = None
        repo_path = Path.cwd()
        if (repo_path / ".git").exists():
            git_analyzer = GitAnalyzer(
                repo_path=repo_path,
                lookback_months=config.git.lookback_months,
            )

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

        tool_registry = ToolRegistry()
        repo_path_str = str(repo_path)

        if code_graph:
            tool_registry.register(SearchCodeTool(code_graph=code_graph, repo_path=repo_path_str))
            tool_registry.register(
                GetDependenciesTool(code_graph=code_graph, memory_data=memory_data)
            )

        tool_registry.register(ReadFileTool(repo_path=repo_path_str))
        tool_registry.register(ReadModuleSummaryTool(memory_data=memory_data))
        tool_registry.register(ListModulesTool(memory_data=memory_data))
        tool_registry.register(GetProjectProfileTool(memory_data=memory_data))
        tool_registry.register(GetTerminologyTool(memory_data=memory_data))

        if vector_store:
            tool_registry.register(SearchRequirementsTool(vector_store=vector_store))

        if git_analyzer:
            tool_registry.register(GetContributorsTool(git_analyzer=git_analyzer))

        console.print("[cyan]开始 ReAct Agent 分析...[/cyan]")

        report_data = await run_react_analysis(
            agent=agent,
            llm_client=llm_client,
            tool_registry=tool_registry,
            config=config,
        )

        renderer = ReportRenderer(config)

        report_data.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        report_data.setdefault("requirement_path", str(requirement_path))
        report_data.setdefault("impact_scope", "")
        report_data.setdefault("content_confidence", "N/A")
        report_data.setdefault("process_completion", "N/A")
        report_data.setdefault("content_completeness", "N/A")
        report_data.setdefault("evidence_support", "N/A")

        report_content = renderer.render_from_data(report_data)

        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)

        report_filename = (
            f"report_{requirement_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        report_path = output_path / report_filename

        renderer.save(report_content, report_path)

        console.print(f"\n[bold green]报告已生成: {report_path}[/bold green]")

        from rich.table import Table as RichTable

        table = RichTable(title="分析结果概览")
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")

        risk_level = report_data.get("risk_level", "unknown")
        table.add_row("风险等级", risk_level)
        table.add_row("分析步骤", f"{agent.step_count}/{agent.max_steps}")
        table.add_row("证据数量", str(len(agent.evidence_collector.evidences)))
        table.add_row("维度完成", str(agent.dimension_tracker.status_summary()))

        console.print(table)

        if config.memory.enabled:
            try:
                memory_manager.save()
            except (OSError, Exception):
                pass

        return report_data

    try:
        asyncio.run(run_analysis())
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[bold red]分析失败: {e}[/bold red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise SystemExit(1)
