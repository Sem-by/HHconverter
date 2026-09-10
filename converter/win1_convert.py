from __future__ import annotations

import re
from datetime import date

from converter.hand_ids import onewin_display_hand_id
from converter.time_et import parse_header_timestamp, strip_existing_et_brackets

_HAND_HEADER_RE = re.compile(
    r"1WinPoker\s+Hand\s+#(\d+)\s*:\s*(.+)$",
    re.I,
)
_TOURNEY_TAIL_RE = re.compile(
    r"^Tournament\s+\((.+?)\)#(\d+)\s*,\s*(.+?)\s+Hold'?em\s+No\s+Limit\s+"
    r"-\s*Level\s+(\S+)\s+\(([^)]+)\)\s+-\s*(.+)$",
    re.I,
)
_CASH_TAIL_RE = re.compile(
    r"^Hold'?em\s+No\s+Limit\s+\(([^)]+)\)\s+-\s*(.+)$",
    re.I,
)
_CASH_STAKES_RE = re.compile(
    r"([\d,.]+)\s*\$?\s*/\s*([\d,.]+)\s*\$?",
)
_TABLE_TOURNEY_RE = re.compile(
    r"^Table\s+'([^']+)'\((\d+)\)\s+(\d+)-max\s+Seat\s+#(\d+)\s+is\s+the\s+button\s*$",
    re.I,
)
_TABLE_CASH_RE = re.compile(
    r"^Table\s+'([^']+)'\((\d+)\)\s+(\d+)-max\s+\(Real Money\)\s+"
    r"Seat\s+#(\d+)\s+is\s+the\s+button\s*$",
    re.I,
)
_MONEY_SPACE_RE = re.compile(r"([\d,.]+)\s+\$")
_UNCALLED_RE = re.compile(
    r"^Uncalled bet \(([^)]+)\) returned to (\S+)\s*$",
    re.I,
)
_EMPTY_DEALT_RE = re.compile(r"^Dealt to \S+\s*$")
_BUYIN_RE = re.compile(
    r"([\d,.]+)\s*\$\s*\+\s*([\d,.]+)\s*\$",
)
_BUYIN_SINGLE_RE = re.compile(r"([\d,.]+)\s*\$")
_SEAT_LINE_RE = re.compile(r"^Seat\s+(\d+):\s+(\S+)\s+\(")
_BUTTON_RE = re.compile(r"Seat\s+#(\d+)\s+is\s+the\s+button", re.I)
_SB_POST_RE = re.compile(r"^(\S+):\s+posts\s+small\s+blind\b", re.I)
_BB_POST_RE = re.compile(r"^(\S+):\s+posts\s+big\s+blind\b", re.I)

# Hand2Note-style table prefix for 1Win (parallel to GG_ / CPR_).
_ONEWIN_TABLE_PREFIX = "1W_"


def is_onewin_cash_hand(block: str) -> bool:
    lines = block.splitlines()
    if not lines:
        return False
    header = lines[0].strip()
    m = _HAND_HEADER_RE.match(header)
    if not m:
        return False
    tail = m.group(2).strip()
    if tail.lower().startswith("tournament"):
        return False
    return bool(_CASH_TAIL_RE.match(tail))


def onewin_tournament_id(block: str) -> str:
    lines = block.splitlines()
    if not lines:
        raise ValueError("empty 1Win hand")
    m = _HAND_HEADER_RE.match(lines[0].strip())
    if not m:
        raise ValueError(f"Unrecognized 1Win header: {lines[0]!r}")
    tm = _TOURNEY_TAIL_RE.match(m.group(2).strip())
    if not tm:
        raise ValueError(f"Unrecognized 1Win tournament header: {m.group(2)!r}")
    return tm.group(2)


def onewin_group_key(block: str) -> str:
    if is_onewin_cash_hand(block):
        meta = onewin_cash_meta(block)
        return f"cash|{meta[0].isoformat()}|{meta[1]}|{meta[2]}"
    return onewin_tournament_id(block)


