from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from loguru import logger
from opentelemetry import trace

if TYPE_CHECKING:
    from loguru import Logger, Message, Record


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


def setup_logging(service_name: str) -> Logger:
    def json_sink(message: Message) -> None:
        record = message.record
        entry = {
            "timestamp": record["time"].isoformat(timespec="milliseconds"),
            "level": record["level"].name,
            "service": service_name,
            "message": record["message"],
            **record["extra"],
        }
        sys.stdout.write(json.dumps(entry, default=str) + "\n")

    logger.remove()
    logger.configure(patcher=otel_patcher)
    logger.add(json_sink, level="INFO")
    return logger
