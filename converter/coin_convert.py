from __future__ import annotations

import re

from converter.coin_format import (
    clean_tournament_title,
    coin_postprocess,
    coin_timestamp_to_utc,
    format_coin_body_line,
    format_stakes_int,
)
from converter.player_names import COIN_PLAYER_TOKEN, PlayerNameSession
from converter.normalize import replace_seat_token
from converter.settings import SOURCE_HERO_TOKEN

_NUM = r"[\d,.]+"
_COIN_HAND_RE = re.compile(
    rf"CoinPoker\s+Hand\s+#(\d+)\s*:\s*NLH\s+\(({_NUM})/({_NUM})/({_NUM})\)\s+(.+)$",
)
_COIN_TOURNAMENT_RE = re.compile(
    r"^Tournament\s+'(.+?)'\s+'(\d+)'\s+(\d+)-max\s+Seat\s+#(\d+)\s+is\s+the\s+button\s*$",
)


def coin_tournament_id(block: str) -> str:
    m = _COIN_TOURNAMENT_RE.search(block)
    if m:
        return m.group(2)
    m = re.search(r"Tournament\s+'(.+?)'\s+'(\d+)'\s+", block)
    if m:
        return m.group(2)
    raise ValueError("CoinPoker hand missing Tournament id line")


def _parse_stakes_token(raw: str) -> float:
    return float(raw.replace(",", ""))


class CoinPokerConverter:
    """Convert CoinPoker export text into Hand2Note3 CoinPoker-module layout."""

    def __init__(self, hero_display_name: str) -> None:
        self._hero_display_name = hero_display_name
        self._players = PlayerNameSession(
            name_suffix="_coin",
            should_rename=self._should_rename_opponent,
        )

    def _should_rename_opponent(self, token: str) -> bool:
        return bool(COIN_PLAYER_TOKEN(token)) and token != SOURCE_HERO_TOKEN

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        self._players.reset()
        out: list[str] = []
        for idx, block in enumerate(blocks):
            next_text = blocks[idx + 1] if idx + 1 < len(blocks) else None
            body = self._players.map_players(block, next_hand_text=next_text)
            out.append(self.convert_hand(body))
        return out

    def convert_hand(self, block: str) -> str:
        text = _build_hand(block)
        text = replace_seat_token(
            text,
            SOURCE_HERO_TOKEN,
            self._hero_display_name,
        )
        return coin_postprocess(text)


def _build_hand(block: str) -> str:
    lines = block.splitlines()
    if len(lines) < 2:
        return block

    first = lines[0].strip()
    hm = _COIN_HAND_RE.match(first)
    if not hm:
        return block

    hand_id = hm.group(1)
    sb = _parse_stakes_token(hm.group(2))
    bb = _parse_stakes_token(hm.group(3))
    time_part = hm.group(5).strip()

    tournament_line = lines[1].strip()
    tm = _COIN_TOURNAMENT_RE.match(tournament_line)
    if not tm:
        return block

    title = clean_tournament_title(tm.group(1).strip())
    tid = tm.group(2).strip()
    max_seats = tm.group(3)
    button = tm.group(4)

    sb_s = format_stakes_int(sb)
    bb_s = format_stakes_int(bb)
    utc_time = coin_timestamp_to_utc(time_part)

    header = (
        f"PokerStars Hand #{hand_id}: Tournament #{tid}, {title} Hold'em No Limit "
        f"- Level ({sb_s}/{bb_s}) - {utc_time}"
    )
    table_line = f"Table 'CPR_{tid} 0' {max_seats}-max Seat #{button} is the button"

    body_lines: list[str] = []
    for line in lines[2:]:
        formatted = format_coin_body_line(line)
        if formatted is not None:
            body_lines.append(formatted)

    return "\n".join([header, table_line, *body_lines])
