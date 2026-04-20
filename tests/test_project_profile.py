"""测试项目画像构建功能"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reqradar.agent.schemas import PROJECT_PROFILE_SCHEMA
from reqradar.agent.prompts import PROJECT_PROFILE_PROMPT
from reqradar.agent.project_profile import (
    _build_directory_structure,
    _build_file_stats,
    _build_key_files,
    _extract_dependencies,
    _infer_module_path,
    step_build_project_profile,
)
from reqradar.modules.code_parser import CodeFile, CodeGraph, CodeSymbol


class TestBuildFileStats:
    def test_basic_stats(self):
        files = [
            CodeFile(path="src/main.py", symbols=[CodeSymbol(name="main", type="function", line=1, end_line=10)]),
            CodeFile(path="src/utils.py", symbols=[CodeSymbol(name="helper", type="function", line=1, end_line=5)]),
            CodeFile(path="tests/test_main.py", symbols=[CodeSymbol(name="test_main", type="function", line=1, end_line=10)]),
        ]
        graph = CodeGraph(files=files)

        result = _build_file_stats(graph)

        assert "总文件数: 3" in result
        assert "总符号数: 3" in result
        assert ".py" in result

    def test_empty_graph(self):
        graph = CodeGraph(files=[])
        result = _build_file_stats(graph)
        assert "总文件数: 0" in result


class TestBuildDirectoryStructure:
    def test_basic_structure(self):
        files = [
            CodeFile(path="src/main.py", symbols=[]),
            CodeFile(path="src/utils/helper.py", symbols=[]),
            CodeFile(path="tests/test_main.py", symbols=[]),
        ]
        graph = CodeGraph(files=files)

        result = _build_directory_structure(graph)

        assert "src" in result
        assert "tests" in result

    def test_deep_paths(self):
        files = [
            CodeFile(path="a/b/c/d/e/file.py", symbols=[]),
        ]
        graph = CodeGraph(files=files)

        result = _build_directory_structure(graph)

        assert "a" in result
        assert "a/b" in result


class TestBuildKeyFiles:
    def test_files_with_symbols(self):
        files = [
            CodeFile(path="src/main.py", symbols=[
                CodeSymbol(name="main", type="function", line=1, end_line=10),
                CodeSymbol(name="helper", type="function", line=10, end_line=20),
            ]),
            CodeFile(path="src/utils.py", symbols=[
                CodeSymbol(name="util1", type="function", line=1, end_line=5),
            ]),
        ]
        graph = CodeGraph(files=files)

        result = _build_key_files(graph)

        assert "src/main.py" in result
        assert "main" in result or "helper" in result

    def test_files_without_symbols(self):
        files = [
            CodeFile(path="src/empty.py", symbols=[]),
        ]
        graph = CodeGraph(files=files)

        result = _build_key_files(graph)

        assert result == ""


class TestExtractDependencies:
    def test_pyproject_toml(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        result = _extract_dependencies(str(tmp_path))

        assert "pyproject.toml" in result
        assert "name = 'test'" in result

    def test_requirements_txt(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.0\n")

        result = _extract_dependencies(str(tmp_path))

        assert "requirements.txt" in result
        assert "requests" in result

    def test_no_dependency_files(self, tmp_path):
        result = _extract_dependencies(str(tmp_path))

        assert "未找到依赖文件" in result


class TestInferModulePath:
    def test_matching_path(self):
        files = [
            CodeFile(path="src/agent/steps.py", symbols=[]),
        ]
        graph = CodeGraph(files=files)

        result = _infer_module_path("agent", graph)

        assert "agent" in result or result == "src"

    def test_no_matching_path(self):
        files = [
            CodeFile(path="src/main.py", symbols=[]),
        ]
        graph = CodeGraph(files=files)

        result = _infer_module_path("nonexistent", graph)

        assert result == ""


class TestStepBuildProjectProfile:
    @pytest.mark.asyncio
    async def test_successful_build(self, tmp_path):
        files = [
            CodeFile(path="src/main.py", symbols=[
                CodeSymbol(name="main", type="function", line=1, end_line=10),
            ]),
            CodeFile(path="src/utils.py", symbols=[
                CodeSymbol(name="helper", type="function", line=1, end_line=5),
            ]),
        ]
        graph = CodeGraph(files=files)

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value={
            "description": "A test project",
            "architecture_style": "CLI application",
            "tech_stack": {
                "languages": ["Python"],
                "frameworks": ["Click"],
                "key_dependencies": ["httpx"],
            },
            "modules": [
                {
                    "name": "main",
                    "responsibility": "Main entry point",
                    "key_classes": ["main"],
                    "dependencies": [],
                },
            ],
        })

        mock_memory = MagicMock()
        mock_memory.update_project_profile = MagicMock()
        mock_memory.add_module = MagicMock()
        mock_memory.save = MagicMock()

        with patch("reqradar.agent.project_profile._extract_dependencies", return_value="pyproject.toml"):
            result = await step_build_project_profile(
                code_graph=graph,
                llm_client=mock_llm,
                memory_manager=mock_memory,
                repo_path=str(tmp_path),
            )

        assert result is not None
        assert "project_profile" in result
        assert result["project_profile"]["description"] == "A test project"

        mock_memory.update_project_profile.assert_called_once()
        mock_memory.add_module.assert_called()
        mock_memory.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_code_graph(self):
        graph = CodeGraph(files=[])
        mock_llm = AsyncMock()
        mock_memory = MagicMock()

        result = await step_build_project_profile(
            code_graph=graph,
            llm_client=mock_llm,
            memory_manager=mock_memory,
            repo_path=".",
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_llm_failure(self, tmp_path):
        files = [
            CodeFile(path="src/main.py", symbols=[CodeSymbol(name="main", type="function", line=1, end_line=10)]),
        ]
        graph = CodeGraph(files=files)

        mock_llm = AsyncMock()
        mock_llm.complete_structured = AsyncMock(return_value=None)
        mock_llm.complete = AsyncMock(return_value="")

        mock_memory = MagicMock()

        with patch("reqradar.agent.project_profile._extract_dependencies", return_value=""):
            result = await step_build_project_profile(
                code_graph=graph,
                llm_client=mock_llm,
                memory_manager=mock_memory,
                repo_path=str(tmp_path),
            )

        assert result == {}


class TestProjectProfileSchema:
    def test_schema_structure(self):
        assert PROJECT_PROFILE_SCHEMA["name"] == "build_project_profile"
        assert "parameters" in PROJECT_PROFILE_SCHEMA
        assert "properties" in PROJECT_PROFILE_SCHEMA["parameters"]
        assert "description" in PROJECT_PROFILE_SCHEMA["parameters"]["properties"]
        assert "architecture_style" in PROJECT_PROFILE_SCHEMA["parameters"]["properties"]
        assert "modules" in PROJECT_PROFILE_SCHEMA["parameters"]["properties"]
        assert "tech_stack" in PROJECT_PROFILE_SCHEMA["parameters"]["properties"]

    def test_required_fields(self):
        required = PROJECT_PROFILE_SCHEMA["parameters"]["required"]
        assert "description" in required
        assert "architecture_style" in required
        assert "modules" in required


class TestProjectProfilePrompt:
    def test_prompt_format(self):
        formatted = PROJECT_PROFILE_PROMPT.format(
            file_stats="10 files",
            directory_structure="src/\ntests/",
            key_files="src/main.py",
            dependencies_content="requests",
        )

        assert "10 files" in formatted
        assert "src/" in formatted
        assert "src/main.py" in formatted
        assert "requests" in formatted
