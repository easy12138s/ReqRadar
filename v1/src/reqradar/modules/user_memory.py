import logging
from datetime import datetime
from pathlib import Path
from reqradar.core.exceptions import ReqRadarException

logger = logging.getLogger("reqradar.user_memory")


class UserMemoryError(ReqRadarException):
    pass


class UserMemory:
    def __init__(self, storage_path: str, user_id: int):
        self.user_id = user_id
        self.storage_path = Path(storage_path) / "users" / str(user_id)
        self.file_path = self.storage_path / "user.md"
        self._data: dict = {}
        self._loaded = False

    def _default_data(self) -> dict:
        return {
            "corrections": [],
            "focus_areas": [],
            "preferences": {
                "default_depth": "standard",
                "report_language": "zh",
            },
            "term_preference": [],
        }

    def load(self) -> dict:
        if self._loaded:
            return self._data
        self.storage_path.mkdir(parents=True, exist_ok=True)
        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8")
                self._data = self._parse_markdown(content)
                self._loaded = True
                return self._data
            except OSError as e:
                logger.warning("Failed to load user memory: %s, using defaults", e)
        self._data = self._default_data()
        self._loaded = True
        return self._data

    def save(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        content = self._render_markdown(self._data)
        try:
            self.file_path.write_text(content, encoding="utf-8")
            logger.info("User memory saved to %s", self.file_path)
        except OSError as e:
            raise UserMemoryError(f"Failed to save user memory: {e}") from e

    def add_correction(
        self,
        business_term: str,
        code_terms: list[str],
        source: str = "user_correction",
        analysis_id: int | None = None,
    ) -> None:
        self.load()
        self._data["corrections"].append(
            {
                "business_term": business_term,
                "code_terms": code_terms,
                "source": source,
                "analysis_id": analysis_id,
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        self.save()

    def set_preference(self, key: str, value: str) -> None:
        self.load()
        self._data["preferences"][key] = value
        self.save()

    def add_focus_area(self, area: str, priority: str = "medium") -> None:
        self.load()
        self._data["focus_areas"].append({"area": area, "priority": priority})
        self.save()

    def add_term_preference(self, term: str, definition: str) -> None:
        self.load()
        self._data["term_preference"].append({"term": term, "definition": definition})
        self.save()

    def batch_add_corrections(self, corrections: list[dict]) -> None:
        self.load()
        for c in corrections:
            self._data["corrections"].append(c)
        self.save()

    def get_corrections_for_term(self, business_term: str) -> list[str]:
        self.load()
        results = []
        for c in self._data["corrections"]:
            if c["business_term"] == business_term:
                results.extend(c.get("code_terms", []))
        return list(set(results))

    def _parse_markdown(self, content: str) -> dict:
        data = self._default_data()
        lines = content.split("\n")
        current_section = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                pass
            elif stripped == "## Corrections":
                current_section = "corrections"
            elif stripped == "## Focus Areas":
                current_section = "focus_areas"
            elif stripped == "## Preferences":
                current_section = "preferences"
            elif stripped == "## Term Preferences":
                current_section = "term_preferences"
            elif stripped.startswith("- ") and stripped != "- ":
                text = stripped[2:].strip()
                if current_section == "corrections" and "→" in text:
                    parts = text.split("→")
                    bt = parts[0].strip().strip('"')
                    code_str = parts[1].strip().strip("[]")
                    code_terms = [c.strip() for c in code_str.split(",")]
                    data["corrections"].append(
                        {
                            "business_term": bt,
                            "code_terms": code_terms,
                            "source": "user_correction",
                            "analysis_id": None,
                            "date": "",
                        }
                    )
                elif current_section == "focus_areas" and ":" in text:
                    area, pri = text.split(":", 1)
                    data["focus_areas"].append({"area": area.strip(), "priority": pri.strip()})
                elif current_section == "preferences" and ":" in text:
                    key, val = text.split(":", 1)
                    data["preferences"][key.strip()] = val.strip()
                elif current_section == "term_preferences":
                    if "→" in text:
                        parts = text.split("→")
                    elif ":" in text:
                        parts = text.split(":", 1)
                    else:
                        continue
                    data["term_preference"].append(
                        {
                            "term": parts[0].strip().strip('"'),
                            "definition": parts[1].strip().strip('"'),
                        }
                    )
        return data

    def _render_markdown(self, data: dict) -> str:
        lines = ["# User Preferences", ""]
        corrections = data.get("corrections", [])
        if corrections:
            lines.append("## Corrections")
            for c in corrections:
                code_str = ", ".join(c.get("code_terms", []))
                source_info = (
                    f" (source: {c.get('source', 'unknown')}"
                    + (f", analysis #{c.get('analysis_id')}" if c.get("analysis_id") else "")
                    + ")"
                    if c.get("source")
                    else ""
                )
                lines.append(f'- "{c["business_term"]}" → [{code_str}]{source_info}')
            lines.append("")
        focus_areas = data.get("focus_areas", [])
        if focus_areas:
            lines.append("## Focus Areas")
            for fa in focus_areas:
                lines.append(f"- {fa['area']}: {fa.get('priority', 'medium')}")
            lines.append("")
        prefs = data.get("preferences", {})
        if prefs:
            lines.append("## Preferences")
            for key, val in prefs.items():
                lines.append(f"- {key}: {val}")
            lines.append("")
        term_prefs = data.get("term_preference", [])
        if term_prefs:
            lines.append("## Term Preferences")
            for tp in term_prefs:
                lines.append(f'- "{tp["term"]}" → "{tp["definition"]}"')
            lines.append("")
        return "\n".join(lines)
