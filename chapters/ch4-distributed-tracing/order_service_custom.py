# order_service_custom.py
import asyncio
import os
import sys

from fastapi import FastAPI
from loguru import logger
from opentelemetry import trace

# Loguru + OTel Trace ID Patching (reused from Chapter 3)
def otel_patcher(record):
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        record["extra"]["trace_id"] = format(ctx.trace_id, "032x")
        record["extra"]["span_id"] = format(ctx.span_id, "016x")


logger.configure(patcher=otel_patcher)

if os.getenv("ENV") == "PROD":
    logger.remove()
    logger.add(sys.stdout, serialize=True)

tracer = trace.get_tracer(__name__)

app = FastAPI()


@app.post("/orders")
async def create_order(order: dict):
    with tracer.start_as_current_span("check_inventory") as span:
        span.set_attribute("item", order.get("item", ""))
        await asyncio.sleep(0.3)
        logger.info(f"Inventory checked for item={order.get('item', '')}")

    with tracer.start_as_current_span("insert_order_record") as span:
        span.set_attribute("order.item", order.get("item", ""))
        span.set_attribute("order.qty", order.get("qty", 0))
        await asyncio.sleep(1.5)
        logger.info("Order record inserted")

    return {"order_id": "ord-789", "status": "created"}
