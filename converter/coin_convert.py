from __future__ import annotations

import re

from converter.coin_format import (
    clean_tournament_title,
    coin_postprocess,
    coin_timestamp_to_utc,
    format_coin_body_line,
    format_ps_body_line,
    format_stakes_int,
    normalize_coin_hand_actions,
)
from converter.hand_ids import HAND_PREFIX_COINPOKER, prefixed_hand_id
from converter.normalize import global_postprocess, replace_seat_token
from converter.player_names import COIN_PLAYER_TOKEN, PlayerNameSession
from converter.pp_blinds import format_blinds_piece
from converter.pp_format import normalize_pp_header_timestamp
from converter.settings import SOURCE_HERO_TOKEN

_NUM = r"[\d,.]+"
_COIN_HAND_RE = re.compile(
    rf"CoinPoker\s+Hand\s+#(\d+)\s*:\s*NLH\s+\(({_NUM})/({_NUM})/({_NUM})\)\s+(.+)$",
)
_COIN_TOURNAMENT_RE = re.compile(
    r"^Tournament\s+'(.+?)'\s+'(\d+)'\s+(\d+)-max\s+Seat\s+#(\d+)\s+is\s+the\s+button\s*$",
)
_N_MAX_TITLE_RE = re.compile(r"^\d+-Max\b", re.I)


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


def coin_h2n_tournament_title(title_raw: str, max_seats: str) -> str:
    """Hand2Note Coin datetime parsing needs ``{N}-Max …`` or ``Freeroll`` in the header title."""
    title = clean_tournament_title(title_raw)
    if title.lower().startswith("freeroll") or _N_MAX_TITLE_RE.match(title):
        return title
    return f"{max_seats}-Max {title}"


def _stakes_int(value: float) -> int:
    return int(value) if value == int(value) else int(round(value))


class CoinPokerConverter:
    """Convert CoinPoker export text for Hand2Note import."""

    def __init__(self, hero_display_name: str, *, coin_as_ps: bool = False) -> None:
        self._hero_display_name = hero_display_name
        self._coin_as_ps = coin_as_ps
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
        text = _build_hand(block, coin_as_ps=self._coin_as_ps)
        hero_name = self._hero_display_name
        if self._coin_as_ps:
            hero_name = f"{hero_name}_coin"
        text = replace_seat_token(text, SOURCE_HERO_TOKEN, hero_name)
        if self._coin_as_ps:
            text = normalize_coin_hand_actions(text)
            return global_postprocess(text)
        return coin_postprocess(text)


def _parse_coin_hand(block: str):
    lines = block.splitlines()
    if len(lines) < 2:
        return None

    hm = _COIN_HAND_RE.match(lines[0].strip())
    if not hm:
        return None

    tm = _COIN_TOURNAMENT_RE.match(lines[1].strip())
    if not tm:
        return None

    return (
        hm.group(1),
        _parse_stakes_token(hm.group(2)),
        _parse_stakes_token(hm.group(3)),
        _parse_stakes_token(hm.group(4)),
        hm.group(5).strip(),
        tm.group(1).strip(),
        tm.group(2).strip(),
        tm.group(3),
        tm.group(4),
        lines[2:],
    )


def _build_hand(block: str, *, coin_as_ps: bool) -> str:
    if coin_as_ps:
        return _build_hand_ps(block)
    return _build_hand_h2n(block)


def _build_hand_h2n(block: str) -> str:
    parsed = _parse_coin_hand(block)
    if parsed is None:
        return block

    hand_id, sb, bb, _ante, time_part, title_raw, tid, max_seats, button, body_lines = parsed
    title = coin_h2n_tournament_title(title_raw, max_seats)
    sb_s = format_stakes_int(sb)
    bb_s = format_stakes_int(bb)
    utc_time = coin_timestamp_to_utc(time_part)

    header = (
        f"PokerStars Hand #{hand_id}: Tournament #{tid}, {title} Hold'em No Limit "
        f"- Level ({sb_s}/{bb_s}) - {utc_time}"
    )
    table_line = f"Table 'CPR_{tid} 0' {max_seats}-max Seat #{button} is the button"

    out_body: list[str] = []
    for line in body_lines:
        formatted = format_coin_body_line(line)
        if formatted is not None:
            out_body.append(formatted)

    return "\n".join([header, table_line, *out_body])


def _build_hand_ps(block: str) -> str:
    parsed = _parse_coin_hand(block)
    if parsed is None:
        return block

    hand_id, sb, bb, ante, time_part, title_raw, tid, max_seats, button, body_lines = parsed
    hid = prefixed_hand_id(HAND_PREFIX_COINPOKER, hand_id)
    utc_time = coin_timestamp_to_utc(time_part)
    level_piece = format_blinds_piece(_stakes_int(sb), _stakes_int(bb), _stakes_int(ante))
    tail = (
        f"Tournament #{tid}, {title_raw} Hold'em No Limit "
        f"- Level I {level_piece} - {utc_time}"
    )
    tail = normalize_pp_header_timestamp(tail)
    header = f"PokerStars Hand #{hid}: {tail}"
    table_line = f"Table '{tid} 1' {max_seats}-max Seat #{button} is the button"

    out_body: list[str] = []
    for line in body_lines:
        formatted = format_ps_body_line(line)
        if formatted is not None:
            out_body.append(formatted)

    return "\n".join([header, table_line, *out_body])
