"""CLI 项目管理命令"""

import asyncio
import re
import shutil
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from reqradar.cli.utils import get_db_session, close_db
from reqradar.web.models import Project

console = Console()


@click.group()
def project():
    """项目管理"""
    pass


@project.command("create")
@click.option("--name", "-n", required=True, help="项目名称（字母、数字、下划线、连字符）")
@click.option("--description", "-d", default="", help="项目描述")
@click.option(
    "--local-path", "-l", type=click.Path(exists=True, file_okay=False), help="本地代码路径"
)
@click.option("--git-url", "-g", help="Git 仓库 URL")
@click.option("--branch", "-b", default=None, help="Git 分支名")
@click.option("--zip-file", "-z", type=click.Path(exists=True), help="ZIP 文件路径")
@click.pass_context
def project_create(ctx, name, description, local_path, git_url, branch, zip_file):
    """创建新项目"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    source_types = [x for x in [local_path, git_url, zip_file] if x]
    if len(source_types) != 1:
        console.print(
            "[red]错误: 必须且只能指定一种来源 (--local-path, --git-url, 或 --zip-file)[/red]"
        )
        raise SystemExit(1)

    pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    if not pattern.match(name):
        console.print("[red]错误: 项目名称只能包含字母、数字、下划线、连字符（1-64字符）[/red]")
        raise SystemExit(1)

    from reqradar.infrastructure.paths import get_paths
    from reqradar.web.services.project_file_service import ProjectFileService

    file_svc = ProjectFileService(get_paths(config)["projects"])

    async def _create():
        async with session_factory() as session:
            result = await session.execute(select(Project).where(Project.name == name))
            if result.scalar_one_or_none():
                console.print(f"[red]错误: 项目 '{name}' 已存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            if local_path:
                source_type = "local"
                source_url = str(Path(local_path).resolve())
            elif git_url:
                source_type = "git"
                source_url = git_url
            else:
                source_type = "zip"
                source_url = str(Path(zip_file).resolve())

            project = Project(
                name=name,
                description=description,
                source_type=source_type,
                source_url=source_url,
                owner_id=1,
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)

            file_svc.create_project_dirs(name)

            if local_path:
                src_code = file_svc.get_project_path(name) / "project_code"
                for item in Path(local_path).iterdir():
                    if item.is_dir() and not item.is_symlink():
                        shutil.copytree(str(item), str(src_code / item.name), dirs_exist_ok=True)
                    elif item.is_file() and not item.is_symlink():
                        shutil.copy2(str(item), str(src_code / item.name))
            elif git_url:
                if not file_svc.is_git_available():
                    console.print("[red]错误: Git 不可用[/red]")
                    await close_db(engine)
                    raise SystemExit(1)
                try:
                    file_svc.clone_git(name, git_url, branch)
                except Exception as e:
                    await session.delete(project)
                    await session.commit()
                    file_svc.delete_project_files(name)
                    console.print(f"[red]Git clone 失败: {e}[/red]")
                    await close_db(engine)
                    raise SystemExit(1)
            elif zip_file:
                zip_bytes = Path(zip_file).read_bytes()
                try:
                    file_svc.extract_zip(name, zip_bytes)
                except Exception as e:
                    await session.delete(project)
                    await session.commit()
                    file_svc.delete_project_files(name)
                    console.print(f"[red]ZIP 解压失败: {e}[/red]")
                    await close_db(engine)
                    raise SystemExit(1)

            console.print(f"[green]✓[/green] 项目 '{name}' 创建成功 (id={project.id})")
            console.print(f"  类型: {source_type}")
            console.print(f"  路径: {source_url}")

        await close_db(engine)

    try:
        asyncio.run(_create())
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]创建失败: {e}[/red]")
        raise SystemExit(1)


@project.command("list")
@click.pass_context
def project_list(ctx):
    """列出所有项目"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _list():
        async with session_factory() as session:
            result = await session.execute(select(Project).order_by(Project.created_at.desc()))
            projects = result.scalars().all()

            if not projects:
                console.print("[yellow]暂无项目[/yellow]")
                await close_db(engine)
                return

            table = Table(title="项目列表")
            table.add_column("ID", style="cyan")
            table.add_column("名称", style="green")
            table.add_column("类型", style="yellow")
            table.add_column("描述")
            table.add_column("创建时间")

            for p in projects:
                table.add_row(
                    str(p.id),
                    p.name,
                    p.source_type,
                    (p.description[:40] or ""),
                    p.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)

        await close_db(engine)

    try:
        asyncio.run(_list())
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1)


