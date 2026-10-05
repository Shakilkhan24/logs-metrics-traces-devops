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

Files through Phase 3 are implemented; later-phase files are planned.
Run from the repository root using `python -m uvicorn app.main:app` after
activating the virtual environment and initializing PostgreSQL with
`python -m app.database`. Database routes use ordinary `def` functions, which
FastAPI runs in worker threads; the payment route uses async HTTP I/O.
See the [Phase 3 lesson](../docs/phase-03-postgresql.md) for commands and examples.
