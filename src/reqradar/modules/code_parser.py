"""代码解析器 - Python AST"""

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from reqradar.core.exceptions import ParseException


@dataclass
class CodeSymbol:
    name: str
    type: str
    line: int
    end_line: int
    parent: Optional[str] = None
    children: list[str] = field(default_factory=list)


@dataclass
class CodeFile:
    path: str
    symbols: list[CodeSymbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    call_graph: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class CodeGraph:
    files: list[CodeFile] = field(default_factory=list)
    module_dependencies: dict[str, list[str]] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "files": [
                    {
                        "path": f.path,
                        "symbols": [
                            {"name": s.name, "type": s.type, "line": s.line, "end_line": s.end_line}
                            for s in f.symbols
                        ],
                        "imports": f.imports,
                    }
                    for f in self.files
                ]
            },
            indent=2,
        )

    def find_symbols(self, keywords: list[str]) -> list[CodeFile]:
        results = []
        for f in self.files:
            for kw in keywords:
                if kw.lower() in f.path.lower():
                    results.append(f)
                    break
                for sym in f.symbols:
                    if kw.lower() in sym.name.lower():
                        results.append(f)
                        break
        return results


class CodeParser:
    """代码解析器基类"""

    def __init__(self):
        self.graph = CodeGraph()

    def parse_file(self, file_path: Path) -> CodeFile:
        raise NotImplementedError

    def parse_directory(self, directory: Path) -> CodeGraph:
        raise NotImplementedError


class PythonCodeParser(CodeParser):
    """Python 代码解析器 - 基于 AST"""

    def parse_file(self, file_path: Path) -> CodeFile:
        """解析单个 Python 文件"""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            symbols = []
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    symbols.append(
                        CodeSymbol(
                            name=node.name,
                            type="function",
                            line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                        )
                    )
                elif isinstance(node, ast.ClassDef):
                    symbols.append(
                        CodeSymbol(
                            name=node.name,
                            type="class",
                            line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                        )
                    )
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        if isinstance(node, ast.Import):
                            imports.append(alias.name)
                        else:
                            imports.append(f"from {node.module} import {alias.name}")

            return CodeFile(
                path=str(file_path),
                symbols=symbols,
                imports=imports,
            )
        except SyntaxError as e:
            raise ParseException(f"Syntax error in {file_path}: {e}", cause=e)
        except Exception as e:
            raise ParseException(f"Failed to parse {file_path}: {e}", cause=e)

    def parse_directory(self, directory: Path, extensions: list[str] = None) -> CodeGraph:
        """解析目录下所有 Python 文件"""
        if extensions is None:
            extensions = [".py"]

        graph = CodeGraph()

        for ext in extensions:
            for file_path in directory.rglob(f"*{ext}"):
                if "__pycache__" in str(file_path):
                    continue
                try:
                    code_file = self.parse_file(file_path)
                    graph.files.append(code_file)
                except ParseException:
                    pass

        return graph
