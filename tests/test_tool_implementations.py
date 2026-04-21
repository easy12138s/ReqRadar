import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from reqradar.agent.tools.search_code import SearchCodeTool
from reqradar.agent.tools.read_file import ReadFileTool
from reqradar.agent.tools.read_module_summary import ReadModuleSummaryTool
from reqradar.agent.tools.list_modules import ListModulesTool
from reqradar.agent.tools.search_requirements import SearchRequirementsTool
from reqradar.agent.tools.get_dependencies import GetDependenciesTool
from reqradar.agent.tools.get_contributors import GetContributorsTool
from reqradar.agent.tools.get_project_profile import GetProjectProfileTool
from reqradar.agent.tools.get_terminology import GetTerminologyTool
from reqradar.agent.tools.base import ToolResult


def _make_code_graph():
    from reqradar.modules.code_parser import CodeFile, CodeGraph, CodeSymbol

    return CodeGraph(
        files=[
            CodeFile(
                path="src/reqradar/agent/steps.py",
                symbols=[
                    CodeSymbol(name="step_extract", type="function", line=1, end_line=10),
                    CodeSymbol(name="step_analyze", type="function", line=12, end_line=20),
                ],
            ),
            CodeFile(
                path="src/reqradar/modules/memory.py",
                symbols=[
                    CodeSymbol(name="MemoryManager", type="class", line=1, end_line=50),
                ],
            ),
        ]
    )


def _make_memory_data():
    return {
        "project_profile": {
            "name": "ReqRadar",
            "description": "需求分析工具",
            "architecture_style": "分层架构",
            "tech_stack": {"languages": ["Python"], "frameworks": [], "key_dependencies": []},
        },
        "modules": [
            {
                "name": "agent",
                "responsibility": "Agent模块",
                "code_summary": "负责分析流程",
                "key_classes": ["StepRunner"],
            },
            {
                "name": "modules/memory",
                "responsibility": "记忆管理",
                "code_summary": "持久化存储",
                "key_classes": ["MemoryManager"],
            },
        ],
        "terminology": [
            {"term": "需求分析", "definition": "Requirement Analysis", "domain": "产品"},
        ],
    }


@pytest.mark.asyncio
async def test_search_code_tool():
    code_graph = _make_code_graph()
    tool = SearchCodeTool(code_graph=code_graph, repo_path="/tmp/fake")
    result = await tool.execute(keyword="step_extract")
    assert result.success is True
    assert "step_extract" in result.data


@pytest.mark.asyncio
async def test_search_code_no_match():
    code_graph = _make_code_graph()
    tool = SearchCodeTool(code_graph=code_graph, repo_path="/tmp/fake")
    result = await tool.execute(keyword="nonexistent_xyz")
    assert result.success is True
    assert "未找到" in result.data or "no match" in result.data.lower()


@pytest.mark.asyncio
async def test_read_module_summary_tool():
    memory_data = _make_memory_data()
    tool = ReadModuleSummaryTool(memory_data=memory_data)
    result = await tool.execute(module_name="agent")
    assert result.success is True
    assert "Agent模块" in result.data


@pytest.mark.asyncio
async def test_list_modules_tool():
    memory_data = _make_memory_data()
    tool = ListModulesTool(memory_data=memory_data)
    result = await tool.execute()
    assert result.success is True
    assert "agent" in result.data
    assert "modules/memory" in result.data


@pytest.mark.asyncio
async def test_get_project_profile_tool():
    memory_data = _make_memory_data()
    tool = GetProjectProfileTool(memory_data=memory_data)
    result = await tool.execute()
    assert result.success is True
    assert "ReqRadar" in result.data


@pytest.mark.asyncio
async def test_get_terminology_tool():
    memory_data = _make_memory_data()
    tool = GetTerminologyTool(memory_data=memory_data)
    result = await tool.execute()
    assert result.success is True
    assert "需求分析" in result.data


@pytest.mark.asyncio
async def test_get_dependencies_tool():
    code_graph = _make_code_graph()
    tool = GetDependenciesTool(code_graph=code_graph, memory_data=_make_memory_data())
    result = await tool.execute(module="agent")
    assert result.success is True


@pytest.mark.asyncio
async def test_get_contributors_tool_no_git():
    tool = GetContributorsTool(git_analyzer=None)
    result = await tool.execute(file_path="src/reqradar/agent/steps.py")
    assert result.success is False


@pytest.mark.asyncio
async def test_search_requirements_tool_no_store():
    tool = SearchRequirementsTool(vector_store=None)
    result = await tool.execute(query="web interface")
    assert result.success is False
