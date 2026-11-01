import json
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
