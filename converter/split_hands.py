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
)


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
            done = flush()
            if done:
                yield done
        buf.append(line)

    last = flush()
    if last:
        yield last


def _starts_new_hand(line: str) -> bool:
    s = _strip_bom(line.lstrip())
    return any(s.startswith(prefix) for prefix in _HAND_START_PREFIXES)


def _strip_bom(text: str) -> str:
    return text.removeprefix("\ufeff")


_POKER_HAND_HEADER_RE = re.compile(r"Poker Hand #([^\s:]+)")


def detect_room_from_first_line(first_line: str) -> str | None:
    s = _strip_bom(first_line.lstrip())
    if s.startswith("PokerPlanets Hand #"):
        return "poker_planets"
    if s.startswith("CoinPoker Hand #"):
        return "coinpoker"
    m = _POKER_HAND_HEADER_RE.match(s)
    if m:
        return detect_poker_hand_room(m.group(1))
    return None
