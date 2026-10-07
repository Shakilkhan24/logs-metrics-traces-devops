# Grafana

Phase 7 runs digest-pinned Grafana 13.2.3 on
[localhost:3000](http://127.0.0.1:3000), querying Prometheus over the telemetry
network. Prometheus stores metric history; Grafana visualizes it.

Initial login: **admin / shopsphere_local**. Set `GRAFANA_ADMIN_USER` and
`GRAFANA_ADMIN_PASSWORD` before first startup to choose different local credentials.
An existing account lives in `grafana_data`; changing environment variables does
not reset its password. Anonymous access and account signup are disabled.

Provisioned files:

- `provisioning/datasources/prometheus.yml`: default data source, stable UID
  `shopsphere-prometheus`, five-second scrape interval.
- `provisioning/dashboards/shopsphere.yml`: the **ShopSphere** folder and dashboard
  provider, polling files every 30 seconds for WSL compatibility.
- `dashboards/shopsphere-*.json`: application, database, and infrastructure views.

Dashboard JSON is the source of truth and UI overwrites are disabled. Change
these files for lasting edits; no manual imports, plugins, or data-source setup
are required. Grafana's local data volume retains accounts and preferences across
container replacement. Removing it discards those changes; provisioning restores
the versioned dashboards on the next startup.

The dashboards use `$__rate_interval` for counter rates, retain histogram `le`
when calculating percentiles, and keep missing measurements as gaps. Panel
descriptions explain units and boundaries. The infrastructure view is labeled
Linux kernel and Docker storage; it excludes Windows and container resource limits.

See the [dashboard guide](dashboards/README.md) and
[Phase 7 lesson](../docs/phase-07-metrics.md). The metrics smoke test checks the
provisioned data source, all three dashboard UIDs, and every panel's PromQL against
real samples, including persistence after replacing Grafana and Prometheus.
