"""
Data migration: Move report content from DB columns to file storage.

Usage:
    python -m reqradar.infrastructure.migrate_report_files --config .reqradar.yaml

This script:
1. Reads all Report and ReportVersion rows with non-empty content_markdown/content_html
2. Writes content to files via ReportStorage
3. Updates markdown_path/html_path columns in the DB
4. Does NOT drop the old columns (that requires a separate Alembic migration)
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from reqradar.infrastructure.config import load_config
from reqradar.infrastructure.paths import get_paths
from reqradar.web.database import create_engine, create_session_factory
from reqradar.web.models import Report, ReportVersion
from reqradar.web.services.report_storage import ReportStorage


async def migrate_reports(session_factory, report_storage: ReportStorage):
    async with session_factory() as session:
        result = await session.execute(
            select(Report).where((Report.content_markdown != "") | (Report.content_html != ""))
        )
        reports = result.scalars().all()
        count = 0
        for report in reports:
            if report.content_markdown or report.content_html:
                md, html, rel_md, rel_html = report.content_markdown, report.content_html, "", ""
                rel_md, rel_html = await report_storage.save_report(
                    report.task_id,
                    md or "",
                    html or "",
                )
                report.markdown_path = rel_md
                report.html_path = rel_html
                count += 1
        await session.commit()
        print(f"Migrated {count} Report rows to files")


async def migrate_report_versions(session_factory, report_storage: ReportStorage):
    async with session_factory() as session:
        result = await session.execute(
            select(ReportVersion).where(
                (ReportVersion.content_markdown != "") | (ReportVersion.content_html != "")
            )
        )
        versions = result.scalars().all()
        count = 0
        for version in versions:
            if version.content_markdown or version.content_html:
                md, html = version.content_markdown, version.content_html
                rel_md, rel_html = await report_storage.save_version(
                    version.task_id,
                    version.version_number,
                    md or "",
                    html or "",
                )
                version.markdown_path = rel_md
                version.html_path = rel_html
                count += 1
        await session.commit()
        print(f"Migrated {count} ReportVersion rows to files")


async def main(config_path=None):
    config = load_config(config_path)
    paths = get_paths(config)

    from reqradar.infrastructure.paths import ensure_dirs

    ensure_dirs(paths)

    report_storage = ReportStorage(paths["reports"])
    db_url = config.web.database_url or str(paths["db"] / "reqradar.db")

    engine = create_engine(db_url)
    session_factory = create_session_factory(engine)

    try:
        await migrate_reports(session_factory, report_storage)
        await migrate_report_versions(session_factory, report_storage)
        print("Migration complete.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate report content from DB to files")
    parser.add_argument("--config", default=None, help="Path to .reqradar.yaml config file")
    args = parser.parse_args()
    asyncio.run(main(args.config))
