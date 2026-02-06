# Chapter 4: Distributed Tracing

.PHONY: help run-order run-order-custom run-gateway run-request infra-up infra-down

help:
	@echo "Available commands:"
	@echo "  run-order        - Start Order Service, zero-code (Port 8001)"
	@echo "  run-order-custom - Start Order Service with custom spans (Port 8001)"
	@echo "  run-gateway      - Start API Gateway, zero-code (Port 8000)"
	@echo "  run-request      - Send a checkout request to the gateway"
	@echo "  infra-up         - Start Jaeger (Docker)"
	@echo "  infra-down       - Stop Jaeger"

run-order:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--exporter_otlp_endpoint http://localhost:4317 \
		--service_name order-service \
		uvicorn order_service:app --port 8001

run-order-custom:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--exporter_otlp_endpoint http://localhost:4317 \
		--service_name order-service \
		uvicorn order_service_custom:app --port 8001

run-gateway:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--exporter_otlp_endpoint http://localhost:4317 \
		--service_name api-gateway \
		uvicorn api_gateway:app --port 8000

run-request:
	curl -s http://localhost:8000/checkout | python -m json.tool

infra-up:
	docker-compose up -d

infra-down:
	docker-compose down
