# Chapter 3: Automatic Tracing with OpenTelemetry

This chapter demonstrates the three levels of OpenTelemetry instrumentation.

## Files

| File | Description | Port |
|------|-------------|------|
| `01_zero_code.py` | Zero-code instrumentation via OTel agent | 8000 |
| `02_medium_code.py` | Programmatic instrumentation | 8001 |
| `03_custom_code.py` | Manual spans + log correlation | 8002 |

## Quick Start

1. Start Jaeger:
   ```bash
   make infra-up
   ```

2. Run any example:
   ```bash
   make run-zero    # Zero-Code (Port 8000)
   make run-medium  # Medium-Code (Port 8001)
   make run-custom  # Custom-Code (Port 8002)
   ```

3. Open [http://localhost:16686](http://localhost:16686) to view traces in Jaeger.

## Service Names in Jaeger

Each example appears as a separate service:
- `zero-code-service`
- `medium-code-service`
- `custom-code-service`
