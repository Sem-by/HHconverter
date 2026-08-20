from __future__ import annotations

import re
from datetime import datetime

_HAND_HEADER_RE = re.compile(
    r"^\*\*\*\*\* 888poker Hand History for Game (\d+) \*\*\*\*\s*$",
    re.I,
)
_TOURNAMENT_RE = re.compile(
    r"^Tournament #(\d+)\s+(.+?)\s+-\s+Table #(\d+)\s+(\d+)\s+Max\b",
    re.I,
)
_CASH_TABLE_RE = re.compile(
    r"^Table (.+?) (\d+) Max \(Real Money\)\s*$",
    re.I,
)
_GAME_NO_RE = re.compile(r"^#Game No\s*:\s*\d+\s*$", re.I | re.M)
_RUNOUT_MARKER_RE = re.compile(r"^\*\* (First|Second) runout \*\*\s*$", re.I | re.M)
_RUNOUT_PREFIX_RE = re.compile(r"^(First|Second) runout ", re.I | re.M)
# 888 timestamps: ``*** DD MM YYYY HH:MM:SS`` (day-month-year).
_TIMESTAMP_RE = re.compile(
    r"Blinds No Limit Holdem\s+-\s+\*\*\*\s+"
    r"(\d{1,2})\s+(\d{1,2})\s+(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s*$",
    re.I,
)
_BUYIN_RE = re.compile(r"^(\$[\d.]+(?:\s*\+\s*\$[\d.]+)?)\s*(.*)$")


def is_888_hand(block: str) -> bool:
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _HAND_HEADER_RE.match(stripped):
            return True
        if stripped.startswith("***** 888poker Hand History"):
            return True
    return False


def is_888_new_format(block: str) -> bool:
    if not is_888_hand(block):
        return False
    return bool(
        _GAME_NO_RE.search(block)
        or _RUNOUT_MARKER_RE.search(block)
        or _RUNOUT_PREFIX_RE.search(block)
    )


def eight88_group_key(block: str) -> str:
    for line in block.splitlines():
        stripped = line.strip()
        tm = _TOURNAMENT_RE.match(stripped)
        if tm:
            return tm.group(1)
        cm = _CASH_TABLE_RE.match(stripped)
        if cm:
            ts = _parse_played_on(block)
            return f"cash|{ts}|{cm.group(1).strip()}|{cm.group(2)}"
    raise ValueError("888 hand missing tournament/table line")


def convert_888_hand(block: str) -> str:
    if not is_888_new_format(block):
        return block

    out: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _GAME_NO_RE.match(stripped):
            continue
        if _RUNOUT_MARKER_RE.match(stripped):
            continue
        stripped = _RUNOUT_PREFIX_RE.sub("", stripped)
        out.append(stripped)

    return "\n".join(out).rstrip() + "\n"


def eight88_tournament_meta(block: str) -> tuple[str, str, str, str]:
    """Return (tid, price, name, played_on iso date)."""
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    played = _parse_played_on(block)
    for line in lines:
        tm = _TOURNAMENT_RE.match(line)
        if not tm:
            continue
        tid = tm.group(1)
        rest = tm.group(2).strip()
        buy = _BUYIN_RE.match(rest)
        if buy:
            price = re.sub(r"\s+", "", buy.group(1))
            name = buy.group(2).strip()
        else:
            price, name = "", rest
        return tid, price, name, played
    cash_line = next((ln for ln in lines if _CASH_TABLE_RE.match(ln)), None)
    if cash_line:
        cm = _CASH_TABLE_RE.match(cash_line)
        if cm:
            return f"cash-{cm.group(2)}", "", cm.group(1).strip(), played
    raise ValueError("888 hand missing tournament/table metadata")


class Eight88Converter:
    """Convert 888poker new-format exports to legacy Pacific text for Hand2Note."""

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        return [convert_888_hand(block) for block in blocks]

    def convert_hand(self, block: str) -> str:
        return convert_888_hand(block)


def _parse_played_on(block: str) -> str:
    for line in block.splitlines():
        stripped = line.strip()
        m = _TIMESTAMP_RE.search(stripped)
        if not m:
            continue
        day, month, year, hour, minute, second = (int(x) for x in m.groups())
        try:
            return datetime(year, month, day, hour, minute, second).date().isoformat()
        except ValueError:
            continue
    raise ValueError("888 hand missing play date (expected *** DD MM YYYY HH:MM:SS)")
