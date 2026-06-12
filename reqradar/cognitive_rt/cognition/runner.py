from __future__ import annotations

"""共享 ReAct 分析执行逻辑 - CLI 和 Web 共用"""

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from reqradar.cognitive_rt.runtime.checkpoint import CheckpointManager
    from reqradar.cognitive_rt.runtime.checkpoint_storage import CheckpointStorage
    from reqradar.cognitive_rt.runtime.ws import ConnectionManager

from reqradar.cognitive_rt.cognition.analysis_agent import AgentState, AnalysisAgent
from reqradar.cognitive_rt.cognition.llm_utils import (
    _call_llm_structured,
    _complete_with_tools,
    _parse_json_response,
)
from reqradar.cognitive_rt.cognition.prompts.analysis_phase import (
    build_dynamic_system_prompt,
    build_step_user_prompt,
    build_termination_prompt,
)
from reqradar.cognitive_rt.cognition.prompts.report_phase import build_report_generation_prompt
from reqradar.cognitive_rt.cognition.schemas import REPORT_DATA_SCHEMA, STEP_OUTPUT_SCHEMA
from reqradar.cognitive_rt.cognition.tool_call_tracker import ToolCallTracker
from reqradar.cognitive_rt.cognition.tools import ToolRegistry

logger = logging.getLogger("reqradar.cognitive_rt.cognition.runner")

_RESULT_TRUNCATE_LENGTH = 4000

_EVIDENCE_TYPE_MAP = {
    "analysis": "inference",
    "term": "project_context",
}


def create_pipeline(
    strategy_name: str = "RiskAnalysisStrategy",
    service_url: str | None = None,
    internal_api_key: str | None = None,
) -> object | None:
    """创建配置好的 Context Pipeline。

    Args:
        strategy_name: 策略名称，支持 "RiskAnalysisStrategy" 或 "ArchitectureUnderstandingStrategy"
        service_url: index-service 的 URL，默认从环境变量获取
        internal_api_key: 内部 API Key，默认从环境变量获取

    Returns:
        配置好的 ContextPipeline 实例，如果创建失败返回 None
    """
    try:
        from reqradar.cognitive_rt.cognition.context_pipeline import ContextPipeline
        from reqradar.cognitive_rt.cognition.context_sources import (
            ArchitectureDocSource,
            CodeGraphSource,
            GitHistorySource,
            ProjectMemorySource,
            UserMemorySource,
            VectorResultSource,
        )
        from reqradar.cognitive_rt.cognition.context_strategies import (
            ArchitectureUnderstandingStrategy,
            RiskAnalysisStrategy,
        )

        # 获取服务配置
        _service_url = service_url or os.environ.get(
            "REQRADAR_INDEX_SERVICE_URL", "http://index-service:8003"
        )
        _api_key = internal_api_key or os.environ.get("REQRADAR_INTERNAL_API_KEY", "")

        # 创建并配置 Sources
        sources = []
        for source_cls in [
            CodeGraphSource,
            VectorResultSource,
            GitHistorySource,
            ProjectMemorySource,
            UserMemorySource,
            ArchitectureDocSource,
        ]:
            source = source_cls()
            source.configure(service_url=_service_url, internal_api_key=_api_key)
            sources.append(source)

        # 选择策略
        if strategy_name == "ArchitectureUnderstandingStrategy":
            strategy = ArchitectureUnderstandingStrategy()
        else:
            strategy = RiskAnalysisStrategy()

        pipeline = ContextPipeline(sources=sources, strategy=strategy)
        logger.info("Context Pipeline 创建成功: strategy=%s, service_url=%s", strategy_name, _service_url)
        return pipeline
    except Exception as e:
        logger.warning("Context Pipeline 创建失败, 将使用 f-string 模式: %s", e)
        return None


_EVIDENCE_TYPE_MAP = {
    "analysis": "inference",
    "term": "project_context",
    "code": "code_match",
    "history": "inference",
}


