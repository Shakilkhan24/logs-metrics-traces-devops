# Application

This directory holds the FastAPI e-commerce API. It handles client requests,
business behavior, PostgreSQL transactions, and outbound payment calls.

Files and responsibilities:

| File | Responsibility | Phase |
| --- | --- | --- |
| `main.py` | Application entry point and HTTP routes | 2 |
| `logging.py` | Structured application logging | 2 |
| `schemas.py` | Pydantic request and response contracts | 2 |
| `store.py` | Product/order queries and transaction boundaries | 3 |
| `config.py` | Validated payment and database connection settings | 2–3 |
| `database.py` | Database engine and session lifecycle | 3 |
| `models.py` | SQLAlchemy persistence models | 3 |
| `Dockerfile` | Application image build instructions | 5 |
| `metrics.py` | Request, error, and database measurements | 7 |
| `tracing.py` | OpenTelemetry setup and instrumentation | 8 |

The API, database, Docker, metrics, and tracing files are implemented. The Compose API is reached through NGINX on host port 8088.

`Dockerfile` uses Python 3.12.15 and the pinned runtime requirements, includes the
SQL seed file, and runs as UID 10001. Compose builds API, payment, and `db-init`
images from this recipe with separate tags and shared cached layers. Different
commands select their roles. Source is copied into images, so rebuild after edits.

For the native workflow, run from the repository root using
`python -m uvicorn app.main:app` after
activating the virtual environment and initializing PostgreSQL with
`python -m app.database`. Database routes use ordinary `def` functions, which
FastAPI runs in worker threads; the payment route uses async HTTP I/O.
See the [Phase 3 lesson](../docs/phase-03-postgresql.md) for database examples and
the [native Phase 4 commands](../docs/phase-04-nginx.md#run-the-local-proxy) for
running behind NGINX. The [Phase 5 lesson](../docs/phase-05-docker-compose.md)
explains container startup, service-name URLs, and forwarding-header trust.

`metrics.py` gives each app instance an independent Prometheus registry. The API
and payment service expose `/metrics`; middleware records bounded HTTP categories,
and SQLAlchemy records successful/failed cursor durations. All durations use
seconds. Request IDs, raw SQL, and order IDs are not metric labels. See the
[Phase 7 lesson](../docs/phase-07-metrics.md) for timing and single-worker limits.

`tracing.py` configures a private SDK provider for each app and a bounded batch
exporter during its lifespan. FastAPI creates server spans; only the payment HTTP
client is instrumented. SQLAlchemy event hooks create child spans for cursor
execution without recording SQL text or parameter values. Worker-thread context
preserves parent IDs. Application logs and responses expose the active trace ID.
Compose enables OTLP/HTTP export; native runs require an explicit endpoint.
See the [Phase 8 lesson](../docs/phase-08-distributed-tracing.md) for sampling,
provider ownership, graceful shutdown, and outage behavior.
