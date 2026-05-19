from click.testing import CliRunner

from reqradar.cli.main import cli


def test_cli_version():
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "version 0.8.0" in result.output.lower()


def test_config_init_creates_yaml_file(tmp_path, monkeypatch):
    import reqradar.cli.config as config_module

    source = tmp_path / ".reqradar.yaml.example"
    target = tmp_path / ".reqradar.yaml"
    source.write_text("web:\n  debug: true\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "YAML_EXAMPLE", source)
    monkeypatch.setattr(config_module, "YAML_TARGET", target)

    result = CliRunner().invoke(cli, ["config", "init"])

    assert result.exit_code == 0
    assert target.exists()


def test_config_init_does_not_overwrite_without_force(tmp_path, monkeypatch):
    import reqradar.cli.config as config_module

    target = tmp_path / ".reqradar.yaml"
    target.write_text("custom: true\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "YAML_TARGET", target)

    result = CliRunner().invoke(cli, ["config", "init"])

    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8") == "custom: true\n"
    assert "配置文件已存在" in result.output
