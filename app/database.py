"""Connection pool, SQL event logging, and explicit lab schema initialization."""

import logging
from pathlib import Path
from time import perf_counter

from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode, Tracer
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.logging import REQUEST_ID_PATTERN, configure_logging, request_id_context
from app.metrics import SQL_OPERATIONS, Metrics
from app.models import Base, ProductRecord

logger = logging.getLogger("shopsphere.order-api")


class Database:
    def __init__(
        self,
        settings: Settings,
        *,
        metrics: Metrics | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=5,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 3,
                "application_name": "order-api",
                "options": "-c statement_timeout=10000 -c timezone=UTC",
            },
        )
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

        @event.listens_for(self.engine, "before_cursor_execute", retval=True)
        def before_query(connection, cursor, statement, parameters, context, many):
            context.shopsphere_started = perf_counter()
            if tracer and trace.get_current_span().get_span_context().is_valid:
                operation = (
                    statement.split(None, 1)[0].upper() if statement else "OTHER"
                )
                if operation not in SQL_OPERATIONS:
                    operation = "OTHER"
                # No SQL text, parameter values, credentials, or request-ID comments.
                context.shopsphere_span = tracer.start_span(
                    f"{operation} {self.engine.url.database}",
                    kind=SpanKind.CLIENT,
                    attributes={
                        "db.system.name": "postgresql",
                        "db.namespace": self.engine.url.database,
                        "db.operation.name": operation,
                        "server.address": self.engine.url.host,
                        "server.port": self.engine.url.port or 5432,
                    },
                )
            request_id = request_id_context.get()
            # Only middleware-validated IDs enter SQL comments; values stay bound.
            if request_id and REQUEST_ID_PATTERN.fullmatch(request_id):
                statement += f" /* request_id={request_id} */"
            return statement, parameters

        @event.listens_for(self.engine, "after_cursor_execute")
        def after_query(connection, cursor, statement, parameters, context, many):
            duration = (perf_counter() - context.shopsphere_started) * 1000
            span = getattr(context, "shopsphere_span", None)
            if span is not None:
                span.end()
            if metrics is not None:
                metrics.observe_query(statement, duration / 1000, "success")
            logger.log(
                logging.WARNING if duration >= 250 else logging.INFO,
                "Database query completed",
                extra={
                    "event": "database.query",
                    "db_operation": statement.split()[0].upper(),
                    "query_name": context.execution_options.get("query_name", "sql"),
                    "duration_ms": round(duration, 3),
                    "db_backend_pid": cursor.connection.info.backend_pid,
                },
            )

        @event.listens_for(self.engine, "handle_error")
        def query_failed(context):
            execution = context.execution_context
            started = getattr(execution, "shopsphere_started", None)
            span = getattr(execution, "shopsphere_span", None)
            if span is not None:
                span.set_status(StatusCode.ERROR)
                span.set_attribute(
                    "error.type", type(context.original_exception).__name__
                )
                span.end()
            if metrics is not None and started is not None:
                metrics.observe_query(
                    context.statement or "", perf_counter() - started, "error"
                )
            logger.error(
                "Database query failed",
                extra={
                    "event": "database.query_failed",
                    "error_type": type(context.original_exception).__name__,
                    "sqlstate": getattr(context.original_exception, "sqlstate", None),
                },
            )

    def check_ready(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(select(ProductRecord.id).limit(1))

    def initialize(self) -> None:
        """Create missing tables and seed products; never erase existing orders."""
        with self.engine.begin() as connection:
            Base.metadata.create_all(connection)
            seed = Path(__file__).resolve().parent.parent / "postgres" / "init.sql"
            connection.execute(text(seed.read_text()))

    def close(self) -> None:
        self.engine.dispose()


def main() -> None:
    configure_logging("order-api")
    database = Database(Settings.from_env())
    try:
        database.initialize()
        logger.info("Database initialized", extra={"event": "database.initialized"})
    finally:
        database.close()


if __name__ == "__main__":
    main()
