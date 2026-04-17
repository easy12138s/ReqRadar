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
    - project_profile: project metadata and tech stack
    - modules: architectural modules
    - terminology: project-specific terms and definitions
    - team: key team members and their roles
    - constraints: project constraints
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

            self._migrate_old_format()

            for key, default_val in self._default_memory().items():
                if key not in self._data:
                    self._data[key] = default_val

            logger.info("Memory loaded from %s", self.memory_file)
            return self._data
        except Exception as e:
            logger.warning("Failed to load memory: %s, using defaults", e)
            self._data = self._default_memory()
            self._loaded = True
            return self._data

    def _migrate_old_format(self) -> None:
        """Migrate old flat format to new structured format"""
        if "project_profile" not in self._data:
            self._data["project_profile"] = self._default_memory()["project_profile"]

        if "modules" not in self._data:
            self._data["modules"] = []

        if "constraints" not in self._data:
            self._data["constraints"] = []

        for term in self._data.get("terminology", []):
            if "domain" not in term:
                term["domain"] = ""
            if "related_modules" not in term:
                term["related_modules"] = []
            if "source" not in term:
                term["source"] = "llm_extract"

        for member in self._data.get("team", []):
            if "source" not in member:
                member["source"] = "git_analyzer"

        for record in self._data.get("analysis_history", []):
            if "summary" in record and "key_findings" not in record:
                record["key_findings"] = record.pop("summary")
            if "key_findings" in record and "summary" not in record:
                record["summary"] = record.pop("key_findings")
            if "affected_modules" not in record:
                record["affected_modules"] = []
            if "key_decisions" not in record:
                record["key_decisions"] = []

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

    @property
    def project_profile(self) -> dict:
        data = self.load()
        return data.get("project_profile", {})

    @property
    def modules(self) -> list[dict]:
        data = self.load()
        return data.get("modules", [])

    @property
    def constraints(self) -> list[dict]:
        data = self.load()
        return data.get("constraints", [])

    def update_project_profile(self, profile: dict) -> None:
        """Update project profile (merges with existing)"""
        self.load()
        current = self._data["project_profile"]
        for key, value in profile.items():
            if value is not None and value != "" and value != []:
                if key == "tech_stack" and isinstance(value, dict):
                    ts = current.get("tech_stack", {})
                    for ts_key, ts_val in value.items():
                        if ts_val:
                            ts[ts_key] = ts_val
                    current["tech_stack"] = ts
                elif isinstance(value, list) and isinstance(current.get(key), list):
                    current[key] = value
                else:
                    current[key] = value
        current["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        self.save()

    def add_module(
        self,
        name: str,
        responsibility: str = "",
        key_classes: list = None,
        dependencies: list = None,
        path: str = "",
        owner: str = None,
        code_summary: str = "",
    ) -> None:
        """Add or update a module"""
        self.load()
        modules = self._data["modules"]

        for existing in modules:
            if existing.get("name") == name:
                if responsibility:
                    existing["responsibility"] = responsibility
                if key_classes is not None:
                    existing["key_classes"] = key_classes
                if dependencies is not None:
                    existing["dependencies"] = dependencies
                if path:
                    existing["path"] = path
                if owner is not None:
                    existing["owner"] = owner
                if code_summary:
                    existing["code_summary"] = code_summary
                self.save()
                return

        modules.append(
            {
                "name": name,
                "responsibility": responsibility,
                "key_classes": key_classes or [],
                "dependencies": dependencies or [],
                "path": path,
                "owner": owner,
                "code_summary": code_summary,
                "related_requirements": [],
            }
        )
        self.save()

    def add_module_requirement_history(
        self,
        module_name: str,
        requirement_id: str,
        relevance: str,
        suggested_changes: str = "",
    ) -> None:
        """添加模块的需求关联历史，只保留最近10条"""
        self.load()
        modules = self._data["modules"]

        for module in modules:
            if module.get("name") == module_name:
                if "requirement_history" not in module:
                    module["requirement_history"] = []

                module["requirement_history"].append(
                    {
                        "requirement_id": requirement_id,
                        "relevance": relevance,
                        "suggested_changes": suggested_changes,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                if len(module["requirement_history"]) > 10:
                    module["requirement_history"] = module["requirement_history"][-10:]

                self.save()
                return

    def get_module(self, name: str) -> dict | None:
        """按名称获取模块，返回模块字典或 None"""
        self.load()
        for module in self._data["modules"]:
            if module.get("name") == name:
                return module
        return None

    def add_constraint(
        self,
        description: str,
        constraint_type: str = "other",
        modules: list = None,
        source: str = "requirement_extraction",
    ) -> None:
        """Add a constraint"""
        self.load()
        self._data["constraints"].append(
            {
                "description": description,
                "constraint_type": constraint_type,
                "modules": modules or [],
                "source": source,
            }
        )
        self.save()

    def add_term(
        self,
        term: str,
        definition: str,
        context: str = "",
        domain: str = "",
        related_modules: list = None,
    ) -> None:
        """添加术语定义"""
        self.load()
        terminology = self._data["terminology"]

        for existing in terminology:
            if existing.get("term") == term:
                existing["definition"] = definition
                if context:
                    existing["context"] = context
                if domain:
                    existing["domain"] = domain
                if related_modules is not None:
                    existing["related_modules"] = related_modules
                self.save()
                return

        terminology.append(
            {
                "term": term,
                "definition": definition,
                "context": context,
                "domain": domain,
                "related_modules": related_modules or [],
                "source": "llm_extract",
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
                "source": "git_analyzer",
            }
        )
        self.save()

    def add_analysis_record(
        self,
        requirement: str,
        key_findings: str,
        risk_level: str = "",
        affected_modules: list = None,
        key_decisions: list = None,
    ) -> None:
        """添加分析历史记录"""
        self.load()
        self._data["analysis_history"].append(
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "requirement": requirement,
                "summary": key_findings[:200] if key_findings else "",
                "risk_level": risk_level,
                "affected_modules": affected_modules or [],
                "key_decisions": key_decisions or [],
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
            if t.get("domain"):
                line += f" [{t['domain']}]"
            if t.get("related_modules"):
                line += f" (相关模块: {', '.join(t['related_modules'])})"
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

    def get_project_profile_text(self) -> str:
        """Get project profile text for injecting into prompts"""
        profile = self.project_profile
        has_data = False
        tech_stack = profile.get("tech_stack", {})
        if profile.get("name"):
            has_data = True
        elif profile.get("description"):
            has_data = True
        elif profile.get("architecture_style"):
            has_data = True
        elif any(tech_stack.get(k) for k in ("languages", "frameworks", "key_dependencies")):
            has_data = True
        if not has_data:
            return ""
        lines = ["项目概况："]
        if profile.get("name"):
            lines.append(f"  名称: {profile['name']}")
        if profile.get("description"):
            lines.append(f"  描述: {profile['description']}")
        if profile.get("architecture_style"):
            lines.append(f"  架构风格: {profile['architecture_style']}")
        tech_stack = profile.get("tech_stack", {})
        if tech_stack:
            langs = tech_stack.get("languages", [])
            if langs:
                lines.append(f"  语言: {', '.join(langs)}")
            frameworks = tech_stack.get("frameworks", [])
            if frameworks:
                lines.append(f"  框架: {', '.join(frameworks)}")
            deps = tech_stack.get("key_dependencies", [])
            if deps:
                lines.append(f"  关键依赖: {', '.join(deps)}")
        return "\n".join(lines)

    def get_modules_text(self) -> str:
        """Get modules text for injecting into prompts"""
        modules = self.modules
        if not modules:
            return ""
        lines = ["项目模块："]
        for m in modules:
            line = f"- {m['name']}"
            if m.get("responsibility"):
                line += f": {m['responsibility']}"
            if m.get("key_classes"):
                line += f" (关键类: {', '.join(m['key_classes'])})"
            if m.get("owner"):
                line += f" [负责人: {m['owner']}]"
            lines.append(line)
        return "\n".join(lines)

    async def update_from_analysis(self, context) -> None:
        """从分析上下文更新记忆"""
        self.load()

        understanding = context.understanding
        analysis = context.deep_analysis

        if understanding:
            if understanding.terms:
                for t in understanding.terms:
                    existing_terms = {x.get("term") for x in self._data["terminology"]}
                    if t.term not in existing_terms:
                        self._data["terminology"].append(
                            {
                                "term": t.term,
                                "definition": t.definition,
                                "domain": t.domain if hasattr(t, "domain") else "",
                                "related_modules": [],
                                "source": "llm_extract",
                            }
                        )
            elif understanding.keywords:
                for keyword in understanding.keywords:
                    existing_terms = {x.get("term") for x in self._data["terminology"]}
                    if keyword not in existing_terms and len(keyword) > 1:
                        self._data["terminology"].append(
                            {
                                "term": keyword,
                                "definition": "",
                                "context": "自动提取",
                                "domain": "",
                                "related_modules": [],
                                "source": "llm_extract",
                            }
                        )

            if understanding.structured_constraints:
                for c in understanding.structured_constraints:
                    if c.description:
                        self._data.setdefault("constraints", []).append(
                            {
                                "description": c.description,
                                "constraint_type": c.constraint_type if c.constraint_type else "other",
                                "modules": [],
                                "source": c.source if c.source else "requirement_extraction",
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
                                "source": "git_analyzer",
                            }
                        )

        if understanding and understanding.summary:
            self.add_analysis_record(
                requirement=context.requirement_path.stem,
                key_findings=understanding.summary[:200],
                risk_level=analysis.risk_level if analysis else "",
                affected_modules=analysis.impact_modules if analysis else [],
            )
        else:
            self.save()

    def _default_memory(self) -> dict:
        return {
            "project_profile": {
                "name": "",
                "description": "",
                "tech_stack": {
                    "languages": [],
                    "frameworks": [],
                    "key_dependencies": [],
                },
                "architecture_style": "",
                "source": "llm_inferred",
                "last_updated": "",
            },
            "modules": [],
            "terminology": [],
            "team": [],
            "constraints": [],
            "analysis_history": [],
        }