from __future__ import annotations

import re
from collections.abc import Callable

from converter.hand_ids import gg_display_hand_id
from converter.normalize import restore_poker_hand_header_colon
from converter.time_et import append_utc_bracket_et, normalize_level_piece, parse_header_timestamp

_POKER_HAND_HEADER_RE = re.compile(r"Poker\s+Hand\s+#([^\s:]+)\s*:\s*(.+)")
_DEALT_CARDS_EOL_RE = re.compile(
    r"\[(?:10|[2-9TJQKA])[cdhs](?:\s+(?:10|[2-9TJQKA])[cdhs])*\]\s*$",
    re.I,
)
_UNCALLED_TYPO_RE = re.compile(
    r"^uncalled bet \(([^)]+)\) retured to ",
    re.IGNORECASE,
)
_TOURNAMENT_ID_RE = re.compile(r"(Tournament #)(\d+)")
_TOURNAMENT_WORD_RE = re.compile(r"Tournament\s+#", re.I)
_TABLE_LINE_RE = re.compile(
    r"^Table '([^']*)' (\d+)-max Seat #(\d+) is the button\s*$"
)
_CASH_STAKES_RE = re.compile(
    r"Hold'?em\s+No\s+Limit\s+\(\s*\$?([\d,.]+)\s*/\s*\$?([\d,.]+)\s*\)",
    re.I,
)
_CASHOUT_RE = re.compile(
    r"(?i)^.+?:\s*(?:Chooses to EV Cashout|Pays Cashout Risk\b)"
)

# Hand2Note room table prefixes (clkClubGG.exe room map):
# ClubGG -> CGG_, GG Network -> GG_
_GG_TABLE_PREFIX = "GG_"

_HAND_ID_FN = {
    "ggpoker_ok": gg_display_hand_id,
}


def _is_gg_cash_header(header: str) -> bool:
    if _TOURNAMENT_WORD_RE.search(header):
        return False
    return bool(_CASH_STAKES_RE.search(header))


def is_gg_cash_hand(block: str) -> bool:
    first = block.partition("\n")[0].strip()
    if not first:
        return False
    return _is_gg_cash_header(restore_poker_hand_header_colon(first))


def gg_group_key(block: str) -> str:
    """Tournament id, or cash stakes+date for export splitting."""
    raw_first = block.partition("\n")[0].strip()
    if not raw_first:
        return "unknown"
    header = restore_poker_hand_header_colon(raw_first)
    if _is_gg_cash_header(header):
        stakes = _CASH_STAKES_RE.search(header)
        sb = stakes.group(1) if stakes else "?"
        bb = stakes.group(2) if stakes else "?"
        dt = parse_header_timestamp(header)
        played = dt.date().isoformat() if dt else "unknown-date"
        return f"cash|{played}|{sb}|{bb}"
    m = _TOURNAMENT_ID_RE.search(header)
    return m.group(2) if m else "unknown"


class PokerHandConverter:
    """Convert GGPoker ``Poker Hand #`` blocks to PokerStars format."""

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

        first = restore_poker_hand_header_colon(lines[0].strip())
        m = _POKER_HAND_HEADER_RE.match(first)
        if not m:
            return block

        hid = self._hand_id_fn(m.group(1))
        tail = normalize_level_piece(m.group(2).strip())
        cash = _is_gg_cash_header(first)

        err, tail = append_utc_bracket_et(tail)
        if err:
            pass

        header = f"PokerStars Hand #{hid}: {tail}"
        tid = "" if cash else _extract_tournament_id(tail)
        body: list[str] = []
        append = body.append
        table_seen = False
        for line in lines[1:]:
            if "Cashout" in line or "cashout" in line:
                if _CASHOUT_RE.match(line.strip()):
                    continue
            if not table_seen and line.lstrip().startswith("Table '"):
                table_m = _TABLE_LINE_RE.match(line.strip())
                if table_m:
                    table_seen = True
                    table_id = table_m.group(1)
                    max_seats = table_m.group(2)
                    button = table_m.group(3)
                    if cash:
                        line = (
                            f"Table '{_GG_TABLE_PREFIX}{table_id}' "
                            f"{max_seats}-max Seat #{button} is the button"
                        )
                    else:
                        line = (
                            f"Table '{_GG_TABLE_PREFIX}{tid} {table_id}' "
                            f"{max_seats}-max Seat #{button} is the button"
                        )
                    append(line)
                    continue

            if line.startswith("Dealt to "):
                if not _DEALT_CARDS_EOL_RE.search(line):
                    continue
                append(line)
                continue

            if line and line[0] in ("u", "U") and line.lower().startswith("uncalled bet "):
                line = _normalize_uncalled_line(line)
            elif " won (" in line:
                line = _normalize_won_to_collected(line)
            append(line)
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
    if line.startswith("Dealt to ") and not _DEALT_CARDS_EOL_RE.search(line):
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
    if " won (" not in line or not line.lstrip().startswith("Seat "):
        return line
    if "showed" in line and " with " in line:
        return line
    return line.replace(" won (", " collected (")
