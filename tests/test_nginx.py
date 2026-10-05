"""Exercise the checked-in proxy configuration with real NGINX and Uvicorn."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_ready(process, url, error_path):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Server exited before readiness:\n{error_path.read_text()}")
        try:
            if httpx.get(url, timeout=0.5, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    pytest.fail(f"Server readiness timed out:\n{error_path.read_text()}")


def read_events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def access_event(lab, request_id):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        for event in read_events(lab["access"]):
            if event["request_id"] == request_id:
                return event
        time.sleep(0.01)
    pytest.fail(f"No proxy access event for {request_id}")


@pytest.fixture
def proxy_factory(tmp_path, db_settings):
    if shutil.which(os.getenv("NGINX_BIN", "nginx")) is None:
        pytest.fail("NGINX must be installed for the Phase 4 integration tests")
    processes = []
    streams = []

    def start(read_timeout="30s"):
        prefix = tmp_path / f"proxy-{len(processes)}"
        prefix.mkdir()
        ports = set()
        while len(ports) < 3:
            ports.add(free_port())
        proxy_port, api_port, payment_port = sorted(ports)
        configuration = (ROOT / "nginx/nginx.conf").read_text()
        configuration = configuration.replace(
            "listen 127.0.0.1:8088;", f"listen 127.0.0.1:{proxy_port};"
        ).replace("server 127.0.0.1:8000;", f"server 127.0.0.1:{api_port};")
        configuration = configuration.replace(
            "proxy_read_timeout 30s;", f"proxy_read_timeout {read_timeout};"
        )
        (prefix / "nginx.conf").write_text(configuration)
        shutil.copyfile(ROOT / "nginx/manage.sh", prefix / "manage.sh")
        paths = {name: prefix / f"{name}.jsonl" for name in ["api", "payment"]}
        error_path = prefix / "process.stderr"
        errors = error_path.open("w")
        streams.append(errors)
        environment = dict(
            os.environ,
            DATABASE_URL=db_settings.database_url.get_secret_value(),
            PAYMENT_BASE_URL=f"http://127.0.0.1:{payment_port}",
        )

        def start_service(name, module, port):
            output = paths[name].open("a")
            streams.append(output)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    module,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                    "--proxy-headers",
                    "--forwarded-allow-ips",
                    "127.0.0.1",
                ],
                cwd=ROOT,
                env=environment,
                stdout=output,
                stderr=errors,
            )
            processes.append(process)
            wait_ready(process, f"http://127.0.0.1:{port}/", error_path)
            return process

        payment = start_service("payment", "payment.main:app", payment_port)
        api = start_service("api", "app.main:app", api_port)
        nginx = subprocess.Popen(
            ["bash", str(prefix / "manage.sh"), "foreground"],
            cwd=ROOT,
            env=environment,
            stdout=errors,
            stderr=errors,
        )
        processes.append(nginx)
        url = f"http://127.0.0.1:{proxy_port}"
        wait_ready(nginx, f"{url}/proxy-health", error_path)
        return {
            "url": url,
            "api": api,
            "payment": payment,
            "nginx": nginx,
            "prefix": prefix,
            "access": prefix / "runtime/access.jsonl",
            "error": prefix / "runtime/error.log",
            "api_log": paths["api"],
            "payment_log": paths["payment"],
            "restart_api": lambda: start_service("api", "app.main:app", api_port),
        }

    try:
        yield start
    finally:
        # Only processes created by this fixture are signalled.
        for process in reversed(processes):
            stop_process(process)
        for stream in streams:
            stream.close()


def test_proxy_preserves_order_body_location_docs_and_payment_correlation(
    proxy_factory,
):
    lab = proxy_factory()
    with httpx.Client(base_url=lab["url"], trust_env=False) as client:
        created = client.post(
            "/orders",
            headers={"X-Request-ID": "proxy-order"},
            json={"items": [{"product_id": 1, "quantity": 2}]},
        )
        assert created.status_code == 201
        assert created.json()["total_cents"] == 4998
        assert created.headers.get_list("x-request-id") == ["proxy-order"]
        assert client.get(created.headers["location"]).json() == created.json()
        assert client.get("/docs").status_code == 200
        assert "/orders" in client.get("/openapi.json").json()["paths"]
        redirected = client.get(
            "/products/",
            headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "203.0.113.9"},
        )
        assert redirected.status_code == 307
        assert redirected.headers["location"] == f"{lab['url']}/products"
        payment = client.get("/payment", headers={"X-Request-ID": "proxy-payment"})
        assert payment.status_code == 200 and payment.json()["simulated"] is True
    assert access_event(lab, "proxy-order")["upstream_status"] == "201"
    assert access_event(lab, "proxy-payment")["status_code"] == 200
    for path in [lab["api_log"], lab["payment_log"]]:
        assert any(
            event["request_id"] == "proxy-payment" for event in read_events(path)
        )


@pytest.mark.parametrize(
    "incoming", [None, "valid_request-4", "invalid spaces", "x" * 65]
)
def test_proxy_request_ids_match_application_and_json_escapes_paths(
    proxy_factory, incoming
):
    lab = proxy_factory()
    headers = {"Authorization": "not-for-access-log"}
    if incoming is not None:
        headers["X-Request-ID"] = incoming
    with httpx.Client(base_url=lab["url"], trust_env=False) as client:
        response = client.get("/missing%22path?token=hidden-query", headers=headers)
    assert response.status_code == 404
    request_id = response.headers["x-request-id"]
    if incoming == "valid_request-4":
        assert request_id == incoming
    else:
        assert len(request_id) == 32 and int(request_id, 16) >= 0
    event = access_event(lab, request_id)
    assert event["path"] == '/missing"path'
    assert event["upstream_status"] == "404"
    assert "hidden-query" not in lab["access"].read_text()
    assert "not-for-access-log" not in lab["access"].read_text()
    assert any(
        event["request_id"] == request_id for event in read_events(lab["api_log"])
    )


def test_proxy_preserves_application_error_responses(proxy_factory):
    lab = proxy_factory()
    with httpx.Client(base_url=lab["url"], trust_env=False) as client:
        failure = client.get("/error", headers={"X-Request-ID": "app-error"})
        assert failure.status_code == 500
        assert failure.json() == {
            "detail": "Internal server error",
            "request_id": "app-error",
        }
        assert failure.headers.get_list("x-request-id") == ["app-error"]
        assert client.post("/orders", json={"items": []}).status_code == 422
        stop_process(lab["payment"])
        unavailable = client.get("/payment", headers={"X-Request-ID": "payment-down"})
        assert unavailable.status_code == 502
        assert unavailable.json() == {"detail": "Payment service unavailable"}
    assert access_event(lab, "app-error")["upstream_status"] == "500"
    assert access_event(lab, "payment-down")["upstream_status"] == "502"
    assert "connect() failed" not in lab["error"].read_text()


def test_unavailable_api_produces_proxy_error_and_recovers(proxy_factory):
    lab = proxy_factory()
    stop_process(lab["api"])
    with httpx.Client(base_url=lab["url"], trust_env=False) as client:
        response = client.get("/products", headers={"X-Request-ID": "api-down"})
        assert response.status_code == 502
        assert response.headers.get_list("x-request-id") == ["api-down"]
        assert "text/html" in response.headers["content-type"]
        event = access_event(lab, "api-down")
        error = lab["error"].read_text()
        assert "connect() failed" in error
        assert f"*{event['connection']} " in error
        assert not any(
            event["request_id"] == "api-down" for event in read_events(lab["api_log"])
        )
        health = client.get("/proxy-health", headers={"X-Request-ID": "proxy-only"})
        assert health.status_code == 200
        assert access_event(lab, "proxy-only")["upstream_status"] in ("", "-")
        lab["restart_api"]()
        assert client.get("/products").status_code == 200


def test_slow_sql_is_visible_at_proxy_api_and_database(proxy_factory, postgres_server):
    lab = proxy_factory()
    with httpx.Client(base_url=lab["url"], timeout=10, trust_env=False) as client:
        response = client.get(
            "/slow-query?seconds=0.3", headers={"X-Request-ID": "proxy-slow"}
        )
    assert response.status_code == 200
    assert response.json()["requested_seconds"] == 0.3
    event = access_event(lab, "proxy-slow")
    assert float(event["upstream_response_seconds"]) >= 0.3
    assert event["request_duration_seconds"] >= 0.3
    assert any(
        event["request_id"] == "proxy-slow"
        and event.get("query_name") == "lab.slow_query"
        for event in read_events(lab["api_log"])
    )
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
    assert any(
        "proxy-slow" in event.get("message", "")
        and "pg_sleep" in event.get("message", "")
        for event in map(json.loads, output.splitlines())
    )


def test_proxy_timeout_has_request_id_and_native_error(proxy_factory):
    # Only this temporary copy uses 100ms. The checked-in timeout stays 30s.
    lab = proxy_factory(read_timeout="100ms")
    with httpx.Client(base_url=lab["url"], trust_env=False) as client:
        response = client.get(
            "/slow-query?seconds=0.3", headers={"X-Request-ID": "proxy-timeout"}
        )
    assert response.status_code == 504
    assert response.headers.get_list("x-request-id") == ["proxy-timeout"]
    assert access_event(lab, "proxy-timeout")["status_code"] == 504
    assert "upstream timed out" in lab["error"].read_text()


def test_proxy_rejects_oversized_body_before_api(proxy_factory):
    lab = proxy_factory()
    with httpx.Client(base_url=lab["url"], trust_env=False) as client:
        response = client.post(
            "/orders",
            content=b"x" * (1024 * 1024 + 1),
            headers={"X-Request-ID": "too-large", "Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.headers.get_list("x-request-id") == ["too-large"]
    assert access_event(lab, "too-large")["upstream_status"] in ("", "-")
    assert not any(
        event["request_id"] == "too-large" for event in read_events(lab["api_log"])
    )


def test_reload_checks_configuration_before_signalling_and_stop_targets_lab(
    proxy_factory,
):
    lab = proxy_factory()
    helper = ["bash", str(lab["prefix"] / "manage.sh")]
    subprocess.run(helper + ["reload"], check=True, capture_output=True)
    path = lab["prefix"] / "nginx.conf"
    original = path.read_text()
    try:
        path.write_text(original + "\ninvalid_lab_directive on;\n")
        rejected = subprocess.run(helper + ["reload"], capture_output=True)
        assert rejected.returncode != 0
        assert httpx.get(f"{lab['url']}/products", trust_env=False).status_code == 200
    finally:
        path.write_text(original)
    subprocess.run(helper + ["stop"], check=True, capture_output=True)
    lab["nginx"].wait(timeout=10)
    assert lab["nginx"].returncode in (0, -signal.SIGQUIT)
