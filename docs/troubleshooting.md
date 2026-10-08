# Troubleshooting

## Jaeger is running but a trace is missing

Use `curl -i http://127.0.0.1:8088/payment` and copy `X-Trace-ID`. Open
`http://127.0.0.1:16686/trace/<trace-id>`, or query `/api/v3/traces/<trace-id>`.
Allow a few seconds for batching. Service discovery uses `/api/v3/services` in
the pinned Jaeger version. The minimal tracing images have no Docker health
probe; `compose --wait` alone does not verify delivery.

Check the application tracing endpoint and `OTEL_SDK_DISABLED`. Compose sets the
internal OTLP/HTTP URL ending in `/v1/traces`; native runs require an explicit
reachable endpoint. Published port 16686 is for querying, not OTLP ingestion.
Inspect `docker compose logs --tail 30 api payment otel-collector jaeger` and run
`python3 tests/tracing_smoke.py --no-build` for an isolated pipeline check.
An incoming unsampled parent retains an ID but exports no spans. `/metrics` is
excluded. Health probes can produce ordinary traces even without manual traffic.
Jaeger's internal self-tracing is disabled independently of application ingestion.

The Collector queue is bounded. Its internal metrics on port 8888 expose queue
size, refused spans, and export failures. SDK buffers and unqueued batches can
lose spans during outages; persistence is not an exactly-once delivery guarantee.
If the storage initializer fails, inspect `tracing-storage-init` before changing
UIDs: Collector and Jaeger need their own writable volumes as UID 10001.
Ordinary `down` retains those volumes; `down --volumes` erases traces and queues.

## A trace lacks an NGINX or PostgreSQL server span

NGINX forwards W3C context but has no tracing module in this lab. PostgreSQL spans
are client spans around SQLAlchemy cursor execution in `order-api`; the database
server has no SDK. A supplied curl parent can also appear as an absent external
parent because curl does not export it. Check span kind and service identity
before interpreting an absent span as dropped telemetry. A parent duration
includes its children; do not add both durations as sequential time.

## Metrics targets are down or Grafana has no data

Open Prometheus on port 9090 and inspect **Status → Targets**. Six jobs should
be up. `up=1` confirms a scrape, while `pg_up`, `nginx_up`, and
`node_scrape_collector_success` describe source collection. Check:

```bash
curl -s http://127.0.0.1:8088/metrics
curl -s 'http://127.0.0.1:9090/api/v1/targets'
docker compose logs --tail 30 prometheus nginx-exporter postgres-exporter node-exporter
```

`metrics-db-init` must exit 0 before the database exporter starts. Its separate
monitoring login needs `pg_monitor`; don't substitute the application owner as a
routine repair. NGINX status listens on internal port 8089, not public port 8088.
Health checks generate a small baseline; `/metrics` excludes itself.

Grafana's initial login is `admin` / `shopsphere_local`. Environment overrides set
initial credentials only; an existing account remains in `grafana_data`. Open
the **ShopSphere** folder, choose a recent range, generate traffic, and allow at
least two scrapes. A rate needs multiple samples; a percentile with no requests
can be a gap. Confirm the provisioned data source is `http://prometheus:9090`,
not host localhost. Dashboard edits belong in JSON; polling takes up to 30 seconds.

## Host metrics look different from Windows or Docker stats

On Docker Desktop/WSL, CPU, memory, and block I/O describe the shared Linux VM
kernel, not Windows or an individual container's limits. On native Linux they
describe the Docker host. Storage capacity describes the filesystem containing
Docker's log directory, normally Docker's data disk, rather than every host mount.

WSL can put unescaped spaces in Windows-share mount metadata. Instead of using
the affected filesystem parser, this lab measures `/docker-storage` with `stat`
and publishes it through node exporter's textfile reader. Check
`shopsphere_docker_storage_collection_success`, `node_textfile_scrape_error`, and
the **Storage capacity sample age** panel. An increasing age means stale values;
inspect `docker compose logs node-exporter`. Run `bash elastic/prepare-docker-logs.sh`
if the external source volume is missing, even for metrics-only startup. The
collector needs no whole-host-root bind or recursive host volume.

