# Learning journal

Each implementation milestone records what changed, why it changed, the concept
introduced, and its production equivalent. Entries are included in the milestone
commit so its documentation travels with the implementation. Use
`git log --oneline` to find the corresponding commit ID.

## 2026-10-05 — Phase 1: Repository foundations

Commit subject: `chore: initialize project structure`.

### What changed

- Initialized Git on the `main` branch in the existing workspace.
- Preserved the original README verbatim as `docs/implementation-spec.md`.
- Replaced the root README with a learning guide and a nine-phase roadmap.
- Created component directories with explanations of their responsibilities.
- Added `payment/` for the mock service required by the project scenario.
- Added architecture, troubleshooting, and learning notes.
- Added Git ignore rules, editor defaults, and cross-platform line-ending rules.

### Why it changed

The original file was an implementation brief. The working repository now needs
an entry point that accurately describes the current phase and guides future
changes. Component directories make source and configuration easy to locate,
while preserving the brief keeps the original requirements available.

### DevOps concepts introduced

Repository organization, separation of component responsibilities, the Git
working tree and staging area, meaningful commits, source versus runtime data,
and documentation maintained alongside implementation.

The trace timing example was clarified: a parent request waiting on a five-second
database operation includes that wait in its total duration. The original brief
remains unchanged.

### Production equivalent

A team keeps deployable source and configuration under version control, reviews
changes as commits, and maintains architecture notes and runbooks alongside the
services they describe. Runtime data and local credentials are managed outside
the source repository.

### Verification

- Confirmed all 12 component directory guides and four learning documents exist.
- Checked all 14 required README sections and all 10 local documentation links,
  including linked headings.
- Checked LF line endings, final newlines, and balanced code fences in the 17
  authored Markdown files.
- Verified that the preserved specification's SHA-256 matches the original:
  `b3977549d2df06fbbb51e4e5e66c6e0257c9bb8e8495463ed42096400bfc6384`.
- Checked that environment files, runtime output, and Python caches are ignored,
  while sanitized environment-example filenames remain eligible for tracking.
- Passed `git diff --cached --check` for the staged milestone files.
- No application or telemetry tests were run: this phase contains documentation
  and repository configuration only.

### Learner checkpoint

Complete the exercises in [learning-notes.md](learning-notes.md#practice-checkpoint).
The scaffold is implemented; the learner's understanding has not been assessed.

### Next phase

Phase 2 will implement the FastAPI application and structured application logging.
No application, container, database, or telemetry runtime was implemented in
Phase 1.
