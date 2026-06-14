from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_UTC_ZONE = timezone.utc


def int_to_roman(n: int) -> str | None:
    """Roman numerals for typical tournament blinds levels (bounded)."""

    if n < 1 or n > 49:
        return None

    tens, ones = divmod(n, 10)
    if tens == 4:
        prefix = "XL"
    elif 0 <= tens <= 3:
        prefix = "X" * tens
    else:
        prefix = ""

    digit_roman = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")
    return prefix + digit_roman[ones]


def strip_existing_et_brackets(line: str) -> str:
    return re.sub(r"\s*\[[^\]]*\]\s*$", "", line).rstrip()


def strip_trailing_timestamp_token(line: str) -> str:
    trimmed = strip_existing_et_brackets(line.rstrip())

    utc_m = re.search(r"\s+(\d{4}[/-]\d{2}[/-]\d{2} \d{2}:\d{2}:\d{2})\s+UTC\b", trimmed, flags=re.I)
    if utc_m:
        return trimmed[: utc_m.start()]

    tz_m = re.search(r"\s+(\d{4}[/-]\d{2}[/-]\d{2} \d{2}:\d{2}:\d{2})\s+\+(\d{1,2})$", trimmed)
    if tz_m:
        return trimmed[: tz_m.start()]

    plain_m = re.search(r"\s+(\d{4}[/-]\d{2}[/-]\d{2} \d{2}:\d{2}:\d{2})\s*$", trimmed)
    if plain_m:
        return trimmed[: plain_m.start()]

    return trimmed


def normalize_level_piece(line: str) -> str:
    """Normalize ``Level 11 (...)`` → ``Level XI (...)``."""

    def repl(m: re.Match[str]) -> str:
        lvl = int(m.group(1))
        roman = int_to_roman(lvl) or str(lvl)
        return f"- Level {roman} {m.group(2).lstrip()}"

    return re.sub(
        r"-\s*Level\s*(\d+)\s*(\([\s\S]*$)",
        repl,
        line,
        count=1,
    )


def format_pokerstars_timestamp(dt: datetime, *, suffix: str = "UTC") -> str:
    """PokerStars / H2N text import: ``yyyy/MM/dd H:mm:ss`` (hour without leading zero)."""
    return (
        f"{dt.year}/{dt.month:02d}/{dt.day:02d} "
        f"{dt.hour}:{dt.minute:02d}:{dt.second:02d} {suffix}"
    )


def append_utc_bracket_et(header_line: str) -> tuple[str | None, str]:
    cleaned = strip_existing_et_brackets(header_line.rstrip())
    utc_dt = parse_header_timestamp(cleaned)
    if utc_dt is None:
        return ("Could not parse timestamp on header line.", header_line)

    utc_piece = format_pokerstars_timestamp(utc_dt, suffix="UTC")
    prefix = strip_trailing_timestamp_token(cleaned).rstrip()

    try:
        et = utc_dt.astimezone(ZoneInfo("America/New_York"))

    except ZoneInfoNotFoundError:
        return (
            "Missing IANA zone data (often Windows): install with `python -m pip install tzdata`",
            f"{prefix} {utc_piece}",
        )

    et_piece = "[" + format_pokerstars_timestamp(et, suffix="ET") + "]"
    return None, f"{prefix} {utc_piece} {et_piece}"


def parse_header_timestamp(line: str) -> datetime | None:
    cleaned = strip_existing_et_brackets(line).rstrip()

    utc_m = re.search(r"(\d{4}[/-]\d{2}[/-]\d{2} \d{2}:\d{2}:\d{2})\s+UTC\b", cleaned, flags=re.I)
    if utc_m:
        fmt = "%Y/%m/%d %H:%M:%S" if "/" in utc_m.group(1) else "%Y-%m-%d %H:%M:%S"
        return datetime.strptime(utc_m.group(1), fmt).replace(tzinfo=_UTC_ZONE)

    tz_m = re.search(r"(\d{4}[/-]\d{2}[/-]\d{2} \d{2}:\d{2}:\d{2})\s+\+(\d{1,2})$", cleaned)
    if tz_m:
        fmt = "%Y/%m/%d %H:%M:%S" if "/" in tz_m.group(1) else "%Y-%m-%d %H:%M:%S"
        raw = tz_m.group(1)
        local_dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone(timedelta(hours=int(tz_m.group(2)))))
        return local_dt.astimezone(_UTC_ZONE)

    iso_m = re.search(r"(\d{4}[/-]\d{2}[/-]\d{2} \d{2}:\d{2}:\d{2})\s*$", cleaned)
    if iso_m:
        fmt = "%Y/%m/%d %H:%M:%S" if "/" in iso_m.group(1) else "%Y-%m-%d %H:%M:%S"
        raw = iso_m.group(1)
        return datetime.strptime(raw, fmt).replace(tzinfo=_UTC_ZONE)

    return None
