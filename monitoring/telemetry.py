"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Observability & Telemetry
 Structured logging + OpenTelemetry traces + Prometheus metrics
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator

import structlog
from prometheus_client import Counter, Histogram, Gauge, Info

from core.config import get_settings, LogFormat


# ═══════════════════════════════════════════════════════════════
#  Structured Logging Setup
# ═══════════════════════════════════════════════════════════════

def setup_logging() -> None:
    """Configure structlog with JSON or console output."""
    settings = get_settings()
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.ExceptionRenderer(),
    ]
    if settings.log_format == LogFormat.JSON:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Prometheus Metrics
# ═══════════════════════════════════════════════════════════════

# Counters
AGENT_INVOCATIONS = Counter(
    "apex_agent_invocations_total",
    "Total agent invocations",
    ["agent", "status"],
)
TOKENS_USED = Counter(
    "apex_tokens_used_total",
    "Total LLM tokens consumed",
    ["agent", "model"],
)
SANDBOX_EXECUTIONS = Counter(
    "apex_sandbox_executions_total",
    "Total sandbox code executions",
    ["language", "status"],
)

# Histograms
AGENT_DURATION = Histogram(
    "apex_agent_duration_seconds",
    "Agent execution duration",
    ["agent"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)
LLM_LATENCY = Histogram(
    "apex_llm_latency_seconds",
    "LLM API call latency",
    ["model"],
    buckets=[0.5, 1, 2, 5, 10, 30],
)

# Gauges
ACTIVE_SESSIONS = Gauge(
    "apex_active_sessions",
    "Currently active coding sessions",
)
DEBUG_LOOP_DEPTH = Gauge(
    "apex_debug_loop_depth",
    "Current debug loop iteration",
    ["session_id"],
)

# Info
SYSTEM_INFO = Info(
    "apex_system",
    "System information",
)


def record_system_info() -> None:
    settings = get_settings()
    SYSTEM_INFO.info({
        "model": settings.apex_model,
        "version": "1.0.0",
        "sandbox_mode": "docker" if settings.sandbox_use_docker else "subprocess",
    })


# ═══════════════════════════════════════════════════════════════
#  OpenTelemetry Tracing
# ═══════════════════════════════════════════════════════════════

_tracer = None


def setup_tracing() -> None:
    """Initialize OpenTelemetry with OTLP exporter."""
    global _tracer
    settings = get_settings()
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("apex-coding-agent")
        structlog.get_logger().info("tracing.initialized")
    except ImportError:
        structlog.get_logger().warning("tracing.disabled", reason="OpenTelemetry not installed")
    except Exception as exc:
        structlog.get_logger().warning("tracing.failed", error=str(exc))


def get_tracer():
    return _tracer


# ═══════════════════════════════════════════════════════════════
#  Decorators & Utilities
# ═══════════════════════════════════════════════════════════════

@contextmanager
def track_duration(agent_name: str) -> Generator[dict[str, Any], None, None]:
    """Context manager that tracks execution duration and records metrics."""
    start = time.monotonic()
    context: dict[str, Any] = {"agent": agent_name, "start": start}
    try:
        yield context
        context["status"] = "success"
        AGENT_INVOCATIONS.labels(agent=agent_name, status="success").inc()
    except Exception as exc:
        context["status"] = "error"
        context["error"] = str(exc)
        AGENT_INVOCATIONS.labels(agent=agent_name, status="error").inc()
        raise
    finally:
        duration = time.monotonic() - start
        context["duration"] = round(duration, 3)
        AGENT_DURATION.labels(agent=agent_name).observe(duration)


def traced(agent_name: str) -> Callable:
    """Decorator that adds tracing + metrics to an async function."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            if tracer:
                with tracer.start_as_current_span(f"agent.{agent_name}") as span:
                    span.set_attribute("agent.name", agent_name)
                    with track_duration(agent_name) as ctx:
                        result = await func(*args, **kwargs)
                        span.set_attribute("agent.duration", ctx["duration"])
                    return result
            else:
                with track_duration(agent_name):
                    return await func(*args, **kwargs)
        return wrapper
    return decorator


def init_telemetry() -> None:
    """Initialize all telemetry systems."""
    setup_logging()
    setup_tracing()
    record_system_info()
