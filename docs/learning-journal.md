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
