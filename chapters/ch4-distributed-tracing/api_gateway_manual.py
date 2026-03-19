from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from opentelemetry import propagate, trace

ORDER_SERVICE_URL = "http://localhost:8001"
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.http_client = httpx.AsyncClient()
    yield
    await application.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/checkout")
async def checkout():
    client = app.state.http_client

    with tracer.start_as_current_span("GET /checkout (manual)"):
        headers = {}
        propagate.inject(headers)

        response = await client.post(
            f"{ORDER_SERVICE_URL}/orders",
            json={"item": "widget", "qty": 2},
            headers=headers,
        )

        return {"checkout": "complete", "order": response.json()}
