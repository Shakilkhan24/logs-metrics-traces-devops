# PostgreSQL

Phase 3 uses PostgreSQL 18.6 for products, orders, and order items.

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

The root application Compose stack arrives in Phase 5. Log collection and database
metrics arrive in Phases 6 and 7.
