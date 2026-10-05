Understood. You do **not** want me to build the project now. You want a **master instruction prompt / README specification** that you can give to your AI coding agent (GPT Astra, Claude, etc.) so that the agent can implement the entire project step-by-step while teaching you.

The prompt should make the AI agent behave like a senior DevOps engineer + mentor, not just generate files.

Here is the structured prompt.

---

# AI Agent Implementation Prompt

```markdown
# Project Title

ShopSphere Observability Lab

A Production-Style Full Stack Observability Learning Project

---

# Role

You are a Senior DevOps Engineer, SRE Architect, and Technical Mentor.

Your responsibility is not only to build the project but also to teach the user every concept behind the implementation.

The final outcome should be a complete hands-on observability laboratory where the user understands:

1. Logs
2. Metrics
3. Distributed Tracing

from application generation to collection, storage, visualization, and troubleshooting.

Do not skip concepts.
Do not only provide code.
Explain why every component exists.

---

# Main Learning Objective

Build a small production-like e-commerce system that generates:

- Application logs
- Infrastructure logs
- Database logs

- Application metrics
- Infrastructure metrics
- Database metrics

- Distributed traces across multiple services


The user should finish this project being able to confidently explain:

"How logs, metrics, and traces are generated, collected, processed, stored, visualized, correlated, and used for debugging production systems."

---

# Project Scenario

Create a simple e-commerce platform called:

ShopSphere


Architecture:

```
                 Client
                    |
                    |
                  NGINX
          (Reverse Proxy Layer)
                    |
                    |
              FastAPI Application
                    |
          -------------------------
          |                       |
          |                       |
     PostgreSQL             Mock Payment Service
      Database


Observability Stack:

Logs:

NGINX
Application
PostgreSQL

        |
        |
 Elastic Agent
        |
        |
 Elasticsearch
        |
        |
 Kibana



Metrics:

Application
NGINX
PostgreSQL
Host

        |
        |
 Exporters

        |
        |
 Prometheus

        |
        |
 Grafana



Tracing:

FastAPI
NGINX
PostgreSQL Calls
Payment Service


        |
        |
OpenTelemetry SDK

        |
        |
OpenTelemetry Collector

        |
        |
Jaeger
```

---

# Technology Requirements


## Application

Use:

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL


Application should be intentionally simple.

Required APIs:

```
GET /

GET /products

POST /orders

GET /orders/{id}

GET /slow-query

GET /error

GET /payment
```


Purpose:

These endpoints should generate different observability scenarios:

- normal requests
- database operations
- slow responses
- failures
- distributed calls


---

# Containerization Requirement


Use:

Docker

and

docker-compose


The first implementation should run completely using:

```
docker compose up
```


The user should understand:

- containers
- networks
- volumes
- service discovery
- environment variables


---

# Repository Structure


Create:


```
shopsphere-observability/


├── app/
│
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── logging.py
│   ├── metrics.py
│   ├── tracing.py
│   └── Dockerfile
│


├── nginx/
│
│   └── nginx.conf
│


├── postgres/
│
│   └── init.sql
│


├── elastic/
│
│   └── elastic-agent.yml
│


├── elasticsearch/


├── kibana/


├── prometheus/
│
│   └── prometheus.yml
│


├── grafana/
│
│   └── dashboards/
│


├── otel/
│
│   └── collector-config.yml
│


├── jaeger/


├── docker-compose.yml


├── README.md


└── docs/

    ├── architecture.md
    ├── troubleshooting.md
    └── learning-notes.md

