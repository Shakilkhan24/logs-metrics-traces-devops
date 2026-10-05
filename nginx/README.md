# NGINX reverse proxy

NGINX receives client requests on `127.0.0.1:8088` and forwards them to FastAPI on
`127.0.0.1:8000`. It records what happened at the boundary, including failures
where the application could not be reached.

| File | Purpose |
| --- | --- |
| `nginx.conf` | Listener, upstream, forwarding headers, timeouts, and log format |
| `manage.sh` | Validate, start, reload, and stop this repository's NGINX instance |
| `runtime/access.jsonl` | Generated JSON access events with request IDs and timings |
| `runtime/error.log` | Generated native text errors for proxy/connection problems |
| `runtime/nginx.pid` | Generated PID file for the lab's master process |

Run these commands from the repository root with NGINX installed in the same
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
only NGINX. Start the Python services using the [root guide](../README.md#9-running-the-system).
Use `foreground` instead of `start` to keep the proxy attached to your terminal.
`NGINX_BIN` can select an alternative NGINX executable.

The helper uses an absolute prefix for this directory, even when invoked from
another working directory. It keeps the PID, logs, and temporary files under
ignored `runtime/` and requires no sudo. An existing system NGINX service has
its own configuration and PID file. `start` and `reload` validate first;
`stop` sends a graceful quit to the lab's master process.

See the [Phase 4 lesson](../docs/phase-04-nginx.md) for log fields, request IDs,
failure exercises, and the request lifecycle. Phase 5 will containerize the
proxy; Phase 6 will collect its logs; Phase 7 will add exporter measurements.
