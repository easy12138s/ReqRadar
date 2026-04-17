"""CLI 主入口 - Click"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from reqradar import __version__
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
                    except Exception as e:
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
                from reqradar.agent.steps import step_build_project_profile
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
                        console.print(f"  - 描述: {profile.get('description', 'N/A')}")
                        console.print(f"  - 架构: {profile.get('architecture_style', 'N/A')}")
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
    """分析需求文档并生成报告"""
    import json

    from reqradar.agent.steps import (
        step_analyze,
        step_extract,
        step_generate,
        step_map_keywords,
        step_read,
        step_retrieve,
    )
    from reqradar.core.context import AnalysisContext
    from reqradar.core.report import ReportRenderer
    from reqradar.core.scheduler import Scheduler
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
        from reqradar.modules.memory import MemoryManager

        memory_manager = MemoryManager(storage_path=config.memory.storage_path)
        memory_data = memory_manager.load()

        context = AnalysisContext(
            requirement_path=Path(requirement_file),
            memory_data=memory_data if config.memory.enabled else None,
        )

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

        async def wrapped_extract(ctx):
            return await step_extract(ctx, llm_client)

        async def wrapped_map_keywords(ctx):
            return await step_map_keywords(ctx, llm_client)

        async def wrapped_retrieve(ctx):
            result = await step_retrieve(ctx, vector_store, llm_client)
            ctx.retrieved_context = result
            return result

        async def wrapped_analyze(ctx):
            result = await step_analyze(ctx, code_graph, git_analyzer, llm_client)
            ctx.deep_analysis = result
            return result

        async def wrapped_generate(ctx):
            return await step_generate(ctx, llm_client)

        async def memory_update_hook(ctx):
            if config.memory.enabled:
                try:
                    await memory_manager.update_from_analysis(ctx)
                    logger.info("Memory updated from analysis")
                except Exception as e:
                    logger.warning("Failed to update memory: %s", e)

        async def persist_module_history_hook(ctx):
            """持久化模块关联历史"""
            if not ctx.deep_analysis or not ctx.deep_analysis.impact_modules:
                return
            try:
                for module in ctx.deep_analysis.impact_modules:
                    module_path = module.get("path", "")
                    if module_path:
                        memory_manager.add_module_requirement_history(
                            module_name=module_path,
                            requirement_id=ctx.requirement_path.stem,
                            relevance=module.get("relevance", "unknown"),
                            suggested_changes=module.get("suggested_changes", ""),
                        )
                logger.info("Module requirement history persisted")
            except Exception as e:
                logger.warning("Failed to persist module history: %s", e)

        scheduler = Scheduler(
            read_handler=step_read,
            extract_handler=wrapped_extract,
            map_keywords_handler=wrapped_map_keywords,
            retrieve_handler=wrapped_retrieve,
            analyze_handler=wrapped_analyze,
            generate_handler=wrapped_generate,
        )

        scheduler.register_after_hook("analyze", persist_module_history_hook)
        scheduler.register_after_hook("generate", memory_update_hook)

        result_context = await scheduler.run(context)

        renderer = ReportRenderer(config)

        # generate handler already ran inside the scheduler,
        # use its result from step_results
        generate_result = result_context.get_result("generate")
        generated_content = (
            generate_result.data if generate_result and generate_result.success else None
        )

        report_content = renderer.render(result_context, generated_content)

        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)

        report_filename = f"report_{Path(requirement_file).stem}_{result_context.started_at.strftime('%Y%m%d_%H%M%S')}.md"
        report_path = output_path / report_filename

        renderer.save(report_content, report_path)

        console.print(f"\n[bold green]报告已生成: {report_path}[/bold green]")

        table = Table(title="分析结果概览")
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")

        table.add_row("数据完整度", result_context.completeness)
        table.add_row("置信度", f"{result_context.overall_confidence * 100:.1f}%")
        table.add_row(
            "步骤完成",
            f"{sum(1 for r in result_context.step_results.values() if r.success)}/{len(result_context.step_results)}",
        )

        console.print(table)

        return result_context

    try:
        asyncio.run(run_analysis())
    except Exception as e:
        console.print(f"[bold red]分析失败: {e}[/bold red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise click.Abort()


if __name__ == "__main__":
    cli()
