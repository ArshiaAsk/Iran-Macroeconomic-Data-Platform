"""
Unit tests for logging configuration.
"""

import json
import logging

import pytest

from src.utils.logging import (
    JSONFormatter,
    get_logger,
    log_with_context,
    setup_logging,
)


def make_record(**kwargs: object) -> logging.LogRecord:
    """Build a LogRecord with sensible defaults for formatter tests."""
    defaults: dict[str, object] = {
        "name": "test.logger",
        "level": logging.INFO,
        "pathname": "/app/module.py",
        "lineno": 42,
        "msg": "hello %s",
        "args": ("world",),
        "exc_info": None,
    }
    defaults.update(kwargs)
    return logging.LogRecord(**defaults)  # type: ignore[arg-type]


def test_json_formatter_emits_valid_json() -> None:
    """Formatter output parses as JSON and carries the core fields."""
    payload = json.loads(JSONFormatter().format(make_record()))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "hello world"  # args interpolated
    assert payload["line"] == 42
    assert payload["module"] == "module"
    assert "timestamp" in payload


def test_json_formatter_timestamp_is_timezone_aware() -> None:
    """Timestamps are UTC and carry an offset, not naive local time."""
    from datetime import datetime

    payload = json.loads(JSONFormatter().format(make_record()))
    parsed = datetime.fromisoformat(payload["timestamp"])

    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_json_formatter_includes_exception() -> None:
    """Exception info is rendered into the payload."""
    try:
        msg = "boom"
        raise ValueError(msg)
    except ValueError:
        import sys

        record = make_record(exc_info=sys.exc_info())

    payload = json.loads(JSONFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_json_formatter_merges_extra_fields() -> None:
    """Fields attached via extra_fields are merged into the payload."""
    record = make_record()
    record.extra_fields = {"indicator_id": "TEST_GDP", "records": 12}  # type: ignore[attr-defined]

    payload = json.loads(JSONFormatter().format(record))

    assert payload["indicator_id"] == "TEST_GDP"
    assert payload["records"] == 12


def test_setup_logging_json_format() -> None:
    """setup_logging installs exactly one handler with the JSON formatter."""
    logger = setup_logging(level="DEBUG", log_format="json", logger_name="test.json")

    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, JSONFormatter)


def test_setup_logging_text_format() -> None:
    """The text format uses a plain Formatter rather than the JSON one."""
    logger = setup_logging(level="WARNING", log_format="text", logger_name="test.text")

    assert logger.level == logging.WARNING
    formatter = logger.handlers[0].formatter
    assert formatter is not None
    assert not isinstance(formatter, JSONFormatter)


def test_setup_logging_is_idempotent() -> None:
    """Calling setup_logging twice must not stack duplicate handlers."""
    setup_logging(logger_name="test.idempotent")
    logger = setup_logging(logger_name="test.idempotent")

    assert len(logger.handlers) == 1


def test_get_logger_returns_named_logger() -> None:
    """get_logger returns the same instance for the same name."""
    assert get_logger("a.b.c") is logging.getLogger("a.b.c")


def test_log_with_context_attaches_fields(capsys: pytest.CaptureFixture[str]) -> None:
    """log_with_context writes JSON containing the supplied context."""
    setup_logging(level="INFO", log_format="json", logger_name="test.context")
    logger = get_logger("test.context")
    logger.propagate = False

    log_with_context(logger, "info", "collection finished", source="world_bank", records=120)

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["message"] == "collection finished"
    assert payload["source"] == "world_bank"
    assert payload["records"] == 120


def test_log_with_context_respects_level(capsys: pytest.CaptureFixture[str]) -> None:
    """A debug call is suppressed when the logger is set to INFO."""
    setup_logging(level="INFO", log_format="json", logger_name="test.level")
    logger = get_logger("test.level")
    logger.propagate = False

    log_with_context(logger, "debug", "should not appear")

    assert capsys.readouterr().out == ""
