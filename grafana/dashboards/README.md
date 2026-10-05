# Dashboard definitions

Phase 7 will add versioned dashboard JSON for these views:

| Dashboard | Questions |
| --- | --- |
| Application | What are the request rate, latency, and error rate? |
| Database | How many connections exist, and how is query activity changing? |
| Infrastructure | What are CPU, memory, and disk usage doing? |

Each panel must use metric names and labels verified against the running
exporters. Keeping definitions in Git makes dashboard changes reviewable and
repeatable. No dashboard is implemented yet.