## Samples are missing after sleep or backend restart

Prometheus does not backfill missed scrapes. Existing samples survive replacement
in `prometheus_data`, but gauges during an outage are lost and process counters
may reset. Use `rate()` before summing counters. WSL clock corrections can produce
out-of-order sample warnings; check system/VM time, allow it to stabilize, and
retry. Do not delete retained history as a routine clock repair.

## Kibana is empty although Agent is healthy

Choose **ShopSphere logs** in Discover, set **Last 15 minutes**, generate a new
request ID, and allow a few seconds for collection/index refresh. Check each hop:

```bash
curl -H 'X-Request-ID: logging-check' http://127.0.0.1:8088/payment
docker compose ps --all
docker compose logs --tail 40 elastic-setup elastic-agent
curl -s http://127.0.0.1:9200/_data_stream/logs-shopsphere.*-lab
```

`elastic-setup` must exit 0. Rerun failed setup after dependencies recover with
`docker compose up -d --wait --wait-timeout 360`. Setup retries HTTP 429/502–504
responses during initialization. `tags: "parse_error"` in Discover identifies
records the ingest pipeline could not normalize; expand `error.message` and
`event.original`.

On Docker Desktop/WSL, a healthy reader can point at the wrong distro's old
`/var/lib/docker/containers`. Prepare the actual source and recreate Agent:

```bash
bash elastic/prepare-docker-logs.sh
docker compose up -d --no-deps --force-recreate --wait elastic-agent
```

The helper creates/reuses the external `shopsphere_docker_logs` volume against
the actual daemon's container directory; its definition survives restarts. On
WSL it uses Docker Desktop's Windows CLI, verifying both clients target the same
daemon. Do not fix log access by broadening permissions or mounting the socket.
Collection is limited to the current Compose project; old native phase exercises
will not appear. Files must grow to their configured fingerprint length before
being read (1024 bytes for Docker, 64 for PostgreSQL).

## Elastic startup is slow or fails with an out-of-memory exit

The initial images are large and Kibana needs time to initialize saved objects.
Use `--wait-timeout 360`, inspect `docker stats --no-stream`, and allocate roughly
8 GiB or more for the combined lab. The standalone logging smoke test launches a
second Elastic stack; temporarily stop the regular Agent, Kibana, and Elasticsearch
to free memory, then restore them after the test. Their volumes remain intact.
The Agent limit is 1 GiB, Kibana 1.5 GiB, and Elasticsearch 2 GiB with a 512 MiB heap.

Elasticsearch clock warnings can follow host sleep or clock correction under WSL.
Check the host/VM time and readiness; do not delete persistent data to clear them.
If ports 9200/5601 are occupied, set `ELASTICSEARCH_PORT`/`KIBANA_PORT` in `.env`.
The configured `node.store.allow_mmap=false` avoids requiring a host sysctl change.

## A bind mount fails after restarting Docker Desktop/WSL

Desktop can retain a stale cross-distro bind path after a host restart. A
PostgreSQL startup error mentioning `shopsphere.conf` and "not a directory" can
mean the old file mount was restored as an empty directory. Confirm the source
`postgres/postgresql.conf` still exists, verify the log volume, and recreate
containers using their retained named volumes:

```bash
bash elastic/prepare-docker-logs.sh
docker compose up --force-recreate -d --wait --wait-timeout 360
```

This replaces containers without deleting orders, indexed logs, or collection
state. For the older native database, use
`docker compose -f postgres/compose.yml up --force-recreate -d --wait`.

## Old logs reappear or source storage grows

