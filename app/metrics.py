"""Per-process Prometheus metrics with bounded, deliberately chosen labels."""

from time import perf_counter

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Include the five-second lab delay and the ten-second SQL timeout.
DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)
HTTP_METHODS = {
    "GET",
    "HEAD",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "TRACE",
    "CONNECT",
}
SQL_OPERATIONS = {"SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "SET", "SHOW"}


class Metrics:
    def __init__(self, service: str):
        self.service = service
        # App factories and tests must not share the global default registry.
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "http_requests_total",
            "Completed HTTP requests, excluding /metrics.",
            ("service", "method", "route", "status"),
            registry=self.registry,
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "Complete HTTP response duration in seconds.",
            ("service", "method", "route"),
            buckets=DURATION_BUCKETS,
            registry=self.registry,
        )
        self.errors = Counter(
            "application_errors_total",
            "HTTP requests returning a server error (5xx).",
            ("service", "method", "route"),
            registry=self.registry,
        )
        self.database_duration = Histogram(
            "database_query_duration_seconds",
            "SQL cursor execution duration in seconds.",
            ("service", "operation", "outcome"),
            buckets=DURATION_BUCKETS,
            registry=self.registry,
        )

    def observe_query(self, statement: str, duration: float, outcome: str) -> None:
        words = statement.split(None, 1)
        operation = words[0].upper() if words else "OTHER"
        if operation not in SQL_OPERATIONS:
            operation = "OTHER"
        self.database_duration.labels(self.service, operation, outcome).observe(
            duration
        )

    def response(self) -> Response:
        return Response(
            generate_latest(self.registry),
            headers={"Content-Type": CONTENT_TYPE_LATEST},
        )


class MetricsMiddleware:
    """Wrap the logging/error middleware so handled failures count exactly once."""

    def __init__(self, app: ASGIApp, metrics: Metrics):
        self.app, self.metrics = app, metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return
        started, status = perf_counter(), 500

        async def measure_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, measure_send)
        finally:
            # Templates merge all order IDs; unknown paths/methods stay bounded.
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope["method"] if scope["method"] in HTTP_METHODS else "OTHER"
            labels = (self.metrics.service, method, route)
            self.metrics.requests.labels(*labels, str(status)).inc()
            self.metrics.duration.labels(*labels).observe(perf_counter() - started)
            self.metrics.errors.labels(*labels).inc(int(status >= 500))
