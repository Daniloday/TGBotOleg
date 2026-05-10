## Project Structure & Module Organization
- `app/` - main bot source code.
  - `main.py` - app entrypoint: loads settings, connects SQLite, starts aiogram polling and background workers.
  - `core/` - configuration and environment loading.
  - `db/` - SQLite schema, connection wrapper, and repositories.
    - `schema.py` - database tables and indexes.
    - `database.py` - connection lifecycle and lightweight migrations.
    - `repo/notes.py` - note tree, inbox, reminders, render state, and undo persistence.
    - `repo/models.py` - read models returned from repositories.
  - `features/notes/` - user-facing note feature.
    - `parser.py` - text command parsing (`/rm`, `/push`, `/pushdel`, ranges, multiline add).
    - `service.py` - maps parsed actions to repository operations.
    - `router.py` - aiogram message/callback handlers.
    - `renderer.py` - converts note snapshots into Telegram HTML sections.
    - `rendering.py` - edits or recreates Telegram render messages.
    - `reminders.py` - reminder text/date/time parsing.
  - `services/` - background workers, currently reminder delivery.
  - `utils/` - shared utilities, currently logging setup.
- `tests/` - unit tests for parser, renderer, repository, and reminders.
- `data/` - SQLite storage, mounted in Docker. Do not commit runtime DB files.
- `pyproject.toml` - Python package metadata and dependencies.
- `Dockerfile`, `docker-compose.yml` - container build and VPS runtime setup.
- `.env` - local/runtime configuration. Do not commit secrets.

## Deployment
- Deploys are triggered by annotated version tags that start with `v`.
- Normal flow:
  1. Merge or fast-forward `prod` to the commit you want to deploy.
  2. Push `prod`.
  3. Create an annotated tag, for example:
     `git tag -a v1.2.0 -m "Release v1.2.0"`
  4. Push the tag:
     `git push origin v1.2.0`
- The GitHub Action runs on `v*` tags and verifies that the tagged commit belongs to `origin/prod` before deploying.

## Style + Rules
- Answer in Russian unless asked otherwise.
- Be blunt and practical. No fluff.
- Write code as a senior engineer: clean, minimal, best practices.
- Prefer small, reviewable diffs.
- Before editing many files: propose a plan and list touched files.
- Don't add new dependencies unless explicitly needed.
- If unsure: ask 1 targeted question or make a reasonable assumption and state it.
