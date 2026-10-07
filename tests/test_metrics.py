"""Metric contracts: bounded labels, failures, timings, and app isolation."""

from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import Database
from app.main import create_app
from app.metrics import Metrics
from app.store import simulate_slow_query
from payment.main import create_app as create_payment


def samples(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    return [
        sample
        for family in text_string_to_metric_families(response.text)
        for sample in family.samples
    ]


def value(records, name, **labels):
    return sum(
        sample.value
        for sample in records
        if sample.name == name
        and all(sample.labels.get(key) == val for key, val in labels.items())
    )


def test_labels_merge_ids_and_unknown_paths_and_exclude_scrapes(db_settings):
    with TestClient(create_app(settings=db_settings)) as client:
        for _ in range(3):
            assert (
                client.get(
                    f"/orders/{uuid4()}?secret=private",
                    headers={"X-Request-ID": uuid4().hex},
                ).status_code
                == 404
            )
            assert client.get(f"/unknown-{uuid4()}").status_code == 404
        assert client.request("CUSTOM-METHOD", "/unknown").status_code == 404
        before, after = samples(client), samples(client)
        assert (
            value(after, "http_requests_total")
            == value(before, "http_requests_total")
            == 7
        )
        assert value(after, "http_requests_total", route="/orders/{id}") == 3
        assert value(after, "http_requests_total", route="unmatched") == 4
        assert value(after, "http_requests_total", method="OTHER") == 1
        assert value(after, "application_errors_total") == 0
        for sample in after:
            assert not {"request_id", "order_id", "path", "query", "sql"}.intersection(
                sample.labels
            )
            assert "private" not in str(sample.labels)


def test_handled_and_unhandled_server_errors_count_once(db_settings):
    def timeout(request):
        raise httpx.ReadTimeout("test timeout", request=request)

    app = create_app(
        settings=db_settings, payment_transport=httpx.MockTransport(timeout)
    )
    with TestClient(app) as client:
        assert client.get("/error").status_code == 500
        assert client.get("/payment").status_code == 504
        assert client.get("/slow-query?seconds=-1").status_code == 422
        records = samples(client)
        assert value(records, "http_requests_total", status="500") == 1
        assert value(records, "http_requests_total", status="504") == 1
        assert value(records, "application_errors_total") == 2
        assert value(records, "http_request_duration_seconds_count") == 3


def test_http_and_sql_durations_include_real_database_wait(db_settings):
    with TestClient(create_app(settings=db_settings)) as client:
        before = samples(client)
        assert client.get("/slow-query?seconds=0.1").status_code == 200
        after = samples(client)
        sql_duration = value(after, "database_query_duration_seconds_sum") - value(
            before, "database_query_duration_seconds_sum"
        )
        http_duration = value(
            after, "http_request_duration_seconds_sum", route="/slow-query"
        )
        assert http_duration >= sql_duration >= 0.1
        assert (
            value(after, "database_query_duration_seconds_count", outcome="success")
            - value(before, "database_query_duration_seconds_count", outcome="success")
            == 1
        )


def test_failed_sql_has_duration_without_success_double_count(db_settings):
    metrics = Metrics("order-api")
    database = Database(db_settings, metrics=metrics)
    try:
        with pytest.raises(DBAPIError):
            with database.sessions.begin() as session:
                session.execute(text("SET LOCAL statement_timeout = '50ms'"))
                simulate_slow_query(session, 0.2)
        records = [
            sample for family in metrics.registry.collect() for sample in family.samples
        ]
        assert (
            value(
                records,
                "database_query_duration_seconds_count",
                operation="SELECT",
                outcome="error",
            )
            == 1
        )
        assert (
            value(
                records,
                "database_query_duration_seconds_count",
                operation="SELECT",
                outcome="success",
            )
            == 0
        )
        assert (
            value(records, "database_query_duration_seconds_sum", outcome="error")
            >= 0.04
        )
    finally:
        database.close()


def test_registries_are_isolated_between_instances_and_services(db_settings):
    with (
        TestClient(create_app(settings=db_settings)) as first,
        TestClient(create_app(settings=db_settings)) as second,
        TestClient(create_payment()) as payment,
    ):
        assert first.get("/products").status_code == 200
        assert payment.get("/payment").status_code == 200
        assert value(samples(first), "http_requests_total", service="order-api") == 1
        assert value(samples(second), "http_requests_total") == 0
        assert (
            value(samples(payment), "http_requests_total", service="mock-payment") == 1
        )
