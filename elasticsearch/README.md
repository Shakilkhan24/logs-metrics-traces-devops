# Elasticsearch

Phase 6 stores logs in Elasticsearch 9.5.4, pinned by digest. Its single node uses
a 512 MiB heap within a 2 GiB container limit and the `elasticsearch_data` volume.
`node.store.allow_mmap=false` avoids a host sysctl change for this local lab.

The `elastic-setup` service runs `bootstrap.py` after Elasticsearch and Kibana
are healthy. It installs only the lab's named assets and can run repeatedly:

| File | Purpose |
| --- | --- |
| `pipeline.json` | Parsing, timestamps, SQL correlation, failure tagging |
| `normalize.painless` | Normalize source fields and duration units |
| `index-template.json` | Data-stream settings and explicit search mappings |
| `lifecycle.json` | Daily/1 GiB rollover; deletion seven days after rollover |
| `bootstrap.py` | Install these assets and the Kibana data view over HTTP |

The pipeline is `shopsphere-normalize-v1`; the template and lifecycle policy are
`shopsphere-logs`. Data streams are `logs-shopsphere.container-lab` and
`logs-shopsphere.postgresql-lab`. Each backing index has one primary shard and
zero replicas: appropriate for one node, but offering no redundancy. Template
priority 501 takes precedence over Elastic's generic `logs-*` template.

`dynamic: false` preserves extra fields in `_source` without mapping them for
search. Mappings must be extended deliberately. Raw `event.original` is stored
but not indexed. The pipeline avoids source string/object conflicts by using
`service.name` and `event.action`. `event.duration` is always nanoseconds.

Parser failures retain the record with `tags: parse_error`,
`event.kind: pipeline_error`, and `error.message`. Output/mapping rejections must
also be checked in Agent's logs; ingest failure handling cannot cover all errors.

```bash
curl -s http://127.0.0.1:9200/_data_stream/logs-shopsphere.*-lab
curl -s 'http://127.0.0.1:9200/logs-shopsphere.*-lab/_ilm/explain'
docker compose run --rm --no-deps elastic-setup
```

Setup updates lab-owned assets without deleting documents. Template changes apply
to new backing indices; incompatible field changes require a migration.
Lifecycle transitions are asynchronous, and the seven-day age starts at rollover.
This policy does not delete Docker files or native PostgreSQL logs.

HTTP on loopback port 9200 has no authentication or TLS. Production needs both,
least-privilege ingest credentials, capacity planning, replicas, and snapshots.
