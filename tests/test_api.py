import asyncio
import json
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.logging import request_id_context
from app.main import create_app
from payment.main import create_app as create_payment_app


@pytest.fixture
def client():
    with TestClient(create_app(settings=Settings())) as client:
        yield client


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def approved_response():
    return httpx.Response(
        200,
        json={
            "service": "mock-payment",
            "status": "approved",
            "payment_id": str(uuid4()),
            "simulated": True,
        },
    )


def test_create_and_retrieve_order_with_server_calculated_prices(client):
    products = client.get("/products").json()
    assert len(products) == 3
    payload = {
        "items": [{"product_id": 1, "quantity": 2}, {"product_id": 3, "quantity": 1}]
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 201
    order = response.json()
    UUID(order["id"])
    assert order["total_cents"] == 6297
    assert order["currency"] == "USD"
    assert order["status"] == "created"
    assert order["created_at"].endswith(("Z", "+00:00"))
    assert client.get(response.headers["location"]).json() == order


@pytest.mark.parametrize(
    "payload",
    [
        {"items": []},
        {"items": [{"product_id": 1, "quantity": 0}]},
        {"items": [{"product_id": 1, "quantity": -1}]},
        {"items": [{"product_id": 1, "quantity": 101}]},
        {"items": [{"product_id": 1, "quantity": 1.5}]},
        {"items": [{"product_id": 1, "quantity": True}]},
        {"items": [{"product_id": 1, "quantity": 1, "unit_price_cents": 1}]},
        {"items": [{"product_id": 1, "quantity": 1}], "total_cents": 1},
        {"items": [{"product_id": 1, "quantity": 1}] * 21},
    ],
)
def test_invalid_orders_do_not_mutate_store(client, payload):
    assert client.post("/orders", json=payload).status_code == 422
    assert not client.app.state.store.orders


def test_unknown_product_does_not_create_partial_order(client):
    response = client.post(
        "/orders",
        json={
            "items": [
                {"product_id": 1, "quantity": 1},
                {"product_id": 999, "quantity": 1},
            ]
        },
    )
    assert response.status_code == 404
    assert not client.app.state.store.orders


def test_order_not_found_and_invalid_id_are_distinct(client):
    assert client.get(f"/orders/{uuid4()}").status_code == 404
    assert client.get("/orders/not-a-uuid").status_code == 422


def test_order_store_resets_when_application_restarts():
    application = create_app(settings=Settings())
    with TestClient(application) as client:
        response = client.post(
            "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
        )
        location = response.headers["location"]
    with TestClient(application) as client:
        assert client.get(location).status_code == 404


def test_application_logging_correlates_business_and_request_events(capsys):
    with TestClient(create_app(settings=Settings())) as client:
        capsys.readouterr()
        response = client.post(
            "/orders?token=do-not-log-this",
            headers={
                "X-Request-ID": "checkout-demo-1",
                "Authorization": "secret-header",
            },
            json={"items": [{"product_id": 1, "quantity": 2}]},
        )
        assert response.headers["x-request-id"] == "checkout-demo-1"
        records = events(capsys)
        business = next(event for event in records if event["event"] == "order.created")
        completed = next(
            event for event in records if event["event"] == "request.completed"
        )
        assert business["request_id"] == completed["request_id"] == "checkout-demo-1"
        assert business["order_id"] == response.json()["id"]
        assert completed["route"] == "/orders"
        assert completed["status_code"] == 201
        assert completed["duration_ms"] >= 0
        assert all(
            event["service"] == "order-api" and event["trace_id"] is None
            for event in records
        )
        assert "secret-header" not in json.dumps(records)
        assert "do-not-log-this" not in json.dumps(records)


def test_intentional_exception_has_safe_response_and_correlated_error_logs(capsys):
    with TestClient(create_app(settings=Settings())) as client:
        capsys.readouterr()
        response = client.get("/error", headers={"X-Request-ID": "failure-demo"})
        assert response.status_code == 500
        assert response.json() == {
            "detail": "Internal server error",
            "request_id": "failure-demo",
        }
        assert response.headers["x-request-id"] == "failure-demo"
        records = events(capsys)
        failure = next(event for event in records if event["event"] == "request.failed")
        assert failure["error_type"] == "RuntimeError"
        assert "RuntimeError" in failure["exception"]
        completed = next(
            event for event in records if event["event"] == "request.completed"
        )
        assert completed["status_code"] == 500
        assert all(event["request_id"] == "failure-demo" for event in records)
        assert all(event["level"] == "ERROR" for event in records)
        assert client.get("/").status_code == 200


@pytest.mark.parametrize("request_id", ["contains spaces", "x" * 65, ""])
def test_invalid_request_id_is_replaced(client, request_id):
    response = client.get("/", headers={"X-Request-ID": request_id})
    generated = response.headers["x-request-id"]
    assert len(generated) == 32
    UUID(generated)


def test_mock_payment_call_and_request_id_cross_service_boundary(capsys):
    payment_app = create_payment_app()
    with TestClient(payment_app):
        api = create_app(
            settings=Settings(), payment_transport=httpx.ASGITransport(app=payment_app)
        )
        with TestClient(api) as client:
            capsys.readouterr()
            response = client.get(
                "/payment", headers={"X-Request-ID": "shared-request"}
            )
            assert response.status_code == 200
            assert response.json()["simulated"] is True
            assert response.json()["status"] == "approved"
            records = events(capsys)
    completed = [event for event in records if event["event"] == "request.completed"]
    assert {event["service"] for event in completed} == {"order-api", "mock-payment"}
    assert all(event["request_id"] == "shared-request" for event in records)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("timeout", 504),
        ("connection", 502),
        ("status", 502),
        ("json", 502),
        ("schema", 502),
    ],
)
def test_payment_dependency_failures_have_explicit_status_codes(
    failure, expected, capsys
):
    def downstream(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive upstream details", request=request)
        if failure == "connection":
            raise httpx.ConnectError("sensitive upstream details", request=request)
        if failure == "status":
            return httpx.Response(503, text="sensitive upstream details")
        if failure == "json":
            return httpx.Response(200, text="not JSON")
        return httpx.Response(200, json={"status": "approved"})

    api = create_app(
        settings=Settings(), payment_transport=httpx.MockTransport(downstream)
    )
    with TestClient(api) as client:
        capsys.readouterr()
        response = client.get(
            "/payment", headers={"X-Request-ID": "dependency-failure"}
        )
        assert response.status_code == expected
        records = events(capsys)
        assert "sensitive upstream details" not in response.text
        failure_event = next(
            event for event in records if event["event"] == "payment.failed"
        )
        assert failure_event["request_id"] == "dependency-failure"
        assert records[-1]["status_code"] == expected


def test_concurrent_requests_keep_separate_context(capsys):
    async def scenario():
        observed = []

        async def downstream(request):
            before = request_id_context.get()
            await asyncio.sleep(0.01)
            observed.append(
                (before, request_id_context.get(), request.headers["x-request-id"])
            )
            return approved_response()

        api = create_app(
            settings=Settings(), payment_transport=httpx.MockTransport(downstream)
        )
        async with api.router.lifespan_context(api):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api), base_url="http://test"
            ) as client:
                responses = await asyncio.gather(
                    *(
                        client.get(
                            "/payment", headers={"X-Request-ID": f"parallel-{n}"}
                        )
                        for n in range(8)
                    )
                )
            assert all(response.status_code == 200 for response in responses)
            assert {before for before, _, _ in observed} == {
                f"parallel-{n}" for n in range(8)
            }
            assert all(before == after == sent for before, after, sent in observed)
            assert request_id_context.get() is None

    asyncio.run(scenario())
    records = events(capsys)
    assert all(
        event["request_id"] is None
        for event in records
        if event["event"] == "service.stopped"
    )


def test_validation_and_not_found_requests_are_logged(capsys):
    with TestClient(create_app(settings=Settings())) as client:
        capsys.readouterr()
        assert (
            client.post(
                "/orders",
                content="{broken",
                headers={"Content-Type": "application/json"},
            ).status_code
            == 422
        )
        assert client.get("/not-implemented").status_code == 404
        completed = [
            event for event in events(capsys) if event["event"] == "request.completed"
        ]
        assert [event["status_code"] for event in completed] == [422, 404]
        assert all(event["level"] == "WARNING" for event in completed)


def test_environment_configuration_is_validated(monkeypatch):
    monkeypatch.setenv("PAYMENT_BASE_URL", "http://payment:8001")
    monkeypatch.setenv("PAYMENT_TIMEOUT_SECONDS", "3")
    settings = Settings.from_env()
    assert str(settings.payment_base_url) == "http://payment:8001/"
    assert settings.payment_timeout_seconds == 3
    monkeypatch.setenv("PAYMENT_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError):
        Settings.from_env()
