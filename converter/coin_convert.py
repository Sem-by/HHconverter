from __future__ import annotations

import re

from converter.coin_format import (
    clean_tournament_title,
    coin_postprocess,
    coin_timestamp_to_utc,
    format_cash_body_line,
    format_coin_body_line,
    format_ps_body_line,
    format_stakes_int,
    normalize_coin_hand_actions,
    normalize_money,
)
from converter.hand_ids import HAND_PREFIX_COINPOKER, prefixed_hand_id
from converter.normalize import global_postprocess, replace_seat_token
from converter.player_names import COIN_PLAYER_TOKEN, CashMultiTableNameSession, PlayerNameSession
from converter.pp_blinds import format_blinds_piece
from converter.pp_format import normalize_pp_header_timestamp
from converter.settings import SOURCE_HERO_TOKEN
from converter.time_et import parse_header_timestamp, strip_existing_et_brackets

_NUM = r"[\d,.]+"
# Optional currency glyph(s) before amount: ₮ $ € or mojibake / replacement chars.
_MONEY = rf"[^\d\s/)]*{_NUM}"
_COIN_TOURNEY_HAND_RE = re.compile(
    rf"CoinPoker\s+Hand\s+#(\d+)\s*:\s*NLH\s+\(({_NUM})/({_NUM})/({_NUM})\)\s+(.+)$",
)
# NLH (₮0.01/₮0.02) …  or  Hold'em No Limit (0.01/0.02 ) …
_COIN_CASH_HAND_RE = re.compile(
    rf"CoinPoker\s+Hand\s+#(\d+)\s*:\s*"
    rf"(?:NLH|Hold'?em\s+No\s+Limit)\s+"
    rf"\(\s*({_MONEY})\s*/\s*({_MONEY})\s*\)\s*(?:-\s*)?(.+)$",
    re.I,
)
# Loose fallback for cash stakes when game-type wording differs (PLO, etc.).
_COIN_CASH_STAKES_LOOSE_RE = re.compile(
    rf"CoinPoker\s+Hand\s+#(\d+)\s*:\s*.+?"
    rf"\(\s*({_MONEY})\s*/\s*({_MONEY})\s*\)\s*(?:-\s*)?(.+)$",
    re.I,
)
# Older CoinPoker export: Tournament #id embedded in the first line + Table on line 2.
_COIN_LEGACY_HAND_RE = re.compile(
    r"CoinPoker\s+Hand\s+#(\d+)\s*:\s*Tournament\s+#(\d+),\s*(.+?)\s+"
    r"Hold'em No Limit\s+\(([^)]+)\)\s+(.+)$",
    re.I,
)
_COIN_LEGACY_STAKES_RE = re.compile(
    rf"({_MONEY})\s*/\s*({_MONEY})(?:\s+ante\s+({_MONEY}))?",
    re.I,
)
_COIN_TOURNAMENT_RE = re.compile(
    r"^Tournament\s+'(.+?)'\s+'(\d+)'\s+(\d+)-max\s+Seat\s+#(\d+)\s+is\s+the\s+button\s*$",
)
_COIN_CASH_TABLE_RE = re.compile(
    r"^Table\s+'(.+?)'\s+(\d+)-max\s+Seat\s+#(\d+)\s+is\s+the\s+button\s*$",
    re.I,
)
_N_MAX_TITLE_RE = re.compile(r"^\d+-Max\b", re.I)
_TOURNAMENT_HASH_RE = re.compile(r"Tournament\s+#(\d+)", re.I)


def is_coin_cash_hand(block: str) -> bool:
    lines = block.splitlines()
    if not lines:
        return False
    header = lines[0].strip()
    if _COIN_LEGACY_HAND_RE.match(header) or _TOURNAMENT_HASH_RE.search(header):
        return False
    if any(_COIN_TOURNAMENT_RE.match(ln.strip()) for ln in lines[1:6]):
        return False
    if re.search(r"^Tournament\s+'", block, re.M):
        return False
    # Only treat as cash when the header stakes are parseable (avoids detect/parse mismatch).
    if not (
        _COIN_CASH_HAND_RE.match(header) or _COIN_CASH_STAKES_LOOSE_RE.match(header)
    ):
        return False
    return _find_cash_table_line(lines) is not None


