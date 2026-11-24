from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

_UTC_ZONE = timezone.utc

# Hour may be unpadded (PokerPlanets / PokerStars: ``2026/07/15 8:05:38``).
_DATETIME_RE = r"(\d{4}[/-]\d{2}[/-]\d{2} \d{1,2}:\d{2}:\d{2})"

# ``+03``, ``-5``, ``+05:30``, ``+0530``, ``GMT+8``, ``UTC-05:00``.
_OFFSET_RE = re.compile(
    rf"{_DATETIME_RE}\s+"
    r"(?:(?:GMT|UTC)\s*)?"
    r"([+-])(\d{1,2})(?::?(\d{2}))?(?::\d{2})?\s*$",
    re.I,
)

# Letter abbreviations after the datetime (EST, MSK, AEDT, …).
_NAMED_TZ_RE = re.compile(rf"{_DATETIME_RE}\s+([A-Za-z]{{2,6}})\s*$", re.I)
_PLAIN_DATETIME_RE = re.compile(rf"{_DATETIME_RE}\s*$")
_ET_BRACKETS_RE = re.compile(r"\s*\[[^\]]*\]\s*$")
_LEVEL_NUM_RE = re.compile(r"-\s*Level\s*(\d+)\s*(\([\s\S]*$)")

_ROMAN_NUMERALS: tuple[tuple[int, str], ...] = (
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
)


def _compute_roman(n: int) -> str:
    parts: list[str] = []
    for value, numeral in _ROMAN_NUMERALS:
        count, n = divmod(n, value)
        if count:
            parts.append(numeral * count)
    return "".join(parts)


_ROMAN_CACHE: tuple[str, ...] = tuple(_compute_roman(i) for i in range(256))

# Prefer these IANA zones when an abbreviation is shared by many regions
# (EST/CST/IST/…). Poker rooms / CoinPoker / PokerStars skew North America / EU.
_PREFERRED_ZONES: tuple[str, ...] = (
    "UTC",
    "Etc/UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Toronto",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Dublin",
    "Europe/Berlin",
    "Europe/Paris",
    "Europe/Madrid",
    "Europe/Rome",
    "Europe/Warsaw",
    "Europe/Bucharest",
    "Europe/Athens",
    "Europe/Kyiv",
    "Europe/Moscow",
    "Europe/Istanbul",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Dhaka",
    "Asia/Bangkok",
    "Asia/Jakarta",
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Taipei",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Australia/Perth",
    "Australia/Adelaide",
    "Australia/Sydney",
    "Pacific/Auckland",
)

# Explicit overrides that zoneinfo sampling alone would get wrong or miss.
_MANUAL_ABBREVS: dict[str, str] = {
    "UTC": "UTC",
    "GMT": "UTC",
    # US civil short forms (common in poker HH / UI).
    "ET": "America/New_York",
    "CT": "America/Chicago",
    "MT": "America/Denver",
    "PT": "America/Los_Angeles",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "AKST": "America/Anchorage",
    "AKDT": "America/Anchorage",
    "HST": "Pacific/Honolulu",
    "HDT": "Pacific/Honolulu",
    # Europe / CIS.
    "WET": "Europe/Lisbon",
    "WEST": "Europe/Lisbon",
    "BST": "Europe/London",
    "IST": "Asia/Kolkata",  # India (more common in online poker than Israel).
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",
    "EET": "Europe/Kyiv",
    "EEST": "Europe/Kyiv",
    "MSK": "Europe/Moscow",
    "MSD": "Europe/Moscow",
    "TRT": "Europe/Istanbul",
    # Asia-Pacific.
    "GST": "Asia/Dubai",
    "PKT": "Asia/Karachi",
    "BDST": "Asia/Dhaka",
    "ICT": "Asia/Bangkok",
    "WIB": "Asia/Jakarta",
    "WITA": "Asia/Makassar",
    "WIT": "Asia/Jayapura",
    "HKT": "Asia/Hong_Kong",
    "SGT": "Asia/Singapore",
    "MYT": "Asia/Kuala_Lumpur",
    "PHT": "Asia/Manila",
    "JST": "Asia/Tokyo",
    "KST": "Asia/Seoul",
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
    "AET": "Australia/Sydney",
    "ACST": "Australia/Adelaide",
    "ACDT": "Australia/Adelaide",
    "AWST": "Australia/Perth",
    "NZST": "Pacific/Auckland",
    "NZDT": "Pacific/Auckland",
}


