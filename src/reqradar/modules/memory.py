"""项目记忆管理器 - 按项目隔离的领域知识存储"""

import logging
from datetime import datetime
from pathlib import Path

import yaml

from reqradar.core.exceptions import ReqRadarException

logger = logging.getLogger("reqradar.memory")


class MemoryException(ReqRadarException):
    """记忆操作错误"""

    pass


class MemoryManager:
    """项目记忆管理器

    Memory structure (.reqradar/memory/memory.yaml):
    - terminology: project-specific terms and definitions
    - team: key team members and their roles
    - analysis_history: record of past analyses and findings
    """

    def __init__(self, storage_path: str = ".reqradar/memory"):
        self.storage_path = Path(storage_path)
        self.memory_file = self.storage_path / "memory.yaml"
        self._data: dict = {}
        self._loaded = False

    def load(self) -> dict:
        """加载项目记忆"""
        if self._loaded:
            return self._data

        if not self.memory_file.exists():
            self._data = self._default_memory()
            self._loaded = True
            return self._data

        try:
            with open(self.memory_file, encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            self._loaded = True

            for key in ["terminology", "team", "analysis_history"]:
                if key not in self._data:
                    self._data[key] = []

            logger.info("Memory loaded from %s", self.memory_file)
            return self._data
        except Exception as e:
            logger.warning("Failed to load memory: %s, using defaults", e)
            self._data = self._default_memory()
            self._loaded = True
            return self._data

    def save(self) -> None:
        """保存项目记忆"""
        self.storage_path.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    self._data,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )
            logger.info("Memory saved to %s", self.memory_file)
        except Exception as e:
            raise MemoryException(f"Failed to save memory: {e}") from e

    @property
    def terminology(self) -> list[dict]:
        data = self.load()
        return data.get("terminology", [])

    @property
    def team(self) -> list[dict]:
        data = self.load()
        return data.get("team", [])

    @property
    def analysis_history(self) -> list[dict]:
        data = self.load()
        return data.get("analysis_history", [])

    def add_term(self, term: str, definition: str, context: str = "") -> None:
        """添加术语定义"""
        self.load()
        terminology = self._data["terminology"]

        for existing in terminology:
            if existing.get("term") == term:
                existing["definition"] = definition
                if context:
                    existing["context"] = context
                self.save()
                return

        terminology.append(
            {
                "term": term,
                "definition": definition,
                "context": context,
            }
        )
        self.save()

    def add_team_member(self, name: str, role: str, modules: list[str] = None) -> None:
        """添加团队成员信息"""
        self.load()
        team = self._data["team"]

        for existing in team:
            if existing.get("name") == name:
                existing["role"] = role
                if modules:
                    existing["modules"] = modules
                self.save()
                return

        team.append(
            {
                "name": name,
                "role": role,
                "modules": modules or [],
            }
        )
        self.save()

    def add_analysis_record(
        self, requirement: str, key_findings: str, risk_level: str = ""
    ) -> None:
        """添加分析历史记录"""
        self.load()
        self._data["analysis_history"].append(
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "requirement": requirement,
                "key_findings": key_findings,
                "risk_level": risk_level,
            }
        )

        if len(self._data["analysis_history"]) > 50:
            self._data["analysis_history"] = self._data["analysis_history"][-50:]

        self.save()

    def get_terminology_text(self) -> str:
        """获取术语文本，用于注入 prompt"""
        terms = self.terminology
        if not terms:
            return ""
        lines = ["项目已知术语："]
        for t in terms:
            line = f"- {t['term']}: {t['definition']}"
            if t.get("context"):
                line += f"（{t['context']}）"
            lines.append(line)
        return "\n".join(lines)

    def get_team_text(self) -> str:
        """获取团队信息文本"""
        members = self.team
        if not members:
            return ""
        lines = ["项目已知团队成员："]
        for m in members:
            line = f"- {m['name']}（{m['role']}）"
            if m.get("modules"):
                line += f" 负责模块: {', '.join(m['modules'])}"
            lines.append(line)
        return "\n".join(lines)

    async def update_from_analysis(self, context) -> None:
        """从分析上下文更新记忆"""
        self.load()

        understanding = context.understanding
        analysis = context.deep_analysis

        if understanding and understanding.keywords:
            for keyword in understanding.keywords:
                existing_terms = {t.get("term") for t in self._data["terminology"]}
                if keyword not in existing_terms and len(keyword) > 1:
                    self._data["terminology"].append(
                        {
                            "term": keyword,
                            "definition": "",
                            "context": "自动提取",
                        }
                    )

        if analysis:
            if analysis.contributors:
                for c in analysis.contributors[:3]:
                    existing_names = {t.get("name") for t in self._data["team"]}
                    if c.get("name") and c["name"] not in existing_names:
                        self._data["team"].append(
                            {
                                "name": c["name"],
                                "role": c.get("reason", ""),
                                "modules": [c.get("file", "")],
                            }
                        )

        if understanding and understanding.summary:
            self.add_analysis_record(
                requirement=context.requirement_path.stem,
                key_findings=understanding.summary[:200],
                risk_level=analysis.risk_level if analysis else "",
            )
        else:
            self.save()

    def _default_memory(self) -> dict:
        return {
            "terminology": [],
            "team": [],
            "analysis_history": [],
        }
