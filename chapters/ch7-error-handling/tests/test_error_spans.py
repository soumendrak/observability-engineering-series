import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

import order_service

EXPORTER = InMemorySpanExporter()
PROVIDER = TracerProvider()
PROVIDER.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(PROVIDER)


@pytest.fixture(autouse=True)
def fresh_spans() -> Iterator[None]:
    EXPORTER.clear()
    yield
    EXPORTER.clear()


def span_named(name: str) -> ReadableSpan:
    [span] = [s for s in EXPORTER.get_finished_spans() if s.name == name]
    return span


async def instant(*args: Any, **kwargs: Any) -> None:
    return None


async def db_down(order: dict[str, Any]) -> dict[str, str]:
    raise order_service.DatabaseError("connection refused: pg-primary:5432")


async def db_ok(order: dict[str, Any]) -> dict[str, str]:
    return {"id": "ord-1"}


async def db_read_timeout(product_id: str) -> dict[str, Any]:
    raise order_service.DatabaseError(f"read timeout fetching product {product_id}")


async def stripe_timeout(amount: float) -> dict[str, str]:
    raise ConnectionError("stripe API timeout")


def assert_failed_with(span: ReadableSpan, error_type: str) -> None:
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes is not None
    assert span.attributes["error.type"] == error_type


def test_failed_db_insert_sets_error_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", instant)
    monkeypatch.setattr(order_service, "simulate_db_insert", db_down)
    asyncio.run(order_service.create_order({"item": "widget", "qty": 1}))
    assert_failed_with(span_named("insert_order_record"), "DatabaseError")


def test_failed_payment_sets_error_type_on_client_and_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", instant)
    monkeypatch.setattr(order_service, "simulate_db_insert", db_ok)
    monkeypatch.setattr(order_service, "simulate_payment_charge", stripe_timeout)
    asyncio.run(order_service.create_order({"item": "widget", "qty": 1}))
    assert_failed_with(span_named("external.stripe.charge"), "ConnectionError")
    assert_failed_with(span_named("insert_order_record"), "ConnectionError")


def test_cache_fallback_span_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", instant)
    monkeypatch.setattr(order_service, "simulate_db_get_product", db_read_timeout)
    product = asyncio.run(order_service.get_product("widget"))
    assert product["source"] == "cache"
    span = span_named("fetch_product")
    assert span.status.status_code is StatusCode.UNSET
    assert span.attributes is not None
    assert "error.type" not in span.attributes
    assert span.attributes["product.source"] == "cache"
    assert [event.name for event in span.events] == ["exception", "cache_fallback"]


def test_metrics_endpoint_renders_openmetrics() -> None:
    response = order_service.metrics()
    body = bytes(response.body)
    assert response.media_type == CONTENT_TYPE_LATEST
    assert b"# TYPE orders_processing_duration_milliseconds histogram" in body
    assert body.endswith(b"# EOF\n")
