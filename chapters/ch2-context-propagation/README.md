# Chapter 2: Context Propagation

This chapter demonstrates how to solve the "missing trace ID" problem in asyncio applications using Python's `contextvars` module.

## Files

- `initial.py`: A script demonstrating the **problem** with global state in asyncio. It shows how concurrent requests can corrupt a shared `request_id` variable.
- `final.py`: A script using `contextvars` to properly propagate context. It includes automatic context injection into Loguru logs and proper thread pool handling.

## Usage

Make sure you are in the root of the repository or inside this directory. The commands below assume you are in the repository root.

### Prerequisites

Install dependencies using `uv`:

```bash
uv sync
```

### Running the Examples

**1. The "Before" State (Broken Context)**

Run `initial.py` to see the problem with global state:

```bash
uv run chapters/ch2-context-propagation/initial.py
```

Output (notice the `CONTEXT MISMATCH` errors):
```text
{"text": "... | ERROR | Finished request - CONTEXT MISMATCH", "record": {"extra": {"expected_id": "req-0", "actual_global_id": "req-4"}, ...}}
```

**2. The "After" State (Proper Context Propagation)**

Run `final.py` to see proper context handling:

```bash
uv run chapters/ch2-context-propagation/final.py
```

### Environment Variables

The `final.py` script uses the `ENV` environment variable to toggle between human-readable logs (for development) and serialized JSON logs (for production).

**Development Mode (Pretty-printed)**
Best for local debugging.

```bash
ENV=DEV uv run chapters/ch2-context-propagation/final.py
```

**Production Mode (JSON)**
Best for shipping logs to observability backends (Datadog, Loki, etc.).

```bash
ENV=PROD uv run chapters/ch2-context-propagation/final.py
```

Output (formatted):
```json
{
  "record": {
    "level": {"name": "INFO"},
    "message": "Processing image in thread",
    "extra": {"thread_context_id": "req-3", "request_id": "req-3"},
    "thread": {"name": "asyncio_0"}
  }
}
```

Notice how the `request_id` is automatically injected into every log message, even inside thread pools.
