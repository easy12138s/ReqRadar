"""测试报告生成器"""

import tempfile
from pathlib import Path

import pytest

from reqradar.core.context import (
    AnalysisContext,
    ChangeAssessment,
    DeepAnalysis,
    GeneratedContent,
    ImplementationHints,
    RequirementUnderstanding,
    RetrievedContext,
    RiskItem,
    StepResult,
    StructuredConstraint,
    TermDefinition,
)
from reqradar.core.report import ReportRenderer, _risk_level_to_badge


class TestRiskLevelToBadge:
    def test_critical(self):
        assert _risk_level_to_badge("critical") == "🔴 极高"

    def test_high(self):
        assert _risk_level_to_badge("high") == "🟠 高"

    def test_medium(self):
        assert _risk_level_to_badge("medium") == "🟡 中"

    def test_low(self):
        assert _risk_level_to_badge("low") == "🟢 低"

    def test_unknown(self):
        assert _risk_level_to_badge("unknown") == "⚪ 未知"

    def test_unknown_level(self):
        assert _risk_level_to_badge("invalid") == "⚪ 未知"


class TestReportRenderer:
    def test_render_basic_report(self, tmp_path):
        req_path = tmp_path / "test-requirement.md"
        req_path.write_text("# Test Requirement\n\nTest content")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(
            summary="Test summary",
            keywords=["test", "requirement"],
            terms=[TermDefinition(term="API", definition="Application Programming Interface", domain="技术")],
            constraints=["性能约束"],
            structured_constraints=[StructuredConstraint(description="响应时间<200ms", constraint_type="performance", source="requirement_document")],
            priority_suggestion="high",
            priority_reason="业务紧急",
        )

        context.deep_analysis = DeepAnalysis(
            impact_modules=[{"path": "src/api.py", "symbols": ["get_data", "post_data"]}],
            contributors=[{"name": "张三", "role": "后端负责人", "file": "src/api.py", "reason": "主要贡献者"}],
            risk_level="medium",
            risk_details=["复杂度较高"],
            risks=[RiskItem(description="性能风险", severity="medium", scope="API模块", mitigation="缓存优化")],
            change_assessment=[ChangeAssessment(module="src/api.py", change_type="modify", impact_level="medium", reason="新增接口")],
            verification_points=["验证性能指标", "检查错误处理"],
            implementation_hints=ImplementationHints(approach="增量开发", effort_estimate="medium", dependencies=["缓存模块"]),
        )

        context.generated_content = GeneratedContent(
            requirement_understanding="这是一个测试需求，需要新增API接口...",
            impact_narrative="影响API模块，需要修改数据获取逻辑...",
            risk_narrative="主要风险是性能问题，建议使用缓存...",
            implementation_suggestion="建议分阶段实施...",
        )

        context.retrieved_context = RetrievedContext(
            similar_requirements=[],
            code_files=[],
        )

        context.store_result("extract", StepResult(step="extract", success=True, confidence=0.9))
        context.store_result("analyze", StepResult(step="analyze", success=True, confidence=0.85))

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "# 需求分析报告：test-requirement" in report
        assert "报告概况" in report
        assert "🟡 中" in report
        assert "API" in report
        assert "Application Programming Interface" in report
        assert "验证性能指标" in report
        assert "缓存优化" in report
        assert "张三" in report
        assert "这是一个测试需求" in report

    def test_render_with_memory_data(self, tmp_path):
        req_path = tmp_path / "test-requirement.md"
        req_path.write_text("# Test")

        context = AnalysisContext(
            requirement_path=req_path,
            memory_data={
                "project_profile": {
                    "name": "TestProject",
                    "description": "A test project",
                    "tech_stack": "Python, FastAPI",
                    "architecture_style": "微服务架构",
                },
                "modules": [{"name": "api", "responsibility": "API层"}],
            },
        )
        context.understanding = RequirementUnderstanding(summary="Test")
        context.deep_analysis = DeepAnalysis(risk_level="low")

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "TestProject" in report
        assert "Python, FastAPI" in report

    def test_render_empty_context(self, tmp_path):
        req_path = tmp_path / "test-requirement.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "# 需求分析报告" in report
        assert "暂无" in report or "未知" in report

    def test_render_with_warnings(self, tmp_path):
        req_path = tmp_path / "test-requirement.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)
        context.store_result("extract", StepResult(step="extract", success=True))
        context.store_result("analyze", StepResult(step="analyze", success=False, error="LLM 调用失败"))

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "步骤 analyze 执行失败" in report

    def test_save_report(self, tmp_path):
        req_path = tmp_path / "test-requirement.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)

        renderer = ReportRenderer()
        report = renderer.render(context)

        output_path = tmp_path / "output" / "report.md"
        renderer.save(report, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "# 需求分析报告" in content

    def test_content_confidence_high(self, tmp_path):
        req_path = tmp_path / "test.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(
            summary="Test summary",
            terms=[TermDefinition(term="API", definition="接口")],
        )
        context.deep_analysis = DeepAnalysis(risk_level="medium")

        assert context.content_confidence == "high"

        renderer = ReportRenderer()
        report = renderer.render(context)
        assert "high" in report

    def test_content_confidence_medium(self, tmp_path):
        req_path = tmp_path / "test.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(summary="Test summary")
        context.deep_analysis = DeepAnalysis(risk_level="unknown")

        assert context.content_confidence == "medium"

    def test_content_confidence_low(self, tmp_path):
        req_path = tmp_path / "test.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)

        assert context.content_confidence == "low"
