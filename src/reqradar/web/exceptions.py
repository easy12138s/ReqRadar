from fastapi import Request
from fastapi.responses import JSONResponse

from reqradar.core.exceptions import (
    ConfigException,
    FatalError,
    GitException,
    IndexException,
    LLMException,
    LoaderException,
    ParseException,
    ReqRadarException,
    ReportException,
    VectorStoreException,
    VisionNotConfiguredError,
)

EXCEPTION_STATUS_MAP = {
    FatalError: 500,
    ConfigException: 500,
    ParseException: 400,
    LLMException: 502,
    VectorStoreException: 500,
    GitException: 500,
    IndexException: 500,
    ReportException: 500,
    LoaderException: 400,
    VisionNotConfiguredError: 501,
    ReqRadarException: 500,
}


async def reqradar_exception_handler(request: Request, exc: ReqRadarException):
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message},
    )