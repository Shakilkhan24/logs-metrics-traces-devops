# Grafana

Phase 7 will connect Grafana to Prometheus and add dashboards for application,
database, and infrastructure measurements. Grafana queries a data source and
turns measurements into graphs and other panels; Prometheus stores the metrics.

The [dashboards](dashboards/README.md) directory will hold exported dashboard
definitions so changes can be reviewed and reproduced through Git. Production
teams can provision data sources and dashboards from versioned configuration.
Phase 1 contains no dashboard or provisioning configuration.
