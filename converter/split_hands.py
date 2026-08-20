from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from converter.hand_ids import detect_poker_hand_room

_HAND_START_PREFIXES = (
    "PokerPlanets Hand #",
    "CoinPoker Hand #",
    "Poker Hand #",
    "PokerStars Hand #",
    "***** 888poker Hand History",
)
_GAME_NO_LINE_RE = re.compile(r"^#Game No\s*:", re.I)


def iter_hand_blocks(path: Path) -> Iterable[str]:
    # utf-8-sig strips a leading BOM so the first hand is recognized
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    buf: list[str] = []

    def flush() -> str | None:
        if not buf:
            return None
        block = "\n".join(buf).strip()
        buf.clear()
        return block or None

    for raw in lines:
        line = raw.rstrip("\r")
        if _starts_new_hand(line) and buf:
            if _is_888_preamble(buf):
                buf.append(line)
                continue
            done = flush()
            if done:
                yield done
            buf.append(line)
            continue
        if _starts_new_hand(line):
            buf.append(line)
            continue
        buf.append(line)

    last = flush()
    if last:
        yield last


def _starts_new_hand(line: str) -> bool:
    s = _strip_bom(line.lstrip())
    return any(s.startswith(prefix) for prefix in _HAND_START_PREFIXES)


def _strip_bom(text: str) -> str:
    return text.removeprefix("\ufeff")


def _is_888_preamble(buf: list[str]) -> bool:
    nonempty = [ln.strip() for ln in buf if ln.strip()]
    return bool(nonempty) and all(_GAME_NO_LINE_RE.match(ln) for ln in nonempty)


_POKER_HAND_HEADER_RE = re.compile(r"Poker Hand #([^\s:]+)")


def detect_room_from_first_line(first_line: str) -> str | None:
    s = _strip_bom(first_line.lstrip())
    if s.startswith("PokerPlanets Hand #"):
        return "poker_planets"
    if s.startswith("CoinPoker Hand #"):
        return "coinpoker"
    if s.startswith("***** 888poker Hand History"):
        return "888poker"
    if _GAME_NO_LINE_RE.match(s):
        return "888poker"
    m = _POKER_HAND_HEADER_RE.match(s)
    if m:
        return detect_poker_hand_room(m.group(1))
    return None
