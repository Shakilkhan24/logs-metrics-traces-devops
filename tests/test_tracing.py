"""Trace contracts with real SQL and independent per-service SDK providers."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry import context, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased
from opentelemetry.trace import SpanKind, StatusCode
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import Database
from app.main import create_app
from app.store import simulate_slow_query
from payment.main import create_app as create_payment


@pytest.fixture
def providers():
    exporter = InMemorySpanExporter()
    result = {}
    for service in ("order-api", "mock-payment"):
        provider = TracerProvider(
            resource=Resource.create({"service.name": service}),
            sampler=ParentBased(ALWAYS_ON),
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        result[service] = provider
    yield result, exporter
    for provider in result.values():
        provider.shutdown()


def server_spans(exporter):
    return [s for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER]


def test_w3c_parent_and_slow_sql_timing_and_log_context(db_settings, providers, capsys):
    sdk, exporter = providers
    incoming_id, incoming_span = "1" * 32, "2" * 16
    with TestClient(
        create_app(settings=db_settings, tracer_provider=sdk["order-api"])
    ) as client:
        response = client.get(
            "/slow-query?seconds=0.1",
            headers={
                "traceparent": f"00-{incoming_id}-{incoming_span}-01",
                "tracestate": "lab=example",
                "X-Request-ID": "trace-slow-check",
            },
        )
        assert response.status_code == 200
        assert response.headers["x-trace-id"] == incoming_id
        spans = exporter.get_finished_spans()
        parent = server_spans(exporter)[0]
        assert parent.name == "GET /slow-query"
        assert parent.parent.span_id == int(incoming_span, 16)
        assert parent.parent.is_remote
        assert parent.context.trace_state.get("lab") == "example"
        sql = next(
            s for s in spans if s.attributes.get("db.system.name") == "postgresql"
        )
        assert sql.parent.span_id == parent.context.span_id
        assert sql.context.trace_id == parent.context.trace_id == int(incoming_id, 16)
        assert parent.start_time <= sql.start_time < sql.end_time <= parent.end_time
        assert sql.end_time - sql.start_time >= 100_000_000
        assert not {"db.statement", "db.query.text", "db.user"}.intersection(
            sql.attributes
        )
        assert len(spans) == 2
        client.get("/metrics")
        assert len(exporter.get_finished_spans()) == 2
    events = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    request_events = [e for e in events if e.get("request_id") == "trace-slow-check"]
    assert request_events and all(e["trace_id"] == incoming_id for e in request_events)
    assert not trace.get_current_span().get_span_context().is_valid


class RemotePayment(httpx.AsyncBaseTransport):
    """Simulate a separate process: only HTTP headers cross the boundary."""

    def __init__(self, app):
        self.transport = httpx.ASGITransport(app=app)

    async def handle_async_request(self, request):
        token = context.attach(context.Context())
        try:
            return await self.transport.handle_async_request(request)
        finally:
            context.detach(token)

    async def aclose(self):
        await self.transport.aclose()


def test_payment_is_one_trace_with_client_and_remote_server(db_settings, providers):
    sdk, exporter = providers
    payment = create_payment(tracer_provider=sdk["mock-payment"])
    api = create_app(
        settings=db_settings,
        tracer_provider=sdk["order-api"],
        payment_transport=RemotePayment(payment),
    )
    with TestClient(payment), TestClient(api) as client:
        response = client.get("/payment")
        assert response.status_code == 200
        spans = exporter.get_finished_spans()
        assert len(spans) == 3
        api_span = next(
            s
            for s in spans
            if s.kind == SpanKind.SERVER
            and s.resource.attributes["service.name"] == "order-api"
        )
        client_span = next(s for s in spans if s.kind == SpanKind.CLIENT)
        remote_span = next(
            s for s in spans if s.resource.attributes["service.name"] == "mock-payment"
        )
        assert api_span.parent is None
        assert client_span.parent.span_id == api_span.context.span_id
        assert remote_span.kind == SpanKind.SERVER
        assert remote_span.parent.span_id == client_span.context.span_id
        assert remote_span.parent.is_remote
        assert {f"{s.context.trace_id:032x}" for s in spans} == {
            response.headers["x-trace-id"]
        }
        assert (
            api_span.start_time
            <= client_span.start_time
            < client_span.end_time
            <= api_span.end_time
        )


def test_server_error_and_client_timeout_are_failed_spans(db_settings, providers):
    sdk, exporter = providers

    def timeout(request):
        raise httpx.ReadTimeout("Simulated downstream timeout", request=request)

    with TestClient(
        create_app(
            settings=db_settings,
            tracer_provider=sdk["order-api"],
            payment_transport=httpx.MockTransport(timeout),
        )
    ) as client:
        assert client.get("/error").status_code == 500
        failure = server_spans(exporter)[0]
        assert failure.status.status_code == StatusCode.ERROR
        exceptions = [e for e in failure.events if e.name == "exception"]
        assert len(exceptions) == 1
        assert exceptions[0].attributes["exception.type"] == "RuntimeError"
        exporter.clear()
        assert client.get("/payment").status_code == 504
        spans = exporter.get_finished_spans()
        assert len(spans) == 2
        assert all(s.status.status_code == StatusCode.ERROR for s in spans)
        assert next(s for s in spans if s.kind == SpanKind.CLIENT).events
        exporter.clear()
        assert client.get("/unknown").status_code == 404
        assert server_spans(exporter)[0].status.status_code == StatusCode.UNSET


def test_failed_sql_span_ends_and_records_error_type(db_settings, providers):
    sdk, exporter = providers
    tracer = sdk["order-api"].get_tracer("test")
    database = Database(db_settings, tracer=tracer)
    try:
        with tracer.start_as_current_span("statement timeout"):
            with pytest.raises(DBAPIError):
                with database.sessions.begin() as session:
                    session.execute(text("SET LOCAL statement_timeout = '50ms'"))
                    simulate_slow_query(session, 0.2)
        failed = [
            s
            for s in exporter.get_finished_spans()
            if s.status.status_code == StatusCode.ERROR
        ]
        assert len(failed) == 1
        assert failed[0].attributes["error.type"] == "QueryCanceled"
        assert failed[0].end_time - failed[0].start_time >= 40_000_000
    finally:
        database.close()


def test_sampling_invalid_context_and_independent_requests(db_settings, providers):
    sdk, exporter = providers
    with TestClient(
        create_app(settings=db_settings, tracer_provider=sdk["order-api"])
    ) as client:
        response = client.get(
            "/products", headers={"traceparent": f"00-{'3' * 32}-{'4' * 16}-00"}
        )
        assert response.status_code == 200
        assert response.headers["x-trace-id"] == "3" * 32
        assert not exporter.get_finished_spans()
        first = client.get("/", headers={"traceparent": "not-a-valid-context"})
        second = client.get("/")
        assert first.headers["x-trace-id"] != second.headers["x-trace-id"]
        assert all(s.parent is None for s in server_spans(exporter))
        assert len(server_spans(exporter)) == 2
