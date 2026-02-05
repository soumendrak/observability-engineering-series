# Chapter 3: OpenTelemetry

.PHONY: help run-zero run-medium run-custom infra-up infra-down

help:
	@echo "Available commands:"
	@echo "  run-zero     - Run Zero-Code instrumentation (Port 8000)"
	@echo "  run-medium   - Run Medium-Code instrumentation (Port 8001)"
	@echo "  run-custom   - Run Custom-Code instrumentation (Port 8002)"
	@echo "  infra-up     - Start Jaeger (Docker)"
	@echo "  infra-down   - Stop Jaeger"

run-zero:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--service_name zero-code-service \
		python 01_zero_code.py

run-medium:
	uv run 02_medium_code.py

run-custom:
	uv run 03_custom_code.py

infra-up:
	docker-compose up -d

infra-down:
	docker-compose down
