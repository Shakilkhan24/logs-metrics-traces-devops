# Troubleshooting

This guide covers repository setup and the Phase 2 Python services. Database,
container, and telemetry pipeline checks will follow their implementation phases.

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

## Payment returns 502 or 504

Check that the mock service is running and responds at
`http://127.0.0.1:8001/`. Then inspect the API's `payment.failed` event using the
response's `X-Request-ID`. A connection failure, upstream HTTP error, or invalid
response produces 502; an HTTP client timeout produces 504.

The defaults assume both processes run in the same Linux/WSL environment.
`.env.example` is documentation, not an automatically loaded configuration file.
For another address, export `PAYMENT_BASE_URL` in the API's shell before startup.

## An order disappeared

Phase 2 stores orders in process memory. Restarting, using reload, or starting a
different API process gives a fresh store. Use one worker during this phase.
Durable, shared persistence arrives with PostgreSQL in Phase 3.

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
Use the local Python startup commands for Phase 2. Check the phase table in the
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
