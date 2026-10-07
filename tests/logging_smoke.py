"""Exercise the real Phase 6 pipeline in an isolated, disposable Compose project.

Run: python3 tests/logging_smoke.py [--no-build]
Requires the Phase 6 images and enough memory for one additional Elastic stack.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from uuid import uuid4

from compose_smoke import HTTP, ROOT, request, run, wait_http


def api(base, path, body=None, method=None):
    message = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", "kbn-xsrf": "smoke"},
    )
    try:
        with HTTP.open(message, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise AssertionError(
            f"{path}: {error.code}: {error.read().decode()}"
        ) from error


def eventually(check, description, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(2)
    raise AssertionError(f"Timed out: {description}")


def verify_parser(es):
    """Run genuine source formats through Elasticsearch's actual processors."""
    fixtures = [
        (
            "order-api",
            '{"time":"2026-10-05T12:00:00Z","event":"request.completed",'
            '"level":"ERROR","request_id":"fixture-app","duration_ms":12.5,'
            '"status_code":500,"method":"GET","route":"/error",'
            '"message":"Request completed"}',
        ),
        (
            "nginx",
            '{"time":"2026-10-05T12:00:00+00:00","event":"proxy.request",'
            '"request_id":"fixture-nginx","request_duration_seconds":0.0125,'
            '"method":"GET","path":"/error","status_code":500,"connection":"42"}',
        ),
        (
            "postgresql",
            '{"timestamp":"2026-10-05 12:00:00.123 UTC","error_severity":"LOG",'
            '"pid":42,"message":"duration: 12.500 ms execute <unnamed>: '
            'SELECT pg_sleep($1) /* request_id=fixture-pg */"}',
        ),
        (
            "nginx",
            "2026/10/05 12:00:00 [error] 7#7: *42 connect() failed "
            "(111: Connection refused) while connecting to upstream",
        ),
        ("order-api", "{broken json"),
        ("order-api", "INFO:     Application startup complete."),
        (
            "postgresql",
            '{"timestamp":"2026-10-05 12:00:00.123 UTC","error_severity":"ERROR",'
            '"pid":42,"message":"division by zero","state_code":"22012",'
            '"statement":"SELECT 1/0 /* request_id=fixture-pg-error */"}',
        ),
    ]
    result = api(
        es,
        "/_ingest/pipeline/shopsphere-normalize-v1/_simulate",
        {
            "docs": [
                {"_source": {"message": message, "service": {"name": service}}}
                for service, message in fixtures
            ]
        },
    )
    assert all("doc" in item for item in result["docs"]), result
    docs = [item["doc"]["_source"] for item in result["docs"]]
    assert [item["event"]["duration"] for item in docs[:3]] == [12_500_000] * 3
    assert [item["request_id"] for item in docs[:3]] == [
        "fixture-app",
        "fixture-nginx",
        "fixture-pg",
    ]
    assert docs[3]["nginx"]["connection"] == "42" and "request_id" not in docs[3]
    assert docs[3]["log"]["level"] == "error"
    assert (
        docs[4]["tags"] == ["parse_error"]
        and docs[4]["event"]["original"] == "{broken json"
    )
    assert docs[5]["event"]["action"] == "process.output"
    assert docs[6]["request_id"] == "fixture-pg-error"
    assert docs[6]["postgresql"]["state_code"] == "22012"
    assert not any(
        "parse_error" in d.get("tags", []) for i, d in enumerate(docs) if i != 4
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    project = "shopsphere-logs-test-" + uuid4().hex[:10]
    canary = project + "-unrelated"
    environment = dict(
        os.environ, SHOPSPHERE_PORT="0", ELASTICSEARCH_PORT="0", KIBANA_PORT="0"
    )
    run(["bash", "elastic/prepare-docker-logs.sh"], environment=environment)
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

    def compose(*arguments, **kwargs):
        return run(command + list(arguments), environment=environment, **kwargs)

    def endpoint(service, port):
        address = compose("port", service, str(port)).stdout.strip()
        assert address.startswith("127.0.0.1:"), address
        return "http://" + address

    print(f"Checking private logging project {project}", flush=True)
    try:
        if not args.no_build:
            compose(
                "build",
                "api",
                "payment",
                "db-init",
                "nginx",
                "elastic-agent",
                timeout=600,
            )
        compose(
            "up",
            "-d",
            "--no-build",
            "--wait",
            "--wait-timeout",
            "360",
            "nginx",
            "elastic-agent",
            timeout=480,
        )
        es, kibana, base = (
            endpoint("elasticsearch", 9200),
            endpoint("kibana", 5601),
            endpoint("nginx", 8088),
        )
        # Retain our allocated port during node replacement. Desktop can report
        # ':0' when a healthy replacement requests another automatic host port.
        environment["ELASTICSEARCH_PORT"] = es.rsplit(":", 1)[1]
        api_container = compose("ps", "--quiet", "api").stdout.strip()
        compose(
            "exec",
            "-T",
            "elastic-agent",
            "test",
            "-r",
            f"/var/log/docker/{api_container}/{api_container}-json.log",
        )

        def search(query):
            result = api(
                es, "/logs-shopsphere.*-lab/_search", {"size": 100, "query": query}
            )
            return [hit["_source"] for hit in result["hits"]["hits"]]

        def correlated(identifier):
            return search({"term": {"request_id": identifier}})

        def services(identifier):
            return {doc["service"]["name"] for doc in correlated(identifier)}

        print("Checking parsers, mappings, retention, and Kibana data view", flush=True)
        verify_parser(es)
        assert (
            api(kibana, "/api/data_views/data_view/shopsphere-logs")["data_view"][
                "title"
            ]
            == "logs-shopsphere.*-lab"
        )
        assert "shopsphere-logs" in api(es, "/_ilm/policy/shopsphere-logs")
        fields = api(
            es,
            "/logs-shopsphere.*-lab/_field_caps?fields=request_id,event.duration,http.response.status_code",
        )["fields"]
        assert fields["request_id"]["keyword"]["searchable"]
        assert fields["event.duration"]["long"]["aggregatable"]
        compose("run", "--rm", "--no-deps", "elastic-setup")

        print(
            "Checking business, payment, slow SQL, and error records end to end",
            flush=True,
        )
        slow_id, payment_id, error_id = (
            project + "-slow",
            project + "-payment",
            project + "-error",
        )
        assert request(base, "/slow-query?seconds=0.3", request_id=slow_id)[0] == 200
        assert request(base, "/payment", request_id=payment_id)[0] == 200
        assert request(base, "/error", request_id=error_id)[0] == 500
        order_id = project + "-order"
        assert (
            request(
                base,
                "/orders",
                request_id=order_id,
                body={"items": [{"product_id": 1, "quantity": 1}]},
            )[0]
            == 201
        )
        eventually(
            lambda: services(slow_id) == {"nginx", "order-api", "postgresql"},
            "slow-query correlation",
        )
        eventually(
            lambda: services(payment_id) == {"nginx", "order-api", "mock-payment"},
            "payment correlation",
        )
        eventually(
            lambda: any(
                d["event"].get("action") == "order.created"
                for d in correlated(order_id)
            ),
            "business event",
        )
        eventually(
            lambda: any(
                d.get("error", {}).get("stack_trace") for d in correlated(error_id)
            ),
            "application stack trace",
        )
        pg = next(
            d for d in correlated(slow_id) if d["service"]["name"] == "postgresql"
        )
        assert pg["event"]["duration"] >= 300_000_000
        assert pg["event"]["action"] == "database.slow_statement"

        sql_id = project + "-sql-error"
        failed = compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "shopsphere",
            "-d",
            "shopsphere",
            "-c",
            f"SELECT 1/0 /* request_id={sql_id} */",
            check=False,
        )
        assert failed.returncode != 0
        eventually(
            lambda: any(
                d.get("postgresql", {}).get("state_code") == "22012"
                for d in correlated(sql_id)
            ),
            "native PostgreSQL error",
        )

        print("Checking native proxy errors and project isolation", flush=True)
        compose("stop", "api")
        proxy_id = project + "-proxy"
        assert request(base, "/products", request_id=proxy_id)[0] in (502, 504)
        compose("start", "api")
        wait_http(base, "/products")
        access = eventually(lambda: correlated(proxy_id), "proxy access error")[0]
        connection = access["nginx"]["connection"]
        errors = eventually(
            lambda: search(
                {
                    "bool": {
                        "filter": [
                            {"term": {"event.action": "proxy.error"}},
                            {"term": {"nginx.connection": connection}},
                        ]
                    }
                }
            ),
            "native proxy error",
        )
        assert all("request_id" not in d for d in errors)
        canary_event = json.dumps({"request_id": canary, "message": canary})
        run(
            [
                "docker",
                "run",
                "--name",
                canary,
                "--log-driver",
                "json-file",
                "--log-opt",
                "labels=com.docker.compose.project,com.docker.compose.service",
                "--label",
                "com.docker.compose.project=unrelated-project",
                "--label",
                "com.docker.compose.service=api",
                "shopsphere-api:0.6.0",
                "python",
                "-c",
                f"print(({canary_event!r} + '\\n') * 20)",
            ]
        )

        print(
            "Checking registry persistence and Elasticsearch outage recovery",
            flush=True,
        )
        time.sleep(5)
        before = len(correlated(payment_id))
        compose(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "120",
            "elastic-agent",
        )
        after_restart = project + "-after-restart"
        assert request(base, "/products", request_id=after_restart)[0] == 200
        eventually(
            lambda: services(after_restart) == {"nginx", "order-api"},
            "collector restart",
        )
        assert len(correlated(payment_id)) == before, "Acknowledged records replayed"
        compose("stop", "elasticsearch")
        outage_id = project + "-es-outage"
        assert request(base, "/products", request_id=outage_id)[0] == 200
        compose(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "120",
            "elasticsearch",
        )
        es = endpoint("elasticsearch", 9200)
        eventually(
            lambda: services(outage_id) == {"nginx", "order-api"},
            "buffered outage logs",
        )
        assert correlated(payment_id), (
            "Indexed logs lost after Elasticsearch replacement"
        )
        assert not correlated(canary), "Unrelated project records were collected"
        assert not search({"term": {"tags": "parse_error"}}), (
            "Unexpected parse failures"
        )
        assert not search(
            {"bool": {"must_not": {"term": {"labels.compose_project": project}}}}
        )
        print("All centralized logging smoke checks passed.", flush=True)
    except BaseException:
        print(
            compose("logs", "--no-color", "--tail", "35", check=False).stdout,
            flush=True,
        )
        raise
    finally:
        run(["docker", "rm", "--force", canary], check=False)
        compose("down", "--volumes", "--remove-orphans", "--timeout", "40")
        print(f"Removed disposable project {project} and its volumes.", flush=True)


if __name__ == "__main__":
    main()
