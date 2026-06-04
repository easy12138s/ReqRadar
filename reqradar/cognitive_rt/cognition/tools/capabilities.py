"""工具能力声明 — 为每个已注册工具定义 ToolCapability。"""

from __future__ import annotations

from reqradar.cognitive_rt.runtime.tool_runtime import (
    RetryPolicy,
    ToolCapability,
    ToolCategory,
)


def get_default_capabilities() -> dict[str, ToolCapability]:
    """获取所有工具的默认能力声明。

    Returns:
        {tool_id: ToolCapability} 映射
    """
    return {
        "search_code": ToolCapability(
            tool_id="search_code",
            name="search_code",
            description="在项目中搜索代码片段和函数定义",
            category=ToolCategory.READ_ONLY,
            timeout=15.0,
            retry_policy=RetryPolicy(max_retries=2, initial_backoff=0.5),
            cache_ttl=120,
        ),
        "read_file": ToolCapability(
            tool_id="read_file",
            name="read_file",
            description="读取指定文件的内容",
            category=ToolCategory.READ_ONLY,
            timeout=10.0,
            retry_policy=RetryPolicy(max_retries=1),
            cache_ttl=60,
        ),
        "get_dependencies": ToolCapability(
            tool_id="get_dependencies",
            name="get_dependencies",
            description="获取模块的依赖关系",
            category=ToolCategory.READ_ONLY,
            timeout=15.0,
            retry_policy=RetryPolicy(max_retries=2),
            cache_ttl=300,
        ),
        "list_modules": ToolCapability(
            tool_id="list_modules",
            name="list_modules",
            description="列出项目中的所有模块",
            category=ToolCategory.READ_ONLY,
            timeout=10.0,
            retry_policy=RetryPolicy(max_retries=1),
            cache_ttl=300,
        ),
        "get_terminology": ToolCapability(
            tool_id="get_terminology",
            name="get_terminology",
            description="获取项目术语表",
            category=ToolCategory.READ_ONLY,
            timeout=10.0,
            retry_policy=RetryPolicy(max_retries=1),
            cache_ttl=600,
        ),
        "get_contributors": ToolCapability(
            tool_id="get_contributors",
            name="get_contributors",
            description="获取模块的 Git 贡献者信息",
            category=ToolCategory.READ_ONLY,
            timeout=10.0,
            retry_policy=RetryPolicy(max_retries=1),
            cache_ttl=300,
        ),
        "get_project_profile": ToolCapability(
            tool_id="get_project_profile",
            name="get_project_profile",
            description="获取项目画像（技术栈、模块结构、关键指标）",
            category=ToolCategory.READ_ONLY,
            timeout=15.0,
            retry_policy=RetryPolicy(max_retries=2),
            cache_ttl=600,
        ),
        "read_module_summary": ToolCapability(
            tool_id="read_module_summary",
            name="read_module_summary",
            description="读取模块摘要信息",
            category=ToolCategory.READ_ONLY,
            timeout=10.0,
            retry_policy=RetryPolicy(max_retries=1),
            cache_ttl=120,
        ),
        "search_git_history": ToolCapability(
            tool_id="search_git_history",
            name="search_git_history",
            description="搜索 Git 提交历史",
            category=ToolCategory.EXTERNAL,
            timeout=20.0,
            retry_policy=RetryPolicy(max_retries=3, initial_backoff=2.0),
            cache_ttl=60,
        ),
        "search_requirements": ToolCapability(
            tool_id="search_requirements",
            name="search_requirements",
            description="搜索需求文档",
            category=ToolCategory.READ_ONLY,
            timeout=15.0,
            retry_policy=RetryPolicy(max_retries=2),
            cache_ttl=120,
        ),
    }
