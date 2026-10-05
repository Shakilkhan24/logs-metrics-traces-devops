# Elastic Agent

Phase 6 will introduce `elastic-agent.yml`. The agent bridges local log sources
and central storage: it reads events, applies configured processing, and sends
them to Elasticsearch so logs from multiple components can be searched together.

Input paths, access permissions, and parsing will be verified against the actual
container log files during that phase. In production, agents commonly run near
the workloads whose logs they collect. No agent configuration exists yet.