def onewin_cash_meta(block: str) -> tuple[date, str, str]:
    """Return (played_on, sb, bb) for a cash hand."""
    lines = block.splitlines()
    header = lines[0].strip()
    m = _HAND_HEADER_RE.match(header)
    if not m:
        raise ValueError(f"Unrecognized 1Win header: {header!r}")
    cm = _CASH_TAIL_RE.match(m.group(2).strip())
    if not cm:
        raise ValueError(f"Unrecognized 1Win cash header: {m.group(2)!r}")
    stakes = _CASH_STAKES_RE.search(cm.group(1))
    if not stakes:
        raise ValueError(f"Unrecognized 1Win cash stakes: {cm.group(1)!r}")
    sb = _fmt_stakes(stakes.group(1))
    bb = _fmt_stakes(stakes.group(2))
    played = _parse_date(cm.group(2).strip())
    return played, sb, bb


def onewin_tournament_meta(block: str) -> tuple[str, str, str, date]:
    """Return (tid, price, name, played_on)."""
    lines = block.splitlines()
    header = lines[0].strip()
    m = _HAND_HEADER_RE.match(header)
    if not m:
        raise ValueError(f"Unrecognized 1Win header: {header!r}")
    tm = _TOURNEY_TAIL_RE.match(m.group(2).strip())
    if not tm:
        raise ValueError(f"Unrecognized 1Win tournament header: {m.group(2)!r}")
    name = tm.group(1).strip()
    tid = tm.group(2)
    price = _normalize_buyin(tm.group(3).strip())
    played = _parse_date(tm.group(6).strip())
    return tid, price, name, played


_SEAT_NAME_RE = re.compile(
    r"^Seat\s+\d+:\s+(\S+)\s+\(",
    re.I | re.M,
)
_ONEWIN_NAME_SUFFIX = "_1win"


def _suffix_all_players(text: str) -> str:
    """Append ``_1win`` to every seated player name (room isolation in H2N)."""
    names = []
    seen: set[str] = set()
    for m in _SEAT_NAME_RE.finditer(text):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    # Longer names first so partial overlaps cannot rewrite already-suffixed tokens.
    names.sort(key=len, reverse=True)
    for name in names:
        if name.endswith(_ONEWIN_NAME_SUFFIX):
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)")
        text = pattern.sub(name + _ONEWIN_NAME_SUFFIX, text)
    return text


class OneWinConverter:
    """Convert 1WinPoker cash and tournament hands to PokerStars-style text."""

    def convert_file_blocks(self, blocks: list[str]) -> list[str]:
        return [self.convert_hand(block) for block in blocks]

    def convert_hand(self, block: str) -> str:
        lines = block.splitlines()
        if not lines:
            return block
        header = lines[0].strip()
        m = _HAND_HEADER_RE.match(header)
        if not m:
            return block

        hid = onewin_display_hand_id(m.group(1))
        tail = m.group(2).strip()

        if is_onewin_cash_hand(block):
            converted = self._convert_cash(hid, tail, lines[1:])
        else:
            converted = self._convert_tournament(hid, tail, lines[1:])
        return _postprocess_ps_hand(_suffix_all_players(converted))

    def _convert_cash(self, hid: str, tail: str, body_lines: list[str]) -> str:
        cm = _CASH_TAIL_RE.match(tail)
        if not cm:
            return "\n".join([f"PokerStars Hand #{hid}: {tail}", *body_lines])

        stakes_raw = cm.group(1)
        time_part = cm.group(2).strip()
        stakes = _CASH_STAKES_RE.search(stakes_raw)
        if stakes:
            sb = _fmt_stakes(stakes.group(1))
            bb = _fmt_stakes(stakes.group(2))
            stakes_s = f"${sb}/${bb}"
        else:
            stakes_s = _money_to_ps(stakes_raw)

        utc = _to_utc(time_part)
        header = f"PokerStars Hand #{hid}: Hold'em No Limit ({stakes_s}) - {utc}"

        out: list[str] = []
        for line in body_lines:
            converted = _convert_body_line(line, cash=True)
            if converted is None:
                continue
            if not out:
                table = _TABLE_CASH_RE.match(converted.strip())
                if table:
                    name, _tid, max_seats, button = table.groups()
                    converted = (
                        f"Table '{_ONEWIN_TABLE_PREFIX}{_clean_table_name(name)}' "
                        f"{max_seats}-max Seat #{button} is the button"
                    )
            out.append(converted)
        return "\n".join([header, *out])

    def _convert_tournament(self, hid: str, tail: str, body_lines: list[str]) -> str:
        tm = _TOURNEY_TAIL_RE.match(tail)
        if not tm:
            return "\n".join([f"PokerStars Hand #{hid}: {tail}", *body_lines])

        name = tm.group(1).strip()
        tid = tm.group(2)
        buyin = _normalize_buyin(tm.group(3).strip())
        level = tm.group(4)
        blinds = tm.group(5).strip()
        utc = _to_utc(tm.group(6).strip())
        header = (
            f"PokerStars Hand #{hid}: Tournament #{tid}, {buyin} {name} "
            f"Hold'em No Limit - Level {level} ({blinds}) - {utc}"
        )

        out: list[str] = []
        for line in body_lines:
            converted = _convert_body_line(line, cash=False)
            if converted is None:
                continue
            if not out:
                table = _TABLE_TOURNEY_RE.match(converted.strip())
                if table:
                    name_t, _inner, max_seats, button = table.groups()
                    converted = (
                        f"Table '{_ONEWIN_TABLE_PREFIX}{_clean_table_name(name_t)}' "
                        f"{max_seats}-max Seat #{button} is the button"
                    )
            out.append(converted)
        return "\n".join([header, *out])


