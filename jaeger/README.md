# Jaeger

Phase 8 will use Jaeger to receive, store, and explore distributed traces sent
through the OpenTelemetry Collector. Its trace view will help identify whether
application work, SQL calls, or payment calls account for request latency.

This directory is reserved for configuration and operating notes. Storage,
retention, and availability choices will be explained when implementing the
service and revisited for production. No Jaeger deployment exists in Phase 1.
