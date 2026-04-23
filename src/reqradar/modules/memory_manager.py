import logging
from pathlib import Path
from typing import Optional

from reqradar.modules.project_memory import ProjectMemory
from reqradar.modules.user_memory import UserMemory

logger = logging.getLogger("reqradar.memory_manager")


class AnalysisMemoryManager:
    def __init__(
        self,
        project_id: int,
        user_id: int,
        project_storage_path: str = ".reqradar/memories",
        user_storage_path: str = ".reqradar/user_memories",
        repo_path: str = ".",
        memory_enabled: bool = True,
    ):
        self.project_id = project_id
        self.user_id = user_id
        self.enabled = memory_enabled

        if self.enabled:
            self.project_memory = ProjectMemory(
                storage_path=project_storage_path,
                project_id=project_id,
            )
            self.user_memory = UserMemory(
                storage_path=user_storage_path,
                user_id=user_id,
            )
        else:
            self.project_memory = None
            self.user_memory = None

    def get_project_profile_text(self) -> str:
        if not self.enabled or not self.project_memory:
            return ""
        data = self.project_memory.load()
        lines = []
        if data.get("name"):
            lines.append(f"项目: {data['name']}")
        if data.get("overview"):
            lines.append(f"概述: {data['overview']}")
        ts = data.get("tech_stack", {})
        for cat in ["languages", "frameworks", "databases", "key_dependencies"]:
            items = ts.get(cat, [])
            if items:
                lines.append(f"{cat}: {', '.join(items)}")
        for mod in data.get("modules", []):
            line = f"- {mod['name']}"
            if mod.get("responsibility"):
                line += f": {mod['responsibility']}"
            lines.append(line)
        return "\n".join(lines)

    def get_user_memory_text(self) -> str:
        if not self.enabled or not self.user_memory:
            return ""
        data = self.user_memory.load()
        lines = []
        corrections = data.get("corrections", [])
        if corrections:
            lines.append("用户纠正记录：")
            for c in corrections:
                lines.append(f'- "{c["business_term"]}" → {", ".join(c.get("code_terms", []))}')
        prefs = data.get("preferences", {})
        if prefs:
            lines.append("用户偏好：")
            for k, v in prefs.items():
                lines.append(f"- {k}: {v}")
        return "\n".join(lines) if lines else ""

    def get_terminology_text(self) -> str:
        if not self.enabled or not self.project_memory:
            return ""
        data = self.project_memory.load()
        terms = data.get("terms", [])
        if not terms:
            return ""
        lines = ["项目已知术语："]
        for t in terms:
            line = f"- {t['term']}: {t.get('definition', '')}"
            if t.get("domain"):
                line += f" [{t['domain']}]"
            lines.append(line)
        return "\n".join(lines)

    def get_modules_text(self) -> str:
        if not self.enabled or not self.project_memory:
            return ""
        data = self.project_memory.load()
        modules = data.get("modules", [])
        if not modules:
            return ""
        lines = ["项目模块："]
        for m in modules:
            line = f"- {m['name']}"
            if m.get("responsibility"):
                line += f": {m['responsibility']}"
            if m.get("key_classes"):
                line += f" (关键类: {', '.join(m['key_classes'])})"
            lines.append(line)
        return "\n".join(lines)
