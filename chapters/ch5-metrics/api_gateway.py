import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import psutil
from fastapi import FastAPI, Request, Response
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = "http://localhost:8001"


def setup_metrics() -> MeterProvider:
    reader = PrometheusMetricReader()
    return MeterProvider(metric_readers=[reader])


provider = setup_metrics()
meter = provider.get_meter(__name__)

request_counter = meter.create_counter(
    name="gateway.requests.total",
    description="Total requests to the API Gateway",
    unit="1",
)
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


def cpu_utilization_callback(options: CallbackOptions) -> Iterable[Observation]:
    yield Observation(psutil.cpu_percent() / 100)


meter.create_observable_gauge(
    name="system.cpu.utilization",
    description="CPU utilization of this host, from 0 to 1",
    unit="1",
    callbacks=[cpu_utilization_callback],
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.http_client = httpx.AsyncClient()
    yield
    await application.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    attributes: dict[str, str | int] = {
        "http.method": request.method,
        "http.route": request.url.path,
        "http.status_code": response.status_code,
    }
    request_counter.add(1, attributes)
    request_duration.record(duration_ms, attributes)

    return response


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/checkout")
async def checkout() -> dict[str, Any]:
    client: httpx.AsyncClient = app.state.http_client
    try:
        response = await client.post(
            f"{ORDER_SERVICE_URL}/orders",
            json={"item": "widget", "qty": 2},
        )
        return {"checkout": "complete", "order": response.json()}
    except httpx.HTTPError as e:
        order_service_errors.add(1, {"error.type": type(e).__name__})
        raise
