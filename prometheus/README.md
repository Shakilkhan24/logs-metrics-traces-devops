# Prometheus

Phase 7 will add `prometheus.yml` to declare scrape targets. Prometheus requests
measurements from application endpoints and exporters at intervals, then stores
the samples as time series. Grafana will query those samples.

Planned targets include the FastAPI application, NGINX exporter, PostgreSQL
exporter, and node exporter. In production, scrape discovery, retention,
availability, and alert rules become operating concerns. No scrape configuration
is present in Phase 1.
