import io
import json
import sys
from datetime import UTC, datetime
from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider

from logging_setup import setup_logging


def read_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_message_with_quotes_and_newlines_is_valid_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log = setup_logging("test-service")
    log.info('payment "declined"\nretrying')
    [entry] = read_lines(capsys)
    assert entry["message"] == 'payment "declined"\nretrying'
    assert entry["service"] == "test-service"
    assert entry["level"] == "INFO"


def test_outside_a_span_ids_are_zero(capsys: pytest.CaptureFixture[str]) -> None:
    log = setup_logging("test-service")
    log.info("no span")
    [entry] = read_lines(capsys)
    assert entry["trace_id"] == "0" * 32
    assert entry["span_id"] == "0" * 16
    assert entry["span_name"] == ""


def test_inside_a_span_ids_match_the_span(capsys: pytest.CaptureFixture[str]) -> None:
    log = setup_logging("test-service")
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span('checkout "fast"') as span:
        log.info("in span")
        ctx = span.get_span_context()
    [entry] = read_lines(capsys)
    assert entry["trace_id"] == format(ctx.trace_id, "032x")
    assert entry["span_id"] == format(ctx.span_id, "016x")
    assert entry["span_name"] == 'checkout "fast"'


def test_keyword_fields_are_included(capsys: pytest.CaptureFixture[str]) -> None:
    log = setup_logging("test-service")
    log.error("Order insert failed", error_type="TimeoutError", qty=2)
    [entry] = read_lines(capsys)
    assert entry["error_type"] == "TimeoutError"
    assert entry["qty"] == 2
    assert entry["level"] == "ERROR"


def test_below_info_is_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    log = setup_logging("test-service")
    log.debug("hidden")
    assert capsys.readouterr().out == ""


class FlushRecorder(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flushed_text: list[str] = []

    def flush(self) -> None:
        self.flushed_text.append(self.getvalue())


def test_each_entry_is_flushed_when_written(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = FlushRecorder()
    monkeypatch.setattr(sys, "stdout", stream)
    log = setup_logging("test-service")
    log.info("first")
    assert json.loads(stream.flushed_text[-1])["message"] == "first"


def test_extras_cannot_overwrite_reserved_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log = setup_logging("test-service")
    log.info(
        "real message",
        timestamp="fake-time",
        level="DEBUG",
        service="other-service",
        message="fake message",
        exception="fake exception",
        order_id="ord-1",
    )
    [entry] = read_lines(capsys)
    assert list(entry)[:4] == ["timestamp", "level", "service", "message"]
    assert entry["timestamp"] != "fake-time"
    assert entry["level"] == "INFO"
    assert entry["service"] == "test-service"
    assert entry["message"] == "real message"
    assert "exception" not in entry
    assert entry["order_id"] == "ord-1"


def test_exception_is_serialised_with_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log = setup_logging("test-service")
    try:
        raise ValueError("card declined")
    except ValueError:
        log.exception("payment failed", exception="fake exception")
    [entry] = read_lines(capsys)
    assert entry["level"] == "ERROR"
    assert entry["exception"]["type"] == "ValueError"
    assert entry["exception"]["value"] == "card declined"
    assert entry["exception"]["traceback"].startswith(
        "Traceback (most recent call last):"
    )
    assert 'raise ValueError("card declined")' in entry["exception"]["traceback"]
    assert entry["exception"]["traceback"].endswith("ValueError: card declined\n")


def test_non_json_extras_are_written_with_str(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log = setup_logging("test-service")
    placed_at = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    log.info("order placed", placed_at=placed_at, amount=object())
    [entry] = read_lines(capsys)
    assert entry["placed_at"] == "2026-11-01 09:30:00+00:00"
    assert entry["amount"].startswith("<object object at 0x")
