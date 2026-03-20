# Chapter 8: OTel Collector Pipeline

Route all telemetry (traces, metrics, logs) through the OpenTelemetry Collector instead of exporting directly to backends. Two configurations are provided: **MVP** for getting started and **Production** for hardened deployments.

## What Changed from Chapter 7

| Aspect | Chapter 7 | Chapter 8 |
|--------|-----------|-----------|
| Traces | App → Jaeger directly via OTLP | App → Collector → Jaeger |
| Metrics | App exposes `/metrics` for Prometheus to scrape | App pushes OTLP → Collector exposes `/metrics` |
| Logs | App → stdout only | App pushes OTLP → Collector `debug` exporter |
| App config | One endpoint per signal per backend | One endpoint for everything: `localhost:4317` |
| Dependencies | `prometheus_client`, `opentelemetry-exporter-prometheus` | Removed — all metrics are OTel-native via OTLP |
| `/metrics` endpoint | Exposed by each service | Removed — Collector owns the Prometheus translation |

**Same base**: Two-service architecture (API Gateway + Order Service), error handling patterns from ch7, Loguru + OTel JSON correlation.

## File Structure

```
ch8-otel-collector/
├── api_gateway.py                    # API Gateway (shared by both configs)
├── order_service.py                  # Order Service (shared by both configs)
├── logging_setup.py                  # Loguru + OTel correlation (identical to ch7)
├── pyproject.toml                    # Dependencies (no more prometheus_client)
├── Makefile                          # All commands for both MVP and Production
├── mvp/
│   ├── otel-collector-config.yaml    # Minimum viable Collector config
│   ├── docker-compose.yml            # Collector + Jaeger + Prometheus (:latest)
│   └── prometheus.yml                # Scrapes Collector at :8889
└── production/
    ├── otel-collector-config.yaml    # Hardened: health check, filters, queues
    ├── docker-compose.yml            # Pinned versions, health checks, depends_on
    └── prometheus.yml                # Scrapes Collector app metrics + internal metrics
```

## Quick Start — MVP (Part 2)

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Start infrastructure:**
   ```bash
   make mvp-infra-up
   ```

3. **Start both services** (in separate terminals):
   ```bash
   # Terminal 1: Order Service
   make run-order

   # Terminal 2: API Gateway
   make run-gateway
   ```

4. **Generate traffic:**
   ```bash
   make run-traffic
   ```

5. **Verify the pipeline:**
   - Collector logs: `make mvp-logs` (look for `ScopeSpans` entries)
   - Jaeger: [http://localhost:16686](http://localhost:16686)
   - Prometheus: [http://localhost:9090](http://localhost:9090) → query `otel_gateway_requests_total`

6. **Tear down:**
   ```bash
   make mvp-infra-down
   ```

## Quick Start — Production (Part 3)

1. **Validate the Collector config:**
   ```bash
   make prod-validate
   ```

2. **Start infrastructure:**
   ```bash
   make prod-infra-up
   ```

3. **Start services** (same commands as MVP):
   ```bash
   make run-order    # Terminal 1
   make run-gateway  # Terminal 2
   ```

4. **Verify health check:**
   ```bash
   curl http://localhost:13133
   # {"status":"Server available","upSince":"..."}
   ```

5. **Verify self-observability:**
   - Collector internal metrics: [http://localhost:8888/metrics](http://localhost:8888/metrics)
   - In Prometheus: query `otelcol_exporter_sent_spans_total`

6. **Tear down:**
   ```bash
   make prod-infra-down
   ```

## MVP vs Production — What's Different

| Feature | MVP | Production |
|---------|-----|------------|
| Image tags | `:latest` | Pinned (`0.120.0`, `1.62.0`, `v2.51.0`) |
| `debug` exporter | `verbosity: detailed` | `verbosity: basic` (or remove) |
| `batch.timeout` | `5s` (demo-friendly) | `200ms` (near-real-time) |
| Health check | None | `:13133` with Docker healthcheck |
| Self-observability | Not configured | Internal metrics at `:8888`, telemetry config |
| `filter` processor | Not present | Drops `/health`, `/healthz`, `/readyz` spans |
| `attributes` processor | Not present | Stamps `deployment.environment=dev` on all spans |
| Sending queue | Default (1000 batches) | `queue_size: 5000`, `max_elapsed_time: 10m` |
| `depends_on` | None | Prometheus waits for Collector health |
| Prometheus scrape | App metrics only (`:8889`) | App metrics (`:8889`) + Collector metrics (`:8888`) |

## Verification Checklist

After starting either stack, verify in order:

1. **Collector ready**: `make verify-collector`
2. **Spans flowing**: `make run-request` then check `make mvp-logs` / `make prod-logs`
3. **Jaeger traces**: `make verify-jaeger` → open link, select service, search
4. **Prometheus UP**: `make verify-prometheus` → open targets link
5. **Query a metric**: In Prometheus, run `otel_gateway_requests_total`

## Prometheus Queries

With the `otel` namespace prefix set in the Collector's Prometheus exporter:

```promql
# Total gateway requests
otel_gateway_requests_total

# Total orders created
otel_orders_created_total

# Error rate by error type
rate(otel_orders_errors_total[5m])

# Request duration (histogram)
histogram_quantile(0.95, rate(otel_gateway_request_duration_bucket[5m]))
```

For production self-observability (Collector internal metrics):

```promql
# Spans received vs exported
otelcol_receiver_accepted_spans_total
otelcol_exporter_sent_spans_total

# Queue depth (growing = backend slower than ingestion)
otelcol_exporter_queue_size

# Export failures
otelcol_exporter_send_failed_spans_total
```

## Architecture

```
┌─────────────┐     OTLP      ┌──────────────────┐    OTLP     ┌─────────┐
│ API Gateway │───────────────▶│                  │────────────▶│ Jaeger  │
│  :8000      │                │  OTel Collector  │             │ :16686  │
└─────────────┘                │  :4317 (gRPC)    │             └─────────┘
                               │  :4318 (HTTP)    │
┌─────────────┐     OTLP      │  :8889 (metrics) │  scrape     ┌────────────┐
│ Order Svc   │───────────────▶│  :8888 (internal)│◀────────────│ Prometheus │
│  :8001      │                │  :13133 (health) │             │ :9090      │
└─────────────┘                └──────────────────┘             └────────────┘
```
