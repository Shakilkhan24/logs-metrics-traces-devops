# Troubleshooting

This guide currently covers Phase 1. Runtime checks will be added as the
application, containers, and telemetry pipelines are implemented.

## Git says this is not a repository

Run `pwd` and confirm that your shell is in this project or one of its
subdirectories. From this workspace, the following should locate its root:

```bash
git rev-parse --show-toplevel
```

Phase 1 initialized a `.git/` directory at the workspace root. It is hidden in
many file browsers. Do not create another repository inside a service directory.

## Git cannot create a commit because identity is missing

Inspect the configured identity:

```bash
git config user.name
git config user.email
```

If needed, set your own name and email for this repository using
`git config --local user.name "Your Name"` and
`git config --local user.email "your-email@example.com"`. The placeholders should
be replaced with the identity you want associated with your commits.

## A file does not appear in Git status

Check whether an ignore rule matches it:

```bash
git check-ignore -v .env
```

Local `.env` files, logs, caches, and virtual environments are intentionally
ignored. Future sanitized templates such as `.env.example` may be tracked.
Use `git ls-files` to inspect the files Git is already tracking.

## Docker Compose reports that no configuration file exists

This is expected in Phase 1: `docker-compose.yml` is introduced in Phase 5.
There is no runtime command to execute yet. Check the phase table in the
[README](../README.md#1-project-motivation) before following later-phase commands.

## Git shows unexpected line-ending changes

The project uses `.gitattributes` for LF line endings in new text files, with an
exception for the preserved original brief. Inspect the effective attributes:

```bash
git check-attr text eol -- README.md docs/implementation-spec.md
```

Use an editor that respects `.editorconfig` and inspect `git diff` before
committing broad formatting changes.

## The architecture diagram appears as text

The README uses a Mermaid code block. A Markdown viewer without Mermaid support
will show the diagram source. The component table and request-flow explanation
in [architecture.md](architecture.md) provide the same design in plain text.
