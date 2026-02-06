# Chapter 4: Distributed Tracing

This chapter extends the single-service tracing from Chapter 3 into **distributed tracing** across two FastAPI services, demonstrating how OpenTelemetry propagates the `traceparent` header automatically.

## What Changed from Chapter 3

| Aspect | Chapter 3 | Chapter 4 |
|--------|-----------|-----------|
| Services | Single service (3 variants) | Two services (API Gateway + Order Service) |
| Tracing scope | Within one process | Across service boundaries via W3C Trace Context |
| HTTP client | External call demo | Inter-service call (`api-gateway` → `order-service`) |
| Key concept | Auto / medium / custom instrumentation | Distributed trace propagation |

**Same infrastructure**: Jaeger, same OTel dependencies, same `opentelemetry-instrument` CLI.

**New pattern**: The `httpx` instrumentation automatically injects the `traceparent` header into outgoing requests. The receiving service's FastAPI instrumentation reads it and creates a child span under the same trace.

## Files

| File | Description | Port |
|------|-------------|------|
| `api_gateway.py` | Upstream service — receives `/checkout`, calls Order Service via `httpx` | 8000 |
| `order_service.py` | Downstream service — zero-code, simulates order processing | 8001 |
| `order_service_custom.py` | Downstream service — custom spans (`check_inventory`, `insert_order_record`) + log correlation | 8001 |

## Quick Start

1. **Start Jaeger:**
   ```bash
   make infra-up
   ```

2. **Start both services** (in separate terminals):
   ```bash
   # Terminal 1: Order Service (zero-code)
   make run-order

   # Terminal 2: API Gateway
   make run-gateway
   ```

3. **Send a request:**
   ```bash
   make run-request
   ```

4. **View the distributed trace:**
   Open [http://localhost:16686](http://localhost:16686), select `api-gateway`, and click **Find Traces**. You will see a single trace with spans from **both** `api-gateway` and `order-service`.

## Upgrading to Custom Spans

Stop the Order Service and restart with custom spans:

```bash
# Terminal 1 (restart)
make run-order-custom
```

Now send another request (`make run-request`). In Jaeger, the `order-service` spans will break down into `check_inventory` (300ms) and `insert_order_record` (1.5s), making the slow DB insert immediately obvious.

## Service Names in Jaeger

- `api-gateway`
- `order-service`
