from click.testing import CliRunner

from reqradar.cli.main import cli


def test_requirement_preprocess_rejects_missing_files():
    result = CliRunner().invoke(cli, ["requirement", "preprocess", "--project-id", "1", "--no-wait"])

    assert result.exit_code == 1
    assert "没有找到有效的需求文件" in result.output
