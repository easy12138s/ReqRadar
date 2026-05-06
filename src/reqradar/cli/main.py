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
                    console.print(
                        f"[green]✓[/green] 已识别 {len(result.get('modules', []))} 个模块"
                    )
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


from reqradar.web.cli import serve
from reqradar.cli.projects import project
from reqradar.cli.analyses import analyze
from reqradar.cli.reports import report
from reqradar.cli.config import config
from reqradar.cli.requirements import requirement_group

cli.add_command(serve)
cli.add_command(project)
cli.add_command(analyze)
cli.add_command(report)
cli.add_command(config)
cli.add_command(requirement_group)


if __name__ == "__main__":
    cli()
