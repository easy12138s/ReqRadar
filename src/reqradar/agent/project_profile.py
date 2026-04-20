"""Agent 层 - 项目画像构建"""

import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

from reqradar.agent.schemas import (
    GENERATE_BATCH_MODULE_SUMMARIES_SCHEMA,
    PROJECT_PROFILE_SCHEMA,
)
from reqradar.agent.prompts import (
    GENERATE_BATCH_MODULE_SUMMARIES_PROMPT,
    PROJECT_PROFILE_PROMPT,
)
from reqradar.agent.llm_utils import _call_llm_structured

logger = logging.getLogger("reqradar.agent")


async def step_build_project_profile(
    code_graph,
    llm_client,
    memory_manager,
    repo_path: str = ".",
) -> dict:
    """构建项目画像并存入记忆"""
    if not code_graph or not code_graph.files:
        logger.warning("No code files to build project profile")
        return {}

    try:
        file_stats = _build_file_stats(code_graph)
        directory_structure = _build_directory_structure(code_graph)
        key_files = _build_key_files(code_graph)
        dependencies_content = _extract_dependencies(repo_path)

        messages = [
            {
                "role": "user",
                "content": PROJECT_PROFILE_PROMPT.format(
                    file_stats=file_stats,
                    directory_structure=directory_structure,
                    key_files=key_files,
                    dependencies_content=dependencies_content,
                ),
            },
        ]

        result = await _call_llm_structured(
            llm_client, messages, PROJECT_PROFILE_SCHEMA, max_tokens=2048
        )

        if result:
            profile = {
                "name": Path(repo_path).name,
                "description": result.get("description", ""),
                "architecture_style": result.get("architecture_style", ""),
                "tech_stack": result.get("tech_stack", {}),
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "source": "llm_inferred",
            }

            memory_manager.update_project_profile(profile)
            logger.info("Project profile updated: %s", profile.get("description", ""))

            modules_with_code = []
            module_info_list = []

            for module in result.get("modules", []):
                if isinstance(module, dict) and module.get("name"):
                    module_name = module.get("name", "")
                    responsibility = module.get("responsibility", "")
                    module_files = _find_module_files(module_name, code_graph)

                    if module_files:
                        code_content = _read_module_code(module_files, max_chars=5000)
                        if code_content:
                            modules_with_code.append({
                                "module_name": module_name,
                                "responsibility": responsibility,
                                "code_content": code_content,
                            })
                        else:
                            module_info_list.append((module_name, responsibility))
                    else:
                        module_info_list.append((module_name, responsibility))

            batch_summaries = await _generate_batch_module_summaries(modules_with_code, llm_client)

            for module_name, responsibility in module_info_list:
                memory_manager.add_module(
                    name=module_name,
                    responsibility=responsibility,
                    path=_infer_module_path(module_name, code_graph),
                    code_summary=f"模块 {module_name}：{responsibility}",
                )

            for item in modules_with_code:
                module_name = item["module_name"]
                responsibility = item["responsibility"]
                code_summary = batch_summaries.get(module_name, f"模块 {module_name}：{responsibility}")
                memory_manager.add_module(
                    name=module_name,
                    responsibility=responsibility,
                    path=_infer_module_path(module_name, code_graph),
                    code_summary=code_summary,
                )

            memory_manager.save()
            logger.info("Project profile saved to memory")

            return {
                "project_profile": profile,
                "modules": result.get("modules", []),
            }

    except Exception as e:
        logger.warning("Failed to build project profile: %s", e)

    return {}


def _build_file_stats(code_graph) -> str:
    """构建文件统计信息"""
    total_files = len(code_graph.files)
    total_symbols = sum(len(f.symbols) for f in code_graph.files)

    extensions = Counter(Path(f.path).suffix for f in code_graph.files if Path(f.path).suffix)
    top_extensions = extensions.most_common(5)

    lines = [
        f"- 总文件数: {total_files}",
        f"- 总符号数: {total_symbols}",
        f"- 文件类型分布: {', '.join(f'{ext}({count})' for ext, count in top_extensions)}",
    ]
    return "\n".join(lines)


