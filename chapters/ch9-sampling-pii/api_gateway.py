# api_gateway.py
#
# Chapter 9: Sampling & PII Scrubbing
#
# Builds on Chapter 8. Changes vs ch8:
#   • New /ask endpoint proxying to the Order Service's GenAI endpoint.
#     Demonstrates PII flowing through span attributes that the
#     Collector's transform processor will scrub before export.
#   • No application-side sampling — the Collector handles tail sampling.
#   • All other endpoints (checkout, products, health) unchanged from ch8.
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import metrics, trace
from opentelemetry.trace import StatusCode

from logging_setup import setup_logging

logger = setup_logging("api-gateway")

ORDER_SERVICE_URL = "http://localhost:8001"

tracer = trace.get_tracer(__name__)

# ──────────────────────────────────────────────
# Metrics setup
# ──────────────────────────────────────────────
meter = metrics.get_meter(__name__)

request_counter = meter.create_counter(
    name="gateway.requests.total",
    description="Total requests to the API Gateway",
    unit="1",
)

order_service_errors = meter.create_counter(
    name="gateway.order_service.errors.total",
    description="Errors when calling the Order Service",
    unit="1",
)

request_duration = meter.create_histogram(
    name="gateway.request.duration",
    description="Request duration in milliseconds",
    unit="ms",
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
# Metrics middleware
# ──────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    attributes = {
        "http.method": request.method,
        "http.route": request.url.path,
        "http.status_code": response.status_code,
    }
    request_counter.add(1, attributes)
    request_duration.record(duration_ms, attributes)

    return response


# ──────────────────────────────────────────────
# /checkout — Pattern 2 at the gateway level
# ──────────────────────────────────────────────
@app.get("/checkout")
async def checkout():
    client = app.state.http_client
    span = trace.get_current_span()

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
# /ask — GenAI proxy endpoint
#
# Proxies user questions to the Order Service's /ask endpoint.
# The user query (which may contain PII) flows through span attributes
# on both the gateway and order-service spans.
# The Collector scrubs these attributes before export to Jaeger.
# ──────────────────────────────────────────────
@app.post("/ask")
async def ask_question(body: dict):
    client = app.state.http_client
    span = trace.get_current_span()

    question = body.get(
        "question",
        "My name is John Smith, SSN 123-45-6789. "
        "My email is john.smith@example.com. What are my account options?",
    )

    # Set the user query on the gateway span too — the Collector scrubs it.
    span.set_attribute("user.query", question)

    try:
        logger.info("Proxying GenAI request to order service")
        response = await client.post(
            f"{ORDER_SERVICE_URL}/ask",
            json={"question": question},
        )

        body = response.json()

        if response.status_code >= 500:
            error_msg = body.get("error", f"upstream returned {response.status_code}")
            span.set_status(StatusCode.ERROR, error_msg)
            order_service_errors.add(1, {
                "error.type": "GenAI_Error",
                "http.status_code": str(response.status_code),
            })
            logger.error("GenAI request failed", error_message=error_msg)
            return JSONResponse(status_code=response.status_code, content=body)

        logger.info("GenAI request complete", model=body.get("model"))
        return body

    except httpx.HTTPError as e:
        span.record_exception(e)
        span.set_status(StatusCode.ERROR, str(e))
        order_service_errors.add(1, {
            "error.type": type(e).__name__,
            "http.status_code": "0",
        })
        logger.error(
            "GenAI service call failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        return JSONResponse(
            status_code=503,
            content={"error": "AI service unavailable. Please try again."},
        )


# ──────────────────────────────────────────────
# /health — simple liveness check
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}
