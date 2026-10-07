# Architecture

Status: Phase 7 runs the application, centralized logging, and metrics through Compose.
Elastic Agent collects logs for Elasticsearch/Kibana; Prometheus scrapes metrics
for Grafana. Distributed tracing remains planned.
The [main README](../README.md#3-architecture-diagram) contains the target diagram.

Current path: client → NGINX → FastAPI → SQLAlchemy/Psycopg → PostgreSQL. A separate
`GET /payment` path calls the mock payment service over HTTP. Order creation does
not trigger payment.

The root `docker-compose.yml` defines project `shopsphere`, application and
telemetry bridge networks, twelve long-running services, and three initialization
jobs. NGINX publishes `127.0.0.1:8088`; Elasticsearch and Kibana publish loopback
ports 9200 and 5601; Prometheus and Grafana publish 9090 and 3000. Exporter ports
and NGINX status port 8089 remain internal. NGINX forwards to `api:8000`; the API uses
`postgres:5432` and `payment:8001`. Service names resolve through Docker DNS.
NGINX re-resolves its upstream so an API address change needs no proxy restart.

NGINX replaces caller-supplied forwarding headers. The container API trusts
forwarding headers from all peers because it is confined to this lab's project
network with no host port. Other containers on that network share this trust;
production must narrow the trusted proxy/network boundary.

PostgreSQL health gates `db-init`, successful initialization and payment health
gate API startup, and API health gates NGINX startup. The API health check reads
`/products`, covering database access. The proxy health check covers only NGINX.
Dependency conditions control startup; they do not continuously restart dependent
services. Application pools and the proxy resolver handle recovery.

The database's `shopsphere_postgres_data` volume is mounted at
`/var/lib/postgresql`, the PostgreSQL 18 image's persistent storage location.
Images and containers can be replaced while this volume retains orders.
The older native workflow retains its separate `shopsphere-phase3` database
project, local Python processes, and private NGINX prefix under `nginx/`.
It uses different data and cannot share host port 8088 with the Compose proxy.

Python containers run as UID 10001; NGINX uses its non-root image user. Their
filesystems are read-only except temporary `/tmp` mounts. Runtime source and
NGINX configuration are baked into images; PostgreSQL configuration is mounted
read-only from the repository. Native and container proxies share the files
under `nginx/includes/` for logging and request forwarding.

NGINX preserves accepted request IDs or creates a 32-character hexadecimal ID.
It forwards that ID to the API and returns a single response header, including on
proxy failures. Its 30-second upstream read timeout permits the five-second
database delay. Refused connections or unavailable upstreams produce 502;
upstream connection/read timeouts produce 504. API error responses pass through
without being rewritten.

`products` holds the current catalogue. `orders` and `order_items` hold committed
orders and snapshots of the purchased names/prices. Each operation opens its own
SQLAlchemy session; order creation commits the order and its items together
before the route logs success. Later price changes do not rewrite earlier orders.

Database routes run synchronous Psycopg I/O in FastAPI worker threads. One engine
per API instance manages a pool of up to ten connections (five retained plus five
overflow); sessions are never shared across concurrent requests. Startup checks
the database, and shutdown disposes the pool.

## System boundaries

ShopSphere has two connected parts: the services that handle shopping
requests and the services that help us understand their behavior.

| Component | Responsibility | Connects to |
| --- | --- | --- |
| NGINX | Receive requests and forward them to the API | Client, FastAPI |
| FastAPI | Validate inputs and implement product and order behavior | PostgreSQL, payment service |
| PostgreSQL | Persist products and orders | FastAPI, database exporter |
| Mock payment service | Simulate a separate payment dependency | FastAPI |
| Elastic Agent | Collect and process logs | Log sources, Elasticsearch |
| Elasticsearch | Index and store logs | Elastic Agent, Kibana |
| Kibana | Search and explore logs | Elasticsearch |
| Exporters | Expose NGINX, database, and host measurements | Source systems, Prometheus |
| Prometheus | Scrape and store metric samples | Application, exporters, Grafana |
| Grafana | Visualize metrics | Prometheus |
| OpenTelemetry SDKs | Create spans and propagate context | Application, payment service, Collector |
| OpenTelemetry Collector | Receive, process, and forward spans | SDKs, Jaeger |
| Jaeger | Store and display traces | Collector |

Telemetry is a record of the request's execution. The checkout request does not
pass through Grafana, Kibana, or Jaeger on its way to the database.

## Repository organization

Application source belongs in `app/` and `payment/`. Configuration for a service
belongs in its named directory. Cross-cutting explanations belong in `docs/`.
This lets a learner locate a change by asking which component owns the behavior.

The root Compose file connects the containers, network, storage, and settings.
The files listed in the original brief are planned deliverables, not empty
executable placeholders in Phase 1.

The project uses the existing workspace root. The additional `payment/` directory
gives the required mock payment service its own source location.

## Request and signal flows

The request path is client → NGINX → FastAPI → database and/or payment service.
The API's business logic determines which downstream operations are needed.

Logs originate at their sources: NGINX access JSON on stdout and error text
on stderr, application JSON on stdout, and PostgreSQL JSON in its volume.
Compose sets Docker log rotation to 10 MB and three files per container. This
does not retain source logs after container removal. Native
Phase 4 NGINX runs still write to ignored `nginx/runtime/`.
NGINX timings are seconds; application and SQL event durations are milliseconds.
Phase 6 collects and normalizes these events through Elastic Agent and
Elasticsearch, with Kibana for exploration. The Agent reads Docker files through
a read-only external bind volume, filters Compose project/service labels, and separately
reads PostgreSQL's log-directory volume subpath. It has no Docker socket.
The mounted Docker directory remains readable by the Agent even for projects
excluded from publication; this is not a multi-tenant isolation mechanism.

The setup job installs lab-owned ingest and index assets and a Kibana data view.
Agent starts after setup succeeds. App readiness is independent of telemetry.
One replica-free Elasticsearch node stores two data streams, with daily/1 GiB
rollover and deletion seven days after rollover. PostgreSQL source logs rotate
but need separate archival/cleanup for extended use. Agent's registry and
Elasticsearch data live in separate persistent volumes. Source rotation can lose
unread events during a long output outage; failed batches may be replayed.

Metrics flow from the application and exporters to Prometheus in response to
scrapes initiated by Prometheus every five seconds. Prometheus joins both networks;
Grafana queries it over telemetry DNS. Each Python app owns a registry and runs one
worker process. HTTP counters use route templates and bounded methods/statuses;
SQL cursor histograms distinguish success and failure. Scrape requests exclude
themselves; existing health checks remain ordinary measured requests.

NGINX's internal status listener supplies aggregate connections/request counts.
The database exporter uses a separate `pg_monitor` role installed by the rerunnable
`metrics-db-init` job, without grants on application table contents. Node exporter
reads global Linux kernel CPU, memory, and block I/O counters through its normal
proc/sys views. On Desktop these describe the Linux VM. Docker storage capacity
uses `stat` through the existing non-recursive, read-only Docker log source volume,
with atomic textfile publication, collection success, and sample-age signals.
This measures the filesystem containing Docker's logs; it excludes other host
filesystems, Windows metrics, and container resource limits. The trusted collector
runs as non-root with dropped capabilities and no host root or Docker socket mount.

Prometheus retains time-series blocks for seven days or 512 MB, with additional
space needed for its WAL/head and compaction. Grafana provisions its data source
and three versioned dashboards, retaining accounts/preferences in a separate
volume. Neither backend gates application startup. Missing scrapes create gaps;
persistent storage preserves older samples but cannot reconstruct those gaps.

Spans flow from instrumented services to the Collector and then to Jaeger. The
FastAPI and payment services will propagate trace context over HTTP, while
SQLAlchemy instrumentation will create database client spans in the API process.
Those spans do not require installing an application SDK inside PostgreSQL.

The services propagate `X-Request-ID` for log correlation only. SQL statements also
carry the validated ID in a comment, making it visible in native slow/error logs.
No tracing SDK or
export pipeline has been configured, and application logs report `trace_id: null`.

NGINX is now part of the request path. Forwarding trace context and producing a
proxy span are separate behaviors. Native NGINX spans require explicit proxy
instrumentation; module and image support will be checked in Phase 8 before
claiming that the proxy appears as a span.

## Timing and correlation

A trace ID connects related spans and can also be written into application logs.
Metric labels describe bounded categories, such as route templates and
outcomes. Per-request IDs do not become metric labels, because each unique
label combination creates a separate time series.

For a request that synchronously waits on a five-second SQL operation, its parent
span covers that wait. Additional sequential work extends the total request
duration. The original brief's 500 ms application work and five-second database
work therefore imply approximately 5.5 seconds overall in that scenario.

## Decisions deferred to their implementation phases

Python dependencies are pinned. The container bases pin Python 3.12.15, NGINX
1.30.5, and PostgreSQL 18.6 by version and digest. `SHOPSPHERE_PORT` changes the
proxy's host port; `PAYMENT_TIMEOUT_SECONDS` changes the HTTP client timeout.
Compose injects service-name connection URLs; native defaults still use localhost.
Elastic components pin matching 9.5.4 images. The lab disables Elastic security
and binds host ports to loopback; production requires authentication and TLS.
Metrics components also pin image versions/digests. Grafana has a configurable
initial local account; Prometheus is unauthenticated on loopback. Tracing storage
and capacity choices remain for Phase 8.
