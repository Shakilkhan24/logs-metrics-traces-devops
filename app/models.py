"""PostgreSQL tables: products, orders, and immutable order item snapshots."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProductRecord(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_cents > 0", name="positive_product_price"),
        CheckConstraint("currency = 'USD'", name="product_currency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))
    price_cents: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3), default="USD")


class OrderRecord(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_cents > 0", name="positive_order_total"),
        CheckConstraint("currency = 'USD'", name="order_currency"),
        CheckConstraint("status = 'created'", name="order_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    total_cents: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(16), default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    items: Mapped[list["OrderItemRecord"]] = relationship(
        cascade="all, delete-orphan",
        order_by="OrderItemRecord.line_number",
        lazy="raise",
    )


class OrderItemRecord(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity BETWEEN 1 AND 100", name="valid_item_quantity"),
        CheckConstraint("unit_price_cents > 0", name="positive_item_price"),
        CheckConstraint(
            "subtotal_cents = quantity * unit_price_cents", name="correct_item_subtotal"
        ),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True
    )
    line_number: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int]
    unit_price_cents: Mapped[int]
    subtotal_cents: Mapped[int]
