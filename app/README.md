# Application

This directory holds the Phase 2 FastAPI e-commerce API. It handles client requests,
business behavior and outbound payment calls; database access arrives in Phase 3. In production,
this is a deployable application service.

Files and responsibilities:

| File | Responsibility | Phase |
| --- | --- | --- |
| `main.py` | Application entry point and HTTP routes | 2 |
| `logging.py` | Structured application logging | 2 |
| `schemas.py` | Pydantic request and response contracts | 2 |
| `store.py` | Temporary in-memory products and orders | 2 |
| `config.py` | Validated payment URL and timeout settings | 2 |
| `database.py` | Database engine and session lifecycle | 3 |
| `models.py` | SQLAlchemy persistence models | 3 |
| `Dockerfile` | Application image build instructions | 5 |
| `metrics.py` | Request, error, and database measurements | 7 |
| `tracing.py` | OpenTelemetry setup and instrumentation | 8 |

Phase 2 files are implemented; files listed for later phases are planned.
Run from the repository root using `python -m uvicorn app.main:app` after
activating the virtual environment. Use one worker while orders live in memory.
See the [Phase 2 lesson](../docs/phase-02-fastapi.md) for full commands and examples.
