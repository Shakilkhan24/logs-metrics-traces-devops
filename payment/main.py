"""A separate HTTP dependency; no real payment processing takes place."""

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI

from app.logging import RequestLoggingMiddleware, configure_logging
from app.metrics import Metrics, MetricsMiddleware
from app.schemas import PaymentResult

logger = logging.getLogger("shopsphere.mock-payment")


def create_app() -> FastAPI:
    metrics = Metrics("mock-payment")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging("mock-payment")
        logger.info("Mock payment started", extra={"event": "service.started"})
        try:
            yield
        finally:
            logger.info("Mock payment stopped", extra={"event": "service.stopped"})

    application = FastAPI(title="ShopSphere Mock Payment", lifespan=lifespan)
    application.add_middleware(RequestLoggingMiddleware, service="mock-payment")
    application.add_middleware(MetricsMiddleware, metrics=metrics)
    application.state.metrics = metrics
    application.add_api_route("/metrics", metrics.response, include_in_schema=False)

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"service": "mock-payment", "status": "ok"}

    @application.get("/payment", response_model=PaymentResult)
    async def payment() -> PaymentResult:
        result = PaymentResult(status="approved", payment_id=uuid4(), simulated=True)
        logger.info(
            "Simulated payment approved",
            extra={"event": "payment.approved", "payment_id": str(result.payment_id)},
        )
        return result

    return application


app = create_app()
