"""错误定义 - 错误分级处理"""

from enum import Enum


class ErrorLevel(Enum):
    FATAL = "fatal"
    DEGRADED = "degraded"
    IGNORABLE = "ignorable"


class ReqRadarError(Exception):
    level: ErrorLevel = ErrorLevel.DEGRADED

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class FatalError(ReqRadarError):
    level = ErrorLevel.FATAL


class DegradedError(ReqRadarError):
    level = ErrorLevel.DEGRADED


class IgnorableError(ReqRadarError):
    level = ErrorLevel.IGNORABLE


class ConfigError(FatalError):
    pass


class ParseError(DegradedError):
    pass


class LLMError(DegradedError):
    pass


class VectorStoreError(DegradedError):
    pass


class GitError(DegradedError):
    pass
