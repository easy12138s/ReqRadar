"""代码解析器 — Python AST 解析，提取模块/类/函数的结构化信息。"""

from __future__ import annotations

import ast
import contextlib
from dataclasses import dataclass, field
from pathlib import Path

from reqradar.kernel.exceptions import IngestionException


@dataclass
class CodeModuleData:
    """代码模块/类/函数的结构化数据。"""

    module_type: str  # module / class / function / method
    qualified_name: str  # e.g. "reqradar.kernel.models.Project"
    short_name: str  # e.g. "Project"
    file_path: str
    line_start: int
    line_end: int | None = None
    signature: str | None = None
    docstring: str | None = None
    imports: list[str] = field(default_factory=list)
    parent_name: str | None = None  # 父级 qualified_name


class CodeParser:
    """Python AST 解析 — 提取模块/类/函数/方法的结构化信息。"""

    MAX_FILES: int = 1000

    def parse_file(self, file_path: Path) -> list[CodeModuleData]:
        """解析单个 Python 文件。

        Args:
            file_path: .py 文件路径

        Returns:
            CodeModuleData 列表（1 个 module + N 个 class/function/method）
        """
        if not file_path.suffix == ".py":
            raise IngestionException(
                f"不支持的文件类型: {file_path.suffix}，仅支持 .py",
                detail={"file_path": str(file_path)},
            )

        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            raise IngestionException(
                f"文件读取失败: {file_path}",
                detail={"file_path": str(file_path), "error": str(e)},
            ) from e

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            raise IngestionException(
                f"Python 语法错误: {file_path}",
                detail={"file_path": str(file_path), "error": str(e)},
            ) from e

        results: list[CodeModuleData] = []

        # 模块级
        module_doc = ast.get_docstring(tree)
        module_imports = self._extract_imports(tree)
        module_name = file_path.stem

        results.append(
            CodeModuleData(
                module_type="module",
                qualified_name=module_name,
                short_name=module_name,
                file_path=str(file_path),
                line_start=1,
                line_end=len(source.splitlines()) or None,
                docstring=module_doc,
                imports=module_imports,
            )
        )

        # 遍历顶层节点
        for node in ast.iter_child_nodes(tree):
            results.extend(self._parse_node(node, file_path, parent_name=module_name))

        return results

    def parse_directory(
        self, dir_path: Path, max_files: int | None = None
    ) -> list[CodeModuleData]:
        """递归解析目录下所有 .py 文件。

        Args:
            dir_path: 目录路径
            max_files: 最大文件数限制

        Returns:
            CodeModuleData 列表
        """
        limit = max_files if max_files is not None else self.MAX_FILES

        py_files = sorted(dir_path.rglob("*.py"))
        if len(py_files) > limit:
            raise IngestionException(
                f"文件数过多: {len(py_files)} (最大 {limit})",
                detail={"dir_path": str(dir_path), "file_count": len(py_files)},
            )

        results: list[CodeModuleData] = []
        for py_file in py_files:
            with contextlib.suppress(IngestionException):
                results.extend(self.parse_file(py_file))

        return results

    def _parse_node(
        self,
        node: ast.AST,
        file_path: Path,
        parent_name: str,
    ) -> list[CodeModuleData]:
        """递归解析 AST 节点。"""
        results: list[CodeModuleData] = []

        if isinstance(node, ast.ClassDef):
            qualified = f"{parent_name}.{node.name}"
            docstring = ast.get_docstring(node)
            bases = [ast.unparse(b) for b in node.bases] if node.bases else []
            sig = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"

            results.append(
                CodeModuleData(
                    module_type="class",
                    qualified_name=qualified,
                    short_name=node.name,
                    file_path=str(file_path),
                    line_start=node.lineno,
                    line_end=node.end_lineno,
                    signature=sig,
                    docstring=docstring,
                    parent_name=parent_name,
                )
            )
            # 递归解析类内方法
            for child in ast.iter_child_nodes(node):
                results.extend(self._parse_node(child, file_path, parent_name=qualified))

        elif isinstance(node, ast.FunctionDef):
            parent_is_class = hasattr(node, "_parent_is_class") or parent_name.split(".")[-1][0].isupper() if parent_name else False
            node_type = "method" if parent_is_class else "function"
            qualified = f"{parent_name}.{node.name}"
            docstring = ast.get_docstring(node)
            args = [a.arg for a in node.args.args]
            sig = f"def {node.name}({', '.join(args)})"

            results.append(
                CodeModuleData(
                    module_type=node_type,
                    qualified_name=qualified,
                    short_name=node.name,
                    file_path=str(file_path),
                    line_start=node.lineno,
                    line_end=node.end_lineno,
                    signature=sig,
                    docstring=docstring,
                    parent_name=parent_name,
                )
            )

        elif isinstance(node, ast.AsyncFunctionDef):
            docstring = ast.get_docstring(node)
            args = [a.arg for a in node.args.args]
            qualified = f"{parent_name}.{node.name}"
            sig = f"async def {node.name}({', '.join(args)})"

            results.append(
                CodeModuleData(
                    module_type="function",
                    qualified_name=qualified,
                    short_name=node.name,
                    file_path=str(file_path),
                    line_start=node.lineno,
                    line_end=node.end_lineno,
                    signature=sig,
                    docstring=docstring,
                    parent_name=parent_name,
                )
            )

        return results

    @staticmethod
    def _extract_imports(tree: ast.Module) -> list[str]:
        """提取模块的导入列表。"""
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return sorted(set(imports))
