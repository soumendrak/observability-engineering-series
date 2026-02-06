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
    - Two-service setup: API Gateway → Order Service.
    - Custom spans for fine-grained visibility across services.

For detailed usage instructions, please refer to the [Chapter 4 README](chapters/ch4-distributed-tracing/README.md).
