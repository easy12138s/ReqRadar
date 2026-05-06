import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from reqradar.cli.utils import get_db_session
from reqradar.infrastructure.config import load_config

console = Console()


@click.group(name="requirement")
def requirement_group():
    """需求预处理命令"""
    pass


@requirement_group.command(name="preprocess")
@click.option("-p", "--project-id", type=int, required=True, help="项目 ID")
@click.option(
    "-f",
    "--files",
    type=click.Path(exists=True, path_type=Path),
    multiple=True,
    help="需求文件路径（可多次指定）",
)
@click.option(
    "-d",
    "--dir",
    "directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="扫描目录",
)
@click.option("-n", "--name", type=str, default="", help="需求文档标题")
@click.option("--output", type=click.Path(path_type=Path), help="保存确认文档到文件")
@click.option("--wait/--no-wait", default=True, help="是否交互确认")
def preprocess_command(project_id, files, directory, name, output, wait):
    """预处理需求文件，整合为结构化文档"""
    from reqradar.agent.requirement_preprocessor import preprocess_requirements
    from reqradar.agent.llm_utils import _call_llm_structured
    from reqradar.modules.llm_client import OpenAIClient
    from reqradar.web.models import RequirementDocument, Project
    from sqlalchemy import select

    ALLOWED_EXTENSIONS = {
        ".txt",
        ".md",
        ".pdf",
        ".docx",
        ".xlsx",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".html",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
    }

    file_paths = list(files) if files else []

    if directory:
        for ext in ALLOWED_EXTENSIONS:
            file_paths.extend(sorted(directory.glob(f"*{ext}")))
            if ext == ".docx":
                file_paths.extend(sorted(directory.glob("*.doc")))

    file_paths = sorted(set(file_paths))

    if not file_paths:
        console.print("[red]错误: 没有找到有效的需求文件[/red]")
        sys.exit(1)

    console.print(f"\n正在处理 {len(file_paths)} 个文件...")

    for fp in file_paths:
        console.print(f"  [dim] ✓[/dim] {fp.name}")

    title = name or file_paths[0].stem

    config = load_config()
    llm_client = OpenAIClient(config.llm)

    async def _run():
        return await preprocess_requirements(file_paths, llm_client, title)

    console.print("\n[dim]正在整合需求文档...[/dim]\n")
    result = asyncio.run(_run())
    consolidated_text = result.get("consolidated_text", "")

    console.print(Markdown(consolidated_text))

    if output:
        output.write_text(consolidated_text, encoding="utf-8")
        console.print(f"\n[green]✓ 文档已保存: {output}[/green]")

    if not wait:
        engine, session_factory = get_db_session(config)

        async def _save_doc():
            async with session_factory() as session:
                project = (
                    await session.execute(select(Project).where(Project.id == project_id))
                ).scalar_one_or_none()
                if not project:
                    console.print(f"[red]错误: 项目 {project_id} 不存在[/red]")
                    return

                doc = RequirementDocument(
                    project_id=project_id,
                    user_id=1,
                    title=title,
                    consolidated_text=consolidated_text,
                    source_files=[{"filename": p.name, "type": p.suffix} for p in file_paths],
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)
                console.print(f"\n[green]✓ 需求文档已保存，ID: {doc.id}[/green]")

        try:
            asyncio.run(_save_doc())
        finally:
            asyncio.run(engine.dispose())
        return

    while True:
        choice = click.prompt(
            "\n确认使用此文档？", type=click.Choice(["y", "n", "e", "q"]), default="y"
        )
        if choice == "y":
            engine, session_factory = get_db_session(config)

            async def _save_doc():
                async with session_factory() as session:
                    project = (
                        await session.execute(select(Project).where(Project.id == project_id))
                    ).scalar_one_or_none()
                    if not project:
                        console.print(f"[red]错误: 项目 {project_id} 不存在[/red]")
                        return

                    doc = RequirementDocument(
                        project_id=project_id,
                        user_id=1,
                        title=title,
                        consolidated_text=consolidated_text,
                        source_files=[{"filename": p.name, "type": p.suffix} for p in file_paths],
                    )
                    session.add(doc)
                    await session.commit()
                    await session.refresh(doc)
                    console.print(f"\n[green]✓ 需求文档已保存，ID: {doc.id}[/green]")

            try:
                asyncio.run(_save_doc())
            finally:
                asyncio.run(engine.dispose())
            break
        elif choice == "e":
            import tempfile
            import subprocess
            import os

            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
                tmp.write(consolidated_text)
                tmp_path = tmp.name
            editor = os.environ.get("EDITOR", "vim")
            subprocess.run([editor, tmp_path])
            consolidated_text = Path(tmp_path).read_text()
            console.clear()
            console.print(Markdown(consolidated_text))
        elif choice in ("n", "q"):
            console.print("[yellow]已取消[/yellow]")
            break
