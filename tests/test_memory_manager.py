import pytest
from pathlib import Path
from reqradar.modules.memory_manager import AnalysisMemoryManager


@pytest.fixture
def tmp_storage(tmp_path):
    return {
        "project_path": str(tmp_path / "memories"),
        "user_path": str(tmp_path / "user_memories"),
    }


def test_memory_manager_loads_project_memory(tmp_storage):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=tmp_storage["project_path"],
        user_storage_path=tmp_storage["user_path"],
    )
    project_mem = mm.project_memory
    data = project_mem.load()
    assert "overview" in data


def test_memory_manager_loads_user_memory(tmp_storage):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=tmp_storage["project_path"],
        user_storage_path=tmp_storage["user_path"],
    )
    user_mem = mm.user_memory
    data = user_mem.load()
    assert "corrections" in data


def test_memory_manager_gets_project_profile_text(tmp_storage):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=tmp_storage["project_path"],
        user_storage_path=tmp_storage["user_path"],
    )
    mm.project_memory.update_overview("Test overview")
    mm.project_memory.save()
    text = mm.get_project_profile_text()
    assert "Test overview" in text


def test_memory_manager_disabled_returns_empty(tmp_storage):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=tmp_storage["project_path"],
        user_storage_path=tmp_storage["user_path"],
        memory_enabled=False,
    )
    assert mm.project_memory is None
    assert mm.user_memory is None
    assert mm.get_project_profile_text() == ""
    assert mm.get_user_memory_text() == ""
