"""固定流程调度器 - 5步工作流"""

import logging
from typing import Callable

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from reqradar.core.context import AnalysisContext, StepResult
from reqradar.core.exceptions import FatalError

logger = logging.getLogger("reqradar.scheduler")


class Scheduler:
    """固定6步工作流调度器"""

    STEPS = [
        ("read", "读取需求文档"),
        ("extract", "提取关键术语"),
        ("map_keywords", "映射关键词到代码术语"),
        ("retrieve", "检索相似需求与代码"),
        ("analyze", "深度分析"),
        ("generate", "生成报告"),
    ]

    def __init__(
        self,
        read_handler: Callable,
        extract_handler: Callable,
        map_keywords_handler: Callable = None,
        retrieve_handler: Callable = None,
        analyze_handler: Callable = None,
        generate_handler: Callable = None,
    ):
        self.handlers = {
            "read": read_handler,
            "extract": extract_handler,
            "retrieve": retrieve_handler,
            "analyze": analyze_handler,
            "generate": generate_handler,
        }
        if map_keywords_handler:
            self.handlers["map_keywords"] = map_keywords_handler
        self._hooks_before: dict[str, list[Callable]] = {step: [] for step in self.handlers}
        self._hooks_after: dict[str, list[Callable]] = {step: [] for step in self.handlers}

    def register_before_hook(self, step: str, hook: Callable):
        """注册步骤执行前的钩子"""
        if step in self._hooks_before:
            self._hooks_before[step].append(hook)

    def register_after_hook(self, step: str, hook: Callable):
        """注册步骤执行后的钩子"""
        if step in self._hooks_after:
            self._hooks_after[step].append(hook)

    async def run(self, context: AnalysisContext) -> AnalysisContext:
        """执行完整工作流"""

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,
        ) as progress:
            main_task = progress.add_task("[cyan]需求分析中...", total=100)

            for step_name, step_desc in self.STEPS:
                progress.update(main_task, description=f"[cyan]{step_desc}...")

                logger.info("Step %s started", step_name)

                for hook in self._hooks_before.get(step_name, []):
                    await hook(context)

                handler = self.handlers.get(step_name)
                if not handler:
                    logger.warning("No handler for step: %s", step_name)
                    continue

                try:
                    result = await handler(context)

                    step_result = StepResult(
                        step=step_name,
                        success=True,
                        confidence=1.0,
                        data=result,
                    )
                    context.store_result(step_name, step_result)

                    logger.info("Step %s completed", step_name)

                except FatalError as e:
                    logger.error("Step %s fatal error: %s", step_name, e)
                    context.store_result(
                        step_name,
                        StepResult(
                            step=step_name,
                            success=False,
                            confidence=0.0,
                            error=str(e),
                        ),
                    )
                    break

                except Exception as e:
                    logger.warning("Step %s failed (degraded): %s", step_name, e)
                    context.store_result(
                        step_name,
                        StepResult(
                            step=step_name,
                            success=False,
                            confidence=0.0,
                            error=str(e),
                        ),
                    )

                for hook in self._hooks_after.get(step_name, []):
                    await hook(context)

                progress.update(main_task, advance=20)

        context.finalize()
        return context
