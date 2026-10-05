"""Temporary, per-process storage for learning HTTP before persistence."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.schemas import Order, OrderCreate, OrderItem, Product


class UnknownProductError(Exception):
    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"Product {product_id} not found")


class MemoryStore:
    def __init__(self) -> None:
        self.products = {
            product.id: product
            for product in (
                Product(id=1, name="ShopSphere T-shirt", price_cents=2499),
                Product(id=2, name="ShopSphere Backpack", price_cents=4999),
                Product(id=3, name="ShopSphere Mug", price_cents=1299),
            )
        }
        self.orders: dict[UUID, Order] = {}

    def create_order(self, payload: OrderCreate) -> Order:
        items = []
        for requested in payload.items:
            product = self.products.get(requested.product_id)
            if product is None:
                raise UnknownProductError(requested.product_id)
            items.append(
                OrderItem(
                    product_id=product.id,
                    name=product.name,
                    quantity=requested.quantity,
                    unit_price_cents=product.price_cents,
                    subtotal_cents=product.price_cents * requested.quantity,
                )
            )
        order = Order(
            id=uuid4(),
            items=items,
            total_cents=sum(item.subtotal_cents for item in items),
            created_at=datetime.now(UTC),
        )
        # Only store after every item has been validated and priced.
        self.orders[order.id] = order
        return order
