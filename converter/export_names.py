from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from converter.coin_convert import coin_tournament_id
from converter.coin_format import clean_tournament_title
from converter.hand_ids import up_display_tournament_id
from converter.time_et import parse_header_timestamp, strip_existing_et_brackets

_ROOM_ABBREV = {
    "poker_planets": "PP",
    "ggpoker_ok": "GG",
    "uppoker": "UP",
    "coinpoker": "Coin",
}

_PP_HEADER_RE = re.compile(r"PokerPlanets\s+Hand\s+#\d+\s*:\s*(.+)", re.I)
_PP_TOURNAMENT_RE = re.compile(
    r"^Tournament\s+\(([^)]+)\)#(\d+),\s*(.+)$",
    re.I,
)
_GG_HEADER_RE = re.compile(r"Poker\s+Hand\s+#\S+\s*:\s*(.+)", re.I)
_GG_TOURNAMENT_RE = re.compile(
    r"^Tournament\s+#(\d+),\s*(.+?)\s+Hold'em\b",
    re.I,
)
_COIN_TITLE_RE = re.compile(r"^Tournament\s+'([^']+)'\s+'(\d+)'", re.I | re.M)
_COIN_PRICE_RE = re.compile(r"^(₮[\d.]+)")
_USD_PRICE_RE = re.compile(r"\$[\d.]+(?:\+\$[\d.]+)?")
_INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class TournamentMeta:
    room: str
    tournament_id: str
    tournament_price: str
    tournament_name: str
    played_on: date


def export_filename(meta: TournamentMeta) -> str:
    abbrev = _ROOM_ABBREV.get(meta.room, meta.room)
    price = meta.tournament_price
    if meta.room == "poker_planets" and price:
        price = _shorten_pp_price(price)
    parts = [
        abbrev,
        meta.played_on.isoformat(),
        meta.tournament_id,
        _sanitize_filename_part(price),
        _sanitize_filename_part(meta.tournament_name),
    ]
    return f"{' '.join(part for part in parts if part)}.txt"


def tournament_meta_from_blocks(room: str, blocks: list[str]) -> TournamentMeta:
    if not blocks:
        raise ValueError(f"No hands to derive tournament metadata for {room}")

    first = blocks[0].splitlines()[0].strip()
    if room == "poker_planets":
        return _pp_meta(first)
    if room == "ggpoker_ok":
        return _gg_meta(first)
    if room == "uppoker":
        return _up_meta(first)
    if room == "coinpoker":
        return _coin_meta(blocks[0])
    raise ValueError(f"Unsupported room for export naming: {room}")


def _pp_meta(header: str) -> TournamentMeta:
    m = _PP_HEADER_RE.match(header)
    if not m:
        raise ValueError(f"Unrecognized PokerPlanets header: {header!r}")

    tail = m.group(1).strip()
    tm = _PP_TOURNAMENT_RE.match(tail)
    if not tm:
        raise ValueError(f"Unrecognized PokerPlanets tournament header: {tail!r}")

    name, tid, rest = tm.group(1).strip(), tm.group(2), tm.group(3)
    price = _extract_usd_price(rest) or ""
    played = _header_date(rest)
    return TournamentMeta("poker_planets", tid, price, name, played)


def _gg_meta(header: str) -> TournamentMeta:
    m = _GG_HEADER_RE.match(header)
    if not m:
        raise ValueError(f"Unrecognized GG header: {header!r}")

    tail = m.group(1).strip()
    tm = _GG_TOURNAMENT_RE.match(tail)
    if not tm:
        raise ValueError(f"Unrecognized GG tournament header: {tail!r}")

    tid, name_part = tm.group(1), tm.group(2).strip()
    price = _extract_usd_price(name_part) or ""
    name = re.sub(r"^\$[\d.]+\S*\s+", "", name_part).strip()
    name = re.sub(r"\s+\$[\d.]+\S*$", "", name).strip()
    if price and (not name or name == price):
        name = ""
    if not name and not price:
        name = "Tournament"
    played = _header_date(tail)
    return TournamentMeta("ggpoker_ok", tid, price, name, played)


def _up_meta(header: str) -> TournamentMeta:
    meta = _gg_meta(header)
    raw_tid_m = re.search(r"Tournament\s+#(\d+)", header, re.I)
    raw_tid = raw_tid_m.group(1) if raw_tid_m else meta.tournament_id
    return TournamentMeta(
        "uppoker",
        up_display_tournament_id(raw_tid),
        meta.tournament_price,
        meta.tournament_name,
        meta.played_on,
    )


def _coin_meta(block: str) -> TournamentMeta:
    tid = coin_tournament_id(block)
    title_m = _COIN_TITLE_RE.search(block)
    raw_title = title_m.group(1) if title_m else ""
    price_m = _COIN_PRICE_RE.match(raw_title.strip())
    price = price_m.group(1) if price_m else ""
    name = clean_tournament_title(raw_title) if raw_title else tid

    header = block.splitlines()[0].strip()
    played = _header_date(header)
    return TournamentMeta("coinpoker", tid, price, name, played)


def _extract_usd_price(text: str) -> str | None:
    m = _USD_PRICE_RE.search(text)
    return m.group(0) if m else None


def _shorten_pp_price(price: str) -> str:
    parts = [f"${_shorten_decimal_zeros(m.group(1))}" for m in re.finditer(r"\$([\d.]+)", price)]
    return "+".join(parts) if parts else price


def _shorten_decimal_zeros(amount: str) -> str:
    if "." not in amount:
        return amount
    whole, frac = amount.split(".", 1)
    frac = frac.rstrip("0")
    return whole if not frac else f"{whole}.{frac}"


def _header_date(text: str) -> date:
    cleaned = strip_existing_et_brackets(text.rstrip())
    dt = parse_header_timestamp(cleaned)
    if dt is None:
        raise ValueError(f"Could not parse tournament date from: {text!r}")
    return dt.date()


def _sanitize_filename_part(text: str) -> str:
    cleaned = _INVALID_FILENAME_CHARS_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
