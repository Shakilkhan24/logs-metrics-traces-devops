"""HTTP contracts, kept separate from SQLAlchemy persistence models."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PositiveInteger = Annotated[int, Field(strict=True, gt=0)]


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PositiveInteger
    name: str
    price_cents: PositiveInteger
    currency: Literal["USD"] = "USD"


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: PositiveInteger
    quantity: Annotated[int, Field(strict=True, ge=1, le=100)]


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemCreate] = Field(min_length=1, max_length=20)


class OrderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    name: str
    quantity: int
    unit_price_cents: int
    subtotal_cents: int


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    items: list[OrderItem]
    total_cents: int
    currency: Literal["USD"] = "USD"
    status: Literal["created"] = "created"
    created_at: datetime


class PaymentResult(BaseModel):
    service: Literal["mock-payment"] = "mock-payment"
    status: Literal["approved"]
    payment_id: UUID
    simulated: Literal[True]
