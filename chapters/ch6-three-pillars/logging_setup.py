# logging_setup.py
import sys
from opentelemetry import trace
from loguru import logger


def otel_patcher(record):
    """Inject OTel context into every log record."""
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        record["extra"]["trace_id"] = format(ctx.trace_id, "032x")
        record["extra"]["span_id"] = format(ctx.span_id, "016x")
        record["extra"]["span_name"] = span.name
    else:
        record["extra"]["trace_id"] = "00000000000000000000000000000000"
        record["extra"]["span_id"] = "0000000000000000"
        record["extra"]["span_name"] = ""


def setup_logging(service_name: str):
    """Configure Loguru for production with OTel correlation."""
    logger.remove()
    logger.configure(patcher=otel_patcher)

    # JSON format for production
    log_format = (
        '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSSZ}", '
        '"level": "{level.name}", '
        '"service": "' + service_name + '", '
        '"message": "{message}", '
        '"trace_id": "{extra[trace_id]}", '
        '"span_id": "{extra[span_id]}", '
        '"span_name": "{extra[span_name]}"}}'
    )

    logger.add(sys.stdout, format=log_format, level="INFO")
    return logger
