from __future__ import annotations

import json
import sys
import traceback
from typing import TYPE_CHECKING

from loguru import logger
from opentelemetry import trace

if TYPE_CHECKING:
    from loguru import Logger, Message, Record

RESERVED_KEYS = frozenset({"timestamp", "level", "service", "message", "exception"})


def otel_patcher(record: Record) -> None:
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        record["extra"]["trace_id"] = format(ctx.trace_id, "032x")
        record["extra"]["span_id"] = format(ctx.span_id, "016x")
        record["extra"]["span_name"] = getattr(span, "name", "")
    else:
        record["extra"]["trace_id"] = "00000000000000000000000000000000"
        record["extra"]["span_id"] = "0000000000000000"
        record["extra"]["span_name"] = ""


def exception_fields(record: Record) -> dict[str, dict[str, str]]:
    exception = record["exception"]
    if exception is None or exception.value is None:
        return {}
    return {
        "exception": {
            "type": type(exception.value).__name__,
            "value": str(exception.value),
            "traceback": "".join(traceback.format_exception(exception.value)),
        }
    }


def setup_logging(service_name: str) -> Logger:
    def json_sink(message: Message) -> None:
        record = message.record
        reserved = {
            "timestamp": record["time"].isoformat(timespec="milliseconds"),
            "level": record["level"].name,
            "service": service_name,
            "message": record["message"],
            **exception_fields(record),
        }
        extra = {
            key: value
            for key, value in record["extra"].items()
            if key not in RESERVED_KEYS
        }
        entry = {**reserved, **extra}
        sys.stdout.write(json.dumps(entry, default=str) + "\n")
        sys.stdout.flush()

    logger.remove()
    logger.configure(patcher=otel_patcher)
    logger.add(json_sink, level="INFO")
    return logger
