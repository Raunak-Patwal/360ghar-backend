"""
Tests for app.core.logging module.
"""

import io
import json
import logging
from unittest.mock import patch

import pytest

from app.core.logging import ColorFormatter, StructuredFormatter, get_logger, setup_logging


class TestColorFormatter:
    """Tests for ColorFormatter class."""

    def test_format_returns_string(self):
        formatter = ColorFormatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            use_colors=False,
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert isinstance(result, str)
        assert "Hello" in result

    def test_format_with_colors_enabled(self):
        formatter = ColorFormatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            use_colors=True,
        )
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Error occurred" in result
        assert "\033[" in result  # ANSI escape sequences

    def test_format_without_colors(self):
        formatter = ColorFormatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            use_colors=False,
        )
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning msg",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "\033[" not in result  # No ANSI codes

    def test_name_map_cleans_logger_names(self):
        formatter = ColorFormatter(
            fmt="%(name)s",
            use_colors=False,
        )
        record = logging.LogRecord(
            name="uvicorn.error",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        # The name is mapped to "uvicorn" but extras may append
        assert result.startswith("uvicorn")

    def test_extras_appended_as_key_value(self):
        formatter = ColorFormatter(
            fmt="%(message)s",
            use_colors=False,
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Done",
            args=(),
            exc_info=None,
        )
        record.custom_key = "custom_value"  # type: ignore[attr-defined]
        result = formatter.format(record)
        assert "custom_key=custom_value" in result

    @pytest.mark.parametrize(
        "level,expected_color",
        [
            ("DEBUG", "\033[36m"),
            ("INFO", "\033[32m"),
            ("WARNING", "\033[33m"),
            ("ERROR", "\033[31m"),
        ],
    )
    def test_level_color_mapping(self, level, expected_color):
        formatter = ColorFormatter(
            fmt="%(levelname)s",
            use_colors=True,
        )
        record = logging.LogRecord(
            name="test",
            level=getattr(logging, level),
            pathname="test.py",
            lineno=1,
            msg="",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert expected_color in result


class TestStructuredFormatter:
    """Tests for StructuredFormatter class."""

    def test_format_returns_valid_json(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello world",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert data["message"] == "Hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert "timestamp" in data

    def test_format_includes_exception_info(self):
        formatter = StructuredFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys as _sys

            exc_info = _sys.exc_info()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Failed",
            args=(),
            exc_info=exc_info,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "boom" in data["exception"]["message"]
        assert "traceback" in data["exception"]

    def test_format_includes_extras_in_context(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Request done",
            args=(),
            exc_info=None,
        )
        record.method = "GET"  # type: ignore[attr-defined]
        record.path = "/api/v1/properties"  # type: ignore[attr-defined]
        result = formatter.format(record)
        data = json.loads(result)
        assert "context" in data
        assert data["context"]["method"] == "GET"
        assert data["context"]["path"] == "/api/v1/properties"

    def test_format_redacts_sensitive_keys(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Auth event",
            args=(),
            exc_info=None,
        )
        record.api_key = "sk-super-secret"  # type: ignore[attr-defined]
        record.password = "hunter2"  # type: ignore[attr-defined]
        record.token = "abc123"  # type: ignore[attr-defined]
        record.safe_field = "visible"  # type: ignore[attr-defined]
        result = formatter.format(record)
        data = json.loads(result)
        ctx = data["context"]
        assert ctx["api_key"] == "[REDACTED]"
        assert ctx["password"] == "[REDACTED]"
        assert ctx["token"] == "[REDACTED]"
        assert ctx["safe_field"] == "visible"

    def test_format_includes_correlation_id_when_present(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="With correlation",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-123"  # type: ignore[attr-defined]
        result = formatter.format(record)
        data = json.loads(result)
        assert data["correlation_id"] == "req-123"

    def test_format_no_correlation_id_when_absent(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="No correlation",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert "correlation_id" not in data

    def test_format_non_serializable_extra_converted_to_str(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Non-serializable",
            args=(),
            exc_info=None,
        )
        record.obj = object()  # type: ignore[attr-defined]  # Not JSON-serializable
        result = formatter.format(record)
        data = json.loads(result)
        assert isinstance(data["context"]["obj"], str)

    def test_format_no_context_when_no_extras(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Plain",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert "context" not in data

    def test_timestamp_is_valid_isoformat(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Time check",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        # Should be parseable as ISO 8601
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"])


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_instance(self):
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_logger_name_matches(self):
        logger = get_logger("my_module")
        assert logger.name == "my_module"

    def test_same_name_returns_same_logger(self):
        logger1 = get_logger("shared")
        logger2 = get_logger("shared")
        assert logger1 is logger2


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_does_not_raise(self):
        # Should not raise in any environment
        setup_logging()

    def test_debug_mode_uses_debug_level(self):
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.DEBUG = True
            mock_settings.ENVIRONMENT = "development"
            setup_logging()
            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG

    def test_production_mode_uses_info_level(self):
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.DEBUG = False
            mock_settings.ENVIRONMENT = "production"
            setup_logging()
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_production_uses_structured_formatter(self):
        """In production, the root handler should use StructuredFormatter."""
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.DEBUG = False
            mock_settings.ENVIRONMENT = "production"
            setup_logging()
            root_logger = logging.getLogger()
            # Find the console handler and verify its formatter type
            console_handlers = [
                h for h in root_logger.handlers
                if isinstance(h, logging.StreamHandler)
            ]
            assert len(console_handlers) >= 1
            handler = console_handlers[0]
            assert isinstance(handler.formatter, StructuredFormatter)

    def test_production_routes_error_records_to_stderr(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("app.core.logging.settings") as mock_settings, \
             patch("sys.stdout", stdout), \
             patch("sys.stderr", stderr):
            mock_settings.DEBUG = False
            mock_settings.ENVIRONMENT = "production"
            setup_logging()

            logger = logging.getLogger("test.production.streams")
            logger.warning("warning event")
            logger.error("error event")

        stdout_lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
        stderr_lines = [json.loads(line) for line in stderr.getvalue().splitlines()]

        assert [line["message"] for line in stdout_lines] == ["warning event"]
        assert [line["message"] for line in stderr_lines] == ["error event"]
        assert stdout_lines[0]["level"] == "WARNING"
        assert stderr_lines[0]["level"] == "ERROR"

    def test_development_uses_color_formatter_on_tty(self):
        """In development with TTY, the root handler should use ColorFormatter."""
        with patch("app.core.logging.settings") as mock_settings, \
             patch("app.core.logging.sys") as mock_sys:
            mock_settings.DEBUG = True
            mock_settings.ENVIRONMENT = "development"
            # Simulate a TTY
            mock_sys.stderr.isatty.return_value = True
            mock_sys.stderr = type("FakeStderr", (), {"isatty": lambda self: True})()
            setup_logging()
            root_logger = logging.getLogger()
            console_handlers = [
                h for h in root_logger.handlers
                if isinstance(h, logging.StreamHandler)
            ]
            assert len(console_handlers) >= 1
            handler = console_handlers[0]
            assert isinstance(handler.formatter, ColorFormatter)

    def test_production_handler_has_request_id_filter(self):
        """In production, the root handler should have a RequestIDFilter."""
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.DEBUG = False
            mock_settings.ENVIRONMENT = "production"
            setup_logging()
            root_logger = logging.getLogger()
            from app.middleware.security import RequestIDFilter

            for handler in root_logger.handlers:
                filters = [f for f in handler.filters if isinstance(f, RequestIDFilter)]
                assert len(filters) == 1
