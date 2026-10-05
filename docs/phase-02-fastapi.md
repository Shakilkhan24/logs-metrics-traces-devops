# Phase 2: FastAPI and structured logging

The application now accepts HTTP requests, validates order data, calls a separate
mock service, and writes JSON events. Follow the installation and two-terminal
startup commands in the [README](../README.md#8-installation) first.

## What each piece does

| Piece | Problem it solves | How it connects |
| --- | --- | --- |
| Uvicorn | A Python function cannot listen for HTTP by itself | Runs the application through the ASGI server interface |
| FastAPI | Requests need routing, validation, and responses | Matches method/path pairs to route functions |
| Pydantic schemas | Untrusted JSON needs a defined shape | Validates request bodies and shapes responses |
| MemoryStore | Routes need product and order state before the database phase | Holds catalogue and order objects in one process |
| HTTPX | The API needs to contact a separate service | Reuses an async HTTP client for payment requests |
| Logging middleware | Every request needs consistent context and timing | Wraps request processing and response delivery |
| JSON formatter | Plain strings are difficult to query consistently | Writes named fields as one JSON object per line |

Production services use these same boundaries. They would replace the temporary
store with shared persistence, define real payment semantics, and add authentication,
deployment configuration, and telemetry backends. We introduce those concerns in
later phases as the lab grows.

## How a request reaches your code

For `POST /orders`, Uvicorn receives the HTTP request and passes it to the ASGI
application. Middleware selects or generates a request ID and starts a timer.
FastAPI matches the route; Pydantic checks the body before the function runs.

The route asks the store to look up each product, calculates subtotals, and stores
the completed order. It emits an `order.created` event and returns the order.
FastAPI serializes the response; middleware adds `X-Request-ID`, measures elapsed
time, and emits `request.completed`.

HTTP status codes are part of the contract:

| Status | Meaning in this lab |
| --- | --- |
| 200 | A successful read or simulated payment call |
| 201 | An order was created; `Location` identifies its retrieval route |
| 404 | The requested product, order, or route does not exist |
| 422 | The request does not match the schema |
| 500 | The intentional error endpoint raised an exception |
| 502 | The payment dependency failed or returned an invalid response |
| 504 | The payment dependency exceeded its HTTP timeout |

See FastAPI's [error handling guide](https://fastapi.tiangolo.com/tutorial/handling-errors/)
for how `HTTPException` becomes an HTTP response.

## Why prices use integer cents

Product 1 costs 2499 cents, or USD 24.99. Two units total 4998 cents. Using integers
keeps these calculations exact without binary floating-point rounding surprises.
The server determines prices from its catalogue; the client supplies product IDs
and quantities. Supplying a price or total in the request is rejected.

An order accepts 1–20 item lines, each with an integer quantity of 1–100. Repeated
product IDs are allowed as separate lines and each contributes to the total.
All items are validated before the order is stored, so an unknown product does
not leave a partial order behind.

## Try the API

Use a third terminal while both servers are running.

Read the catalogue:

```bash
curl -i http://127.0.0.1:8000/products
```

Expect 200 and three products. Create an order:

```bash
curl -i http://127.0.0.1:8000/orders \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: phase2-order' \
  -d '{"items":[{"product_id":1,"quantity":2}]}'
```

Expect 201, a `Location: /orders/<uuid>` header, `status: "created"`, and
`total_cents: 4998`. Copy the UUID into the next request:

```bash
curl -i http://127.0.0.1:8000/orders/REPLACE_WITH_ORDER_UUID
```

Expect the same order. A malformed UUID returns 422; a valid UUID absent from the
store returns 404. Stop and restart the API, then repeat the lookup: it returns
404 because process memory was lost. PostgreSQL will address that in Phase 3.

Try invalid input:

```bash
curl -i http://127.0.0.1:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":0}]}'
```

Expect 422 and a warning-level request event. This is a rejected request, not a
server crash. The request never reaches the order-creation logic.

## Read the logs

The order example produces an `order.created` event and a `request.completed`
event in the API terminal. Both contain `request_id: "phase2-order"`. An
illustrative completion event looks like this; actual time and duration vary:

```json
{
  "time": "2026-10-05T10:00:00+00:00",
  "level": "INFO",
  "service": "order-api",
  "message": "Request completed",
  "request_id": "phase2-order",
  "trace_id": null,
  "event": "request.completed",
  "method": "POST",
  "route": "/orders",
  "status_code": 201,
  "duration_ms": 1.234
}
```

Each actual event occupies one line. Query strings, request bodies, and authorization
headers are not included in request logs. Request logs use route templates such
as `/orders/{id}`. Business events include the generated order ID where relevant.

An incoming request ID is accepted only if it has 1–64 ASCII letters, digits,
hyphens, or underscores; otherwise the service generates one. The response header
lets you correlate logs even if you did not send an ID. This ID is a diagnostic
label, not authentication or a guarantee of global uniqueness.

Python's `ContextVar` holds the ID for the current request's execution context,
so overlapping async requests do not overwrite one shared global variable. The
middleware resets that context after completion. The
[Python logging cookbook](https://docs.python.org/3/howto/logging-cookbook.html#use-of-contextvars)
explains why context-local storage is useful in concurrent applications.

## Investigate an application error

```bash
curl -i -H 'X-Request-ID: phase2-error' http://127.0.0.1:8000/error
```

Expect 500 with a generic error message and the request ID. The log includes a
`request.failed` event with the exception and a `request.completed` event with
status 500. The exception is available to the operator in logs rather than in
the HTTP error body. A later request to `/` should still succeed.

## Follow the payment call across processes

```bash
curl -i -H 'X-Request-ID: phase2-payment' http://127.0.0.1:8000/payment
```

Expect 200 with `status: "approved"`, `simulated: true`, and a generated payment
UUID. Find `phase2-payment` in both terminals. The API forwarded the ID in an HTTP
header, and the payment service used it in its own logs.

`GET /payment` is a diagnostic simulation. It moves no money, updates no order,
and stores no payment. `POST /orders` currently creates an unpaid order without
calling it. Real payment creation would require a different API contract and
durable state.

Stop the payment process with Ctrl+C and repeat the call to the API. Expect 502,
a `payment.failed` event, and a request completion event. Restart the payment
process to restore successful calls. The automated tests also check timeouts
(504), downstream 503 responses, malformed JSON, and invalid response schemas.

The API creates one reusable HTTPX client during its lifespan and closes it on
shutdown. This avoids setting up an independent connection pool for every
request. `await` allows other requests to run while HTTP I/O is pending. See
[FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/) for the
startup/shutdown pattern used here.

Export `PAYMENT_BASE_URL` and `PAYMENT_TIMEOUT_SECONDS` before starting the API to
change the connection. The timeout must be greater than zero and at most 30
seconds. HTTPX applies timeout limits to network operations, rather than promising
a single overall request deadline; see its
[timeout documentation](https://www.python-httpx.org/advanced/timeouts/).
Invalid configuration stops startup with a validation error.

## What the tests establish

```bash
.venv/bin/python -m pytest -q
```

Tests verify order totals and lookup, invalid input handling, loss of in-memory
state on restart, JSON log correlation, concurrent context isolation, HTTP
dependency failures, and cross-service request IDs. They use
[FastAPI's test client](https://fastapi.tiangolo.com/tutorial/testing/) and
[HTTPX test transports](https://www.python-httpx.org/advanced/transports/).
Application lifespan is entered explicitly so tests exercise startup and cleanup.

In-process HTTP tests cannot prove that real ports, sockets, and startup commands
work. A separate live smoke check starts both Uvicorn processes, creates and reads
an order, calls payment, and checks failure logs. The learning journal records
which checks were actually run for this milestone.

## Learner checkpoint

1. Explain the jobs of Uvicorn, FastAPI, and Pydantic in one request.
2. Show the difference between a 422 validation failure and the 500 error exercise.
3. Find one order's business and request logs using their request ID.
4. Follow a payment request across both processes using the same ID.
5. Explain why orders disappear after restarting the API and why multiple workers
   would have different order stores at this phase.
6. Explain why `trace_id: null` is honest: no tracing SDK, Collector, or Jaeger
   pipeline has been configured yet.

Next is Phase 3: replace the temporary store with SQLAlchemy and PostgreSQL, then
introduce real database slow-query behavior and SQL logging.
