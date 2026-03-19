import asyncio

from fastapi import FastAPI, Request
from opentelemetry import propagate, trace

app = FastAPI()
tracer = trace.get_tracer(__name__)


@app.post("/orders")
async def create_order(order: dict, request: Request):
    carrier = dict(request.headers)
    extracted_context = propagate.extract(carrier)

    with tracer.start_as_current_span(
        "POST /orders (manual)", context=extracted_context
    ):
        await asyncio.sleep(0.3)
        await asyncio.sleep(1.5)
        return {"order_id": "ord-789", "status": "created"}
