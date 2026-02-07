# Chapter 5: Custom Metrics with OpenTelemetry

.PHONY: help run-order run-gateway run-request run-traffic infra-up infra-down

help:
	@echo "Available commands:"
	@echo "  run-order    - Start Order Service with metrics (Port 8001)"
	@echo "  run-gateway  - Start API Gateway with metrics (Port 8000)"
	@echo "  run-request  - Send a single checkout request"
	@echo "  run-traffic  - Send 20 requests to generate metric data"
	@echo "  infra-up     - Start Jaeger + Prometheus (Docker)"
	@echo "  infra-down   - Stop Jaeger + Prometheus"

run-order:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--metrics_exporter none \
		--exporter_otlp_endpoint http://localhost:4317 \
		--service_name order-service \
		uvicorn order_service:app --port 8001

run-gateway:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--metrics_exporter none \
		--exporter_otlp_endpoint http://localhost:4317 \
		--service_name api-gateway \
		uvicorn api_gateway:app --port 8000

run-request:
	curl -s http://localhost:8000/checkout | python -m json.tool

run-traffic:
	@echo "Sending 20 requests..."
	@for i in $$(seq 1 20); do curl -s http://localhost:8000/checkout > /dev/null; done
	@echo "Done. Check Prometheus at http://localhost:9090"

infra-up:
	docker-compose up -d

infra-down:
	docker-compose down