def is_coin_legacy_tournament(block: str) -> bool:
    lines = block.splitlines()
    if not lines:
        return False
    return bool(_COIN_LEGACY_HAND_RE.match(lines[0].strip()))


def coin_tournament_id(block: str) -> str:
    m = _COIN_TOURNAMENT_RE.search(block)
    if m:
        return m.group(2)
    m = re.search(r"Tournament\s+'(.+?)'\s+'(\d+)'\s+", block)
    if m:
        return m.group(2)
    m = _TOURNAMENT_HASH_RE.search(block)
    if m:
        return m.group(1)
    raise ValueError("CoinPoker hand missing Tournament id line")


def coin_group_key(block: str) -> str:
    """Group key for export splitting (tournament id or cash stakes+date)."""
    if is_coin_cash_hand(block):
        parsed = _parse_coin_cash_hand(block)
        if parsed is None:
            header = block.splitlines()[0].strip() if block.splitlines() else ""
            raise ValueError(f"Unrecognized CoinPoker cash hand: {header!r}")
        hand_id, sb, bb, time_part, table_name, max_seats, button, body = parsed
        del hand_id, table_name, max_seats, button, body
        try:
            played = _cash_played_on(time_part)
        except ValueError:
            # Keep Convert running when one cash header has a bad/missing timestamp.
            played = "unknown-date"
        sb_s = format_stakes_int(sb)
        bb_s = format_stakes_int(bb)
        return f"cash|{played}|{sb_s}|{bb_s}"
    return coin_tournament_id(block)


def _parse_stakes_token(raw: str) -> float:
    cleaned = re.sub(r"[^\d,.]+", "", raw)
    return float(normalize_money(cleaned))


def _find_cash_table_line(lines: list[str]) -> re.Match[str] | None:
    for ln in lines[1:8]:
        stripped = ln.strip()
        if not stripped:
            continue
        m = _COIN_CASH_TABLE_RE.match(stripped)
        if m:
            return m
        # Stop at seat/action content so we don't scan the whole hand.
        if stripped.startswith("Seat ") or stripped.startswith("***"):
            break
    return None


def _cash_played_on(time_part: str) -> str:
    cleaned = strip_existing_et_brackets(time_part.rstrip())
    dt = parse_header_timestamp(cleaned)
    if dt is None:
        raise ValueError(f"Could not parse cash date from: {time_part!r}")
    return dt.date().isoformat()


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
        self._cash_players = CashMultiTableNameSession(
            name_suffix="_coin",
            should_rename=self._should_rename_opponent,
        )

    def _should_rename_opponent(self, token: str) -> bool:
        return bool(COIN_PLAYER_TOKEN(token)) and token != SOURCE_HERO_TOKEN

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        self._players.reset()
        self._cash_players.reset()
        out: list[str] = []
        for idx, block in enumerate(blocks):
            if is_coin_cash_hand(block):
                body = self._cash_players.map_players(block)
            else:
                next_text = _next_tournament_block(blocks, idx)
                body = self._players.map_players(block, next_hand_text=next_text)
            out.append(self.convert_hand(body))
        return out

    def convert_hand(self, block: str) -> str:
        text = _build_hand(block, coin_as_ps=self._coin_as_ps)
        hero_name = self._hero_display_name
        if not hero_name.endswith("_coin"):
            hero_name = f"{hero_name}_coin"
        text = replace_seat_token(text, SOURCE_HERO_TOKEN, hero_name)
        if is_coin_cash_hand(block):
            text = normalize_coin_hand_actions(text)
            return global_postprocess(text)
        if self._coin_as_ps:
            text = normalize_coin_hand_actions(text)
            return global_postprocess(text)
        return coin_postprocess(text)


def _next_tournament_block(blocks: list[str], idx: int) -> str | None:
    """Next non-cash Coin hand (tournament continuity ignores interleaved cash)."""
    for j in range(idx + 1, len(blocks)):
        if not is_coin_cash_hand(blocks[j]):
            return blocks[j]
    return None


