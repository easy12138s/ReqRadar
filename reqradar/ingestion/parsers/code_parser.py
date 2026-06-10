"""代码解析器 — 多语言代码解析，提取模块/类/函数的结构化信息。

支持语言：Python (.py), JavaScript (.js), TypeScript (.ts/.tsx), Java (.java), Go (.go)
"""

from __future__ import annotations

import ast
import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from reqradar.kernel.exceptions import IngestionException

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".java", ".go"}


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
    """多语言代码解析 — 提取模块/类/函数/方法的结构化信息。"""

    MAX_FILES: int = 1000

    def parse_file(self, file_path: Path) -> list[CodeModuleData]:
        """解析单个代码文件。

        Args:
            file_path: 代码文件路径

        Returns:
            CodeModuleData 列表
        """
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise IngestionException(
                f"不支持的文件类型: {suffix}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                detail={"file_path": str(file_path)},
            )

        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            raise IngestionException(
                f"文件读取失败: {file_path}",
                detail={"file_path": str(file_path), "error": str(e)},
            ) from e

        if suffix == ".py":
            return self._parse_python(file_path, source)
        elif suffix in (".js", ".ts", ".tsx"):
            return self._parse_javascript(file_path, source)
        elif suffix == ".java":
            return self._parse_java(file_path, source)
        elif suffix == ".go":
            return self._parse_go(file_path, source)
        else:
            return []

    def parse_directory(
        self, dir_path: Path, max_files: int | None = None
    ) -> list[CodeModuleData]:
        """递归解析目录下所有支持的代码文件。

        Args:
            dir_path: 目录路径
            max_files: 最大文件数限制

        Returns:
            CodeModuleData 列表
        """
        limit = max_files if max_files is not None else self.MAX_FILES

        code_files = []
        for ext in SUPPORTED_EXTENSIONS:
            code_files.extend(dir_path.rglob(f"*{ext}"))
        code_files = sorted(code_files)

        if len(code_files) > limit:
            raise IngestionException(
                f"文件数过多: {len(code_files)} (最大 {limit})",
                detail={"dir_path": str(dir_path), "file_count": len(code_files)},
            )

        results: list[CodeModuleData] = []
        for code_file in code_files:
            with contextlib.suppress(IngestionException):
                results.extend(self.parse_file(code_file))

        return results

    def _parse_python(self, file_path: Path, source: str) -> list[CodeModuleData]:
        """解析 Python 文件。"""
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

    def _parse_javascript(self, file_path: Path, source: str) -> list[CodeModuleData]:
        """解析 JavaScript/TypeScript 文件（基于正则）。"""
        results: list[CodeModuleData] = []
        module_name = file_path.stem
        lines = source.splitlines()

        results.append(
            CodeModuleData(
                module_type="module",
                qualified_name=module_name,
                short_name=module_name,
                file_path=str(file_path),
                line_start=1,
                line_end=len(lines) or None,
            )
        )

        # 提取 import 语句
        imports = []
        for line in lines:
            match = re.match(r'import\s+.*?from\s+["\'](.+?)["\']', line)
            if match:
                imports.append(match.group(1))
        results[0].imports = imports

        # 提取 class 定义
        for i, line in enumerate(lines, 1):
            match = re.match(r'export\s+)?class\s+(\w+)', line)
            if match:
                class_name = match.group(2)
                results.append(
                    CodeModuleData(
                        module_type="class",
                        qualified_name=f"{module_name}.{class_name}",
                        short_name=class_name,
                        file_path=str(file_path),
                        line_start=i,
                        parent_name=module_name,
                    )
                )

        # 提取 function 定义
        for i, line in enumerate(lines, 1):
            match = re.match(r'export\s+)?(async\s+)?function\s+(\w+)', line)
            if match:
                func_name = match.group(2)
                results.append(
                    CodeModuleData(
                        module_type="function",
                        qualified_name=f"{module_name}.{func_name}",
                        short_name=func_name,
                        file_path=str(file_path),
                        line_start=i,
                        parent_name=module_name,
                    )
                )

        return results

    def _parse_java(self, file_path: Path, source: str) -> list[CodeModuleData]:
        """解析 Java 文件（基于正则）。"""
        results: list[CodeModuleData] = []
        lines = source.splitlines()

        # 提取 package 名
        package = ""
        for line in lines:
            match = re.match(r'package\s+([\w.]+);', line)
            if match:
                package = match.group(1)
                break

        # 提取 import 语句
        imports = []
        for line in lines:
            match = re.match(r'import\s+([\w.]+);', line)
            if match:
                imports.append(match.group(1))

        # 提取 class/interface 定义
        for i, line in enumerate(lines, 1):
            match = re.match(r'.*?(class|interface|enum)\s+(\w+)', line)
            if match:
                class_name = match.group(2)
                qualified = f"{package}.{class_name}" if package else class_name
                results.append(
                    CodeModuleData(
                        module_type="class",
                        qualified_name=qualified,
                        short_name=class_name,
                        file_path=str(file_path),
                        line_start=i,
                        imports=imports,
                    )
                )

        return results

    def _parse_go(self, file_path: Path, source: str) -> list[CodeModuleData]:
        """解析 Go 文件（基于正则）。"""
        results: list[CodeModuleData] = []
        lines = source.splitlines()

        # 提取 package 名
        package = ""
        for line in lines:
            match = re.match(r'package\s+(\w+)', line)
            if match:
                package = match.group(1)
                break

        module_name = file_path.stem

        results.append(
            CodeModuleData(
                module_type="module",
                qualified_name=f"{package}.{module_name}" if package else module_name,
                short_name=module_name,
                file_path=str(file_path),
                line_start=1,
                line_end=len(lines) or None,
            )
        )

        # 提取 import 块
        imports = []
        in_import = False
        for line in lines:
            if line.strip() == "import (":
                in_import = True
                continue
            if in_import:
                if line.strip() == ")":
                    in_import = False
                    continue
                match = re.match(r'\s*"(.+?)"', line)
                if match:
                    imports.append(match.group(1))
        results[0].imports = imports

        # 提取 struct 和 func 定义
        for i, line in enumerate(lines, 1):
            struct_match = re.match(r'type\s+(\w+)\s+struct', line)
            if struct_match:
                struct_name = struct_match.group(1)
                results.append(
                    CodeModuleData(
                        module_type="class",
                        qualified_name=f"{package}.{struct_name}" if package else struct_name,
                        short_name=struct_name,
                        file_path=str(file_path),
                        line_start=i,
                        parent_name=package,
                    )
                )

            func_match = re.match(r'func\s+(?:\([^)]+\)\s+)?(\w+)', line)
            if func_match:
                func_name = func_match.group(1)
                results.append(
                    CodeModuleData(
                        module_type="function",
                        qualified_name=f"{package}.{func_name}" if package else func_name,
                        short_name=func_name,
                        file_path=str(file_path),
                        line_start=i,
                        parent_name=package,
                    )
                )

        return results

    def _parse_node(
        self,
        node: ast.AST,
        file_path: Path,
        parent_name: str,
    ) -> list[CodeModuleData]:
        """递归解析 AST 节点（Python 专用）。"""
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
        """提取模块的导入列表（Python 专用）。"""
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return sorted(set(imports))
