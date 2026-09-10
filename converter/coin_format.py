from __future__ import annotations

import re
from datetime import datetime

from converter.time_et import parse_header_timestamp

_SHOWDOWN_RE = re.compile(r"\*\*\* SHOWDOWN \*\*\*")
_EMPTY_DEALT_RE = re.compile(r"^Dealt to \S+\s*$")

_MONEY = r"[₮$€]?([\d,.]+)"
_SEAT_CHIPS_RE = re.compile(rf"^(Seat \d+: \S+ \(){_MONEY}( in chips\))$")
_ANTE_RE = re.compile(rf"^(\S+): posts ante {_MONEY}$")
_ANTE_ALLIN_RE = re.compile(rf"^(\S+): posts ante {_MONEY} ALLIN$")
_SB_RE = re.compile(rf"^(\S+): posts small blind {_MONEY}$")
_SB_ALLIN_RE = re.compile(rf"^(\S+): posts small blind {_MONEY} ALLIN$")
_BB_RE = re.compile(rf"^(\S+): posts big blind {_MONEY}$")
_BB_ALLIN_RE = re.compile(rf"^(\S+): posts big blind {_MONEY} ALLIN$")
_RAISE_RE = re.compile(rf"^(\S+): raises {_MONEY} to {_MONEY}(.*)$")
_CALL_RE = re.compile(rf"^(\S+): calls {_MONEY}$")
_BET_RE = re.compile(rf"^(\S+): bets {_MONEY}(.*)$")
_ALLIN_RE = re.compile(rf"^(\S+): ALLIN {_MONEY}$")
_COLLECTED_RE = re.compile(rf"^(\S+) collected {_MONEY} from pot$")
_UNCALLED_RE = re.compile(rf"^Uncalled bet \({_MONEY}\) returned to (\S+)$")
_RETURN_RE = re.compile(rf"^(\S+): RETURN {_MONEY}$")
_TOTAL_POT_RE = re.compile(rf"^Total pot {_MONEY}")
_SUMMARY_WON_ONLY_RE = re.compile(
    rf"^(Seat \d+: \S+(?: \([^)]+\))?) won \({_MONEY}\)\s*$"
)
_SUMMARY_SHOWED_WON_BARE_RE = re.compile(
    rf"^(Seat \d+: \S+) showed \[[^\]]+\] and won \({_MONEY}\)\s*$"
)
_SUMMARY_DIDNT_SHOW_RE = re.compile(
    r"^(Seat \d+: \S+) didn't show\s*$",
    re.I,
)
_SUMMARY_MONEY_RE = re.compile(rf"\({_MONEY}\)")
_TOURNAMENT_TITLE_RE = re.compile(r"^₮[\d.]+\s+")
_CURRENCY_PREFIX_RE = re.compile(r"[₮$€]")