def int_to_roman(n: int) -> str | None:
    """Roman numerals for tournament blind levels (1..3999)."""

    if n < 1 or n > 3999:
        return None
    if n < 256:
        return _ROMAN_CACHE[n]
    return _compute_roman(n)


def strip_existing_et_brackets(line: str) -> str:
    if "]" not in line:
        return line.rstrip()
    return _ET_BRACKETS_RE.sub("", line).rstrip()


def strip_trailing_timestamp_token(line: str) -> str:
    trimmed = strip_existing_et_brackets(line.rstrip())
    cut = _timestamp_match_span(trimmed)
    if cut is not None:
        return trimmed[: cut[0]].rstrip()
    return trimmed


def normalize_level_piece(line: str) -> str:
    """Normalize ``Level 11 (...)`` → ``Level XI (...)``."""

    def repl(m: re.Match[str]) -> str:
        lvl = int(m.group(1))
        roman = int_to_roman(lvl) or str(lvl)
        return f"- Level {roman} {m.group(2).lstrip()}"

    return _LEVEL_NUM_RE.sub(repl, line, count=1)


def format_pokerstars_timestamp(dt: datetime, *, suffix: str = "UTC") -> str:
    """PokerStars / H2N text import: ``yyyy/MM/dd H:mm:ss`` (hour without leading zero)."""
    return (
        f"{dt.year}/{dt.month:02d}/{dt.day:02d} "
        f"{dt.hour}:{dt.minute:02d}:{dt.second:02d} {suffix}"
    )


@lru_cache(maxsize=64)
def _get_zoneinfo(zone_name: str) -> ZoneInfo:
    return ZoneInfo(zone_name)


def append_utc_bracket_et(header_line: str) -> tuple[str | None, str]:
    cleaned = strip_existing_et_brackets(header_line.rstrip())
    parsed = _parse_timestamp_with_span(cleaned)
    if parsed is None:
        return ("Could not parse timestamp on header line.", header_line)

    utc_dt, start_idx = parsed
    utc_piece = format_pokerstars_timestamp(utc_dt, suffix="UTC")
    prefix = cleaned[:start_idx].rstrip()

    try:
        et = utc_dt.astimezone(_get_zoneinfo("America/New_York"))
    except ZoneInfoNotFoundError:
        return (
            "Missing IANA zone data (often Windows): install with `python -m pip install tzdata`",
            f"{prefix} {utc_piece}",
        )

    et_piece = "[" + format_pokerstars_timestamp(et, suffix="ET") + "]"
    return None, f"{prefix} {utc_piece} {et_piece}"


def _strptime_header_dt(raw: str) -> datetime | None:
    """Fast parser for ``YYYY/MM/DD H:MM:SS`` or ``YYYY-MM-DD HH:MM:SS``."""
    # Length is 18 (1-digit hour) or 19 (2-digit hour).
    n = len(raw)
    if n == 19:
        try:
            return datetime(
                int(raw[0:4]),
                int(raw[5:7]),
                int(raw[8:10]),
                int(raw[11:13]),
                int(raw[14:16]),
                int(raw[17:19]),
            )
        except ValueError:
            return None
    if n == 18:
        try:
            return datetime(
                int(raw[0:4]),
                int(raw[5:7]),
                int(raw[8:10]),
                int(raw[11:12]),
                int(raw[13:15]),
                int(raw[16:18]),
            )
        except ValueError:
            return None
    fmt = "%Y/%m/%d %H:%M:%S" if "/" in raw else "%Y-%m-%d %H:%M:%S"
    try:
        return datetime.strptime(raw, fmt)
    except ValueError:
        return None


def _offset_timezone(sign: str, hours: str, minutes: str | None) -> timezone | None:
    mins = int(minutes or 0)
    if mins >= 60:
        return None
    total = int(hours) * 60 + mins
    if total >= 24 * 60:
        return None
    if sign == "-":
        total = -total
    return timezone(timedelta(minutes=total))


