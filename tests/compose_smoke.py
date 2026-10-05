"""Real Compose lifecycle checks in a disposable project; only stdlib required.

Run: python3 tests/compose_smoke.py [--no-build]
The generated project owns all containers/volumes removed by this script.
"""

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def run(arguments, *, environment=None, check=True, timeout=180):
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"Command failed: {arguments}\n{result.stdout}\n{result.stderr}"
        )
    return result


def request(base, path, *, request_id=None, body=None):
    headers = {}
    if request_id:
        headers["X-Request-ID"] = request_id
    if body is not None:
        headers["Content-Type"] = "application/json"
    message = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
    )
    try:
        response = HTTP.open(message, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


def wait_http(base, path, status=200):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            result = request(base, path)
            if result[0] == status:
                return result
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise AssertionError(f"{path} did not recover to HTTP {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-build", action="store_true", help="Use existing lab images"
    )
    arguments = parser.parse_args()
    project = "shopsphere-smoke-" + uuid4().hex[:12]
    holder = project + "-old-api-address"
    probe = project + "-subnet-probe"
    temporary = tempfile.TemporaryDirectory(prefix=project)
    environment = dict(os.environ, SHOPSPHERE_PORT="0", PAYMENT_TIMEOUT_SECONDS="2")
    command = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        os.devnull,
        "--file",
        str(ROOT / "docker-compose.yml"),
    ]

    def compose(*args, **kwargs):
        return run(command + list(args), environment=environment, **kwargs)

    def inspect(service):
        identifier = compose("ps", "--all", "--quiet", service).stdout.strip()
        assert identifier, f"Missing service: {service}"
        return json.loads(run(["docker", "inspect", identifier]).stdout)[0]

    def base_url():
        address = compose("port", "nginx", "8088").stdout.strip()
        assert address.startswith("127.0.0.1:"), address
        return "http://" + address

    def events(service):
        output = compose("logs", "--no-color", "--no-log-prefix", service).stdout
        return [
            json.loads(line) for line in output.splitlines() if line.startswith("{")
        ]

    print(f"Checking private Compose project {project}", flush=True)
    try:
        # Ask Docker for a free subnet, then explicitly configure that same range
        # only in this test. Static address reservation requires explicit IPAM.
        run(["docker", "network", "create", probe])
        subnet = json.loads(run(["docker", "network", "inspect", probe]).stdout)[0][
            "IPAM"
        ]["Config"][0]["Subnet"]
        run(["docker", "network", "rm", probe])
        network_override = Path(temporary.name) / "network.json"
        network_override.write_text(
            json.dumps(
                {"networks": {"app": {"ipam": {"config": [{"subnet": subnet}]}}}}
            )
        )
        command.extend(["--file", str(network_override)])
        if not arguments.no_build:
            print("Building images", flush=True)
            compose("build", timeout=600)

        print("Checking that failed initialization blocks the API", flush=True)
        with tempfile.TemporaryDirectory(prefix=project) as directory:
            override = Path(directory) / "init-failure.json"
            override.write_text(
                json.dumps(
                    {
                        "services": {
                            "db-init": {
                                "command": ["python", "-c", "raise SystemExit(7)"]
                            }
                        }
                    }
                )
            )
            failed = compose(
                "--file",
                str(override),
                "up",
                "--no-build",
                "--detach",
                "--wait",
                "--wait-timeout",
                "120",
                check=False,
            )
            assert failed.returncode != 0
            assert inspect("db-init")["State"]["ExitCode"] == 7
            assert not inspect("api")["State"]["Running"]

        print(
            "Checking fresh startup, health, image users, and port boundaries",
            flush=True,
        )
        compose("up", "--no-build", "--detach", "--wait", "--wait-timeout", "120")
        base = base_url()
        assert inspect("db-init")["State"]["ExitCode"] == 0
        for service in ("api", "payment", "nginx", "postgres"):
            details = inspect(service)
            assert details["State"]["Health"]["Status"] == "healthy", service
            if service != "postgres":
                assert details["Config"]["User"] not in ("", "0", "root")
                assert details["HostConfig"]["ReadonlyRootfs"]
            if service != "nginx":
                assert not details["HostConfig"]["PortBindings"]
        compose("exec", "-T", "nginx", "nginx", "-t")
        compose("exec", "-T", "api", "python", "-m", "pip", "check")
        assert request(base, "/docs")[0] == 200
        assert "/orders" in json.loads(request(base, "/openapi.json")[2])["paths"]
        assert len(json.loads(request(base, "/products")[2])) == 3

        print(
            "Checking orders, payment, errors, and correlated slow-query logs",
            flush=True,
        )
        order_id = project + "-order"
        status, headers, body = request(
            base,
            "/orders?db_delay_seconds=0.3",
            request_id=order_id,
            body={"items": [{"product_id": 1, "quantity": 2}]},
        )
        assert status == 201 and headers.get_all("X-Request-ID") == [order_id]
        order = json.loads(body)
        order_path = headers["Location"]
        assert order["total_cents"] == 4998
        assert json.loads(request(base, order_path)[2]) == order
        payment_id = project + "-payment"
        assert request(base, "/payment", request_id=payment_id)[0] == 200
        slow_id = project + "-slow"
        assert request(base, "/slow-query", request_id=slow_id)[0] == 200
        error_id = project + "-error"
        failure = request(base, "/error", request_id=error_id)
        assert failure[0] == 500 and json.loads(failure[2])["request_id"] == error_id
        assert len(request(base, "/products")[1]["X-Request-ID"]) == 32
        access = {event["request_id"]: event for event in events("nginx")}
        assert access[order_id]["upstream_status"] == "201"
        assert access[slow_id]["request_duration_seconds"] >= 5
        assert float(access[slow_id]["upstream_response_seconds"]) >= 5
        for service in ("api", "payment"):
            assert any(event["request_id"] == payment_id for event in events(service))
        assert any(
            event["request_id"] == slow_id
            and event.get("query_name") == "lab.slow_query"
            for event in events("api")
        )
        database_log = compose(
            "exec", "-T", "postgres", "sh", "-c", 'cat "$PGDATA"/log/*.json'
        ).stdout
        assert any(
            slow_id in event.get("message", "") and "pg_sleep" in event["message"]
            for event in map(json.loads, database_log.splitlines())
        )

        print("Checking payment and database outages and recovery", flush=True)
        compose("stop", "payment")
        # A detached Docker peer can time out instead of refusing immediately.
        payment_failure = request(base, "/payment")
        assert payment_failure[0] in (502, 504)
        assert json.loads(payment_failure[2])["detail"] in (
            "Payment service unavailable",
            "Payment service timed out",
        )
        compose("start", "payment")
        wait_http(base, "/payment")
        compose("stop", "postgres")
        assert request(base, "/products")[0] == 503
        assert request(base, "/")[0] == 200
        readiness = inspect("api")["Config"]["Healthcheck"]["Test"]
        assert readiness[0] == "CMD"
        assert compose("exec", "-T", "api", *readiness[1:], check=False).returncode != 0
        compose("start", "postgres")
        wait_http(base, order_path)

        print("Checking API outage and DNS recovery after its IP changes", flush=True)
        nginx_before = inspect("nginx")
        old_api = inspect("api")
        network, endpoint = next(iter(old_api["NetworkSettings"]["Networks"].items()))
        old_ip = endpoint["IPAddress"]
        compose("stop", "api")
        api_failure = request(base, "/products")
        assert api_failure[0] in (502, 504)
        assert "text/html" in api_failure[1]["Content-Type"]
        assert api_failure[1]["X-Request-ID"]
        assert request(base, "/proxy-health")[0] == 200
        compose("rm", "--force", "api")
        # Occupy the old address so this test proves a DNS update, not IP reuse.
        run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                holder,
                "--network",
                network,
                "--ip",
                old_ip,
                "--label",
                f"shopsphere.smoke-project={project}",
                old_api["Config"]["Image"],
                "python",
                "-c",
                "import time; time.sleep(180)",
            ]
        )
        compose(
            "up",
            "--no-deps",
            "--no-build",
            "--detach",
            "--wait",
            "--wait-timeout",
            "60",
            "api",
        )
        new_ip = inspect("api")["NetworkSettings"]["Networks"][network]["IPAddress"]
        assert new_ip != old_ip
        assert json.loads(wait_http(base, order_path)[2]) == order
        nginx_after = inspect("nginx")
        assert nginx_after["Id"] == nginx_before["Id"]
        assert nginx_after["State"]["StartedAt"] == nginx_before["State"]["StartedAt"]
        run(["docker", "rm", "--force", holder])

        print(
            "Checking volume persistence across down/up and repeat initialization",
            flush=True,
        )
        volume = next(
            mount["Name"]
            for mount in inspect("postgres")["Mounts"]
            if mount["Destination"] == "/var/lib/postgresql"
        )
        assert volume.startswith(project + "_")
        compose("down", "--timeout", "40")
        run(["docker", "volume", "inspect", volume])
        compose("up", "--no-build", "--detach", "--wait", "--wait-timeout", "120")
        base = base_url()
        assert json.loads(request(base, order_path)[2]) == order
        assert len(json.loads(request(base, "/products")[2])) == 3
        compose("run", "--rm", "--no-deps", "db-init")
        assert json.loads(request(base, order_path)[2]) == order
        print("All Compose smoke checks passed.", flush=True)
    except BaseException:
        diagnostics = compose("logs", "--no-color", "--tail", "30", check=False)
        print(diagnostics.stdout, flush=True)
        raise
    finally:
        # Never act on the default lab project or any pre-existing volume.
        run(["docker", "rm", "--force", holder], check=False)
        compose("down", "--volumes", "--remove-orphans", "--timeout", "40")
        run(["docker", "network", "rm", probe], check=False)
        temporary.cleanup()
        print(f"Removed disposable project {project} and its volumes.", flush=True)


if __name__ == "__main__":
    main()
