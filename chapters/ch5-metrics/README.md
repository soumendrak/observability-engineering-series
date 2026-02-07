# Chapter 5: Custom Metrics with OpenTelemetry

This chapter extends the distributed tracing setup from Chapter 4 with **custom metrics** using OpenTelemetry's Metrics API and a Prometheus backend.

## What Changed from Chapter 4

| Aspect | Chapter 4 | Chapter 5 |
|--------|-----------|-----------|
| Observability pillar | Traces only | Traces + Metrics |
| Metric instruments | None | Counter, Histogram (+ Observable Gauge example) |
| Infrastructure | Jaeger | Jaeger + Prometheus |
| Exporter | OTLP (traces) | OTLP (traces) + Prometheus (metrics) |
| Key concept | Distributed trace propagation | Custom metrics, cardinality, instrument selection |

**Same base**: Two-service architecture (API Gateway + Order Service), Jaeger for traces, `opentelemetry-instrument` CLI.

**New patterns**:
- `PrometheusMetricReader` exposes a `/metrics` endpoint that Prometheus scrapes.
- Counters track request totals and errors.
- Histograms track request duration and order processing time.
- Middleware automatically records per-request metrics with low-cardinality attributes.

## Files

| File | Description | Port |
|------|-------------|------|
| `api_gateway.py` | Upstream service — metrics middleware (request counter + duration histogram) + error counter | 8000 |
| `order_service.py` | Downstream service — business metrics (orders created, processing duration, inventory check duration) + custom spans | 8001 |
| `docker-compose.yml` | Jaeger + Prometheus infrastructure | — |
| `prometheus.yml` | Prometheus scrape configuration for both services | — |

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

3. **Send a request:**
   ```bash
   make run-request
   ```

4. **Generate traffic for meaningful metrics:**
   ```bash
   make run-traffic
   ```

5. **View metrics in Prometheus:**
   Open [http://localhost:9090](http://localhost:9090) and try these queries:

   ```promql
   # Total requests to the gateway
   gateway_requests_total

   # Average request duration over the last 5 minutes
   rate(gateway_request_duration_milliseconds_sum[5m]) / rate(gateway_request_duration_milliseconds_count[5m])

   # P99 request duration
   histogram_quantile(0.99, rate(gateway_request_duration_milliseconds_bucket[5m]))

   # Orders created per second
   rate(orders_created_total[1m])
   ```

6. **View distributed traces in Jaeger:**
   Open [http://localhost:16686](http://localhost:16686), select `api-gateway`, and click **Find Traces**.

## Metric Instruments Used

| Instrument | Metric Name | Service | Purpose |
|------------|-------------|---------|---------|
| Counter | `gateway.requests.total` | API Gateway | Total HTTP requests |
| Histogram | `gateway.request.duration` | API Gateway | Request latency distribution |
| Counter | `gateway.order_service.errors.total` | API Gateway | Downstream call failures |
| Counter | `orders.created.total` | Order Service | Orders successfully created |
| Histogram | `orders.processing.duration` | Order Service | End-to-end order processing time |
| Histogram | `orders.inventory_check.duration` | Order Service | Inventory check latency |

## Service Names

- `api-gateway` (traces in Jaeger)
- `order-service` (traces in Jaeger)
