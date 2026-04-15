"""核心异常"""


class ReqRadarException(Exception):
    """基础异常类"""

    def __init__(self, message: str, cause: Exception = None):
        super().__init__(message)
        self.message = message
        self.cause = cause


class FatalError(ReqRadarException):
    """致命错误 - 终止流程"""

    pass


class ConfigException(ReqRadarException):
    """配置错误"""

    pass


class ParseException(ReqRadarException):
    """解析错误"""

    pass


class LLMException(ReqRadarException):
    """LLM 调用错误"""

    pass


class VectorStoreException(ReqRadarException):
    """向量存储错误"""

    pass


class GitException(ReqRadarException):
    """Git 操作错误"""

    pass


class IndexException(ReqRadarException):
    """索引错误"""

    pass


class ReportException(ReqRadarException):
    """报告生成错误"""

    pass


class LoaderException(ReqRadarException):
    """加载器错误"""

    pass


class VisionNotConfiguredError(ReqRadarException):
    """视觉模型未配置错误"""

    pass