class AnalysisSessionLogger:
    """分析会话日志包装器，自动注入 task_id/phase/step 标签"""

    def __init__(self, task_id: int | None = None):
        self.task_id = task_id
        self._round_start: float | None = None
        self._round_tools: list[str] = []

    def enter(self):
        from reqradar.infrastructure.logging import set_log_context

        set_log_context(session_id=str(self.task_id or ""))
        self.info("analysis_started")

    def exit(self):
        from reqradar.infrastructure.logging import clear_log_context

        clear_log_context()

    def phase(self, name: str):
        self.info("phase_changed", phase=name)

    def round_start(self, step_count: int):
        self._round_start = time.monotonic()
        self._round_tools.clear()
        self.debug("react_round_start", step=step_count)

    def tool_call(self, seq: int, name: str, args: dict, result_len: int):
        self._round_tools.append(name)
        self.debug(
            "tool_call",
            seq=seq,
            tool=name,
            args=args,
            result_chars=result_len,
        )

    def round_end(self, step_count: int, llm_tokens: int):
        elapsed = 0.0
        if self._round_start is not None:
            elapsed = time.monotonic() - self._round_start
        self.info(
            "react_round_complete",
            step=step_count,
            tools_called=len(self._round_tools),
            tools=self._round_tools,
            tokens=llm_tokens,
            duration_ms=round(elapsed * 1000),
        )
        self._round_start = None

    def report_generated(self, duration_ms: float):
        self.info("report_generated", duration_ms=duration_ms)

    def analysis_done(self, total_steps: int, status: str):
        self.info(
            "analysis_completed",
            total_steps=total_steps,
            status=status,
        )

    # ---- 低级接口（直接透传到 stdlib logger）----

    def info(self, event: str, **kwargs):
        if kwargs:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            logger.info("%s %s", event, extras)
        else:
            logger.info(event)

    def debug(self, event: str, **kwargs):
        if kwargs:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            logger.debug("%s %s", event, extras)
        else:
            logger.debug(event)

    def warning(self, event: str, **kwargs):
        if kwargs:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            logger.warning("%s %s", event, extras)
        else:
            logger.warning(event)

    def error(self, event: str, **kwargs):
        if kwargs:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            logger.error("%s %s", event, extras)
        else:
            logger.error(event)