def _clean_table_name(name: str) -> str:
    """Strip ``#`` so H2N does not confuse table tags with ``Seat #N``."""
    cleaned = name.replace("#", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _postprocess_ps_hand(text: str) -> str:
    """H2N-friendly fixes: blinds required as a pair; bomb-pot preflop; no walk SHOW DOWN."""
    lines = text.splitlines()
    lines = _ensure_blind_posts(lines)
    lines = _fill_skipped_preflop(lines)
    lines = _strip_walk_showdown(lines)
    return "\n".join(lines)


def _next_occupied_seat(seats: list[int], after: int) -> int:
    ordered = sorted(seats)
    for seat in ordered:
        if seat > after:
            return seat
    return ordered[0]


def _preflop_action_order(seats: dict[int, str], bb_seat: int) -> list[str]:
    """UTG → … → BB (everyone acts, BB last)."""
    seat_nums = list(seats.keys())
    order: list[str] = []
    seat = _next_occupied_seat(seat_nums, bb_seat)
    start = seat
    while True:
        order.append(seats[seat])
        seat = _next_occupied_seat(seat_nums, seat)
        if seat == start:
            break
    return order


def _ensure_blind_posts(lines: list[str]) -> list[str]:
    """Hand2Note ignores a lone BB and crashes on ante-only (bomb pot) hands.

    Inject missing SB/BB as ``$0`` / ``0`` so positions resolve without changing pot.
    """
    btn_m = None
    seats: dict[int, str] = {}
    has_sb = False
    has_bb = False
    hole_idx: int | None = None

    for i, line in enumerate(lines):
        if btn_m is None:
            btn_m = _BUTTON_RE.search(line)
        sm = _SEAT_LINE_RE.match(line)
        if sm:
            seats[int(sm.group(1))] = sm.group(2)
            continue
        if hole_idx is None and line.strip() == "*** HOLE CARDS ***":
            hole_idx = i
            continue
        if hole_idx is not None:
            continue
        if _SB_POST_RE.match(line):
            has_sb = True
        if _BB_POST_RE.match(line):
            has_bb = True

    if has_sb and has_bb:
        return lines
    if hole_idx is None or btn_m is None or len(seats) < 2:
        return lines

    button = int(btn_m.group(1))
    seat_nums = list(seats.keys())
    sb_seat = _next_occupied_seat(seat_nums, button)
    bb_seat = _next_occupied_seat(seat_nums, sb_seat)
    zero = "$0" if any("$" in ln for ln in lines[: hole_idx + 1]) else "0"

    result = list(lines)
    # SB must appear before BB or H2N drops the BB flag.
    if not has_sb:
        sb_line = f"{seats[sb_seat]}: posts small blind {zero}"
        insert_at = hole_idx
        for i, line in enumerate(result):
            if i >= hole_idx:
                break
            if _BB_POST_RE.match(line):
                insert_at = i
                break
        result.insert(insert_at, sb_line)
        hole_idx += 1
    if not has_bb:
        bb_line = f"{seats[bb_seat]}: posts big blind {zero}"
        result.insert(hole_idx, bb_line)
    return result


_ACTION_LINE_RE = re.compile(
    r"^(\S+):\s+(folds|checks|calls|bets|raises)\b",
    re.I,
)


def _fill_skipped_preflop(lines: list[str]) -> list[str]:
    """Bomb pots jump HOLE → FLOP; with synthetic blinds H2N still needs a preflop round."""
    hole_idx: int | None = None
    flop_idx: int | None = None
    for i, line in enumerate(lines):
        core = line.strip()
        if hole_idx is None and core == "*** HOLE CARDS ***":
            hole_idx = i
        elif hole_idx is not None and flop_idx is None and core.startswith("*** FLOP"):
            flop_idx = i
            break
    if hole_idx is None or flop_idx is None:
        return lines

    between = lines[hole_idx + 1 : flop_idx]
    if any(_ACTION_LINE_RE.match(ln) for ln in between):
        return lines

    seats: dict[int, str] = {}
    bb_seat: int | None = None
    for line in lines[:hole_idx]:
        sm = _SEAT_LINE_RE.match(line)
        if sm:
            seats[int(sm.group(1))] = sm.group(2)
            continue
        bm = _BB_POST_RE.match(line)
        if bm and bb_seat is None:
            name = bm.group(1)
            for seat, nick in seats.items():
                if nick == name:
                    bb_seat = seat
                    break
    if bb_seat is None or len(seats) < 2:
        return lines

    checks = [f"{name}: checks" for name in _preflop_action_order(seats, bb_seat)]
    # Insert after Dealt-to / blank lines, immediately before FLOP.
    insert_at = flop_idx
    return [*lines[:insert_at], *checks, *lines[insert_at:]]


def _strip_walk_showdown(lines: list[str]) -> list[str]:
    """Drop SHOW DOWN when nobody shows/mucks (walks / uncontested pots)."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "*** SHOW DOWN ***":
            out.append(lines[i])
            i += 1
            continue
        j = i + 1
        body: list[str] = []
        while j < len(lines) and not lines[j].startswith("*** SUMMARY"):
            body.append(lines[j])
            j += 1
        has_reveal = any(
            ("shows [" in ln) or ("mucks hand" in ln.lower()) for ln in body
        )
        if has_reveal:
            out.append(lines[i])
            out.extend(body)
        else:
            for ln in body:
                low = ln.lower()
                if "collected" in low and "doesn't show" not in low:
                    out.append(ln)
        i = j
    return out


def _convert_body_line(line: str, *, cash: bool) -> str | None:
    stripped = line.rstrip()
    if _EMPTY_DEALT_RE.match(stripped):
        return None
    if cash:
        stripped = _money_to_ps(stripped)
    m = _UNCALLED_RE.match(stripped)
    if m:
        return f"Uncalled bet ({m.group(1)}) returned to {m.group(2)}"
    if "doesn't show hand" in stripped.lower():
        return stripped
    if " won (" in stripped and "showed" not in stripped:
        stripped = re.sub(r"\bwon \(", "collected (", stripped)
    return stripped


def _money_to_ps(text: str) -> str:
    """``0.01 $`` / ``0.30 $ in chips`` → ``$0.01`` / ``$0.30 in chips``."""
    return _MONEY_SPACE_RE.sub(r"$\1", text)


def _normalize_buyin(raw: str) -> str:
    m = _BUYIN_RE.search(raw)
    if m:
        return f"${_fmt_stakes(m.group(1))}+${_fmt_stakes(m.group(2))}"
    m = _BUYIN_SINGLE_RE.search(raw)
    if m:
        return f"${_fmt_stakes(m.group(1))}"
    return raw.replace(" $", "").replace("$", "").strip()


def _fmt_stakes(raw: str) -> str:
    cleaned = raw.replace(",", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return cleaned
    if "." in cleaned:
        frac_len = len(cleaned.split(".", 1)[1])
        return f"{value:.{frac_len}f}"
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _parse_date(time_part: str) -> date:
    cleaned = strip_existing_et_brackets(time_part.rstrip())
    dt = parse_header_timestamp(cleaned)
    if dt is None:
        raise ValueError(f"Could not parse 1Win date from: {time_part!r}")
    return dt.date()


def _to_utc(time_part: str) -> str:
    cleaned = strip_existing_et_brackets(time_part.rstrip())
    dt = parse_header_timestamp(cleaned)
    if dt is None:
        if cleaned.upper().endswith("UTC"):
            return cleaned
        return f"{cleaned} UTC"
    return (
        f"{dt.year}/{dt.month:02d}/{dt.day:02d} "
        f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} UTC"
    )
