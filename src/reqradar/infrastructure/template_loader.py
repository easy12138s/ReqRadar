import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from jinja2 import Template

logger = logging.getLogger("reqradar.template_loader")


@dataclass
class SectionDefinition:
    id: str
    title: str
    description: str
    requirements: str = ""
    required: bool = True
    dimensions: list[str] = field(default_factory=list)


@dataclass
class TemplateDefinition:
    name: str
    description: str = ""
    sections: list[SectionDefinition] = field(default_factory=list)


class TemplateLoader:
    def load_definition(self, yaml_path: str | Path) -> TemplateDefinition:
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Template file not found: {path}")
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        template_def = raw.get("template_definition", raw)
        name = template_def.get("name", "Unnamed Template")
        description = template_def.get("description", "")
        sections = []
        for sec_raw in template_def.get("sections", []):
            sections.append(SectionDefinition(
                id=sec_raw.get("id", ""),
                title=sec_raw.get("title", ""),
                description=sec_raw.get("description", ""),
                requirements=sec_raw.get("requirements", ""),
                required=sec_raw.get("required", True),
                dimensions=sec_raw.get("dimensions", []),
            ))
        return TemplateDefinition(name=name, description=description, sections=sections)

    def render(self, render_template: str, report_data: dict) -> str:
        template = Template(render_template)
        return template.render(**report_data)

    def build_section_prompts(self, defn: TemplateDefinition) -> dict[str, str]:
        prompts = {}
        for section in defn.sections:
            parts = [f"章节: {section.title}"]
            if section.description:
                parts.append(f"描述: {section.description}")
            if section.requirements:
                parts.append(f"写作要求: {section.requirements}")
            if section.dimensions:
                parts.append(f"所需维度: {', '.join(section.dimensions)}")
            parts.append(f"必填: {'是' if section.required else '否'}")
            prompts[section.id] = "\n".join(parts)
        return prompts

    def load_from_db_data(self, definition_str: str, render_template_str: str) -> TemplateDefinition:
        try:
            raw = yaml.safe_load(definition_str) or {}
        except yaml.YAMLError:
            raw = {}
        template_def = raw.get("template_definition", raw)
        name = template_def.get("name", "DB Template")
        description = template_def.get("description", "")
        sections = []
        for sec_raw in template_def.get("sections", []):
            sections.append(SectionDefinition(
                id=sec_raw.get("id", ""),
                title=sec_raw.get("title", ""),
                description=sec_raw.get("description", ""),
                requirements=sec_raw.get("requirements", ""),
                required=sec_raw.get("required", True),
                dimensions=sec_raw.get("dimensions", []),
            ))
        return TemplateDefinition(name=name, description=description, sections=sections)

    def get_default_template_path(self) -> Path:
        return Path(__file__).parent.parent / "templates" / "default_report.yaml"

    def get_default_render_template_path(self) -> Path:
        return Path(__file__).parent.parent / "templates" / "report.md.j2"
