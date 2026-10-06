# NGINX reverse proxy

NGINX receives client requests on host port `127.0.0.1:8088`. The Compose proxy
forwards them to `api:8000`; the earlier native proxy uses `127.0.0.1:8000`.
It records what happened at the boundary, including failures where the application
could not be reached.

| File | Purpose |
| --- | --- |
| `Dockerfile` | Pin NGINX 1.30.5 and run it as its non-root user |
| `container.conf` | Container listener, Docker DNS, stdout/stderr logs, and temporary paths |
| `includes/http.conf` | Shared request-ID policy and JSON log format |
| `includes/server.conf` | Shared health route, forwarding headers, timeouts, and error handling |
| `nginx.conf` | Native listener, upstream, local logs, and temporary paths |
| `manage.sh` | Validate, start, reload, and stop this repository's NGINX instance |
| `runtime/access.jsonl` | Generated JSON access events with request IDs and timings |
| `runtime/error.log` | Generated native text errors for proxy/connection problems |
| `runtime/nginx.pid` | Generated PID file for the lab's master process |

For Phase 5, run `docker compose up --build -d --wait` at the repository root.
Inspect logs with `docker compose logs nginx` and configuration with
`docker compose exec nginx nginx -T`. Container access events go to stdout;
native text errors go to stderr. `container.conf` uses Docker's resolver and a
shared upstream zone to follow the API's address after container replacement.
Rebuild after editing any included configuration.

For the native Phase 4 workflow, run these commands with NGINX installed in the same
Linux/WSL environment as the API:

```bash
bash nginx/manage.sh test
bash nginx/manage.sh start
curl -i http://127.0.0.1:8088/proxy-health
curl -i http://127.0.0.1:8088/products
bash nginx/manage.sh reload
bash nginx/manage.sh stop
```

The API and PostgreSQL must be running for `/products`. `/proxy-health` checks
only NGINX. Start Python using the [native guide](../docs/phase-04-nginx.md#run-the-local-proxy).
Use `foreground` instead of `start` to keep the proxy attached to your terminal.
`NGINX_BIN` can select an alternative NGINX executable.

The helper uses an absolute prefix for this directory, even when invoked from
another working directory. It keeps the PID, logs, and temporary files under
ignored `runtime/` and requires no sudo. An existing system NGINX service has
its own configuration and PID file. `start` and `reload` validate first;
`stop` sends a graceful quit to the lab's master process.

See the [Phase 4 lesson](../docs/phase-04-nginx.md) for log fields, request IDs,
failure exercises, and the request lifecycle. The
[Phase 5 lesson](../docs/phase-05-docker-compose.md) explains containers and DNS.
The [Phase 6 lesson](../docs/phase-06-centralized-logging.md) searches the proxy's
access and error events centrally. Phase 7 will add exporter measurements.
