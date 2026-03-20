# Chapter 9: Sampling & PII Scrubbing

.PHONY: help \
        infra-up infra-down logs \
        run-order run-gateway \
        run-request run-products run-traffic run-error-traffic run-genai \
        verify-collector verify-jaeger verify-prometheus verify-pii verify-sampling \
        validate-config

help:
	@echo ""
	@echo "Chapter 9: Sampling & PII Scrubbing"
	@echo "====================================="
	@echo ""
	@echo "Infrastructure:"
	@echo "  infra-up           - Start stack (Collector + Jaeger + Prometheus)"
	@echo "  infra-down         - Stop stack"
	@echo "  logs               - Tail Collector logs"
	@echo "  validate-config    - Validate Collector config before deploying"
	@echo ""
	@echo "Services:"
	@echo "  run-order          - Start Order Service (port 8001)"
	@echo "  run-gateway        - Start API Gateway (port 8000)"
	@echo ""
	@echo "Traffic:"
	@echo "  run-request        - Send a single checkout request"
	@echo "  run-products       - Send a single product fetch request"
	@echo "  run-genai          - Send a GenAI /ask request (contains PII)"
	@echo "  run-traffic        - Send 100 mixed requests (checkout + genai)"
	@echo "  run-error-traffic  - Send mixed checkout + product + genai requests"
	@echo ""
	@echo "Verification:"
	@echo "  verify-collector   - Check Collector startup logs"
	@echo "  verify-jaeger      - Open Jaeger UI URL"
	@echo "  verify-prometheus  - Open Prometheus targets URL"
	@echo "  verify-pii         - Check that PII is scrubbed in exported spans"
	@echo "  verify-sampling    - Check sampling decisions in Collector logs"

# ──────────────────────────────────────────────
# Infrastructure
# ──────────────────────────────────────────────
infra-up:
	docker compose up -d
	@echo ""
	@echo "Stack started. Waiting for Collector health check..."
	@sleep 5
	@curl -sf http://localhost:13133 > /dev/null 2>&1 && \
		echo "✓ Collector is healthy!" || \
		echo "⚠ Health check not responding yet. Run: make logs"

infra-down:
	docker compose down

logs:
	docker compose logs -f otel-collector

validate-config:
	@echo "Validating Collector config..."
	docker run --rm \
		-v $$(pwd)/otel-collector-config.yaml:/etc/otel/config.yaml \
		otel/opentelemetry-collector-contrib:0.120.0 \
		validate --config /etc/otel/config.yaml

# ──────────────────────────────────────────────
# Services
#
# All three signals (traces, metrics, logs) are sent via OTLP
# to the Collector on localhost:4317.
# No application-side sampling — the Collector handles tail sampling.
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

run-genai:
	@echo "Sending GenAI /ask request (contains PII: name, SSN, email)..."
	curl -s -X POST http://localhost:8000/ask \
		-H "Content-Type: application/json" \
		-d '{"question": "My name is John Smith, SSN 123-45-6789. My email is john.smith@example.com. What are my account options?"}' \
		| python -m json.tool

run-traffic:
	@echo "Sending 100 mixed requests (checkout + genai)..."
	@echo "With tail sampling, expect ~5% of successful traces in Jaeger,"
	@echo "but 100% of error traces."
	@echo ""
	@for i in $$(seq 1 80); do curl -s http://localhost:8000/checkout > /dev/null; done
	@for i in $$(seq 1 20); do \
		curl -s -X POST http://localhost:8000/ask \
			-H "Content-Type: application/json" \
			-d '{"question": "My name is Jane Doe, SSN 987-65-4321. Email: jane@example.com. Show my balance."}' \
			> /dev/null; \
	done
	@echo ""
	@echo "Done. Wait ~10s (decision_wait) then check:"
	@echo "  Jaeger:      http://localhost:16686"
	@echo "  Prometheus:  http://localhost:9090"
	@echo ""
	@echo "In Jaeger you should see:"
	@echo "  • ALL traces with errors (red spans) — 100% kept"
	@echo "  • Only ~5% of fast, successful traces"
	@echo "  • llm.prompt and llm.completion show 'REDACTED'"

