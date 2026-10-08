"""Install the lab-owned assets before standalone Elastic Agent starts."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ES = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")
KIBANA = os.environ.get("KIBANA_URL", "http://kibana:5601")
JAEGER_PUBLIC = os.environ.get("JAEGER_PUBLIC_URL", "http://127.0.0.1:16686").rstrip(
    "/"
)
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def send(base, method, path, body=None):
    request = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", "kbn-xsrf": "shopsphere-setup"},
    )
    for attempt in range(6):
        try:
            with HTTP.open(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode()
            if error.code in (429, 502, 503, 504) and attempt < 5:
                print(f"Retrying {method} {path} after HTTP {error.code}", flush=True)
                time.sleep(5)
                continue
            raise RuntimeError(f"{method} {path}: {error.code} {detail}") from error


def asset(name):
    return json.loads((ROOT / name).read_text())


def main():
    pipeline = asset("pipeline.json")
    pipeline["processors"][2]["script"]["source"] = (
        ROOT / "normalize.painless"
    ).read_text()
    send(ES, "PUT", "/_ingest/pipeline/shopsphere-normalize-v1", pipeline)
    send(ES, "PUT", "/_ilm/policy/shopsphere-logs", asset("lifecycle.json"))
    send(ES, "PUT", "/_index_template/shopsphere-logs", asset("index-template.json"))
    existing = send(ES, "GET", "/_data_stream")
    names = {stream["name"] for stream in existing["data_streams"]}
    for name in ("logs-shopsphere.container-lab", "logs-shopsphere.postgresql-lab"):
        if name not in names:
            send(ES, "PUT", "/_data_stream/" + name)
    send(
        KIBANA,
        "POST",
        "/api/data_views/data_view",
        {
            "data_view": {
                "id": "shopsphere-logs",
                "name": "ShopSphere logs",
                "title": "logs-shopsphere.*-lab",
                "timeFieldName": "@timestamp",
                "fieldFormats": {
                    "trace.id": {
                        "id": "url",
                        "params": {
                            "urlTemplate": JAEGER_PUBLIC + "/trace/{{value}}",
                            "labelTemplate": "{{value}}",
                            "openLinkInCurrentTab": False,
                        },
                    }
                },
            },
            "override": True,
        },
    )
    print("Installed ShopSphere pipeline, lifecycle, template, streams, and data view.")


if __name__ == "__main__":
    main()
