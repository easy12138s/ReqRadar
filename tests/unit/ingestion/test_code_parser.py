"""代码解析器单元测试 — Python AST 解析。"""

from __future__ import annotations

from pathlib import Path

import pytest

from reqradar.ingestion.parsers.code_parser import CodeParser


class TestCodeParser:
    """代码解析器测试。"""

    def test_parse_single_file(self, tmp_path: Path) -> None:
        """解析单文件应提取 module/class/function。"""
        py_file = tmp_path / "test_module.py"
        py_file.write_text(
            '"""Module docstring."""\n\n'
            "import os\n\n"
            "class MyClass:\n"
            '    """Class docstring."""\n'
            "    def method(self, x):\n"
            '        """Method docstring."""\n'
            "        return x + 1\n\n"
            "def top_func(a: int) -> int:\n"
            '    """Function docstring."""\n'
            "    return a * 2\n",
            encoding="utf-8",
        )

        parser = CodeParser()
        results = parser.parse_file(py_file)

        modules = [r for r in results if r.module_type == "module"]
        classes = [r for r in results if r.module_type == "class"]
        methods = [r for r in results if r.module_type == "method"]
        functions = [r for r in results if r.module_type == "function"]

        assert len(modules) == 1
        assert modules[0].module_type == "module"
        assert len(classes) == 1
        assert classes[0].short_name == "MyClass"
        assert len(methods) == 1
        assert methods[0].short_name == "method"
        assert len(functions) == 1
        assert functions[0].short_name == "top_func"

    def test_parse_directory(self, tmp_path: Path) -> None:
        """解析目录应处理多个文件。"""
        (tmp_path / "a.py").write_text("def foo(): pass\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("def bar(): pass\n", encoding="utf-8")

        parser = CodeParser()
        results = parser.parse_directory(tmp_path, max_files=10)

        foo_results = [r for r in results if r.short_name == "foo"]
        bar_results = [r for r in results if r.short_name == "bar"]
        assert len(foo_results) >= 1
        assert len(bar_results) >= 1

    def test_non_python_file_skipped(self) -> None:
        """非 .py 文件应抛出异常。"""
        parser = CodeParser()
        with pytest.raises(Exception):  # noqa: B017
            parser.parse_file(Path("/tmp/test.txt"))