@project.command("show")
@click.argument("project_id", type=int)
@click.pass_context
def project_show(ctx, project_id):
    """查看项目详情"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _show():
        async with session_factory() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            p = result.scalar_one_or_none()

            if p is None:
                console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            table = Table(title=f"项目详情: {p.name}")
            table.add_column("属性", style="cyan")
            table.add_column("值", style="green")

            table.add_row("ID", str(p.id))
            table.add_row("名称", p.name)
            table.add_row("描述", p.description or "(无)")
            table.add_row("类型", p.source_type)
            table.add_row("来源", p.source_url)
            table.add_row("创建时间", p.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row("更新时间", p.updated_at.strftime("%Y-%m-%d %H:%M:%S"))

            console.print(table)

        await close_db(engine)

    try:
        asyncio.run(_show())
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1)


@project.command("delete")
@click.argument("project_id", type=int)
@click.option("--force", "-f", is_flag=True, help="跳过确认")
@click.pass_context
def project_delete(ctx, project_id, force):
    """删除项目及其所有文件"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    from reqradar.infrastructure.paths import get_paths
    from reqradar.web.services.project_file_service import ProjectFileService

    file_svc = ProjectFileService(get_paths(config)["projects"])

    async def _delete():
        async with session_factory() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            p = result.scalar_one_or_none()

            if p is None:
                console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            if not force:
                confirm = click.confirm(f"确定要删除项目 '{p.name}' 及其所有文件吗？")
                if not confirm:
                    console.print("[yellow]已取消[/yellow]")
                    await close_db(engine)
                    return

            try:
                file_svc.delete_project_files(p.name)
            except Exception as e:
                console.print(f"[yellow]⚠ 删除文件时出错: {e}[/yellow]")

            await session.delete(p)
            await session.commit()

            console.print(f"[green]✓[/green] 项目 '{p.name}' 已删除")

        await close_db(engine)

    try:
        asyncio.run(_delete())
    except Exception as e:
        console.print(f"[red]删除失败: {e}[/red]")
        raise SystemExit(1)


@project.command("index")
@click.argument("project_id", type=int)
@click.option("--build-profile/--no-build-profile", default=True, help="是否构建项目画像")
@click.pass_context
def project_index(ctx, project_id, build_profile):
    """为项目构建代码和文档索引"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _index():
        from reqradar.modules.code_parser import PythonCodeParser
        from reqradar.infrastructure.paths import get_paths
        from reqradar.web.services.project_file_service import ProjectFileService

        file_svc = ProjectFileService(get_paths(config)["projects"])

        async with session_factory() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            p = result.scalar_one_or_none()

            if p is None:
                console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            code_root = file_svc.detect_code_root(p.name)
            if not code_root.exists():
                console.print("[red]错误: 项目代码目录不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            index_path = file_svc.get_index_path(p.name)
            index_path.mkdir(parents=True, exist_ok=True)

            console.print(f"[cyan]开始为项目 '{p.name}' 构建索引...[/cyan]")

            console.print("[yellow]解析代码仓库...[/yellow]")
            parser = PythonCodeParser()
            code_graph = parser.parse_directory(code_root)

            code_graph_path = index_path / "code_graph.json"
            with open(code_graph_path, "w", encoding="utf-8") as f:
                f.write(code_graph.to_json())
            console.print(f"[green]✓[/green] 代码图谱已保存: {code_graph_path}")

            if build_profile and config.llm.api_key:
                console.print("[yellow]构建项目画像...[/yellow]")
                from reqradar.agent.project_profile import step_build_project_profile
                from reqradar.modules.llm_client import create_llm_client
                from reqradar.modules.project_memory import ProjectMemory

                memory_path = str(get_paths(config)["memories"])
                project_memory = ProjectMemory(storage_path=memory_path, project_id=p.id)

                llm_client = create_llm_client(
                    model=config.llm.model,
                    api_key=config.llm.api_key,
                    base_url=config.llm.base_url or "https://api.openai.com/v1",
                    timeout=config.llm.timeout,
                    max_retries=config.llm.max_retries,
                )

                try:
                    res = await step_build_project_profile(
                        code_graph=code_graph,
                        llm_client=llm_client,
                        project_memory=project_memory,
                        repo_path=str(code_root),
                    )
                    if res:
                        console.print("[green]✓[/green] 项目画像已构建")
                    else:
                        console.print("[yellow]⚠ 项目画像构建失败[/yellow]")
                except Exception as e:
                    console.print(f"[yellow]⚠ 项目画像构建出错: {e}[/yellow]")

            console.print(f"[bold green]项目 '{p.name}' 索引构建完成![/bold green]")

        await close_db(engine)

    try:
        asyncio.run(_index())
    except Exception as e:
        console.print(f"[red]索引构建失败: {e}[/red]")
        raise SystemExit(1)
