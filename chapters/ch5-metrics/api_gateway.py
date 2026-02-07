# api_gateway.py
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = "http://localhost:8001"


def setup_metrics():
    """Initialize OTel metrics with Prometheus exporter."""
    logger.info("Setting up PrometheusMetricReader...")
    reader = PrometheusMetricReader()
    try:
        REGISTRY.register(reader)
        logger.info("Registered PrometheusMetricReader with global REGISTRY")
    except Exception as e:
        logger.warning(f"Failed to register reader (might be already registered): {e}")
    
    provider = MeterProvider(metric_readers=[reader])
    return provider


# Initialize metrics before creating instruments
provider = setup_metrics()
meter = provider.get_meter(__name__)

# --- Define Instruments ---
request_counter = meter.create_counter(
    name="gateway.requests.total",
    description="Total requests to the API Gateway",
    unit="1",
)
# Initialize with 0 to ensure it appears
request_counter.add(0, {"http.method": "init", "http.route": "init", "http.status_code": 0})

request_duration = meter.create_histogram(
    name="gateway.request.duration",
    description="Request duration in milliseconds",
    unit="ms",
)

order_service_errors = meter.create_counter(
    name="gateway.order_service.errors.total",
    description="Errors when calling the Order Service",
    unit="1",
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

    attributes = {
        "http.method": request.method,
        "http.route": request.url.path,
        "http.status_code": response.status_code,
    }
    request_counter.add(1, attributes)
    request_duration.record(duration_ms, attributes)

    return response


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/checkout")
async def checkout():
    client = app.state.http_client
    try:
        response = await client.post(
            f"{ORDER_SERVICE_URL}/orders",
            json={"item": "widget", "qty": 2},
        )
        return {"checkout": "complete", "order": response.json()}
    except httpx.HTTPError as e:
        order_service_errors.add(1, {"error.type": type(e).__name__})
        raise