def _timestamp_match_span(line: str) -> tuple[int, int] | None:
    """Start/end of ``datetime + optional tz`` at the end of a header line."""
    trimmed = line.rstrip()
    offset_m = _OFFSET_RE.search(trimmed)
    if offset_m:
        # Prefer offset over a bare ``UTC`` word that is part of ``UTC+3``.
        return offset_m.start(), offset_m.end()

    named_m = _NAMED_TZ_RE.search(trimmed)
    if named_m:
        return named_m.start(), named_m.end()

    plain_m = _PLAIN_DATETIME_RE.search(trimmed)
    if plain_m:
        return plain_m.start(), plain_m.end()
    return None


@lru_cache(maxsize=1)
def _abbrev_to_zone() -> dict[str, str]:
    """Map timezone abbreviations → IANA zone using tzdata + poker-oriented overrides."""
    samples = (
        datetime(2024, 1, 15, 12, 0, 0),
        datetime(2024, 7, 15, 12, 0, 0),
    )
    candidates: dict[str, set[str]] = {}
    preferred_rank = {name: i for i, name in enumerate(_PREFERRED_ZONES)}

    for zone_name in available_timezones():
        if zone_name.startswith("Etc/") and zone_name not in {"Etc/UTC", "Etc/GMT"}:
            # Etc/GMT± uses inverted POSIX signs; skip to avoid wrong offsets.
            continue
        try:
            zi = ZoneInfo(zone_name)
        except ZoneInfoNotFoundError:
            continue
        for sample in samples:
            try:
                abbr = sample.replace(tzinfo=zi).tzname()
            except Exception:
                continue
            if not abbr or not abbr.isalpha() or not (2 <= len(abbr) <= 6):
                continue
            key = abbr.upper()
            candidates.setdefault(key, set()).add(zone_name)

    mapping: dict[str, str] = {}
    for abbr, zones in candidates.items():
        mapping[abbr] = min(
            zones,
            key=lambda z: (preferred_rank.get(z, 10_000), z),
        )

    mapping.update(_MANUAL_ABBREVS)
    return mapping


def resolve_tz_abbrev(abbrev: str) -> str | None:
    """Return IANA zone name for a header abbreviation, or None if unknown."""
    key = abbrev.strip().upper()
    manual = _MANUAL_ABBREVS.get(key)
    if manual is not None:
        return manual
    return _abbrev_to_zone().get(key)


def _parse_timestamp_with_span(cleaned: str) -> tuple[datetime, int] | None:
    # Numeric / GMT± / UTC± offsets first (covers ``+03``, ``-05:00``, ``GMT+8``).
    offset_m = _OFFSET_RE.search(cleaned)
    if offset_m:
        naive = _strptime_header_dt(offset_m.group(1))
        tz = _offset_timezone(offset_m.group(2), offset_m.group(3), offset_m.group(4))
        if naive is None or tz is None:
            return None
        return naive.replace(tzinfo=tz).astimezone(_UTC_ZONE), offset_m.start()

    named_m = _NAMED_TZ_RE.search(cleaned)
    if named_m:
        naive = _strptime_header_dt(named_m.group(1))
        if naive is None:
            return None
        zone_name = resolve_tz_abbrev(named_m.group(2))
        if zone_name:
            if zone_name in ("UTC", "Etc/UTC"):
                return naive.replace(tzinfo=_UTC_ZONE), named_m.start()
            try:
                return naive.replace(tzinfo=_get_zoneinfo(zone_name)).astimezone(_UTC_ZONE), named_m.start()
            except ZoneInfoNotFoundError:
                return None
        # Unknown letter token: still recover the wall-clock as UTC so Convert
        # does not abort; export/Dropbox day stays usable.
        return naive.replace(tzinfo=_UTC_ZONE), named_m.start()

    iso_m = _PLAIN_DATETIME_RE.search(cleaned)
    if iso_m:
        naive = _strptime_header_dt(iso_m.group(1))
        if naive is None:
            return None
        return naive.replace(tzinfo=_UTC_ZONE), iso_m.start()

    return None


def parse_header_timestamp(line: str) -> datetime | None:
    cleaned = strip_existing_et_brackets(line).rstrip()
    parsed = _parse_timestamp_with_span(cleaned)
    return parsed[0] if parsed is not None else None
