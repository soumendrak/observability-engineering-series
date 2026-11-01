import logging
import re

import httpx
import pytest
from fastapi.testclient import TestClient

import api_gateway


def order_service(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


def metric_value(text: str, name: str, labels: str = "") -> float:
    pattern = rf"^{name}\{{[^}}]*{labels}[^}}]*\}} (\S+)$"
    match = re.search(pattern, text, re.MULTILINE)
    assert match, f"{name} with {labels!r} not exposed"
    return float(match.group(1))


def test_setup_metrics_logs_no_registration_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        api_gateway.setup_metrics()
    assert caplog.records == []


def test_metrics_exposes_cpu_utilization_between_zero_and_one() -> None:
    with TestClient(api_gateway.app) as client:
        client.get("/metrics")
        body = client.get("/metrics").text
    value = metric_value(body, "system_cpu_utilization")
    assert 0.0 <= value <= 1.0


def test_checkout_returns_order_and_counts_request() -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"order_id": "ord-1"})

    with TestClient(api_gateway.app) as client:
        api_gateway.app.state.http_client = order_service(httpx.MockTransport(reply))
        response = client.get("/checkout")
        body = client.get("/metrics").text
    assert response.json() == {"checkout": "complete", "order": {"order_id": "ord-1"}}
    assert metric_value(body, "gateway_requests_total", 'http_route="/checkout"') >= 1


def test_checkout_counts_order_service_errors_by_type() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with TestClient(api_gateway.app) as client:
        api_gateway.app.state.http_client = order_service(httpx.MockTransport(refuse))
        with pytest.raises(httpx.ConnectError):
            client.get("/checkout")
        body = client.get("/metrics").text
    errors = metric_value(
        body, "gateway_order_service_errors_total", 'error_type="ConnectError"'
    )
    assert errors >= 1
