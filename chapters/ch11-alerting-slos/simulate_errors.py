# simulate_errors.py — Chapter 11: Alerting & SLOs
#
# Simulates an error burst to test alert rules.
#
# Usage:
#   1. Stop the Order Service so the gateway can't reach it:
#      docker compose stop order-service   (or: Ctrl+C in the run-order terminal)
#   2. Run this script: uv run python simulate_errors.py
#   3. The gateway returns 503 for /checkout because the downstream is unavailable.
#   4. Watch the alert transition: Normal → Pending → Firing in Grafana Alerting UI.
#   5. Restart the Order Service when done: make run-order

import asyncio

import httpx


async def simulate_error_burst():
    """Hit the gateway's /checkout route while Order Service is stopped.

    With the Order Service down, GET /checkout triggers a connection error
    in the gateway-to-order-service call, which returns 503 to the caller.
    This drives up the error rate and should trigger the HighErrorRate alert
    after the configured `for: 5m` duration.
    """
    async with httpx.AsyncClient() as client:
        for i in range(100):
            try:
                response = await client.get(
                    "http://localhost:8000/checkout",
                    timeout=2.0,
                )
                print(f"[{i+1:3d}/100] status={response.status_code}")
            except Exception as e:
                print(f"[{i+1:3d}/100] error={type(e).__name__}")
            await asyncio.sleep(0.1)  # 10 req/sec

    print("\nDone. Wait ~5 minutes for the alert to transition to Firing.")
    print("Check Grafana Alerting: http://localhost:3000/alerting/list")


if __name__ == "__main__":
    asyncio.run(simulate_error_burst())
