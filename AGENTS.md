## Project Structure & Module Organization
- `app/` - main bot source code.
  - `main.py` - entrypoint and polling startup.
  - `core/` - configuration and environment loading.
  - `db/` - database initialization and repositories (`db/repo/`).
  - `features/` - business logic and routers; folder structure mirrors the bot menu.
  - `services/` - background workers, for example notifications.
  - `utils/`, `texts.py` - utilities and text templates.
- `data/` - SQLite storage.
- `pyproject.toml` - Python dependencies.
- `.env` - local configuration. Do not commit secrets.

