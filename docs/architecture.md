# Architecture

Status: Phase 1 design. No application or telemetry services are running yet.
The [main README](../README.md#3-architecture-diagram) contains the target diagram.

## System boundaries

ShopSphere will have two connected parts: the services that handle shopping
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

The root Compose file will eventually connect the containers, networks, storage,
and settings. It is deliberately introduced in Phase 5 with actual services.
The files listed in the original brief are planned deliverables, not empty
executable placeholders in Phase 1.

The project uses the existing workspace root. The additional `payment/` directory
gives the required mock payment service its own source location.

## Planned request and signal flows

The request path is client → NGINX → FastAPI → database and/or payment service.
The API's business logic determines which downstream operations are needed.

Logs flow from application and infrastructure sources through Elastic Agent to
Elasticsearch. Kibana queries Elasticsearch. Concrete log mounts, formats, and
permissions will be established during the logging phase.

Metrics flow from the application and exporters to Prometheus in response to
scrapes initiated by Prometheus. Grafana queries Prometheus. Exporters measure
the system they can access; under Docker Desktop or WSL, the Linux environment
being measured must be verified before calling those measurements “host” metrics.

Spans flow from instrumented services to the Collector and then to Jaeger. The
FastAPI and payment services will propagate trace context over HTTP, while
SQLAlchemy instrumentation will create database client spans in the API process.
Those spans do not require installing an application SDK inside PostgreSQL.

NGINX is part of the request path. Forwarding trace context and producing a
proxy span are separate behaviors. Native NGINX spans require explicit proxy
instrumentation; module and image support will be checked in Phase 8 before
claiming that the proxy appears as a span.

## Timing and correlation

A trace ID connects related spans and can also be written into application logs.
Metric labels will describe bounded categories, such as route templates and
outcomes. Per-request IDs will not become metric labels, because each unique
label combination creates a separate time series.

For a request that synchronously waits on a five-second SQL operation, its parent
span covers that wait. Additional sequential work extends the total request
duration. The original brief's 500 ms application work and five-second database
work therefore imply approximately 5.5 seconds overall in that scenario.

## Decisions deferred to their implementation phases

Versions, ports, dependency pins, network names, storage paths, retention, and
resource requirements will be chosen and verified as the relevant services are
added. Phase 1 defines responsibilities without presenting untested settings as
a working deployment.
