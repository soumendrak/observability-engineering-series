# api_gateway.py
#
# Chapter 7: Error Handling & Semantic Instrumentation
#
# Builds on Chapter 6. New additions vs ch6:
#   • Manual tracer — enriches the active span with business context before HTTP calls
#   • span.record_exception() + span.set_status(ERROR) on every caught failure
#   • Structured error logs with error_type / error_message fields
#   • /products/{product_id} proxy endpoint (Pattern 3 visible end-to-end)
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.trace import StatusCode
from prometheus_client import Counter, Histogram, REGISTRY
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from logging_setup import setup_logging

logger = setup_logging("api-gateway")

ORDER_SERVICE_URL = "http://localhost:8001"

tracer = trace.get_tracer(__name__)


def get_exemplar() -> dict:
    """Extract trace_id and span_id from the current OTel context."""
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    return {}


# ──────────────────────────────────────────────
# Metrics setup
# ──────────────────────────────────────────────
def setup_metrics():
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider


provider = setup_metrics()
meter = provider.get_meter(__name__)

# ── OTel counters ─────────────────────────────
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

# ── prometheus_client Histogram (supports exemplars) ─
request_duration = Histogram(
    "gateway_request_duration_milliseconds",
    "Request duration in milliseconds",
    labelnames=["http_method", "http_route", "http_status_code"],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)


# ──────────────────────────────────────────────
# App lifecycle
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.http_client = httpx.AsyncClient()
    yield
    await application.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


# ──────────────────────────────────────────────
# Metrics middleware (unchanged from ch6)
# ──────────────────────────────────────────────
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


# ──────────────────────────────────────────────
# /checkout — demonstrates Pattern 2 at the gateway level
#
# Business context (item, qty) is set on the span before the downstream
# call. On HTTP error, the exception is recorded and the span is marked
# ERROR — so Jaeger shows both the gateway span and the order-service
# span as red.
# ──────────────────────────────────────────────
@app.get("/checkout")
async def checkout():
    client = app.state.http_client
    span = trace.get_current_span()

    # Set business context on the active (auto-instrumented) span
    # BEFORE making the downstream call.
    item = "widget"
    qty = 2
    span.set_attribute("checkout.item", item)
    span.set_attribute("checkout.qty", qty)

    try:
        logger.info("Starting checkout request", item=item, qty=qty)
        response = await client.post(
            f"{ORDER_SERVICE_URL}/orders",
            json={"item": item, "qty": qty},
        )

        body = response.json()

        if response.status_code >= 500:
            # The order service returned an explicit error body.
            # Record it on the span so the gateway trace also turns red.
            error_msg = body.get("error", f"upstream returned {response.status_code}")
            exc = httpx.HTTPStatusError(
                error_msg,
                request=response.request,
                response=response,
            )
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, error_msg)
            order_service_errors.add(1, {
                "error.type": "HTTPStatusError",
                "http.status_code": str(response.status_code),
            })
            logger.error(
                "Order service returned error",
                status_code=response.status_code,
                error_message=error_msg,
                item=item,
                qty=qty,
            )
            return JSONResponse(status_code=response.status_code, content=body)

        order_id = body.get("order_id")
        span.set_attribute("checkout.order_id", order_id or "unknown")
        logger.info("Checkout complete", order_id=order_id, item=item, qty=qty)
        return {"checkout": "complete", "order": body}

    except httpx.HTTPError as e:
        # Network-level failure (connection refused, timeout, etc.)
        span.record_exception(e)
        span.set_status(StatusCode.ERROR, str(e))
        order_service_errors.add(1, {
            "error.type": type(e).__name__,
            "http.status_code": "0",
        })
        logger.error(
            "Order service call failed",
            error_type=type(e).__name__,
            error_message=str(e),
            item=item,
            qty=qty,
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Order service unavailable. Please try again."},
        )


# ──────────────────────────────────────────────
# /products/{product_id} — proxy to order service
#
# Demonstrates Pattern 3 end-to-end: even when the downstream service
# falls back to cache, the overall request is still "successful" from
# the gateway's perspective. The gateway span stays green; the order-
# service span carries the exception event + cache_fallback event.
# ──────────────────────────────────────────────
@app.get("/products/{product_id}")
async def get_product(product_id: str):
    client = app.state.http_client
    span = trace.get_current_span()
    span.set_attribute("product.id", product_id)

    try:
        logger.info("Fetching product", product_id=product_id)
        response = await client.get(f"{ORDER_SERVICE_URL}/products/{product_id}")
        body = response.json()
        source = body.get("source", "unknown")
        span.set_attribute("product.source", source)
        logger.info(
            "Product fetched",
            product_id=product_id,
            source=source,
        )
        return body

    except httpx.HTTPError as e:
        span.record_exception(e)
        span.set_status(StatusCode.ERROR, str(e))
        order_service_errors.add(1, {
            "error.type": type(e).__name__,
            "http.status_code": "0",
        })
        logger.error(
            "Failed to fetch product",
            product_id=product_id,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Product service unavailable."},
        )


# ──────────────────────────────────────────────
# /health — simple liveness check (no downstream call)
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}