Keep Agent input IDs, fingerprints, and its state volume stable. Deleting the
registry or changing file identities can cause replay; an unacknowledged batch
may duplicate after a crash. Docker rotates three 10 MB files, but container
removal deletes them. PostgreSQL rotates files without age-based cleanup; monitor
the data volume and plan separate archival/cleanup for long-running use.
Elasticsearch's seven-day lifecycle applies after index rollover and does not
delete source files. See the [Phase 6 lesson](phase-06-centralized-logging.md).

This guide covers the Compose application, logs, metrics, and earlier native
Python/NGINX workflow.

## Compose startup fails or a service is unhealthy

Run `docker compose ps --all`, then inspect the failing service with
`docker compose logs --tail 50 <service>`. PostgreSQL health gates `db-init`;
successful initialization and payment health gate the API; API health gates
NGINX. The API's probe calls `/products`, so a database problem affects readiness.
Use `docker compose config --quiet` to check configuration before startup.

An unhealthy flag alone does not restart a running process. Repair the dependency
and retry, or restart the affected service if its process requires it. Dependency
conditions primarily govern startup, not continuous recovery orchestration.

## db-init shows Exited (0)

This is expected. The one-time initialization command succeeded. An exit code
other than zero blocks API startup; inspect `docker compose logs db-init`.
After fixing configuration, run `docker compose up -d --wait` again. Do not use
volume deletion as a routine initialization repair: it erases orders.

## Edited Python or proxy configuration is not taking effect

These files are copied into images. Run `docker compose up --build -d --wait`
after editing them. `docker compose restart` uses the existing image and does
not rebuild. Inspect the active proxy with `docker compose exec nginx nginx -T`.
The database configuration is a read-only bind mount; restart PostgreSQL to
apply startup-only settings.

## localhost cannot reach another container

Inside a container, localhost is that container. Compose configures the API with
`postgres:5432` and `payment:8001` and NGINX with `api:8000`. NGINX is the only
application host port; the telemetry UIs have separate loopback ports.
Inspect DNS with:

```bash
docker compose exec api python -c "import socket; print(socket.gethostbyname('postgres'))"
```

The native localhost URLs in `.env.example` apply to host Python processes,
not the Compose services.

## An API replacement briefly produces proxy failures

The new container may have a different address. The container proxy uses Docker
DNS with a five-second refresh interval; retry after the API becomes ready and
DNS refreshes. Inspect `docker compose logs nginx api` for upstream and startup
errors. The native Phase 4 configuration uses a fixed localhost upstream and
does not apply inside the container network.

## Creating the virtual environment fails

Use Python 3.12. If `python3.12 -m venv .venv` reports that `ensurepip` is missing,
install your distribution's matching Python venv support, or use the `uv venv`
alternative in the README. Verify the result with `.venv/bin/python --version`.

## Python cannot import app, FastAPI, or payment

Run the documented commands from the repository root and use `.venv/bin/python`.
Install `requirements-dev.txt` into that environment. Avoid launching
`python app/main.py`; launch the package through
`python -m uvicorn app.main:app` instead. This also avoids confusing the local
`app/logging.py` module with Python's standard-library logging package.

## The port is already in use

The Compose proxy publishes port 8088. Stop an earlier native lab proxy with
`bash nginx/manage.sh stop`, or use `SHOPSPHERE_PORT=8089 docker compose up -d --wait`.
Keep that override in `.env` if using the alternate port for later commands.

For native runs, another process may already be listening on 8000 or 8001. Stop your previous lab
server, or choose another port with Uvicorn's `--port` option. If changing the
payment port, export a matching `PAYMENT_BASE_URL` before starting the API.
Do not terminate an unrelated process just to free the default port.

The lab's NGINX listens on 8088. Change its `listen` directive if needed, then run
`bash nginx/manage.sh test` before starting or reloading. If changing the API port,
also update the `upstream shopsphere_api` server address in `nginx/nginx.conf`.

