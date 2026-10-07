# Prometheus and exporters

Phase 7 scrapes six targets every five seconds: the order API, mock payment,
NGINX exporter, PostgreSQL exporter, node exporter, and Prometheus itself.
`prometheus.yml` declares those targets using Compose DNS. Prometheus joins both
networks so it can reach application metrics and the telemetry-only host exporter.
Applications have no dependency on Prometheus availability.

Pinned images: Prometheus 3.15.0, NGINX exporter 1.5.3, PostgreSQL exporter 0.20.1,
and node exporter 1.12.1. Compose pins image digests as well as versions.

```bash
bash elastic/prepare-docker-logs.sh
docker compose up --build -d --wait --wait-timeout 180 \
  nginx-exporter postgres-exporter node-exporter prometheus grafana
curl -s 'http://127.0.0.1:9090/api/v1/targets'
```

Node exporter uses native CPU, memory, disk I/O, and kernel identity collectors.
Its normal `/proc` and `/sys` expose global Linux kernel counters: the Docker host
on native Linux, or the Linux VM on Docker Desktop. They do not describe Windows
or individual container resource limits. No host root, proc/sys bind, host PID
namespace, or Docker socket is needed for these collectors.

For capacity, the container reuses the existing non-recursive Docker log source
volume at `/docker-storage:ro`. `host-filesystem.sh` runs `stat` on that directory
every five seconds and atomically publishes `shopsphere_docker_storage_size_bytes`
and `shopsphere_docker_storage_avail_bytes` through the textfile collector. These
gauges measure the filesystem containing Docker's logs, normally Docker's data
disk. They do not measure the total size of the log files or all host filesystems.
The native filesystem collector is disabled because some WSL Windows-share mount
metadata cannot be parsed. Collection success, textfile parse errors, and sample
age expose failed or stale capacity measurements.

The collector runs as UID 65534, with capabilities dropped and a read-only root
filesystem. The log source volume is read-only; files accessible to that UID
remain accessible to this trusted collector. It writes only to a temporary
textfile directory. The same log-volume helper used by Elastic must run before
starting metrics, even when Elastic services are stopped.

NGINX exporter reads internal `nginx:8089/stub_status`; the PostgreSQL exporter
uses `shopsphere_metrics` with `pg_monitor`. The `metrics-db-init` job safely adds
that login to existing databases. No exporter ports or NGINX status port are
published. Only Prometheus's UI/API port 9090 is exposed on loopback.

`prometheus_data` stores samples and the write-ahead log. Retention is seven days
or 512 MB of retained blocks; active data/WAL can use additional disk space.
Container replacement keeps history; deleting this volume erases it. Missed
scrapes are not backfilled. `up` describes scrape success, while `pg_up`,
`nginx_up`, and `node_scrape_collector_success` describe underlying collection.

Validate configuration using the actual pinned binary:

```bash
docker compose run --rm --no-deps --entrypoint promtool prometheus \
  check config /etc/prometheus/prometheus.yml
python3 tests/metrics_smoke.py --no-build
```

The smoke test uses a disposable project and temporary ports, checks every
dashboard query against real measurements, tests outages and persistence, and
removes its own data volumes. It also checks collector removal and replacement without affecting other containers.
See the [Phase 7 lesson](../docs/phase-07-metrics.md) for metric types, PromQL,
cardinality, measurement boundaries, and production differences.
