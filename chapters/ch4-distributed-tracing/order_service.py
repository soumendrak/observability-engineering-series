# order_service.py
import asyncio

from fastapi import FastAPI

app = FastAPI()


@app.post("/orders")
async def create_order(order: dict):
    # Simulate inventory check
    await asyncio.sleep(0.3)

    # Simulate a slow DB insert
    await asyncio.sleep(1.5)

    return {"order_id": "ord-789", "status": "created"}
