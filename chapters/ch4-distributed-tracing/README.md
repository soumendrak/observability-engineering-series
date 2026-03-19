# Chapter 4: Distributed Tracing

In Chapter 3, we traced a single service. In this chapter, we trace one request across two services:

- `api-gateway` receives `/checkout`
- `order-service` receives `/orders`

OpenTelemetry propagates the same `trace_id` across the network using the `traceparent` header, so Jaeger renders one connected trace.

## Files

| File | Purpose |
|------|---------|
| `api_gateway.py` | API Gateway with zero-code propagation (`httpx` instrumentation handles inject) |
| `order_service.py` | Order Service with zero-code propagation (FastAPI instrumentation handles extract) |
| `api_gateway_manual.py` | Manual caller propagation (`propagate.inject`) |
| `order_service_manual.py` | Manual receiver propagation (`propagate.extract`) |
| `order_service_custom.py` | Order Service with custom spans (`check_inventory`, `insert_order_record`) |

## Run: Zero-Code Distributed Tracing

1. Start Jaeger:

```bash
make infra-up
```

2. Start services in two terminals:

```bash
# Terminal 1
make run-order

# Terminal 2
make run-gateway
```

3. Fire a request:

```bash
make run-request
```

4. Open Jaeger at [http://localhost:16686](http://localhost:16686), select `api-gateway`, and click **Find Traces**.

You should see one trace containing spans from both `api-gateway` and `order-service`.

## Under the Hood: Manual Context Propagation

This chapter now includes a fully manual flow for learning.

### Caller Side (`api_gateway_manual.py`)

- Starts a span: `GET /checkout (manual)`
- Creates a header carrier (`headers = {}`)
- Injects active context with `propagate.inject(headers)`
- Sends headers on outbound `httpx` call

### Receiver Side (`order_service_manual.py`)

- Builds carrier from incoming headers (`dict(request.headers)`)
- Extracts parent context with `propagate.extract(carrier)`
- Starts child span using extracted context: `POST /orders (manual)`

### Run manual mode

```bash
# Terminal 1
make run-order-manual

# Terminal 2
make run-gateway-manual

# Terminal 3
make run-request
```

This completes the explicit inject/extract propagation loop while preserving a shared `trace_id` across both services.

## Add Custom Business Spans

To see granular work inside `order-service`, run:

```bash
make run-order-custom
```

Then send `make run-request`. Jaeger will show:

- `check_inventory` (~300ms)
- `insert_order_record` (~1.5s)

## Dependencies

This chapter uses:

- `fastapi`
- `uvicorn`
- `httpx`
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-instrumentation-httpx`
- `loguru`

## Unit Tests and Coverage

- Unit tests are in `tests/test_api_gateway_manual.py` and `tests/test_order_service_manual.py`.
- Run tests:

```bash
make test
```

- Run coverage:

```bash
make coverage
```