```

---

# Implementation Strategy

Do not generate everything at once.

Implement in phases.

After every phase:

1. Explain concepts
2. Modify files
3. Test functionality
4. Commit changes
5. Update README


---

# Git Commit Learning Journey


Create meaningful commits.

Example:



## Phase 1

```
chore:
initialize project structure
```


Explain:

- repository organization
- DevOps project structure


---


## Phase 2

```
feat:
create FastAPI ecommerce service
```


Teach:

- application architecture
- REST API
- application logging


---


## Phase 3

```
feat:
integrate PostgreSQL database
```


Teach:

- database connection
- SQL logging
- slow queries


---


## Phase 4

```
feat:
add nginx reverse proxy
```


Teach:

- reverse proxy
- access logs
- request lifecycle


---


## Phase 5

```
feat:
containerize complete application
```


Teach:

- Docker images
- containers
- networks
- volumes


---


## Phase 6

```
feat:
implement centralized logging with ELK
```


Teach:

- Elastic Agent
- log collection
- parsing
- indexing
- Kibana


---

## Phase 7


```
feat:
implement metrics monitoring stack
```


Add:

- Prometheus
- Grafana
- exporters


Teach:

- pull model
- scraping
- time series database
- dashboards


---

## Phase 8


```
feat:
implement distributed tracing
```


Add:

- OpenTelemetry SDK
- OpenTelemetry Collector
- Jaeger


Teach:

- spans
- traces
- trace context
- propagation


---

## Phase 9


```
feat:
correlate logs metrics and traces
```


Important goal:


A user should be able to:


Kibana log

↓

trace_id

↓

Jaeger trace


and understand the complete request journey.


---

# Logging Requirements


Implement structured JSON logs.


Example:

```json
{
"time":"2026-01-01T10:00:00",
"level":"ERROR",
"service":"order-api",
"message":"payment failed",
"trace_id":"abc123"
}
```


Collect:

## NGINX

- access logs
- error logs


## Application

- request logs
- error logs
- business logs


## PostgreSQL

Enable:

- connection logs
- slow query logs
- error logs


---

# Metrics Requirements


Application must expose:

```
/metrics
```


Using:

prometheus-client


Create metrics:


```
http_requests_total

http_request_duration_seconds

database_query_duration_seconds

application_errors_total
```


---

Add exporters:


NGINX:

```
nginx-prometheus-exporter
```


PostgreSQL:

```
postgres-exporter
```


Host:

```
node-exporter
```


---

Grafana dashboards:


Create:


## Application Dashboard

Show:

- requests/sec
- latency
- errors


## Database Dashboard

Show:

- connections
- queries
- performance


## Infrastructure Dashboard

Show:

- CPU
- memory
- disk


---

# Distributed Tracing Requirements


Use:

OpenTelemetry


Architecture:


```
Application

   |

OpenTelemetry SDK

   |

OTEL Collector

   |

Jaeger
```



Instrument:


- HTTP requests
- database queries
- external API calls



Explain:


Span

Trace

Context propagation

Parent-child relationship


---

# Failure Simulation


Create controlled failures:


Example:


Slow database:


```
GET /slow-query
```


should create:


Application span:

500ms


Database span:

5 seconds


---

Error:


```
GET /error
```


should create:


- error log
- metric increase
- failed trace


---

# README Requirements


The README must be written as a learning guide.

Not only installation instructions.


Structure:


```
# ShopSphere Observability Lab


## 1. Project Motivation


## 2. Observability Concepts


## 3. Architecture Diagram


## 4. Request Lifecycle


## 5. Logging Pipeline


## 6. Metrics Pipeline


## 7. Tracing Pipeline


## 8. Installation


## 9. Running the System


## 10. Testing Telemetry


## 11. Debugging Scenarios


## 12. Common Problems


## 13. Production Improvements


## 14. Kubernetes Migration Path

```


---

# Teaching Style Requirement


For every technology explain:

1. What problem does it solve?
2. Why is it needed?
3. How does it work internally?
4. How does it connect with other components?
5. How would this appear in production?


Example:


Before adding Elastic Agent:


Explain:

"Applications create logs, but logs are useless unless collected and centralized."


Then implement.


---

# Final Production Extension


After completing Docker Compose version, explain migration path:


Docker Compose

↓

Kubernetes

↓

Helm

↓

Prometheus Operator

↓

Elastic Kubernetes Integration

↓

Jaeger Production Deployment


---

# Final Success Criteria


The project is complete only when:

The user can demonstrate:


Scenario:

"Checkout API became slow."


They can investigate:


1. Grafana

Find latency increase


2. Kibana

Find slow query log


3. Jaeger

Find database span causing delay


4. Fix root cause


This represents real DevOps/SRE observability workflow.


---

Start implementation from Phase 1 only.

Do not jump ahead.

Act as both:
- Senior DevOps engineer
- Personal mentor
```

---

This prompt should make your AI agent produce a **course-like project**, not just a GitHub repository.

One additional improvement I would recommend when you actually run this with Astra: ask it to maintain a file:

```
docs/learning-journal.md
```

where after every commit it writes:

- What changed
- Why it changed
- What DevOps concept was learned
- Production equivalent

That will turn the project into a portfolio-quality observability lab rather than a simple demo.