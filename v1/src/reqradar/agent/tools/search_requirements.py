from reqradar.agent.tools.base import BaseTool, ToolResult


class SearchRequirementsTool(BaseTool):
    name = "search_requirements"
    description = "在历史需求文档中进行语义搜索，查找与指定查询相似的需求"
    required_permissions = ["read:history"]
    parameters_schema = {
        "name": "search_requirements",
        "description": "在历史需求文档中进行语义搜索，查找与指定查询相似的需求",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "语义搜索查询文本",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认5",
                },
            },
            "required": ["query"],
        },
    }

    def __init__(self, vector_store=None):
        self.vector_store = vector_store

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)

        if not self.vector_store:
            return ToolResult(success=False, data="", error="Vector store not available")
        if not query:
            return ToolResult(success=False, data="", error="No query provided")

        try:
            results = self.vector_store.search(query, top_k=top_k)
            if not results:
                return ToolResult(success=True, data="未找到相似需求")

            lines = []
            for r in results:
                title = r.metadata.get("title", r.id)
                similarity = round((1 - r.distance) * 100, 1)
                content_preview = r.content[:150].replace("\n", " ")
                lines.append(f"- [{r.id}] {title} (相似度: {similarity}%)\n  {content_preview}...")

            return ToolResult(success=True, data="\n\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
