# order_service.py
#
# Chapter 7: Error Handling & Semantic Instrumentation
#
# Demonstrates all three error patterns:
#   Pattern 1 — Let It Propagate  (/health endpoint)
#   Pattern 2 — Catch and Record  (/orders endpoint)
#   Pattern 3 — Catch and Continue (/products/{product_id} endpoint)
#
# New vs Chapter 6:
#   • DatabaseError simulation with configurable FAILURE_RATE
#   • span.record_exception() + span.set_status(ERROR) in every caught failure
#   • cache fallback with span.add_event() but no ERROR status (pattern 3)
#   • Business-context span attributes (order.item, order.qty, order.total_usd, …)
#   • call_external_api() wrapper for instrumented external calls
#   • orders.errors.total OTel counter with error.type / operation labels
import asyncio
import random
import time
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.trace import StatusCode
from prometheus_client import Histogram as PromHistogram, REGISTRY
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from logging_setup import setup_logging

logger = setup_logging("order-service")

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
# Set to 0.0 for deterministic success, 1.0 for always-fail.
FAILURE_RATE: float = 0.35  # ~35 % of DB calls will fail


# ──────────────────────────────────────────────
# Custom exception
# ──────────────────────────────────────────────
class DatabaseError(Exception):
    """Simulated database failure."""


# ──────────────────────────────────────────────
# Metrics setup (carried over from ch6)
# ──────────────────────────────────────────────
def setup_metrics():
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider


provider = setup_metrics()
meter = provider.get_meter(__name__)
tracer = trace.get_tracer(__name__)

# ── OTel counters (no exemplar needed) ───────
orders_created = meter.create_counter(
    name="orders.created.total",
    description="Total orders successfully created",
    unit="1",
)

# NEW: error counter — tracks failures by operation and error type
orders_errors = meter.create_counter(
    name="orders.errors.total",
    description="Total order processing errors",
    unit="1",
)

# ── prometheus_client Histograms (support exemplars) ─
order_processing_duration = PromHistogram(
    "orders_processing_duration_milliseconds",
    "Time to process an order end-to-end",
    labelnames=["item"],
    buckets=[100, 250, 500, 1000, 2500, 5000, 10000],
)

