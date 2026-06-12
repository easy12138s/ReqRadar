"""异常层次结构 — V1 + V2 合并的唯一异常定义源。

所有异常支持 cause 参数，保留原始异常的 __cause__ 链。
"""


class ReqRadarException(Exception):
    """基础异常类，所有 ReqRadar 异常的根类。"""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause


class FatalError(ReqRadarException):
    """致命错误 — 终止整个流程。"""


class ConfigException(ReqRadarException):
    """配置错误 — 配置文件缺失、格式错误或值无效。"""


class LLMException(ReqRadarException):
    """LLM 调用异常 — API 超时、限流、响应格式错误。"""


class ParseException(ReqRadarException):
    """解析异常 — 文档格式不支持、内容损坏。"""


class IngestionException(ReqRadarException):
    """数据摄取异常 — 文档/代码/Git 解析、向量化失败。"""

    def __init__(
        self,
        message: str,
        detail: dict | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.detail = detail or {}


class VectorStoreException(ReqRadarException):
    """向量存储异常 — 连接失败或查询错误。"""


class GitException(ReqRadarException):
    """Git 操作异常 — 仓库不存在、权限不足。"""


class IndexException(ReqRadarException):
    """索引异常 — 索引构建失败、数据不一致。"""


class ReportException(ReqRadarException):
    """报告生成异常 — 模板渲染失败、输出格式错误。"""


class LoaderException(ReqRadarException):
    """文档加载异常 — 文件不存在、编码错误。"""


class VisionNotConfiguredError(ReqRadarException):
    """视觉模型未配置 — 需要图像分析但未配置视觉 LLM。"""


class ToolExecutionError(ReqRadarException):
    """工具执行异常 — V2 ToolRuntime 统一工具错误。"""


class CheckpointException(ReqRadarException):
    """检查点异常 — 创建、恢复或归档失败。"""


class SessionException(ReqRadarException):
    """会话异常 — 生命周期转换违规、状态不一致。"""


class ContextBudgetExceededException(ReqRadarException):
    """上下文预算超限 — Context Pipeline 组装后的上下文超出 Token 预算。"""

    def __init__(
        self,
        message: str,
        budget: int = 0,
        actual: int = 0,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.budget = budget
        self.actual = actual
