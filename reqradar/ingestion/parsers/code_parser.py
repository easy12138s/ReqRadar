"""代码解析器 — 多语言 AST 解析，提取模块/类/函数的结构化信息。

支持语言：Python (.py), JavaScript (.js), TypeScript (.ts/.tsx), Java (.java), Go (.go)
使用 tree-sitter 进行精确的语法解析。
"""

from __future__ import annotations

import ast
import contextlib
from dataclasses import dataclass, field
from pathlib import Path

from reqradar.kernel.exceptions import IngestionException

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".java", ".go"}

# tree-sitter 语言映射
_TS_LANGUAGES: dict[str, object] = {}


def _get_ts_language(ext: str) -> object | None:
    """获取 tree-sitter 语言对象（延迟加载）。"""
    if ext in _TS_LANGUAGES:
        return _TS_LANGUAGES[ext]

    try:
        if ext in (".js",):
            import tree_sitter_javascript as tsjs

            lang = tsjs.language()
        elif ext in (".ts", ".tsx"):
            import tree_sitter_typescript as tsts

            lang = tsts.language_tsx() if ext == ".tsx" else tsts.language_typescript()
        elif ext == ".java":
            import tree_sitter_java as tsjava

            lang = tsjava.language()
        elif ext == ".go":
            import tree_sitter_go as tsgo

            lang = tsgo.language()
        else:
            return None

        _TS_LANGUAGES[ext] = lang
        return lang
    except ImportError:
        return None


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
        else:
            return self._parse_with_tree_sitter(file_path, source, suffix)

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
        """解析 Python 文件（使用 ast 模块）。"""
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
        module_imports = self._extract_python_imports(tree)
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
            results.extend(self._parse_python_node(node, file_path, parent_name=module_name))

        return results

    def _parse_with_tree_sitter(
        self, file_path: Path, source: str, ext: str
    ) -> list[CodeModuleData]:
        """使用 tree-sitter 解析非 Python 文件。"""
        from tree_sitter import Language, Parser

        ts_lang = _get_ts_language(ext)
        if ts_lang is None:
            raise IngestionException(
                f"tree-sitter 语言包未安装: {ext}",
                detail={"file_path": str(file_path)},
            )

        parser = Parser(Language(ts_lang))
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node

        module_name = file_path.stem
        results: list[CodeModuleData] = []

        # 提取 imports
        imports = self._extract_ts_imports(root, source)

        results.append(
            CodeModuleData(
                module_type="module",
                qualified_name=module_name,
                short_name=module_name,
                file_path=str(file_path),
                line_start=1,
                line_end=root.end_point[0] + 1,
                imports=imports,
            )
        )

        # 递归遍历 AST 节点
        self._walk_ts_nodes(root, file_path, source, module_name, results)

        return results

    def _walk_ts_nodes(
        self,
        node,
        file_path: Path,
        source: str,
        parent_name: str,
        results: list[CodeModuleData],
    ) -> None:
        """递归遍历 tree-sitter AST 节点。"""
        node_type = node.type

        # 类声明
        if node_type in ("class_declaration", "class"):
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = source[name_node.start_byte:name_node.end_byte]
                qualified = f"{parent_name}.{class_name}"

                # 提取类签名
                signature = self._extract_ts_signature(node, source)

                # 提取 docstring（JSDoc 等）
                docstring = self._extract_ts_docstring(node, source)

                results.append(
                    CodeModuleData(
                        module_type="class",
                        qualified_name=qualified,
                        short_name=class_name,
                        file_path=str(file_path),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=signature,
                        docstring=docstring,
                        parent_name=parent_name,
                    )
                )

                # 递归解析类体
                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        self._walk_ts_nodes(child, file_path, source, qualified, results)

        # 函数声明
        elif node_type in (
            "function_declaration",
            "function",
            "method_definition",
            "method_signature",
        ):
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = source[name_node.start_byte:name_node.end_byte]
                qualified = f"{parent_name}.{func_name}"

                # 判断是方法还是函数
                is_method = node_type in ("method_definition", "method_signature")

                # 提取函数签名
                signature = self._extract_ts_signature(node, source)

                # 提取 docstring
                docstring = self._extract_ts_docstring(node, source)

                results.append(
                    CodeModuleData(
                        module_type="method" if is_method else "function",
                        qualified_name=qualified,
                        short_name=func_name,
                        file_path=str(file_path),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=signature,
                        docstring=docstring,
                        parent_name=parent_name,
                    )
                )

        # 箭头函数 / 变量声明中的函数
        elif node_type in ("lexical_declaration", "variable_declaration"):
            # 检查是否是 const/let/var func = () => {}
            for child in node.children:
                if child.type == "variable_declarator":
                    value_node = child.child_by_field_name("value")
                    if value_node and value_node.type in (
                        "arrow_function",
                        "function",
                        "function_expression",
                    ):
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            func_name = source[name_node.start_byte:name_node.end_byte]
                            qualified = f"{parent_name}.{func_name}"
                            signature = self._extract_ts_signature(node, source)

                            results.append(
                                CodeModuleData(
                                    module_type="function",
                                    qualified_name=qualified,
                                    short_name=func_name,
                                    file_path=str(file_path),
                                    line_start=node.start_point[0] + 1,
                                    line_end=node.end_point[0] + 1,
                                    signature=signature,
                                    parent_name=parent_name,
                                )
                            )

        # Go: struct 和 interface
        elif node_type in ("type_declaration",):
            for child in node.children:
                if child.type == "type_spec":
                    name_node = child.child_by_field_name("name")
                    type_node = child.child_by_field_name("type")
                    if name_node and type_node:
                        type_name = source[name_node.start_byte:name_node.end_byte]
                        qualified = f"{parent_name}.{type_name}"

                        if type_node.type == "struct_type":
                            results.append(
                                CodeModuleData(
                                    module_type="class",
                                    qualified_name=qualified,
                                    short_name=type_name,
                                    file_path=str(file_path),
                                    line_start=child.start_point[0] + 1,
                                    line_end=child.end_point[0] + 1,
                                    signature=f"type {type_name} struct",
                                    parent_name=parent_name,
                                )
                            )
                        elif type_node.type == "interface_type":
                            results.append(
                                CodeModuleData(
                                    module_type="class",
                                    qualified_name=qualified,
                                    short_name=type_name,
                                    file_path=str(file_path),
                                    line_start=child.start_point[0] + 1,
                                    line_end=child.end_point[0] + 1,
                                    signature=f"type {type_name} interface",
                                    parent_name=parent_name,
                                )
                            )

        # Go: func 声明
        elif node_type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = source[name_node.start_byte:name_node.end_byte]
                qualified = f"{parent_name}.{func_name}"
                signature = self._extract_ts_signature(node, source)

                results.append(
                    CodeModuleData(
                        module_type="function",
                        qualified_name=qualified,
                        short_name=func_name,
                        file_path=str(file_path),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=signature,
                        parent_name=parent_name,
                    )
                )

        # 递归遍历子节点（对于非类/函数节点）
        else:
            for child in node.children:
                self._walk_ts_nodes(child, file_path, source, parent_name, results)

    def _extract_ts_signature(self, node, source: str) -> str | None:
        """提取 tree-sitter 节点的签名。"""
        try:
            # 提取到第一个 { 或 : 之前的内容作为签名
            text = source[node.start_byte:node.end_byte]
            # 限制签名长度
            lines = text.split("\n")
            sig_lines = []
            for line in lines[:5]:  # 最多取 5 行
                sig_lines.append(line)
                if "{" in line:
                    break
            return "\n".join(sig_lines).strip()
        except Exception:
            return None

    def _extract_ts_docstring(self, node, source: str) -> str | None:
        """提取 tree-sitter 节点的文档注释。"""
        try:
            # 查找前一个兄弟节点是否是注释
            prev_sibling = node.prev_sibling
            if prev_sibling and prev_sibling.type in ("comment", "block_comment"):
                comment_text = source[prev_sibling.start_byte:prev_sibling.end_byte]
                # 清理注释标记
                for prefix in ("/**", "/*", "//", "*/", "*"):
                    comment_text = comment_text.replace(prefix, "")
                return comment_text.strip()
            return None
        except Exception:
            return None

    def _extract_ts_imports(self, node, source: str) -> list[str]:
        """提取 tree-sitter AST 中的导入语句。"""
        imports = []
        self._collect_imports(node, source, imports)
        return sorted(set(imports))

    def _collect_imports(self, node, source: str, imports: list[str]) -> None:
        """递归收集导入语句。"""
        if node.type == "import_statement":
            # 提取 import 来源
            for child in node.children:
                if child.type == "string":
                    import_path = source[child.start_byte + 1 : child.end_byte - 1]  # 去掉引号
                    imports.append(import_path)

        elif node.type == "import_declaration":
            # Java import
            for child in node.children:
                if child.type == "scoped_identifier":
                    imports.append(source[child.start_byte:child.end_byte])

        elif node.type == "import_spec":
            # Go import
            for child in node.children:
                if child.type == "interpreted_string_literal":
                    import_path = source[child.start_byte + 1 : child.end_byte - 1]
                    imports.append(import_path)

        # 递归子节点
        for child in node.children:
            self._collect_imports(child, source, imports)

    def _parse_python_node(
        self,
        node: ast.AST,
        file_path: Path,
        parent_name: str,
    ) -> list[CodeModuleData]:
        """递归解析 Python AST 节点。"""
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
                results.extend(self._parse_python_node(child, file_path, parent_name=qualified))

        elif isinstance(node, ast.FunctionDef):
            parent_is_class = (
                hasattr(node, "_parent_is_class")
                or parent_name.split(".")[-1][0].isupper()
                if parent_name
                else False
            )
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
    def _extract_python_imports(tree: ast.Module) -> list[str]:
        """提取 Python 模块的导入列表。"""
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return sorted(set(imports))
