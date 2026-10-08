"""One JSON event per line, with context isolated to each HTTP request."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from opentelemetry import trace
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
EVENT_FIELDS = (
    "event",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "order_id",
    "item_count",
    "total_cents",
    "payment_id",
    "error_type",
    "upstream_status",
    "db_operation",
    "query_name",
    "db_backend_pid",
    "sqlstate",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        event = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": record.name.removeprefix("shopsphere."),
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
            "trace_id": f"{span_context.trace_id:032x}"
            if span_context.is_valid
            else None,
            "span_id": f"{span_context.span_id:016x}"
            if span_context.is_valid
            else None,
        }
        for field in EVENT_FIELDS:
            if hasattr(record, field):
                event[field] = getattr(record, field)
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=True, allow_nan=False)


def configure_logging(service: str) -> logging.Logger:
    logger = logging.getLogger(f"shopsphere.{service}")
    for existing in logger.handlers[:]:
        logger.removeHandler(existing)
        existing.close()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class RequestLoggingMiddleware:
    """Measure the complete ASGI response and retain context during error logs."""

    def __init__(self, app: ASGIApp, service: str) -> None:
        self.app = app
        self.logger = logging.getLogger(f"shopsphere.{service}")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if REQUEST_ID_PATTERN.fullmatch(incoming) else uuid4().hex
        token = request_id_context.set(request_id)
        started = perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
                context = trace.get_current_span().get_span_context()
                if context.is_valid:
                    MutableHeaders(scope=message)["X-Trace-ID"] = (
                        f"{context.trace_id:032x}"
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            status_code = 500
            # This middleware handles the exception before outer OTel middleware.
            trace.get_current_span().record_exception(exc)
            self.logger.exception(
                "Unhandled request error",
                extra={"event": "request.failed", "error_type": type(exc).__name__},
            )
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )
            await response(scope, receive, send_with_request_id)
        finally:
            try:
                route = scope.get("route")
                level = (
                    logging.ERROR
                    if status_code >= 500
                    else logging.WARNING
                    if status_code >= 400
                    else logging.INFO
                )
                self.logger.log(
                    level,
                    "Request completed",
                    extra={
                        "event": "request.completed",
                        "method": scope["method"],
                        # Route templates avoid recording query strings or raw IDs.
                        "route": getattr(route, "path", "unmatched"),
                        "status_code": status_code,
                        "duration_ms": round((perf_counter() - started) * 1000, 3),
                    },
                )
            finally:
                request_id_context.reset(token)
