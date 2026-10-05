# OpenTelemetry Collector

Phase 8 will add `collector-config.yml`. Application SDKs create spans; the
Collector receives them, applies configured processing, and exports them to
Jaeger. This separates application instrumentation from telemetry delivery.

We will explain receivers, processors, exporters, and how a pipeline connects
them when adding the configuration. Production deployments also consider
batching, delivery failures, capacity, and sampling. No Collector runs yet.
