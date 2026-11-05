---
name: aletheia-testing
description: Implement or review Aletheia backend tests against its API and persistence requirements. Use for Aletheia backend changes and regression checks; does not authorize provider calls or replace research-quality evaluation.
---

# Aletheia backend testing

Read the repository's README and the milestone acceptance checklist in
`docs/backend-foundation.md`. Distinguish implemented contracts from future research,
refresh, and comparison features. Follow the user's current milestone scope.

Use `uv sync --locked --dev` for setup and `uv run --locked pytest` for tests.
Use `uv run --locked ruff check .` and `uv run --locked ruff format --check .`
for static checks. Never read, inspect, print, copy, or search `.env` files.

## Evidence to require

- Derive expected behavior from the agreed contract before reading implementation
  details. Map each changed behavior to an observable assertion in the checklist.
- Exercise FastAPI through HTTPX with the real SQLite storage and temporary file
  databases. Enter the app lifespan explicitly; an ASGI transport alone does not
  initialize or shut down the application.
- Keep the default suite offline: pytest-socket blocks network connections, explicit
  Settings bypass dotenv, and tests use synthetic values. Provider calls need a
  separate, explicitly authorized live workflow.
- For duplicate protection, preserve outer-trim/NFC rules for claims, context key
  ordering, and omitted-versus-supplied fields. Verify original text/timestamps survive
  reuse. Race independent storage instances so a shared Python lock cannot hide a bug.
- For transactions, inject a database failure after earlier writes, then inspect all
  affected tables. Prove rollback, successful retry, and exactly one initial event.
- Restart checks must reopen the same file with a new app/storage instance. Verify
  queued work survives, interrupted work is reconciled once, and terminal history
  remains stable.
- Check bounded input and queue capacity, including reuse when full. Put a synthetic
  secret in invalid settings/requests/errors; verify public responses and logs do not
  expose it. Do not weaken assertions just to obtain a passing run.

For major persistence or API changes, request an independent agent review when
delegation is authorized. Give the reviewer the requirements and code, asking for
missing cases and reproducible defects. Fix confirmed findings and add regression
tests. Never treat an agent's agreement as a substitute for execution.

For critical protections, selectively demonstrate test sensitivity in a temporary
copy: introduce one deliberate fault, run the relevant test, and require a failure
that detects that fault. Do not leave mutants in the working tree or run exhaustive
mutation testing on every edit.

Report executed commands, observed results, reviewer findings, and remaining gaps.
Distinguish local tests, remote CI, and manual walkthroughs. Passing foundation tests
does not establish citation accuracy, research quality, or the absence of all bugs.
