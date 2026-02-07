# order_service.py
import asyncio
import time

from fastapi import FastAPI, Response
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY


# --- Metrics Setup ---
def setup_metrics():
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    
    # Register with Prometheus REGISTRY to expose metrics via generate_latest()
    try:
        REGISTRY.register(reader)
    except Exception:
        pass
        
    return provider


provider = setup_metrics()
meter = provider.get_meter(__name__)
tracer = trace.get_tracer(__name__)

# --- Business Metrics ---
orders_created = meter.create_counter(
    name="orders.created.total",
    description="Total orders successfully created",
    unit="1",
)

order_processing_duration = meter.create_histogram(
    name="orders.processing.duration",
    description="Time to process an order end-to-end",
    unit="ms",
)

inventory_check_duration = meter.create_histogram(
    name="orders.inventory_check.duration",
    description="Time spent checking inventory",
    unit="ms",
)

app = FastAPI()


@app.post("/orders")
async def create_order(order: dict):
    start = time.perf_counter()
    item = order.get("item", "unknown")

    with tracer.start_as_current_span("check_inventory") as span:
        span.set_attribute("item", item)
        inv_start = time.perf_counter()
        await asyncio.sleep(0.3)
        inventory_check_duration.record(
            (time.perf_counter() - inv_start) * 1000,
            {"item": item},
        )

    with tracer.start_as_current_span("insert_order_record") as span:
        span.set_attribute("order.item", item)
        span.set_attribute("order.qty", order.get("qty", 0))
        await asyncio.sleep(1.5)

    # Record business metrics
    total_ms = (time.perf_counter() - start) * 1000
    order_processing_duration.record(total_ms, {"item": item})
    orders_created.add(1, {"item": item})

    return {"order_id": "ord-789", "status": "created"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
