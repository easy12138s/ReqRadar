#!/usr/bin/env python3
"""校验 reqradar 模块依赖规则。

在 CI 中运行，或在本地通过 `python scripts/check_dependencies.py` 执行。
依赖规则定义见 docs/detailed/C-02_MODULE_DEPENDENCY_MAP.md 第 6 节。
"""
import ast
import sys
from pathlib import Path

# 定义禁止的依赖方向：key 所在目录禁止 import value 中的任何模块
FORBIDDEN = {
    "kernel": ["web", "modules", "agent", "mcp", "cli"],
    "modules": ["web", "agent", "cli"],
    "agent": ["web", "cli"],
    "mcp": ["web", "agent", "cli"],
}

# 同层隔离目录：这些目录下的文件之间禁止互相 import
SAME_LAYER_ISOLATED = [
    "web/api",
    "web/services",
    "agent/tools",
    "agent/prompts",
]


def get_imports(file_path: Path) -> list[str]:
    """提取文件中所有 reqradar 内部 import。"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("reqradar."):
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("reqradar."):
                imports.append(node.module)
    return imports


def get_layer(file_path: Path, src_root: Path) -> str | None:
    """从文件路径提取所属 layer 名。"""
    rel = file_path.relative_to(src_root)
    parts = rel.parts
    if len(parts) < 2 or parts[0] != "reqradar":
        return None
    return parts[1]


def get_dir_key(file_path: Path, src_root: Path) -> str:
    """从文件路径提取目录路径（用于同层隔离检查）。"""
    rel = file_path.relative_to(src_root)
    parts = list(rel.parts[:-1])  # 去掉文件名
    return "/".join(parts)


def check_violations(src_root: Path) -> list[str]:
    """检查所有文件的依赖违规。"""
    violations: list[str] = []
    for py_file in sorted(src_root.rglob("*.py")):
        layer = get_layer(py_file, src_root)
        if layer is None:
            continue

        # 同层隔离检查
        dir_key = get_dir_key(py_file, src_root)
        for isolated_dir in SAME_LAYER_ISOLATED:
            if dir_key.startswith(isolated_dir):
                for imp in get_imports(py_file):
                    imp_parts = imp.split(".")
                    imp_dir = "/".join(imp_parts[:-1]) if len(imp_parts) > 1 else ""
                    imp_target_dir = f"reqradar/{imp_dir}"
                    if imp_target_dir.startswith(isolated_dir):
                        # 检查是否为同目录但不同文件
                        source_file = py_file.stem
                        # 如果 import 路径指向同目录（最后一段是文件名或相同前缀）
                        if len(imp_parts) >= 2 and imp_parts[-2] == py_file.parent.stem:
                            if imp_parts[-1] != py_file.stem:
                                violations.append(
                                    f"D-11/D-12/D-13/D-14 同层隔离违规: "
                                    f"{py_file.relative_to(src_root)} import {imp} "
                                    f"({isolated_dir} 内文件禁止互相 import)"
                                )

        # 跨层依赖检查
        if layer not in FORBIDDEN:
            continue
        forbidden_targets = FORBIDDEN[layer]
        for imp in get_imports(py_file):
            imp_parts = imp.split(".")
            if len(imp_parts) >= 2 and imp_parts[1] in forbidden_targets:
                violations.append(
                    f"D-xx 依赖穿透违规: {layer}/ 禁止 import {imp} "
                    f"(文件: {py_file.relative_to(src_root)})"
                )
    return violations


def check_init_py_exports(src_root: Path) -> list[str]:
    """检查 __init__.py 中是否暴露了公共 API（可选检查）。"""
    warnings: list[str] = []
    for init_file in src_root.rglob("__init__.py"):
        rel = init_file.relative_to(src_root)
        content = init_file.read_text(encoding="utf-8").strip()
        if not content:
            warnings.append(f"WARNING: {rel} 为空，建议导出公共 API 或添加 docstring")
    return warnings


if __name__ == "__main__":
    src = Path("src")
    if not src.exists():
        print("ERROR: src/ 目录不存在，请在项目根目录运行此脚本", file=sys.stderr)
        sys.exit(1)

    violations = check_violations(src)
    warnings = check_init_py_exports(src)

    if warnings:
        for w in warnings:
            print(w, file=sys.stderr)

    if violations:
        print(f"\n发现 {len(violations)} 个依赖违规:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        sys.exit(1)

    print("所有依赖规则检查通过。")
