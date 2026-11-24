from __future__ import annotations

import re
from datetime import datetime

from converter.time_et import parse_header_timestamp

_SHOWDOWN_RE = re.compile(r"\*\*\* SHOWDOWN \*\*\*")
_DEALT_CARDS_EOL_RE = re.compile(
    r"\[(?:10|[2-9TJQKA])[cdhs](?:\s+(?:10|[2-9TJQKA])[cdhs])*\]\s*$",
    re.I,
)

_MONEY = r"[₮$€]?([\d,.]+)"
_SEAT_CHIPS_RE = re.compile(rf"^(Seat \d+: .+? \(){_MONEY}( in chips\))$")
_ANTE_RE = re.compile(rf"^(.+?): posts ante {_MONEY}$")
_ANTE_ALLIN_RE = re.compile(rf"^(.+?): posts ante {_MONEY} ALLIN$")
_SB_RE = re.compile(rf"^(.+?): posts small blind {_MONEY}$")
_SB_ALLIN_RE = re.compile(rf"^(.+?): posts small blind {_MONEY} ALLIN$")
_BB_RE = re.compile(rf"^(.+?): posts big blind {_MONEY}$")
_BB_ALLIN_RE = re.compile(rf"^(.+?): posts big blind {_MONEY} ALLIN$")
_RAISE_RE = re.compile(rf"^(.+?): raises {_MONEY} to {_MONEY}(.*)$")
_CALL_RE = re.compile(rf"^(.+?): calls {_MONEY}$")
_BET_RE = re.compile(rf"^(.+?): bets {_MONEY}(.*)$")
_ALLIN_RE = re.compile(rf"^(.+?): ALLIN {_MONEY}$")
_COLLECTED_RE = re.compile(rf"^(.+?) collected {_MONEY} from pot$")
_UNCALLED_RE = re.compile(rf"^Uncalled bet \({_MONEY}\) returned to (.+?)\s*$")
_RETURN_RE = re.compile(rf"^(.+?): RETURN {_MONEY}$")
_TOTAL_POT_RE = re.compile(rf"^Total pot {_MONEY}")
_SUMMARY_WON_ONLY_RE = re.compile(
    rf"^(Seat \d+: .+?(?: \([^)]+\))?) won \({_MONEY}\)\s*$"
)
_SUMMARY_SHOWED_WON_BARE_RE = re.compile(
    rf"^(Seat \d+: .+?) showed \[[^\]]+\] and won \({_MONEY}\)\s*$"
)
_SUMMARY_DIDNT_SHOW_RE = re.compile(
    r"^(Seat \d+: .+?) didn't show\s*$",
    re.I,
)
_SUMMARY_MONEY_RE = re.compile(rf"\({_MONEY}\)")
_TOURNAMENT_TITLE_RE = re.compile(r"^₮[\d.]+\s+")
_CURRENCY_PREFIX_RE = re.compile(r"[₮$€]")
_WS_RE = re.compile(r"\s+")
_GAME_ENDED_RE = re.compile(r"(?m)^Game ended:.*(?:\n|$)")
_DECIMAL_CHIP_RE = re.compile(r"(?<=[\s($€])\d+\.\d+")


