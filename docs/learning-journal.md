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
