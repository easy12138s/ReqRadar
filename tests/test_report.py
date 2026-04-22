"""测试报告生成器"""

import tempfile
from pathlib import Path

import pytest

from reqradar.core.context import (
    AnalysisContext,
    ChangeAssessment,
    DecisionSummary,
    DecisionSummaryItem,
    DeepAnalysis,
    EvidenceItem,
    GeneratedContent,
    ImpactDomain,
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

    def test_render_reports_medium_content_confidence_without_substantive_content(self, tmp_path):
        req_path = tmp_path / "test.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(
            summary="Test summary",
            terms=[TermDefinition(term="API", definition="接口")],
        )
        context.deep_analysis = DeepAnalysis(risk_level="medium")

        assert context.content_confidence == "medium"

        renderer = ReportRenderer()
        report = renderer.render(context)
        assert "| 流程完成度 | empty |" in report
        assert "| 内容完整度 | partial |" in report
        assert "| 证据支撑度 | low |" in report

    def test_render_reports_high_content_confidence_with_decision_summary(self, tmp_path):
        req_path = tmp_path / "test.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(summary="Test summary")
        context.deep_analysis = DeepAnalysis(risk_level="medium")
        context.decision_summary = DecisionSummary(
            summary="Roll out behind a feature flag.",
            decisions=[
                DecisionSummaryItem(
                    topic="release_strategy",
                    decision="Use feature flag rollout.",
                    rationale="Allows validation before global release.",
                )
            ],
        )

        assert context.content_confidence == "high"

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "| 内容完整度 | partial |" in report

    def test_render_reports_medium_content_confidence_for_empty_decision_items(self, tmp_path):
        req_path = tmp_path / "test.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(summary="Test summary")
        context.deep_analysis = DeepAnalysis(risk_level="medium")
        context.decision_summary = DecisionSummary(decisions=[DecisionSummaryItem()])

        assert context.content_confidence == "medium"

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "| 内容完整度 | partial |" in report

    def test_render_report_shows_three_quality_dimensions(self, tmp_path):
        req_path = tmp_path / "test.md"
        req_path.write_text("# Test")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(summary="Test summary")
        context.deep_analysis = DeepAnalysis(
            risk_level="medium",
            impact_narrative="Affects API module.",
            evidence_items=[
                EvidenceItem(
                    kind="requirement_text",
                    source="docs/test.md",
                    summary="Requirement explicitly references API updates.",
                    confidence="high",
                )
            ],
            impact_domains=[
                ImpactDomain(
                    domain="api_layer",
                    confidence="high",
                    basis="Requirement scope includes API surface.",
                    inferred=True,
                )
            ],
        )
        context.generated_content = GeneratedContent(
            requirement_understanding="Detailed understanding",
            executive_summary="Proceed incrementally.",
            technical_summary="Touches API and validation layers.",
        )
        context.store_result("extract", StepResult(step="extract", success=True, confidence=0.9))
        context.store_result("analyze", StepResult(step="analyze", success=True, confidence=0.8))

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "| 流程完成度 | full |" in report
        assert "| 内容完整度 | full |" in report
        assert "| 证据支撑度 | high |" in report

    def test_render_dual_layer_sections_with_decision_evidence(self, tmp_path):
        req_path = tmp_path / "web-module.md"
        req_path.write_text("# Web module")

        context = AnalysisContext(requirement_path=req_path)
        context.understanding = RequirementUnderstanding(
            summary="Add a web module for collaborative requirement analysis.",
            priority_suggestion="high",
            priority_reason="跨层能力建设",
        )
        context.deep_analysis = DeepAnalysis(
            risk_level="medium",
            decision_summary=DecisionSummary(
                summary="建议分阶段推进，先交付只读能力。",
                decisions=[
                    DecisionSummaryItem(
                        topic="delivery_strategy",
                        decision="先做只读报告与任务查看",
                        rationale="降低集成复杂度并缩短首个交付周期",
                        implications=["后续再开放记忆编辑", "权限模型可后置细化"],
                    )
                ],
                open_questions=["是否首期纳入 OAuth 登录"],
                follow_ups=["确认 MVP 范围"],
            ),
            evidence_items=[
                EvidenceItem(
                    kind="requirement_text",
                    source="docs/requirements/web-module.md",
                    summary="需求覆盖索引、分析、报告、记忆、权限、API 六个能力域。",
                    confidence="high",
                )
            ],
            impact_domains=[
                ImpactDomain(
                    domain="web_api",
                    confidence="high",
                    basis="需求明确要求 FastAPI + WebSocket 接口层",
                    inferred=True,
                )
            ],
            verification_points=["验证首期范围是否控制在只读能力"],
            implementation_hints=ImplementationHints(
                approach="先后端 API，再只读前端",
                effort_estimate="large",
                dependencies=["认证方案确认", "部署方式确定"],
            ),
            impact_narrative="将新增 Web API、任务状态推送与报告展示边界。",
            risk_narrative="主要风险在于跨层集成和权限边界。",
        )
        context.generated_content = GeneratedContent(
            requirement_understanding="该需求旨在为非 CLI 用户提供统一入口。",
            executive_summary="建议高优先级推进，但采用分阶段实施策略。",
            technical_summary="技术上涉及 API 层、任务编排、报告展示和权限边界。",
            decision_highlights=["首期只读", "通过 feature flag 控制上线"],
            implementation_suggestion="优先收敛 MVP，再逐步扩展交互能力。",
        )

        renderer = ReportRenderer()
        report = renderer.render(context)

        assert "## 决策摘要" in report
        assert "### 1. 结论与证据" in report
        assert "建议分阶段推进，先交付只读能力。" in report
        assert "需求覆盖索引、分析、报告、记忆、权限、API 六个能力域。" in report
        assert "## 技术支撑" in report
        assert "### 4. 影响域与模块" in report
        assert "web_api" in report
        assert "需求明确要求 FastAPI + WebSocket 接口层" in report

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
