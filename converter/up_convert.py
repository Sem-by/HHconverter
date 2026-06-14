from __future__ import annotations

import re

from converter.coin_format import format_h2n_utc_datetime
from converter.hand_ids import up_display_hand_id, up_display_tournament_id
from converter.time_et import (
    parse_header_timestamp,
    strip_existing_et_brackets,
    strip_trailing_timestamp_token,
)

_SHOWDOWN_RE = re.compile(r"\*\*\* SHOWDOWN \*\*\*")
_EMPTY_DEALT_RE = re.compile(r"^Dealt to \S+\s*$")
_UNCALLED_TYPO_RE = re.compile(
    r"^uncalled bet \(([^)]+)\) retured to ",
    re.IGNORECASE,
)
_TOURNAMENT_ID_RE = re.compile(r"(Tournament #)(\d+)")
_TABLE_LINE_RE = re.compile(
    r"^Table '([^']*)' (\d+)-max Seat #(\d+) is the button\s*$"
)


class UPokerConverter:
    """Convert UPoker text to Hand2Note Upoker-module layout (Coin-like, not GG-like)."""

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        return [self.convert_hand(block) for block in blocks]

    def convert_hand(self, block: str) -> str:
        lines = block.splitlines()
        if not lines:
            return block

        first = lines[0].strip()
        m = re.match(r"Poker\s+Hand\s+#([^\s:]+)\s*:\s*(.+)", first)
        if not m:
            return block

        hid = up_display_hand_id(m.group(1))
        tail = _normalize_up_header_tail(m.group(2).strip())
        header = f"PokerStars Hand #{hid}: {tail}"

        body: list[str] = []
        for line in lines[1:]:
            table_m = _TABLE_LINE_RE.match(line.strip())
            if table_m and not body:
                tid = _extract_tournament_id(tail)
                max_seats = table_m.group(2)
                button = table_m.group(3)
                line = f"Table '{tid} 0' {max_seats}-max Seat #{button} is the button"

            line = _strip_empty_dealt_line(line)
            if line is None:
                continue
            line = _normalize_uncalled_line(line)
            line = _normalize_showdown_line(line)
            line = _normalize_won_to_collected(line)
            body.append(line)

        return "\n".join([header, *body])


def _extract_tournament_id(header_tail: str) -> str:
    m = _TOURNAMENT_ID_RE.search(header_tail)
    if not m:
        return "0"
    return m.group(2)


def _normalize_up_header_tail(header_tail: str) -> str:
    def tid_repl(match: re.Match[str]) -> str:
        return match.group(1) + up_display_tournament_id(match.group(2))

    header_tail = _TOURNAMENT_ID_RE.sub(tid_repl, header_tail, count=1)
    header_tail = re.sub(r",\s{2,}", ", ", header_tail)
    header_tail = re.sub(r"Level\s*\d+\s*\(", "Level (", header_tail, count=1)

    cleaned = strip_existing_et_brackets(header_tail.rstrip())
    utc_dt = parse_header_timestamp(cleaned)
    if utc_dt is None:
        return header_tail

    prefix = strip_trailing_timestamp_token(cleaned).rstrip()
    return f"{prefix} {format_h2n_utc_datetime(utc_dt)}"


def _strip_empty_dealt_line(line: str) -> str | None:
    if _EMPTY_DEALT_RE.match(line.rstrip()):
        return None
    return line


def _normalize_showdown_line(line: str) -> str:
    return _SHOWDOWN_RE.sub("*** SHOW DOWN ***", line)


def _normalize_uncalled_line(line: str) -> str:
    m = _UNCALLED_TYPO_RE.match(line)
    if m:
        return f"Uncalled bet ({m.group(1)}) returned to {line[m.end():]}"
    if line.lower().startswith("uncalled bet "):
        return "U" + line[1:]
    return line


def _normalize_won_to_collected(line: str) -> str:
    if " won (" not in line:
        return line
    if "showed" in line and " with " in line:
        return line
    return re.sub(r"\bwon \(", "collected (", line)
