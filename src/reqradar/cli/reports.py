"""CLI 报告管理命令"""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from reqradar.cli.utils import get_db_session, close_db
from reqradar.infrastructure.paths import get_paths
from reqradar.web.models import AnalysisTask, Report, ReportVersion

console = Console()


@click.group()
def report():
    """报告管理"""
    pass


@report.command("get")
@click.argument("task_id", type=int)
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["markdown", "html", "json"]),
    default="markdown",
    help="输出格式",
)
@click.option(
    "--output", "-o", type=click.Path(), default=None, help="输出文件路径（默认输出到终端）"
)
@click.pass_context
def report_get(ctx, task_id, fmt, output):
    """获取分析报告"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)
    paths = get_paths(config)
    from reqradar.web.services.report_storage import ReportStorage

    report_storage = ReportStorage(paths["reports"])

    async def _get():
        async with session_factory() as session:
            task_result = await session.execute(
                select(AnalysisTask).where(AnalysisTask.id == task_id)
            )
            task = task_result.scalar_one_or_none()

            if task is None:
                console.print(f"[red]错误: 任务 ID {task_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            if task.status != "completed":
                console.print(f"[red]错误: 任务状态为 '{task.status}'，尚未生成报告[/red]")
                await close_db(engine)
                raise SystemExit(1)

            report_result = await session.execute(select(Report).where(Report.task_id == task_id))
            report = report_result.scalar_one_or_none()

            if report is None:
                console.print("[red]错误: 报告不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            if fmt == "markdown":
                content = report.content_markdown
                file_md, file_html = await report_storage.read_report(task_id)
                if file_md is not None:
                    content = file_md
            elif fmt == "html":
                content = report.content_html
                file_md, file_html = await report_storage.read_report(task_id)
                if file_html is not None:
                    content = file_html
            else:
                content = json.dumps(task.context_json, ensure_ascii=False, indent=2)

            if output:
                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding="utf-8")
                console.print(f"[green]✓[/green] 报告已保存到: {output_path}")
            else:
                console.print(content)

        await close_db(engine)

    try:
        asyncio.run(_get())
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]获取失败: {e}[/red]")
        raise SystemExit(1)


@report.command("versions")
@click.argument("task_id", type=int)
@click.pass_context
def report_versions(ctx, task_id):
    """列出报告版本"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _versions():
        async with session_factory() as session:
            task_result = await session.execute(
                select(AnalysisTask).where(AnalysisTask.id == task_id)
            )
            task = task_result.scalar_one_or_none()

            if task is None:
                console.print(f"[red]错误: 任务 ID {task_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            result = await session.execute(
                select(ReportVersion)
                .where(ReportVersion.task_id == task_id)
                .order_by(ReportVersion.version_number.desc())
            )
            versions = result.scalars().all()

            if not versions:
                console.print("[yellow]暂无报告版本[/yellow]")
                await close_db(engine)
                return

            table = Table(title=f"报告版本列表 (任务 #{task_id})")
            table.add_column("版本号", style="cyan")
            table.add_column("触发类型", style="green")
            table.add_column("描述")
            table.add_column("创建时间")

            for v in versions:
                current_marker = " ← 当前" if v.version_number == task.current_version else ""
                table.add_row(
                    f"v{v.version_number}{current_marker}",
                    v.trigger_type,
                    (v.trigger_description[:40] or ""),
                    v.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)

        await close_db(engine)

    try:
        asyncio.run(_versions())
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1)


@report.command("evidence")
@click.argument("task_id", type=int)
@click.option("--version", "-v", type=int, default=None, help="版本号（默认当前版本）")
@click.option("--evidence-id", "-e", default=None, help="查看特定证据详情")
@click.pass_context
def report_evidence(ctx, task_id, version, evidence_id):
    """查看证据链"""
    config = ctx.obj["config"]
    engine, session_factory = get_db_session(config)

    async def _evidence():
        async with session_factory() as session:
            task_result = await session.execute(
                select(AnalysisTask).where(AnalysisTask.id == task_id)
            )
            task = task_result.scalar_one_or_none()

            if task is None:
                console.print(f"[red]错误: 任务 ID {task_id} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            version_num = version or task.current_version or 1

            version_result = await session.execute(
                select(ReportVersion).where(
                    ReportVersion.task_id == task_id,
                    ReportVersion.version_number == version_num,
                )
            )
            ver = version_result.scalar_one_or_none()

            if ver is None:
                console.print(f"[red]错误: 版本 v{version_num} 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            evidence_list = (
                ver.context_snapshot.get("evidence_list", []) if ver.context_snapshot else []
            )

            if not evidence_list:
                console.print("[yellow]暂无证据[/yellow]")
                await close_db(engine)
                return

            if evidence_id:
                for ev in evidence_list:
                    if ev.get("id") == evidence_id:
                        table = Table(title=f"证据详情: {evidence_id}")
                        table.add_column("属性", style="cyan")
                        table.add_column("值", style="green")
                        table.add_row("ID", ev.get("id", ""))
                        table.add_row("类型", ev.get("type", ""))
                        table.add_row("来源", ev.get("source", ""))
                        table.add_row("置信度", ev.get("confidence", ""))
                        table.add_row("关联维度", ", ".join(ev.get("dimensions", [])))
                        table.add_row("内容", (ev.get("content", "") or "")[:500])
                        console.print(table)
                        await close_db(engine)
                        return
                console.print(f"[red]错误: 证据 ID '{evidence_id}' 不存在[/red]")
                await close_db(engine)
                raise SystemExit(1)

            table = Table(title=f"证据链 (任务 #{task_id}, 版本 v{version_num})")
            table.add_column("ID", style="cyan")
            table.add_column("类型", style="green")
            table.add_column("来源", style="yellow")
            table.add_column("置信度")
            table.add_column("维度")

            for ev in evidence_list:
                table.add_row(
                    (ev.get("id", "") or "")[:12],
                    ev.get("type", ""),
                    (ev.get("source", "") or "")[:30],
                    ev.get("confidence", ""),
                    ", ".join(ev.get("dimensions", []))[:30],
                )

            console.print(table)

        await close_db(engine)

    try:
        asyncio.run(_evidence())
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]查询失败: {e}[/red]")
        raise SystemExit(1)
