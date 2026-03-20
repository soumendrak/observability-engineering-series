# Chapter 8: OTel Collector Pipeline

.PHONY: help \
        mvp-infra-up mvp-infra-down mvp-logs \
        prod-infra-up prod-infra-down prod-logs prod-validate \
        run-order run-gateway \
        run-request run-products run-traffic run-error-traffic \
        verify-collector verify-jaeger verify-prometheus

help:
	@echo ""
	@echo "Chapter 8: OTel Collector Pipeline"
	@echo "==================================="
	@echo ""
	@echo "Infrastructure (choose MVP or Production):"
	@echo "  mvp-infra-up       - Start MVP stack (Collector + Jaeger + Prometheus)"
	@echo "  mvp-infra-down     - Stop MVP stack"
	@echo "  mvp-logs           - Tail MVP Collector logs"
	@echo "  prod-infra-up      - Start production stack (pinned versions, health checks)"
	@echo "  prod-infra-down    - Stop production stack"
	@echo "  prod-logs          - Tail production Collector logs"
	@echo "  prod-validate      - Validate production Collector config"
	@echo ""
	@echo "Services (same for both MVP and Production):"
	@echo "  run-order          - Start Order Service (port 8001)"
	@echo "  run-gateway        - Start API Gateway (port 8000)"
	@echo ""
	@echo "Traffic:"
	@echo "  run-request        - Send a single checkout request"
	@echo "  run-products       - Send a single product fetch request"
	@echo "  run-traffic        - Send 20 checkout requests"
	@echo "  run-error-traffic  - Send mixed checkout + product requests"
	@echo ""
	@echo "Verification:"
	@echo "  verify-collector   - Check Collector startup logs"
	@echo "  verify-jaeger      - Open Jaeger UI URL"
	@echo "  verify-prometheus  - Open Prometheus targets URL"

# ──────────────────────────────────────────────
# MVP Infrastructure (Chapter 8 Part 2)
# ──────────────────────────────────────────────
mvp-infra-up:
	docker compose -f mvp/docker-compose.yml up -d
	@echo ""
	@echo "MVP stack started. Waiting for Collector..."
	@sleep 3
	@docker compose -f mvp/docker-compose.yml logs otel-collector 2>&1 | grep -q "Everything is ready" && \
		echo "✓ Collector is ready!" || \
		echo "⚠ Collector may still be starting. Run: make mvp-logs"

mvp-infra-down:
	docker compose -f mvp/docker-compose.yml down

mvp-logs:
	docker compose -f mvp/docker-compose.yml logs -f otel-collector

# ──────────────────────────────────────────────
# Production Infrastructure (Chapter 8 Part 3)
# ──────────────────────────────────────────────
prod-infra-up:
	docker compose -f production/docker-compose.yml up -d
	@echo ""
	@echo "Production stack started. Waiting for Collector health check..."
	@sleep 5
	@curl -sf http://localhost:13133 > /dev/null 2>&1 && \
		echo "✓ Collector is healthy!" || \
		echo "⚠ Health check not responding yet. Run: make prod-logs"

prod-infra-down:
	docker compose -f production/docker-compose.yml down

prod-logs:
	docker compose -f production/docker-compose.yml logs -f otel-collector

prod-validate:
	@echo "Validating production Collector config..."
	docker run --rm \
		-v $$(pwd)/production/otel-collector-config.yaml:/etc/otel/config.yaml \
		otel/opentelemetry-collector-contrib:0.120.0 \
		validate --config /etc/otel/config.yaml

# ──────────────────────────────────────────────
# Services (shared — same for MVP and Production)
#
# All three signals (traces, metrics, logs) are sent via OTLP
# to the Collector on localhost:4317.
# ──────────────────────────────────────────────
run-order:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--metrics_exporter otlp \
		--logs_exporter otlp \
		--exporter_otlp_endpoint http://localhost:4317 \
		--service_name order-service \
		uvicorn order_service:app --port 8001

run-gateway:
	uv run opentelemetry-instrument \
		--traces_exporter otlp \
		--metrics_exporter otlp \
		--logs_exporter otlp \
		--exporter_otlp_endpoint http://localhost:4317 \
		--service_name api-gateway \
		uvicorn api_gateway:app --port 8000

# ──────────────────────────────────────────────
# Traffic generation
# ──────────────────────────────────────────────
run-request:
	curl -s http://localhost:8000/checkout | python -m json.tool

run-products:
	curl -s http://localhost:8000/products/widget-1 | python -m json.tool

run-traffic:
	@echo "Sending 20 checkout requests..."
	@for i in $$(seq 1 20); do curl -s http://localhost:8000/checkout > /dev/null; done
	@echo "Done. Check Jaeger at http://localhost:16686 and Prometheus at http://localhost:9090"

run-error-traffic:
	@echo "Sending mixed traffic: 20 checkout + 10 product requests..."
	@for i in $$(seq 1 20); do curl -s http://localhost:8000/checkout > /dev/null; done
	@for i in $$(seq 1 10); do curl -s http://localhost:8000/products/widget-$${i} > /dev/null; done
	@echo "Done."
	@echo ""
	@echo "Observe in Jaeger (http://localhost:16686):"
	@echo "  • /orders spans:  red (ERROR) for DB/payment failures"
	@echo "  • /products spans: green (OK) with cache_fallback events"
	@echo ""
	@echo "Prometheus queries (http://localhost:9090):"
	@echo "  otel_gateway_requests_total"
	@echo "  otel_orders_created_total"
	@echo "  rate(otel_orders_errors_total[5m])"

# ──────────────────────────────────────────────
# Verification helpers
# ──────────────────────────────────────────────
verify-collector:
	@echo "Step 1: Checking Collector startup..."
	@docker compose -f mvp/docker-compose.yml logs otel-collector 2>/dev/null | grep "Everything is ready" || \
	 docker compose -f production/docker-compose.yml logs otel-collector 2>/dev/null | grep "Everything is ready" || \
	 echo "⚠ Collector not found or not ready. Start with: make mvp-infra-up"
	@echo ""
	@echo "Step 2: Checking for incoming spans (hit an endpoint first)..."
	@docker compose -f mvp/docker-compose.yml logs otel-collector 2>/dev/null | grep -c "ScopeSpans" || \
	 docker compose -f production/docker-compose.yml logs otel-collector 2>/dev/null | grep -c "ScopeSpans" || \
	 echo "0 spans found. Send traffic with: make run-request"

verify-jaeger:
	@echo "Jaeger UI: http://localhost:16686"
	@echo "Look for services: api-gateway, order-service"

verify-prometheus:
	@echo "Prometheus targets: http://localhost:9090/targets"
	@echo "The otel-collector target should show State: UP"
	@echo ""
	@echo "Try these queries:"
	@echo "  otel_gateway_requests_total"
	@echo "  otel_orders_created_total"
	@echo "  rate(otel_orders_errors_total[5m])"
