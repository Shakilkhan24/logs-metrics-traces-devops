"""ShopSphere HTTP API. Start with: python -m uvicorn app.main:app."""

import logging
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import ValidationError

from app.config import Settings
from app.logging import (
    RequestLoggingMiddleware,
    configure_logging,
    request_id_context,
)
from app.schemas import Order, OrderCreate, PaymentResult, Product
from app.store import MemoryStore, UnknownProductError

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
        application.state.store = MemoryStore()
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

    application = FastAPI(
        title="ShopSphere Order API",
        version="0.2.0",
        description="Phase 2: in-memory orders, JSON logs, and a mock HTTP dependency.",
        lifespan=lifespan,
    )
    application.add_middleware(RequestLoggingMiddleware, service="order-api")

    @application.get("/")
    async def root() -> dict[str, str | int]:
        return {"service": "order-api", "status": "ok", "phase": 2, "storage": "memory"}

    @application.get("/products", response_model=list[Product])
    async def products(request: Request):
        return list(request.app.state.store.products.values())

    @application.post("/orders", response_model=Order, status_code=201)
    async def create_order(payload: OrderCreate, request: Request, response: Response):
        try:
            order = request.app.state.store.create_order(payload)
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
    async def get_order(id: UUID, request: Request):
        order = request.app.state.store.orders.get(id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return order

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
