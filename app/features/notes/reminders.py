from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kiev")
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])([:.])([0-5]\d)\b")
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b")


@dataclass(frozen=True)
class ParsedReminder:
    text: str
    remind_at: datetime


def parse_reminder_text(raw_text: str, now: datetime) -> Optional[ParsedReminder]:
    now = now.astimezone(KYIV_TZ)
    date_match = _find_date(raw_text, now.year)
    time_match = _find_time(raw_text, date_match)
    if time_match is None and date_match is not None:
        time_match = TIME_RE.search(raw_text)
        date_match = None
    if time_match is None:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(3))

    if date_match is None:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
    else:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year_raw = date_match.group(3)
        year = now.year if year_raw is None else _parse_year(year_raw)
        try:
            target = now.replace(year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            return None
        if target <= now:
            try:
                target = target.replace(year=target.year + 1)
            except ValueError:
                return None

    text = _remove_match(raw_text, time_match)
    if date_match is not None:
        text = _remove_match(text, DATE_RE.search(text))
    text = " ".join(text.split())
    if not text:
        return None
    return ParsedReminder(text=text, remind_at=target)


def _parse_year(value: str) -> int:
    year = int(value)
    if year < 100:
        return 2000 + year
    return year


def _find_date(raw_text: str, current_year: int) -> Optional[re.Match[str]]:
    for match in DATE_RE.finditer(raw_text):
        day = int(match.group(1))
        month = int(match.group(2))
        year_raw = match.group(3)
        year = current_year if year_raw is None else _parse_year(year_raw)
        try:
            datetime(year, month, day)
        except ValueError:
            continue
        return match
    return None


def _find_time(raw_text: str, date_match: Optional[re.Match[str]]) -> Optional[re.Match[str]]:
    matches = list(TIME_RE.finditer(raw_text))
    if not matches:
        return None

    if date_match is None:
        return matches[0]

    for match in matches:
        if match.span() != date_match.span():
            return match
    return None


def _remove_match(text: str, match: Optional[re.Match[str]]) -> str:
    if match is None:
        return text
    return f"{text[:match.start()]} {text[match.end():]}"
