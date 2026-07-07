from __future__ import annotations

import re

from converter.hand_ids import HAND_PREFIX_POKER_PLANETS, prefixed_hand_id
from converter.pp_blinds import extract_blinds_from_hand, patch_header_blinds
from converter.pp_format import normalize_pp_header_timestamp, normalize_pp_table_line, parse_pp_tournament_header_with_buyin
from converter.player_names import PP_PLAYER_TOKEN, PlayerNameSession

_PP_HEADER_RE = re.compile(r"PokerPlanets\s+Hand\s+#(\d+)\s*:\s*(.+)")

class PokerPlanetsConverter:
    def __init__(self) -> None:
        self._players = PlayerNameSession(
            name_suffix="_pp",
            should_rename=PP_PLAYER_TOKEN,
        )

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        self._players.reset()
        out: list[str] = []
        for idx, block in enumerate(blocks):
            next_text = blocks[idx + 1] if idx + 1 < len(blocks) else None
            body = self._players.map_players(block, next_hand_text=next_text)
            out.append(self._build_hand(body))
        return out

    def _build_hand(self, block: str) -> str:
        lines = block.splitlines()
        if not lines:
            return block

        first = lines[0]
        m = _PP_HEADER_RE.match(first.strip())
        if not m:
            return block

        hid = prefixed_hand_id(HAND_PREFIX_POKER_PLANETS, m.group(1))
        tail = m.group(2).strip()

        tm = parse_pp_tournament_header_with_buyin(tail)
        if tm:
            name, tid, buyin, rest = tm
            tail = f"Tournament #{tid}, {name} {buyin} {rest}".rstrip()

        blinds = extract_blinds_from_hand(block)
        if blinds:
            sb, bb, ante = blinds
            tail = patch_header_blinds(tail, sb, bb, ante)

        tail = normalize_pp_header_timestamp(tail)

        header = f"PokerStars Hand #{hid}: {tail}"

        out_lines = [header]
        for idx, line in enumerate(lines[1:], start=1):
            if idx == 1 and line.strip().startswith("Table "):
                out_lines.append(normalize_pp_table_line(line))
            else:
                out_lines.append(line)

        return "\n".join(out_lines)
