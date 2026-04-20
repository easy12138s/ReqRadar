import json
import textwrap
from pathlib import Path

import pytest

from reqradar.core.exceptions import ParseException
from reqradar.modules.code_parser import CodeFile, CodeGraph, CodeParser, CodeSymbol, PythonCodeParser


def test_code_symbol_creation():
    sym = CodeSymbol(name="foo", type="function", line=1, end_line=10)
    assert sym.name == "foo"
    assert sym.type == "function"
    assert sym.line == 1
    assert sym.end_line == 10
    assert sym.parent is None
    assert sym.children == []


def test_code_symbol_with_parent_children():
    sym = CodeSymbol(name="bar", type="function", line=5, end_line=8, parent="Foo", children=["baz"])
    assert sym.parent == "Foo"
    assert sym.children == ["baz"]


def test_code_file_creation():
    symbols = [CodeSymbol(name="func", type="function", line=1, end_line=3)]
    imports = ["os"]
    cf = CodeFile(path="test.py", symbols=symbols, imports=imports)
    assert cf.path == "test.py"
    assert len(cf.symbols) == 1
    assert cf.symbols[0].name == "func"
    assert cf.imports == ["os"]
    assert cf.call_graph == {}


def test_code_file_defaults():
    cf = CodeFile(path="empty.py")
    assert cf.symbols == []
    assert cf.imports == []
    assert cf.call_graph == {}


def test_code_graph_creation():
    graph = CodeGraph()
    assert graph.files == []
    assert graph.module_dependencies == {}


def test_code_graph_to_json_from_json_roundtrip():
    symbols = [
        CodeSymbol(name="MyClass", type="class", line=1, end_line=10),
        CodeSymbol(name="my_func", type="function", line=2, end_line=5),
    ]
    files = [CodeFile(path="app.py", symbols=symbols, imports=["os", "from sys import exit"])]
    graph = CodeGraph(files=files)

    json_str = graph.to_json()
    data = json.loads(json_str)
    assert len(data["files"]) == 1
    assert data["files"][0]["path"] == "app.py"
    assert len(data["files"][0]["symbols"]) == 2
    assert data["files"][0]["symbols"][0]["name"] == "MyClass"
    assert data["files"][0]["symbols"][1]["type"] == "function"
    assert data["files"][0]["imports"] == ["os", "from sys import exit"]


def test_code_parser_is_abstract():
    parser = CodeParser()
    with pytest.raises(NotImplementedError):
        parser.parse_file(Path("dummy.py"))
    with pytest.raises(NotImplementedError):
        parser.parse_directory(Path("."))


def test_parse_file_functions_and_classes(tmp_path):
    code = textwrap.dedent("""\
        import os
        from sys import exit

        def hello():
            pass

        class Foo:
            def bar(self):
                pass
    """)
    py_file = tmp_path / "sample.py"
    py_file.write_text(code, encoding="utf-8")

    parser = PythonCodeParser()
    result = parser.parse_file(py_file)

    assert result.path == str(py_file)
    assert "os" in result.imports
    assert "from sys import exit" in result.imports

    symbol_names = {s.name for s in result.symbols}
    assert "hello" in symbol_names
    assert "Foo" in symbol_names
    assert "bar" in symbol_names

    hello_sym = next(s for s in result.symbols if s.name == "hello")
    assert hello_sym.type == "function"

    foo_sym = next(s for s in result.symbols if s.name == "Foo")
    assert foo_sym.type == "class"


def test_parse_file_syntax_error(tmp_path):
    bad_code = "def broken(:\n"
    py_file = tmp_path / "bad.py"
    py_file.write_text(bad_code, encoding="utf-8")

    parser = PythonCodeParser()
    with pytest.raises(ParseException):
        parser.parse_file(py_file)


def test_parse_file_nonexistent(tmp_path):
    parser = PythonCodeParser()
    with pytest.raises(ParseException):
        parser.parse_file(tmp_path / "no_such_file.py")


def test_parse_directory_multiple_files(tmp_path):
    (tmp_path / "a.py").write_text("def alpha():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("class Beta:\n    pass\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("import os\n\ndef gamma():\n    pass\n", encoding="utf-8")

    parser = PythonCodeParser()
    graph = parser.parse_directory(tmp_path)

    assert len(graph.files) == 3
    all_symbols = [s for f in graph.files for s in f.symbols]
    symbol_names = {s.name for s in all_symbols}
    assert "alpha" in symbol_names
    assert "Beta" in symbol_names
    assert "gamma" in symbol_names


def test_parse_directory_skips_pycache(tmp_path):
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "cached.py").write_text("def internal():\n    pass\n", encoding="utf-8")
    (tmp_path / "real.py").write_text("def external():\n    pass\n", encoding="utf-8")

    parser = PythonCodeParser()
    graph = parser.parse_directory(tmp_path)

    assert len(graph.files) == 1
    assert graph.files[0].path == str(tmp_path / "real.py")


def test_parse_directory_with_extensions(tmp_path):
    (tmp_path / "a.py").write_text("def py_func():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.pyi").write_text("def pyi_func(): ...\n", encoding="utf-8")

    parser = PythonCodeParser()
    graph = parser.parse_directory(tmp_path, extensions=[".py", ".pyi"])

    assert len(graph.files) == 2


def test_parse_directory_skips_unparseable_files(tmp_path):
    (tmp_path / "good.py").write_text("def ok():\n    pass\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")

    parser = PythonCodeParser()
    graph = parser.parse_directory(tmp_path)

    assert len(graph.files) == 1
    assert graph.files[0].path == str(tmp_path / "good.py")
