import pytest
from pathlib import Path

from reqradar.infrastructure.template_loader import TemplateLoader, TemplateDefinition, SectionDefinition


def test_load_default_template():
    loader = TemplateLoader()
    template_dir = Path(__file__).parent.parent / "src" / "reqradar" / "templates"
    defn = loader.load_definition(template_dir / "default_report.yaml")
    assert defn.name == "默认企业级报告模板"
    assert len(defn.sections) == 8
    assert defn.sections[0].id == "requirement_understanding"
    assert defn.sections[0].required is True


def test_section_dimensions():
    loader = TemplateLoader()
    template_dir = Path(__file__).parent.parent / "src" / "reqradar" / "templates"
    defn = loader.load_definition(template_dir / "default_report.yaml")
    impact_section = next(s for s in defn.sections if s.id == "impact_analysis")
    assert "impact" in impact_section.dimensions
    assert "change" in impact_section.dimensions


def test_render_with_template(tmp_path):
    loader = TemplateLoader()
    render_template = "# {{ requirement_title }}\n\n## 执行摘要\n\n{{ executive_summary }}"
    report_data = {
        "requirement_title": "Test Requirement",
        "executive_summary": "This is a test summary.",
    }
    result = loader.render(render_template, report_data)
    assert "Test Requirement" in result
    assert "This is a test summary" in result


def test_build_section_prompts():
    loader = TemplateLoader()
    template_dir = Path(__file__).parent.parent / "src" / "reqradar" / "templates"
    defn = loader.load_definition(template_dir / "default_report.yaml")
    prompts = loader.build_section_prompts(defn)
    assert "requirement_understanding" in prompts
    assert "impact_analysis" in prompts
    assert len(prompts) == 8
