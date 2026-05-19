"""文件辅助工具 — 提供临时项目仓库创建、ZIP 打包、路径安全检查。"""

from __future__ import annotations

import zipfile
from pathlib import Path


def create_sample_repo(base: Path, name: str = "sample_repo") -> Path:
    repo = base / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "main.py").write_text('print("hello")\n', encoding="utf-8")
    (repo / "README.md").write_text("# Sample Project\n", encoding="utf-8")
    (repo / "utils.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    return repo


def create_sample_zip(base: Path, name: str = "project.zip") -> Path:
    repo = create_sample_repo(base / "_zip_src")
    zip_path = base / name
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file_path in repo.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(repo))
    return zip_path


def create_sample_requirement_file(base: Path, name: str = "requirement.txt") -> Path:
    req_file = base / name
    req_file.write_text(
        "# 需求文档\n\n用户需要通过邮箱和密码登录系统，"
        "登录后能查看个人信息，支持记住登录状态。"
        "安全要求：密码必须加密存储，连续失败5次锁定账户。\n",
        encoding="utf-8",
    )
    return req_file
