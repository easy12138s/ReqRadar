"""CLI 集成测试"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from reqradar.cli.main import cli
from reqradar.cli.main import _build_quality_overview_rows
from reqradar.core.context import AnalysisContext, DeepAnalysis, GeneratedContent, RequirementUnderstanding, StepResult


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


class TestCliQualityOverview:
    def test_build_quality_overview_rows_uses_three_dimensions(self):
        ctx = AnalysisContext(requirement_path=Path("test.md"))
        ctx.understanding = RequirementUnderstanding(summary="Test summary")
        ctx.deep_analysis = DeepAnalysis(
            risk_level="medium",
            impact_narrative="Affects API layer.",
        )
        ctx.generated_content = GeneratedContent(
            requirement_understanding="Detailed understanding",
            executive_summary="Proceed in stages.",
            technical_summary="Touches API and orchestration.",
        )
        ctx.store_result("extract", StepResult(step="extract", success=True, confidence=0.9))
        ctx.store_result("analyze", StepResult(step="analyze", success=False, confidence=0.2))

        rows = _build_quality_overview_rows(ctx)

        assert rows == [
            ("流程完成度", "partial"),
            ("内容完整度", "full"),
            ("证据支撑度", "low"),
            ("步骤完成", "1/2"),
        ]
