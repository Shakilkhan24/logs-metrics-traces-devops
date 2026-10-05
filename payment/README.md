# Mock payment service

This directory contains a separate FastAPI process that simulates a payment
provider. The API calls its `GET /payment` route so we can study HTTP dependency
failures and correlate logs across processes without using a real payment system.

The service was introduced in Phase 2, will be containerized
in Phase 5, and instrumented for tracing in Phase 8. In production, this boundary could
connect to an internal payment service or an external provider.

Run `python -m uvicorn payment.main:app --port 8001 --no-access-log` from the
repository root in the activated virtual environment. `GET /` reports process
status; `GET /payment` returns a new simulated approval ID. Neither route charges
money or changes an order. A real payment operation would not use GET.

The service reuses the lab's JSON logger and response schema from `app/`, so run
it from the repository root. This is shared code in one repository, while the
HTTP requests still cross a real process boundary when the servers run separately.
