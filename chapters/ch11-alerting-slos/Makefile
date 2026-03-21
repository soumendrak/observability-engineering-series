# Chapter 11: Alerting & Service Level Objectives (SLOs)

.PHONY: help \
        infra-up infra-down logs \
        run-order run-gateway \
        run-request run-traffic run-error-traffic \
        simulate-errors test-alerts \
        verify-collector verify-grafana verify-alerts \
        open-grafana open-alerts open-jaeger open-prometheus

help:
	@echo ""
	@echo "Chapter 11: Alerting & Service Level Objectives (SLOs)"
	@echo "======================================================="
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
	@echo "  run-traffic        - Send 50 checkout requests (populates dashboard)"
	@echo "  run-error-traffic  - Send mixed checkout + product requests"
	@echo ""
	@echo "Alerting:"
	@echo "  simulate-errors    - Simulate error burst (stop Order Service first!)"
	@echo "  test-alerts        - Run promtool unit tests on alert rules"
	@echo "  open-alerts        - Open Grafana Alerting UI"
	@echo ""
	@echo "Dashboards:"
	@echo "  open-grafana       - Open RED dashboard in browser"
	@echo "  open-jaeger        - Open Jaeger in browser"
	@echo "  open-prometheus    - Open Prometheus in browser"
	@echo ""
	@echo "Verification:"
	@echo "  verify-collector   - Check Collector startup logs"
	@echo "  verify-grafana     - Check Grafana health and datasources"
	@echo "  verify-alerts      - Check provisioned alert rules in Grafana"

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
		echo "⚠ Grafana not responding yet. Wait a few seconds."
	@echo ""
	@echo "Open Grafana:    http://localhost:3000  (admin / admin)"
	@echo "Open Alerts:     http://localhost:3000/alerting/list"
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

run-traffic:
	@echo "Sending 50 checkout requests to populate the dashboard..."
	@for i in $$(seq 1 50); do \
		curl -s http://localhost:8000/checkout > /dev/null; \
		sleep 0.5; \
	done
	@echo "Done. Open Grafana: http://localhost:3000/d/red-dashboard"

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
	@echo "Done."

# ──────────────────────────────────────────────
# Alerting
# ──────────────────────────────────────────────
simulate-errors:
	@echo "Simulating error burst..."
	@echo "Make sure the Order Service is STOPPED first!"
	@echo "  Stop it with: Ctrl+C in the run-order terminal"
	@echo ""
	uv run python simulate_errors.py

test-alerts:
	@echo "Running promtool unit tests on alert rules..."
	@command -v promtool > /dev/null 2>&1 || \
		{ echo "⚠ promtool not found. Install with:"; \
		  echo "  brew install prometheus  (macOS)"; \
		  echo "  or download from https://prometheus.io/download/"; \
		  exit 1; }
	promtool test rules test_alerts.yaml

# ──────────────────────────────────────────────
# Dashboard & Alert URLs
# ──────────────────────────────────────────────
open-grafana:
	@open http://localhost:3000/d/red-dashboard/service-red-dashboard 2>/dev/null || \
		echo "Open: http://localhost:3000/d/red-dashboard/service-red-dashboard"

open-alerts:
	@open http://localhost:3000/alerting/list 2>/dev/null || \
		echo "Open: http://localhost:3000/alerting/list"

open-jaeger:
	@open http://localhost:16686 2>/dev/null || \
		echo "Open: http://localhost:16686"

open-prometheus:
	@open http://localhost:9090 2>/dev/null || \
		echo "Open: http://localhost:9090"

# ──────────────────────────────────────────────
# Verification helpers
# ──────────────────────────────────────────────
verify-collector:
	@echo "Checking Collector startup..."
	@docker compose logs otel-collector 2>/dev/null | grep "Everything is ready" || \
		echo "⚠ Collector not ready. Start with: make infra-up"

verify-grafana:
	@echo "Checking Grafana..."
	@curl -sf http://localhost:3000/api/health 2>/dev/null && \
		echo "✓ Grafana is running!" || \
		echo "⚠ Grafana not responding. Start with: make infra-up"
	@echo ""
	@echo "Checking provisioned datasources..."
	@curl -sf http://localhost:3000/api/datasources 2>/dev/null | python -m json.tool 2>/dev/null || \
		echo "Could not fetch datasources."

verify-alerts:
	@echo "Checking provisioned alert rules..."
	@curl -sf http://localhost:3000/api/v1/provisioning/alert-rules 2>/dev/null | python -m json.tool 2>/dev/null || \
		echo "Could not fetch alert rules. Make sure Grafana is running: make infra-up"
	@echo ""
	@echo "Alert rules UI: http://localhost:3000/alerting/list"
	@echo ""
	@echo "Expected alerts:"
	@echo "  • High Error Rate (critical, fires at > 5% for 5m)"
	@echo "  • P99 Latency Above Threshold (warning, fires at > 3000ms for 10m)"
	@echo "  • Request Rate Dropped Significantly (warning, fires at < 50% for 5m)"
	@echo "  • Error Budget Burn Rate Critical (critical, fires at > 14.4x burn rate)"
