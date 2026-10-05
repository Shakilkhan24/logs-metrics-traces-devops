# Elasticsearch

Phase 6 will use Elasticsearch to index and store collected logs. Elastic Agent
will send events here, and Kibana will query them for investigation.

This directory is for service configuration and operating notes; generated
indices do not belong in Git. In production, retention, storage capacity,
access control, and cluster availability determine how this component is run.
Phase 1 reserves its place without starting a service.
