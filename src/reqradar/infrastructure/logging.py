"""日志系统 - structlog + rich"""

import logging
import sys

import structlog


def setup_logging(level: str = "INFO", use_rich: bool = True) -> structlog.BoundLogger:
    """配置日志系统"""

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    if use_rich:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("reqradar")


def log_step(step_name: str, status: str, **kwargs):
    """记录步骤执行状态"""
    logger = structlog.get_logger("reqradar.step")
    logger.info(step_name, status=status, **kwargs)


def log_error(error: Exception, context: dict = None):
    """记录错误"""
    logger = structlog.get_logger("reqradar.error")

    if context is None:
        context = {}

    if hasattr(error, "level") and hasattr(error.level, "value"):
        context["error_level"] = error.level.value

    if isinstance(error, Exception):
        logger.error(str(error), error_type=type(error).__name__, **context)
    else:
        logger.error(str(error), **context)


def log_warning(message: str, **kwargs):
    """记录警告"""
    logger = structlog.get_logger("reqradar.warning")
    logger.warning(message, **kwargs)


def log_info(message: str, **kwargs):
    """记录信息"""
    logger = structlog.get_logger("reqradar.info")
    logger.info(message, **kwargs)


def log_debug(message: str, **kwargs):
    """记录调试信息"""
    logger = structlog.get_logger("reqradar.debug")
    logger.debug(message, **kwargs)
