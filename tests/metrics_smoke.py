"""Verify real exporters, PromQL, Grafana, outages, and retained metric history.

Run: python3 tests/metrics_smoke.py [--no-build]
Uses an isolated Compose project, temporary ports, and its own data volumes.
"""

import argparse
import base64
import json
import math
import os
import time
import urllib.parse
import urllib.request
from uuid import uuid4

from compose_smoke import HTTP, ROOT, request, run, wait_http


def eventually(check, description, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if result := check():
            return result
        time.sleep(2)
    raise AssertionError(f"Timed out: {description}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    project = "shopsphere-metrics-test-" + uuid4().hex[:10]
    environment = dict(
        os.environ,
        SHOPSPHERE_PORT="0",
        PROMETHEUS_PORT="0",
        GRAFANA_PORT="0",
        GRAFANA_ADMIN_USER="admin",
        GRAFANA_ADMIN_PASSWORD="metrics_smoke_local",
    )
    command = [
        "docker",
        "compose",
        "-p",
        project,
        "--env-file",
        os.devnull,
        "-f",
        str(ROOT / "docker-compose.yml"),
    ]
    run(["bash", "elastic/prepare-docker-logs.sh"], environment=environment)

    def compose(*arguments, **kwargs):
        return run(command + list(arguments), environment=environment, **kwargs)

    def endpoint(service, port):
        address = compose("port", service, str(port)).stdout.strip()
        assert address.startswith("127.0.0.1:") and not address.endswith(":0"), address
        return "http://" + address

    def api(base, path, *, grafana=False):
        headers = {}
        if grafana:
            headers["Authorization"] = (
                "Basic " + base64.b64encode(b"admin:metrics_smoke_local").decode()
            )
        with HTTP.open(
            urllib.request.Request(base + path, headers=headers), timeout=15
        ) as response:
            return json.load(response)

    print(f"Checking private metrics project {project}", flush=True)
    try:
        if not args.no_build:
            compose(
                "build",
                "api",
                "payment",
                "db-init",
                "nginx",
                "node-exporter",
                timeout=600,
            )
        compose(
            "up",
            "-d",
            "--no-build",
            "--wait",
            "--wait-timeout",
            "180",
            "nginx-exporter",
            "postgres-exporter",
            "node-exporter",
            "prometheus",
            "grafana",
            timeout=240,
        )
        base, prom, grafana = (
            endpoint("nginx", 8088),
            endpoint("prometheus", 9090),
            endpoint("grafana", 3000),
        )
        environment["PROMETHEUS_PORT"] = prom.rsplit(":", 1)[1]
        environment["GRAFANA_PORT"] = grafana.rsplit(":", 1)[1]

        def query(expression, timestamp=None):
            params = {"query": expression}
            if timestamp is not None:
                params["time"] = str(timestamp)
            result = api(prom, "/api/v1/query?" + urllib.parse.urlencode(params))
            assert result["status"] == "success", result
            return result["data"]["result"]

        def scalar(expression, timestamp=None):
            rows = query(expression, timestamp)
            return float(rows[0]["value"][1]) if rows else None

        print(
            "Checking scrape targets, exporter values, and access boundaries",
            flush=True,
        )
        eventually(lambda: scalar("sum(up)") == 6, "all six scrape targets up")
        assert scalar("pg_up") == 1
        assert scalar("pg_exporter_last_scrape_error") == 0
        assert scalar("nginx_up") == 1
        assert scalar("min(node_scrape_collector_success)") == 1
        assert scalar("node_memory_MemTotal_bytes") > 0
        assert scalar("count(node_cpu_seconds_total)") > 0
        assert scalar("shopsphere_docker_storage_size_bytes") > 0
        assert scalar("shopsphere_docker_storage_collection_success") == 1
        assert scalar("node_textfile_scrape_error") == 0
        assert request(base, "/stub_status")[0] == 404
        assert request(base, "/metrics")[0] == 200
        for service in ("node-exporter", "nginx-exporter", "postgres-exporter"):
            identifier = compose("ps", "--quiet", service).stdout.strip()
            container = json.loads(run(["docker", "inspect", identifier]).stdout)[0]
            assert not container["HostConfig"]["PortBindings"], service
        compose("run", "--rm", "--no-deps", "metrics-db-init")
        permissions = compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "shopsphere",
            "-d",
            "shopsphere",
            "-tAc",
            "SELECT rolsuper, rolcreatedb, rolcreaterole, "
            "has_table_privilege('shopsphere_metrics','public.orders','SELECT') "
            "FROM pg_roles WHERE rolname='shopsphere_metrics';",
        ).stdout.strip()
        assert permissions == "f|f|f|f", permissions

        # Replacing the collector must leave the daemon and application usable.
        compose("rm", "--stop", "--force", "node-exporter")
        compose("exec", "-T", "nginx", "nginx", "-t")
        run(["docker", "info", "--format", "{{.ID}}"])
        compose("up", "-d", "node-exporter")
        eventually(
            lambda: scalar('up{job="linux-host"}') == 1, "host collector returns"
        )

        print("Generating requests and checking counter/histogram changes", flush=True)
        for _ in range(4):
            assert request(base, "/payment")[0] == 200
            assert request(base, "/error")[0] == 500
            assert request(base, "/slow-query?seconds=0.1")[0] == 200
        order = request(
            base, "/orders", body={"items": [{"product_id": 1, "quantity": 1}]}
        )
        assert order[0] == 201
        order_path = "/orders/" + json.loads(order[2])["id"]
        assert request(base, order_path)[0] == 200
        eventually(
            lambda: (
                scalar(
                    'http_requests_total{service="order-api",route="/payment",status="200"}'
                )
                == 4
            ),
            "payment counter",
        )
        assert (
            scalar('application_errors_total{service="order-api",route="/error"}') == 4
        )
        assert (
            scalar(
                'database_query_duration_seconds_sum{service="order-api",operation="SELECT",outcome="success"}'
            )
            >= 0.4
        )
        assert (
            scalar(
                'http_request_duration_seconds_sum{service="order-api",route="/slow-query"}'
            )
            >= 0.4
        )
        assert not query('http_requests_total{route="/metrics"}')
        assert not query('http_requests_total{route="' + order_path + '"}')

        print(
            "Checking all provisioned dashboard queries and the Grafana data source",
            flush=True,
        )
        health = api(
            grafana, "/api/datasources/uid/shopsphere-prometheus/health", grafana=True
        )
        assert health["status"] == "OK", health
        for path in sorted((ROOT / "grafana/dashboards").glob("shopsphere-*.json")):
            dashboard = json.loads(path.read_text())
            actual = api(
                grafana, "/api/dashboards/uid/" + dashboard["uid"], grafana=True
            )
            assert actual["meta"]["provisioned"]
            for panel in dashboard["panels"]:
                for target in panel["targets"]:
                    expression = target["expr"].replace("$__rate_interval", "1m")
                    eventually(
                        lambda expr=expression: any(
                            math.isfinite(float(row["value"][1])) for row in query(expr)
                        ),
                        panel["title"] + ": " + expression,
                    )

        print(
            "Checking exporter/database outages and application observability",
            flush=True,
        )
        compose("stop", "nginx-exporter")
        eventually(lambda: scalar('up{job="nginx"}') == 0, "stopped exporter visible")
        assert request(base, "/products")[0] == 200
        compose("start", "nginx-exporter")
        eventually(lambda: scalar('up{job="nginx"}') == 1, "exporter recovers")
        compose("stop", "postgres")
        eventually(lambda: scalar("pg_up") == 0, "database failure visible")
        assert request(base, "/products")[0] == 503
        assert scalar('up{job="order-api"}') == 1
        compose("start", "postgres")
        wait_http(base, "/products")
        eventually(lambda: scalar("pg_up") == 1, "database recovers")
        assert request(base, order_path)[0] == 200

        print(
            "Checking stored samples and dashboards survive container replacement",
            flush=True,
        )
        timestamp = time.time()
        expression = (
            'http_requests_total{service="order-api",route="/payment",status="200"}'
        )
        retained = scalar(expression, timestamp)
        assert retained == 4
        compose("stop", "prometheus", "grafana")
        assert request(base, "/payment")[0] == 200
        compose(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "120",
            "prometheus",
            "grafana",
            timeout=180,
        )
        assert scalar(expression, timestamp) == retained
        eventually(lambda: scalar(expression) == 5, "new samples after recovery")
        assert len(api(grafana, "/api/search?tag=shopsphere", grafana=True)) == 3
        assert scalar("sum(up)") == 6
        print("All metrics smoke checks passed.", flush=True)
    except Exception:
        print(compose("ps", "--all", check=False).stdout, flush=True)
        print(
            compose(
                "logs",
                "--tail",
                "35",
                "postgres-exporter",
                "node-exporter",
                "prometheus",
                "grafana",
                check=False,
            ).stdout,
            flush=True,
        )
        raise
    finally:
        compose("down", "--volumes", "--remove-orphans", timeout=180)
        print(f"Removed disposable project {project} and its data volumes.", flush=True)


if __name__ == "__main__":
    main()
