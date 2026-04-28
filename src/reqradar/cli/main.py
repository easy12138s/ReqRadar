"""CLI 主入口 - Click"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

import yaml


from reqradar import __version__
from reqradar.core.exceptions import LoaderException
from reqradar.infrastructure.config import load_config
from reqradar.infrastructure.logging import setup_logging

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="配置文件路径",
)
@click.pass_context
def cli(ctx, config):
    """ReqRadar - 需求透视垂直领域 Agent"""
    ctx.ensure_object(dict)

    config_path = Path(config) if config else None
    ctx.obj["config"] = load_config(config_path)
    ctx.obj["config_path"] = config_path


@cli.command()
@click.option(
    "--repo-path",
    "-r",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="代码仓库路径",
)
@click.option(
    "--docs-path",
    "-d",
    type=click.Path(exists=True, file_okay=False),
    help="需求文档目录",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False),
    default=".reqradar/index",
    help="索引输出目录",
)
@click.option(
    "--build-profile/--no-build-profile",
    "do_build_profile",
    is_flag=True,
    default=True,
    help="是否调用 LLM 构建项目画像",
)
@click.pass_context
def index(ctx, repo_path, docs_path, output, do_build_profile):
    """构建代码和文档索引"""
    from reqradar.modules.code_parser import PythonCodeParser
    from reqradar.modules.vector_store import ChromaVectorStore

    config = ctx.obj["config"]
    logger = setup_logging(level=config.log.level)

    console.print("[cyan]开始构建索引...[/cyan]")

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        console.print("[yellow]解析代码仓库...[/yellow]")
        parser = PythonCodeParser()
        code_graph = parser.parse_directory(Path(repo_path))

        code_graph_path = output_path / "code_graph.json"
        with open(code_graph_path, "w", encoding="utf-8") as f:
            f.write(code_graph.to_json())
        console.print(f"[green]✓[/green] 代码图谱已保存: {code_graph_path}")

        if docs_path:
            console.print("[yellow]索引需求文档...[/yellow]")
            from reqradar.modules.loaders import LoaderRegistry
            from reqradar.modules.vector_store import Document

            vector_store = ChromaVectorStore(
                persist_directory=str(output_path / "vectorstore"),
                embedding_model=config.index.embedding_model,
            )

            docs_path_obj = Path(docs_path)
            indexed_count = 0
            skipped_count = 0

            for doc_path in docs_path_obj.rglob("*"):
                if doc_path.is_file():
                    loader = LoaderRegistry.get_for_file(doc_path)
                    if loader is None:
                        skipped_count += 1
                        continue

                    try:
                        loaded_docs = loader.load(
                            doc_path,
                            chunk_size=config.loader.chunk_size,
                            chunk_overlap=config.loader.chunk_overlap,
                        )
                    except (LoaderException, OSError, UnicodeDecodeError) as e:
                        console.print(f"[yellow]⚠[/yellow] 跳过 {doc_path.name}: {e}")
                        skipped_count += 1
                        continue

                    documents = [
                        Document(
                            id=f"{doc_path.stem}_{i}",
                            content=doc.content,
                            metadata={**doc.metadata, "format": doc.format},
                        )
                        for i, doc in enumerate(loaded_docs)
                    ]

                    if documents:
                        vector_store.add_documents(documents)
                        indexed_count += 1
                        console.print(f"[green]✓[/green] 已索引: {doc_path.name}")

            vector_store.persist()
            console.print(
                f"[green]✓[/green] 已索引 {indexed_count} 个文件，跳过 {skipped_count} 个"
            )

        if do_build_profile and config.llm.api_key:
            console.print("[yellow]构建项目画像...[/yellow]")

            async def build_profile():
                from reqradar.agent.project_profile import step_build_project_profile
                from reqradar.modules.llm_client import create_llm_client
                from reqradar.modules.memory import MemoryManager

                memory_manager = MemoryManager(storage_path=config.memory.storage_path)

                llm_client = create_llm_client(
                    config.llm.provider,
                    api_key=config.llm.api_key,
                    model=config.llm.model,
                    base_url=config.llm.base_url or "https://api.openai.com/v1",
                    timeout=config.llm.timeout,
                    max_retries=config.llm.max_retries,
                    embedding_model=config.llm.embedding_model,
                    embedding_dim=config.llm.embedding_dim,
                )

                result = await step_build_project_profile(
                    code_graph=code_graph,
                    llm_client=llm_client,
                    memory_manager=memory_manager,
                    repo_path=repo_path,
                )

                if result:
                    console.print(f"[green]✓[/green] 项目画像已构建")
                    if result.get("project_profile"):
                        profile = result["project_profile"]
                        console.print(f" - 描述: {profile.get('description', 'N/A')}")
                        console.print(f" - 架构: {profile.get('architecture_style', 'N/A')}")
                    console.print(f"[green]✓[/green] 已识别 {len(result.get('modules', []))} 个模块")
                else:
                    console.print("[yellow]⚠[/yellow] 项目画像构建失败，请检查 LLM 配置")

            try:
                asyncio.run(build_profile())
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] 项目画像构建出错: {e}")

        console.print("[bold green]索引构建完成![/bold green]")

    except Exception as e:
        console.print(f"[bold red]索引构建失败: {e}[/bold red]")
        raise click.Abort()


@cli.command()
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
def analyze(ctx, requirement_file, index_path, output, llm_backend, verbose):
    """分析需求文档并生成报告（ReAct Agent 模式）"""
    import json

    from reqradar.agent.analysis_agent import AnalysisAgent
    from reqradar.agent.runner import run_react_analysis
    from reqradar.core.report import ReportRenderer
    from reqradar.modules.git_analyzer import GitAnalyzer
    from reqradar.modules.llm_client import create_llm_client
    from reqradar.modules.vector_store import ChromaVectorStore

    config = ctx.obj["config"]
    log_level = "DEBUG" if verbose else config.log.level
    logger = setup_logging(level=log_level)

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
                "embedding_model": config.llm.embedding_model,
                "embedding_dim": config.llm.embedding_dim,
            },
            "ollama": {
                "model": config.llm.model if llm_backend == "ollama" else "qwen2.5:14b",
                "host": config.llm.host or "http://localhost:11434",
                "embedding_dim": config.llm.embedding_dim,
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
            ToolRegistry, SearchCodeTool, ReadFileTool,
            ReadModuleSummaryTool, ListModulesTool,
            SearchRequirementsTool, GetDependenciesTool,
            GetContributorsTool, GetProjectProfileTool,
            GetTerminologyTool,
        )

        tool_registry = ToolRegistry()
        repo_path_str = str(repo_path)

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

        report_filename = f"report_{requirement_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = output_path / report_filename

        renderer.save(report_content, report_path)

        console.print(f"\n[bold green]报告已生成: {report_path}[/bold green]")

        table = Table(title="分析结果概览")
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
            except (OSError, yaml.YAMLError):
                pass

        return report_data

    try:
        asyncio.run(run_analysis())
    except Exception as e:
        console.print(f"[bold red]分析失败: {e}[/bold red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise click.Abort()


from reqradar.web.cli import serve

cli.add_command(serve)


if __name__ == "__main__":
    cli()
