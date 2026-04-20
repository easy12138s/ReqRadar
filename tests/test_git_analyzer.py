import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from reqradar.core.exceptions import GitException
from reqradar.modules.git_analyzer import Contributor, FileContributor, GitAnalyzer


def _create_test_repo(repo_dir: Path, files_and_commits: list[tuple[str, str, str]]):
    """Create a temp git repo with commits.

    Args:
        repo_dir: Path where the repo is created.
        files_and_commits: List of (file_path, content, commit_message).
    """
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    for file_path, content, message in files_and_commits:
        full_path = repo_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        subprocess.run(["git", "add", file_path], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )


class TestGitAnalyzerInit:
    def test_init_with_valid_repo(self, tmp_path):
        _create_test_repo(tmp_path, [("hello.py", "print('hi')", "initial commit")])
        analyzer = GitAnalyzer(tmp_path)
        assert analyzer.repo_path == tmp_path

    def test_init_with_invalid_path_raises_git_exception(self, tmp_path):
        not_a_repo = tmp_path / "nonexistent"
        not_a_repo.mkdir()
        with pytest.raises(GitException, match="Not a valid git repository"):
            GitAnalyzer(not_a_repo)

    def test_init_lookback_default(self, tmp_path):
        _create_test_repo(tmp_path, [("f.py", "x=1", "init")])
        analyzer = GitAnalyzer(tmp_path)
        expected = datetime.now() - __import__("datetime").timedelta(days=6 * 30)
        assert abs((analyzer.lookback_date - expected).total_seconds()) < 5

    def test_init_custom_lookback(self, tmp_path):
        _create_test_repo(tmp_path, [("f.py", "x=1", "init")])
        analyzer = GitAnalyzer(tmp_path, lookback_months=3)
        expected = datetime.now() - __import__("datetime").timedelta(days=3 * 30)
        assert abs((analyzer.lookback_date - expected).total_seconds()) < 5


class TestGetFileContributors:
    def test_single_file_single_contributor(self, tmp_path):
        _create_test_repo(
            tmp_path,
            [
                ("main.py", "print('hello')", "add main"),
                ("main.py", "print('hello')\nprint('world')", "update main"),
            ],
        )
        analyzer = GitAnalyzer(tmp_path)
        results = analyzer.get_file_contributors(["main.py"])
        assert len(results) == 1
        fc = results[0]
        assert isinstance(fc, FileContributor)
        assert fc.file_path == "main.py"
        assert fc.primary_contributor is not None
        assert fc.primary_contributor.name == "Test User"
        assert fc.primary_contributor.email == "test@test.com"
        assert fc.primary_contributor.commit_count == 2

    def test_multiple_files(self, tmp_path):
        _create_test_repo(
            tmp_path,
            [
                ("a.py", "x=1", "add a"),
                ("b.py", "y=2", "add b"),
            ],
        )
        analyzer = GitAnalyzer(tmp_path)
        results = analyzer.get_file_contributors(["a.py", "b.py"])
        assert len(results) == 2
        paths = {r.file_path for r in results}
        assert "a.py" in paths
        assert "b.py" in paths

    def test_nonexistent_file_returns_empty_contributors(self, tmp_path):
        _create_test_repo(tmp_path, [("real.py", "x=1", "init")])
        analyzer = GitAnalyzer(tmp_path)
        results = analyzer.get_file_contributors(["nonexistent.py"])
        assert len(results) == 1
        fc = results[0]
        assert fc.file_path == "nonexistent.py"
        assert fc.primary_contributor is None
        assert fc.all_contributors == []

    def test_recent_contributors_capped_at_three(self, tmp_path):
        commits = [("f.py", f"x={i}", f"commit {i}") for i in range(5)]
        _create_test_repo(tmp_path, commits)
        analyzer = GitAnalyzer(tmp_path)
        results = analyzer.get_file_contributors(["f.py"])
        fc = results[0]
        assert len(fc.recent_contributors) <= 3


class TestGetModuleMaintainer:
    def test_returns_top_contributor(self, tmp_path):
        _create_test_repo(
            tmp_path,
            [
                ("mod/a.py", "x=1", "add a"),
                ("mod/b.py", "y=2", "add b"),
                ("mod/a.py", "x=1\nz=3", "update a"),
            ],
        )
        analyzer = GitAnalyzer(tmp_path)
        maintainer = analyzer.get_module_maintainer(["mod/a.py", "mod/b.py"])
        assert maintainer is not None
        assert isinstance(maintainer, Contributor)
        assert maintainer.email == "test@test.com"

    def test_returns_none_for_no_contributors(self, tmp_path):
        _create_test_repo(tmp_path, [("real.py", "x=1", "init")])
        analyzer = GitAnalyzer(tmp_path)
        maintainer = analyzer.get_module_maintainer(["nonexistent.py"])
        assert maintainer is None


class TestContributorScore:
    def test_score_with_no_activity(self):
        c = Contributor(name="A", email="a@test.com")
        assert c.score == pytest.approx(0.0)

    def test_score_with_recent_activity(self):
        c = Contributor(
            name="A",
            email="a@test.com",
            commit_count=50,
            lines_added=1000,
            lines_deleted=0,
            last_modified=datetime.now(),
        )
        assert 0.0 < c.score <= 1.0

    def test_score_components(self):
        c = Contributor(
            name="A",
            email="a@test.com",
            commit_count=25,
            lines_added=500,
            lines_deleted=500,
            last_modified=datetime.now(),
        )
        expected = min(25 / 50, 1.0) * 0.4 + min(1000 / 1000, 1.0) * 0.3 + 1.0 * 0.3
        assert c.score == pytest.approx(expected)

    def test_score_recency_decay(self):
        old = Contributor(
            name="Old",
            email="old@test.com",
            commit_count=50,
            lines_added=1000,
            lines_deleted=0,
            last_modified=datetime.now() - __import__("datetime").timedelta(days=90),
        )
        recent = Contributor(
            name="Recent",
            email="recent@test.com",
            commit_count=50,
            lines_added=1000,
            lines_deleted=0,
            last_modified=datetime.now(),
        )
        assert recent.score > old.score


class TestMultipleContributors:
    def test_different_authors_tracked_separately(self, tmp_path):
        _create_test_repo(tmp_path, [("f.py", "x=1", "first commit")])

        subprocess.run(
            ["git", "config", "user.email", "other@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Other User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "f.py").write_text("x=2")
        subprocess.run(["git", "add", "f.py"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "second commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        analyzer = GitAnalyzer(tmp_path)
        results = analyzer.get_file_contributors(["f.py"])
        fc = results[0]
        assert len(fc.all_contributors) == 2
        emails = {c.email for c in fc.all_contributors}
        assert "test@test.com" in emails
        assert "other@test.com" in emails