## NGINX is missing or complains about permissions

This section concerns native runs; the Compose image includes NGINX.
Run `nginx -v` in the same Linux/WSL shell as Python. Install the distribution's
NGINX package if needed; `NGINX_BIN` can select an alternative executable. Start
with `bash nginx/manage.sh start` so the configuration prefix, PID file, logs,
and temporary files all belong to this lab. These commands do not need sudo.

## The proxy health check passes, but API requests return 502

`/proxy-health` checks only NGINX. In Compose, check `docker compose ps api`
and `docker compose logs nginx api`. A stopped Docker peer can produce 502 or
504 depending on whether connection failure or timeout is observed.

For native runs, confirm that Uvicorn is listening on
`127.0.0.1:8000` and that the proxy's upstream address matches. Check
`nginx/runtime/error.log` for a connection error and use its `*connection` number
with the access log's `connection` field, timestamp, and path.

If `/payment` returns a JSON 502/504 and the API logs `payment.failed`, the proxy
reached the API but the payment dependency failed. An `upstream_status` of 502
alone does not distinguish these cases; inspect logs at both layers.

## An application error is absent from the NGINX error log

An API-generated 500 is normally a valid HTTP response that NGINX passes through.
Look for its status and request ID in `docker compose logs nginx` (or native
`access.jsonl`), then find the application
exception using that ID. The native error log records proxy/connection problems,
not every HTTP error status.

## NGINX returns 504 for a slow request

Inspect the native error log for an upstream timeout. The checked-in read timeout
is 30 seconds between upstream reads, allowing the five-second SQL exercise.
Check for local configuration changes, an overloaded API, or a stalled dependency.
The timeout tests shorten it only in a temporary copy of the configuration.

## A native NGINX reload failed or an old configuration is still serving

Run `bash nginx/manage.sh test` and correct the reported error. The reload helper
tests before signalling, so an invalid file does not replace the running
configuration. Restore valid configuration and run `bash nginx/manage.sh reload`.
Use the same helper to stop the lab instance; system service commands target a
different NGINX instance.

## NGINX runtime files are absent from Git status

This is intentional. `nginx/runtime/` contains generated logs, the PID file, and
temporary buffers. Only configuration, the helper, tests, and documentation belong
in the commit. Access events are JSON; native error messages are plain text and
may include the original request URI, including query parameters.

## Payment returns 502 or 504

In Compose, check `docker compose ps payment` and `docker compose logs payment api`.
Use `docker compose start payment` to recover from the stop exercise. A missing
Docker peer may cause a connection timeout (504) instead of a prompt failure (502).

For native runs, check that the mock service is running and responds at
`http://127.0.0.1:8001/`. Then inspect the API's `payment.failed` event using the
response's `X-Request-ID`. A connection failure, upstream HTTP error, or invalid
response produces 502; an HTTP client timeout produces 504.

The defaults assume both processes run in the same Linux/WSL environment.
Native Python does not load `.env` automatically; Compose does read it for interpolation.
For another address, export `PAYMENT_BASE_URL` in the API's shell before startup.

## An order disappeared

Restarting the API should preserve orders. Check the Compose project name and
volume with `docker compose ps --all` and `docker volume ls`. The root stack uses
`shopsphere_postgres_data`; the earlier native database uses
`shopsphere-phase3_postgres_data`. They hold different orders. Changing the
project name selects different resources; it does not migrate data.

For native runs, also check whether `DATABASE_URL` points to the expected database.
`docker compose down` retains it; `down --volumes` deletes it. Orders created under
the old Phase 2 in-memory version cannot be recovered after that process exits.

## The API reports that the database is not ready

For the complete application, run `docker compose ps --all`, inspect
`docker compose logs db-init postgres api`, and correct the startup failure.
`docker compose up -d --wait` includes initialization and health ordering.

