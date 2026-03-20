# Observability Engineering Series

Code examples and practical implementations for the blog series **"Practical Observability with Python"**, based on concepts from the book *Observability Engineering* by Charity Majors, Liz Fong-Jones, and George Miranda.

## Prerequisites

- Python 3.13+
- `uv` for dependency management

## Chapter 1: Structured Logging
*Status: Complete*

Moving from "grep-based debugging" to "query-based observability" using structured logging.

- **Location:** `chapters/ch1-structured-logging/`
- **Key Concepts:**
    - The limitations of standard text logs.
    - Implementing structured JSON logging with `loguru`.
    - Context binding for queryable logs.

For detailed usage instructions, including how to run the examples and configure environment variables, please refer to the [Chapter 1 README](chapters/ch1-structured-logging/README.md).

## Chapter 2: Context Propagation
*Status: Complete*

Correlating logs across a request lifecycle using context propagation.

- **Location:** `chapters/ch2-context-propagation/`
- **Key Concepts:**
    - Propagating request context through function calls.
    - Correlation IDs for tracing a request across log lines.

For detailed usage instructions, please refer to the [Chapter 2 README](chapters/ch2-context-propagation/README.md).

## Chapter 3: OpenTelemetry Tracing
*Status: Complete*

Automatic tracing with OpenTelemetry — three levels of instrumentation within a single service.

- **Location:** `chapters/ch3-opentelemetry/`
- **Key Concepts:**
    - Zero-code, medium-code, and custom instrumentation.
    - Exporting traces to Jaeger via OTLP.
    - Loguru + OTel trace ID patching for log correlation.

For detailed usage instructions, please refer to the [Chapter 3 README](chapters/ch3-opentelemetry/README.md).

## Chapter 4: Distributed Tracing
*Status: Complete*

Following a request across service boundaries — from single-service tracing to distributed tracing.

- **Location:** `chapters/ch4-distributed-tracing/`
- **Key Concepts:**
    - W3C Trace Context and the `traceparent` header.
    - Automatic context propagation via `httpx` instrumentation.
    - Manual context propagation with explicit inject/extract flow.
    - Two-service setup: API Gateway → Order Service.
    - Custom spans for fine-grained visibility across services.

For detailed usage instructions, please refer to the [Chapter 4 README](chapters/ch4-distributed-tracing/README.md).

## Chapter 5: Custom Metrics
*Status: Complete*

Adding custom metrics with the OpenTelemetry Metrics API and Prometheus as the backend.

- **Location:** `chapters/ch5-metrics/`
- **Key Concepts:**
    - OTel instrument types: Counter, Histogram, Observable Gauge.
    - `PrometheusMetricReader` exposing `/metrics` for Prometheus scraping.
    - Middleware recording per-request metrics with low-cardinality attributes.
    - Infrastructure: Jaeger (traces) + Prometheus (metrics).

For detailed usage instructions, please refer to the [Chapter 5 README](chapters/ch5-metrics/README.md).

## Chapter 6: Three Pillars Connected
*Status: Complete*

Correlating all three telemetry signals — logs, traces, and metrics — via the pivot workflow.

- **Location:** `chapters/ch6-three-pillars/`
- **Key Concepts:**
    - Replacing stdlib `logging` with Loguru + OTel patcher for trace correlation.
    - Structured JSON logs with `trace_id`, `span_id`, `span_name`.
    - Metric exemplars linking Prometheus metrics to specific traces.
    - The pivot workflow: Metrics → Traces → Logs.

For detailed usage instructions, please refer to the [Chapter 6 README](chapters/ch6-three-pillars/README.md).

## Chapter 7: Error Handling & Semantic Instrumentation
*Status: Complete*

Three error-handling patterns for production observability — propagate, catch-and-record, catch-and-continue.

- **Location:** `chapters/ch7-error-handling/`
- **Key Concepts:**
    - `span.record_exception()` + `span.set_status(ERROR)` for semantic error recording.
    - Business-context span attributes set before the operation (present even on failure).
    - `call_external_api()` wrapper auto-instrumenting external dependencies.
    - DB-fail → cache-fallback recovery pattern (`/products/{id}`).

For detailed usage instructions, please refer to the [Chapter 7 README](chapters/ch7-error-handling/README.md).

## Chapter 8: OTel Collector Pipeline
*Status: Complete*

Routing all telemetry through the OpenTelemetry Collector instead of exporting directly to backends.

- **Location:** `chapters/ch8-otel-collector/`
- **Key Concepts:**
    - App → Collector → backends (Jaeger, Prometheus) instead of direct export.
    - Single OTLP endpoint (`localhost:4317`) for all signals.
    - Removing `prometheus_client` — metrics are OTel-native via OTLP.
    - Two configurations: MVP (getting started) and Production (hardened).

For detailed usage instructions, please refer to the [Chapter 8 README](chapters/ch8-otel-collector/README.md).

## Chapter 9: Sampling & PII Scrubbing
*Status: Complete*

Keeping 100% of error traces while sampling successes, and redacting sensitive data before telemetry leaves your infrastructure.

- **Location:** `chapters/ch9-sampling-pii/`
- **Key Concepts:**
    - Tail sampling: 100% errors, 100% slow traces, 5% normal traces.
    - PII scrubbing via `transform` processor: redacts `llm.prompt`, `llm.completion`, emails, SSNs.
    - Processor ordering: `transform` → `tail_sampling` → `batch`.
    - GenAI-style `/ask` endpoint demonstrating PII in span attributes.

For detailed usage instructions, please refer to the [Chapter 9 README](chapters/ch9-sampling-pii/README.md).
