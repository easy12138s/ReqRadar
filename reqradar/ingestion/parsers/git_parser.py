"""Git 解析器 — git log 命令封装，提取提交历史结构化数据。"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from reqradar.kernel.exceptions import IngestionException

logger = logging.getLogger(__name__)


@dataclass
class GitCommitData:
    """Git 提交的结构化数据。"""

    commit_hash: str
    author: str
    author_email: str | None
    committed_at: datetime
    message: str
    changed_files: list[dict] = field(default_factory=list)  # [{path, additions, deletions}]


class GitParser:
    """git log 解析 — 仓库路径 → 提交历史列表。"""

    MAX_COMMITS: int = 1000

    def parse_repo(
        self, repo_path: Path, max_commits: int | None = None
    ) -> list[GitCommitData]:
        """解析 Git 仓库的提交历史。

        Args:
            repo_path: 仓库根目录路径（需包含 .git 目录）
            max_commits: 最大提交数限制

        Returns:
            GitCommitData 列表

        Raises:
            IngestionException: 仓库不合法或 git 命令执行失败
        """
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            raise IngestionException(
                f"目录不是 Git 仓库（无 .git 目录）: {repo_path}",
                detail={"repo_path": str(repo_path)},
            )

        limit = max_commits if max_commits is not None else self.MAX_COMMITS

        try:
            commits = self._get_commits(repo_path, limit)
        except subprocess.SubprocessError as e:
            raise IngestionException(
                f"git log 执行失败: {repo_path}",
                detail={"repo_path": str(repo_path), "error": str(e)},
            ) from e

        return commits

    def _get_commits(self, repo_path: Path, limit: int) -> list[GitCommitData]:
        """执行 git log 命令并解析输出。"""
        # 格式: hash|author|email|timestamp|message
        fmt = "%H|%an|%ae|%at|%s"
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "log",
                f"--pretty=format:{fmt}",
                "-n",
                str(limit),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        commits: list[GitCommitData] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) < 5:
                continue

            commit_hash = parts[0]
            author = parts[1]
            author_email = parts[2] if parts[2] else None
            committed_at = datetime.fromtimestamp(int(parts[3]))
            message = parts[4]

            # 获取文件变更统计
            changed_files = self._get_changed_files(repo_path, commit_hash)

            commits.append(
                GitCommitData(
                    commit_hash=commit_hash,
                    author=author,
                    author_email=author_email,
                    committed_at=committed_at,
                    message=message,
                    changed_files=changed_files,
                )
            )

        return commits

    def _get_changed_files(self, repo_path: Path, commit_hash: str) -> list[dict]:
        """获取单次提交的文件变更列表。"""
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "show",
                    "--numstat",
                    "--format=",
                    commit_hash,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            files: list[dict] = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    additions = int(parts[0]) if parts[0] != "-" else 0
                    deletions = int(parts[1]) if parts[1] != "-" else 0
                    files.append(
                        {
                            "path": parts[2],
                            "additions": additions,
                            "deletions": deletions,
                        }
                    )
            return files
        except subprocess.SubprocessError as e:
            logger.warning("获取文件变更失败: commit=%s, error=%s", commit_hash[:8], e)
            return []
