import logging
import os
import shutil
import zipfile
from pathlib import Path

from reqradar.infrastructure.config import WebConfig

logger = logging.getLogger("reqradar.web.services.project_file_service")

VALID_SOURCE_TYPES = {"zip", "git", "local"}


class ProjectFileService:
    def __init__(self, web_config: WebConfig):
        self._data_root = Path(os.path.expanduser(web_config.data_root))

    def get_project_path(self, name: str) -> Path:
        return self._data_root / name

    def get_index_path(self, name: str) -> Path:
        return self.get_project_path(name) / "index"

    def get_memory_path(self, name: str) -> Path:
        return self.get_project_path(name) / "memory"

    def get_requirements_path(self, name: str) -> Path:
        return self.get_project_path(name) / "requirements"

    def create_project_dirs(self, name: str) -> None:
        base = self.get_project_path(name)
        for subdir in ("project_code", "requirements", "index", "memory"):
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def extract_zip(self, name: str, zip_bytes: bytes) -> None:
        base = self.get_project_path(name)
        code_dir = base / "project_code"
        zip_backup = base / "project.zip"
        zip_backup.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_backup) as zf:
            zf.extractall(code_dir)

        logger.info("Extracted zip for project '%s' to %s", name, code_dir)

    def clone_git(self, name: str, url: str, branch: str | None = None) -> None:
        if not self.is_git_available():
            raise RuntimeError("Git is not available on this system. Use ZIP upload instead.")

        base = self.get_project_path(name)
        code_dir = base / "project_code"

        cmd = ["git", "clone", url, str(code_dir)]
        if branch:
            cmd = ["git", "clone", "--branch", branch, url, str(code_dir)]

        import subprocess

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        logger.info("Cloned git repo for project '%s' from %s", name, url)

    def detect_code_root(self, name: str) -> Path:
        code_dir = self.get_project_path(name) / "project_code"
        if not code_dir.exists():
            return code_dir

        entries = list(code_dir.iterdir())
        dirs = [e for e in entries if e.is_dir()]
        files = [e for e in entries if e.is_file()]

        if len(dirs) == 1 and len(files) == 0:
            return dirs[0]

        return code_dir

    def delete_project_files(self, name: str) -> None:
        project_path = self.get_project_path(name)
        if project_path.exists():
            shutil.rmtree(project_path)
            logger.info("Deleted project files for '%s'", name)

    def get_file_tree(self, name: str) -> list[dict]:
        base = self.get_project_path(name)
        if not base.exists():
            return []

        def _build_tree(path: Path, relative: str = "") -> list[dict]:
            items = []
            try:
                for entry in sorted(path.iterdir()):
                    entry_rel = f"{relative}/{entry.name}" if relative else entry.name
                    if entry.is_dir():
                        children = _build_tree(entry, entry_rel)
                        items.append(
                            {
                                "name": entry.name,
                                "path": entry_rel,
                                "type": "directory",
                                "children": children,
                            }
                        )
                    else:
                        items.append(
                            {
                                "name": entry.name,
                                "path": entry_rel,
                                "type": "file",
                                "size": entry.stat().st_size,
                            }
                        )
            except PermissionError:
                pass
            return items

        return _build_tree(base)

    @staticmethod
    def is_git_available() -> bool:
        return shutil.which("git") is not None
