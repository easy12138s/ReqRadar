import pytest
from pathlib import Path
from reqradar.modules.user_memory import UserMemory


@pytest.fixture
def tmp_memory_dir(tmp_path):
    return tmp_path / "user_memories"


def test_user_memory_creates_dir_and_file(tmp_memory_dir):
    um = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    data = um.load()
    assert data["corrections"] == []
    assert um.file_path.parent.exists()
    assert "users" in str(um.storage_path)


def test_user_memory_add_correction(tmp_memory_dir):
    um = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    um.add_correction("配置", ["config", "settings"], source="user_correction", analysis_id=42)
    um.save()
    um2 = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    data = um2.load()
    assert len(data["corrections"]) == 1
    assert data["corrections"][0]["business_term"] == "配置"


def test_user_memory_set_preference(tmp_memory_dir):
    um = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    um.set_preference("default_depth", "deep")
    um.set_preference("report_language", "zh")
    um.save()
    um2 = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    data = um2.load()
    assert data["preferences"]["default_depth"] == "deep"
    assert data["preferences"]["report_language"] == "zh"


def test_user_memory_isolation(tmp_memory_dir):
    um1 = UserMemory(storage_path=str(tmp_memory_dir), user_id=1)
    um2 = UserMemory(storage_path=str(tmp_memory_dir), user_id=2)
    um1.add_correction("术语A", ["codeA"])
    um2.add_correction("术语B", ["codeB"])
    um1.save()
    um2.save()
    data1 = um1.load()
    data2 = um2.load()
    assert data1["corrections"] != data2["corrections"]
