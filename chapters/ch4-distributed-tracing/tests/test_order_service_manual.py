from contextlib import contextmanager

from fastapi.testclient import TestClient

import order_service_manual


@contextmanager
def span_context_manager():
    yield


def test_orders_extracts_context_and_creates_child_span(monkeypatch):
    captured = {"carrier": None, "context": None}
    extracted_context = object()

    async def fake_sleep(_seconds):
        return None

    def fake_extract(carrier):
        captured["carrier"] = carrier
        return extracted_context

    def fake_start_as_current_span(name, context=None):
        assert name == "POST /orders (manual)"
        captured["context"] = context
        return span_context_manager()

    monkeypatch.setattr(order_service_manual.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(order_service_manual.propagate, "extract", fake_extract)
    monkeypatch.setattr(
        order_service_manual.tracer,
        "start_as_current_span",
        fake_start_as_current_span,
    )

    with TestClient(order_service_manual.app) as client:
        response = client.post(
            "/orders",
            json={"item": "widget", "qty": 2},
            headers={
                "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "created"
    assert captured["carrier"] is not None
    assert "traceparent" in captured["carrier"]
    assert captured["context"] is extracted_context