def _truncate_result(text: str, max_len: int = _RESULT_TRUNCATE_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...(截断)"


def _safe_truncate_history(
    history: list[dict],
    llm_client,
    max_tokens: int = 6000,
    keep_pairs: bool = True,
) -> list[dict]:
    """按 token 数截断历史，保持 assistant(tool_calls) + tool 结果原子性。

    如果截断后会留下孤儿 tool 消息（即其对应的 assistant 消息已被截断），
    则跳过该组，确保 API 不会看到没有匹配 assistant 的 tool 消息。
    """
    if not history:
        return history

    total_tokens = llm_client.estimate_tokens(history)
    if total_tokens <= max_tokens:
        return history

    # 从旧到新遍历，找到截断点
    truncated = []
    current_tokens = 0

    for msg in reversed(history):
        msg_tokens = llm_client.estimate_tokens([msg])

        # 检查是否是 tool 消息且其对应的 assistant 消息已被截断
        if keep_pairs and msg.get("role") == "tool":
            tool_call_id = msg.get("tool_call_id")
            has_parent = any(
                m.get("role") == "assistant"
                and any(tc.get("id") == tool_call_id for tc in (m.get("tool_calls") or []))
                for m in truncated
            )
            if not has_parent:
                continue  # 跳过孤儿 tool 消息

        if current_tokens + msg_tokens > max_tokens:
            break

        truncated.insert(0, msg)
        current_tokens += msg_tokens

    return truncated


def update_agent_from_step_result(agent: AnalysisAgent, step_data: dict) -> None:
    for dim, new_status in step_data.get("dimension_status", {}).items():
        if new_status == "sufficient":
            agent.dimension_tracker.mark_sufficient(dim)

    for finding in step_data.get("key_findings", []):
        agent.record_evidence(
            type="analysis",
            source=f"step:{agent.step_count}",
            content=finding.get("finding", ""),
            confidence=finding.get("confidence", "medium"),
            dimensions=[finding.get("dimension", "")],
        )

    agent._pending_actions = step_data.get("next_actions", [])
    agent._llm_declared_terminal = step_data.get("final_step", False)


def update_agent_from_tool_result(agent: AnalysisAgent, data: dict) -> None:
    if data.get("terms"):
        for t in data.get("terms", []):
            if isinstance(t, dict) and t.get("term"):
                agent.record_evidence(
                    type="term",
                    source=f"llm_extract:{t['term']}",
                    content=f"{t['term']}: {t.get('definition', '')}",
                    confidence="medium",
                    dimensions=["understanding"],
                )

    if data.get("impact_modules"):
        for m in data.get("impact_modules", []):
            if isinstance(m, dict):
                agent.record_evidence(
                    type="code",
                    source=m.get("path", "unknown"),
                    content=m.get("relevance_reason", "Unknown relevance"),
                    confidence=m.get("relevance", "low"),
                    dimensions=["impact", "change"],
                )
                agent.dimension_tracker.mark_in_progress("impact")

    if data.get("risks"):
        for r in data.get("risks", []):
            if isinstance(r, dict):
                confidence_map = {"high": "high", "medium": "medium", "low": "low"}
                agent.record_evidence(
                    type="history",
                    source=f"risk:{r.get('description', '')[:50]}",
                    content=r.get("description", ""),
                    confidence=confidence_map.get(r.get("severity", ""), "medium"),
                    dimensions=["risk"],
                )
                agent.dimension_tracker.mark_in_progress("risk")


async def generate_report(
    agent: AnalysisAgent,
    llm_client,
    system_prompt: str,
    section_descriptions=None,
) -> dict:
    termination_prompt = build_termination_prompt()
    evidence_text = agent.evidence_collector.get_all_evidence_text()

    report_prompt = build_report_generation_prompt(
        requirement_text=agent.requirement_text,
        evidence_text=evidence_text,
        dimension_status=agent.dimension_tracker.status_summary(),
        template_sections=section_descriptions,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": report_prompt},
        {"role": "assistant", "content": termination_prompt},
    ]

    try:
        result = await _call_llm_structured(llm_client, messages, REPORT_DATA_SCHEMA)
        if result:
            result.setdefault("requirement_title", agent.requirement_text[:100])
            result.setdefault("warnings", [])
            return result
    except Exception as e:
        logger.warning("Report generation failed, using fallback: %s", e)

    return build_fallback_report_data(agent)


def build_fallback_report_data(agent: AnalysisAgent) -> dict:
    return {
        "requirement_title": agent.requirement_text[:100],
        "requirement_understanding": f"需求理解: {agent.requirement_text[:200]}",
        "executive_summary": "分析完成，但有部分信息不完整。",
        "technical_summary": "",
        "impact_narrative": "",
        "risk_narrative": "",
        "risk_level": "unknown",
        "decision_highlights": [],
        "impact_domains": [],
        "impact_modules": [],
        "change_assessment": [],
        "risks": [],
        "decision_summary": {
            "summary": "",
            "decisions": [],
            "open_questions": [],
            "follow_ups": [],
        },
        "evidence_items": [
            {
                "kind": _EVIDENCE_TYPE_MAP.get(ev.type, "inference"),
                "source": ev.source,
                "summary": ev.content,
                "confidence": ev.confidence,
            }
            for ev in agent.evidence_collector.evidences
        ],
        "verification_points": [],
        "implementation_suggestion": "",
        "priority": "medium",
        "priority_reason": "",
        "terms": [],
        "keywords": [],
        "constraints": [],
        "structured_constraints": [],
        "contributors": [],
        "warnings": ["Agent analysis completed with partial data due to insufficient evidence."],
    }


async def _execute_tool_calls(
    tool_calls: list[dict],
    tool_registry: ToolRegistry,
    tracker: ToolCallTracker,
    agent: AnalysisAgent | None = None,
    session: AnalysisSessionLogger | None = None,
    ws_manager=None,
    task_id: int | None = None,
) -> list[dict]:
    tool_results = []
    for tc in tool_calls:
        tc_name = tc.get("name", "")
        tc_id = tc.get("id", "")
        tc_args_str = tc.get("arguments", "{}")

        try:
            tc_args = json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
        except json.JSONDecodeError:
            tc_args = {}

        if ws_manager and task_id:
            await ws_manager.broadcast(
                task_id,
                {
                    "type": "agent_action",
                    "task_id": task_id,
                    "message": f"调用工具: {tc_name}",
                    "tool": tc_name,
                    "args": tc_args,
                },
            )

        if tc_name not in tool_registry._tools:
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": f"Error: Unknown tool '{tc_name}'",
                }
            )
            continue

        if tracker.is_duplicate(tc_name, tc_args):
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": "(此调用已去重，跳过重复请求)",
                }
            )
            continue

        if tracker.is_tool_over_limit(tc_name):
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": f"Error: Tool '{tc_name}' has reached its call limit ({tracker.max_calls_per_tool})",
                }
            )
            continue

        tracker.track_call(tc_name, tc_args)

        try:
            result = await tool_registry.execute_with_permissions(tc_name, **tc_args)
            result_text = result.data if result.success else f"Error: {result.error}"
        except Exception as e:
            result_text = f"Error executing {tc_name}: {e}"

        result_text = _truncate_result(result_text)
        tool_results.append(
            {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result_text,
            }
        )
        try:
            tool_data = json.loads(result_text)
            if isinstance(tool_data, dict) and agent is not None:
                update_agent_from_tool_result(agent, tool_data)
        except (json.JSONDecodeError, TypeError):
            pass

        if session is not None:
            session.tool_call(tracker.call_count, tc_name, tc_args, len(result_text))
        else:
            logger.debug(
                "Tool #%d: %s(%s) -> %d chars",
                tracker.call_count,
                tc_name,
                json.dumps(tc_args, ensure_ascii=False)[:60],
                len(result_text),
            )

    return tool_results


