"""Real PostgreSQL tests: a private container and a fresh database per test."""

import subprocess
import time
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database import Database
from app.logging import configure_logging


@pytest.fixture(scope="session")
def postgres_server():
    name = f"shopsphere-tests-{uuid4().hex[:12]}"
    configuration = Path(__file__).resolve().parents[1] / "postgres/postgresql.conf"
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--tmpfs",
            "/var/lib/postgresql:rw",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            "POSTGRES_USER=shopsphere_test",
            "--env",
            "POSTGRES_PASSWORD=test_only",
            "--env",
            "POSTGRES_DB=postgres",
            "--mount",
            f"type=bind,source={configuration},target=/etc/postgresql/lab.conf,readonly",
            "postgres:18.6-bookworm",
            "postgres",
            "-c",
            "config_file=/etc/postgresql/lab.conf",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        address = subprocess.check_output(
            ["docker", "port", name, "5432/tcp"], text=True
        ).strip()
        url = f"postgresql://shopsphere_test:test_only@{address}/postgres"
        deadline = time.monotonic() + 60
        while True:
            try:
                with psycopg.connect(url, connect_timeout=1):
                    break
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    pytest.fail(
                        "The private PostgreSQL test container did not become ready"
                    )
                time.sleep(0.2)
        yield {"name": name, "url": url}
    finally:
        subprocess.run(
            ["docker", "rm", "--force", name], check=True, capture_output=True
        )


@pytest.fixture(autouse=True)
def db_settings(postgres_server, monkeypatch):
    name = f"test_{uuid4().hex}"
    with psycopg.connect(postgres_server["url"], autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = make_url(postgres_server["url"]).set(
        drivername="postgresql+psycopg", database=name
    )
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    settings = Settings.from_env()
    configure_logging("order-api")
    database = Database(settings)
    try:
        database.initialize()
        yield settings
    finally:
        database.close()
        # Only the uniquely named database created by this fixture is removed.
        with psycopg.connect(postgres_server["url"], autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
def sql_connection(db_settings):
    url = make_url(db_settings.database_url.get_secret_value()).set(
        drivername="postgresql"
    )
    with psycopg.connect(
        url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        yield connection


@pytest.fixture
def order_counts(sql_connection):
    def counts():
        return sql_connection.execute(
            "SELECT (SELECT count(*) FROM orders), (SELECT count(*) FROM order_items)"
        ).fetchone()

    return counts
