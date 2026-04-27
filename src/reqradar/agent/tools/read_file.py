from pathlib import Path

from reqradar.agent.tools.base import BaseTool, ToolResult
from reqradar.agent.tools.security import PathSandbox, SensitiveFileFilter


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取项目中指定文件的源代码内容"
    required_permissions = ["read:code"]
    parameters_schema = {
        "name": "read_file",
        "description": "读取项目中指定文件的源代码内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从1开始），不指定则从文件开头",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号，不指定则到文件末尾（最多2000行）",
                },
            },
            "required": ["path"],
        },
    }

    MAX_LINES = 2000

    def __init__(self, repo_path: str = ""):
        self.repo_path = repo_path
        self._sandbox = PathSandbox(repo_path) if repo_path else None
        self._sensitive_filter = SensitiveFileFilter()

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("path", "")
        start_line = kwargs.get("start_line", 1)
        end_line = kwargs.get("end_line", start_line + self.MAX_LINES - 1)

        if not file_path:
            return ToolResult(success=False, data="", error="No file path provided")

        full_path = Path(self.repo_path) / file_path
        resolved = str(full_path.resolve())

        if self._sandbox and not self._sandbox.is_allowed(resolved):
            return ToolResult(success=False, data="", error=f"Access denied: path escapes project root: {file_path}")

        if self._sensitive_filter.is_sensitive(file_path):
            return ToolResult(success=False, data="", error=f"Access denied: sensitive file: {file_path}")

        if not full_path.exists():
            return ToolResult(success=False, data="", error=f"File not found: {file_path}")

        try:
            content = full_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            total_lines = len(lines)

            start_idx = max(0, start_line - 1)
            end_idx = min(total_lines, end_line)

            selected = lines[start_idx:end_idx]
            truncated = end_idx < total_lines

            result_text = "\n".join(
                f"{start_idx + i + 1}: {line}" for i, line in enumerate(selected)
            )
            if truncated:
                result_text += (
                    f"\n... (truncated, showing lines {start_line}-{end_idx} of {total_lines})"
                )

            return ToolResult(success=True, data=result_text, truncated=truncated)
        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(success=False, data="", error=str(e))
