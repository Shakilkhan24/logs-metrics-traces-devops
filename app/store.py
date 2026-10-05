"""Request-local SQLAlchemy transactions backed by shared PostgreSQL state."""

from time import perf_counter
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.models import OrderItemRecord, OrderRecord, ProductRecord
from app.schemas import Order, OrderCreate, Product


class UnknownProductError(Exception):
    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"Product {product_id} not found")


def simulate_slow_query(session: Session, seconds: float) -> float:
    started = perf_counter()
    session.execute(
        text("SELECT pg_sleep(:seconds)").execution_options(
            query_name="lab.slow_query"
        ),
        {"seconds": seconds},
    )
    return round((perf_counter() - started) * 1000, 3)


class PostgresStore:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def list_products(self) -> list[Product]:
        with self.sessions.begin() as session:
            rows = session.scalars(select(ProductRecord).order_by(ProductRecord.id))
            return [Product.model_validate(row) for row in rows]

    def create_order(self, payload: OrderCreate, db_delay_seconds: float = 0) -> Order:
        with self.sessions.begin() as session:
            if db_delay_seconds:
                simulate_slow_query(session, db_delay_seconds)
            product_ids = {item.product_id for item in payload.items}
            products = {
                product.id: product
                for product in session.scalars(
                    select(ProductRecord).where(ProductRecord.id.in_(product_ids))
                )
            }
            items = []
            for index, requested in enumerate(payload.items):
                product = products.get(requested.product_id)
                if product is None:
                    raise UnknownProductError(requested.product_id)
                items.append(
                    OrderItemRecord(
                        line_number=index,
                        product_id=product.id,
                        name=product.name,
                        quantity=requested.quantity,
                        unit_price_cents=product.price_cents,
                        subtotal_cents=product.price_cents * requested.quantity,
                    )
                )
            order = OrderRecord(
                items=items, total_cents=sum(item.subtotal_cents for item in items)
            )
            session.add(order)
            session.flush()
            response = Order.model_validate(order)
        # The transaction commits BEFORE the route logs success or returns 201.
        return response

    def get_order(self, order_id: UUID) -> Order | None:
        with self.sessions.begin() as session:
            row = session.scalar(
                select(OrderRecord)
                .where(OrderRecord.id == order_id)
                .options(selectinload(OrderRecord.items))
            )
            return Order.model_validate(row) if row is not None else None

    def slow_query(self, seconds: float) -> float:
        with self.sessions.begin() as session:
            return simulate_slow_query(session, seconds)
