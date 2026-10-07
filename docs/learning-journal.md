# Learning journal

Each implementation milestone records what changed, why it changed, the concept
introduced, and its production equivalent. Entries are included in the milestone
commit so its documentation travels with the implementation. Use
`git log --oneline` to find the corresponding commit ID.

## 2026-10-05 — Phase 1: Repository foundations

Commit subject: `chore: initialize project structure`.

### What changed

- Initialized Git on the `main` branch in the existing workspace.
- Preserved the original README verbatim as `docs/implementation-spec.md`.
- Replaced the root README with a learning guide and a nine-phase roadmap.
- Created component directories with explanations of their responsibilities.
- Added `payment/` for the mock service required by the project scenario.
- Added architecture, troubleshooting, and learning notes.
- Added Git ignore rules, editor defaults, and cross-platform line-ending rules.

### Why it changed

The original file was an implementation brief. The working repository now needs
an entry point that accurately describes the current phase and guides future
changes. Component directories make source and configuration easy to locate,
while preserving the brief keeps the original requirements available.

### DevOps concepts introduced

Repository organization, separation of component responsibilities, the Git
working tree and staging area, meaningful commits, source versus runtime data,
and documentation maintained alongside implementation.

The trace timing example was clarified: a parent request waiting on a five-second
database operation includes that wait in its total duration. The original brief
remains unchanged.

### Production equivalent

A team keeps deployable source and configuration under version control, reviews
changes as commits, and maintains architecture notes and runbooks alongside the
services they describe. Runtime data and local credentials are managed outside
the source repository.

### Verification

- Confirmed all 12 component directory guides and four learning documents exist.
- Checked all 14 required README sections and all 10 local documentation links,
  including linked headings.
- Checked LF line endings, final newlines, and balanced code fences in the 17
  authored Markdown files.
- Verified that the preserved specification's SHA-256 matches the original:
  `b3977549d2df06fbbb51e4e5e66c6e0257c9bb8e8495463ed42096400bfc6384`.
- Checked that environment files, runtime output, and Python caches are ignored,
  while sanitized environment-example filenames remain eligible for tracking.
- Passed `git diff --cached --check` for the staged milestone files.
- No application or telemetry tests were run: this phase contains documentation
  and repository configuration only.

### Learner checkpoint

