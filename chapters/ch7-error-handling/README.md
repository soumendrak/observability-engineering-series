# Chapter 7: Error Handling & Semantic Instrumentation

This chapter makes every failure visible to your observability stack by applying OpenTelemetry's semantic error-recording APIs (`span.record_exception()` and `span.set_status(ERROR)`) alongside business-context span attributes and combined three-pillar error emission.

## What Changed from Chapter 6

| Aspect | Chapter 6 | Chapter 7 |
|--------|-----------|-----------|
| Error recording | Unhandled exceptions only | All three error patterns (propagate / catch-and-record / catch-and-continue) |
| Span on failure | Status `UNSET`, no events | Status `ERROR` + exception Events with full stack trace |
| Business context | `order.item`, `order.qty` on success | Same attributes set **before** the operation — present even on failure |
| Error metrics | `gateway.order_service.errors.total` | Adds `orders.errors.total` with `error.type` + `operation` labels |
| External calls | Bare `httpx` call | `call_external_api()` wrapper — auto-instruments any external dependency |
| Pattern 3 (recovery) | Not demonstrated | `/products/{id}` — DB fails → cache fallback, span stays green |
| Pattern 1 (propagate) | Not demonstrated | `/health` — unhandled `RuntimeError`, OTel auto-instruments it |
| New endpoint | — | `GET /products/{product_id}` on both gateway and order service |

**Same base**: Two-service architecture (API Gateway + Order Service), Jaeger for traces, Prometheus for metrics, `opentelemetry-instrument` CLI, `logging_setup.py` with Loguru + OTel JSON correlation.

## Files

| File | Description | Port |
|------|-------------|------|
| `logging_setup.py` | Shared Loguru setup with OTel correlation (identical to ch6) | — |
| `order_service.py` | Order Service — all three error patterns, `call_external_api` wrapper, product endpoint | 8001 |
| `api_gateway.py` | API Gateway — semantic error recording on proxy calls, product proxy endpoint | 8000 |
| `docker-compose.yml` | Jaeger + Prometheus infrastructure (identical to ch6) | — |
| `prometheus.yml` | Prometheus scrape config (identical to ch6) | — |

## Quick Start

1. **Start infrastructure (Jaeger + Prometheus):**
   ```bash
   make infra-up
   ```

2. **Start both services** (in separate terminals):
   ```bash
   # Terminal 1: Order Service
   make run-order

   # Terminal 2: API Gateway
   make run-gateway
   ```

3. **Generate mixed traffic** (successes + failures):
   ```bash
   make run-error-traffic
   ```

## Observing the Three Error Patterns

### Pattern 1 — Let It Propagate (`/health`)

```bash
# Hit the endpoint a few times (20% chance of RuntimeError)
for i in $(seq 1 10); do curl -s http://localhost:8001/health; echo; done
```

In Jaeger, search for service `order-service`, operation `GET /health`. Failing requests show:
- Span status: **ERROR** (set automatically by the FastAPI instrumentor)
- Events: `exception` with `exception.type: "RuntimeError"` and full stack trace

### Pattern 2 — Catch and Record (`POST /orders`)

```bash
make run-traffic   # 20 checkout requests, ~35% fail at DB or payment layer
```

In Jaeger, search for `order-service`, operation `insert_order_record`:
- **Red spans** (ERROR): include `order.item`, `order.qty`, `order.total_usd` attributes and an `exception` event
- **Green spans** (OK): include the same business attributes plus `order.id` and `payment.charge_id`

In Prometheus (`http://localhost:9090`):
```promql
# Error rate by operation
rate(orders_errors_total[5m])

# Sum by error type
sum by (error_type, operation) (orders_errors_total)
```

### Pattern 3 — Catch and Continue (`GET /products/{product_id}`)

```bash
for i in $(seq 1 10); do curl -s http://localhost:8000/products/widget-1; echo; done
```

In Jaeger, search for `order-service`, operation `fetch_product`:
- **All spans are green** (OK) — because the fallback succeeded
- Spans that hit a DB failure carry:
  - An `exception` Event (`exception.type: "DatabaseError"`, stack trace)
  - A `cache_fallback` Event (`reason: "...", fallback_source: "redis"`)
  - `product.source: "cache"` attribute
- Spans that hit the DB successfully show `product.source: "db"` — no exception events

### Checking External API Spans

When an order succeeds but the payment call fails, you'll see nested spans in the Jaeger waterfall:

```
POST /orders [ERROR]
  └── check_inventory [OK]
  └── insert_order_record [ERROR]
        └── external.stripe.charge [ERROR]
              external.service: "stripe"
              external.operation: "charge"
              external.status: "error"
              external.error_type: "ConnectionError"
              external.duration_ms: 214.3
```

## Key Concepts

| Concept | API | Effect in Jaeger |
|---------|-----|------------------|
| Record exception | `span.record_exception(e)` | Adds an `exception` Event with type, message, and stack trace |
| Mark span failed | `span.set_status(StatusCode.ERROR, msg)` | Span turns **red** in the waterfall |
| Record without failing | `span.record_exception(e)` (no `set_status`) | Exception visible in Events, span stays **green** |
| Recovery event | `span.add_event("cache_fallback", {...})` | Named event visible in Jaeger's span detail |
| Business context | `span.set_attribute("order.total_usd", 49.98)` | Always present — even on the failing span |
| External call span | `SpanKind.CLIENT` + `external.*` attributes | Separate child span for every external dependency |
