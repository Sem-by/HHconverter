from __future__ import annotations

import re

# Level I (75/150(20)) 2026/05/14 ...  ->  Level I (75/150(20)) - 2026/05/14 ...
_LEVEL_DATE_NO_DASH_RE = re.compile(r"\)\s+(\d{4}/)")
_LEVEL_DATE_WITH_DASH_RE = re.compile(r"\)\s+-\s+\d{4}/")
_TOURNAMENT_OPEN_RE = re.compile(r"^Tournament\s+\(", re.I)
_TOURNAMENT_ID_REST_RE = re.compile(r"^#(\d+),\s*(.+)$")

# Table '451075 7'(1061498) 8-max  ->  Table '451075 7' 8-max
_TABLE_INTERNAL_ID_RE = re.compile(r"^(Table\s+'[^']+')\(\d+\)(\s+)")
_PP_BUYIN_RE = re.compile(r"^(\$\S+)\s*(.+)$")


def parse_pp_tournament_header(tail: str) -> tuple[str, str, str] | None:
    """Parse ``Tournament (name)#id, remainder``; name may contain nested ``(...)``."""
    trimmed = tail.strip()
    open_m = _TOURNAMENT_OPEN_RE.match(trimmed)
    if not open_m:
        return None

    depth = 0
    name_start = open_m.end()
    idx = name_start - 1
    while idx < len(trimmed):
        ch = trimmed[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
        idx += 1
    else:
        return None

    name = trimmed[name_start:idx]
    rest = trimmed[idx + 1 :].lstrip()
    id_m = _TOURNAMENT_ID_REST_RE.match(rest)
    if not id_m:
        return None
    return name, id_m.group(1), id_m.group(2)


def parse_pp_tournament_header_with_buyin(tail: str) -> tuple[str, str, str, str] | None:
    """Like :func:`parse_pp_tournament_header`, splitting buy-in from the remainder."""
    parsed = parse_pp_tournament_header(tail)
    if parsed is None:
        return None
    name, tid, remainder = parsed
    buyin_m = _PP_BUYIN_RE.match(remainder)
    if buyin_m:
        return name, tid, buyin_m.group(1), buyin_m.group(2)
    return name, tid, "", remainder


def normalize_pp_header_timestamp(tail: str) -> str:
    """Ensure `` - `` before the UTC timestamp (required by Hand2Note parser)."""
    if _LEVEL_DATE_WITH_DASH_RE.search(tail):
        return tail
    return _LEVEL_DATE_NO_DASH_RE.sub(r") - \1", tail, count=1)


def normalize_pp_table_line(line: str) -> str:
    """Remove PokerPlanets internal table id in parentheses after the table name."""
    return _TABLE_INTERNAL_ID_RE.sub(r"\1\2", line.strip())
