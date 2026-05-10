# Oleg Tododo Bot

[![Telegram](https://img.shields.io/badge/Telegram-@oleg__tododo__bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/oleg_tododo_bot)

Oleg Tododo Bot is a private Telegram todo bot for fast personal notes, nested chapters, inbox capture, bulk commands, and timed reminders.

This project was fully written with OpenAI Codex.

## Features

- Inbox-first capture for quick notes.
- Chapters and subchapters for structured todo lists.
- Bulk item actions with ranges.
- Done, delete, move up/down, and chapter removal commands.
- Timed reminders parsed from natural note text, using Kyiv timezone.
- Telegram message rendering with HTML formatting and stable per-chat render locking.
- Reminder delivery worker with inline delete buttons.
- SQLite persistence with undo support for core note operations.

## Tech Stack

- Python 3.9
- aiogram 3
- SQLite
- aiosqlite
- python-dotenv
- zoneinfo/tzdata for timezone handling
- Docker
- Docker Compose
- GitHub Actions CI/CD
- VPS deployment over SSH

## Project Structure

```text
app/
  main.py                    # Bot startup, DB connection, polling, workers
  core/                      # Settings and environment loading
  db/                        # SQLite schema, connection, repositories
  features/notes/            # Notes feature: parser, router, service, renderer
  services/                  # Background workers
  utils/                     # Shared utilities
tests/                       # Unit tests
data/                        # Runtime SQLite storage
.github/workflows/prod.yml   # Production deploy workflow
Dockerfile                   # Bot image
docker-compose.yml           # VPS runtime setup
```

## Local Setup

Create `.env`:

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_PATH=data/bot.sqlite3
```

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m app.main
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Docker

Build and run with Docker Compose:

```bash
docker compose up -d --build
```

The SQLite database is stored under `./data` and mounted into the container at `/app/data`.

Logs are written to stdout/stderr and can be viewed with:

```bash
docker compose logs -f bot
```

## Deployment

Production deployment is handled by GitHub Actions.

The workflow is triggered by annotated version tags that start with `v`, for example `v1.2.0`. Before deploying, the workflow verifies that the tagged commit belongs to `origin/prod`.

Release flow:

```bash
git checkout prod
git merge dev --ff-only
git push origin prod

git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0
```

The GitHub Action then:

- checks that the tag is on `prod`;
- builds a Docker test image;
- runs the unit test suite inside Docker;
- connects to the VPS over SSH;
- fetches `prod`;
- rebuilds and restarts the service with Docker Compose.

Required GitHub secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_DEPLOY_PATH`

## Bot Link

[Open @oleg_tododo_bot in Telegram](https://t.me/oleg_tododo_bot)