def format_stakes_int(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def normalize_money(amount: str) -> str:
    """Strip thousands separators; keep a single decimal point when present."""
    if "," not in amount:
        return amount.strip()
    amount = amount.strip()
    if "." in amount:
        whole, frac = amount.rsplit(".", 1)
        return f"{whole.replace(',', '')}.{frac.replace(',', '')}"
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
    if amount and amount[0] in ("₮", "$", "€"):
        amount = _CURRENCY_PREFIX_RE.sub("", amount)
    cleaned = normalize_money(amount)
    if currency:
        return f"{currency}{cleaned}"
    return cleaned


def format_coin_body_line(line: str) -> str | None:
    """Tournament CPR_ path body lines: bare chip amounts (ASCII-safe for file import)."""
    return _format_body_line(line, currency="")


def format_ps_body_line(line: str) -> str | None:
    """PokerStars-style tournament path: bare chip amounts."""
    return _format_body_line(line, currency="")



def format_cash_body_line(line: str) -> str | None:
    """Cash games: CoinPoker ₮ amounts become ``$``."""
    return _format_body_line(line, currency="$")


_STREET_MARKERS = frozenset({"HOLE CARDS", "FLOP", "TURN", "RIVER", "SHOW DOWN", "SUMMARY"})
_STREET_LINE_RE = re.compile(r"^\*\*\* (.+?) \*\*\*")
_STREET_MARKER_RE = re.compile(
    r"^(?:FIRST|SECOND)\s+(FLOP|TURN|RIVER|SHOW\s*DOWN|SHOWDOWN)$"
    r"|^(HOLE CARDS|FLOP|TURN|RIVER|SHOW\s*DOWN|SHOWDOWN|SUMMARY)$",
    re.I,
)
_BETS_RE = re.compile(r"^(.+?): bets ([€$]?)([\d,.]+)(.*)$")
_RAISES_RE = re.compile(r"^(.+?): raises ([€$]?)([\d,.]+) to ([€$]?)([\d,.]+)(.*)$")
_CALLS_RE = re.compile(r"^(.+?): calls ([€$]?)([\d,.]+)(.*)$")
_BLIND_POST_RE = re.compile(
    rf"^(.+?): posts (?:small|big) blind {_MONEY}(?: and is all-in| ALLIN)?$"
)
_CASH_HEADER_BLINDS_RE = re.compile(
    r"Hold'?em\s+No\s+Limit\s+\(\s*[€$]?([\d,.]+)\s*/\s*[€$]?([\d,.]+)\s*\)",
    re.I,
)
_VOLUNTARY_ACTION_RE = re.compile(r"^.+?: (?:calls|raises|bets) ")


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
    if abs(amount - rounded) < 1e-6:
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


def _header_nominal_bb(first_line: str) -> float:
    """Extract nominal big blind from a converted hand header, or 0.0 if absent."""
    m = _LEVEL_BLINDS_RE.search(first_line)
    if m:
        return float(normalize_money(m.group(2)))
    m = _CASH_HEADER_BLINDS_RE.search(first_line)
    if m:
        return float(normalize_money(m.group(2)))
    return 0.0


def normalize_coin_action_lines(lines: list[str]) -> list[str]:
    """Fix ALLIN/bet lines so Hand2Note action stamps parse (raises/calls vs bets).

    A native ALLIN becomes ``bets <remaining chips> and is all-in`` in the
    formatting pass. Those chips are additional to the player's earlier
    contribution on this street, including a preflop blind.
    """
    out: list[str] = []
    append = out.append
    street: str | None = None
    # Seed preflop live wager with nominal BB from the header when present so a
    # dead or short big blind still classifies preflop short all-ins as calls
    # and computes raise increments against the nominal big blind.
    street_level = _header_nominal_bb(lines[0]) if lines else 0.0
    committed: dict[str, float] = {}
    preflop_voluntary = False

    for line in lines:
        if line and line[0] == "*":
            marker = _STREET_LINE_RE.match(line)
            if marker:
                name = _street_from_marker(marker.group(1))
                if name is not None:
                    street = name
                    if name != "HOLE CARDS":
                        street_level = 0.0
                        committed = {}
                        preflop_voluntary = False
                append(line)
                continue

        # Blinds are written before HOLE CARDS, but belong to the same round.
        # Antes do not count towards the live wager.
        if street is None and "posts " in line:
            blind = _BLIND_POST_RE.match(line)
            if blind:
                player, amount_raw = blind.groups()
                committed[player] = committed.get(player, 0.0) + float(normalize_money(amount_raw))
                street_level = max(street_level, committed[player])
                append(line)
                continue

        if street is None or street in ("SUMMARY", "SHOW DOWN"):
            append(line)
            continue

        if line.startswith("Uncalled bet ("):
            uncalled = _UNCALLED_RE.match(line)
            if uncalled:
                amount_raw, player = uncalled.groups()
                committed[player] = committed.get(player, 0.0) - float(normalize_money(amount_raw))
                street_level = max(committed.values(), default=0.0)
                append(line)
                continue

        if ": " not in line:
            append(line)
            continue

        if ": RETURN " in line:
            returned = _RETURN_RE.match(line)
            if returned:
                player, amount_raw = returned.groups()
                committed[player] = committed.get(player, 0.0) - float(normalize_money(amount_raw))
                street_level = max(committed.values(), default=0.0)
                append(line)
                continue

        is_preflop = street == "HOLE CARDS"

        if ": bets " in line:
            bets = _BETS_RE.match(line)
            if bets:
                player, symbol, amount_raw, tail = bets.groups()
                amount = float(normalize_money(amount_raw))
                suffix = " and is all-in" if "all-in" in tail else ""

                if suffix:
                    total = committed.get(player, 0.0) + amount
                    if total <= street_level + 0.005:
                        line = _fmt_call(player, amount, symbol, suffix)
                    elif is_preflop or street_level > 0:
                        line = _fmt_raise(player, total - street_level, total, symbol, suffix)
                    committed[player] = total
                    street_level = max(street_level, total)
                    preflop_voluntary = preflop_voluntary or is_preflop
                    append(line)
                    continue

                if street_level > 0:
                    if amount <= street_level + 0.005:
                        line = _fmt_call(player, amount, symbol, suffix)
                        committed[player] = committed.get(player, 0.0) + amount
                    else:
                        line = _fmt_raise(
                            player, amount - street_level, amount, symbol, suffix
                        )
                        committed[player] = amount
                        street_level = max(street_level, amount)
                    preflop_voluntary = preflop_voluntary or is_preflop
                elif is_preflop and not preflop_voluntary:
                    line = _fmt_raise(player, amount, amount, symbol, suffix)
                    committed[player] = amount
                    street_level = max(street_level, amount)
                    preflop_voluntary = True
                else:
                    committed[player] = amount
                    street_level = amount
                    if is_preflop:
                        preflop_voluntary = True
                append(line)
                continue

        if ": raises " in line:
            raises = _RAISES_RE.match(line)
            if raises:
                player, _inc_sym, _inc_raw, total_sym, total_raw, tail = raises.groups()
                if "all-in" not in tail and "ALLIN" in tail:
                    line = (
                        f"{player}: raises {raises.group(2)}{raises.group(3)} to "
                        f"{total_sym}{total_raw} and is all-in"
                    )
                committed[player] = float(normalize_money(total_raw))
                street_level = max(street_level, committed[player])
                if is_preflop:
                    preflop_voluntary = True
                append(line)
                continue

        if ": calls " in line:
            calls = _CALLS_RE.match(line)
            if calls:
                player = calls.group(1)
                amount = float(normalize_money(calls.group(3)))
                committed[player] = committed.get(player, 0.0) + amount
                street_level = max(street_level, committed[player])
                if is_preflop:
                    preflop_voluntary = True
                append(line)
                continue

        append(line)

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
_CHIP_AMT = r"[€$]?([\d,.]+)"
_SEAT_STACK_RE = re.compile(
    rf"^(Seat \d+: )(.+?) \({_CHIP_AMT} in chips\)$",
)
_POST_SB_LINE_RE = re.compile(
    rf"^(.+?): posts small blind {_CHIP_AMT}( and is all-in)?$"
)
_POST_BB_AI_LINE_RE = re.compile(
    r"^(.+?): posts big blind ([€$]?)([\d,.]+) and is all-in$"
)
_POST_ANTE_LINE_RE = re.compile(
    rf"^(.+?): posts the ante {_CHIP_AMT}( and is all-in)?$"
)
_UNCALLED_LINE_RE = re.compile(
    rf"^Uncalled bet \({_CHIP_AMT}\) returned to (.+?)\s*$"
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
    if "posts big blind " not in text or " and is all-in" not in text:
        return text

    lines = text.splitlines()
    if len(lines) < 8:
        return text

    level = _LEVEL_BLINDS_RE.search(lines[0])
    if not level:
        return text
    level_sb = float(normalize_money(level.group(1)))
    level_bb = float(normalize_money(level.group(2)))

    sb_i = bb_i = None
    sb_m = bb_m = None
    for i, line in enumerate(lines):
        if sb_i is None and ": posts small blind " in line:
            m = _POST_SB_LINE_RE.match(line)
            if m:
                sb_i = i
                sb_m = m
        if bb_i is None and ": posts big blind " in line:
            m = _POST_BB_AI_LINE_RE.match(line)
            if m:
                bb_i = i
                bb_m = m
    if sb_i is None or bb_i is None or sb_m is None or bb_m is None:
        return text

    sb_name, sb_post = sb_m.group(1), float(normalize_money(sb_m.group(2)))
    bb_name, cur, bb_post = bb_m.group(1), bb_m.group(2), float(normalize_money(bb_m.group(3)))

    if bb_post + 0.001 >= level_bb:
        return text

    has_flop = any(line.startswith("*** FLOP ***") for line in lines)
    has_voluntary = any(_VOLUNTARY_ACTION_RE.match(line) for line in lines)
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
        lines[seat_i] = (
            f"{seat_m.group(1)}{bb_name} ({cur}{_coin_amt_token(need_stack)} in chips)"
        )
        lines[bb_i] = f"{bb_name}: posts big blind {cur}{_coin_amt_token(level_bb)}"
        if uncalled_i is not None:
            lines[uncalled_i] = (
                f"Uncalled bet ({cur}{_coin_amt_token(level_bb - sb_post)}) "
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
        bb_tok = f"{cur}{_coin_amt_token(bb_post)}"
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
    """Round fractional chip amounts in the body; keep header and nicknames intact."""

    def repl(match: re.Match[str]) -> str:
        return str(int(round(float(match.group(0)))))

    lines = text.splitlines()
    if not lines:
        return text
    out = [lines[0]]
    append = out.append
    for line in lines[1:]:
        if "." in line:
            append(_DECIMAL_CHIP_RE.sub(repl, line))
        else:
            append(line)
    return "\n".join(out)


def _format_body_line(line: str, *, currency: str) -> str | None:
    stripped = line.rstrip()
    if not stripped:
        return ""

    if stripped.startswith("Dealt to "):
        if not _DEALT_CARDS_EOL_RE.search(stripped):
            return None
        return stripped

    if stripped[0] == "*":
        if "*** SHOWDOWN ***" in stripped:
            return _SHOWDOWN_RE.sub("*** SHOW DOWN ***", stripped)
        return stripped

    if stripped.startswith("Seat "):
        m = _SEAT_CHIPS_RE.match(stripped)
        if m:
            return f"{m.group(1)}{_format_amount(m.group(2), currency=currency)}{m.group(3)}"
        if " won (" in stripped:
            m = _SUMMARY_WON_ONLY_RE.match(stripped)
            if m:
                return f"{m.group(1)} collected ({_format_amount(m.group(2), currency=currency)})"
            m = _SUMMARY_SHOWED_WON_BARE_RE.match(stripped)
            if m:
                return f"{m.group(1)} collected ({_format_amount(m.group(2), currency=currency)})"
            return _SUMMARY_MONEY_RE.sub(
                lambda match: f"({_format_amount(match.group(1), currency=currency)})",
                stripped,
            )
        if "collected (" in stripped:
            return _SUMMARY_MONEY_RE.sub(
                lambda match: f"({_format_amount(match.group(1), currency=currency)})",
                stripped,
            )
        if "didn't show" in stripped or "Didn't show" in stripped:
            m = _SUMMARY_DIDNT_SHOW_RE.match(stripped)
            if m:
                return f"{m.group(1)} mucked"
        if "₮" in stripped:
            return stripped.replace("₮", currency if currency else "")
        return stripped

    if ": " in stripped:
        if ": posts " in stripped:
            # Blind/ante ALLIN: other working converters emit the short post only (no
            # "and is all-in"). H2N NullRefs / drops the "posts … and is all-in" form.
            if stripped.endswith(" ALLIN"):
                m = _ANTE_ALLIN_RE.match(stripped)
                if m:
                    return (
                        f"{m.group(1)}: posts the ante "
                        f"{_format_amount(m.group(2), currency=currency)}"
                    )
                m = _SB_ALLIN_RE.match(stripped)
                if m:
                    return (
                        f"{m.group(1)}: posts small blind "
                        f"{_format_amount(m.group(2), currency=currency)}"
                    )
                m = _BB_ALLIN_RE.match(stripped)
                if m:
                    return (
                        f"{m.group(1)}: posts big blind "
                        f"{_format_amount(m.group(2), currency=currency)}"
                    )
            else:
                m = _ANTE_RE.match(stripped)
                if m:
                    return (
                        f"{m.group(1)}: posts the ante "
                        f"{_format_amount(m.group(2), currency=currency)}"
                    )
                m = _SB_RE.match(stripped)
                if m:
                    return (
                        f"{m.group(1)}: posts small blind "
                        f"{_format_amount(m.group(2), currency=currency)}"
                    )
                m = _BB_RE.match(stripped)
                if m:
                    return (
                        f"{m.group(1)}: posts big blind "
                        f"{_format_amount(m.group(2), currency=currency)}"
                    )
        elif ": ALLIN " in stripped:
            m = _ALLIN_RE.match(stripped)
            if m:
                return (
                    f"{m.group(1)}: bets {_format_amount(m.group(2), currency=currency)} and is all-in"
                )
        elif ": raises " in stripped:
            m = _RAISE_RE.match(stripped)
            if m:
                tail = m.group(4)
                if "all-in" not in tail and "ALLIN" in tail:
                    tail = " and is all-in"
                return (
                    f"{m.group(1)}: raises {_format_amount(m.group(2), currency=currency)} to "
                    f"{_format_amount(m.group(3), currency=currency)}{tail}"
                )
        elif ": calls " in stripped:
            m = _CALL_RE.match(stripped)
            if m:
                return f"{m.group(1)}: calls {_format_amount(m.group(2), currency=currency)}"
        elif ": bets " in stripped:
            m = _BET_RE.match(stripped)
            if m:
                return f"{m.group(1)}: bets {_format_amount(m.group(2), currency=currency)}{m.group(3)}"
        elif ": RETURN " in stripped:
            m = _RETURN_RE.match(stripped)
            if m:
                return (
                    f"Uncalled bet ({_format_amount(m.group(2), currency=currency)}) "
                    f"returned to {m.group(1)}"
                )
        if "₮" in stripped:
            stripped = stripped.replace("₮", currency if currency else "")
        return stripped

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

    if stripped.startswith("Uncalled bet "):
        m = _UNCALLED_RE.match(stripped)
        if m:
            return (
                f"Uncalled bet ({_format_amount(m.group(1), currency=currency)}) "
                f"returned to {m.group(2)}"
            )

    if " collected " in stripped:
        m = _COLLECTED_RE.match(stripped)
        if m:
            return (
                f"{m.group(1)} collected {_format_amount(m.group(2), currency=currency)} from pot"
            )

    # Remaining money tokens (₮ from cash exports).
    if "₮" in stripped:
        stripped = stripped.replace("₮", currency if currency else "")

    return stripped


def normalize_coin_board_line(line: str) -> str:
    if not line.startswith("Board ["):
        return line

    inner = line[len("Board [") : -1] if line.endswith("]") else line[7:]
    if "[ " in inner:
        inner = inner.replace("[ ", "[")
    if " ]" in inner:
        inner = inner.replace(" ]", "]")
    inner = _WS_RE.sub(" ", inner.strip())
    return f"Board [{inner}]"


def _strip_unshown_showdown(text: str) -> str:
    """Match H2N Coin-module layout: no SHOW DOWN unless someone shows cards."""
    if ": shows [" in text:
        return text
    lines_out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {"*** SHOW DOWN ***", "*** SHOWDOWN ***"}:
            continue
        if stripped in {"Board []", "Board [ ]"}:
            continue
        lines_out.append(line)
    return "\n".join(lines_out)


def coin_postprocess(text: str) -> str:
    """Finalize CPR_ tournament hands for Hand2Note's CoinPoker file import.

    Official Hand2NoteHh Coin exports: integer chips, and no ``SHOW DOWN`` unless
    someone shows. Unshown SHOW DOWN + fractional actions are where the text
    importer throws ``BiggestBlind is zero`` / silent BuildStats drops.
    """
    if "Game ended:" in text:
        text = _GAME_ENDED_RE.sub("", text)
    lines_out: list[str] = []
    for line in text.splitlines():
        if line.startswith("Board ["):
            line = normalize_coin_board_line(line)
        lines_out.append(line.rstrip())
    text = normalize_coin_hand_actions("\n".join(lines_out))
    text = _integerize_hand_decimals(text)
    text = _strip_unshown_showdown(text)
    return text.rstrip() + "\n"