def format_stakes_int(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def normalize_money(amount: str) -> str:
    """Strip thousands separators; keep a single decimal point when present."""
    amount = amount.strip()
    if "." in amount:
        whole, frac = amount.rsplit(".", 1)
        whole = whole.replace(",", "")
        frac = frac.replace(",", "")
        return f"{whole}.{frac}"
    return amount.replace(",", "")


def euro_amount(amount: str) -> str:
    return f"€{normalize_money(amount)}"


def dollar_amount(amount: str) -> str:
    return f"${normalize_money(amount)}"


def clean_tournament_title(title: str) -> str:
    title = title.strip()
    return _TOURNAMENT_TITLE_RE.sub("", title) or title


def format_h2n_utc_datetime(dt: datetime) -> str:
    """Hand2Note CoinPoker / PokerStars text import: ``yyyy/MM/dd H:mm:ss UTC``."""
    return (
        f"{dt.year}/{dt.month:02d}/{dt.day:02d} "
        f"{dt.hour}:{dt.minute:02d}:{dt.second:02d} UTC"
    )


def coin_timestamp_to_utc(time_part: str) -> str:
    time_part = time_part.strip()
    parsed = parse_header_timestamp(time_part)
    if parsed is not None:
        return format_h2n_utc_datetime(parsed)
    if time_part.upper().endswith("UTC"):
        return time_part
    return f"{time_part} UTC"


def _format_amount(amount: str, *, currency: str) -> str:
    cleaned = normalize_money(_CURRENCY_PREFIX_RE.sub("", amount))
    if currency == "€":
        return euro_amount(cleaned)
    if currency == "$":
        return dollar_amount(cleaned)
    return cleaned


def format_coin_body_line(line: str) -> str | None:
    """Tournament CPR_ path: chips as bare numbers (no room-currency glyph)."""
    return _format_body_line(line, currency="")


def format_ps_body_line(line: str) -> str | None:
    return _format_body_line(line, currency="")


def format_cash_body_line(line: str) -> str | None:
    """Cash games: CoinPoker ₮ amounts become ``$``."""
    return _format_body_line(line, currency="$")


_STREET_MARKERS = frozenset({"HOLE CARDS", "FLOP", "TURN", "RIVER", "SHOW DOWN", "SUMMARY"})
_STREET_MARKER_RE = re.compile(
    r"^(?:FIRST|SECOND)\s+(FLOP|TURN|RIVER|SHOW\s*DOWN|SHOWDOWN)$"
    r"|^(HOLE CARDS|FLOP|TURN|RIVER|SHOW\s*DOWN|SHOWDOWN|SUMMARY)$",
    re.I,
)
_BETS_RE = re.compile(r"^(\S+): bets ([€$]?)([\d,.]+)(.*)$")
_RAISES_RE = re.compile(r"^(\S+): raises ([€$]?)([\d,.]+) to ([€$]?)([\d,.]+)(.*)$")
_CALLS_RE = re.compile(r"^(\S+): calls ([€$]?)([\d,.]+)(.*)$")
_ACTION_LINE_RE = re.compile(r"^(\S+): ")


def _street_from_marker(name: str) -> str | None:
    """Map ``FLOP`` / ``FIRST FLOP`` / ``SECOND RIVER`` / … to a street key."""
    m = _STREET_MARKER_RE.match(name.strip())
    if not m:
        return None
    core = (m.group(1) or m.group(2) or "").upper().replace("  ", " ")
    if core in {"SHOW DOWN", "SHOWDOWN"}:
        return "SHOW DOWN"
    return core


def _amount_to_str(amount: float) -> str:
    rounded = round(amount)
    if abs(amount - rounded) < 0.005:
        return str(int(rounded))
    text = f"{amount:.2f}"
    return text.rstrip("0").rstrip(".")


def _money_token(symbol: str, amount: float) -> str:
    value = _amount_to_str(amount)
    return f"{symbol}{value}" if symbol else value


def _fmt_raise(player: str, increment: float, total: float, symbol: str, suffix: str) -> str:
    return (
        f"{player}: raises {_money_token(symbol, increment)} to "
        f"{_money_token(symbol, total)}{suffix}"
    )


def _fmt_call(player: str, amount: float, symbol: str, suffix: str) -> str:
    return f"{player}: calls {_money_token(symbol, amount)}{suffix}"


def normalize_coin_action_lines(lines: list[str]) -> list[str]:
    """Fix ALLIN/bet lines so Hand2Note action stamps parse (raises/calls vs bets)."""
    out: list[str] = []
    street: str | None = None
    street_level = 0.0
    preflop_voluntary = False

    for line in lines:
        marker = re.match(r"\*\*\* (.+?) \*\*\*", line)
        if marker:
            name = _street_from_marker(marker.group(1))
            if name is not None:
                street = name
                street_level = 0.0
                if name != "HOLE CARDS":
                    preflop_voluntary = False
            out.append(line)
            continue

        if street is None or street in ("SUMMARY", "SHOW DOWN"):
            out.append(line)
            continue

        if not _ACTION_LINE_RE.match(line):
            out.append(line)
            continue

        is_preflop = street == "HOLE CARDS"

        bets = _BETS_RE.match(line)
        if bets:
            player, symbol, amount_raw, tail = bets.groups()
            amount = float(normalize_money(amount_raw))
            suffix = " and is all-in" if "all-in" in tail else ""

            if is_preflop and not preflop_voluntary:
                line = _fmt_raise(player, amount, amount, symbol, suffix)
                street_level = amount
                preflop_voluntary = True
            elif street_level > 0:
                if amount <= street_level + 0.005:
                    line = _fmt_call(player, amount, symbol, suffix)
                else:
                    line = _fmt_raise(
                        player, amount - street_level, amount, symbol, suffix
                    )
                    street_level = amount
                preflop_voluntary = preflop_voluntary or is_preflop
            else:
                street_level = amount
                if is_preflop:
                    preflop_voluntary = True
            out.append(line)
            continue

        raises = _RAISES_RE.match(line)
        if raises:
            player, _inc_sym, _inc_raw, total_sym, total_raw, tail = raises.groups()
            if "all-in" not in tail and "ALLIN" in tail:
                line = (
                    f"{player}: raises {raises.group(2)}{raises.group(3)} to "
                    f"{total_sym}{total_raw} and is all-in"
                )
            street_level = float(normalize_money(total_raw))
            if is_preflop:
                preflop_voluntary = True
            out.append(line)
            continue

        calls = _CALLS_RE.match(line)
        if calls:
            amount = float(normalize_money(calls.group(3)))
            street_level = max(street_level, amount)
            if is_preflop:
                preflop_voluntary = True
            out.append(line)
            continue

        if re.match(r"^\S+: (folds|checks)", line):
            out.append(line)
            continue

        out.append(line)

    return out


def normalize_coin_hand_actions(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    text = "\n".join(normalize_coin_action_lines(lines))
    return fix_short_blind_allin_for_h2n(text)


_LEVEL_BLINDS_RE = re.compile(
    r"Level [^\n]*\(([\d,.]+)/([\d,.]+)(?:\(([\d,.]+)\))?\)",
    re.I,
)
_SEAT_STACK_RE = re.compile(
    r"^(Seat \d+: )(\S+) \(([\d,.]+) in chips\)$",
)
_POST_SB_LINE_RE = re.compile(
    r"^(\S+): posts small blind ([\d,.]+)( and is all-in)?$"
)
_POST_BB_AI_LINE_RE = re.compile(
    r"^(\S+): posts big blind ([\d,.]+) and is all-in$"
)
_POST_ANTE_LINE_RE = re.compile(
    r"^(\S+): posts the ante ([\d,.]+)( and is all-in)?$"
)
_UNCALLED_LINE_RE = re.compile(
    r"^Uncalled bet \(([\d,.]+)\) returned to (\S+)$"
)


def _coin_amt_token(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text


def fix_short_blind_allin_for_h2n(text: str) -> str:
    """Rewrite short big-blind all-ins that Hand2Note BuildStats drops or NullRefs.

    Pattern A — walk to chip-dead / short-stack BB (SB folds, no board): H2N expects a
    live BB; rewrite as a normal full-BB walk with enough chips behind.

    Pattern B — blinds-only all-in runout (short BB, no call/raise, board dealt): match
    the SB post to the BB all-in amount, drop uncalled, insert an SB check, and round
    chip amounts to integers (H2N NullRefs on the decimal blinds-only split path).
    """
    lines = text.splitlines()
    if len(lines) < 8:
        return text

    level = _LEVEL_BLINDS_RE.search(lines[0])
    if not level:
        return text
    level_sb = float(normalize_money(level.group(1)))
    level_bb = float(normalize_money(level.group(2)))

    sb_i = bb_i = None
    for i, line in enumerate(lines):
        if sb_i is None and _POST_SB_LINE_RE.match(line):
            sb_i = i
        if bb_i is None and _POST_BB_AI_LINE_RE.match(line):
            bb_i = i
    if sb_i is None or bb_i is None:
        return text

    sb_m = _POST_SB_LINE_RE.match(lines[sb_i])
    bb_m = _POST_BB_AI_LINE_RE.match(lines[bb_i])
    assert sb_m and bb_m
    sb_name, sb_post = sb_m.group(1), float(normalize_money(sb_m.group(2)))
    bb_name, bb_post = bb_m.group(1), float(normalize_money(bb_m.group(2)))

    if bb_post + 0.001 >= level_bb:
        return text

    has_flop = any(line.startswith("*** FLOP ***") for line in lines)
    has_voluntary = any(
        re.match(r"^\S+: (calls|raises|bets) ", line) for line in lines
    )
    uncalled_i = next(
        (i for i, line in enumerate(lines) if _UNCALLED_LINE_RE.match(line)),
        None,
    )
    uncalled_to = None
    if uncalled_i is not None:
        um = _UNCALLED_LINE_RE.match(lines[uncalled_i])
        assert um
        uncalled_to = um.group(2)

    sb_folded = any(line == f"{sb_name}: folds" for line in lines)
    sb_checked = any(line == f"{sb_name}: checks" for line in lines)

    # --- Pattern A: walk to short BB who covered SB ---
    if (
        not has_flop
        and not has_voluntary
        and sb_folded
        and bb_post + 1e-9 >= sb_post
        and uncalled_to == bb_name
    ):
        ante = 0.0
        for line in lines:
            am = _POST_ANTE_LINE_RE.match(line)
            if am and am.group(1) == bb_name:
                ante = float(normalize_money(am.group(2)))
                break
        seat_i = next(
            (
                i
                for i, line in enumerate(lines)
                if (m := _SEAT_STACK_RE.match(line)) and m.group(2) == bb_name
            ),
            None,
        )
        if seat_i is None:
            return text
        seat_m = _SEAT_STACK_RE.match(lines[seat_i])
        assert seat_m
        stack = float(normalize_money(seat_m.group(3)))
        remaining = stack - ante - bb_post
        if remaining + 1e-9 >= sb_post:
            return text

        need_stack = ante + level_bb + sb_post
        lines[seat_i] = f"{seat_m.group(1)}{bb_name} ({_coin_amt_token(need_stack)} in chips)"
        lines[bb_i] = f"{bb_name}: posts big blind {_coin_amt_token(level_bb)}"
        if uncalled_i is not None:
            lines[uncalled_i] = (
                f"Uncalled bet ({_coin_amt_token(level_bb - sb_post)}) "
                f"returned to {bb_name}"
            )
        return "\n".join(lines)

    # --- Pattern B: short BB vs SB runout, no voluntary money ---
    # Matches both the raw form (uncalled to SB) and the prior partial rewrite
    # (SB already matched to BB, uncalled removed).
    pattern_b = (
        has_flop
        and not has_voluntary
        and not sb_folded
        and (
            uncalled_to == sb_name
            or (uncalled_i is None and abs(sb_post - bb_post) < 0.001)
        )
    )
    if pattern_b:
        bb_tok = _coin_amt_token(bb_post)
        lines[sb_i] = f"{sb_name}: posts small blind {bb_tok}"
        lines[bb_i] = f"{bb_name}: posts big blind {bb_tok} and is all-in"
        if uncalled_i is not None:
            del lines[uncalled_i]
            if uncalled_i < sb_i:
                sb_i -= 1
            if uncalled_i < bb_i:
                bb_i -= 1
        if not sb_checked:
            flop_i = next(
                i for i, line in enumerate(lines) if line.startswith("*** FLOP ***")
            )
            lines.insert(flop_i, f"{sb_name}: checks")
        return _integerize_hand_decimals("\n".join(lines))

    return text


def _integerize_hand_decimals(text: str) -> str:
    """Round fractional chip amounts in the body; keep the header buy-in text intact."""

    def repl(match: re.Match[str]) -> str:
        return str(int(round(float(match.group(0)))))

    lines = text.splitlines()
    if not lines:
        return text
    out = [lines[0]]
    for line in lines[1:]:
        out.append(re.sub(r"\d+\.\d+", repl, line))
    return "\n".join(out)


def _format_body_line(line: str, *, currency: str) -> str | None:
    stripped = line.rstrip()
    if not stripped:
        return ""

    if _EMPTY_DEALT_RE.match(stripped):
        return None

    stripped = _SHOWDOWN_RE.sub("*** SHOW DOWN ***", stripped)

    m = _SEAT_CHIPS_RE.match(stripped)
    if m:
        return f"{m.group(1)}{_format_amount(m.group(2), currency=currency)}{m.group(3)}"

    m = _ANTE_ALLIN_RE.match(stripped)
    if m:
        return (
            f"{m.group(1)}: posts the ante "
            f"{_format_amount(m.group(2), currency=currency)} and is all-in"
        )

    m = _ANTE_RE.match(stripped)
    if m:
        return f"{m.group(1)}: posts the ante {_format_amount(m.group(2), currency=currency)}"

    m = _SB_ALLIN_RE.match(stripped)
    if m:
        return (
            f"{m.group(1)}: posts small blind "
            f"{_format_amount(m.group(2), currency=currency)} and is all-in"
        )

    m = _SB_RE.match(stripped)
    if m:
        return f"{m.group(1)}: posts small blind {_format_amount(m.group(2), currency=currency)}"

    m = _BB_ALLIN_RE.match(stripped)
    if m:
        return (
            f"{m.group(1)}: posts big blind "
            f"{_format_amount(m.group(2), currency=currency)} and is all-in"
        )

    m = _BB_RE.match(stripped)
    if m:
        return f"{m.group(1)}: posts big blind {_format_amount(m.group(2), currency=currency)}"

    m = _ALLIN_RE.match(stripped)
    if m:
        return (
            f"{m.group(1)}: bets {_format_amount(m.group(2), currency=currency)} and is all-in"
        )

    m = _RAISE_RE.match(stripped)
    if m:
        tail = m.group(4)
        if "all-in" not in tail and "ALLIN" in tail:
            tail = " and is all-in"
        return (
            f"{m.group(1)}: raises {_format_amount(m.group(2), currency=currency)} to "
            f"{_format_amount(m.group(3), currency=currency)}{tail}"
        )

    m = _CALL_RE.match(stripped)
    if m:
        return f"{m.group(1)}: calls {_format_amount(m.group(2), currency=currency)}"

    m = _BET_RE.match(stripped)
    if m:
        return f"{m.group(1)}: bets {_format_amount(m.group(2), currency=currency)}{m.group(3)}"

    m = _COLLECTED_RE.match(stripped)
    if m:
        return (
            f"{m.group(1)} collected {_format_amount(m.group(2), currency=currency)} from pot"
        )

    m = _UNCALLED_RE.match(stripped)
    if m:
        return (
            f"Uncalled bet ({_format_amount(m.group(1), currency=currency)}) "
            f"returned to {m.group(2)}"
        )

    m = _RETURN_RE.match(stripped)
    if m:
        return (
            f"Uncalled bet ({_format_amount(m.group(2), currency=currency)}) "
            f"returned to {m.group(1)}"
        )

    if stripped.startswith("Total pot"):
        m = _TOTAL_POT_RE.match(stripped)
        if m:
            pot = _format_amount(m.group(1), currency=currency)
            if currency == "€":
                rake = "€0"
            elif currency == "$":
                rake = "$0"
            else:
                rake = "0"
            return f"Total pot {pot} | Rake {rake}"

    m = _SUMMARY_WON_ONLY_RE.match(stripped)
    if m:
        return f"{m.group(1)} collected ({_format_amount(m.group(2), currency=currency)})"

    # Coin walks: "showed [Xx Yy] and won (N)" with no hand rank — PS uses collected.
    m = _SUMMARY_SHOWED_WON_BARE_RE.match(stripped)
    if m:
        return f"{m.group(1)} collected ({_format_amount(m.group(2), currency=currency)})"

    m = _SUMMARY_DIDNT_SHOW_RE.match(stripped)
    if m:
        return f"{m.group(1)} mucked"

    if stripped.startswith("Seat ") and ("collected (" in stripped or "won (" in stripped):
        return _SUMMARY_MONEY_RE.sub(
            lambda match: f"({_format_amount(match.group(1), currency=currency)})",
            stripped,
        )

    # Remaining money tokens (₮ from cash exports).
    if "₮" in stripped:
        stripped = stripped.replace("₮", currency if currency else "")

    return stripped


def normalize_coin_board_line(line: str) -> str:
    if not line.startswith("Board ["):
        return line

    inner = line[len("Board [") : -1] if line.endswith("]") else line[7:]
    inner = inner.replace("[ ", "[").replace(" ]", "]")
    inner = re.sub(r"\s+", " ", inner.strip())
    return f"Board [{inner}]"


def coin_postprocess(text: str) -> str:
    text = re.sub(r"(?m)^Game ended:.*\n", "", text)
    lines_out: list[str] = []
    for line in text.splitlines():
        if line.startswith("Board ["):
            line = normalize_coin_board_line(line)
        lines_out.append(line.rstrip())
    lines_out = normalize_coin_action_lines(lines_out)
    text = "\n".join(lines_out)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip() + "\n"
