"""测试项目记忆管理器"""

from pathlib import Path

import pytest

from reqradar.modules.memory import MemoryManager


class TestMemoryManager:
    def test_default_memory(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        data = manager.load()

        assert "terminology" in data
        assert "team" in data
        assert "analysis_history" in data
        assert data["terminology"] == []

    def test_add_term(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term("SSO", "Single Sign-On 统一身份认证", "认证模块")

        terms = manager.terminology
        assert len(terms) == 1
        assert terms[0]["term"] == "SSO"
        assert terms[0]["definition"] == "Single Sign-On 统一身份认证"

    def test_add_duplicate_term_updates(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term("SSO", "旧定义")
        manager.add_term("SSO", "新定义")

        terms = manager.terminology
        assert len(terms) == 1
        assert terms[0]["definition"] == "新定义"

    def test_add_team_member(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_team_member("张三", "后端负责人", ["auth", "user"])

        team = manager.team
        assert len(team) == 1
        assert team[0]["name"] == "张三"
        assert team[0]["role"] == "后端负责人"

    def test_add_analysis_record(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_analysis_record("IDE集成", "涉及auth模块", "medium")

        history = manager.analysis_history
        assert len(history) == 1
        assert history[0]["requirement"] == "IDE集成"
        assert history[0]["risk_level"] == "medium"

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
