import io
import zipfile

import pytest

from reqradar.web.services.project_file_service import ProjectFileService


def make_zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def test_create_project_dirs_creates_expected_layout(tmp_path):
    service = ProjectFileService(tmp_path)

    service.create_project_dirs("sample_project")

    project_path = tmp_path / "sample_project"
    assert (project_path / "project_code").is_dir()
    assert (project_path / "requirements").is_dir()
    assert (project_path / "index").is_dir()


def test_invalid_project_name_is_rejected(tmp_path):
    service = ProjectFileService(tmp_path)

    with pytest.raises(ValueError, match="Invalid project name"):
        service.get_project_path("../unsafe")


def test_extract_zip_rejects_path_traversal(tmp_path):
    service = ProjectFileService(tmp_path)
    service.create_project_dirs("safe_project")

    with pytest.raises(ValueError, match="Zip path traversal detected"):
        service.extract_zip("safe_project", make_zip({"../evil.py": "bad"}))


def test_extract_zip_and_get_file_tree(tmp_path):
    service = ProjectFileService(tmp_path)
    service.create_project_dirs("safe_project")

    service.extract_zip(
        "safe_project",
        make_zip({"pkg/app.py": "print('ok')", "README.md": "# Title"}),
    )

    tree = service.get_file_tree("safe_project")
    names = {item["name"] for item in tree}

    assert "project_code" in names
    assert "project.zip" in names


def test_delete_project_files_removes_only_project_directory(tmp_path):
    service = ProjectFileService(tmp_path)
    service.create_project_dirs("sample_project")

    service.delete_project_files("sample_project")

    assert not (tmp_path / "sample_project").exists()
    assert tmp_path.exists()


def test_validate_local_path_rejects_missing_path(tmp_path):
    service = ProjectFileService(tmp_path)

    with pytest.raises(ValueError, match="Local path does not exist"):
        service.validate_local_path(str(tmp_path / "missing"))
