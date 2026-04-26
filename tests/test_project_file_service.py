import os
import shutil
import zipfile
from pathlib import Path

import pytest

from reqradar.infrastructure.config import WebConfig
from reqradar.web.services.project_file_service import ProjectFileService


@pytest.fixture
def service(tmp_path):
    data_root = str(tmp_path / "data")
    config = WebConfig(data_root=data_root)
    return ProjectFileService(config)


def test_get_project_path(service, tmp_path):
    result = service.get_project_path("my-project")
    assert result == Path(tmp_path / "data" / "my-project")


def test_create_project_dirs(service, tmp_path):
    service.create_project_dirs("test-proj")
    base = tmp_path / "data" / "test-proj"
    assert (base / "project_code").is_dir()
    assert (base / "requirements").is_dir()
    assert (base / "index").is_dir()
    assert (base / "memory").is_dir()


def test_create_project_dirs_idempotent(service, tmp_path):
    service.create_project_dirs("test-proj")
    service.create_project_dirs("test-proj")
    assert (tmp_path / "data" / "test-proj" / "project_code").is_dir()


def test_extract_zip(service, tmp_path):
    zip_dir = tmp_path / "zip_source"
    zip_dir.mkdir()
    (zip_dir / "main.py").write_text("print('hello')")
    (zip_dir / "README.md").write_text("# test")

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in zip_dir.iterdir():
            zf.write(f, f.name)

    zip_bytes = zip_path.read_bytes()

    service.create_project_dirs("zip-proj")
    service.extract_zip("zip-proj", zip_bytes)

    code_dir = tmp_path / "data" / "zip-proj" / "project_code"
    assert (code_dir / "main.py").exists()
    assert (code_dir / "README.md").exists()
    assert (tmp_path / "data" / "zip-proj" / "project.zip").exists()


def test_extract_zip_single_subdir(service, tmp_path):
    inner = tmp_path / "inner"
    inner.mkdir()
    subdir = inner / "my-app"
    subdir.mkdir()
    (subdir / "app.py").write_text("print('app')")

    zip_path = tmp_path / "subdir.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in subdir.rglob("*"):
            zf.write(f, f.relative_to(inner))

    zip_bytes = zip_path.read_bytes()

    service.create_project_dirs("subdir-proj")
    service.extract_zip("subdir-proj", zip_bytes)

    code_dir = tmp_path / "data" / "subdir-proj" / "project_code"
    assert (code_dir / "my-app" / "app.py").exists()


def test_detect_code_root_flat(service, tmp_path):
    service.create_project_dirs("flat-proj")
    code_dir = tmp_path / "data" / "flat-proj" / "project_code"
    (code_dir / "main.py").write_text("print('hello')")
    (code_dir / "utils.py").write_text("def util(): pass")

    result = service.detect_code_root("flat-proj")
    assert result == code_dir


def test_detect_code_root_single_subdir(service, tmp_path):
    service.create_project_dirs("sub-proj")
    code_dir = tmp_path / "data" / "sub-proj" / "project_code"
    subdir = code_dir / "cool-agent"
    subdir.mkdir()
    (subdir / "main.py").write_text("print('hello')")

    result = service.detect_code_root("sub-proj")
    assert result == subdir


def test_detect_code_root_multiple_subdirs(service, tmp_path):
    service.create_project_dirs("multi-proj")
    code_dir = tmp_path / "data" / "multi-proj" / "project_code"
    (code_dir / "dir1").mkdir()
    (code_dir / "dir2").mkdir()
    (code_dir / "main.py").write_text("print('hello')")

    result = service.detect_code_root("multi-proj")
    assert result == code_dir


def test_delete_project_files(service, tmp_path):
    service.create_project_dirs("del-proj")
    base = tmp_path / "data" / "del-proj"
    assert base.is_dir()

    service.delete_project_files("del-proj")
    assert not base.exists()


def test_delete_project_files_nonexistent(service):
    service.delete_project_files("nonexistent-proj")


def test_get_file_tree(service, tmp_path):
    service.create_project_dirs("tree-proj")
    code_dir = tmp_path / "data" / "tree-proj" / "project_code"
    (code_dir / "main.py").write_text("code")
    (code_dir / "sub").mkdir()
    (code_dir / "sub" / "helper.py").write_text("help")

    tree = service.get_file_tree("tree-proj")
    assert isinstance(tree, list)
    names = [item["name"] for item in tree]
    assert "project_code" in names


def test_is_git_available():
    config = WebConfig()
    svc = ProjectFileService(config)
    result = svc.is_git_available()
    assert isinstance(result, bool)


def test_get_project_path_tilde_expansion():
    config = WebConfig(data_root="~/reqradar_test_data")
    svc = ProjectFileService(config)
    path = svc.get_project_path("test")
    assert "~" not in str(path)
    assert str(path).endswith("test")


def test_clone_git_invalid_url(service, tmp_path):
    service.create_project_dirs("git-proj")
    with pytest.raises(RuntimeError):
        service.clone_git("git-proj", "https://invalid-url-that-does-not-exist-12345.com/repo.git")


def test_get_index_path(service, tmp_path):
    service.create_project_dirs("idx-proj")
    result = service.get_index_path("idx-proj")
    assert result == tmp_path / "data" / "idx-proj" / "index"


def test_get_memory_path(service, tmp_path):
    service.create_project_dirs("mem-proj")
    result = service.get_memory_path("mem-proj")
    assert result == tmp_path / "data" / "mem-proj" / "memory"


def test_get_requirements_path(service, tmp_path):
    service.create_project_dirs("req-proj")
    result = service.get_requirements_path("req-proj")
    assert result == tmp_path / "data" / "req-proj" / "requirements"


def test_project_name_validation_rejects_traversal(service):
    with pytest.raises(ValueError, match="Invalid project name"):
        service.get_project_path("../etc")


def test_project_name_validation_rejects_slashes(service):
    with pytest.raises(ValueError, match="Invalid project name"):
        service.get_project_path("foo/bar")


def test_project_name_validation_rejects_spaces(service):
    with pytest.raises(ValueError, match="Invalid project name"):
        service.get_project_path("bad name")


def test_extract_zip_rejects_path_traversal(service, tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../etc/crontab", "* * * * * root echo pwned\n")
    zip_bytes = zip_path.read_bytes()

    service.create_project_dirs("evil-proj")
    with pytest.raises(ValueError, match="path traversal"):
        service.extract_zip("evil-proj", zip_bytes)


def test_clone_git_rejects_disallowed_url_scheme(service, tmp_path):
    service.create_project_dirs("scheme-proj")
    with pytest.raises(ValueError, match="scheme not allowed"):
        service.clone_git("scheme-proj", "file:///etc/passwd")


def test_validate_local_path_accepts_allowed_prefix(service):
    result = service.validate_local_path("/tmp")
    assert result.is_dir()


def test_validate_local_path_rejects_nonexistent(service):
    with pytest.raises(ValueError, match="does not exist"):
        service.validate_local_path("/opt/nonexistent_dir_xyz_12345")


def test_validate_local_path_rejects_disallowed_prefix(service):
    with pytest.raises(ValueError, match="must be under one of"):
        service.validate_local_path("/etc")