async def run_react_analysis(
    agent: AnalysisAgent,
    llm_client,
    tool_registry: ToolRegistry,
    config=None,
    section_descriptions=None,
    project_memory=None,
    requirement_text: str | None = None,
    ws_manager: ConnectionManager | None = None,  # type: ignore[name-defined]
    task_id: int | None = None,
    progress_callback=None,
    event_publisher=None,
    checkpoint_interval: int = 3,
    # ── V2 集成参数 ──
    session_id: str | None = None,
    checkpoint_mgr: CheckpointManager | None = None,
    checkpoint_storage: CheckpointStorage | None = None,
    on_complete: Callable[[str], Awaitable[None]] | None = None,
    on_fail: Callable[[str, str], Awaitable[None]] | None = None,
    on_checkpoint: Callable[[str, object, int], Awaitable[None]] | None = None,
    # ── Context Pipeline ──
    pipeline: object | None = None,
) -> dict:
    session = AnalysisSessionLogger(task_id=task_id)
    session.enter()
    effective_session_id = session_id or f"agent-{id(agent)}"
    report_start = time.monotonic()

    try:
        if requirement_text:
            agent.requirement_text = requirement_text

        tool_schemas = tool_registry.get_schemas(tool_registry.list_names())
        tracker = ToolCallTracker()
        conversation_history: list[dict] = []

        # 项目画像自动触发：首次推理时如果项目画像为空，自动构建
        if not agent.project_memory_text and project_memory is not None:
            try:
                from reqradar.cognitive_rt.cognition.project_profile import (
                    step_build_project_profile,
                )

                logger.info("Building project profile (首次推理自动触发)")
                profile_result = await step_build_project_profile(
                    code_graph=None,  # 会在后续步骤中通过工具获取
                    llm_client=llm_client,
                    project_memory=project_memory,
                )
                if profile_result:
                    agent.project_memory_text = str(profile_result.get("description", ""))
                    logger.info("项目画像构建完成")
            except Exception as e:
                logger.warning("项目画像自动构建失败, 继续推理: %s", e)

        agent.state = AgentState.ANALYZING
        session.phase("analyze")

        while True:
            agent.step_count += 1
            session.round_start(agent.step_count)

            if event_publisher is not None:
                from reqradar.kernel.enums import EventLevel, EventType

                event_publisher.publish(
                    session_id=effective_session_id,
                    event_type=EventType.STEP_STARTED,
                    event_level=EventLevel.REASONING,
                    producer="analysis_runner",
                    payload={"step": agent.step_count},
                )

            if ws_manager and task_id:
                await ws_manager.broadcast(
                    task_id,
                    {
                        "type": "dimension_progress",
                        "task_id": task_id,
                        "step": agent.step_count,
                        "dimensions": agent.dimension_tracker.status_summary(),
                    },
                )

            ds = agent.dimension_tracker.status_summary()

            # 尝试使用 Context Pipeline 获取增强上下文
            # 缓存机制：每 3 步重新执行一次 Pipeline，避免重复计算
            pipeline_context = ""
            if pipeline is not None:
                # 检查是否需要重新执行 Pipeline
                should_execute_pipeline = (
                    not hasattr(agent, '_pipeline_cache')
                    or agent._pipeline_cache is None
                    or agent.step_count % 3 == 1  # 每 3 步执行一次
                    or agent.step_count == 1  # 第一步必须执行
                )

                if should_execute_pipeline:
                    try:
                        pipeline_result = await pipeline.execute(
                            session_id=effective_session_id,
                            project_id=str(agent.project_id),
                            query=agent.requirement_text[:500],
                            context_budget=128000,
                        )
                        # 缓存结果
                        agent._pipeline_cache = {
                            'context': pipeline_result.context,
                            'strategy_name': pipeline_result.strategy_name,
                            'token_count': pipeline_result.token_count,
                            'step': agent.step_count,
                        }
                        pipeline_context = pipeline_result.context
                        logger.info(
                            "Pipeline 完成: strategy=%s, collected≥1, scored≥1, selected≥1, tokens=%d",
                            pipeline_result.strategy_name,
                            pipeline_result.token_count,
                        )
                    except Exception as e:
                        logger.warning("Context Pipeline 执行失败, 回退到 f-string: %s", e)
                        # 使用缓存（如果有）
                        if hasattr(agent, '_pipeline_cache') and agent._pipeline_cache:
                            pipeline_context = agent._pipeline_cache['context']
                else:
                    # 使用缓存
                    pipeline_context = agent._pipeline_cache['context']
                    logger.debug("Pipeline 使用缓存 (step=%d, cached_at=%d)",
                               agent.step_count, agent._pipeline_cache['step'])

            system_prompt = build_dynamic_system_prompt(
                dimension_status=ds,
                project_memory=agent.project_memory_text,
                user_memory=agent.user_memory_text,
                historical_context=agent.historical_context,
                template_sections=section_descriptions,
                pending_actions=agent._pending_actions,
                pipeline_context=pipeline_context,
            )

            user_prompt = build_step_user_prompt(
                requirement_text=agent.requirement_text,
                step_count=agent.step_count,
                max_steps=agent.max_steps,
                weak_dimensions=agent.get_weak_dimensions_text(),
                evidence_count=len(agent.evidence_collector.evidences),
                depth=agent.depth,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            if conversation_history:
                recent = _safe_truncate_history(conversation_history, llm_client, max_tokens=6000)
                messages = messages[:1] + recent + messages[1:]

            if not tool_schemas:
                result = await _call_llm_structured(llm_client, messages, STEP_OUTPUT_SCHEMA)
                if result:
                    update_agent_from_step_result(agent, result)
                if agent.should_terminate():
                    break
                await asyncio.sleep(0)
                continue

            supported = await llm_client.supports_tool_calling()
            if not supported:
                result = await _call_llm_structured(llm_client, messages, STEP_OUTPUT_SCHEMA)
                if result:
                    update_agent_from_step_result(agent, result)
                if agent.should_terminate():
                    break
                await asyncio.sleep(0)
                continue

            response = await _complete_with_tools(llm_client, messages, tool_schemas)

            if response is None:
                agent._consecutive_failures += 1
                if agent.should_terminate():
                    break
                await asyncio.sleep(0)
                continue

            agent._consecutive_failures = 0

            tokens_used = response.get("tokens", 0)

            if response.get("tool_calls"):
                assistant_msg = response.get("assistant_message", {})
                if assistant_msg:
                    conversation_history.append(assistant_msg)

                tool_results = await _execute_tool_calls(
                    response["tool_calls"],
                    tool_registry,
                    tracker,
                    agent,
                    session,
                    ws_manager,
                    task_id,
                )
                conversation_history.extend(tool_results)
                agent._consecutive_empty_steps = 0
                session.round_end(agent.step_count, tokens_used)
                if progress_callback is not None:
                    await progress_callback(
                        agent.step_count, agent.dimension_tracker.status_summary()
                    )
                if agent._cancelled or agent.step_count >= agent.max_steps:
                    break
                await asyncio.sleep(0)
                continue

            if response.get("content"):
                try:
                    parsed = _parse_json_response(response["content"])
                    update_agent_from_step_result(agent, parsed)

                    if len(parsed.get("key_findings", [])) == 0:
                        agent._consecutive_empty_steps += 1
                    else:
                        agent._consecutive_empty_steps = 0
                except (json.JSONDecodeError, ValueError):
                    agent._consecutive_empty_steps += 1
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "content": response["content"],
                        }
                    )

            session.round_end(agent.step_count, tokens_used)
            if progress_callback is not None:
                await progress_callback(agent.step_count, agent.dimension_tracker.status_summary())

            if event_publisher is not None:
                from reqradar.kernel.enums import EventLevel, EventType

                event_publisher.publish(
                    session_id=effective_session_id,
                    event_type=EventType.STEP_COMPLETED,
                    event_level=EventLevel.REASONING,
                    producer="analysis_runner",
                    payload={"step": agent.step_count, "tokens": tokens_used},
                )

                if checkpoint_interval > 0 and agent.step_count % checkpoint_interval == 0:
                    try:
                        from reqradar.cognitive_rt.runtime.checkpoint import (
                            CheckpointManager,
                            StateSummary,
                        )
                        from reqradar.kernel.enums import CheckpointType

                        mgr = checkpoint_mgr or CheckpointManager()
                        summary = StateSummary(
                            current_step=agent.step_count,
                            total_steps=agent.max_steps,
                            evidence_count=len(agent.evidence_collector.evidences),
                            dimension_status=agent.dimension_tracker.status_summary(),
                        )
                        record = mgr.create_checkpoint(
                            session_id=effective_session_id,
                            checkpoint_type=CheckpointType.STEP_COMPLETE,
                            state_summary=summary,
                        )
                        # create_checkpoint 内部已通过 mgr._storage.save() 持久化
                        # 此处不再重复调用 checkpoint_storage.save()
                        if on_checkpoint is not None:
                            await on_checkpoint(
                                effective_session_id,
                                CheckpointType.STEP_COMPLETE,
                                record.version,
                            )
                    except Exception as cp_err:
                        logger.warning("Checkpoint 创建失败: %s", cp_err)

            if agent.should_terminate():
                break

            await asyncio.sleep(0)

        agent.state = AgentState.GENERATING
        session.phase("report")

        ds = agent.dimension_tracker.status_summary()
        final_system_prompt = build_dynamic_system_prompt(
            dimension_status=ds,
            project_memory=agent.project_memory_text,
            user_memory=agent.user_memory_text,
            historical_context=agent.historical_context,
            template_sections=section_descriptions,
        )
        report_data = await generate_report(
            agent, llm_client, final_system_prompt, section_descriptions
        )

        report_elapsed = round((time.monotonic() - report_start) * 1000)
        session.report_generated(report_elapsed)

        agent.final_report_data = report_data

        enable_memory_evolution = (
            config and hasattr(config, "memory_evolution") and config.memory_evolution.enabled
        )
        if enable_memory_evolution and project_memory is not None:
            try:
                from reqradar.cognitive_rt.cognition.memory_evolution import (
                    evolve_memory_after_analysis,
                )

                await evolve_memory_after_analysis(agent, project_memory, llm_client)
            except Exception as e:
                logger.warning("Memory evolution failed: %s", e)

        # L3 知识沉淀
        try:
            from reqradar.cognitive_rt.cognition.knowledge_precipitator import KnowledgePrecipitator

            precipitator = KnowledgePrecipitator()
            agent_snapshot = agent.get_context_snapshot()
            await precipitator.precipitate(
                project_id=str(agent.project_id),
                session_id=effective_session_id,
                agent_data=agent_snapshot,
            )
        except Exception as e:
            logger.warning("L3 知识沉淀失败: %s", e)

        agent.state = AgentState.COMPLETED
        session.analysis_done(agent.step_count, "completed")
        if on_complete is not None:
            await on_complete(effective_session_id)
        return report_data

    except Exception as e:
        session.error("analysis_failed", error=str(e))
        if on_fail is not None:
            await on_fail(effective_session_id, str(e))
        raise
    finally:
        session.exit()
