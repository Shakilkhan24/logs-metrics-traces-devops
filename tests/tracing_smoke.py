"""Verify real OTLP delivery, distributed spans, failures, and durable storage.

Run: python3 tests/tracing_smoke.py [--no-build]
Owns a disposable Compose project and removes only its containers/data volumes.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from uuid import uuid4

from compose_smoke import HTTP, ROOT, request, run, wait_http


def eventually(check, description, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if result := check():
                return result
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(1)
    raise AssertionError(f"Timed out: {description}")


def attributes(items):
    return {item["key"]: next(iter(item["value"].values())) for item in items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    project = "shopsphere-tracing-test-" + uuid4().hex[:10]
    environment = dict(
        os.environ, SHOPSPHERE_PORT="0", JAEGER_PORT="0", OTEL_SDK_DISABLED="false"
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

    def compose(*args, **kwargs):
        return run(command + list(args), environment=environment, **kwargs)

    def endpoint(service, port):
        address = compose("port", service, str(port)).stdout.strip()
        assert address.startswith("127.0.0.1:") and not address.endswith(":0"), address
        return "http://" + address

    def internal_get(path):
        code = (
            "import urllib.request; print(urllib.request.urlopen("
            + repr("http://otel-collector:" + path)
            + ", timeout=3).read().decode())"
        )
        result = compose("exec", "-T", "api", "python", "-c", code, check=False)
        return result.stdout if result.returncode == 0 else ""

    print(f"Checking private tracing project {project}", flush=True)
    try:
        if not args.no_build:
            compose("build", "api", "payment", "db-init", "nginx", timeout=600)
        compose(
            "up",
            "-d",
            "--no-build",
            "--wait",
            "--wait-timeout",
            "180",
            "nginx",
            "otel-collector",
            "jaeger",
            timeout=240,
        )
        base, jaeger = endpoint("nginx", 8088), endpoint("jaeger", 16686)
        environment["JAEGER_PORT"] = jaeger.rsplit(":", 1)[1]
        eventually(
            lambda: request(jaeger, "/api/v3/services")[0] == 200, "Jaeger query API"
        )
        eventually(lambda: internal_get("13133/"), "Collector health")
        for service in ("otel-collector", "jaeger"):
            identifier = compose("ps", "-q", service).stdout.strip()
            container = json.loads(run(["docker", "inspect", identifier]).stdout)[0]
            assert container["Config"]["User"] == "10001:10001"
            bindings = container["HostConfig"]["PortBindings"] or {}
            assert set(bindings) == ({"16686/tcp"} if service == "jaeger" else set())
        compose("run", "--rm", "--no-deps", "tracing-storage-init")

        def traced(path, status=200, headers=None):
            message = urllib.request.Request(base + path, headers=headers or {})
            try:
                response = HTTP.open(message, timeout=15)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                assert response.status in (
                    (status,) if isinstance(status, int) else status
                ), response.status
                trace_id = response.headers["X-Trace-ID"]
                assert len(trace_id) == 32 and int(trace_id, 16) > 0
                return trace_id

        def spans(trace_id):
            status, _, data = request(
                jaeger, "/api/v3/traces/" + trace_id + "?rawTraces=true"
            )
            if status == 404:
                return []
            assert status == 200, data
            result = []
            # API v3 streams one or more JSON result envelopes, with OTLP spans.
            for line in data.decode().splitlines():
                for resource in json.loads(line)["result"].get("resourceSpans", []):
                    service = attributes(resource["resource"]["attributes"])[
                        "service.name"
                    ]
                    for scope in resource["scopeSpans"]:
                        for span in scope["spans"]:
                            span["service"] = service
                            span["attrs"] = attributes(span.get("attributes", []))
                            result.append(span)
            return result

        def complete(trace_id, count):
            return eventually(
                lambda: found if len(found := spans(trace_id)) >= count else None,
                "trace " + trace_id,
            )

        print(
            "Checking propagation, distributed parents, SQL timing, and failures",
            flush=True,
        )
        incoming, parent_id = uuid4().hex, "1234567890abcdef"
        payment_id = traced(
            "/payment",
            headers={
                "traceparent": f"00-{incoming}-{parent_id}-01",
                "tracestate": "lab=smoke",
            },
        )
        assert payment_id == incoming
        payment = complete(payment_id, 3)
        assert len(payment) == 3
        root = next(
            s for s in payment if s["service"] == "order-api" and s["kind"] == 2
        )
        downstream = next(s for s in payment if s["kind"] == 3)
        remote = next(s for s in payment if s["service"] == "mock-payment")
        assert root["parentSpanId"] == parent_id
        assert downstream["parentSpanId"] == root["spanId"]
        assert remote["parentSpanId"] == downstream["spanId"]
        assert all(s["traceId"] == incoming for s in payment)
        assert root.get("traceState") == "lab=smoke"
        slow_id = traced("/slow-query?seconds=0.3")
        slow = complete(slow_id, 2)
        root = next(s for s in slow if s["kind"] == 2)
        sql = next(s for s in slow if s["attrs"].get("db.system.name") == "postgresql")
        assert sql["parentSpanId"] == root["spanId"]
        start, end = int(sql["startTimeUnixNano"]), int(sql["endTimeUnixNano"])
        assert end - start >= 300_000_000
        assert (
            int(root["startTimeUnixNano"])
            <= start
            < end
            <= int(root["endTimeUnixNano"])
        )
        assert (
            "db.query.text" not in sql["attrs"] and "db.statement" not in sql["attrs"]
        )
        error_id = traced("/error", 500)
        error = complete(error_id, 1)[0]
        assert error["status"]["code"] == 2
        assert any(e["name"] == "exception" for e in error["events"])
        unsampled = uuid4().hex
        assert (
            traced(
                "/products", headers={"traceparent": f"00-{unsampled}-{parent_id}-00"}
            )
            == unsampled
        )
        assert request(base, "/metrics")[1].get("X-Trace-ID") is None

        print(
            "Checking downstream failure, graceful flush, and Collector independence",
            flush=True,
        )
        compose("stop", "payment")
        failed_id = traced("/payment", (502, 504))
        failed = complete(failed_id, 2)
        assert all(s["status"]["code"] == 2 for s in failed)
        compose("start", "payment")
        wait_http(base, "/payment")
        flush_id = traced("/error", 500)
        compose("stop", "api")
        complete(flush_id, 1)
        compose("start", "api")
        wait_http(base, "/products")
        compose("stop", "otel-collector")
        assert request(base, "/payment")[0] == 200
        assert request(base, "/products")[0] == 200
        compose("start", "otel-collector")
        eventually(lambda: internal_get("13133/"), "Collector recovery")
        complete(traced("/payment"), 3)

        print(
            "Checking persistent queue after Collector crash and Jaeger replacement",
            flush=True,
        )
        compose("stop", "jaeger")
        queued_id = traced("/payment")
        for _ in range(5):
            time.sleep(1.2)
            traced("/payment")

        def queued():
            for line in internal_get("8888/metrics").splitlines():
                if line.startswith("otelcol_exporter_queue_size{"):
                    if float(line.rsplit(" ", 1)[1]) >= 3:
                        return True
            return False

        eventually(queued, "persisted exporter queue")
        # Only this test project's Collector is deliberately killed.
        compose("kill", "-s", "SIGKILL", "otel-collector")
        compose("up", "-d", "--no-deps", "--force-recreate", "otel-collector", "jaeger")
        eventually(
            lambda: request(jaeger, "/api/v3/services")[0] == 200, "Jaeger recovery"
        )
        complete(queued_id, 3)
        complete(payment_id, 3)
        complete(slow_id, 2)
        assert not spans(unsampled)
        services = json.loads(request(jaeger, "/api/v3/services")[2])["services"]
        assert {"order-api", "mock-payment"} <= set(services)
        assert request(base, "/products")[0] == 200
        print("All distributed tracing smoke checks passed.", flush=True)
    except Exception:
        print(
            compose(
                "logs",
                "--tail",
                "25",
                "postgres",
                "payment",
                "nginx",
                "api",
                "otel-collector",
                "jaeger",
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
