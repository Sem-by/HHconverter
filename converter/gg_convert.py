from __future__ import annotations

import re
from collections.abc import Callable

from converter.hand_ids import gg_display_hand_id
from converter.time_et import append_utc_bracket_et, normalize_level_piece

_POKER_HAND_HEADER_RE = re.compile(r"Poker\s+Hand\s+#([^\s:]+)\s*:\s*(.+)")
_EMPTY_DEALT_RE = re.compile(r"^Dealt to \S+\s*$")
_UNCALLED_TYPO_RE = re.compile(
    r"^uncalled bet \(([^)]+)\) retured to ",
    re.IGNORECASE,
)
_TOURNAMENT_ID_RE = re.compile(r"(Tournament #)(\d+)")
_TABLE_LINE_RE = re.compile(
    r"^Table '([^']*)' (\d+)-max Seat #(\d+) is the button\s*$"
)

# Hand2Note room table prefixes (clkClubGG.exe room map):
# ClubGG -> CGG_, GG Network -> GG_
_GG_TABLE_PREFIX = "GG_"

_HAND_ID_FN = {
    "ggpoker_ok": gg_display_hand_id,
}


class PokerHandConverter:
    """Convert GGPoker / UPoker ``Poker Hand #`` blocks to PokerStars format."""

    def __init__(self, room: str) -> None:
        if room not in _HAND_ID_FN:
            raise ValueError(f"Unsupported poker-hand room: {room}")
        self._room = room
        self._hand_id_fn: Callable[[str], str] = _HAND_ID_FN[room]

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        return [self.convert_hand(block) for block in blocks]

    def convert_hand(self, block: str) -> str:
        lines = block.splitlines()
        if not lines:
            return block

        first = lines[0].strip()
        m = _POKER_HAND_HEADER_RE.match(first)
        if not m:
            return block

        hid = self._hand_id_fn(m.group(1))
        tail = normalize_level_piece(m.group(2).strip())

        err, tail = append_utc_bracket_et(tail)
        if err:
            pass

        header = f"PokerStars Hand #{hid}: {tail}"
        body: list[str] = []
        for line in lines[1:]:
            table_m = _TABLE_LINE_RE.match(line.strip())
            if table_m and not body:
                tid = _extract_tournament_id(tail)
                table_id = table_m.group(1)
                max_seats = table_m.group(2)
                button = table_m.group(3)
                line = (
                    f"Table '{_GG_TABLE_PREFIX}{tid} {table_id}' "
                    f"{max_seats}-max Seat #{button} is the button"
                )

            line = _strip_empty_dealt_line(line)
            if line is None:
                continue
            line = _normalize_uncalled_line(line)
            line = _normalize_won_to_collected(line)
            body.append(line)
        return "\n".join([header, *body])


class GGPokerConverter(PokerHandConverter):
    def __init__(self) -> None:
        super().__init__("ggpoker_ok")


def _extract_tournament_id(header_tail: str) -> str:
    m = _TOURNAMENT_ID_RE.search(header_tail)
    if not m:
        return "0"
    return m.group(2)


def _strip_empty_dealt_line(line: str) -> str | None:
    if _EMPTY_DEALT_RE.match(line.rstrip()):
        return None
    return line


def _normalize_uncalled_line(line: str) -> str:
    m = _UNCALLED_TYPO_RE.match(line)
    if m:
        return f"Uncalled bet ({m.group(1)}) returned to {line[m.end():]}"
    if line.lower().startswith("uncalled bet "):
        return "U" + line[1:]
    return line


def _normalize_won_to_collected(line: str) -> str:
    """Hand2Note: ``won`` for showed hands with a rank; ``collected`` otherwise."""
    if " won (" not in line:
        return line
    if "showed" in line and " with " in line:
        return line
    return re.sub(r"\bwon \(", "collected (", line)
