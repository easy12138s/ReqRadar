"""日志系统 - structlog + rich + 文件输出 + 噪音过滤"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

_NOISE_LOGGERS = {
    "fontTools",
    "pdfplumber",
    "PyPDF2",
    "freetype",
    "PIL.PdfImagePlugin",
}

_NOISE_MESSAGES = {
    "Could not get FontBBox from font descriptor",
}


class _NoiseFilter(logging.Filter):
    """过滤第三方库的噪音日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        msg = record.getMessage()

        for prefix in _NOISE_LOGGERS:
            if name.startswith(prefix):
                return False

        return not any(noise in msg for noise in _NOISE_MESSAGES)


def _make_console_processor(colors: bool = True) -> list:
    """构建控制台处理器链"""
    return [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _ContextInjector(),
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(colors=colors),
    ]


def _make_file_processor() -> list:
    """构建文件处理器链（JSON 结构化）"""
    return [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _ContextInjector(),
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(sort_keys=True),
    ]


def setup_logging(
    level: str = "INFO",
    use_rich: bool = True,
    log_file: Path | str | None = None,
) -> structlog.BoundLogger:
    """配置日志系统，支持控制台(可读) + 可选文件(JSON结构化)"""

    log_level = getattr(logging, level.upper(), logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.addFilter(_NoiseFilter())

    handlers: list[logging.Handler] = [console_handler]

    file_handler = None
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.addFilter(_NoiseFilter())
        handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=log_level,
    )

    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _ContextInjector(),
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if use_rich:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.JSONRenderer(sort_keys=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    for noise_logger in _NOISE_LOGGERS:
        logging.getLogger(noise_logger).setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.ERROR)
    logging.getLogger("markdown_it").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)

    return structlog.get_logger("reqradar")


def log_step(step_name: str, status: str, **kwargs):
    logger = structlog.get_logger("reqradar.step")
    logger.info(step_name, status=status, **kwargs)


def log_error(error: Exception, context: dict = None):
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
    logger = structlog.get_logger("reqradar.warning")
    logger.warning(message, **kwargs)


def log_info(message: str, **kwargs):
    logger = structlog.get_logger("reqradar.info")
    logger.info(message, **kwargs)


def log_debug(message: str, **kwargs):
    logger = structlog.get_logger("reqradar.debug")
    logger.debug(message, **kwargs)


class _ContextInjector(structlog.types.Processor):
    """自动注入 task_id / phase 等上下文字段到每条日志"""

    def __init__(self):
        self._context: dict = {}

    def set_context(self, **kwargs):
        self._context.update(kwargs)

    def clear_context(self):
        self._context.clear()

    def __call__(self, logger, method_name, event_dict):
        event_dict.update(self._context)
        return event_dict


_global_context_injector = _ContextInjector()


def set_log_context(**kwargs):
    """设置当前日志上下文（线程内全局生效，用于分析任务关联）"""
    _global_context_injector.set_context(**kwargs)


def clear_log_context():
    """清除日志上下文"""
    _global_context_injector.clear_context()
