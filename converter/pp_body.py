from __future__ import annotations

import re

_SB_POST_RE = re.compile(r"^(.+?): posts small blind ([\d,]+)(.*)")
_BB_POST_RE = re.compile(r"^(.+?): posts big blind ([\d,]+)(.*)")
_PREFLOP_ACTION_RE = re.compile(
    r"^(.+?): (folds|checks|calls|raises|bets|all-in|is all-in)",
    re.I,
)
_SITS_OUT_RE = re.compile(r"^(.+?): sits out\s*$", re.I)
_JOIN_TABLE_RE = re.compile(r"^.+ joins the table at seat #\d+\s*$", re.I)
_TIMED_OUT_RE = re.compile(r"^.+ has timed out\s*$", re.I)
_MASKED_BRACKET_RE = re.compile(r"\[[^\]]*##[^\]]*\]")
_SEAT_DECL_RE = re.compile(r"^Seat (\d+): (.+?) \([^)]*in chips\)\s*$")
_SUMMARY_BARE_SEAT_RE = re.compile(r"^(Seat \d+: \S+)\s*$")
_SUMMARY_SEAT_PREFIX_RE = re.compile(r"^Seat (\d+): (.+?)\s*$")


def normalize_pp_body_lines(lines: list[str]) -> list[str]:
    """Fix PokerPlanets body quirks that break Hand2Note BuildStats."""
    cleaned: list[str] = []
    in_betting = False
    for line in lines:
        s = line.strip()
        if s.startswith("*** HOLE CARDS ***"):
            in_betting = True
        elif s.startswith("*** SHOW DOWN ***") or s.startswith("*** SHOWDOWN ***") or s.startswith("*** SUMMARY ***"):
            in_betting = False
        if _is_noise_line(s):
            continue
        if in_betting and "sits out" in s.lower():
            line = _fix_sits_out(line)
        if "##" in line:
            line = _fix_masked_cards(line)
        cleaned.append(line)

    lines = _ensure_small_blind_post(cleaned)
    lines = _insert_implicit_blind_folds(lines)
    lines = _fix_bare_summary_seats(lines)
    return lines


def _fix_sits_out(line: str) -> str:
    m = _SITS_OUT_RE.match(line.strip())
    if m:
        return f"{m.group(1)}: folds"
    return line


def _is_noise_line(stripped: str) -> bool:
    if not stripped:
        return False
    if "joins the table" in stripped or "has timed out" in stripped:
        return bool(_JOIN_TABLE_RE.match(stripped) or _TIMED_OUT_RE.match(stripped))
    return False


def _fix_masked_cards(line: str) -> str:
    return _MASKED_BRACKET_RE.sub(lambda m: m.group(0).replace("##", "Xx"), line)


def _ensure_small_blind_post(lines: list[str]) -> list[str]:
    hole_idx = _index_of_street(lines, "HOLE CARDS")
    if hole_idx is None:
        return lines

    posting = lines[:hole_idx]
    if any(_SB_POST_RE.match(line.strip()) for line in posting):
        return lines

    out: list[str] = []
    inserted = False
    for idx, line in enumerate(lines):
        if not inserted and idx < hole_idx:
            bb_m = _BB_POST_RE.match(line.strip())
            if bb_m:
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
    """Return blind posters who are still live (not already all-in on the blind post)."""
    posters: list[str] = []
    allin_posters: set[str] = set()
    for line in posting_lines:
        s = line.strip()
        for pattern in (_SB_POST_RE, _BB_POST_RE):
            m = pattern.match(s)
            if not m:
                continue
            name = m.group(1)
            if "all-in" in m.group(3).lower():
                allin_posters.add(name)
            if name not in posters:
                posters.append(name)
    return [name for name in posters if name not in allin_posters]


def _fix_bare_summary_seats(lines: list[str]) -> list[str]:
    summary_idx = _index_of_street(lines, "SUMMARY")
    if summary_idx is None:
        return lines

    known_seats: dict[str, str] = {}
    for line in lines[:summary_idx]:
        dm = _SEAT_DECL_RE.match(line.strip())
        if dm:
            known_seats[dm.group(1)] = dm.group(2)

    out = list(lines[: summary_idx + 1])
    for line in lines[summary_idx + 1 :]:
        s = line.strip()
        m = _SUMMARY_BARE_SEAT_RE.match(s)
        if m:
            out.append(f"{m.group(1)} folded before Flop")
            continue
        sm = _SUMMARY_SEAT_PREFIX_RE.match(s)
        if sm and known_seats.get(sm.group(1)) == sm.group(2):
            out.append(f"Seat {sm.group(1)}: {sm.group(2)} folded before Flop")
            continue
        out.append(line)
    return out


def _index_of_street(lines: list[str], street: str) -> int | None:
    marker = f"*** {street} ***"
    for idx, line in enumerate(lines):
        if line.strip().startswith(marker):
            return idx
    return None