run-error-traffic:
	@echo "Sending mixed traffic: 20 checkout + 10 product + 10 genai requests..."
	@for i in $$(seq 1 20); do curl -s http://localhost:8000/checkout > /dev/null; done
	@for i in $$(seq 1 10); do curl -s http://localhost:8000/products/widget-$${i} > /dev/null; done
	@for i in $$(seq 1 10); do \
		curl -s -X POST http://localhost:8000/ask \
			-H "Content-Type: application/json" \
			-d '{"question": "SSN 111-22-3333, email test@corp.com. Help me."}' \
			> /dev/null; \
	done
	@echo "Done."
	@echo ""
	@echo "Observe in Jaeger (http://localhost:16686):"
	@echo "  • /orders spans:  red (ERROR) for DB/payment failures — ALL kept"
	@echo "  • /products spans: green (OK) with cache_fallback events"
	@echo "  • /ask spans:     llm.prompt = REDACTED, llm.completion = REDACTED"
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
	@docker compose logs otel-collector 2>/dev/null | grep "Everything is ready" || \
		echo "⚠ Collector not ready. Start with: make infra-up"
	@echo ""
	@echo "Step 2: Checking for incoming spans (hit an endpoint first)..."
	@docker compose logs otel-collector 2>/dev/null | grep -c "ScopeSpans" || \
		echo "0 spans found. Send traffic with: make run-request"

verify-jaeger:
	@echo "Jaeger UI: http://localhost:16686"
	@echo "Look for services: api-gateway, order-service"
	@echo ""
	@echo "Sampling verification:"
	@echo "  1. Send 100 requests: make run-traffic"
	@echo "  2. Wait 10s (decision_wait)"
	@echo "  3. In Jaeger, search for api-gateway traces"
	@echo "  4. Error traces (red): should be ~35% of total (all kept)"
	@echo "  5. Successful traces: should be ~5% of successful ones"

verify-prometheus:
	@echo "Prometheus targets: http://localhost:9090/targets"
	@echo "The otel-collector target should show State: UP"
	@echo ""
	@echo "Try these queries:"
	@echo "  otel_gateway_requests_total"
	@echo "  otel_orders_created_total"
	@echo "  rate(otel_orders_errors_total[5m])"
	@echo ""
	@echo "Sampling metrics (Collector internal):"
	@echo "  otelcol_receiver_accepted_spans_total"
	@echo "  otelcol_exporter_sent_spans_total"
	@echo "  (sent << accepted = sampling is working)"

verify-pii:
	@echo "Verifying PII scrubbing..."
	@echo ""
	@echo "Step 1: Sending a GenAI request with PII..."
	@curl -s -X POST http://localhost:8000/ask \
		-H "Content-Type: application/json" \
		-d '{"question": "My SSN is 999-88-7777 and email is secret@private.com"}' \
		> /dev/null
	@echo "Request sent. Waiting 12s for trace to be processed (decision_wait + buffer)..."
	@sleep 12
	@echo ""
	@echo "Step 2: Checking Collector debug output for scrubbed attributes..."
	@echo "Looking for 'REDACTED' in recent Collector logs:"
	@docker compose logs --tail=200 otel-collector 2>/dev/null | grep -i "REDACTED" && \
		echo "" && echo "✓ PII scrubbing is active — attributes show REDACTED" || \
		echo "⚠ Could not confirm scrubbing in logs. Check Jaeger manually:" && \
		echo "  1. Open http://localhost:16686" && \
		echo "  2. Search for order-service traces" && \
		echo "  3. Find a span named 'llm_generation'" && \
		echo "  4. Verify llm.prompt = 'REDACTED' and llm.completion = 'REDACTED'"

verify-sampling:
	@echo "Checking sampling decisions in Collector logs..."
	@docker compose logs --tail=100 otel-collector 2>/dev/null | grep -i "sampl" || \
		echo "No sampling log entries found. The tail_sampling processor works silently."
	@echo ""
	@echo "To verify sampling is working, compare span counts:"
	@echo "  curl -s http://localhost:8888/metrics | grep otelcol_receiver_accepted_spans_total"
	@echo "  curl -s http://localhost:8888/metrics | grep otelcol_exporter_sent_spans_total"
	@echo ""
	@echo "If sent << accepted, tail sampling is dropping non-error, fast traces."
