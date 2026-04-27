import difflib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from reqradar.core.exceptions import ReqRadarException

logger = logging.getLogger("reqradar.project_memory")


class ProjectMemoryError(ReqRadarException):
    pass


class ProjectMemory:
    STORAGE_DIR = "memories"

    def __init__(self, storage_path: str, project_id: int):
        self.project_id = project_id
        self.storage_path = Path(storage_path) / str(project_id)
        self.file_path = self.storage_path / "project.md"
        self._data: dict = {}
        self._loaded = False

    def _default_data(self) -> dict:
        return {
            "name": "",
            "overview": "",
            "tech_stack": {"languages": [], "frameworks": [], "databases": [], "key_dependencies": []},
            "modules": [],
            "terms": [],
            "constraints": [],
            "changelog": [],
        }

    def load(self) -> dict:
        if self._loaded:
            return {k: (v[:] if isinstance(v, list) else v) for k, v in self._data.items()}

        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8")
                self._data = self._parse_markdown(content)
                self._loaded = True
                return self._data
            except OSError as e:
                logger.warning("Failed to load project memory: %s, using defaults", e)

        self._data = self._default_data()
        self._loaded = True
        self.save()
        return self._data

    def save(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        content = self._render_markdown(self._data)
        try:
            self.file_path.write_text(content, encoding="utf-8")
            logger.info("Project memory saved to %s", self.file_path)
        except OSError as e:
            raise ProjectMemoryError(f"Failed to save project memory: {e}") from e

    def update_overview(self, overview: str) -> None:
        self.load()
        self._data["overview"] = overview
        self._save_changelog("Updated project overview")
        self.save()

    def update_name(self, name: str) -> None:
        self.load()
        self._data["name"] = name
        self.save()

    def add_tech_stack(self, category: str, items: list[str]) -> None:
        self.load()
        ts = self._data.setdefault("tech_stack", {})
        existing = ts.setdefault(category, [])
        for item in items:
            if item not in existing:
                existing.append(item)
        self.save()

    def add_module(self, name: str, responsibility: str = "", key_classes: list[str] | None = None) -> None:
        self.load()
        modules = self._data.setdefault("modules", [])
        for m in modules:
            if m["name"] == name:
                if responsibility:
                    m["responsibility"] = responsibility
                if key_classes:
                    m["key_classes"] = key_classes
                self.save()
                return
        modules.append({
            "name": name,
            "responsibility": responsibility,
            "key_classes": key_classes or [],
            "dependencies": [],
            "path": "",
        })
        self.save()

    def add_term(self, term: str, definition: str, domain: str = "") -> None:
        self.load()
        terms = self._data.setdefault("terms", [])
        for t in terms:
            if t["term"] == term:
                t["definition"] = definition
                if domain:
                    t["domain"] = domain
                self.save()
                return
        terms.append({"term": term, "definition": definition, "domain": domain})
        self.save()

    def batch_add_terms(self, terms: list[dict]) -> None:
        self.load()
        existing = self._data.setdefault("terms", [])
        existing_map = {t["term"]: t for t in existing}
        for item in terms:
            term, definition, domain = item["term"], item["definition"], item.get("domain", "")
            if term in existing_map:
                existing_map[term]["definition"] = definition
                if domain:
                    existing_map[term]["domain"] = domain
            else:
                existing.append({"term": term, "definition": definition, "domain": domain})
        self.save()

    def batch_add_modules(self, modules: list[dict]) -> None:
        self.load()
        existing = self._data.setdefault("modules", [])
        existing_map = {m["name"]: m for m in existing}
        for item in modules:
            name = item["name"]
            if name in existing_map:
                if item.get("responsibility"):
                    existing_map[name]["responsibility"] = item["responsibility"]
                if item.get("key_classes"):
                    existing_map[name]["key_classes"] = item["key_classes"]
            else:
                existing.append({
                    "name": name,
                    "responsibility": item.get("responsibility", ""),
                    "key_classes": item.get("key_classes", []),
                    "dependencies": [],
                    "path": "",
                })
        self.save()

    def batch_add_constraints(self, constraints: list[dict]) -> None:
        self.load()
        for c in constraints:
            self._data.setdefault("constraints", []).append({
                "description": c["description"],
                "type": c.get("constraint_type", "other"),
            })
        self.save()

    def _save_changelog(self, description: str) -> None:
        self._data.setdefault("changelog", []).append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": description,
        })

    def detect_changes(self, old_data: dict, new_data: dict) -> list[dict]:
        changes = []

        if old_data.get("overview", "") != new_data.get("overview", ""):
            changes.append({"change_type": "overview_updated", "target": "overview"})

        old_mod_names = {m["name"] for m in old_data.get("modules", [])}
        new_mod_names = {m["name"] for m in new_data.get("modules", [])}
        for name in new_mod_names - old_mod_names:
            changes.append({"change_type": "module_added", "target": f"module:{name}"})

        old_terms = {t["term"] for t in old_data.get("terms", [])}
        new_terms = {t["term"] for t in new_data.get("terms", [])}
        for term in new_terms - old_terms:
            changes.append({"change_type": "term_added", "target": f"term:{term}"})

        old_ts = old_data.get("tech_stack", {})
        new_ts = new_data.get("tech_stack", {})
        for category in set(list(old_ts.keys()) + list(new_ts.keys())):
            old_items = set(old_ts.get(category, []))
            new_items = set(new_ts.get(category, []))
            if new_items - old_items:
                changes.append({"change_type": "tech_stack_updated", "target": f"tech_stack:{category}"})

        return changes

    def generate_diff(self, old_content: str, new_content: str) -> str:
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after")
        return "".join(diff)

    def migrate_from_yaml(self, yaml_path: str) -> None:
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            return

        try:
            with open(yaml_file, encoding="utf-8") as f:
                old = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return

        profile = old.get("project_profile", {})
        self.load()

        if profile.get("name"):
            self._data["name"] = profile["name"]
        if profile.get("description"):
            self._data["overview"] = profile["description"]

        ts = profile.get("tech_stack", {})
        if ts:
            self._data["tech_stack"] = ts

        for mod in old.get("modules", []):
            self.add_module(mod.get("name", ""), mod.get("responsibility", ""), mod.get("key_classes", []))

        for term in old.get("terminology", []):
            self.add_term(term.get("term", ""), term.get("definition", ""), term.get("domain", ""))

        self.save()

    def _parse_markdown(self, content: str) -> dict:
        data = self._default_data()
        lines = content.split("\n")
        current_section = None
        current_subsection = None
        current_module = None

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("# ") and not stripped.startswith("## "):
                data["name"] = stripped[2:].strip()
                current_section = "header"
            elif stripped == "## Overview":
                current_section = "overview"
                current_subsection = None
            elif stripped == "## Tech Stack":
                current_section = "tech_stack"
                current_subsection = None
            elif stripped == "## Modules":
                current_section = "modules"
                current_subsection = None
                current_module = None
            elif stripped == "## Terms":
                current_section = "terms"
                current_subsection = None
            elif stripped == "## Constraints":
                current_section = "constraints"
                current_subsection = None
            elif stripped == "## Changelog":
                current_section = "changelog"
                current_subsection = None
            elif stripped.startswith("### "):
                if current_section == "tech_stack":
                    category = stripped[4:].strip().lower().rstrip(":")
                    current_subsection = category
                elif current_section == "modules":
                    mod_name = stripped[4:].strip()
                    current_module = {"name": mod_name, "responsibility": "", "key_classes": [], "dependencies": [], "path": ""}
                    data["modules"].append(current_module)
                    current_subsection = "module_body"
            elif stripped.startswith("- ") and stripped != "- ":
                if current_section == "overview":
                    data["overview"] += stripped[2:] + "\n"
                elif current_section == "tech_stack" and current_subsection:
                    item = stripped[2:].strip()
                    data["tech_stack"].setdefault(current_subsection, []).append(item)
                elif current_section == "terms":
                    parts = stripped[2:].strip()
                    if ": " in parts:
                        term, definition = parts.split(": ", 1)
                        domain = ""
                        if "[" in definition and definition.endswith("]"):
                            domain = definition[definition.rindex("[") + 1 : -1]
                            definition = definition[: definition.rindex("[")].strip()
                        data["terms"].append({"term": term.strip(), "definition": definition.strip(), "domain": domain})
                elif current_section == "constraints":
                    text = stripped[2:].strip()
                    if text:
                        data["constraints"].append({"description": text, "type": "other"})
                elif current_section == "changelog":
                    text = stripped[2:].strip()
                    if text:
                        data["changelog"].append({"date": "", "description": text})
            elif current_section == "overview" and stripped and not stripped.startswith("#"):
                data["overview"] += stripped + "\n"
            elif current_section == "modules" and current_module and stripped and not stripped.startswith("#"):
                if stripped.startswith("responsibility:") or stripped.startswith("Responsibility:"):
                    current_module["responsibility"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("key_classes:") or stripped.startswith("Key classes:"):
                    classes_str = stripped.split(":", 1)[1].strip()
                    current_module["key_classes"] = [c.strip() for c in classes_str.split(",") if c.strip()]

        data["overview"] = data["overview"].strip()
        return data

    def _render_markdown(self, data: dict) -> str:
        lines = []
        name = data.get("name", "")
        lines.append(f"# {name}" if name else "# Project")
        lines.append("")

        overview = data.get("overview", "")
        lines.append("## Overview")
        lines.append(overview if overview else "")
        lines.append("")

        ts = data.get("tech_stack", {})
        lines.append("## Tech Stack")
        for category in ["languages", "frameworks", "databases", "key_dependencies"]:
            items = ts.get(category, [])
            if items:
                lines.append(f"### {category.title()}")
                for item in items:
                    lines.append(f"- {item}")
        lines.append("")

        modules = data.get("modules", [])
        if modules:
            lines.append("## Modules")
            for mod in modules:
                lines.append(f"### {mod['name']}")
                if mod.get("responsibility"):
                    lines.append(f"Responsibility: {mod['responsibility']}")
                if mod.get("key_classes"):
                    lines.append(f"Key classes: {', '.join(mod['key_classes'])}")
                lines.append("")

        terms = data.get("terms", [])
        if terms:
            lines.append("## Terms")
            for t in terms:
                line = f"- {t['term']}: {t['definition']}"
                if t.get("domain"):
                    line += f" [{t['domain']}]"
                lines.append(line)
        lines.append("")

        constraints = data.get("constraints", [])
        if constraints:
            lines.append("## Constraints")
            for c in constraints:
                lines.append(f"- {c['description']} ({c.get('type', 'other')})")
        lines.append("")

        changelog = data.get("changelog", [])
        if changelog:
            lines.append("## Changelog")
            for entry in changelog:
                date = entry.get("date", "")
                desc = entry.get("description", "")
                lines.append(f"- {date}: {desc}" if date else f"- {desc}")
        lines.append("")

        return "\n".join(lines)
