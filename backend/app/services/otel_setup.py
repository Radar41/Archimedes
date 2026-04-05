from __future__ import annotations

import base64
import os
from typing import Any

from fastapi import FastAPI

_TELEMETRY_INITIALIZED = False


def _langfuse_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    explicit_headers = os.getenv("LANGFUSE_OTEL_HEADERS")
    if explicit_headers:
        for entry in explicit_headers.split(","):
            if "=" in entry:
                key, value = entry.split("=", 1)
                headers[key.strip()] = value.strip()
        return headers

    if public_key and secret_key:
        token = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {token}"
    return headers


def init_telemetry(app: FastAPI) -> dict[str, Any]:
    global _TELEMETRY_INITIALIZED

    if _TELEMETRY_INITIALIZED:
        return {"enabled": True, "reason": "already_initialized"}

    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return {"enabled": False, "reason": "opentelemetry_packages_missing"}

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "archimedes"),
                "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "development"),
            }
        )
    )

    langfuse_endpoint = (
        os.getenv("LANGFUSE_OTEL_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or "http://localhost:3000/api/public/otel/v1/traces"
    )
    if langfuse_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=langfuse_endpoint, headers=_langfuse_headers())
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            pass

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    _TELEMETRY_INITIALIZED = True
    return {"enabled": True, "reason": "initialized"}
