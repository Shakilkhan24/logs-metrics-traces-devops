# PostgreSQL

PostgreSQL 18.6 stores products, orders, and order items. Phase 5 runs it as the
`postgres` service in the root Compose stack, with no published host port.
`db-init` creates tables and seeds products after database health succeeds.

```bash
docker compose up --build -d --wait
docker compose exec postgres psql -U shopsphere -d shopsphere
docker compose exec -T postgres sh -c 'cat "$PGDATA"/log/*.json'
```

The root project owns `shopsphere_postgres_data`. It is separate from the earlier
native lab's `shopsphere-phase3_postgres_data`; neither workflow automatically
copies orders from the other. `down` retains the selected project's volume;
`down --volumes` deletes it. See the [Phase 5 lesson](../docs/phase-05-docker-compose.md).

The files and commands below support the earlier native Phase 3 workflow.

| File | Purpose |
| --- | --- |
| `compose.yml` | Run only PostgreSQL, bound to localhost, with persistent storage |
| `postgresql.conf` | Configure native connection, slow-statement, and error logs |
| `init.sql` | Seed the catalogue after SQLAlchemy creates the tables |

From the repository root, after installing the Python requirements:

```bash
docker compose -f postgres/compose.yml up -d --wait
.venv/bin/python -m app.database
```

The Python command creates missing tables from `app/models.py`, then executes
`init.sql`. It can be repeated without removing orders or overwriting products.
The SQL file is not mounted as a Docker entrypoint script because it depends on
the tables created by SQLAlchemy.

The local defaults are database/user `shopsphere`, password `shopsphere_local`,
and localhost port 5432. `.env.example` documents the matching application URL.
This lab role owns its database; production role separation is discussed in the
[Phase 3 lesson](../docs/phase-03-postgresql.md).

Docker stores PostgreSQL data in the `shopsphere-phase3_postgres_data` volume,
mounted at `/var/lib/postgresql`. In the version 18 image, `PGDATA` is
`/var/lib/postgresql/18/docker`. Native logs are under `$PGDATA/log/`.

Stop with `docker compose -f postgres/compose.yml stop`. `down` removes the
container and network while retaining the volume; `down --volumes` deletes data.
No runtime database files are committed to Git.

Log collection and database metrics arrive in Phases 6 and 7.

Phase 7 adds `metrics-role.sql`, run by the separate `metrics-db-init` Compose job
on both new and retained databases. It creates the `shopsphere_metrics` login
with `pg_monitor`, without granting access to application table rows. The exporter
reads server statistics through that login; its `exporter.yml` uses single-target
environment settings. The role's local password is `metrics_local`. Production
needs managed credentials and a reviewed monitoring privilege boundary.
