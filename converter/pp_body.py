from __future__ import annotations

import re

_SB_POST_RE = re.compile(r"^(.+?): posts small blind (\d+)")
_BB_POST_RE = re.compile(r"^(.+?): posts big blind (\d+)")
_PREFLOP_ACTION_RE = re.compile(
    r"^(.+?): (folds|checks|calls|raises|bets|all-in|is all-in)",
    re.I,
)
_SITS_OUT_RE = re.compile(r"^(\S+): sits out\s*$", re.I)
_JOIN_TABLE_RE = re.compile(r"^.+ joins the table at seat #\d+\s*$", re.I)
_TIMED_OUT_RE = re.compile(r"^.+ has timed out\s*$", re.I)
_MASKED_CARD_RE = re.compile(r"(\[)([^\]]*?)##([^\]]*?)(\])")
_SUMMARY_BARE_SEAT_RE = re.compile(r"^(Seat \d+: \S+)\s*$")


def normalize_pp_body_lines(lines: list[str]) -> list[str]:
    """Fix PokerPlanets body quirks that break Hand2Note BuildStats."""
    lines = [_fix_sits_out(line) for line in lines]
    lines = [line for line in lines if not _is_noise_line(line)]
    lines = [_fix_masked_cards(line) for line in lines]
    lines = _ensure_small_blind_post(lines)
    lines = _insert_implicit_blind_folds(lines)
    lines = _fix_bare_summary_seats(lines)
    return lines


def _fix_sits_out(line: str) -> str:
    m = _SITS_OUT_RE.match(line.strip())
    if m:
        return f"{m.group(1)}: folds"
    return line


def _is_noise_line(line: str) -> bool:
    s = line.strip()
    return bool(_JOIN_TABLE_RE.match(s) or _TIMED_OUT_RE.match(s))


def _fix_masked_cards(line: str) -> str:
    return _MASKED_CARD_RE.sub(r"\1\2Xx\4", line)


def _ensure_small_blind_post(lines: list[str]) -> list[str]:
    hole_idx = _index_of_street(lines, "HOLE CARDS")
    if hole_idx is None:
        return lines

    posting = lines[:hole_idx]
    if any(_SB_POST_RE.match(line.strip()) for line in posting):
        return lines

    out: list[str] = []
    inserted = False
    for line in lines:
        bb_m = _BB_POST_RE.match(line.strip())
        if bb_m and not inserted:
            out.append(f"{bb_m.group(1)}: posts small blind 0")
            inserted = True
        out.append(line)
    return out


def _insert_implicit_blind_folds(lines: list[str]) -> list[str]:
    hole_idx = _index_of_street(lines, "HOLE CARDS")
    flop_idx = _index_of_street(lines, "FLOP")
    if hole_idx is None or flop_idx is None:
        return lines

    blind_posters = _blind_posters(lines[:hole_idx])
    if not blind_posters:
        return lines

    preflop = lines[hole_idx + 1 : flop_idx]
    acted = {m.group(1) for line in preflop for m in [_PREFLOP_ACTION_RE.match(line.strip())] if m}
    missing = [name for name in blind_posters if name not in acted]
    if not missing:
        return lines

    folds = [f"{name}: folds" for name in missing]
    return lines[:flop_idx] + folds + lines[flop_idx:]


def _blind_posters(posting_lines: list[str]) -> list[str]:
    posters: list[str] = []
    for line in posting_lines:
        for pattern in (_SB_POST_RE, _BB_POST_RE):
            m = pattern.match(line.strip())
            if m and m.group(1) not in posters:
                posters.append(m.group(1))
    return posters


def _fix_bare_summary_seats(lines: list[str]) -> list[str]:
    summary_idx = _index_of_street(lines, "SUMMARY")
    if summary_idx is None:
        return lines

    out = list(lines[: summary_idx + 1])
    for line in lines[summary_idx + 1 :]:
        m = _SUMMARY_BARE_SEAT_RE.match(line.strip())
        if m:
            out.append(f"{m.group(1)} folded before Flop")
        else:
            out.append(line)
    return out


def _index_of_street(lines: list[str], street: str) -> int | None:
    marker = f"*** {street} ***"
    for idx, line in enumerate(lines):
        if line.strip().startswith(marker):
            return idx
    return None
