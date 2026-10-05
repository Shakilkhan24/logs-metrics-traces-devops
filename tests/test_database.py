import asyncio
import json
import subprocess
from time import perf_counter

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import Database
from app.main import create_app
from app.store import simulate_slow_query


def test_order_is_visible_to_another_api_instance(db_settings):
    with TestClient(create_app(settings=db_settings)) as first:
        created = first.post(
            "/orders", json={"items": [{"product_id": 1, "quantity": 2}]}
        )
        assert created.status_code == 201
        with TestClient(create_app(settings=db_settings)) as second:
            assert second.get(created.headers["location"]).json() == created.json()


def test_failed_item_insert_rolls_back_order_and_releases_session(
    db_settings, sql_connection, order_counts, capsys
):
    sql_connection.execute(
        "ALTER TABLE order_items ADD CONSTRAINT test_failure CHECK (line_number < 1)"
    )
    with TestClient(create_app(settings=db_settings)) as client:
        capsys.readouterr()
        failed = client.post(
            "/orders",
            headers={"X-Request-ID": "rollback-demo"},
            json={
                "items": [
                    {"product_id": 1, "quantity": 1},
                    {"product_id": 2, "quantity": 1},
                ]
            },
        )
        assert failed.status_code == 503
        assert failed.json() == {"detail": "Database unavailable"}
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert not any(event["event"] == "order.created" for event in records)
        assert any(
            event["event"] == "database.query_failed" and event["sqlstate"] == "23514"
            for event in records
        )
        assert order_counts() == (0, 0)
        assert (
            client.post(
                "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
            ).status_code
            == 201
        )
        assert order_counts() == (1, 1)


def test_order_keeps_original_price_after_catalogue_changes(
    db_settings, sql_connection
):
    with TestClient(create_app(settings=db_settings)) as client:
        created = client.post(
            "/orders", json={"items": [{"product_id": 1, "quantity": 2}]}
        )
        sql_connection.execute(
            "UPDATE products SET price_cents = 9999, name = 'New name' WHERE id = 1"
        )
        assert client.get(created.headers["location"]).json() == created.json()
        assert client.get("/products").json()[0]["price_cents"] == 9999


def test_repeated_initialization_preserves_data(db_settings, order_counts):
    with TestClient(create_app(settings=db_settings)) as client:
        created = client.post(
            "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
        )
        database = Database(db_settings)
        try:
            database.initialize()
        finally:
            database.close()
        assert order_counts() == (1, 1)
        assert len(client.get("/products").json()) == 3
        assert client.get(created.headers["location"]).json() == created.json()


def test_database_delay_appears_in_application_and_postgres_logs(
    db_settings, postgres_server, capsys
):
    with TestClient(create_app(settings=db_settings)) as client:
        capsys.readouterr()
        started = perf_counter()
        response = client.get(
            "/slow-query?seconds=0.3", headers={"X-Request-ID": "slow-test"}
        )
        assert response.status_code == 200
        assert perf_counter() - started >= 0.3
        assert response.json()["duration_ms"] >= 300
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        query = next(
            event for event in records if event.get("query_name") == "lab.slow_query"
        )
        assert query["level"] == "WARNING"
        assert query["request_id"] == "slow-test"
        assert records[-1]["duration_ms"] >= query["duration_ms"]
    output = subprocess.check_output(
        [
            "docker",
            "exec",
            postgres_server["name"],
            "sh",
            "-c",
            'cat "$PGDATA"/log/*.json',
        ],
        text=True,
    )
    logs = [json.loads(line) for line in output.splitlines()]
    assert any(
        "pg_sleep" in event.get("message", "")
        and "slow-test" in event.get("message", "")
        for event in logs
    )
    assert any("connection authorized" in event.get("message", "") for event in logs)


@pytest.mark.parametrize("seconds", ["-1", "5.1", "nan", "inf"])
def test_database_delay_bounds_are_enforced(db_settings, seconds):
    with TestClient(create_app(settings=db_settings)) as client:
        assert client.get(f"/slow-query?seconds={seconds}").status_code == 422
        assert (
            client.post(
                f"/orders?db_delay_seconds={seconds}",
                json={"items": [{"product_id": 1, "quantity": 1}]},
            ).status_code
            == 422
        )


def test_checkout_delay_is_a_real_database_wait(db_settings, capsys):
    with TestClient(create_app(settings=db_settings)) as client:
        capsys.readouterr()
        response = client.post(
            "/orders?db_delay_seconds=0.1",
            headers={"X-Request-ID": "slow-checkout"},
            json={"items": [{"product_id": 1, "quantity": 1}]},
        )
        assert response.status_code == 201
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        query = next(
            event for event in records if event.get("query_name") == "lab.slow_query"
        )
        assert query["duration_ms"] >= 100
        assert query["request_id"] == "slow-checkout"
        assert any(event["event"] == "order.created" for event in records)


def test_statement_timeout_rolls_back_and_connection_remains_usable(db_settings):
    database = Database(db_settings)
    try:
        with pytest.raises(DBAPIError) as error:
            with database.sessions.begin() as session:
                session.execute(text("SET LOCAL statement_timeout = '50ms'"))
                simulate_slow_query(session, 0.2)
        assert error.value.orig.sqlstate == "57014"
        database.check_ready()
    finally:
        database.close()


def test_concurrent_orders_use_independent_transactions(db_settings, order_counts):
    async def scenario():
        api = create_app(settings=db_settings)
        async with api.router.lifespan_context(api):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api), base_url="http://test"
            ) as client:
                responses = await asyncio.gather(
                    *(
                        client.post(
                            "/orders",
                            json={"items": [{"product_id": 1, "quantity": 1}]},
                        )
                        for _ in range(8)
                    )
                )
                assert all(response.status_code == 201 for response in responses)
                assert len({response.json()["id"] for response in responses}) == 8

    asyncio.run(scenario())
    assert order_counts() == (8, 8)
