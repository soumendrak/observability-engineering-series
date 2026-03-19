# api_gateway.py
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import Counter, Histogram, REGISTRY
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from logging_setup import setup_logging

logger = setup_logging("api-gateway")

ORDER_SERVICE_URL = "http://localhost:8001"


def get_exemplar():
    """Extract trace_id and span_id from the current OTel context for use as a Prometheus exemplar."""
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    return {}


def setup_metrics():
    """Initialize OTel metrics with Prometheus exporter (for counters)."""
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider


# OTel metrics (counters — no exemplar needed)
provider = setup_metrics()
meter = provider.get_meter(__name__)

request_counter = meter.create_counter(
    name="gateway.requests.total",
    description="Total requests to the API Gateway",
    unit="1",
)
request_counter.add(0, {"http.method": "init", "http.route": "init", "http.status_code": 0})

order_service_errors = meter.create_counter(
    name="gateway.order_service.errors.total",
    description="Errors when calling the Order Service",
    unit="1",
)

# prometheus_client Histogram (supports exemplars)
request_duration = Histogram(
    "gateway_request_duration_milliseconds",
    "Request duration in milliseconds",
    labelnames=["http_method", "http_route", "http_status_code"],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.http_client = httpx.AsyncClient()
    yield
    await application.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    if request.url.path == "/metrics":
        return response

    attributes = {
        "http.method": request.method,
        "http.route": request.url.path,
        "http.status_code": response.status_code,
    }
    request_counter.add(1, attributes)

    # Attach the current trace context as an exemplar
    exemplar = get_exemplar()
    request_duration.labels(
        http_method=request.method,
        http_route=request.url.path,
        http_status_code=str(response.status_code),
    ).observe(duration_ms, exemplar=exemplar if exemplar else None)

    return response


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.get("/checkout")
async def checkout():
    client = app.state.http_client
    try:
        logger.info("Starting checkout request")
        response = await client.post(
            f"{ORDER_SERVICE_URL}/orders",
            json={"item": "widget", "qty": 2},
        )
        logger.info("Checkout complete", order_id=response.json().get("order_id"))
        return {"checkout": "complete", "order": response.json()}
    except httpx.HTTPError as e:
        order_service_errors.add(1, {"error.type": type(e).__name__})
        logger.error(f"Order service call failed: {e}")
        raise
