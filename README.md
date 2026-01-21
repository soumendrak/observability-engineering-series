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

### Files
- `initial.py`: Demonstrates the problem with standard unstructured logging.
- `final.py`: Demonstrates the solution using structured logging (JSON) with `loguru`.

### Usage
Navigate to the repository root and use `uv` to run the examples.

```bash
# Install dependencies
uv sync

# Run the 'before' example
uv run chapters/ch1-structured-logging/initial.py

# Run the 'after' example (structured logging)
uv run chapters/ch1-structured-logging/final.py
```

### Environment Variables
For `final.py` in Chapter 1, you can toggle production mode (JSON serialization) using the `ENV` variable.

```bash
# Development mode (pretty printing)
ENV=DEV uv run chapters/ch1-structured-logging/final.py

# Production mode (JSON serialization)
ENV=PROD uv run chapters/ch1-structured-logging/final.py
```

## Chapter 2: Context Propagation
*Status: Planned*

(Content to be added...)
