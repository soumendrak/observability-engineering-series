# Chapter 1: Structured Logging

This chapter demonstrates the transition from standard text-based logging to structured JSON logging using `loguru`.

## Files

- `initial.py`: A script using Python's standard `logging` module. It produces unstructured text logs, which are hard to query programmatically.
- `final.py`: A script using `loguru` to produce structured JSON logs. This enables "observability as code" by making logs queryable like a database.

## Usage

Make sure you are in the root of the repository or inside this directory. The commands below assume you are in the repository root.

### Prerequisites

Install dependencies using `uv`:

```bash
uv sync
```

### Running the Examples

**1. The "Before" State (Text Logs)**

Run `initial.py` to see standard text logging:

```bash
uv run chapters/ch1-structured-logging/initial.py
```

Output:
```text
2026-01-21 10:00:01 WARNING:root:User 123 failed to login with error: invalid_password
```

**2. The "After" State (Structured Logs)**

Run `final.py` to see structured logging. By default, it may run in development mode (pretty-printed) or production mode depending on your configuration.

```bash
uv run chapters/ch1-structured-logging/final.py
```

### Environment Variables

The `final.py` script uses the `ENV` environment variable to toggle between human-readable logs (for development) and serialized JSON logs (for production).

**Development Mode (Pretty-printed)**
Best for local debugging.

```bash
ENV=DEV uv run chapters/ch1-structured-logging/final.py
```

**Production Mode (JSON)**
Best for shipping logs to observability backends (Datadog, Loki, etc.).

```bash
ENV=PROD uv run chapters/ch1-structured-logging/final.py
```

Output (formatted):
```json
{
  "record": {
    "level": {"name": "WARNING", "no": 30},
    "message": "user_login_failed",
    "extra": {"user_id": 123, "error_type": "invalid_password"},
    "time": {"timestamp": 1737482500.123}
  }
}
```
