# Oleg Todo Bot

[![Telegram](https://img.shields.io/badge/Telegram-@oleg__tododo__bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/oleg_tododo_bot)

Oleg Todo Bot is a private Telegram todo bot for fast personal notes, nested chapters, inbox capture, bulk commands, and timed reminders.

This project was fully written with OpenAI Codex.

## Features

- Inbox-first capture for quick notes.
- Chapters and subchapters for structured todo lists.
- Bulk item actions with ranges.
- Done, delete, move up/down, and chapter removal commands.
- Timed reminders parsed from natural note text, using Kyiv timezone.
- Telegram message rendering with HTML formatting and stable per-chat render locking.
- Reminder delivery worker with inline delete buttons.

## Tech Stack

- Python 3.9
- aiogram 3
- SQLite
- aiosqlite
- python-dotenv
- Docker Compose
- GitHub Actions CI/CD

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



