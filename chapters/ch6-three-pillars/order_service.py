# order_service.py
import asyncio
import time

from fastapi import FastAPI, Response
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import Histogram as PromHistogram, REGISTRY
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from logging_setup import setup_logging

logger = setup_logging("order-service")


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


# --- Metrics Setup ---
def setup_metrics():
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider


provider = setup_metrics()
meter = provider.get_meter(__name__)
tracer = trace.get_tracer(__name__)

# --- OTel Counter (no exemplar needed) ---
orders_created = meter.create_counter(
    name="orders.created.total",
    description="Total orders successfully created",
    unit="1",
)

# --- prometheus_client Histograms (supports exemplars) ---
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

app = FastAPI()


@app.post("/orders")
async def create_order(order: dict):
    start = time.perf_counter()
    item = order.get("item", "unknown")
    qty = order.get("qty", 0)

    with tracer.start_as_current_span("check_inventory") as span:
        span.set_attribute("item", item)
        logger.info("Starting inventory check", item=item)
        inv_start = time.perf_counter()
        await asyncio.sleep(0.3)
        inv_ms = (time.perf_counter() - inv_start) * 1000
        exemplar = get_exemplar()
        inventory_check_duration.labels(item=item).observe(
            inv_ms, exemplar=exemplar if exemplar else None
        )
        logger.info("Inventory check complete", item=item, available=True)

    with tracer.start_as_current_span("insert_order_record") as span:
        span.set_attribute("order.item", item)
        span.set_attribute("order.qty", qty)
        logger.info("Inserting order record", item=item, qty=qty)
        await asyncio.sleep(1.5)
        logger.info("Order record inserted", item=item, qty=qty)

    # Record business metrics with exemplar context
    total_ms = (time.perf_counter() - start) * 1000
    exemplar = get_exemplar()
    order_processing_duration.labels(item=item).observe(
        total_ms, exemplar=exemplar if exemplar else None
    )
    orders_created.add(1, {"item": item})

    logger.info(
        "Order created",
        order_id="ord-789",
        item=item,
        qty=qty,
        processing_time_ms=round(total_ms, 1),
    )

    return {"order_id": "ord-789", "status": "created"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
