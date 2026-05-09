import logging
import os
import platform
import re
import shutil
import subprocess
import zipfile
from pathlib import Path


logger = logging.getLogger("reqradar.web.services.project_file_service")

VALID_SOURCE_TYPES = {"zip", "git", "local"}
PROJECT_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_EXTRACTED_SIZE = 500 * 1024 * 1024
ALLOWED_GIT_URL_SCHEMES = {"https://", "ssh://", "git@", "http://"}


class ProjectFileService:
    def __init__(self, projects_path: Path):
        self._data_root = Path(projects_path).expanduser()

    def _validate_project_name(self, name: str) -> None:
        if not PROJECT_NAME_RE.match(name):
            raise ValueError(f"Invalid project name: {name!r}")

    def get_project_path(self, name: str) -> Path:
        self._validate_project_name(name)
        return self._data_root / name

    def get_index_path(self, name: str) -> Path:
        return self.get_project_path(name) / "index"

    def get_requirements_path(self, name: str) -> Path:
        return self.get_project_path(name) / "requirements"

    def create_project_dirs(self, name: str) -> None:
        base = self.get_project_path(name)
        for subdir in ("project_code", "requirements", "index"):
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def extract_zip(self, name: str, zip_bytes: bytes) -> None:
        base = self.get_project_path(name)
        code_dir = base / "project_code"
        zip_backup = base / "project.zip"
        zip_backup.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_backup) as zf:
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_EXTRACTED_SIZE:
                raise ValueError(
                    f"Zip contents too large: {total_size} bytes (max {MAX_EXTRACTED_SIZE})"
                )

            for member in zf.infolist():
                target = (code_dir / member.filename).resolve()
                if not str(target).startswith(str(code_dir.resolve())):
                    raise ValueError(f"Zip path traversal detected: {member.filename}")

            zf.extractall(code_dir)

        logger.info("Extracted zip for project '%s' to %s", name, code_dir)

    def clone_git(self, name: str, url: str, branch: str | None = None) -> None:
        if not self.is_git_available():
            raise RuntimeError("Git is not available on this system. Use ZIP upload instead.")

        if not any(url.startswith(scheme) for scheme in ALLOWED_GIT_URL_SCHEMES):
            raise ValueError(f"Git URL scheme not allowed: {url!r}")

        base = self.get_project_path(name)
        code_dir = base / "project_code"

        cmd = ["git", "clone", url, str(code_dir)]
        if branch:
            cmd = ["git", "clone", "--branch", branch, url, str(code_dir)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Git clone timed out after 300s: {url}") from e

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
        resolved = project_path.resolve()
        if not str(resolved).startswith(str(self._data_root.resolve())):
            raise ValueError(f"Project path escapes data root: {name!r}")
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
                    if entry.is_symlink():
                        continue
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
                logger.debug("Permission denied reading %s", path)
            return items

        return _build_tree(base)

    ALLOWED_LOCAL_PREFIXES = (
        "/home/",
        "/opt/",
        "/srv/",
        "/data/",
        "/var/lib/",
        "/Users/",
        "/workspace/",
        "/tmp",
    )

    @classmethod
    def _get_allowed_local_prefixes(cls) -> tuple[str, ...]:
        prefixes = list(cls.ALLOWED_LOCAL_PREFIXES)
        if platform.system() == "Windows":
            user_profile = os.environ.get("USERPROFILE", "")
            if user_profile:
                prefixes.append(user_profile.replace("\\", "/") + "/")
            home_drive = os.environ.get("HOMEDRIVE", "")
            if home_drive:
                prefixes.append(home_drive.replace("\\", "/"))
            for drive in ("C:", "D:", "E:"):
                prefixes.append(f"/{drive}/")
                prefixes.append(f"{drive}/")
            prefixes.append("/Users/")
        return tuple(prefixes)

    def validate_local_path(self, local_path: str) -> Path:
        p = Path(local_path).resolve()
        if not p.exists():
            raise ValueError(f"Local path does not exist: {local_path}")
        if not p.is_dir():
            raise ValueError(f"Local path is not a directory: {local_path}")
        resolved_str = str(p).replace("\\", "/") + "/"
        allowed_prefixes = self._get_allowed_local_prefixes()
        if not any(resolved_str.startswith(prefix) for prefix in allowed_prefixes):
            raise ValueError(
                f"Local path must be under one of: {', '.join(allowed_prefixes)}. Got: {local_path}"
            )
        return p

    @staticmethod
    def is_git_available() -> bool:
        return shutil.which("git") is not None