def _parse_coin_hand(block: str):
    lines = block.splitlines()
    if len(lines) < 2:
        return None

    legacy = _parse_coin_legacy_hand(block)
    if legacy is not None:
        return legacy

    hm = _COIN_TOURNEY_HAND_RE.match(lines[0].strip())
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


def _parse_coin_legacy_hand(block: str):
    """Older format with ``Tournament #id`` on the hand line and a Table line."""
    lines = block.splitlines()
    if len(lines) < 2:
        return None

    hm = _COIN_LEGACY_HAND_RE.match(lines[0].strip())
    if not hm:
        return None

    tm = _find_cash_table_line(lines)
    if not tm:
        return None

    stakes = _COIN_LEGACY_STAKES_RE.match(hm.group(4).strip())
    if not stakes:
        return None

    table_idx = next(
        (
            i
            for i, ln in enumerate(lines[1:8], start=1)
            if _COIN_CASH_TABLE_RE.match(ln.strip())
        ),
        None,
    )
    if table_idx is None:
        return None

    ante_raw = stakes.group(3) or "0"
    return (
        hm.group(1),
        _parse_stakes_token(stakes.group(1)),
        _parse_stakes_token(stakes.group(2)),
        _parse_stakes_token(ante_raw),
        hm.group(5).strip(),
        hm.group(3).strip(),
        hm.group(2).strip(),
        tm.group(2),
        tm.group(3),
        lines[table_idx + 1 :],
    )


def _parse_coin_cash_hand(block: str):
    lines = block.splitlines()
    if len(lines) < 2:
        return None

    header = lines[0].strip()
    hm = _COIN_CASH_HAND_RE.match(header) or _COIN_CASH_STAKES_LOOSE_RE.match(header)
    if not hm:
        return None

    tm = _find_cash_table_line(lines)
    if not tm:
        return None

    # Body starts after the Table line we matched.
    table_idx = next(
        i for i, ln in enumerate(lines[1:8], start=1) if _COIN_CASH_TABLE_RE.match(ln.strip())
    )
    return (
        hm.group(1),
        _parse_stakes_token(hm.group(2)),
        _parse_stakes_token(hm.group(3)),
        hm.group(4).strip(),
        tm.group(1).strip(),
        tm.group(2),
        tm.group(3),
        lines[table_idx + 1 :],
    )


def _build_hand(block: str, *, coin_as_ps: bool) -> str:
    if is_coin_cash_hand(block):
        return _build_hand_cash(block, coin_as_ps=coin_as_ps)
    if coin_as_ps:
        return _build_hand_ps(block)
    return _build_hand_h2n(block)


def _build_hand_cash(block: str, *, coin_as_ps: bool) -> str:
    parsed = _parse_coin_cash_hand(block)
    if parsed is None:
        return block

    hand_id, sb, bb, time_part, table_name, max_seats, button, body_lines = parsed
    utc_time = coin_timestamp_to_utc(time_part)
    sb_s = format_stakes_int(sb)
    bb_s = format_stakes_int(bb)
    if coin_as_ps:
        # PokerStars-style for non-PRO H2N: prefixed hand id, plain table name.
        hid = prefixed_hand_id(HAND_PREFIX_COINPOKER, hand_id)
        table_line = f"Table '{table_name}' {max_seats}-max Seat #{button} is the button"
    else:
        # H2N Coin-room style: raw hand id, CPR_ table prefix separates from real PS.
        hid = hand_id
        table_line = (
            f"Table 'CPR_{table_name} 0' {max_seats}-max Seat #{button} is the button"
        )
    header = (
        f"PokerStars Hand #{hid}: Hold'em No Limit (${sb_s}/${bb_s}) - {utc_time}"
    )

    out_body: list[str] = []
    for line in body_lines:
        formatted = format_cash_body_line(line)
        if formatted is not None:
            out_body.append(formatted)

    return "\n".join([header, table_line, *out_body])


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
