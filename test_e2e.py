#!/usr/bin/env python3
"""端到端测试脚本 - 使用 MiniMax API"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from reqradar.core.context import AnalysisContext
from reqradar.core.report import ReportRenderer
from reqradar.modules.code_parser import CodeFile, CodeGraph, CodeSymbol
from reqradar.modules.llm_client import create_llm_client
from reqradar.modules.memory import MemoryManager


async def run_e2e_test():
    """运行端到端测试"""

    # 设置 MiniMax API
    api_key = "sk-api-fNt5hVLGuZuJknY2UYk96G-1celhCTbAcLSprVcHKZBt2sEKBdQTD8zdCu7XBEkbzdUQO_2lJk9HJ_LWzt1knk9MNs8tXbdRgO7IAO9P3b1rI4am_ftHPJ4"
    os.environ["OPENAI_API_KEY"] = api_key

    print("=" * 60)
    print("ReqRadar 端到端测试 (MiniMax API)")
    print("=" * 60)

    # 1. 加载记忆
    memory_path = Path(".reqradar/memory")
    memory_manager = MemoryManager(storage_path=str(memory_path))
    memory_data = memory_manager.load()
    print(f"\n[1/6] 记忆加载完成")
    print(f"  - 术语数量: {len(memory_data.get('terminology', []))}")
    print(f"  - 模块数量: {len(memory_data.get('modules', []))}")

    # 2. 创建 LLM 客户端
    llm_client = create_llm_client(
        "openai",
        api_key=api_key,
        model="MiniMax-Text-01",
        base_url="https://api.minimax.chat/v1",
        timeout=120,
    )
    print(f"\n[2/6] LLM 客户端创建完成 (MiniMax-Text-01)")

    # 3. 加载代码图谱
    code_graph_path = Path(".reqradar/index/code_graph.json")
    if code_graph_path.exists():
        with open(code_graph_path, encoding="utf-8") as f:
            graph_data = json.load(f)
        code_graph = CodeGraph(
            files=[
                CodeFile(
                    path=f["path"],
                    symbols=[CodeSymbol(**s) for s in f.get("symbols", [])],
                    imports=f.get("imports", []),
                )
                for f in graph_data.get("files", [])
            ]
        )
        print(f"\n[3/6] 代码图谱加载完成")
        print(f"  - 文件数量: {len(code_graph.files)}")
    else:
        code_graph = None
        print(f"\n[3/6] 代码图谱不存在")

    # 4. 创建分析上下文
    requirement_path = Path("docs/requirements/ide-integration.md")
    context = AnalysisContext(
        requirement_path=requirement_path,
        memory_data=memory_data,
    )
    print(f"\n[4/6] 分析上下文创建完成")
    print(f"  - 需求文件: {requirement_path}")

    # 5. 执行分析步骤
    from reqradar.agent.steps import step_extract, step_analyze, step_generate, step_read

    # 读取需求
    print(f"\n[5/6] 执行分析步骤...")
    print(f"  - step_read...")
    await step_read(context)
    print(f"    ✓ 完成")

    # 提取信息
    print(f"  - step_extract...")
    await step_extract(context, llm_client)
    print(f"    ✓ 完成")
    if context.understanding:
        print(f"    - 摘要长度: {len(context.understanding.summary)}")
        print(f"    - 术语数量: {len(context.understanding.terms)}")

    # 分析
    print(f"  - step_analyze...")
    await step_analyze(context, code_graph, None, llm_client)
    print(f"    ✓ 完成")
    if context.deep_analysis:
        print(f"    - 风险等级: {context.deep_analysis.risk_level}")
        print(f"    - 风险数量: {len(context.deep_analysis.risks)}")
        print(f"    - 变更评估: {len(context.deep_analysis.change_assessment)}")

    # 生成
    print(f"  - step_generate...")
    await step_generate(context, llm_client)
    print(f"    ✓ 完成")
    if context.generated_content:
        print(f"    - 需求理解长度: {len(context.generated_content.requirement_understanding)}")

    # 6. 生成报告
    print(f"\n[6/6] 生成报告...")
    renderer = ReportRenderer()
    report = renderer.render(context)

    output_path = Path("reports/e2e_test_report.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    renderer.save(report, output_path)

    print(f"\n{'=' * 60}")
    print(f"测试完成!")
    print(f"{'=' * 60}")
    print(f"\n报告已保存到: {output_path}")
    print(f"\n报告内容预览:")
    print("-" * 60)
    lines = report.split("\n")
    for line in lines[:80]:
        print(line)
    if len(lines) > 80:
        print(f"\n... (共 {len(lines)} 行)")

    # 打印关键指标
    print(f"\n{'=' * 60}")
    print(f"关键指标:")
    print(f"  - 数据完整度: {context.completeness}")
    print(f"  - 分析置信度: {context.overall_confidence * 100:.1f}%")
    print(f"  - 内容可信度: {context.content_confidence}")
    print(f"  - 风险等级: {context.deep_analysis.risk_level if context.deep_analysis else 'unknown'}")
    print(f"{'=' * 60}")

    return context


if __name__ == "__main__":
    asyncio.run(run_e2e_test())
