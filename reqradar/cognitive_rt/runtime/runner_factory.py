"""Runner 工厂函数 — 统一创建 Agent/LLMClient/ToolRegistry。"""

from __future__ import annotations

import logging
import os

from reqradar.cognitive_rt.cognition.analysis_agent import AnalysisAgent
from reqradar.cognitive_rt.cognition.llm_client import LiteLLMClient
from reqradar.cognitive_rt.cognition.tools.registry import ToolRegistry

logger = logging.getLogger("reqradar.cognitive_rt.runtime.runner_factory")


def create_runner_components(
    session_id: str,
    requirement_text: str,
    project_id: str = "default",
    user_id: str = "system",
    config: dict | None = None,
) -> tuple[AnalysisAgent, LiteLLMClient, ToolRegistry]:
    """创建 Runner 运行所需的三个核心组件。

    Returns:
        (agent, llm_client, tool_registry) 三元组
    """
    config = config or {}
    depth = config.get("depth", "standard")

    # 创建 LLMClient
    llm_client = LiteLLMClient()

    # 创建 AnalysisAgent
    agent = AnalysisAgent(
        requirement_text=requirement_text,
        project_id=project_id,
        user_id=user_id,
        depth=depth,
    )

    # 创建 ToolRegistry 并注册所有已导出的内置工具
    registry = ToolRegistry()
    _register_builtin_tools(registry)

    logger.info(
        "Runner 组件创建完成: session_id=%s, tools=%d, depth=%s",
        session_id,
        len(registry.list_names()),
        depth,
    )

    return agent, llm_client, registry


def _register_builtin_tools(registry: ToolRegistry) -> None:
    """注册所有已导出的内置工具。"""
    from reqradar.cognitive_rt.cognition.tools import (
        GetContributorsTool,
        GetDependenciesTool,
        GetProjectProfileTool,
        GetTerminologyTool,
        ListModulesTool,
        ReadFileTool,
        ReadModuleSummaryTool,
        SearchCodeTool,
        SearchRequirementsTool,
    )

    tools = [
        SearchCodeTool(),
        ReadFileTool(),
        ReadModuleSummaryTool(),
        ListModulesTool(),
        SearchRequirementsTool(),
        GetDependenciesTool(),
        GetContributorsTool(),
        GetProjectProfileTool(),
        GetTerminologyTool(),
    ]

    for tool in tools:
        registry.register(tool)


def create_context_sources(
    index_service_url: str = "",
    internal_api_key: str = "",
) -> list:
    """创建 5 个 ContextSource 实例，注入 index-service 连接配置。

    Returns:
        5 个 ContextSource 实例列表
    """
    from reqradar.cognitive_rt.cognition.context_sources import (
        CodeGraphSource,
        GitHistorySource,
        ProjectMemorySource,
        UserMemorySource,
        VectorResultSource,
    )

    url = index_service_url or os.environ.get("INDEX_SERVICE_URL", "http://localhost:8003")
    key = internal_api_key or os.environ.get("INTERNAL_API_KEY", "")

    sources = [
        ProjectMemorySource(),
        UserMemorySource(),
        CodeGraphSource(),
        VectorResultSource(),
        GitHistorySource(),
    ]

    for src in sources:
        src._service_url = url
        src._internal_api_key = key

    logger.info("Context Sources 创建完成: count=%d, service_url=%s", len(sources), url)
    return sources
