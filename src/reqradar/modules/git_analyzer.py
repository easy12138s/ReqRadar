"""Git 分析器 - 贡献者分析"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import git

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    git = None

from reqradar.core.exceptions import GitException


@dataclass
class Contributor:
    name: str
    email: str
    commit_count: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    last_modified: Optional[datetime] = None

    @property
    def score(self) -> float:
        recency = 0.0
        if self.last_modified:
            days_ago = (datetime.now() - self.last_modified).days
            recency = max(0.0, 1.0 - days_ago / 180)

        return (
            min(self.commit_count / 50, 1.0) * 0.4
            + min((self.lines_added + self.lines_deleted) / 1000, 1.0) * 0.3
            + recency * 0.3
        )


@dataclass
class FileContributor:
    file_path: str
    primary_contributor: Optional[Contributor] = None
    recent_contributors: list[Contributor] = field(default_factory=list)
    all_contributors: list[Contributor] = field(default_factory=list)


class GitAnalyzer:
    """Git 贡献者分析器"""

    def __init__(self, repo_path: Path, lookback_months: int = 6):
        if not GIT_AVAILABLE:
            raise ImportError("gitpython is not installed. Run: pip install gitpython")

        self.repo_path = Path(repo_path)
        self.lookback_date = datetime.now() - timedelta(days=lookback_months * 30)

        try:
            self.repo = git.Repo(self.repo_path)
        except git.InvalidGitRepositoryError:
            raise GitException(f"Not a valid git repository: {repo_path}")

    def get_file_contributors(self, file_paths: list[str]) -> list[FileContributor]:
        """获取文件贡献者信息"""
        results = []

        for file_path in file_paths:
            try:
                contributors = self._analyze_file(file_path)
                results.append(
                    FileContributor(
                        file_path=file_path,
                        primary_contributor=contributors[0] if contributors else None,
                        recent_contributors=contributors[:3],
                        all_contributors=contributors,
                    )
                )
            except GitException:
                results.append(FileContributor(file_path=file_path))

        return results

    def _analyze_file(self, file_path: str) -> list[Contributor]:
        """分析单个文件的贡献者"""
        contributor_stats = {}

        try:
            commits = list(self.repo.iter_commits(paths=file_path, since=self.lookback_date))
        except git.GitCommandError:
            return []

        for commit in commits:
            author = commit.author
            email = author.email

            if email not in contributor_stats:
                contributor_stats[email] = Contributor(
                    name=author.name,
                    email=email,
                )

            stats = contributor_stats[email]
            stats.commit_count += 1
            stats.lines_added += len(commit.stats.files.get(file_path, {}).get("insertions", 0))
            stats.lines_deleted += len(commit.stats.files.get(file_path, {}).get("deletions", 0))

            commit_time = datetime.fromtimestamp(commit.committed_date)
            if stats.last_modified is None or commit_time > stats.last_modified:
                stats.last_modified = commit_time

        contributors = list(contributor_stats.values())
        contributors.sort(key=lambda c: c.score, reverse=True)

        return contributors

    def get_module_maintainer(self, module_files: list[str]) -> Optional[Contributor]:
        """获取模块的主要维护者"""
        all_contributors: dict[str, Contributor] = {}

        for file_path in module_files:
            contributors = self._analyze_file(file_path)
            for c in contributors:
                if c.email not in all_contributors:
                    all_contributors[c.email] = Contributor(
                        name=c.name,
                        email=c.email,
                    )
                all_contributors[c.email].commit_count += c.commit_count
                all_contributors[c.email].lines_added += c.lines_added
                all_contributors[c.email].lines_deleted += c.lines_deleted
                if c.last_modified:
                    if (
                        all_contributors[c.email].last_modified is None
                        or c.last_modified > all_contributors[c.email].last_modified
                    ):
                        all_contributors[c.email].last_modified = c.last_modified

        if not all_contributors:
            return None

        contributors = list(all_contributors.values())
        contributors.sort(key=lambda c: c.score, reverse=True)

        return contributors[0]
