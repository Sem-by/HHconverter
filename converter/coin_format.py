from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_SHOWDOWN_RE = re.compile(r"\*\*\* SHOWDOWN \*\*\*")
_EMPTY_DEALT_RE = re.compile(r"^Dealt to \S+\s*$")

_SEAT_CHIPS_RE = re.compile(r"^(Seat \d+: \S+ \()([\d,.]+)( in chips\))$")
_ANTE_RE = re.compile(r"^(\S+): posts ante ([\d,.]+)$")
_SB_RE = re.compile(r"^(\S+): posts small blind ([\d,.]+)$")
_BB_RE = re.compile(r"^(\S+): posts big blind ([\d,.]+)$")
_RAISE_RE = re.compile(r"^(\S+): raises ([\d,.]+) to ([\d,.]+)(.*)$")
_CALL_RE = re.compile(r"^(\S+): calls ([\d,.]+)$")
_BET_RE = re.compile(r"^(\S+): bets ([\d,.]+)(.*)$")
_ALLIN_RE = re.compile(r"^(\S+): ALLIN ([\d,.]+)$")
_COLLECTED_RE = re.compile(r"^(\S+) collected ([\d,.]+) from pot$")
_UNCALLED_RE = re.compile(r"^Uncalled bet \(([\d,.]+)\) returned to (\S+)$")
_RETURN_RE = re.compile(r"^(\S+): RETURN ([\d,.]+)$")
_TOTAL_POT_RE = re.compile(r"^Total pot ([\d,.]+)")
_SUMMARY_WON_ONLY_RE = re.compile(r"^(Seat \d+: \S+(?: \([^)]+\))?) won \(([\d,.]+)\)\s*$")
_SUMMARY_MONEY_RE = re.compile(r"\(([\d,.]+)\)")
_TOURNAMENT_TITLE_RE = re.compile(r"^₮[\d.]+\s+")
_COIN_TIME_RE = re.compile(
    r"^(\d{4}/\d{2}/\d{2}) (\d{1,2}):(\d{2}):(\d{2}) \+(\d{1,2})$",
)


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
    m = _COIN_TIME_RE.match(time_part)
    if m:
        date_s, hour, minute, second, offset_h = m.groups()
        dt = datetime.strptime(
            f"{date_s} {int(hour):02d}:{minute}:{second}",
            "%Y/%m/%d %H:%M:%S",
        ).replace(tzinfo=timezone(timedelta(hours=int(offset_h))))
        utc = dt.astimezone(timezone.utc)
        return format_h2n_utc_datetime(utc)
    if time_part.upper().endswith("UTC"):
        return time_part
    return f"{time_part} UTC"


def _format_amount(amount: str, *, use_euro: bool) -> str:
    normalized = normalize_money(amount)
    if use_euro:
        return euro_amount(amount)
    return normalized


def format_coin_body_line(line: str) -> str | None:
    return _format_body_line(line, use_euro=True)


def format_ps_body_line(line: str) -> str | None:
    return _format_body_line(line, use_euro=False)


def _format_body_line(line: str, *, use_euro: bool) -> str | None:
    stripped = line.rstrip()
    if not stripped:
        return ""

    if _EMPTY_DEALT_RE.match(stripped):
        return None

    stripped = _SHOWDOWN_RE.sub("*** SHOW DOWN ***", stripped)

    m = _SEAT_CHIPS_RE.match(stripped)
    if m:
        return f"{m.group(1)}{_format_amount(m.group(2), use_euro=use_euro)}{m.group(3)}"

    m = _ANTE_RE.match(stripped)
    if m:
        return f"{m.group(1)}: posts the ante {_format_amount(m.group(2), use_euro=use_euro)}"

    m = _SB_RE.match(stripped)
    if m:
        return f"{m.group(1)}: posts small blind {_format_amount(m.group(2), use_euro=use_euro)}"

    m = _BB_RE.match(stripped)
    if m:
        return f"{m.group(1)}: posts big blind {_format_amount(m.group(2), use_euro=use_euro)}"

    m = _ALLIN_RE.match(stripped)
    if m:
        return (
            f"{m.group(1)}: bets {_format_amount(m.group(2), use_euro=use_euro)} and is all-in"
        )

    m = _RAISE_RE.match(stripped)
    if m:
        tail = m.group(4)
        if "all-in" not in tail and "ALLIN" in tail:
            tail = " and is all-in"
        return (
            f"{m.group(1)}: raises {_format_amount(m.group(2), use_euro=use_euro)} to "
            f"{_format_amount(m.group(3), use_euro=use_euro)}{tail}"
        )

    m = _CALL_RE.match(stripped)
    if m:
        return f"{m.group(1)}: calls {_format_amount(m.group(2), use_euro=use_euro)}"

    m = _BET_RE.match(stripped)
    if m:
        return f"{m.group(1)}: bets {_format_amount(m.group(2), use_euro=use_euro)}{m.group(3)}"

    m = _COLLECTED_RE.match(stripped)
    if m:
        return (
            f"{m.group(1)} collected {_format_amount(m.group(2), use_euro=use_euro)} from pot"
        )

    m = _UNCALLED_RE.match(stripped)
    if m:
        return (
            f"Uncalled bet ({_format_amount(m.group(1), use_euro=use_euro)}) "
            f"returned to {m.group(2)}"
        )

    m = _RETURN_RE.match(stripped)
    if m:
        return (
            f"Uncalled bet ({_format_amount(m.group(2), use_euro=use_euro)}) "
            f"returned to {m.group(1)}"
        )

    if stripped.startswith("Total pot"):
        m = _TOTAL_POT_RE.match(stripped)
        if m:
            pot = _format_amount(m.group(1), use_euro=use_euro)
            rake = "€0" if use_euro else "0"
            return f"Total pot {pot} | Rake {rake}"

    m = _SUMMARY_WON_ONLY_RE.match(stripped)
    if m:
        return f"{m.group(1)} collected ({_format_amount(m.group(2), use_euro=use_euro)})"

    if stripped.startswith("Seat ") and ("collected (" in stripped or "won (" in stripped):
        return _SUMMARY_MONEY_RE.sub(
            lambda match: f"({_format_amount(match.group(1), use_euro=use_euro)})",
            stripped,
        )

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
    text = "\n".join(lines_out)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip() + "\n"
