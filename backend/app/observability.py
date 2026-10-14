"""Prometheus metrics, OpenTelemetry tracing and JSON logging."""

import json
import logging
import sys
from typing import Any

from opentelemetry import context, propagate, trace
from prometheus_client import Counter, Gauge, Histogram

from app.config import Settings

HTTP_REQUESTS = Counter(
    "evalops_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "evalops_http_request_seconds", "HTTP request latency", ["method", "route"]
)
RUNS_FINISHED = Counter("evalops_runs_finished_total", "Finished eval runs", ["status"])
CASES_EVALUATED = Counter("evalops_cases_total", "Evaluated cases", ["outcome"])
LLM_LATENCY = Histogram(
    "evalops_llm_latency_seconds",
    "LLM call latency",
    ["provider", "model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
)
LLM_TOKENS = Counter("evalops_llm_tokens_total", "LLM tokens", ["model", "direction"])
LLM_COST = Counter("evalops_llm_cost_usd_total", "LLM spend in USD", ["model"])
LLM_ERRORS = Counter("evalops_llm_errors_total", "Failed LLM calls", ["provider", "model"])
QUEUE_AGE = Gauge("evalops_queue_oldest_age_seconds", "Age of the oldest queued run")
QUEUE_DEPTH = Gauge("evalops_queue_depth", "Queued runs")

tracer = trace.get_tracer("evalops")


def current_trace_context() -> dict[str, str] | None:
    """Serialise the active span as W3C headers, for storing on a queued job."""
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier or None


def context_from(carrier: dict[str, str] | None) -> context.Context:
    """Rebuild the context stored by `current_trace_context` (empty context if none)."""
    return propagate.extract(carrier or {})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            payload["trace_id"] = format(span.trace_id, "032x")
        for key in ("run_id", "case_id", "status"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)


def setup_tracing(settings: Settings, service_name: str) -> bool:
    """Export traces over OTLP/HTTP when an endpoint is configured. Returns True if enabled."""
    if not settings.otel_exporter_otlp_endpoint:
        return False
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": service_name, "deployment.environment": settings.environment}
        )
    )
    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    return True
