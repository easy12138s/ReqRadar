from reqradar.agent.tools.base import BaseTool, ToolResult


class GetContributorsTool(BaseTool):
    name = "get_contributors"
    description = "查询指定文件的主要贡献者（代码作者和维护者）"
    required_permissions = ["read:git"]
    parameters_schema = {
        "name": "get_contributors",
        "description": "查询指定文件的主要贡献者（代码作者和维护者）",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）",
                },
            },
            "required": ["file_path"],
        },
    }

    def __init__(self, git_analyzer=None):
        self.git_analyzer = git_analyzer

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")

        if not self.git_analyzer:
            return ToolResult(success=False, data="", error="Git analyzer not available")
        if not file_path:
            return ToolResult(success=False, data="", error="No file path provided")

        try:
            results = self.git_analyzer.get_file_contributors([file_path])
            if not results or not results[0].primary_contributor:
                return ToolResult(success=True, data=f"未找到 {file_path} 的贡献者信息")

            lines = []
            fc = results[0]
            pc = fc.primary_contributor
            lines.append(f"文件: {file_path}")
            lines.append(f"主要贡献者: {pc.name} ({pc.email})")
            lines.append(
                f"  提交数: {pc.commit_count}, 行变更: +{pc.lines_added}/-{pc.lines_deleted}"
            )
            for rc in fc.recent_contributors[:3]:
                if rc.email != pc.email:
                    lines.append(
                        f"近期贡献者: {rc.name} ({rc.email}), 提交数: {rc.commit_count}"
                    )

            return ToolResult(success=True, data="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
