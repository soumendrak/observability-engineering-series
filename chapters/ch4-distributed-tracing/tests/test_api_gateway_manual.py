from contextlib import contextmanager

from fastapi.testclient import TestClient

import api_gateway_manual


class DummyResponse:
    def json(self):
        return {"order_id": "ord-789", "status": "created"}


class DummyHttpClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, json, headers):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return DummyResponse()

    async def aclose(self):
        return None


@contextmanager
def span_context_manager():
    yield


def test_checkout_injects_context_and_calls_order_service(monkeypatch):
    injected = {"called": False}

    def fake_inject(headers):
        injected["called"] = True
        headers["traceparent"] = "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"

    monkeypatch.setattr(api_gateway_manual.propagate, "inject", fake_inject)
    monkeypatch.setattr(
        api_gateway_manual.tracer,
        "start_as_current_span",
        lambda name: span_context_manager(),
    )

    with TestClient(api_gateway_manual.app) as client:
        fake_client = DummyHttpClient()
        api_gateway_manual.app.state.http_client = fake_client

        response = client.get("/checkout")

    assert response.status_code == 200
    body = response.json()
    assert body["checkout"] == "complete"
    assert body["order"]["order_id"] == "ord-789"

    assert injected["called"] is True
    assert len(fake_client.calls) == 1
    sent_call = fake_client.calls[0]
    assert sent_call["url"].endswith("/orders")
    assert sent_call["headers"]["traceparent"].startswith("00-")
