CONSOLIDATION_SYSTEM_PROMPT = """你是一位资深需求分析师。请将以下多个来源的需求文件整合为一份结构化需求文档。

## 整合规则
1. 多文件重复描述同一需求 → 合并为最完整、最准确的版本
2. 多文件内容有矛盾 → 保留两者并标注 "[不一致]"
3. 图片内容 → 用图片描述参与整合，不单独列出图片本身
4. 优先级：正式规格文档 > 补充说明 > 会议记录 > 图片推测"""


def build_consolidation_user_prompt(
    loaded_contents: list[dict],
    title: str = "",
) -> str:
    parts = ["## 文件清单"]
    for i, item in enumerate(loaded_contents):
        parts.append(f"{i + 1}. {item.get('filename', '?')} ({item.get('type', 'unknown')})")

    parts.append("")
    parts.append("## 各文件内容")
    for i, item in enumerate(loaded_contents):
        content = item.get("content", "")
        if len(content) > 8000:
            content = content[:8000] + "\n...(内容已截断)"
        parts.append(f"### {item.get('filename', f'文件{i + 1}')}")
        parts.append(content)
        parts.append("")

    title_line = f"# {title}" if title else "# 需求文档"
    parts.append("## 输出要求")
    parts.append('整合为 Markdown 格式，包含以下章节（无信息则标注 "[待补充]"）：')
    parts.append(
        f"```markdown\n{title_line}\n## 背景与目标\n业务背景、要解决的问题、期望达成的价值\n"
    )
    parts.append("## 功能需求\nFR-01: ... (功能描述、触发条件、输入/输出、验收标准)\n")
    parts.append("## 非功能需求\nNFR-01: ... (性能、安全、可用性等具体指标)\n")
    parts.append("## 约束与限制\n技术约束、资源限制、依赖条件、截止日期\n")
    parts.append("## 关键术语\n术语名: 定义 (来源文件)\n```")
    parts.append("\n如有需用户确认的内容，用 `[请确认: ...]` 标记。")

    return "\n".join(parts)
