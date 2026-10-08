"""Verify the running lab's logs → traces journey and aggregate metrics.

Creates two small demonstration orders; retains them for inspection.
Run: python3 tests/correlation_smoke.py
URLs can be overridden with SHOPSPHERE_URL, ELASTICSEARCH_URL, PROMETHEUS_URL,
KIBANA_URL and JAEGER_URL. Uses only the Python standard library.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
API = os.getenv("SHOPSPHERE_URL", "http://127.0.0.1:8088").rstrip("/")
ES = os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200").rstrip("/")
PROM = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/")
KIBANA = os.getenv("KIBANA_URL", "http://127.0.0.1:5601").rstrip("/")
JAEGER = os.getenv("JAEGER_URL", "http://127.0.0.1:16686").rstrip("/")


def request(base, path, body=None, headers=None):
    message = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        response = HTTP.open(message, timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, response.headers, response.read()


def document(base, path, body=None):
    status, _, data = request(base, path, body)
    assert status == 200, (base, path, status, data[:500])
    return json.loads(data)


def eventually(check, description):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if result := check():
                return result
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(1)
    raise AssertionError("Timed out: " + description)


def counter():
    query = (
        'sum(http_requests_total{service="order-api",route="/orders",status="201"})'
        " or vector(0)"
    )
    result = document(PROM, "/api/v1/query?" + urllib.parse.urlencode({"query": query}))
    return float(result["data"]["result"][0]["value"][1])


def spans(trace_id):
    status, _, raw = request(JAEGER, f"/api/v3/traces/{trace_id}?rawTraces=true")
    if status == 404:
        return []
    assert status == 200, (status, raw[:500])
    return [
        span
        for line in raw.decode().splitlines()
        for resource in json.loads(line)["result"].get("resourceSpans", [])
        for scope in resource["scopeSpans"]
        for span in scope["spans"]
    ]


def main():
    view = document(KIBANA, "/api/data_views/data_view/shopsphere-logs")["data_view"]
    formatter = view["fieldFormats"]["trace.id"]
    assert formatter["id"] == "url"
    template = formatter["params"]["urlTemplate"]
    assert template.endswith("/trace/{{value}}"), template
    before = counter()
    product = document(API, "/products")[0]["id"]
    order = {"items": [{"product_id": product, "quantity": 1}]}
    cases = []
    for name, path, body, expected in [
        ("Slow checkout", "/orders?db_delay_seconds=1", order, 201),
        ("Checkout after removing delay", "/orders", order, 201),
        ("Payment", "/payment", None, 200),
        ("Intentional error", "/error", None, 500),
    ]:
        request_id = "phase9-" + uuid4().hex
        start = time.perf_counter()
        status, headers, raw = request(API, path, body, {"X-Request-ID": request_id})
        elapsed = time.perf_counter() - start
        assert status == expected, (name, status, raw)
        trace_id = headers["X-Trace-ID"]
        assert trace_id and len(trace_id) == 32 and int(trace_id, 16) > 0
        cases.append((name, request_id, trace_id, elapsed, json.loads(raw)))

    print("# ShopSphere correlation evidence\n", flush=True)
    for name, request_id, trace_id, elapsed, payload in cases:

        def matching_logs(request_id=request_id, trace_id=trace_id, name=name):
            hits = document(
                ES,
                "/logs-shopsphere.*-lab/_search",
                {"query": {"term": {"request_id": request_id}}, "size": 50},
            )["hits"]["hits"]
            services = {h["_source"].get("service", {}).get("name") for h in hits}
            required = {"nginx", "order-api"}
            if name == "Payment":
                required.add("mock-payment")
            linked = [
                h for h in hits if h["_source"].get("trace", {}).get("id") == trace_id
            ]
            return hits if required <= services and linked else None

        hits = eventually(matching_logs, name + " logs")
        expected_spans = 3 if name == "Payment" else 1
        trace = eventually(
            lambda trace_id=trace_id, count=expected_spans: (
                found if len(found := spans(trace_id)) >= count else None
            ),
            name + " trace",
        )
        assert all(s["traceId"] == trace_id for s in trace)
        if name == "Slow checkout":
            sql = [
                s
                for s in trace
                if any(a["key"] == "db.system.name" for a in s.get("attributes", []))
            ]
            assert any(
                int(s["endTimeUnixNano"]) - int(s["startTimeUnixNano"]) >= 1_000_000_000
                for s in sql
            )
        if name == "Intentional error":
            assert any(s.get("status", {}).get("code") == 2 for s in trace)
        query = urllib.parse.urlencode(
            {
                "_a": "(index:'shopsphere-logs',query:(language:kuery,"
                f"query:'request_id: \"{request_id}\"'))",
                "_g": "(time:(from:now-15m,to:now))",
            }
        )
        print(f"## {name}\n")
        print(
            f"Request `{request_id}` took {elapsed:.3f}s; "
            f"{len(hits)} logs, {len(trace)} spans.\n"
        )
        print(
            f"[Kibana logs]({KIBANA}/app/discover#/?{query}) · "
            f"[Jaeger trace]({template.replace('{{value}}', trace_id)})\n"
        )
        if "id" in payload:
            print(f"Retained order: `{payload['id']}`.\n")
    eventually(lambda: counter() >= before + 2, "Prometheus to scrape both new orders")
    print(
        "Verified: Kibana trace links, matching Elasticsearch logs and Jaeger spans, "
        "and the Prometheus order counter increase."
    )


if __name__ == "__main__":
    main()
