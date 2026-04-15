"""CLI 集成测试"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from reqradar.cli.main import cli


class TestCliIndex:
    def test_index_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["index", "--help"])
        assert result.exit_code == 0
        assert "代码仓库路径" in result.output

    def test_index_requires_repo_path(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["index"])
        assert result.exit_code != 0


class TestCliAnalyze:
    def test_analyze_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "需求文件" in result.output or "REQUIREMENT_FILE" in result.output

    def test_analyze_requires_file(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze"])
        assert result.exit_code != 0

    def test_analyze_nonexistent_file(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "/nonexistent/file.md"])
        assert result.exit_code != 0


class TestCliVersion:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output
