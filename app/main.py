"""ShopSphere HTTP API. Start with: python -m uvicorn app.main:app."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.database import Database
from app.logging import (
    RequestLoggingMiddleware,
    configure_logging,
    request_id_context,
)
from app.schemas import Order, OrderCreate, PaymentResult, Product
from app.store import PostgresStore, UnknownProductError

logger = logging.getLogger("shopsphere.order-api")


def create_app(
    *,
    settings: Settings | None = None,
    payment_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging("order-api")
        database = Database(config)
        try:
            try:
                database.check_ready()
            except SQLAlchemyError:
                raise RuntimeError(
                    "Database is not ready. Check DATABASE_URL and run "
                    "python -m app.database."
                ) from None
            application.state.database = database
            application.state.store = PostgresStore(database.sessions)
            async with httpx.AsyncClient(
                base_url=str(config.payment_base_url),
                timeout=config.payment_timeout_seconds,
                transport=payment_transport,
                trust_env=False,
            ) as payment_client:
                application.state.payment_client = payment_client
                logger.info("Order API started", extra={"event": "service.started"})
                try:
                    yield
                finally:
                    logger.info("Order API stopped", extra={"event": "service.stopped"})
        finally:
            database.close()

    application = FastAPI(
        title="ShopSphere Order API",
        version="0.3.0",
        description="Phase 3: PostgreSQL persistence, SQL logs, and database delays.",
        lifespan=lifespan,
    )
    application.add_middleware(RequestLoggingMiddleware, service="order-api")

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error(
            "Database operation failed",
            extra={"event": "database.unavailable", "error_type": type(exc).__name__},
        )
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @application.get("/")
    async def root() -> dict[str, str | int]:
        return {
            "service": "order-api",
            "status": "ok",
            "phase": 3,
            "storage": "postgresql",
        }

    @application.get("/products", response_model=list[Product])
    def products(request: Request):
        return request.app.state.store.list_products()

    @application.post("/orders", response_model=Order, status_code=201)
    def create_order(
        payload: OrderCreate,
        request: Request,
        response: Response,
        db_delay_seconds: Annotated[float, Query(ge=0, le=5, allow_inf_nan=False)] = 0,
    ):
        try:
            order = request.app.state.store.create_order(payload, db_delay_seconds)
        except UnknownProductError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        response.headers["Location"] = f"/orders/{order.id}"
        logger.info(
            "Order created",
            extra={
                "event": "order.created",
                "order_id": str(order.id),
                "item_count": len(order.items),
                "total_cents": order.total_cents,
            },
        )
        return order

    @application.get("/orders/{id}", response_model=Order)
    def get_order(id: UUID, request: Request):
        order = request.app.state.store.get_order(id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return order

    @application.get("/slow-query")
    def slow_query(
        request: Request,
        seconds: Annotated[float, Query(ge=0, le=5, allow_inf_nan=False)] = 5,
    ) -> dict[str, str | float]:
        duration = request.app.state.store.slow_query(seconds)
        return {
            "operation": "pg_sleep",
            "requested_seconds": seconds,
            "duration_ms": duration,
        }

    @application.get("/payment", response_model=PaymentResult)
    async def payment(request: Request):
        """Exercise a downstream call. This simulation never charges money."""
        try:
            upstream = await request.app.state.payment_client.get(
                "/payment", headers={"X-Request-ID": request_id_context.get() or ""}
            )
            upstream.raise_for_status()
            result = PaymentResult.model_validate_json(upstream.content)
        except httpx.TimeoutException as exc:
            logger.error(
                "Payment service timed out",
                extra={"event": "payment.failed", "error_type": type(exc).__name__},
            )
            raise HTTPException(
                status_code=504, detail="Payment service timed out"
            ) from exc
        except (httpx.HTTPError, ValidationError) as exc:
            logger.error(
                "Payment service unavailable or returned an invalid response",
                extra={"event": "payment.failed", "error_type": type(exc).__name__},
            )
            raise HTTPException(
                status_code=502, detail="Payment service unavailable"
            ) from exc
        logger.info(
            "Mock payment approved",
            extra={"event": "payment.approved", "payment_id": str(result.payment_id)},
        )
        return result

    @application.get(
        "/error", responses={500: {"description": "Intentional lab error"}}
    )
    async def error():
        raise RuntimeError("Intentional ShopSphere failure for the observability lab")

    return application


app = create_app()
