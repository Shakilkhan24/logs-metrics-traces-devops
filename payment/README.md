# Mock payment service

This directory reserves a separate HTTP service that simulates a payment
provider. The API will call it so we can study latency, failure handling, and
trace context across processes without using a real payment system.

The service will be introduced as part of the application work, containerized
in Phase 5, and instrumented in Phase 8. In production, this boundary could
connect to an internal payment service or an external provider.

No service is implemented in Phase 1. This directory extends the brief's file
tree to give its required mock payment service an explicit home.
