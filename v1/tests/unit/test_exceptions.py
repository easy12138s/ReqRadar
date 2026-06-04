"""核心异常类单元测试"""

import pytest

from reqradar.core.exceptions import (
    ConfigException,
    FatalError,
    GitException,
    IndexException,
    LLMException,
    LoaderException,
    ParseException,
    ReportException,
    ReqRadarException,
    VectorStoreException,
    VisionNotConfiguredError,
)


class TestReqRadarException:
    def test_basic_exception_creation(self):
        exc = ReqRadarException("test error")
        assert str(exc) == "test error"
        assert exc.message == "test error"

    def test_exception_with_cause(self):
        original = ValueError("original error")
        exc = ReqRadarException("wrapped", cause=original)
        assert exc.cause is original
        assert exc.__cause__ is original

    def test_exception_without_cause(self):
        exc = ReqRadarException("no cause")
        assert exc.cause is None

    def test_exception_inheritance(self):
        assert issubclass(ReqRadarException, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ReqRadarException) as ctx:
            raise ReqRadarException("test")
        assert str(ctx.value) == "test"


class TestFatalError:
    def test_inheritance(self):
        assert issubclass(FatalError, ReqRadarException)

    def test_creation(self):
        exc = FatalError("fatal")
        assert exc.message == "fatal"


class TestConfigException:
    def test_inheritance(self):
        assert issubclass(ConfigException, ReqRadarException)

    def test_creation(self):
        exc = ConfigException("config error")
        assert "config" in exc.message.lower()


class TestParseException:
    def test_inheritance(self):
        assert issubclass(ParseException, ReqRadarException)

    def test_with_cause(self):
        cause = SyntaxError("bad syntax")
        exc = ParseException("parse failed", cause=cause)
        assert exc.cause is cause


class TestLLMException:
    def test_inheritance(self):
        assert issubclass(LLMException, ReqRadarException)

    def test_creation(self):
        exc = LLMException("LLM call failed")
        assert exc.message == "LLM call failed"


class TestVectorStoreException:
    def test_inheritance(self):
        assert issubclass(VectorStoreException, ReqRadarException)


class TestGitException:
    def test_inheritance(self):
        assert issubclass(GitException, ReqRadarException)


class TestIndexException:
    def test_inheritance(self):
        assert issubclass(IndexException, ReqRadarException)


class TestReportException:
    def test_inheritance(self):
        assert issubclass(ReportException, ReqRadarException)


class TestLoaderException:
    def test_inheritance(self):
        assert issubclass(LoaderException, ReqRadarException)


class TestVisionNotConfiguredError:
    def test_inheritance(self):
        assert issubclass(VisionNotConfiguredError, ReqRadarException)

    def test_creation(self):
        exc = VisionNotConfiguredError("vision not set up")
        assert "vision" in exc.message.lower()
