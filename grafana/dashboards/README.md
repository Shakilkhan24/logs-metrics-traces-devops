# Dashboard definitions

Phase 7 provisions these versioned dashboards into the **ShopSphere** folder:

| Dashboard | Stable UID | Questions |
| --- | --- | --- |
| Application | `shopsphere-application` | What are request rate, response latency, and server error rate? |
| Database | `shopsphere-database` | How many connections exist; how are transactions, rows, and SQL execution changing? |
| Infrastructure | `shopsphere-infrastructure` | What are Linux host CPU, memory, disk, and NGINX aggregate activity doing? |

All panels use the provisioned `shopsphere-prometheus` data source. Titles,
descriptions, labels, units, and PromQL are checked into JSON. The metrics smoke
test verifies every expression produces real, finite samples after generating
traffic. Percentiles are histogram estimates; a quiet route can show a gap.

The database panels distinguish transactions/rows from SQL execution counts.
The infrastructure panels describe Linux kernel CPU, memory, and block I/O (the
Linux VM on Desktop). Docker storage capacity comes from `stat` on the read-only
Docker log source directory, published through node exporter's textfile collector.
It measures that filesystem, not all mounts, Windows, or individual container
limits. NGINX `stub_status` cannot provide per-route latency or response-code
breakdowns.

Edit JSON for durable changes. Grafana polls every 30 seconds; provisioned
versions are authoritative and cannot be overwritten through the UI.
