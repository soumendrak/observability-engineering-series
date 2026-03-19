# Chapter 7: Error Handling & Semantic Instrumentation

.PHONY: help run-order run-gateway run-request run-products run-traffic run-error-traffic infra-up infra-down

help:
	@echo "Available commands:"
	@echo "  run-order          - Start Order Service (Port 8001)"
	@echo "  run-gateway        - Start API Gateway (Port 8000)"
	@echo "  run-request        - Send a single checkout request"
	@echo "  run-products       - Send a single product fetch request"
	@echo "  run-traffic        - Send 20 checkout requests (mix of success & error)"
	@echo "  run-error-traffic  - Send mixed checkout + product requests (30 total)"
	@echo "  infra-up           - Start Jaeger + Prometheus (Docker)"
	@echo "  infra-down         - Stop Jaeger + Prometheus"

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

run-products:
	curl -s http://localhost:8000/products/widget-1 | python -m json.tool

run-traffic:
	@echo "Sending 20 checkout requests (expect ~35% to fail at DB / payment layer)..."
	@for i in $$(seq 1 20); do curl -s http://localhost:8000/checkout > /dev/null; done
	@echo "Done. Check Jaeger at http://localhost:16686 and Prometheus at http://localhost:9090"

run-error-traffic:
	@echo "Sending mixed traffic: 20 checkout + 10 product requests..."
	@for i in $$(seq 1 20); do curl -s http://localhost:8000/checkout > /dev/null; done
	@for i in $$(seq 1 10); do curl -s http://localhost:8000/products/widget-$${i} > /dev/null; done
	@echo "Done."
	@echo ""
	@echo "Observe in Jaeger (http://localhost:16686):"
	@echo "  • /orders spans:  red (ERROR) for DB/payment failures — Pattern 2"
	@echo "  • /products spans: green (OK) with cache_fallback events — Pattern 3"
	@echo "  • /health spans:  occasionally red from unhandled RuntimeError — Pattern 1"
	@echo ""
	@echo "Prometheus error rate query:"
	@echo "  rate(orders_errors_total[5m])"

infra-up:
	docker-compose up -d

infra-down:
	docker-compose down