Complete the exercises in [learning-notes.md](learning-notes.md#practice-checkpoint).
The scaffold is implemented; the learner's understanding has not been assessed.

### Next phase

Phase 2 will implement the FastAPI application and structured application logging.
No application, container, database, or telemetry runtime was implemented in
Phase 1.

## 2026-10-05 — Phase 2: FastAPI and structured logging

Commit subject: `feat: create FastAPI ecommerce service`.

### What changed

- Implemented the order API with product listing, order creation and retrieval,
  an intentional error endpoint, and an outbound payment demonstration.
- Added a separate mock payment service that returns simulated approvals.
- Added strict order input validation, catalogue-based prices in integer cents,
  and a temporary in-memory order store.
- Added JSON request, business, error, and lifecycle logs to stdout.
- Added validated request IDs, response headers, cross-service ID propagation,
  and context isolation for concurrent requests.
- Added a reusable HTTP client with validated environment settings and explicit
  502/504 dependency failure responses.
- Pinned runtime and test dependencies, added tests and lint configuration, and
  documented setup, request examples, debugging exercises, and limitations.

### Why it changed

A working application is needed before telemetry collection can be meaningful.
This phase exposes normal operations, invalid inputs, application exceptions,
and HTTP dependency failures while keeping database concepts separate.

### DevOps concepts introduced

REST routes and HTTP status codes, input validation, application lifecycle,
environment configuration, in-memory process state, structured JSON events,
request correlation, concurrent execution contexts, and dependency timeouts.

### Production equivalent

Services validate inputs at their boundaries, calculate authoritative values on
the server, reuse connection pools, and provide searchable operational events.
Correlation IDs let an operator connect events from multiple processes.
Production order storage requires durability and shared state; this lab introduces
that with PostgreSQL in Phase 3. The mock payment route does not charge money.

### Verification

- Python 3.12.3; all 27 pytest cases passed.
- Ruff lint and formatting checks passed; installed dependency compatibility
  checks passed.
- Live smoke check started separate Uvicorn processes on temporary local ports
  and verified catalogue access, order creation and lookup, API documentation,
  OpenAPI, the payment call, and an intentional 500 response.
- Stopping the payment process produced 502 from the API; the API remained
  responsive afterward. Both temporary servers were stopped after the check.
- Parsed all 21 application events from the live check as JSON and verified
  matching request IDs across payment logs and error events.
- Checked documentation links, the 14 README sections, formatting, and the
  preserved original specification's unchanged SHA-256.

### Learner checkpoint

Follow [Phase 2](phase-02-fastapi.md), create an order, find its log events, and
explain why a restart loses that order. Then follow one payment request through
both service logs. Passing tests verifies the implementation; these exercises
verify your understanding.

### Next phase

Phase 3 will add PostgreSQL persistence, SQLAlchemy, SQL logging, and controlled
slow database queries. `/slow-query` and `/metrics` are not implemented yet;
logs have request IDs but no OpenTelemetry trace IDs.

## 2026-10-05 — Phase 3: PostgreSQL and SQL observability

Commit subject: `feat: integrate PostgreSQL database`.

### What changed

- Replaced the in-memory store with SQLAlchemy 2.0.54 and Psycopg 3.3.6 connected
  to PostgreSQL 18.6.
- Added products, orders, and order-item tables with keys and check constraints.
  Item names and prices are stored as purchase-time snapshots.
- Added request-local transactions, connection pooling, startup readiness checks,
  shutdown cleanup, and generic 503 responses for failed database operations.
- Added explicit, repeatable table initialization and catalogue seeding.
- Added a database-only Compose file with persistent storage and native JSON
  connection, slow-statement, and error logging.
- Added SQL duration/failure events and validated request IDs in SQL comments.
- Added `/slow-query` and an optional `db_delay_seconds` checkout parameter using
  real PostgreSQL waits, bounded to 0–5 seconds.
- Updated tests to use private PostgreSQL databases and added the Phase 3 lesson.

### Why it changed

Process memory cannot preserve orders across restarts or share them between API
instances. PostgreSQL provides persistent shared state, while a transaction keeps
an order and all its items atomic. Real database waits and database-generated logs
give the observability exercises evidence from an actual dependency.

### DevOps concepts introduced

Relational models, foreign keys, database constraints, connection pools, sessions,
flush versus commit, rollback, persistent volumes, explicit initialization, SQL
timeouts, native database logs, and recovery after dependency failure.

### Production equivalent

Services store durable business state in a database, bound their connection usage,
and use transactions to prevent partial writes. Production also needs reviewed
schema migrations, distinct runtime/migration privileges, managed credentials,
backups, and retention policies. The local owner account and create-missing-tables
command are teaching tools; those production controls remain future work.

### Verification

- All 39 pytest cases passed against a temporary real PostgreSQL container.
- Verified atomic rollback after a database-rejected item insert, independent
  concurrent transactions, price snapshots, repeated initialization, and shared
  orders across API instances and restarts.
- Verified real SQL delay timing, bound enforcement, statement-timeout rollback,
  and request-ID correlation with PostgreSQL's native slow-statement logs.
- Live HTTP checks confirmed an order survived API and PostgreSQL restarts;
  database outage produced 503 and recovery restored access to that same order.
- Live checks exercised the default five-second query, delayed checkout, payment,
  intentional application failure, API docs, and OpenAPI.
- Parsed 43 live application JSON events and checked matching PostgreSQL slow
  logs plus a database-only division-by-zero event with SQLSTATE `22012`.
- Ruff lint/format, dependency compatibility, Compose configuration, documentation
  links, and whitespace checks passed. The original specification is unchanged.

### Runtime state after verification

The lab PostgreSQL container is healthy on localhost:5432, with the named data
volume retained. One verification order remains:
`0a31f891-3f26-4c16-8f78-02e55ecac438`. Temporary API/payment processes and the private
test container were stopped or removed after verification.

### Learner checkpoint

Follow [Phase 3](phase-03-postgresql.md): retrieve an order after restarting the
API, locate a slow SQL statement by request ID, and compare checkout duration
before and after removing the injected delay.

### Next phase

Phase 4 will introduce NGINX as the reverse proxy and add its access and error
logs. Full application containerization, centralized collection, metrics, and
distributed tracing remain in their later phases.

## 2026-10-05 — Phase 4: NGINX and the proxy boundary

Commit subject: `feat: add nginx reverse proxy`.

### What changed

- Added a dedicated local NGINX configuration on loopback port 8088, forwarding
  to the API on port 8000 with route, body, query, host, and response preservation.
- Added a Bash helper for configuration checks, startup, foreground execution,
  graceful reload, and shutdown using this repository's prefix and PID file.
- Added JSON access events with request IDs, status, upstream timings, and
  connection numbers; native proxy errors remain text in a separate file.
- Matched the API's request-ID validation and returned one ID header even for
  proxy-generated failures. Replaced incoming forwarding headers at the entry
  proxy and documented Uvicorn's explicit loopback trust.
- Added proxy-only health, a 1 MiB body limit, upstream timeouts, and disabled
  automatic upstream retries. API error responses pass through intact.
- Added real NGINX integration tests, the Phase 4 lesson, runtime ignore rules,
  and updated startup instructions, architecture, and troubleshooting guidance.

### Why it changed

Application logs cannot describe requests that fail before reaching the API.
The reverse proxy provides a stable entry point and a second view of request
status and duration. Comparing that view with application and database events
helps locate the failing or slow component.

### DevOps concepts introduced

Reverse proxies, upstream servers, connection reuse, forwarding-header trust,
request correlation across boundaries, access versus error logs, timing units,
configuration validation, process prefixes and PID files, graceful reloads,
and the difference between proxy health and end-to-end application readiness.

### Production equivalent

An ingress proxy commonly manages TLS, request routing, and traffic across API
replicas. Operators compare its access/error evidence with application telemetry.
Production requires deliberate proxy trust, network access, timeouts, retries,
and log retention. This phase uses one API and a local unprivileged NGINX process;
image pinning and container networking arrive in Phase 5.

### Verification

- All 50 pytest cases passed, including 11 real proxy integration cases, against
  isolated PostgreSQL databases and temporary NGINX/API/payment processes.
- Verified body and response forwarding, API docs, host-preserving redirects,
  request-ID generation/validation, JSON escaping, and payment correlation.
- Verified API error pass-through, proxy 502 and recovery, proxy-only health,
  504 with an isolated shortened timeout, and 413 before reaching the API.
- Verified correlated slow SQL at the proxy, API, and native PostgreSQL log,
  valid reload, invalid configuration rejection, and graceful shutdown.
- Live checks used the unchanged configuration on ports 8088, 8000, and 8001.
  The Phase 3 order remained available, and a new order survived API restart.
  The default five-second database query took 5.012 seconds at the proxy.
- Parsed 14 live proxy access events, 40 application events, and the two new
  PostgreSQL slow-query events. One retained startup log record contained NUL
  bytes and could not be parsed as JSON; verification selected this run's new
  records, and the historical log was preserved unchanged.
- NGINX syntax, Bash syntax, Ruff lint/format, dependency compatibility, Compose
  configuration, documentation links, and whitespace checks passed. All 14
  required README sections remain, and the original specification is unchanged.

### Runtime state after verification

The existing PostgreSQL container was stopped when the session resumed. It was
restarted with its original named volume and is now healthy on localhost:5432.
The Phase 4 verification order is `400c963d-694a-42cf-af45-e31487d3e4c8`.
The temporary proxy and Python servers were stopped; the private test container
was removed. The pre-existing system NGINX service was left running unchanged.
Live log files remain in ignored `nginx/runtime/` for inspection.

### Learner checkpoint

Follow [Phase 4](phase-04-nginx.md): compare an application 500 with an unavailable
API's proxy 502, follow one ID across log sources, and explain why proxy health
can succeed while product requests fail. Then restore the API and verify recovery.

### Next phase

Phase 5 will containerize NGINX, the API, and payment and connect them with
PostgreSQL in the root Compose application. Centralized collection, metrics,
and distributed tracing remain in Phases 6–8.

## 2026-10-05 — Phase 5: Images, containers, and Compose

Commit subject: `feat: containerize complete application`.

### What changed

- Added a Python Dockerfile with pinned dependencies and source, reused for the
  API, payment, and initializer with distinct image tags and runtime commands.
- Added the NGINX Dockerfile and container configuration. Base images pin Python
  3.12.15, NGINX 1.30.5, and PostgreSQL 18.6 by both version and digest.
- Added the root Compose application with four long-running services, one-time
  database initialization, startup health dependencies, a bridge network, and
  a project-owned persistent PostgreSQL volume.
- Published only NGINX at localhost:8088. Internal calls use service names, and
  NGINX refreshes Docker DNS after API container replacement.
- Ran Python and NGINX as non-root users with read-only root filesystems and
  temporary writable mounts. Restricted build inputs with `.dockerignore`.
- Shared NGINX request-ID, forwarding, and log rules between native and container
  configurations. Container logs use stdout/stderr with bounded Docker rotation.
- Added an isolated Compose lifecycle check, the Phase 5 lesson, and updated
  startup, environment, architecture, and troubleshooting documentation.

### Why it changed

The application previously needed host-installed Python and NGINX plus several
manual startup steps. Versioned images and Compose now package those requirements
and describe how the services connect. Health conditions make startup ordering
explicit, while a volume separates durable orders from replaceable containers.

### DevOps concepts introduced

Image layers and build caching, build contexts, image tags and digests, containers
and process commands, non-root execution, project isolation, bridge networks,
service discovery, published versus internal ports, environment interpolation,
health checks, initialization jobs, persistent volumes, temporary filesystems,
graceful process shutdown, and container log streams.

### Production equivalent

A team builds versioned images and deploys them with explicit networking,
configuration, readiness, and persistent storage. Production also needs secrets,
schema migrations, image update policies, backups, capacity planning, TLS,
access control, and redundancy. This lab has one API replica, local teaching
credentials, and a shared trusted project network; it does not implement those
operating controls merely by running in containers.

### Verification

- All images built successfully with Docker Engine 28.3.0 and Compose 2.38.1.
- All 50 existing pytest cases passed after extracting the shared proxy rules.
- The Compose smoke suite used a unique project and temporary port, verified
  that failed initialization blocks the API, then verified successful startup
  and the configured health checks.
- Checked non-root Python/NGINX users, read-only root filesystems, and that API,
  payment, and PostgreSQL had no published host ports.
- Verified catalogue access, order creation/lookup, API docs, payment calls,
  application errors, request IDs, and correlated five-second SQL evidence in
  proxy, application, and native PostgreSQL logs.
- Verified payment and database outage responses and recovery, database-aware
  API readiness, and proxy-only health during an API outage. Docker peer loss
  can produce a connection timeout (504) instead of immediate refusal (502).
- Forced the replacement API onto a different IP by reserving its old address
  in the disposable network. NGINX recovered without container restart.
- Verified an order survived complete container/network removal and subsequent
  startup using the retained volume; repeated initialization preserved it.
- The smoke project, temporary address holder, network, and data volume were
  removed after the checks. The regular lab projects were not test targets.
- Live checks on localhost:8088 verified Phase 5 metadata, products, order
  creation/retrieval, docs, and payment. Checked runtime image contents excluded
  local credentials, Git history, virtual environments, tests, and runtime logs.
- Both earlier verification orders remained in the separate Phase 3 database.
- Ruff lint/format, Bash and NGINX syntax, Compose configuration, image dependency
  compatibility, documentation links, and whitespace checks passed. The original
  specification and all 14 required README sections are preserved.

### Runtime state after verification

The root `shopsphere` stack is running with four healthy services and successful
`db-init` exit code 0. The entry point is `http://127.0.0.1:8088`, and the root
volume is `shopsphere_postgres_data`. Verification order
`ab88ce70-07a0-4092-ba7a-65d20daf60b2` remains in that database.

The earlier `shopsphere-phase3` database was stopped when the session resumed;
it was restarted and its retained orders verified. It is healthy on host port
5432 with its original, separate volume. The two projects do not share data.
The user's untracked `cmd.sh` was left untouched.

### Learner checkpoint

Follow [Phase 5](phase-05-docker-compose.md): inspect service DNS, explain the
initialization dependency, retrieve an order after `down`/`up`, and recover the
application after stopping each dependency. Explain why rebuilding an image,
restarting a container, and deleting a volume have different effects.

### Next phase

Phase 6 will collect application, NGINX, and PostgreSQL logs with Elastic Agent,
store them in Elasticsearch, and make them searchable in Kibana. Metrics and
distributed tracing remain in Phases 7 and 8.

## 2026-10-05–06 — Phase 6: Centralized logging

Commit subject: `feat: implement centralized logging with ELK`.

### What changed

- Added digest-pinned Elasticsearch, Kibana, and standalone Elastic Agent 9.5.4,
  a separate telemetry network, health checks, memory limits, and persistent
  Elasticsearch/Agent volumes. The application images now use version 0.6.0.
- Added Docker log labels and a collector filter for the current project and
  allowed services. PostgreSQL is read through a read-only log-directory subpath;
  the collector has no Docker socket or access to database data files.
- Added a helper creating an external Docker log-source volume. Desktop/WSL uses
  the Windows Docker CLI to avoid rewriting its device path to the user distro.
  Native Linux uses its normal CLI; Agent mounts the resulting volume read-only.
- Added idempotent setup for parsing, explicit field mappings, two data streams,
  index lifecycle rules, and the **ShopSphere logs** Kibana data view. Setup
  retries temporary initialization HTTP errors without erasing data.
- Normalized service identity, timestamp, severity, HTTP fields, request IDs,
  business/query metadata, and durations in nanoseconds. Preserved raw events and
  made parser failures searchable instead of silently discarding them.
- Added an isolated logging smoke test and kept the earlier Compose lifecycle
  test limited to application services. Updated the README, component guides,
  architecture, troubleshooting, and the Phase 6 lesson.

### Why it changed

Finding one failure previously required reading several independent log sources.
Centralized collection and a consistent schema now let one request-ID search
connect proxy, application, payment, and database evidence. Separate collection
keeps Elasticsearch availability out of the shopping request path.

### DevOps concepts introduced

File harvesting, Docker log envelopes, source identity and fingerprints,
acknowledged offsets, standalone agents, ingest pipelines, structured parsing,
mapping types, event time, duration units, data streams and backing indices,
rollover/deletion policies, Kibana data views and KQL, delivery retries, and
verification of an entire telemetry path rather than only process health.

### Problems found during implementation

The initial 64-byte Docker fingerprint could match identical startup text in
different files. Docker now uses 1024 bytes, including unique timestamps/labels;
PostgreSQL retains a 64-byte fingerprint beginning with its timestamp.

The WSL user distro had an old `/var/lib/docker/containers` directory unrelated
to the active Docker Desktop daemon. Agent could read it and appear healthy while
publishing no ShopSphere container events. The volume helper fixes the source, and
the smoke test checks that the running API's actual log file is visible.

An initial Elasticsearch setup request returned HTTP 429 while cluster startup
work was pending. Bounded retries now cover those temporary responses. WSL clock
corrections also appeared in Elasticsearch logs; persistent data was retained.

One disposable node-replacement check received `:0` instead of an assigned port
from Docker Desktop. The test now retains its originally allocated Elasticsearch
port when replacing that container, keeping the recovery query deterministic.

After a Docker Desktop/WSL restart between sessions, an existing PostgreSQL file
bind pointed at a stale Desktop mount. Recreating the affected containers restored
their configuration while keeping the original data volumes. A shared WSL log
mount also proved unreliable across that restart. The final implementation uses
an external Docker bind volume created directly through the Windows CLI; its
device points at the daemon's real log directory and needs no shared host mount.

### Verification

- All 50 existing pytest cases passed. Image builds, Ruff lint/format, Bash
  syntax, Compose validation, documentation links, and whitespace checks passed.
- The application Compose smoke suite passed initialization failure, readiness,
  dependency outages, API replacement at a different IP, and order persistence.
- Real Elasticsearch pipeline simulations verified app, NGINX, PostgreSQL,
  console text, native errors, malformed JSON retention, and duration conversion.
- The logging suite verified searchable mappings, lifecycle installation,
  idempotent setup, and the Kibana data view through their HTTP APIs.
- End-to-end searches found order business events, application stack traces,
  payment events across three services, and slow SQL across proxy/API/database.
- Native PostgreSQL division-by-zero errors retained SQLSTATE and request ID;
  native NGINX errors matched access events by connection without inventing IDs.
- Agent replacement retained acknowledged offsets without replay in the check.
  Application requests succeeded during an Elasticsearch outage; their logs
  arrived after recovery. Existing indexed records survived node replacement.
- Unrelated-project records were excluded, and normal generated records had no
  unexpected parsing failures. Disposable projects and their volumes were removed.
- The original specification and all 14 README sections remain intact.

### Runtime left after verification

The main `shopsphere` stack has seven healthy services; `db-init` and
`elastic-setup` both exited successfully. The application is available at
`http://127.0.0.1:8088`, Elasticsearch at `http://127.0.0.1:9200`, and Kibana
Discover at `http://127.0.0.1:5601/app/discover`. Fresh payment, slow-query, and
error requests were searchable with the expected service identities and no
parsing failures. Previously indexed verification records also survived.

The root verification order `ab88ce70-07a0-4092-ba7a-65d20daf60b2` and both earlier
Phase 3 verification orders remain available in their separate databases. The
final logging smoke suite passed using the external Docker log volume, and the
application smoke suite passed with a deliberately unavailable log-source volume
name, confirming its independent startup. Both disposable projects were removed.
The user's untracked `cmd.sh` was left untouched.

### Production equivalent and limits

Agents commonly run on workload hosts or as Kubernetes DaemonSets, with centrally
managed policies. Production needs TLS, authentication, narrow ingest privileges,
protected log access, adequate queues/storage, replicas, backups, and ingestion
monitoring. This lab exposes Elastic HTTP only on loopback and disables security.
The Agent can read other Docker logs/metadata through its mount while its publishing
filter excludes them; this is not a tenant security boundary.

The registry prevents routine replay but cannot promise exactly-once delivery.
Unacknowledged batches can duplicate, and unread files can disappear during long
outages. Elasticsearch deletes indices seven days after rollover; PostgreSQL's
rotated source files need separate archival/cleanup for extended use.

### Learner checkpoint and next phase

Follow [Phase 6](phase-06-centralized-logging.md). Find one payment and one slow
query across services in Discover. Explain the differences between source files,
the Agent registry, indexed documents, and a data view. Phase 7 will add
Prometheus metrics, exporters, and Grafana. Tracing remains Phase 8.

## 2026-10-06–07 — Phase 7: Metrics and dashboards

Commit subject: `feat: implement metrics monitoring stack`.

### What changed and why

The API and payment service now expose Prometheus metrics. Per-application
registries count HTTP requests and server errors and measure HTTP/SQL execution
with histograms. Route templates and bounded categories keep IDs and SQL text
out of metric labels. Application images are version 0.7.0.

Prometheus scrapes six targets every five seconds: both applications, NGINX,
PostgreSQL, Linux kernel/storage metrics, and itself. NGINX's status listener and
all exporter ports stay internal. A rerunnable database job creates a separate
`pg_monitor` login without permission to read application tables. Prometheus and
Grafana use persistent volumes, and three dashboards plus the data source are
provisioned from versioned files. Application startup remains independent of
monitoring availability.

### DevOps concepts introduced

Pull-based collection, exposition formats, time-series labels and cardinality,
counters versus rates, gauges, cumulative histogram buckets and estimated
percentiles, SQL timer boundaries, exporter health versus source health, PromQL,
dashboard provisioning, scrape gaps, counter resets, and time-series retention.
The lesson distinguishes transaction/row statistics from SQL execution counts
and explains why a five-second database wait must fit inside HTTP latency.

### Problems found during implementation

Whole-host-root mounts proved unreliable on Docker Desktop/WSL. Recursive root
views caused mount propagation and mount-count problems; a direct root bind also
interfered with WSL integration. Those approaches and their helper were removed.
The final collector has no host-root, proc/sys bind, or host PID namespace. Native
collectors read global Linux kernel CPU, memory, and block I/O counters through
the container's normal proc/sys views. On Desktop those counters describe the
Linux VM, not Windows or individual container limits.

WSL Windows-share mount metadata also broke the native filesystem parser. A
small `stat` loop now measures the filesystem containing Docker's log directory
through the existing non-recursive, read-only log volume. It atomically publishes
capacity and available bytes through node exporter's textfile collector. Success,
parse-error, and sample-age signals reveal failed or stale measurements. It does
not enumerate all host filesystems or measure the size of the log files.

Docker Desktop required recovery after the mount experiments and WSL restarts.
The Ubuntu native daemon was temporarily the default; its identity differed from
the Desktop daemon holding the lab. Validation resumed only after restoring the
original Desktop connection. Main database and Elastic data volumes were retained.
The logging smoke test now starts only its own required services, avoiding
unrelated metrics services and fixed-port conflicts in its disposable project.

### Verification

- All 55 pytest cases passed, including bounded labels, per-app isolation,
  exactly-once server-error counting, real slow SQL, and failed-query histograms.
- The application Compose smoke suite passed initialization failure, dependency
  outages, DNS recovery after API replacement, and order persistence with 0.7.0
  images. Monitoring is not required for application-only startup.
- The metrics smoke suite passed all six scrape targets, collector health,
  monitoring-role permissions, idempotent role setup, HTTP/SQL observations,
  every dashboard query, and Grafana data-source provisioning.
- Collector removal/replacement left NGINX and the Docker API usable. Exporter
  and database outages were visible; application requests continued during
  Prometheus/Grafana downtime. Historical samples and dashboards survived their
  container replacement, and new samples arrived after recovery.
- The centralized logging regression passed parser/mapping checks, cross-service
  correlation, project filtering, Agent offset persistence without replay, and
  delivery after Elasticsearch downtime. Both disposable telemetry projects
  and their own volumes were removed.
- Collector memory matched Docker's 12,393,308,160-byte VM total rather than its
  128 MiB container limit. Storage size matched `stat` on the Docker log view.
- Ruff lint/format, shell syntax, Compose configuration, pinned `promtool`
  validation, local documentation links, and whitespace checks passed. All 14
  README sections and the original specification checksum remain intact.

### Runtime left after verification

The main `shopsphere` project has twelve running services: nine report healthy
through Docker health checks, and three exporters are verified through Prometheus.
All three initialization jobs exited 0. Prometheus reports six healthy targets;
Grafana's data source reports OK and all three dashboards are provisioned.
The UIs are available on loopback ports 9090 and 3000, with the documented initial
Grafana login `admin` / `shopsphere_local`.

Fresh `phase7-live-payment`, `phase7-live-slow`, and `phase7-live-error` requests
produced the expected metrics and searchable cross-service logs without parsing
failures. The main order `ab88ce70-07a0-4092-ba7a-65d20daf60b2`, both earlier Phase 3
orders, and nine historical Phase 6 verification log records remain available.
The separate Phase 3 database is healthy. The user's untracked `cmd.sh` and local
`.env` were left untouched and excluded from the commit.

### Production equivalent and limits

Production needs authenticated/TLS endpoints, secret management, discovery,
resource budgets, high availability or remote storage, alert rules, and backups.
The application currently runs one worker per container; multiple workers need a
supported metrics aggregation design. Histogram percentiles are estimates, and
scrape gaps cannot recover intermediate gauge values. Prometheus retains seven
days or 512 MB of blocks; its active head, WAL, and compaction need extra space.

### Learner checkpoint and next phase

Follow [Phase 7](phase-07-metrics.md). Generate slow queries and server errors,
inspect the dashboards, and find the corresponding requests in Kibana. Explain
why `up` and `pg_up` differ, what resets when an application restarts, and which
machine and filesystem the infrastructure dashboard describes. Phase 8 will add
OpenTelemetry instrumentation, Collector, and Jaeger; tracing is still planned.
