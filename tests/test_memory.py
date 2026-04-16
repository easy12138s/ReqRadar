"""测试项目记忆管理器"""

from pathlib import Path

import pytest
import yaml

from reqradar.modules.memory import MemoryManager


class TestMemoryManager:
    def test_default_memory(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        data = manager.load()

        assert "terminology" in data
        assert "team" in data
        assert "analysis_history" in data
        assert "project_profile" in data
        assert "modules" in data
        assert "constraints" in data
        assert data["terminology"] == []
        assert data["modules"] == []
        assert data["constraints"] == []

    def test_default_memory_structure(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        data = manager.load()

        profile = data["project_profile"]
        assert "name" in profile
        assert "description" in profile
        assert "tech_stack" in profile
        assert "architecture_style" in profile
        assert "source" in profile
        assert "last_updated" in profile
        assert profile["source"] == "llm_inferred"
        assert isinstance(profile["tech_stack"]["languages"], list)

    def test_add_term(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term("SSO", "Single Sign-On 统一身份认证", "认证模块")

        terms = manager.terminology
        assert len(terms) == 1
        assert terms[0]["term"] == "SSO"
        assert terms[0]["definition"] == "Single Sign-On 统一身份认证"

    def test_add_term_with_domain_and_modules(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term(
            "SSO",
            "Single Sign-On",
            domain="auth",
            related_modules=["auth-service", "gateway"],
        )

        terms = manager.terminology
        assert len(terms) == 1
        assert terms[0]["domain"] == "auth"
        assert terms[0]["related_modules"] == ["auth-service", "gateway"]
        assert terms[0]["source"] == "llm_extract"

    def test_add_duplicate_term_updates(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term("SSO", "旧定义")
        manager.add_term("SSO", "新定义", domain="security")

        terms = manager.terminology
        assert len(terms) == 1
        assert terms[0]["definition"] == "新定义"
        assert terms[0]["domain"] == "security"

    def test_add_team_member(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_team_member("张三", "后端负责人", ["auth", "user"])

        team = manager.team
        assert len(team) == 1
        assert team[0]["name"] == "张三"
        assert team[0]["role"] == "后端负责人"
        assert team[0]["source"] == "git_analyzer"

    def test_add_analysis_record(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_analysis_record("IDE集成", "涉及auth模块", "medium")

        history = manager.analysis_history
        assert len(history) == 1
        assert history[0]["requirement"] == "IDE集成"
        assert history[0]["risk_level"] == "medium"

    def test_add_analysis_record_with_new_fields(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_analysis_record(
            "IDE集成",
            "涉及auth模块",
            "high",
            affected_modules=["auth", "gateway"],
            key_decisions=["采用OAuth2", "分阶段迁移"],
        )

        history = manager.analysis_history
        assert len(history) == 1
        assert history[0]["affected_modules"] == ["auth", "gateway"]
        assert history[0]["key_decisions"] == ["采用OAuth2", "分阶段迁移"]
        assert history[0]["summary"] == "涉及auth模块"

    def test_analysis_history_limit(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        for i in range(55):
            manager.add_analysis_record(f"需求{i}", f"发现{i}", "low")

        history = manager.analysis_history
        assert len(history) == 50

    def test_get_terminology_text_empty(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        assert manager.get_terminology_text() == ""

    def test_get_terminology_text_with_data(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term("SSO", "统一身份认证")
        text = manager.get_terminology_text()
        assert "SSO" in text
        assert "统一身份认证" in text

    def test_get_terminology_text_with_domain_and_modules(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term("SSO", "统一身份认证", domain="auth", related_modules=["auth-service"])
        text = manager.get_terminology_text()
        assert "[auth]" in text
        assert "auth-service" in text

    def test_get_team_text_with_data(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_team_member("张三", "后端负责人", ["auth"])
        text = manager.get_team_text()
        assert "张三" in text
        assert "后端负责人" in text

    def test_save_and_reload(self, tmp_path):
        storage = str(tmp_path / "memory")
        manager1 = MemoryManager(storage_path=storage)
        manager1.add_term("RBAC", "基于角色的访问控制")
        manager1.add_team_member("李四", "前端负责人", ["ui"])

        manager2 = MemoryManager(storage_path=storage)
        data = manager2.load()
        assert len(data["terminology"]) == 1
        assert data["terminology"][0]["term"] == "RBAC"
        assert len(data["team"]) == 1

    def test_update_project_profile(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.update_project_profile({
            "name": "ReqRadar",
            "description": "需求分析工具",
            "architecture_style": "微服务",
        })

        profile = manager.project_profile
        assert profile["name"] == "ReqRadar"
        assert profile["description"] == "需求分析工具"
        assert profile["architecture_style"] == "微服务"
        assert profile["last_updated"] != ""

    def test_update_project_profile_merge(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.update_project_profile({
            "name": "ReqRadar",
            "tech_stack": {"languages": ["Python"], "frameworks": ["FastAPI"]},
        })
        manager.update_project_profile({
            "tech_stack": {"languages": ["Python"], "key_dependencies": ["PyYAML"]},
        })

        profile = manager.project_profile
        assert profile["name"] == "ReqRadar"
        assert "PyYAML" in profile["tech_stack"]["key_dependencies"]

    def test_add_module(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_module("auth", responsibility="认证授权模块", key_classes=["AuthService", "TokenManager"])

        modules = manager.modules
        assert len(modules) == 1
        assert modules[0]["name"] == "auth"
        assert modules[0]["responsibility"] == "认证授权模块"
        assert "AuthService" in modules[0]["key_classes"]

    def test_add_module_update_existing(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_module("auth", responsibility="认证模块")
        manager.add_module("auth", responsibility="认证授权模块", owner="张三")

        modules = manager.modules
        assert len(modules) == 1
        assert modules[0]["responsibility"] == "认证授权模块"
        assert modules[0]["owner"] == "张三"

    def test_add_constraint(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_constraint("必须使用HTTPS", constraint_type="security", modules=["gateway"])

        constraints = manager.constraints
        assert len(constraints) == 1
        assert constraints[0]["description"] == "必须使用HTTPS"
        assert constraints[0]["constraint_type"] == "security"
        assert constraints[0]["modules"] == ["gateway"]
        assert constraints[0]["source"] == "requirement_extraction"

    def test_get_project_profile_text_empty(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        assert manager.get_project_profile_text() == ""

    def test_get_project_profile_text_with_data(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.update_project_profile({
            "name": "ReqRadar",
            "description": "需求分析工具",
            "architecture_style": "微服务",
            "tech_stack": {
                "languages": ["Python"],
                "frameworks": ["FastAPI"],
                "key_dependencies": ["PyYAML"],
            },
        })

        text = manager.get_project_profile_text()
        assert "ReqRadar" in text
        assert "需求分析工具" in text
        assert "Python" in text

    def test_get_modules_text_empty(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        assert manager.get_modules_text() == ""

    def test_get_modules_text_with_data(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_module("auth", responsibility="认证模块", key_classes=["AuthService"], owner="张三")
        text = manager.get_modules_text()
        assert "auth" in text
        assert "认证模块" in text
        assert "张三" in text

    def test_backward_compatibility_old_format(self, tmp_path):
        storage_path = tmp_path / "memory"
        storage_path.mkdir()
        old_data = {
            "terminology": [{"term": "SSO", "definition": "单点登录", "context": "认证"}],
            "team": [{"name": "张三", "role": "负责人", "modules": ["auth"]}],
            "analysis_history": [
                {"date": "2024-01-01", "requirement": "test", "key_findings": "f1", "risk_level": "low"}
            ],
        }
        memory_file = storage_path / "memory.yaml"
        with open(memory_file, "w", encoding="utf-8") as f:
            yaml.dump(old_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        manager = MemoryManager(storage_path=str(storage_path))
        data = manager.load()

        assert "project_profile" in data
        assert "modules" in data
        assert "constraints" in data
        assert len(data["terminology"]) == 1
        assert data["terminology"][0]["domain"] == ""
        assert data["terminology"][0]["related_modules"] == []
        assert data["terminology"][0]["source"] == "llm_extract"
        assert data["team"][0]["source"] == "git_analyzer"
        assert data["analysis_history"][0]["summary"] is not None
        assert data["analysis_history"][0]["affected_modules"] == []
        assert data["analysis_history"][0]["key_decisions"] == []