"""Explicit, per-application tracing; exporting never runs on the request path."""

import asyncio
import os

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased


class Tracing:
    def __init__(self, service: str, provider: TracerProvider | None = None):
        self.endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
        enabled = (
            bool(self.endpoint) and os.getenv("OTEL_SDK_DISABLED", "").lower() != "true"
        )
        self.owns_provider = provider is None and enabled
        self.provider = provider
        if self.owns_provider:
            self.provider = TracerProvider(
                resource=Resource.create(
                    {"service.name": service, "service.version": "0.8.0"}
                ),
                sampler=ParentBased(ALWAYS_ON),
                shutdown_on_exit=False,
            )

    @property
    def tracer(self):
        return (
            self.provider.get_tracer("shopsphere.database") if self.provider else None
        )

    def instrument_app(self, app):
        if self.provider:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=self.provider,
                excluded_urls=r"/metrics(?:\?.*)?$",
                # Keep the lesson focused on server, SQL, and downstream spans.
                exclude_spans=["receive", "send"],
                http_capture_headers_server_request=[],
                http_capture_headers_server_response=[],
            )

    def instrument_client(self, client):
        if self.provider:
            HTTPXClientInstrumentor.instrument_client(
                client, tracer_provider=self.provider
            )

    def start(self):
        if self.owns_provider:
            self.provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=self.endpoint, timeout=2),
                    max_queue_size=2048,
                    max_export_batch_size=128,
                    schedule_delay_millis=1000,
                    export_timeout_millis=3000,
                )
            )

    async def shutdown(self):
        if self.owns_provider:
            await asyncio.to_thread(self.provider.shutdown)
