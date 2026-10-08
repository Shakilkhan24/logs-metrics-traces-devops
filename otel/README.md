# OpenTelemetry Collector

Phase 8 runs digest-pinned Collector Contrib 0.162.0. Both Python services send
OTLP/HTTP traces to internal `otel-collector:4318/v1/traces`. The Collector joins
the app and telemetry networks and exports to Jaeger on the telemetry network.
Applications start and serve requests independently of either backend.

`collector-config.yml` connects an OTLP receiver, memory limiter, batch processor,
and OTLP/HTTP exporter. Batches flush every second, with at most 256 spans per
batch. A 192 MiB memory threshold sits below the 256 MiB container limit.
The SDKs have their own bounded background queues; no request waits for export.

The exporter's `file_storage` queue uses `otel_queue`: up to 512 requests and a
64 MiB queue database, with fsync enabled and retries for transient failures.
Requests durably enqueued there survive Collector replacement. SDK memory and
unpersisted batches do not. Full queues, permanent failures, and ambiguous
acknowledgements can lose or duplicate spans; this is not exactly-once delivery.
The queue is not a backup or a strict limit on all telemetry disk consumption.

`tracing-storage-init` assigns UID 10001 ownership of the volume root without
rewriting its contents. The Collector runs as that user with a read-only root
filesystem and dropped capabilities. All its ports remain internal:

- 4318: OTLP/HTTP ingestion.
- 13133: process health extension; readiness does not prove downstream delivery.
- 8888: internal Collector metrics, including queue size and refused/failed exports.

Validate the pinned binary and inspect the running process:

```bash
docker compose run --rm --no-deps otel-collector validate --config=/etc/otelcol/config.yml
docker compose logs --tail 30 otel-collector
docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://otel-collector:13133/').read().decode())"
```

The minimal image has no shell-based Docker health probe. The tracing smoke test
checks readiness and actual ingestion/storage, including a deliberate Collector
crash while Jaeger is unavailable. It affects only its disposable project.
See the [Phase 8 lesson](../docs/phase-08-distributed-tracing.md) for the full flow.
