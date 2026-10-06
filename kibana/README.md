# Kibana

Phase 6 runs Kibana 9.5.4 at [localhost:5601](http://127.0.0.1:5601). It queries
Elasticsearch; it does not collect logs or keep a separate copy of them. Saved
objects, including data views, live in Elasticsearch's persistent volume.

Setup creates **ShopSphere logs** (ID `shopsphere-logs`), matching
`logs-shopsphere.*-lab` with `@timestamp` as its time field. Open **Discover**,
choose that view, and set **Last 15 minutes**. Kibana's navigation can differ by
solution view; its search can locate Discover.

```bash
curl -H 'X-Request-ID: phase6-payment' http://127.0.0.1:8088/payment
```

Search using Kibana Query Language (KQL):

```text
request_id: "phase6-payment"
```

Add columns `service.name`, `event.action`, `log.level`, `request_id`,
`event.duration`, `http.response.status_code`, and `message`. Expect NGINX, API,
and payment events. Expand a document to inspect `event.original`.

Other useful searches:

```text
service.name: "postgresql" and event.action: "database.slow_statement"
log.level: "error"
http.response.status_code >= 500
event.duration >= 5000000000
tags: "parse_error"
```

Native NGINX errors have a connection number, not a request ID. Match
`nginx.connection` with access events in the same container and time window;
keep-alive means a connection can serve several requests.

No Fleet enrollment or extra integration is required. This is an unauthenticated
local lab bound to loopback. Trace links arrive in Phase 9; a request ID is not
a distributed trace ID. See the [Phase 6 lesson](../docs/phase-06-centralized-logging.md).
