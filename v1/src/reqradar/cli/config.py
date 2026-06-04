"""CLI 配置管理命令"""

import asyncio
import shutil
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from reqradar.cli.utils import close_db, get_db_session
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.models import ProjectConfig, SystemConfig, UserConfig

console = Console()

YAML_EXAMPLE = Path(__file__).resolve().parent.parent.parent.parent / ".reqradar.yaml.example"
YAML_TARGET = Path.cwd() / ".reqradar.yaml"


@click.group()
def config():
    """配置管理"""
    pass


@config.command("init")
@click.option("--force", "-f", is_flag=True, help="覆盖已有配置文件")
def config_init(force):
    """生成默认 .reqradar.yaml 配置文件"""
    if not YAML_EXAMPLE.exists():
        console.print("[red]错误: 找不到 .reqradar.yaml.example 模板文件[/red]")
        raise SystemExit(1)

    if YAML_TARGET.exists() and not force:
        console.print(f"[yellow]配置文件已存在: {YAML_TARGET}[/yellow]")
        console.print("使用 --force 覆盖")
        return

    shutil.copy2(str(YAML_EXAMPLE), str(YAML_TARGET))
    console.print(f"[green]✓[/green] 配置文件已生成: {YAML_TARGET}")

    if YAML_TARGET.exists():
        with open(YAML_TARGET, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _print_yaml_summary(data)


@config.command("list")
@click.option(
    "--scope", type=click.Choice(["user", "system", "all"]), default="all", help="配置层级"
)
@click.pass_context
def config_list(ctx, scope):
    """列出配置项"""
    config_obj = ctx.obj["config"]
    engine, session_factory = get_db_session(config_obj)

    async def _list():
        async with session_factory() as session:
            rows = []

            if scope in ("user", "all"):
                result = await session.execute(
                    select(UserConfig)
                    .where(UserConfig.user_id == 1)
                    .order_by(UserConfig.config_key)
                )
                for r in result.scalars().all():
                    value = (
                        ConfigManager._mask_sensitive(r.config_value)
                        if r.is_sensitive
                        else r.config_value
                    )
                    rows.append(("user", r.config_key, value, r.value_type, r.updated_at))

            if scope in ("system", "all"):
                result = await session.execute(
                    select(SystemConfig).order_by(SystemConfig.config_key)
                )
                for r in result.scalars().all():
                    value = (
                        ConfigManager._mask_sensitive(r.config_value)
                        if r.is_sensitive
                        else r.config_value
                    )
                    rows.append(("system", r.config_key, value, r.value_type, r.updated_at))

            if not rows:
                console.print("[yellow]暂无配置项[/yellow]")
                await close_db(engine)
                return

            table = Table(title="配置列表")
            table.add_column("层级", style="cyan")
            table.add_column("键", style="green")
            table.add_column("值")
            table.add_column("类型", style="yellow")
            table.add_column("更新时间")

            for scope_name, key, value, vtype, updated in rows:
                table.add_row(
                    scope_name,
                    key,
                    str(value)[:60],
                    vtype,
                    updated.strftime("%Y-%m-%d %H:%M") if updated else "",
                )

            console.print(table)

        await close_db(engine)

    try:
        asyncio.run(_list())
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1) from None


@config.command("get")
@click.argument("key")
@click.option("--project-id", "-p", type=int, default=None, help="项目 ID (用于项目级解析)")
@click.pass_context
def config_get(ctx, key, project_id):
    """查看配置值 (按优先级解析)"""
    config_obj = ctx.obj["config"]
    engine, session_factory = get_db_session(config_obj)

    async def _get():
        async with session_factory() as session:
            cm = ConfigManager(session, config_obj)

            source = await _resolve_source(cm, key, user_id=1, project_id=project_id)
            value = await cm.get(key, user_id=1, project_id=project_id)

            if value is None:
                console.print(f"[yellow]配置 '{key}' 未设置[/yellow]")
                await close_db(engine)
                return

            table = Table(title=f"配置: {key}")
            table.add_column("属性", style="cyan")
            table.add_column("值", style="green")

            table.add_row("键", key)
            table.add_row("值", str(value))
            table.add_row("来源", source)

            console.print(table)

        await close_db(engine)

    try:
        asyncio.run(_get())
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1) from None


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--scope", type=click.Choice(["user", "system"]), default="user", help="配置层级")
@click.option(
    "--type",
    "value_type",
    type=click.Choice(["string", "integer", "float", "boolean", "json"]),
    default=None,
    help="值类型",
)
@click.option("--sensitive", is_flag=True, help="标记为敏感值")
@click.pass_context
def config_set(ctx, key, value, scope, value_type, sensitive):
    """设置配置值"""
    config_obj = ctx.obj["config"]
    engine, session_factory = get_db_session(config_obj)

    async def _set():
        async with session_factory() as session:
            cm = ConfigManager(session, config_obj)

            if scope == "user":
                await cm.set_user(1, key, value, value_type=value_type, is_sensitive=sensitive)
            else:
                await cm.set_system(key, value, value_type=value_type, is_sensitive=sensitive)

            scope_label = "用户级" if scope == "user" else "系统级"
            console.print(f"[green]✓[/green] {scope_label}配置已设置: {key} = {value}")

        await close_db(engine)

    try:
        asyncio.run(_set())
    except Exception as e:
        console.print(f"[red]设置失败: {e}[/red]")
        raise SystemExit(1) from None


@config.command("delete")
@click.argument("key")
@click.option("--scope", type=click.Choice(["user", "system"]), default="user", help="配置层级")
@click.pass_context
def config_delete(ctx, key, scope):
    """删除配置项"""
    config_obj = ctx.obj["config"]
    engine, session_factory = get_db_session(config_obj)

    async def _delete():
        async with session_factory() as session:
            cm = ConfigManager(session, config_obj)

            if scope == "user":
                deleted = await cm.delete_user(1, key)
            else:
                deleted = await cm.delete_system(key)

            if not deleted:
                scope_label = "用户级" if scope == "user" else "系统级"
                console.print(f"[red]错误: {scope_label}配置 '{key}' 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            scope_label = "用户级" if scope == "user" else "系统级"
            console.print(f"[green]✓[/green] {scope_label}配置已删除: {key}")

        await close_db(engine)

    try:
        asyncio.run(_delete())
    except Exception as e:
        console.print(f"[red]删除失败: {e}[/red]")
        raise SystemExit(1) from None


async def _resolve_source(
    cm: ConfigManager, key: str, *, user_id: int = 1, project_id: int | None = None
) -> str:
    """判断配置值的来源层级"""
    result = await cm._db.execute(
        select(UserConfig).where(UserConfig.user_id == user_id, UserConfig.config_key == key)
    )
    if result.scalar_one_or_none():
        return "user"

    if project_id is not None:
        result = await cm._db.execute(
            select(ProjectConfig).where(
                ProjectConfig.project_id == project_id, ProjectConfig.config_key == key
            )
        )
        if result.scalar_one_or_none():
            return "project"

    result = await cm._db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    if result.scalar_one_or_none():
        return "system"

    if cm._get_from_file(key) is not None:
        return "file"

    return "default"


def _print_yaml_summary(data: dict, prefix: str = ""):
    for k, v in data.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            _print_yaml_summary(v, full_key)
        else:
            console.print(f"  [cyan]{full_key}[/cyan]: {v}")
