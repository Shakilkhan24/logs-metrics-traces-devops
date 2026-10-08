# Jaeger

Phase 8 runs Jaeger 2.22.0, pinned by digest, with a query UI at
[localhost:16686](http://127.0.0.1:16686). It receives OTLP/HTTP from the Collector
on internal port 4318 and uses the `lab` Badger backend in `jaeger-config.yml`.
The query service and ingestion pipeline share that storage in one process.
Jaeger's self-tracing uses `OTEL_TRACES_SAMPLER=always_off` in Compose and
`enable_tracing: false` on its query extension. Application trace ingestion remains
active. This avoids exporting self-traces to an unused local gRPC receiver.

`jaeger_data` retains traces through container replacement, with a 48-hour span
TTL. This is single-node storage with no replicas or backups; TTL is not a strict
disk quota. `docker compose down --volumes` deletes it. Abrupt failure can lose
recently accepted spans that have not reached durable storage.

The storage initializer gives UID 10001 ownership of the volume root. Jaeger runs
as that user, with a read-only root filesystem, temporary `/tmp`, and dropped
capabilities. Only the UI/query port is published, on loopback. There is no TLS or
authentication in this local lab. `JAEGER_PORT` changes the host UI port.

Generate a request, then paste `X-Trace-ID` into the UI or use the API:

```bash
curl -i http://127.0.0.1:8088/payment
curl -s http://127.0.0.1:16686/api/v3/services
# Replace <trace-id> with a response header value:
curl -s 'http://127.0.0.1:16686/api/v3/traces/<trace-id>'
```

API v3 returns streamed JSON result envelopes containing OTLP resource spans.
Search after allowing a few seconds for asynchronous export. An unsampled trace
ID or a trace older than retention may have no stored result. The minimal image
has no shell-based Docker health probe; query/API and end-to-end tests verify
readiness. Internal health listens on port 13133.

```bash
docker compose run --rm --no-deps jaeger validate --config=/etc/jaeger/config.yml
python3 tests/tracing_smoke.py --no-build
```

See the [Phase 8 lesson](../docs/phase-08-distributed-tracing.md) for parent-child
timelines, errors, sampling, persistence tests, and production storage differences.
