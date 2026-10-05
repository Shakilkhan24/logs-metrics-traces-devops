# Learning notes

These notes grow with the project. The [learning journal](learning-journal.md)
records completed changes; this file explains the concepts behind them.

## Phase 1: Repository foundations

### Why organize before implementing?

A multi-service project produces several kinds of files. Application source
defines behavior; service configuration controls how supporting software runs;
documentation explains how to operate the whole system.

Keeping them in predictable locations makes a change easier to find and review.
For example, an HTTP route belongs in `app/`, proxy routing belongs in `nginx/`,
and the explanation of how the request crosses both belongs in `docs/`.

Directories themselves do not run anything. They give later implementation
work a clear home. Each directory currently has a README explaining its purpose.
Git tracks files, not empty directories, so these guides also preserve the
structure when another person clones the repository.

### What does Git record?

Git records snapshots of tracked files and the history connecting those
snapshots. A commit associates a snapshot with its parent commit, author, time,
and message. It is a reviewable checkpoint in our learning journey.

Three places matter during a change:

| Place | Meaning |
| --- | --- |
| Working tree | The files you are editing on disk |
| Staging area, or index | The exact content selected for the next commit |
| Commit history | The recorded snapshots you can inspect later |

The usual sequence is edit → inspect → stage → verify → commit. Updating a file
after staging it requires staging it again to include the newest content.

```bash
git status
git diff
git diff --cached
git log --oneline
git show --stat HEAD
```

`git status` identifies staged, unstaged, and untracked changes. `git diff`
compares tracked working files with the staging area; it does not show the
contents of untracked files. `git diff --cached` compares staged content with
the current commit. `HEAD` identifies the currently checked-out commit.

Our first commit is `chore: initialize project structure`. The `chore` prefix is
a naming convention for project maintenance, not special Git behavior. Later
feature commits will identify the capability introduced by each phase.

In production teams, commits make reviews, automated checks, incident
investigation, and rollback decisions easier to tie to a specific change.

### What belongs in Git?

Commit source code, reproducible configuration, documentation, and sanitized
configuration examples. Local credentials, generated logs, virtual environments,
and database files should not be part of the source history.

`.gitignore` helps Git avoid adding matching untracked files. It does not remove
an already tracked file from history. This repository ignores `.env` files and
allows names such as `.env.example` for future templates with placeholder values.
Phase 2 adds `.env.example` to document the payment connection settings.

Production systems also distinguish deployable configuration from runtime data:
changing a service configuration is a versioned change, while storing a new
order is a database operation.

### Why add editor and line-ending rules?

`.editorconfig` requests consistent indentation and file formatting from editors
that support it. `.gitattributes` tells Git how to handle text line endings.
This matters when editing the same project through Windows and Linux tools.

New project text uses UTF-8 and LF line endings. The original implementation
brief has an explicit exception so its supplied bytes remain unchanged.

### Why document each phase?

A README is the entry point for someone opening the repository. Architecture
notes explain component relationships. Troubleshooting notes explain how to
investigate symptoms. A journal connects the change to the concept learned.

In production, these correspond to project guides, design documentation,
operational runbooks, and change records. They should describe verified behavior
and clearly distinguish planned capabilities from working ones.

### Practice checkpoint

1. Run `git show --stat HEAD` and identify the service directories.
2. Explain why `app/` and `nginx/` are separate.
3. Run `git status` and explain what a clean working tree means.
4. Explain why an application log file and its logging configuration belong in
   different places: runtime storage and version control, respectively.
5. Describe where you expect to find a future SQL model, Grafana dashboard, and
   investigation guide.

Expected locations for the last exercise are `app/models.py`,
`grafana/dashboards/`, and `docs/troubleshooting.md`. The model and dashboards
have not been implemented yet.

Completing these exercises is a learner checkpoint; creating the scaffold alone
does not establish that the concepts have been mastered.

## Phase 2: FastAPI and structured logging

The [Phase 2 lesson](phase-02-fastapi.md) covers routes, schemas, status codes,
process memory, JSON logs, concurrent request context, and HTTP dependency errors.
It includes commands and expected results for running the two services locally.

## Phase 3: PostgreSQL and transactions

The [Phase 3 lesson](phase-03-postgresql.md) explains persistent storage, SQLAlchemy
models, connection pools, sessions, transactions, slow queries, and native database
logs. It replaces the in-memory implementation while preserving the HTTP contract.

## Phase 4: NGINX and the proxy boundary

The [Phase 4 lesson](phase-04-nginx.md) explains reverse proxying, forwarded
headers, shared request IDs, access/error logs, timing units, and the difference
between an application failure and a proxy failure. It also demonstrates testing
configuration before a graceful reload.
