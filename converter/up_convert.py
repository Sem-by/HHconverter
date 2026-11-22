from __future__ import annotations

import re

from converter.coin_format import format_h2n_utc_datetime
from converter.hand_ids import up_display_hand_id, up_display_tournament_id
from converter.normalize import restore_poker_hand_header_colon
from converter.time_et import (
    parse_header_timestamp,
    strip_existing_et_brackets,
    strip_trailing_timestamp_token,
)

_POKER_HAND_HEADER_RE = re.compile(r"Poker\s+Hand\s+#([^\s:]+)\s*:\s*(.+)")
_SHOWDOWN_RE = re.compile(r"\*\*\* SHOWDOWN \*\*\*")
_DEALT_CARDS_EOL_RE = re.compile(
    r"\[(?:10|[2-9TJQKA])[cdhs](?:\s+(?:10|[2-9TJQKA])[cdhs])*\]\s*$",
    re.I,
)
_UNCALLED_TYPO_RE = re.compile(
    r"^uncalled bet \(([^)]+)\) retured to ",
    re.IGNORECASE,
)
_TOURNAMENT_ID_RE = re.compile(r"(Tournament #)(\d+)")
_TABLE_LINE_RE = re.compile(
    r"^Table '([^']*)' (\d+)-max Seat #(\d+) is the button\s*$"
)
_MULTI_COMMA_SPACE_RE = re.compile(r",\s{2,}")
_UP_LEVEL_RE = re.compile(r"Level\s*\d+\s*\(")


class UPpokerConverter:
    """Convert UPpoker text to Hand2Note UPpoker-module layout (Coin-like, not GG-like)."""

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        return [self.convert_hand(block) for block in blocks]

    def convert_hand(self, block: str) -> str:
        lines = block.splitlines()
        if not lines:
            return block

        first = restore_poker_hand_header_colon(lines[0].strip())
        m = _POKER_HAND_HEADER_RE.match(first)
        if not m:
            return block

        hid = up_display_hand_id(m.group(1))
        tail = _normalize_up_header_tail(m.group(2).strip())
        header = f"PokerStars Hand #{hid}: {tail}"
        tid = _extract_tournament_id(tail)

        body: list[str] = []
        append = body.append
        table_seen = False
        for line in lines[1:]:
            if not table_seen and line.lstrip().startswith("Table '"):
                table_m = _TABLE_LINE_RE.match(line.strip())
                if table_m:
                    table_seen = True
                    max_seats = table_m.group(2)
                    button = table_m.group(3)
                    append(f"Table '{tid} 0' {max_seats}-max Seat #{button} is the button")
                    continue

            if line.startswith("Dealt to "):
                if not _DEALT_CARDS_EOL_RE.search(line):
                    continue
                append(line)
                continue

            if line and line[0] in ("u", "U") and line.lower().startswith("uncalled bet "):
                line = _normalize_uncalled_line(line)
            elif "*** SHOWDOWN ***" in line:
                line = _normalize_showdown_line(line)
            elif " won (" in line:
                line = _normalize_won_to_collected(line)
            append(line)

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
    header_tail = _MULTI_COMMA_SPACE_RE.sub(", ", header_tail)
    header_tail = _UP_LEVEL_RE.sub("Level (", header_tail, count=1)

    cleaned = strip_existing_et_brackets(header_tail.rstrip())
    utc_dt = parse_header_timestamp(cleaned)
    if utc_dt is None:
        return header_tail

    prefix = strip_trailing_timestamp_token(cleaned).rstrip()
    return f"{prefix} {format_h2n_utc_datetime(utc_dt)}"


def _strip_empty_dealt_line(line: str) -> str | None:
    if line.startswith("Dealt to ") and not _DEALT_CARDS_EOL_RE.search(line):
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
    if " won (" not in line or not line.lstrip().startswith("Seat "):
        return line
    if "showed" in line and " with " in line:
        return line
    return line.replace(" won (", " collected (")


# Backward-compatible alias
UPokerConverter = UPpokerConverter
