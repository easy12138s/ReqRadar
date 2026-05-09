import pytest
from pathlib import Path
from reqradar.modules.project_memory import ProjectMemory


@pytest.fixture
def tmp_memory_dir(tmp_path):
    return tmp_path / "memories"


def test_project_memory_creates_dir_and_file(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    data = pm.load()
    assert data["overview"] == ""
    assert pm.storage_path.exists()
    assert "projects" in str(pm.storage_path)


def test_project_memory_save_and_load(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm.update_overview("A test project for requirement analysis")
    pm.add_tech_stack("languages", ["Python", "TypeScript"])
    pm.add_module("web", "Web server module", ["app.py"])
    pm.add_term("RQ", "Requirement", domain="general")
    pm.save()

    pm2 = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    data = pm2.load()
    assert "A test project" in data["overview"]
    assert "Python" in data["tech_stack"]["languages"]
    assert any(m["name"] == "web" for m in data["modules"])
    assert any(t["term"] == "RQ" for t in data["terms"])


def test_project_memory_detect_changes(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm.update_overview("Original overview")
    pm.save()

    old_data = pm.load()

    pm.update_overview("Updated overview")
    pm.add_module("new_module", "A new module")
    pm.save()

    new_data = pm.load()
    changes = pm.detect_changes(old_data, new_data)
    assert len(changes) > 0
    assert any(c["change_type"] == "overview_updated" for c in changes)


def test_project_memory_isolation(tmp_memory_dir):
    pm1 = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm2 = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=2)

    pm1.update_overview("Project 1")
    pm2.update_overview("Project 2")
    pm1.save()
    pm2.save()

    data1 = pm1.load()
    data2 = pm2.load()
    assert data1["overview"] != data2["overview"]


def test_project_memory_migrate_from_yaml(tmp_memory_dir):
    import yaml

    yaml_path = tmp_memory_dir / ".." / "memory"
    yaml_path.mkdir(parents=True, exist_ok=True)
    yaml_file = yaml_path / "memory.yaml"

    old_data = {
        "project_profile": {"name": "OldProject", "description": "Old desc"},
        "modules": [{"name": "old_mod", "responsibility": "old"}],
        "terminology": [],
        "team": [],
        "constraints": [],
        "analysis_history": [],
    }

    with open(yaml_file, "w") as f:
        yaml.dump(old_data, f)

    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)
    pm.migrate_from_yaml(str(yaml_file))
    data = pm.load()
    assert "OldProject" in data["overview"] or data.get("name") == "OldProject"


def test_project_memory_generate_diff(tmp_memory_dir):
    pm = ProjectMemory(storage_path=str(tmp_memory_dir), project_id=1)

    old_content = "# Project\n\n## Overview\nOld overview\n"
    new_content = "# Project\n\n## Overview\nNew overview\n\n## Modules\n### auth\nAuth module\n"

    diff = pm.generate_diff(old_content, new_content)
    assert "+### auth" in diff or "+ auth" in diff