inventory_check_duration = PromHistogram(
    "orders_inventory_check_duration_milliseconds",
    "Time spent checking inventory",
    labelnames=["item"],
    buckets=[50, 100, 250, 500, 1000],
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
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


def calculate_total(order: dict) -> float:
    """Very simple total calculator for demonstration purposes."""
    price_per_unit = {"widget": 24.99, "gadget": 49.99, "doohickey": 9.99}
    item = order.get("item", "widget")
    qty = order.get("qty", 1)
    return round(price_per_unit.get(item, 24.99) * qty, 2)


# ──────────────────────────────────────────────
# Simulated external dependencies
# ──────────────────────────────────────────────
async def simulate_db_insert(order: dict) -> dict:
    """Simulate a DB insert that sometimes fails."""
    await asyncio.sleep(0.3 + random.uniform(0, 0.2))  # 300–500 ms latency
    if random.random() < FAILURE_RATE:
        raise DatabaseError("connection refused: pg-primary:5432")
    return {"id": f"ord-{random.randint(1000, 9999)}"}


async def simulate_db_get_product(product_id: str) -> dict:
    """Simulate a DB read that sometimes fails."""
    await asyncio.sleep(0.1 + random.uniform(0, 0.1))  # 100–200 ms latency
    if random.random() < FAILURE_RATE:
        raise DatabaseError(f"read timeout fetching product {product_id}")
    return {"product_id": product_id, "name": "Super Widget", "stock": 42}


async def simulate_cache_get_product(product_id: str) -> dict:
    """Simulate a cache lookup — always succeeds, much faster."""
    await asyncio.sleep(0.01)  # 10 ms
    return {"product_id": product_id, "name": "Super Widget (cached)", "stock": 42}


async def simulate_payment_charge(amount: float) -> dict:
    """Simulate calling a payment gateway (Stripe-like)."""
    await asyncio.sleep(0.2 + random.uniform(0, 0.1))  # 200–300 ms
    if random.random() < FAILURE_RATE * 0.5:  # Lower failure rate for payments
        raise ConnectionError("stripe API timeout — no response after 300 ms")
    return {"charge_id": f"ch_{random.randint(10000, 99999)}", "status": "succeeded"}


async def simulate_health_dependency() -> None:
    """Simulate a dependency check that occasionally throws an unhandled error."""
    await asyncio.sleep(0.05)
    if random.random() < 0.2:  # 20 % chance to blow up
        raise RuntimeError("health check failed: redis unreachable")


# ──────────────────────────────────────────────
# call_external_api wrapper (Pattern: instrumented external call)
# Wraps any external API call with a CLIENT span, timing, and error recording.
# ──────────────────────────────────────────────
async def call_external_api(
    service_name: str,
    operation: str,
    call_func,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Wrap an external API call with full observability.

    Creates a CLIENT span, records duration, and sets ERROR status on failure.
    The caller is responsible for deciding whether to re-raise or handle.
    """
    with tracer.start_as_current_span(
        f"external.{service_name}.{operation}",
        kind=trace.SpanKind.CLIENT,
    ) as span:
        span.set_attribute("external.service", service_name)
        span.set_attribute("external.operation", operation)

        start = time.perf_counter()
        try:
            result = await call_func(*args, **kwargs)
            span.set_attribute("external.status", "success")
            return result
        except Exception as e:
            # Record exception details AND mark span as failed
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            span.set_attribute("external.status", "error")
            span.set_attribute("external.error_type", type(e).__name__)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("external.duration_ms", round(duration_ms, 2))


# ──────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────
app = FastAPI()


# ──────────────────────────────────────────────
# Pattern 2: Catch and Record (/orders)
#
# The DB call may fail. We catch it, record the exception on the span,
# mark the span as ERROR, increment the error metric, log a structured
# error, and return a graceful 500 response.
#
# For the payment call we use call_external_api() which handles span
# recording internally — we only need to catch it here and decide what
# to return to the caller.
# ──────────────────────────────────────────────
@app.post("/orders")
async def create_order(order: dict):
    start = time.perf_counter()
    item = order.get("item", "unknown")
    qty = order.get("qty", 0)
    total_usd = calculate_total(order)

    # ── inventory check (unchanged from ch6) ─────────
    with tracer.start_as_current_span("check_inventory") as inv_span:
        inv_span.set_attribute("inventory.item", item)
        inv_span.set_attribute("inventory.requested_qty", qty)
        logger.info("Starting inventory check", item=item, qty=qty)
        inv_start = time.perf_counter()
        await asyncio.sleep(0.15)  # simulate inventory lookup
        inv_ms = (time.perf_counter() - inv_start) * 1000
        exemplar = get_exemplar()
        inventory_check_duration.labels(item=item).observe(
            inv_ms, exemplar=exemplar if exemplar else None
        )
        logger.info("Inventory check complete", item=item, available=True)

    # ── DB insert — Pattern 2 ─────────────────────────
    with tracer.start_as_current_span("insert_order_record") as span:
        # Set business context BEFORE the operation so it's
        # present on the span even if the operation fails.
        span.set_attribute("order.item", item)
        span.set_attribute("order.qty", qty)
        span.set_attribute("order.total_usd", total_usd)

        try:
            logger.info("Inserting order record", item=item, qty=qty, total_usd=total_usd)
            result = await simulate_db_insert(order)
            order_id = result["id"]
            span.set_attribute("order.id", order_id)

        except DatabaseError as e:
            # 1. Record the exception on the span (adds Events with stack trace)
            span.record_exception(e)
            # 2. Mark the span as failed in the UI (red in Jaeger)
            span.set_status(StatusCode.ERROR, str(e))
            # 3. Increment the error metric
            orders_errors.add(1, {
                "error.type": type(e).__name__,
                "operation": "insert_order_record",
            })
            # 4. Structured log with full context
            logger.error(
                "Order insert failed",
                error_type=type(e).__name__,
                error_message=str(e),
                item=item,
                qty=qty,
            )
            # 5. Graceful response — caller gets a 500 with a retry hint
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Order could not be created. Please try again later.",
                    "error_type": type(e).__name__,
                },
            )

        # ── Payment — call_external_api wrapper ──────
        try:
            payment = await call_external_api(
                service_name="stripe",
                operation="charge",
                call_func=simulate_payment_charge,
                amount=total_usd,
            )
            span.set_attribute("payment.charge_id", payment["charge_id"])
            span.set_attribute("payment.status", payment["status"])
        except Exception as e:
            # call_external_api already recorded the exception on its own span.
            # Here we record it on the parent span too, and mark the order failed.
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, f"Payment failed: {e}")
            orders_errors.add(1, {
                "error.type": type(e).__name__,
                "operation": "payment_charge",
            })
            logger.error(
                "Payment charge failed",
                error_type=type(e).__name__,
                error_message=str(e),
                order_id=order_id,
                total_usd=total_usd,
            )
            return JSONResponse(
                status_code=502,
                content={
                    "error": "Payment processing failed. Your order has not been placed.",
                    "order_id": order_id,
                },
            )

    # ── Success path ─────────────────────────────────
    total_ms = (time.perf_counter() - start) * 1000
    exemplar = get_exemplar()
    order_processing_duration.labels(item=item).observe(
        total_ms, exemplar=exemplar if exemplar else None
    )
    orders_created.add(1, {"item": item})
    logger.info(
        "Order created",
        order_id=order_id,
        item=item,
        qty=qty,
        total_usd=total_usd,
        processing_time_ms=round(total_ms, 1),
    )
    return {"order_id": order_id, "status": "created", "total_usd": total_usd}


# ──────────────────────────────────────────────
# Pattern 3: Catch and Continue (/products/{product_id})
#
# The DB read may fail, but we can recover from a cache. The span is
# NOT marked as ERROR — we recovered. We do record the exception as an
# Event and add a cache_fallback span event so the recovery is visible
# in Jaeger.
# ──────────────────────────────────────────────
@app.get("/products/{product_id}")
async def get_product(product_id: str):
    with tracer.start_as_current_span("fetch_product") as span:
        span.set_attribute("product.id", product_id)

        try:
            product = await simulate_db_get_product(product_id)
            source = "db"
            logger.info("Product fetched from DB", product_id=product_id)

        except DatabaseError as e:
            # Record the exception as an Event for visibility — but
            # do NOT set status to ERROR, because we will recover.
            span.record_exception(e)
            span.add_event(
                "cache_fallback",
                {"reason": str(e), "fallback_source": "redis"},
            )
            logger.warning(
                "DB fetch failed, falling back to cache",
                product_id=product_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            product = await simulate_cache_get_product(product_id)
            source = "cache"

        span.set_attribute("product.source", source)
        return {**product, "source": source}


# ──────────────────────────────────────────────
# Pattern 1: Let It Propagate (/health)
#
# The dependency check may throw a RuntimeError. We do NOT catch it.
# OTel auto-instrumentation (FastAPI instrumentor) will automatically:
#   • catch the unhandled exception
#   • call span.record_exception() on the active span
#   • set span status to ERROR
# FastAPI converts it to a 500 response.
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    await simulate_health_dependency()
    return {"status": "ok", "service": "order-service"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