def _build_directory_structure(code_graph) -> str:
    """构建目录结构"""
    dirs = set()
    for f in code_graph.files:
        parts = Path(f.path).parts
        for i in range(1, min(len(parts), 4)):
            dirs.add("/".join(parts[:i]))

    sorted_dirs = sorted(dirs)[:20]
    return "\n".join(f"- {d}" for d in sorted_dirs)


def _build_key_files(code_graph) -> str:
    """构建核心文件列表"""
    files_with_symbols = [
        (f.path, len(f.symbols), [s.name for s in f.symbols[:5]])
        for f in code_graph.files
        if f.symbols
    ]
    files_with_symbols.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for path, count, symbols in files_with_symbols[:10]:
        lines.append(f"- {path} ({count} symbols: {', '.join(symbols)})")

    return "\n".join(lines)


def _extract_dependencies(repo_path: str) -> str:
    """提取依赖文件内容"""
    repo = Path(repo_path)
    dep_files = [
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
    ]

    contents = []
    for dep_file in dep_files:
        path = repo / dep_file
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")[:1000]
                contents.append(f"=== {dep_file} ===\n{content}\n")
            except Exception:
                pass

    if not contents:
        contents.append("未找到依赖文件")

    return "\n".join(contents)


def _infer_module_path(module_name: str, code_graph) -> str:
    """推断模块路径"""
    for f in code_graph.files:
        if module_name.lower() in f.path.lower():
            return str(Path(f.path).parent)
    return ""


def _find_module_files(module_name: str, code_graph) -> list:
    """查找模块对应的代码文件（最多5个）"""
    matching_files = []
    for f in code_graph.files:
        if module_name.lower() in f.path.lower():
            matching_files.append(f)
    return matching_files[:5]


def _read_module_code(module_files: list, max_chars: int = 5000) -> str:
    """读取模块代码内容"""
    all_content = []
    total_chars = 0
    for code_file in module_files:
        try:
            path = Path(code_file.path)
            if path.exists():
                content = path.read_text(encoding="utf-8")
                key_content = _extract_key_code(content, code_file.symbols)
                all_content.append(f"# {code_file.path}\n{key_content}")
                total_chars += len(key_content)
                if total_chars >= max_chars:
                    break
        except Exception:
            continue
    return "\n\n".join(all_content)[:max_chars]


def _extract_key_code(content: str, symbols: list) -> str:
    """提取代码的关键部分（函数和类定义），基于缩进判断边界"""
    lines = content.split("\n")
    key_lines = []

    for sym in symbols[:10]:
        sym_name = sym.get("name", "") if isinstance(sym, dict) else str(sym)

        for i, line in enumerate(lines):
            if f"def {sym_name}" in line or f"class {sym_name}" in line:
                base_indent = len(line) - len(line.lstrip())
                end = i + 1

                while end < len(lines):
                    next_line = lines[end]
                    if not next_line.strip():
                        end += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= base_indent and next_line.strip():
                        break
                    end += 1
                if end - i > 50:
                    break

                key_lines.extend(lines[i:end])
                break

    return "\n".join(key_lines)


async def _generate_batch_module_summaries(
    modules_with_code: list[dict],
    llm_client,
) -> dict[str, str]:
    """批量生成模块摘要，减少 LLM 调用次数"""
    if not modules_with_code:
        return {}

    modules_info = []
    for item in modules_with_code:
        info = f"""### {item['module_name']}
职责: {item['responsibility']}
代码片段:
```
{item['code_content'][:2000]}
```
"""
        modules_info.append(info)

    try:
        messages = [{
            "role": "user",
            "content": GENERATE_BATCH_MODULE_SUMMARIES_PROMPT.format(
                modules_info="\n---\n".join(modules_info)
            ),
        }]

        result = await _call_llm_structured(
            llm_client,
            messages,
            GENERATE_BATCH_MODULE_SUMMARIES_SCHEMA,
            max_tokens=4096,
        )

        summaries = {}
        for item in result.get("summaries", []):
            module_name = item.get("module_name", "")
            if module_name:
                summaries[module_name] = item.get("summary", "")

        logger.info("Generated batch summaries for %d modules", len(summaries))
        return summaries

    except Exception as e:
        logger.warning("Failed to generate batch summaries: %s", e)
        return {}
