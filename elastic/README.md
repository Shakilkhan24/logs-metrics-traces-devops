# Elastic Agent

Phase 6 runs standalone Elastic Agent 9.5.4, pinned by digest. It supervises a
Filebeat filestream collector and sends this project's logs to Elasticsearch.
Fleet Server and enrollment are not needed for this versioned local config.

- `elastic-agent.yml` defines stable inputs for Docker files and PostgreSQL JSON.
- `docker-source.js` unwraps Docker JSON and filters project/service labels.
- `Dockerfile` bakes those files with safe permissions, including on WSL mounts.

The filter accepts only `api`, `payment`, `db-init`, and `nginx` in the current
project. PostgreSQL uses its native files, avoiding duplicate console collection.
The collector's own logs are excluded to prevent a feedback loop.

The container runs as root to read private files. Source mounts are read-only;
PostgreSQL exposes only `18/docker/log`. The Docker directory mount exposes other
containers' logs and metadata to the collector, even though the publishing filter
excludes them. This is a local trust boundary, not tenant isolation. No Docker
socket is mounted. An external Docker volume named `shopsphere_docker_logs`
provides the source directory, normally `/var/lib/docker/containers` inside the
daemon host. Prepare it once before running the complete stack:

```bash
bash elastic/prepare-docker-logs.sh
docker compose up --build -d --wait --wait-timeout 360
```

The helper creates a local-driver bind volume and safely reuses it on later runs.
On Desktop/WSL it uses Docker Desktop's Windows CLI, checking that both clients
target the same daemon. This avoids WSL's path rewriting to a different distro's
directory. Native Linux uses its normal Docker CLI. No host shared mount, Docker
socket mount, daemon configuration change, or permission change is needed.

The volume definition persists across restarts and is external to Compose:
`down --volumes` cannot remove it. It is a view of existing Docker files, not a
copy or backup. All test projects reuse this read-only source and filter their
own project labels. The setup targets native Linux and Docker Desktop/WSL;
runtime verification used Desktop/WSL. Other Desktop platforms may need adjustment.

Export optional helper overrides explicitly: `DOCKER_LOG_ROOT` for the daemon
directory, `DOCKER_LOG_VOLUME` for the shared volume name, and `DOCKER_WINDOWS_CLI`
for a nonstandard `docker.exe` location. The Bash helper does not auto-load `.env`;
Compose reads `.env`, so use the same volume name in both. After all collectors
are removed, `docker volume rm shopsphere_docker_logs` removes only the view's
definition, not the daemon's log files.

File fingerprints identify rotated files. Docker uses 1024 bytes so identical
startup text does not hide the unique timestamp/labels later in the record.
PostgreSQL uses 64 bytes, beginning with its timestamp. Smaller files wait to grow.
Keep IDs and fingerprint settings stable to avoid replay. `elastic_agent_state`
persists acknowledged offsets across container replacement. Unacknowledged
batches can duplicate after a failure. Rotation/removal during a prolonged output
outage can lose unread events; the publishing queue is in memory in this lab.

```bash
docker compose exec elastic-agent elastic-agent status
docker compose logs --tail 50 elastic-agent
docker compose up --build -d --wait elastic-agent
```

The health check uses Agent's local liveness endpoint. Input health alone does
not prove successful indexing; the smoke test also queries actual records.
Elastic Agent 9.5.4 runs these filestream readers as Beat receivers inside its
embedded collector. This is log collection, not the Phase 8 application tracing
instrumentation or its separate OpenTelemetry Collector.
See the [Phase 6 lesson](../docs/phase-06-centralized-logging.md).
