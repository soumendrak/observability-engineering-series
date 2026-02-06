# api_gateway.py
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

ORDER_SERVICE_URL = "http://localhost:8001"


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Create a single client for the app's lifetime (reuses connection pools)
    application.state.http_client = httpx.AsyncClient()
    yield
    await application.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/checkout")
async def checkout():
    client = app.state.http_client
    response = await client.post(
        f"{ORDER_SERVICE_URL}/orders",
        json={"item": "widget", "qty": 2},
    )
    return {"checkout": "complete", "order": response.json()}
