import asyncio
import os
import sys
from fastapi import FastAPI
import uvicorn
import httpx
from dotenv import load_dotenv
load_dotenv()

# OTel Imports
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# 1. Programmatic Setup (Medium-Code)
resource = Resource.create({
    "service.name": "medium-code-service",
    "instrumentation.level": "medium"
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

app = FastAPI()

# 2. Explicitly instrument the app and libraries
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

@app.get("/")
async def root():
    async with httpx.AsyncClient() as client:
        await client.get("https://www.soumendrak.com")
    return {"message": "Medium-code instrumentation works!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
