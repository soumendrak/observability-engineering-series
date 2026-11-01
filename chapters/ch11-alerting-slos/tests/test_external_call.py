import asyncio

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

import order_service

EXPORTER = InMemorySpanExporter()
PROVIDER = TracerProvider()
PROVIDER.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(PROVIDER)


async def stripe_timeout(amount: float) -> dict[str, str]:
    raise ConnectionError("stripe API timeout")


async def stripe_ok(amount: float) -> dict[str, str]:
    return {"charge_id": "ch_1", "status": "succeeded"}


def stripe_span() -> ReadableSpan:
    [span] = [
        s for s in EXPORTER.get_finished_spans() if s.name == "external.stripe.charge"
    ]
    return span


def test_failed_external_call_records_one_exception_event() -> None:
    EXPORTER.clear()
    with pytest.raises(ConnectionError):
        asyncio.run(
            order_service.call_external_api("stripe", "charge", stripe_timeout, 9.99)
        )
    span = stripe_span()
    assert [event.name for event in span.events] == ["exception"]
    [event] = span.events
    assert event.attributes is not None
    assert event.attributes["exception.type"] == "ConnectionError"
    assert span.status.status_code is StatusCode.ERROR


def test_successful_external_call_records_no_events() -> None:
    EXPORTER.clear()
    result = asyncio.run(
        order_service.call_external_api("stripe", "charge", stripe_ok, 9.99)
    )
    assert result == {"charge_id": "ch_1", "status": "succeeded"}
    span = stripe_span()
    assert span.events == ()
    assert span.status.status_code is StatusCode.UNSET
    assert span.attributes is not None
    assert span.attributes["external.status"] == "success"
