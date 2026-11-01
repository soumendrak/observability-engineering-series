import asyncio

import pytest
from fastapi.testclient import TestClient

import order_service


async def no_wait(seconds: float) -> None:
    return None


def test_create_order_records_business_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    with TestClient(order_service.app) as client:
        response = client.post("/orders", json={"item": "widget", "qty": 2})
        body = client.get("/metrics").text
    assert response.json() == {"order_id": "ord-789", "status": "created"}
    assert 'orders_created_total{item="widget"' in body
    assert "orders_processing_duration_milliseconds_bucket" in body
