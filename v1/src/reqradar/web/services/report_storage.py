import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("reqradar.report_storage")


class ReportStorage:
    def __init__(self, reports_path: Path):
        self._root = reports_path

    def _task_dir(self, task_id: int) -> Path:
        return self._root / str(task_id)

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp).replace(path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    async def save_report(
        self,
        task_id: int,
        markdown: str,
        html: str,
        context: Optional[dict] = None,
    ) -> tuple[str, str]:
        task_dir = self._task_dir(task_id)
        md_path = task_dir / "report.md"
        html_path = task_dir / "report.html"
        self._atomic_write(md_path, markdown)
        self._atomic_write(html_path, html)
        if context is not None:
            ctx_path = task_dir / "context.json"
            self._atomic_write(
                ctx_path, json.dumps(context, ensure_ascii=False, indent=2, default=str)
            )
        rel_md = f"{task_id}/report.md"
        rel_html = f"{task_id}/report.html"
        return rel_md, rel_html

    async def save_version(
        self,
        task_id: int,
        version: int,
        markdown: str,
        html: str,
        context: Optional[dict] = None,
    ) -> tuple[str, str]:
        versions_dir = self._task_dir(task_id) / "versions"
        md_path = versions_dir / f"v{version}.md"
        html_path = versions_dir / f"v{version}.html"
        self._atomic_write(md_path, markdown)
        self._atomic_write(html_path, html)
        if context is not None:
            ctx_path = versions_dir / f"v{version}_context.json"
            self._atomic_write(
                ctx_path, json.dumps(context, ensure_ascii=False, indent=2, default=str)
            )
        rel_md = f"{task_id}/versions/v{version}.md"
        rel_html = f"{task_id}/versions/v{version}.html"
        return rel_md, rel_html

    async def read_report(self, task_id: int) -> tuple[Optional[str], Optional[str]]:
        task_dir = self._task_dir(task_id)
        md_path = task_dir / "report.md"
        html_path = task_dir / "report.html"
        md = md_path.read_text(encoding="utf-8") if md_path.exists() else None
        html = html_path.read_text(encoding="utf-8") if html_path.exists() else None
        return md, html

    async def read_version(self, task_id: int, version: int) -> tuple[Optional[str], Optional[str]]:
        versions_dir = self._task_dir(task_id) / "versions"
        md_path = versions_dir / f"v{version}.md"
        html_path = versions_dir / f"v{version}.html"
        md = md_path.read_text(encoding="utf-8") if md_path.exists() else None
        html = html_path.read_text(encoding="utf-8") if html_path.exists() else None
        return md, html

    async def delete_task_reports(self, task_id: int) -> None:
        task_dir = self._task_dir(task_id)
        if task_dir.exists():
            shutil.rmtree(task_dir)
            logger.info("Deleted report files for task %d", task_id)

    async def delete_version_files(self, task_id: int, version: int) -> None:
        versions_dir = self._task_dir(task_id) / "versions"
        md_path = versions_dir / f"v{version}.md"
        html_path = versions_dir / f"v{version}.html"
        ctx_path = versions_dir / f"v{version}_context.json"
        for p in (md_path, html_path, ctx_path):
            p.unlink(missing_ok=True)

    async def delete_project_reports(self, project_id: int, db) -> None:
        from sqlalchemy import select
        from reqradar.web.models import AnalysisTask

        result = await db.execute(
            select(AnalysisTask.id).where(AnalysisTask.project_id == project_id)
        )
        task_ids = [row[0] for row in result.all()]
        for tid in task_ids:
            await self.delete_task_reports(tid)
