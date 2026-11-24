from __future__ import annotations

import re
from functools import lru_cache

_GAME_ENDED_RE = re.compile(r"(?m)^Game ended:.*(?:\n|$)")
_BOARD_RE = re.compile(r"Board \[(.*?)\]", re.DOTALL)
_WS_RE = re.compile(r"\s+")
_HEADER_OR_TABLE_PREFIXES = (
    "PokerStars Hand #",
    "Poker Hand #",
    "CoinPoker Hand #",
    "PokerPlanets Hand #",
    "1WinPoker Hand #",
    "Table '",
    "Tournament '",
)


def _board_norm(m: re.Match[str]) -> str:
    inner = m.group(1)
    if "[ " in inner:
        inner = inner.replace("[ ", "[")
    if " ]" in inner:
        inner = inner.replace(" ]", "]")
    inner = _WS_RE.sub(" ", inner.strip())
    return "Board [" + inner + "]"


def global_postprocess(text: str, *, trim_total_pot: bool = True) -> str:
    if "Game ended:" in text:
        text = _GAME_ENDED_RE.sub("", text)

    if "Board [" in text:
        text = _BOARD_RE.sub(_board_norm, text)

    lines_out: list[str] = []
    append = lines_out.append

    for line in text.splitlines():
        if trim_total_pot:
            stripped = line.lstrip()
            if stripped.startswith("Total pot"):
                pot_only = stripped.split("|", 1)[0].rstrip()
                if " $" in pot_only:
                    rake = "$0"
                elif " €" in pot_only:
                    rake = "€0"
                else:
                    rake = "0"
                line = f"{pot_only} | Rake {rake}"

        append(line.rstrip())

    return "\n".join(lines_out).rstrip() + "\n"


_MISSING_POKER_HAND_COLON_RE = re.compile(
    r"^(Poker\s+Hand\s+#[^\s:]+)\s+(?!:)",
    re.I,
)


def restore_poker_hand_header_colon(header: str) -> str:
    """Insert ``:`` after ``Poker Hand #id`` when a room export omitted it."""
    return _MISSING_POKER_HAND_COLON_RE.sub(r"\1: ", header, count=1)


def gg_postprocess(text: str) -> str:
    """GG export: keep Jackpot/Bingo/etc. on Total pot lines; still normalize boards."""
    return global_postprocess(text, trim_total_pot=False)


def up_postprocess(text: str) -> str:
    """UP export: keep Jackpot on Total pot; normalize boards like GG."""
    return global_postprocess(text, trim_total_pot=False)


@lru_cache(maxsize=256)
def _token_pattern(seat_token: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + re.escape(seat_token) + r"(?!\w)")


def replace_seat_token(text: str, seat_token: str, replacement: str) -> str:
    if not seat_token or seat_token == replacement or seat_token not in text:
        return text
    pattern = _token_pattern(seat_token)
    repl = lambda _m: replacement

    # Preserve hand header / Table metadata lines so a Hero token matching a word
    # in the tournament title or table name (e.g. "Hero Bounty") is never mangled.
    lines = text.splitlines(keepends=True)
    if len(lines) >= 2 and lines[0].lstrip().startswith(_HEADER_OR_TABLE_PREFIXES):
        skip = 1
        if lines[1].lstrip().startswith(_HEADER_OR_TABLE_PREFIXES):
            skip = 2
        head = "".join(lines[:skip])
        body = "".join(lines[skip:])
        if seat_token not in body:
            return text
        return head + pattern.sub(repl, body)
    return pattern.sub(repl, text)
