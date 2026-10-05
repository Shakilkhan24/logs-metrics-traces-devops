# Troubleshooting

This guide covers repository setup, the Python services, PostgreSQL, and NGINX.
The full container stack and telemetry pipeline checks follow in later phases.

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

Another process may already be listening on 8000 or 8001. Stop your previous lab
server, or choose another port with Uvicorn's `--port` option. If changing the
payment port, export a matching `PAYMENT_BASE_URL` before starting the API.
Do not terminate an unrelated process just to free the default port.

The lab's NGINX listens on 8088. Change its `listen` directive if needed, then run
`bash nginx/manage.sh test` before starting or reloading. If changing the API port,
also update the `upstream shopsphere_api` server address in `nginx/nginx.conf`.

## NGINX is missing or complains about permissions

Run `nginx -v` in the same Linux/WSL shell as Python. Install the distribution's
NGINX package if needed; `NGINX_BIN` can select an alternative executable. Start
with `bash nginx/manage.sh start` so the configuration prefix, PID file, logs,
and temporary files all belong to this lab. These commands do not need sudo.

## The proxy health check passes, but API requests return 502

`/proxy-health` checks only NGINX. Confirm that Uvicorn is listening on
`127.0.0.1:8000` and that the proxy's upstream address matches. Check
`nginx/runtime/error.log` for a connection error and use its `*connection` number
with the access log's `connection` field, timestamp, and path.

If `/payment` returns a JSON 502 and the API logs `payment.failed`, the proxy
reached the API but the payment dependency failed. An `upstream_status` of 502
alone does not distinguish these cases; inspect logs at both layers.

## An application error is absent from the NGINX error log

An API-generated 500 is normally a valid HTTP response that NGINX passes through.
Look for its status and request ID in `access.jsonl`, then find the application
exception using that ID. The native error log records proxy/connection problems,
not every HTTP error status.

## NGINX returns 504 for a slow request

Inspect the native error log for an upstream timeout. The checked-in read timeout
is 30 seconds between upstream reads, allowing the five-second SQL exercise.
Check for local configuration changes, an overloaded API, or a stalled dependency.
The timeout tests shorten it only in a temporary copy of the configuration.

## A reload failed or an old configuration is still serving

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

Check that the mock service is running and responds at
`http://127.0.0.1:8001/`. Then inspect the API's `payment.failed` event using the
response's `X-Request-ID`. A connection failure, upstream HTTP error, or invalid
response produces 502; an HTTP client timeout produces 504.

The defaults assume both processes run in the same Linux/WSL environment.
`.env.example` is documentation, not an automatically loaded configuration file.
For another address, export `PAYMENT_BASE_URL` in the API's shell before startup.

## An order disappeared

In Phase 3, restarting the API should preserve orders. Check whether `DATABASE_URL`
points to the same database and whether the named data volume still exists.
`docker compose down` retains it; `down --volumes` deletes it. Orders created under
the old Phase 2 in-memory version cannot be recovered after that process exits.

## The API reports that the database is not ready

Run `docker compose -f postgres/compose.yml ps`, then start the database with
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
the persistent volume. Use the native JSON inspection command in the
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

This is expected before Phase 5, when `docker-compose.yml` is introduced.
For Phase 3, specify `-f postgres/compose.yml` for the database and use the local
Python commands for the application. Check the phase table in the
[README](../README.md#1-project-motivation) before following later-phase commands.

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
