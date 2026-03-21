# Chapter 10: Dashboards & the RED Method

.PHONY: help \
        infra-up infra-down logs \
        run-order run-gateway \
        run-request run-products run-traffic run-error-traffic \
        verify-collector verify-jaeger verify-prometheus verify-grafana \
        open-grafana open-jaeger open-prometheus

help:
	@echo ""
	@echo "Chapter 10: Dashboards & the RED Method"
	@echo "========================================="
	@echo ""
	@echo "Infrastructure:"
	@echo "  infra-up           - Start stack (Collector + Jaeger + Prometheus + Grafana)"
	@echo "  infra-down         - Stop stack"
	@echo "  logs               - Tail Collector logs"
	@echo ""
	@echo "Services:"
	@echo "  run-order          - Start Order Service (port 8001)"
	@echo "  run-gateway        - Start API Gateway (port 8000)"
	@echo ""
	@echo "Traffic:"
	@echo "  run-request        - Send a single checkout request"
	@echo "  run-products       - Send a single product fetch request"
	@echo "  run-traffic        - Send 50 checkout requests (populates dashboard)"
	@echo "  run-error-traffic  - Send mixed checkout + product requests"
	@echo ""
	@echo "Dashboards:"
	@echo "  open-grafana       - Open Grafana in browser (http://localhost:3000)"
	@echo "  open-jaeger        - Open Jaeger in browser (http://localhost:16686)"
	@echo "  open-prometheus    - Open Prometheus in browser (http://localhost:9090)"
	@echo ""
	@echo "Verification:"
	@echo "  verify-collector   - Check Collector startup logs"
	@echo "  verify-jaeger      - Show Jaeger UI URL"
	@echo "  verify-prometheus  - Show Prometheus targets URL"
	@echo "  verify-grafana     - Check Grafana is running and datasources are provisioned"

# ──────────────────────────────────────────────
# Infrastructure
# ──────────────────────────────────────────────
infra-up:
	docker compose up -d
	@echo ""
	@echo "Stack started. Waiting for services..."
	@sleep 5
	@curl -sf http://localhost:13133 > /dev/null 2>&1 && \
		echo "✓ Collector is healthy!" || \
		echo "⚠ Collector health check not responding yet. Run: make logs"
	@curl -sf http://localhost:3000/api/health > /dev/null 2>&1 && \
		echo "✓ Grafana is healthy!" || \
		echo "⚠ Grafana not responding yet. Wait a few seconds and try: make verify-grafana"
	@echo ""
	@echo "Open Grafana:    http://localhost:3000  (admin / admin)"
	@echo "Open Jaeger:     http://localhost:16686"
	@echo "Open Prometheus: http://localhost:9090"

infra-down:
	docker compose down -v

logs:
	docker compose logs -f otel-collector

# ──────────────────────────────────────────────
# Services
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
	@echo "Sending 50 checkout requests to populate the RED dashboard..."
	@echo "Watch the dashboard at http://localhost:3000"
	@echo ""
	@for i in $$(seq 1 50); do \
		curl -s http://localhost:8000/checkout > /dev/null; \
		sleep 0.5; \
	done
	@echo ""
	@echo "Done. Open Grafana: http://localhost:3000"
	@echo "Navigate to: Dashboards → Observability Series → Service RED Dashboard"
	@echo ""
	@echo "You should see:"
	@echo "  • Error Rate % (green if < 1%, yellow 1-5%, red > 5%)"
	@echo "  • Request Rate (~2 req/sec)"
	@echo "  • P99 Latency"
	@echo "  • Request Rate by Route graph filling in"
	@echo "  • Latency Percentiles (P50, P95, P99)"

run-error-traffic:
	@echo "Sending mixed traffic: 30 checkout + 10 product + 10 genai requests..."
	@for i in $$(seq 1 30); do curl -s http://localhost:8000/checkout > /dev/null; sleep 0.3; done
	@for i in $$(seq 1 10); do curl -s http://localhost:8000/products/widget-$${i} > /dev/null; sleep 0.2; done
	@for i in $$(seq 1 10); do \
		curl -s -X POST http://localhost:8000/ask \
			-H "Content-Type: application/json" \
			-d '{"question": "What products do you have?"}' \
			> /dev/null; \
		sleep 0.3; \
	done
	@echo "Done. Check the dashboard for error rate and latency changes."

# ──────────────────────────────────────────────
# Dashboard URLs
# ──────────────────────────────────────────────
open-grafana:
	@echo "Opening Grafana..."
	@open http://localhost:3000/d/red-dashboard/service-red-dashboard 2>/dev/null || \
		echo "Open: http://localhost:3000/d/red-dashboard/service-red-dashboard"

open-jaeger:
	@echo "Opening Jaeger..."
	@open http://localhost:16686 2>/dev/null || \
		echo "Open: http://localhost:16686"

open-prometheus:
	@echo "Opening Prometheus..."
	@open http://localhost:9090 2>/dev/null || \
		echo "Open: http://localhost:9090"

# ──────────────────────────────────────────────
# Verification helpers
# ──────────────────────────────────────────────
verify-collector:
	@echo "Checking Collector startup..."
	@docker compose logs otel-collector 2>/dev/null | grep "Everything is ready" || \
		echo "⚠ Collector not ready. Start with: make infra-up"

verify-jaeger:
	@echo "Jaeger UI: http://localhost:16686"
	@echo "Look for services: api-gateway, order-service"

verify-prometheus:
	@echo "Prometheus targets: http://localhost:9090/targets"
	@echo "The otel-collector target should show State: UP"
	@echo ""
	@echo "Try these PromQL queries:"
	@echo "  rate(otel_gateway_requests_total[5m])"
	@echo "  histogram_quantile(0.99, sum(rate(otel_gateway_request_duration_milliseconds_bucket[5m])) by (le))"

verify-grafana:
	@echo "Checking Grafana..."
	@curl -sf http://localhost:3000/api/health 2>/dev/null && \
		echo "✓ Grafana is running!" || \
		echo "⚠ Grafana not responding. Start with: make infra-up"
	@echo ""
	@echo "Checking provisioned datasources..."
	@curl -sf http://localhost:3000/api/datasources 2>/dev/null | python -m json.tool 2>/dev/null || \
		echo "Could not fetch datasources. Grafana may still be starting."
	@echo ""
	@echo "Dashboard URL: http://localhost:3000/d/red-dashboard/service-red-dashboard"
