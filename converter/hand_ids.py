HAND_PREFIX_POKER_PLANETS = "111111"
HAND_PREFIX_GGPOKER = "222222"
# Short prefix: ``333333`` + 10–12 digit Coin ids → 16–18 digits, which collide in
# IEEE-754 doubles (Hand2Note/JS). Keep total length ≤ 14 like GG/UP (12-digit) ids.
HAND_PREFIX_COINPOKER = "33"
HAND_PREFIX_UPPOKER = "444444"
HAND_PREFIX_ONEWIN = "55"
HAND_PREFIX_GG_CASH = "22"

_GG_ID_SOURCE_PREFIX = "5730"
_GG_ID_DISPLAY_PREFIX = "205730"


def poker_hand_suffix(raw_hand_id: str) -> str:
    suffix = raw_hand_id.strip()
    upper = suffix.upper()
    if upper.startswith("TM"):
        return suffix[2:]
    if upper.startswith("HD"):
        return suffix[2:]
    return suffix


def detect_poker_hand_room(raw_hand_id: str) -> str:
    """GGPoker: numeric ``TM5730…`` / cash ``HD…``; UPpoker: hex ``TM0ED72…``."""
    raw = raw_hand_id.strip()
    upper = raw.upper()
    if upper.startswith("HD") and upper[2:].isdigit():
        return "ggpoker_ok"
    suffix = poker_hand_suffix(raw_hand_id)
    if suffix.isdigit():
        return "ggpoker_ok"
    return "uppoker"


def prefixed_hand_id(prefix: str, raw_hand_id: str, *, strip_tm: bool = False) -> str:
    """Build display hand id: room prefix + suffix (optionally drop leading ``TM`` for GG)."""
    suffix = poker_hand_suffix(raw_hand_id) if strip_tm else raw_hand_id.strip()
    return f"{prefix}{suffix}"


def coin_display_hand_id(raw_hand_id: str) -> str:
    """Coin → PokerStars-style id that stays unique under float64 (≤14 digits)."""
    return prefixed_hand_id(HAND_PREFIX_COINPOKER, raw_hand_id)


def gg_display_hand_id(raw_hand_id: str) -> str:
    """Map GGPoker ``TM5730…`` / cash ``HD…`` ids to PokerStars-style ids for Hand2Note."""
    raw = raw_hand_id.strip()
    upper = raw.upper()
    # Cash: HD3035310615 → 223035310615 (≤14 digits).
    if upper.startswith("HD") and upper[2:].isdigit():
        return f"{HAND_PREFIX_GG_CASH}{upper[2:]}"
    suffix = poker_hand_suffix(raw_hand_id)
    if suffix.startswith(_GG_ID_SOURCE_PREFIX):
        return f"{_GG_ID_DISPLAY_PREFIX}{suffix[len(_GG_ID_SOURCE_PREFIX):]}"
    return prefixed_hand_id(HAND_PREFIX_GGPOKER, suffix)


def onewin_display_hand_id(raw_hand_id: str) -> str:
    """1Win numeric ids → prefixed PokerStars-style ids (≤14 digits for H2N/float64)."""
    digits = "".join(ch for ch in raw_hand_id.strip() if ch.isdigit()) or raw_hand_id.strip()
    max_suffix = 14 - len(HAND_PREFIX_ONEWIN)
    if digits.isdigit() and len(digits) > max_suffix:
        digits = digits[-max_suffix:]
    return prefixed_hand_id(HAND_PREFIX_ONEWIN, digits)


_UP_ID_MAX_DIGITS = 12
_UP_HAND_HEX_LEN = 7
_UP_TOURNAMENT_ID_MAX_LEN = 9
_UP_TOURNAMENT_MOD = 10**9
_UP_HAND_ID_BASE = 205_872_000_000


def up_display_hand_id(raw_hand_id: str) -> str:
    """Map UPpoker hex ids to 12-digit PokerStars-style ids (parallel to GG 205730…)."""
    suffix = poker_hand_suffix(raw_hand_id)
    head = suffix[:_UP_HAND_HEX_LEN]
    try:
        return str(_UP_HAND_ID_BASE + int(head, 16) % 1_000_000)
    except ValueError:
        pass
    try:
        digits = str(int(suffix, 16))
        if len(digits) > _UP_ID_MAX_DIGITS:
            digits = digits[-_UP_ID_MAX_DIGITS:]
        return digits
    except ValueError:
        return prefixed_hand_id(HAND_PREFIX_UPPOKER, suffix)


def up_display_tournament_id(raw_tid: str) -> str:
    """UP tournament ids are 19-digit snowflakes; compress to 9-digit Stars-style ids."""
    digits = raw_tid.strip()
    if not digits.isdigit():
        return digits
    if len(digits) <= _UP_TOURNAMENT_ID_MAX_LEN:
        return digits
    return str(int(digits) % _UP_TOURNAMENT_MOD)
