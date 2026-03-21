# order_service.py
#
# Chapter 10: Dashboards & the RED Method
#
# Identical to Chapter 9. No application code changes — this chapter
# focuses on building Grafana dashboards to visualize the metrics
# already emitted by these services.
#
# The Order Service dashboard queries these metric instruments:
#   • orders.created.total       → order rate panel
#   • orders.errors.total        → order error rate panel
#   • orders.processing.duration → order processing latency panel
#   • orders.inventory_check.duration → inventory check latency panel
#   • orders.llm_calls.total     → GenAI call rate
import asyncio
import random
import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from opentelemetry import metrics, trace
from opentelemetry.trace import StatusCode

from logging_setup import setup_logging

logger = setup_logging("order-service")

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
FAILURE_RATE: float = 0.35  # ~35 % of DB calls will fail


# ──────────────────────────────────────────────
# Custom exception
# ──────────────────────────────────────────────
class DatabaseError(Exception):
    """Simulated database failure."""


# ──────────────────────────────────────────────
# Metrics setup
# ──────────────────────────────────────────────
meter = metrics.get_meter(__name__)
tracer = trace.get_tracer(__name__)

orders_created = meter.create_counter(
    name="orders.created.total",
    description="Total orders successfully created",
    unit="1",
)

orders_errors = meter.create_counter(
    name="orders.errors.total",
    description="Total order processing errors",
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

llm_calls_total = meter.create_counter(
    name="orders.llm_calls.total",
    description="Total LLM generation calls",
    unit="1",
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
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
    await asyncio.sleep(0.3 + random.uniform(0, 0.2))
    if random.random() < FAILURE_RATE:
        raise DatabaseError("connection refused: pg-primary:5432")
    return {"id": f"ord-{random.randint(1000, 9999)}"}


async def simulate_db_get_product(product_id: str) -> dict:
    """Simulate a DB read that sometimes fails."""
    await asyncio.sleep(0.1 + random.uniform(0, 0.1))
    if random.random() < FAILURE_RATE:
        raise DatabaseError(f"read timeout fetching product {product_id}")
    return {"product_id": product_id, "name": "Super Widget", "stock": 42}


async def simulate_cache_get_product(product_id: str) -> dict:
    """Simulate a cache lookup — always succeeds, much faster."""
    await asyncio.sleep(0.01)
    return {"product_id": product_id, "name": "Super Widget (cached)", "stock": 42}


async def simulate_payment_charge(amount: float) -> dict:
    """Simulate calling a payment gateway (Stripe-like)."""
    await asyncio.sleep(0.2 + random.uniform(0, 0.1))
    if random.random() < FAILURE_RATE * 0.5:
        raise ConnectionError("stripe API timeout — no response after 300 ms")
    return {"charge_id": f"ch_{random.randint(10000, 99999)}", "status": "succeeded"}


async def simulate_health_dependency() -> None:
    """Simulate a dependency check that occasionally throws an unhandled error."""
    await asyncio.sleep(0.05)
    if random.random() < 0.2:
        raise RuntimeError("health check failed: redis unreachable")


async def simulate_llm_generation(prompt: str) -> dict:
    """Simulate an LLM call (GPT-style) that returns a completion."""
    await asyncio.sleep(0.5 + random.uniform(0, 0.5))
    if random.random() < 0.1:
        raise ConnectionError("LLM API timeout — no response after 5000 ms")

    completion = (
        "Hello John! Based on your account ending in 6789, "
        "I can see you have several options available. "
        "Your email john.smith@example.com is on file."
    )
    tokens_used = random.randint(200, 600)
    return {
        "completion": completion,
        "model": "gpt-4",
        "tokens_used": tokens_used,
    }


# ──────────────────────────────────────────────
# call_external_api wrapper
# ──────────────────────────────────────────────
async def call_external_api(
    service_name: str,
    operation: str,
    call_func,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Wrap an external API call with full observability."""
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
# ──────────────────────────────────────────────
@app.post("/orders")
async def create_order(order: dict):
    start = time.perf_counter()
    item = order.get("item", "unknown")
    qty = order.get("qty", 0)
    total_usd = calculate_total(order)

    # ── inventory check ──────────────────────────
    with tracer.start_as_current_span("check_inventory") as inv_span:
        inv_span.set_attribute("inventory.item", item)
        inv_span.set_attribute("inventory.requested_qty", qty)
        logger.info("Starting inventory check", item=item, qty=qty)
        inv_start = time.perf_counter()
        await asyncio.sleep(0.15)
        inv_ms = (time.perf_counter() - inv_start) * 1000
        inventory_check_duration.record(inv_ms, {"item": item})
        logger.info("Inventory check complete", item=item, available=True)

    # ── DB insert — Pattern 2 ─────────────────────
    with tracer.start_as_current_span("insert_order_record") as span:
        span.set_attribute("order.item", item)
        span.set_attribute("order.qty", qty)
        span.set_attribute("order.total_usd", total_usd)

        try:
            logger.info("Inserting order record", item=item, qty=qty, total_usd=total_usd)
            result = await simulate_db_insert(order)
            order_id = result["id"]
            span.set_attribute("order.id", order_id)

        except DatabaseError as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            orders_errors.add(1, {
                "error.type": type(e).__name__,
                "operation": "insert_order_record",
            })
            logger.error(
                "Order insert failed",
                error_type=type(e).__name__,
                error_message=str(e),
                item=item,
                qty=qty,
            )
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

    # ── Success path ─────────────────────────────
    total_ms = (time.perf_counter() - start) * 1000
    order_processing_duration.record(total_ms, {"item": item})
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
# GenAI simulation: /ask
# ──────────────────────────────────────────────
@app.post("/ask")
async def ask_question(body: dict):
    """GenAI-style endpoint: user asks a question, LLM responds."""
    user_query = body.get(
        "question",
        "My name is John Smith, SSN 123-45-6789. "
        "My email is john.smith@example.com. What are my account options?",
    )

    with tracer.start_as_current_span("llm_generation") as span:
        span.set_attribute("llm.prompt", user_query)
        span.set_attribute("user.query", user_query)
        span.set_attribute("llm.model", "gpt-4")

        try:
            logger.info("Starting LLM generation")
            result = await call_external_api(
                service_name="openai",
                operation="chat_completion",
                call_func=simulate_llm_generation,
                prompt=user_query,
            )

            span.set_attribute("llm.completion", result["completion"])
            span.set_attribute("llm.tokens_used", result["tokens_used"])
            llm_calls_total.add(1, {"model": result["model"], "status": "success"})

            logger.info(
                "LLM generation complete",
                model=result["model"],
                tokens_used=result["tokens_used"],
            )
            return {
                "answer": result["completion"],
                "model": result["model"],
                "tokens_used": result["tokens_used"],
            }

        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            llm_calls_total.add(1, {"model": "gpt-4", "status": "error"})
            logger.error(
                "LLM generation failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return JSONResponse(
                status_code=503,
                content={"error": "AI service temporarily unavailable."},
            )


# ──────────────────────────────────────────────
# Pattern 1: Let It Propagate (/health)
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    await simulate_health_dependency()
    return {"status": "ok", "service": "order-service"}
