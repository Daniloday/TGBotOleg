from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kiev")
COLON_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
DOT_PAIR_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b")
SPACE_PAIR_RE = re.compile(r"(?<!\d)(\d{1,2})\s+(\d{1,2})(?!\d)")
ESCAPED_PAIR_RE = re.compile(
    r"\.(?=(?:[01]?\d|2[0-3]):[0-5]\d\b|\d{1,2}\.\d{1,2}(?:\.\d{2,4})?\b|\d{1,2}\s+\d{1,2}(?!\d))"
)


@dataclass(frozen=True)
class ParsedReminder:
    text: str
    remind_at: datetime


@dataclass(frozen=True)
class _DateTimeCandidate:
    start: int
    end: int
    first: int
    second: int
    year_raw: Optional[str]
    separator: str
    can_time: bool
    can_date: bool


def parse_reminder_text(raw_text: str, now: datetime) -> Optional[ParsedReminder]:
    now = now.astimezone(KYIV_TZ)
    date_candidate, time_candidate = _select_datetime(raw_text, now.year)
    if time_candidate is None:
        return None

    hour = time_candidate.first
    minute = time_candidate.second

    if date_candidate is None:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
    else:
        day = date_candidate.first
        month = date_candidate.second
        year_raw = date_candidate.year_raw
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

    text = _remove_spans(raw_text, _selected_spans(date_candidate, time_candidate))
    text = _unescape_text_fragments(text)
    text = " ".join(text.split())
    if not text:
        return None
    return ParsedReminder(text=text, remind_at=target)


def _parse_year(value: str) -> int:
    year = int(value)
    if year < 100:
        return 2000 + year
    return year


def _select_datetime(raw_text: str, current_year: int) -> tuple[Optional[_DateTimeCandidate], Optional[_DateTimeCandidate]]:
    candidates = _find_candidates(raw_text, current_year)
    colon_time = next((candidate for candidate in candidates if candidate.separator == ":" and candidate.can_time), None)
    if colon_time is not None:
        date_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.start < colon_time.start and candidate.separator != ":" and candidate.can_date
            ),
            None,
        )
        return date_candidate, colon_time

    if len(candidates) == 1:
        candidate = candidates[0]
        return None, candidate if candidate.can_time else None

    if len(candidates) >= 2:
        first, second = candidates[0], candidates[1]
        if first.can_date and second.can_time:
            return first, second

    time_candidate = next((candidate for candidate in candidates if candidate.can_time), None)
    return None, time_candidate


def _find_candidates(raw_text: str, current_year: int) -> list[_DateTimeCandidate]:
    candidates = []
    for match in COLON_TIME_RE.finditer(raw_text):
        if _is_escaped(raw_text, match.start()):
            continue
        candidates.append(
            _DateTimeCandidate(
                start=match.start(),
                end=match.end(),
                first=int(match.group(1)),
                second=int(match.group(2)),
                year_raw=None,
                separator=":",
                can_time=True,
                can_date=False,
            )
        )

    for match in DOT_PAIR_RE.finditer(raw_text):
        if _is_escaped(raw_text, match.start()):
            continue
        first = int(match.group(1))
        second = int(match.group(2))
        year_raw = match.group(3)
        candidates.append(
            _DateTimeCandidate(
                start=match.start(),
                end=match.end(),
                first=first,
                second=second,
                year_raw=year_raw,
                separator=".",
                can_time=year_raw is None and _is_valid_time(first, second),
                can_date=_is_valid_date(first, second, year_raw, current_year),
            )
        )

    for match in SPACE_PAIR_RE.finditer(raw_text):
        if _is_escaped(raw_text, match.start()):
            continue
        first = int(match.group(1))
        second = int(match.group(2))
        candidates.append(
            _DateTimeCandidate(
                start=match.start(),
                end=match.end(),
                first=first,
                second=second,
                year_raw=None,
                separator=" ",
                can_time=_is_valid_time(first, second),
                can_date=_is_valid_date(first, second, None, current_year),
            )
        )

    valid_candidates = [candidate for candidate in candidates if candidate.can_time or candidate.can_date]
    return sorted(valid_candidates, key=lambda candidate: candidate.start)


def _is_valid_time(hour: int, minute: int) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _is_valid_date(day: int, month: int, year_raw: Optional[str], current_year: int) -> bool:
    year = current_year if year_raw is None else _parse_year(year_raw)
    try:
        datetime(year, month, day)
    except ValueError:
        return False
    return True


def _is_escaped(text: str, start: int) -> bool:
    return start > 0 and text[start - 1] == "."


def _selected_spans(
    date_candidate: Optional[_DateTimeCandidate],
    time_candidate: Optional[_DateTimeCandidate],
) -> list[tuple[int, int]]:
    spans = []
    for candidate in (date_candidate, time_candidate):
        if candidate is not None:
            spans.append((candidate.start, candidate.end))
    return spans


def _remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    result = text
    for start, end in sorted(spans, reverse=True):
        result = f"{result[:start]} {result[end:]}"
    return result


def _unescape_text_fragments(text: str) -> str:
    return ESCAPED_PAIR_RE.sub("", text)
