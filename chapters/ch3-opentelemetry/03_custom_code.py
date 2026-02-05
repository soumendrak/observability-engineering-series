import asyncio
import os
import sys
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from loguru import logger
from dotenv import load_dotenv
load_dotenv()

# OTel Imports
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# 1. Setup OTel Provider
resource = Resource.create({
    "service.name": "custom-code-service",
    "instrumentation.level": "custom"
})
provider = TracerProvider(resource=resource)

# Export to OTLP if configured, otherwise Console
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    is_insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "false").lower() == "true"
    
    # Simple logic: If port ends in 18 or 20, use HTTP. Otherwise gRPC.
    if otlp_endpoint.endswith(":4318") or otlp_endpoint.endswith(":4320"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces" if "/v1/traces" not in otlp_endpoint else otlp_endpoint)
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=is_insecure)
else:
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    exporter = ConsoleSpanExporter()

processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# 2. Loguru Trace ID Patching (Custom-Code)
def otel_patcher(record):
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        # Inject IDs into the 'extra' dict for Loguru
        record["extra"]["trace_id"] = format(ctx.trace_id, "032x")
        record["extra"]["span_id"] = format(ctx.span_id, "016x")

logger.configure(patcher=otel_patcher)

# Production pattern from Ch1/Ch2
if os.getenv("ENV") == "PROD":
    logger.remove()
    logger.add(sys.stdout, serialize=True)

app = FastAPI()

async def check_inventory(item_id: str):
    # 3. Manual Instrumentation (Custom Span)
    with tracer.start_as_current_span("inventory_check") as span:
        span.set_attribute("item.id", item_id)
        
        await asyncio.sleep(random.uniform(0.05, 0.1))
        
        # Log will now have trace_id from the span!
        logger.info(f"Inventory check for {item_id}")
        
        span.add_event("inventory_verified")
        return True

@app.get("/")
async def root():
    logger.info("Custom instrumentation root request")
    return HTMLResponse("""
        <h1>Custom instrumentation works!</h1>
        <p>Try the custom span: <a href="/items/123">/items/123</a></p>
    """)

@app.get("/items/{item_id}")
async def get_item(item_id: str):
    logger.info("Handling request")
    await check_inventory(item_id)
    return {"status": "success", "item_id": item_id}

FastAPIInstrumentor.instrument_app(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