For native runs, use `docker compose -f postgres/compose.yml ps`, then start with
`docker compose -f postgres/compose.yml up -d --wait`. Run
`.venv/bin/python -m app.database` before starting the API to create missing tables
and seed products. Verify that your exported `DATABASE_URL` matches the database.

If 5432 is occupied, export `POSTGRES_PORT=5433` before starting this Compose
project and use port 5433 in `DATABASE_URL` too. The application uses the
`postgresql+psycopg://` URL scheme. Invalid configuration fails validation.

Changing the Compose password does not change a role in an existing data volume:
the official image's initialization variables apply when the data directory is
empty. Keep the settings consistent or deliberately manage the database role.

## Database requests return 503

Find `database.query_failed` and `database.unavailable` events using the response's
request ID. Inspect the database's JSON logs for SQLSTATE and error details.
Connection failures and failed database operations return a generic 503; an
unknown product still returns 404. A failed transaction is rolled back before
its session closes. After the database recovers, the pool checks connections
before reuse.

## Docker logs do not show the slow SQL statement

PostgreSQL's logging collector writes runtime events into `$PGDATA/log/` inside
the persistent volume. For the root stack, run
`docker compose exec -T postgres sh -c 'cat "$PGDATA"/log/*.json'`.
For the older native database, use the inspection command in the
[Phase 3 lesson](phase-03-postgresql.md#inspect-native-postgresql-logs).
`docker compose logs` mainly shows startup messages once the collector is active.
Statements shorter than 250 ms are not included in the native slow-statement log.

## Tests require Docker or cannot start PostgreSQL

The suite now uses real PostgreSQL. Check `docker version` and network access for
the first image pull. Tests start a uniquely named temporary container and drop
only their own generated databases; they do not connect to the ordinary lab
database. An unavailable test database is a test failure, not a skipped check.

## Application events are JSON, but some console messages are plain text

Uvicorn writes its own startup and shutdown messages to stderr. ShopSphere writes
its structured application events to stdout. `--no-access-log` disables duplicate
Uvicorn access logs. If collecting the JSON stream into a file, redirect stdout;
do not combine stderr into that file.

## Git says this is not a repository

Run `pwd` and confirm that your shell is in this project or one of its
subdirectories. From this workspace, the following should locate its root:

```bash
git rev-parse --show-toplevel
```

Phase 1 initialized a `.git/` directory at the workspace root. It is hidden in
many file browsers. Do not create another repository inside a service directory.

## Git cannot create a commit because identity is missing

Inspect the configured identity:

```bash
git config user.name
git config user.email
```

If needed, set your own name and email for this repository using
`git config --local user.name "Your Name"` and
`git config --local user.email "your-email@example.com"`. The placeholders should
be replaced with the identity you want associated with your commits.

## A file does not appear in Git status

Check whether an ignore rule matches it:

```bash
git check-ignore -v .env
```

Local `.env` files, logs, caches, and virtual environments are intentionally
ignored. Future sanitized templates such as `.env.example` may be tracked.
Use `git ls-files` to inspect the files Git is already tracking.

## Docker Compose reports that no configuration file exists

Run from the repository root, which contains `docker-compose.yml`, or pass its
path with `docker compose -f /path/to/docker-compose.yml ...`. Earlier native
database exercises explicitly use `-f postgres/compose.yml`; that file starts
only the separate Phase 3 database.

## Git shows unexpected line-ending changes

The project uses `.gitattributes` for LF line endings in new text files, with an
exception for the preserved original brief. Inspect the effective attributes:

```bash
git check-attr text eol -- README.md docs/implementation-spec.md
```

Use an editor that respects `.editorconfig` and inspect `git diff` before
committing broad formatting changes.

## The architecture diagram appears as text

The README uses a Mermaid code block. A Markdown viewer without Mermaid support
will show the diagram source. The component table and request-flow explanation
in [architecture.md](architecture.md) provide the same design in plain text.
