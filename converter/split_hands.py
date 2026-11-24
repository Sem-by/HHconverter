from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from converter.hand_ids import detect_poker_hand_room

_HAND_START_PREFIXES = (
    "PokerPlanets Hand #",
    "CoinPoker Hand #",
    "1WinPoker Hand #",
    "Poker Hand #",
    "PokerStars Hand #",
    "***** 888poker Hand History",
)
_START_CHARS = frozenset("PC1*#\ufeff \t")
_GAME_NO_LINE_RE = re.compile(r"^#Game No\s*:", re.I)
_BODY_ACTION_RE = re.compile(
    r":\s*(?:folds|checks|calls|bets|raises|posts|shows|mucks|doesn't|does not|"
    r"ALLIN|RETURN|sits out|is sitting out|has timed out|is disconnected|"
    r"is connected|has returned)\b|\ssaid,\s",
    re.I,
)


def iter_hand_blocks(path: Path) -> Iterable[str]:
    # utf-8-sig strips a leading BOM so the first hand is recognized
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    buf: list[str] = []
    append = buf.append
    starts_new = _starts_new_hand
    start_chars = _START_CHARS

    def flush() -> str | None:
        if not buf:
            return None
        block = "\n".join(buf).strip()
        buf.clear()
        return block or None

    for line in text.splitlines():
        is_start = False
        if line:
            ch = line[0]
            if ch in ("P", "C", "1", "*"):
                if line.startswith(_HAND_START_PREFIXES) and not _BODY_ACTION_RE.search(line):
                    is_start = True
            elif ch in ("#", "\ufeff", " ", "\t"):
                is_start = starts_new(line)
        if is_start:
            cleaned = _strip_leading_bom(line)
            if buf:
                if _is_888_preamble(buf) and cleaned.lstrip().startswith("***** 888poker Hand History"):
                    append(cleaned)
                    continue
                done = flush()
                if done:
                    yield done
            append(cleaned)
            continue
        append(line)

    last = flush()
    if last:
        yield last


def _starts_new_hand(line: str) -> bool:
    s = _strip_bom(line.lstrip())
    if not s:
        return False
    if s.startswith(_HAND_START_PREFIXES):
        # Guard against a player nicknamed like a hand header performing an action/chat.
        if _BODY_ACTION_RE.search(s):
            return False
        return True
    return bool(_GAME_NO_LINE_RE.match(s))


def _strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")


def _strip_leading_bom(line: str) -> str:
    if "\ufeff" in line:
        stripped = line.lstrip()
        if stripped.startswith("\ufeff"):
            return stripped.lstrip("\ufeff")
    return line


def _is_888_preamble(buf: list[str]) -> bool:
    has_game_no = False
    for ln in buf:
        stripped = ln.strip()
        if not stripped:
            continue
        if not _GAME_NO_LINE_RE.match(stripped):
            return False
        has_game_no = True
    return has_game_no


_POKER_HAND_HEADER_RE = re.compile(r"Poker Hand #([^\s:]+)")


def detect_room_from_first_line(first_line: str) -> str | None:
    s = _strip_bom(first_line.lstrip())
    if s.startswith("PokerPlanets Hand #"):
        return "poker_planets"
    if s.startswith("CoinPoker Hand #"):
        return "coinpoker"
    if s.startswith("1WinPoker Hand #"):
        return "onewin"
    if s.startswith("***** 888poker Hand History"):
        return "888poker"
    if _GAME_NO_LINE_RE.match(s):
        return "888poker"
    m = _POKER_HAND_HEADER_RE.match(s)
    if m:
        return detect_poker_hand_room(m.group(1))
    return None
